import secrets
from typing import Any

from app.db import connect
from app.utils import generate_uuid, utcnow


def create_job(
    sqlite_path: str,
    *,
    source: str,
    user_id: str | None,
    chat_id: str | None,
    input_path: str,
    profile: str,
    input_bytes: int | None,
) -> dict[str, Any]:
    job_id = generate_uuid()
    token = secrets.token_urlsafe(24)
    now = utcnow()
    with connect(sqlite_path) as conn:
        conn.execute(
            """
            INSERT INTO jobs (
                id, source, user_id, chat_id, input_path, output_path,
                status, profile, progress, input_bytes, output_bytes,
                duration_seconds, created_at, updated_at, error_message,
                download_token
            )
            VALUES (?, ?, ?, ?, ?, NULL, ?, ?, 0, ?, 0, 0, ?, ?, '', ?)
            """,
            (
                job_id,
                source,
                user_id,
                chat_id,
                input_path,
                "queued",
                profile,
                input_bytes or 0,
                now,
                now,
                token,
            ),
        )
    return {"id": job_id, "download_token": token}


def get_job(sqlite_path: str, job_id: str) -> dict[str, Any] | None:
    with connect(sqlite_path) as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            return None
        return dict(row)


def update_job(sqlite_path: str, job_id: str, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = utcnow()
    assignments = ", ".join([f"{key} = ?" for key in fields.keys()])
    values = list(fields.values())
    values.append(job_id)
    with connect(sqlite_path) as conn:
        conn.execute(f"UPDATE jobs SET {assignments} WHERE id = ?", values)


def lock_next_job(sqlite_path: str) -> dict[str, Any] | None:
    now = utcnow()
    with connect(sqlite_path) as conn:
        row = conn.execute(
            """
            UPDATE jobs
            SET status = 'processing', progress = 0, updated_at = ?
            WHERE id = (
                SELECT id FROM jobs WHERE status = 'queued' ORDER BY created_at LIMIT 1
            )
            AND status = 'queued'
            RETURNING *
            """,
            (now,),
        ).fetchone()
        if not row:
            return None
        return dict(row)


def set_user_profile(sqlite_path: str, user_id: str, profile: str) -> None:
    now = utcnow()
    with connect(sqlite_path) as conn:
        conn.execute(
            """
            INSERT INTO user_settings (user_id, profile, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET profile = excluded.profile, updated_at = excluded.updated_at
            """,
            (user_id, profile, now),
        )


def get_user_profile(sqlite_path: str, user_id: str) -> str | None:
    with connect(sqlite_path) as conn:
        row = conn.execute(
            "SELECT profile FROM user_settings WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not row:
            return None
        return row["profile"]