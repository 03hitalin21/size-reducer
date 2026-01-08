import os
from dataclasses import dataclass


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def _get_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str | None
    telegram_webhook_url: str | None
    base_url: str
    sqlite_path: str
    storage_path: str
    max_upload_mb: int
    max_duration_seconds: int
    max_telegram_send_mb: int
    rate_limit_per_min: int
    web_host: str
    web_port: int
    bot_listen_host: str
    bot_listen_port: int


def load_settings() -> Settings:
    return Settings(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        telegram_webhook_url=os.getenv("TELEGRAM_WEBHOOK_URL"),
        base_url=_get_str("BASE_URL", "http://localhost:8000"),
        sqlite_path=_get_str("SQLITE_PATH", "db/jobs.sqlite"),
        storage_path=_get_str("STORAGE_PATH", "storage"),
        max_upload_mb=_get_int("MAX_UPLOAD_MB", 200),
        max_duration_seconds=_get_int("MAX_DURATION_SECONDS", 900),
        max_telegram_send_mb=_get_int("MAX_TELEGRAM_SEND_MB", 45),
        rate_limit_per_min=_get_int("RATE_LIMIT_PER_MIN", 30),
        web_host=_get_str("WEB_HOST", "0.0.0.0"),
        web_port=_get_int("WEB_PORT", 8000),
        bot_listen_host=_get_str("BOT_LISTEN_HOST", "0.0.0.0"),
        bot_listen_port=_get_int("BOT_LISTEN_PORT", 8080),
    )