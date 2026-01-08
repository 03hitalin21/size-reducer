import asyncio
import json
import logging
import os
import subprocess
import time
from pathlib import Path

from telegram import Bot

from app.config import load_settings
from app.jobs import lock_next_job, update_job
from app.logging import setup_logging
from app.media import parse_ffprobe_json, parse_timecode
from app.utils import build_download_url, ensure_dir

logger = logging.getLogger("worker")


def run_ffprobe(input_path: str) -> dict:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        input_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"ffprobe failed: {detail}")
    payload = json.loads(result.stdout)
    parsed = parse_ffprobe_json(payload)
    if not parsed["has_video"]:
        raise RuntimeError("No video stream detected")
    return parsed


def build_ffmpeg_cmd(
    input_path: str,
    output_path: str,
    profile: str,
    width: int,
    height: int,
) -> list[str]:
    cmd = ["ffmpeg", "-y", "-i", input_path]

    filters = []
    if profile == "small":
        if height > 720:
            target_height = 720
        elif height > 480:
            target_height = 480
        else:
            target_height = height
        if target_height < height:
            filters.append(f"scale=-2:{target_height}")
        video_opts = ["-c:v", "libx264", "-b:v", "1000k", "-maxrate", "1200k", "-bufsize", "2000k"]
        audio_opts = ["-c:a", "aac", "-b:a", "96k"]
    elif profile == "balanced":
        target_height = 720 if height > 720 else height
        if target_height < height:
            filters.append(f"scale=-2:{target_height}")
        video_opts = ["-c:v", "libx264", "-b:v", "1600k", "-maxrate", "2000k", "-bufsize", "3000k"]
        audio_opts = ["-c:a", "aac", "-b:a", "128k"]
    else:
        target_height = 1080 if height > 1080 else height
        if target_height < height:
            filters.append(f"scale=-2:{target_height}")
        video_opts = ["-c:v", "libx264", "-crf", "23", "-preset", "medium"]
        audio_opts = ["-c:a", "aac", "-b:a", "128k"]

    if filters:
        cmd += ["-vf", ",".join(filters)]

    cmd += (
        video_opts
        + audio_opts
        + ["-movflags", "+faststart", "-progress", "pipe:1", "-nostats", "-v", "error", output_path]
    )
    return cmd


def run_ffmpeg(cmd: list[str], duration: float, on_progress) -> None:
    last_percent = -1
    last_update = 0.0
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )
    if not proc.stdout:
        raise RuntimeError("Failed to capture ffmpeg progress")

    for line in proc.stdout:
        line = line.strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        out_time = None
        if key == "out_time_ms":
            try:
                out_time = int(value) / 1_000_000.0
            except ValueError:
                out_time = None
        elif key == "out_time":
            out_time = parse_timecode(value)
        elif key == "progress" and value == "end":
            out_time = duration

        if out_time is not None and duration > 0:
            percent = min(100, int((out_time / duration) * 100))
            now = time.monotonic()
            if percent != last_percent and now - last_update > 0.5:
                on_progress(percent)
                last_percent = percent
                last_update = now

    return_code = proc.wait()
    if return_code != 0:
        raise RuntimeError("ffmpeg failed")


def notify_telegram(job: dict, settings, output_path: str, output_bytes: int) -> None:
    if not settings.telegram_bot_token:
        return
    if not job.get("chat_id"):
        return

    async def _send() -> None:
        bot = Bot(token=settings.telegram_bot_token)
        if output_bytes <= settings.max_telegram_send_mb * 1024 * 1024:
            try:
                with open(output_path, "rb") as handle:
                    await bot.send_video(
                        chat_id=job["chat_id"],
                        video=handle,
                        supports_streaming=True,
                        caption=f"Job {job['id']} complete.",
                    )
                return
            except Exception:
                logger.warning("telegram_send_failed", extra={"job_id": job["id"]})

        download_url = build_download_url(
            settings.base_url, job["id"], job["download_token"]
        )
        try:
            await bot.send_message(
                chat_id=job["chat_id"],
                text=f"Your video is ready: {download_url}",
            )
        except Exception:
            logger.warning("telegram_link_failed", extra={"job_id": job["id"]})

    try:
        asyncio.run(_send())
    except Exception:
        logger.warning("telegram_notify_exception", extra={"job_id": job["id"]})


def process_job(job: dict, settings) -> None:
    job_id = job["id"]
    input_path = job["input_path"]
    output_dir = Path(settings.storage_path) / "outputs"
    ensure_dir(output_dir)

    if not os.path.exists(input_path):
        update_job(
            settings.sqlite_path,
            job_id,
            status="error",
            error_message="Input file missing",
        )
        return

    output_path = str(output_dir / f"{job_id}.mp4")

    try:
        probe = run_ffprobe(input_path)
        duration = probe["duration"]
        if duration <= 0:
            raise RuntimeError("Unable to determine duration")
        if duration > settings.max_duration_seconds:
            update_job(
                settings.sqlite_path,
                job_id,
                status="error",
                error_message="Duration exceeds limit",
                duration_seconds=int(duration),
            )
            return

        cmd = build_ffmpeg_cmd(
            input_path,
            output_path,
            job.get("profile", "balanced"),
            probe["width"],
            probe["height"],
        )

        def _progress(percent: int) -> None:
            update_job(settings.sqlite_path, job_id, progress=percent)

        run_ffmpeg(cmd, duration, _progress)

        output_bytes = os.path.getsize(output_path)
        update_job(
            settings.sqlite_path,
            job_id,
            status="done",
            output_path=output_path,
            output_bytes=output_bytes,
            duration_seconds=int(duration),
            progress=100,
        )

        if job.get("source") == "telegram":
            notify_telegram(job, settings, output_path, output_bytes)

    except Exception as exc:
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass
        update_job(
            settings.sqlite_path,
            job_id,
            status="error",
            error_message=str(exc),
        )
        logger.exception("job_failed", extra={"job_id": job_id})


def main() -> None:
    settings = load_settings()
    setup_logging()
    ensure_dir(Path(settings.storage_path) / "uploads")
    ensure_dir(Path(settings.storage_path) / "outputs")

    logger.info("worker_started")

    while True:
        job = lock_next_job(settings.sqlite_path)
        if not job:
            time.sleep(1)
            continue
        logger.info("job_locked", extra={"job_id": job["id"]})
        process_job(job, settings)


if __name__ == "__main__":
    main()