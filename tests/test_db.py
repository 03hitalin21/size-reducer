from pathlib import Path

from app.db import get_connection
from app.jobs import create_job, get_job


def init_db(sqlite_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    sql = (root / "scripts" / "init_db.sql").read_text(encoding="utf-8")
    conn = get_connection(str(sqlite_path))
    conn.executescript(sql)
    conn.close()


def test_create_job(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "jobs.sqlite"
    init_db(sqlite_path)

    job = create_job(
        str(sqlite_path),
        source="web",
        user_id="127.0.0.1",
        chat_id=None,
        input_path="/tmp/input.mp4",
        profile="balanced",
        input_bytes=123,
    )

    fetched = get_job(str(sqlite_path), job["id"])
    assert fetched is not None
    assert fetched["id"] == job["id"]
    assert fetched["status"] == "queued"