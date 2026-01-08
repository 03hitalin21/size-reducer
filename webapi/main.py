import asyncio
import logging
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import load_settings
from app.jobs import create_job, get_job
from app.logging import set_request_id, setup_logging
from app.utils import (
    build_download_url,
    ensure_dir,
    generate_uuid,
    is_probable_video,
    safe_extension,
)
from webapi.rate_limit import RateLimiter

settings = load_settings()
setup_logging()
logger = logging.getLogger("webapi")

uploads_dir = Path(settings.storage_path) / "uploads"
outputs_dir = Path(settings.storage_path) / "outputs"
ensure_dir(uploads_dir)
ensure_dir(outputs_dir)

rate_limiter = RateLimiter(settings.rate_limit_per_min, 60)

app = FastAPI()


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    set_request_id(request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/")
async def root():
    return RedirectResponse(url="/web/")


@app.post("/api/upload")
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
    profile: str = Form("balanced"),
):
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.allow(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    if profile not in {"small", "balanced", "hq"}:
        raise HTTPException(status_code=400, detail="Invalid profile")

    if not is_probable_video(file.filename, file.content_type):
        raise HTTPException(status_code=400, detail="Unsupported file type")

    ext = safe_extension(file.filename) or ".bin"
    input_name = f"{generate_uuid()}{ext}"
    input_path = uploads_dir / input_name

    size_limit = settings.max_upload_mb * 1024 * 1024
    written = 0

    try:
        with open(input_path, "wb") as handle:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > size_limit:
                    raise HTTPException(status_code=413, detail="File too large")
                handle.write(chunk)
    except HTTPException:
        if input_path.exists():
            input_path.unlink()
        raise
    except Exception as exc:
        if input_path.exists():
            input_path.unlink()
        raise HTTPException(status_code=500, detail="Upload failed") from exc
    finally:
        await file.close()

    job = await asyncio.to_thread(
        create_job,
        settings.sqlite_path,
        source="web",
        user_id=client_ip,
        chat_id=None,
        input_path=str(input_path),
        profile=profile,
        input_bytes=written,
    )

    logger.info("job_created", extra={"job_id": job["id"]})
    return {"job_id": job["id"]}


@app.get("/api/status/{job_id}")
async def job_status(job_id: str):
    job = await asyncio.to_thread(get_job, settings.sqlite_path, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    download_url = None
    if job["status"] == "done":
        download_url = build_download_url(
            settings.base_url, job["id"], job["download_token"]
        )

    return {
        "status": job["status"],
        "progress": job["progress"],
        "error": job["error_message"],
        "output_bytes": job["output_bytes"],
        "download_url": download_url,
    }


@app.get("/api/download/{job_id}")
async def download_job(job_id: str, token: str):
    job = await asyncio.to_thread(get_job, settings.sqlite_path, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "done":
        raise HTTPException(status_code=404, detail="Job not ready")
    if token != job["download_token"]:
        raise HTTPException(status_code=403, detail="Invalid token")

    output_path = job.get("output_path")
    if not output_path or not os.path.exists(output_path):
        raise HTTPException(status_code=404, detail="Output missing")

    return FileResponse(
        output_path,
        media_type="video/mp4",
        filename=f"{job_id}.mp4",
    )


static_dir = Path(__file__).with_name("static")
app.mount("/web", StaticFiles(directory=static_dir, html=True), name="web")
