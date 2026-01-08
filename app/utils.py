import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

_SAFE_EXT_RE = re.compile(r"^[a-z0-9]{1,8}$")


def utcnow() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def ensure_dir(path: str | Path) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def generate_uuid() -> str:
    return str(uuid.uuid4())


def safe_extension(filename: str | None) -> str:
    if not filename:
        return ""
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    if not ext:
        return ""
    if not _SAFE_EXT_RE.match(ext):
        return ""
    return f".{ext}"


def is_probable_video(filename: str | None, content_type: str | None) -> bool:
    if content_type and content_type.startswith("video/"):
        return True
    ext = safe_extension(filename)
    if ext in {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}:
        return True
    return False


def build_download_url(base_url: str, job_id: str, token: str) -> str:
    base = base_url.rstrip("/") + "/"
    path = f"api/download/{job_id}?token={token}"
    return urljoin(base, path)