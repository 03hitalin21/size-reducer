import asyncio
import logging
from pathlib import Path
from urllib.parse import urlparse

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.config import load_settings
from app.jobs import create_job, get_user_profile, set_user_profile
from app.logging import setup_logging
from app.utils import ensure_dir, generate_uuid, is_probable_video, safe_extension

logger = logging.getLogger("bot")

PROFILES = {"small", "balanced", "hq"}


def build_settings_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("Small", callback_data="profile:small")],
        [InlineKeyboardButton("Balanced", callback_data="profile:balanced")],
        [InlineKeyboardButton("HQ", callback_data="profile:hq")],
    ]
    return InlineKeyboardMarkup(buttons)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = context.application.bot_data["settings"]
    text = (
        "Send me a video or document and I will compress it.\n"
        f"Max upload size: {settings.max_upload_mb} MB.\n"
        "Use /settings to pick a profile (small, balanced, hq)."
    )
    await update.message.reply_text(text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Upload a video and I will compress it. Use /settings to pick a profile."
    )


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Choose a compression profile:", reply_markup=build_settings_keyboard()
    )


async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    _, profile = query.data.split(":", 1)
    if profile not in PROFILES:
        await query.edit_message_text("Unknown profile.")
        return

    settings = context.application.bot_data["settings"]
    await asyncio.to_thread(
        set_user_profile, settings.sqlite_path, str(query.from_user.id), profile
    )
    await query.edit_message_text(f"Profile set to {profile}.")


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return

    media = message.video or message.document
    if not media:
        return

    if message.document and not is_probable_video(
        message.document.file_name, message.document.mime_type
    ):
        await message.reply_text("Please send a video file.")
        return

    settings = context.application.bot_data["settings"]
    uploads_dir = context.application.bot_data["uploads_dir"]

    if media.file_size and media.file_size > settings.max_upload_mb * 1024 * 1024:
        await message.reply_text("File too large for this bot.")
        return

    file = await context.bot.get_file(media.file_id)
    ext = safe_extension(getattr(media, "file_name", None)) or ".bin"
    input_path = uploads_dir / f"{generate_uuid()}{ext}"

    await file.download_to_drive(custom_path=str(input_path))

    profile = await asyncio.to_thread(
        get_user_profile, settings.sqlite_path, str(message.from_user.id)
    )
    if profile not in PROFILES:
        profile = "balanced"

    job = await asyncio.to_thread(
        create_job,
        settings.sqlite_path,
        source="telegram",
        user_id=str(message.from_user.id),
        chat_id=str(message.chat_id),
        input_path=str(input_path),
        profile=profile,
        input_bytes=media.file_size or 0,
    )

    logger.info("job_created", extra={"job_id": job["id"]})
    await message.reply_text(
        f"Job {job['id']} queued. Processing started.",
    )


def main() -> None:
    settings = load_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    setup_logging()
    uploads_dir = Path(settings.storage_path) / "uploads"
    ensure_dir(uploads_dir)

    application = Application.builder().token(settings.telegram_bot_token).build()
    application.bot_data["settings"] = settings
    application.bot_data["uploads_dir"] = uploads_dir

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CallbackQueryHandler(profile_callback, pattern=r"^profile:"))
    application.add_handler(
        MessageHandler(filters.VIDEO | filters.Document.ALL, handle_media)
    )

    if settings.telegram_webhook_url:
        parsed = urlparse(settings.telegram_webhook_url)
        url_path = parsed.path.lstrip("/") or "telegram"
        application.run_webhook(
            listen=settings.bot_listen_host,
            port=settings.bot_listen_port,
            url_path=url_path,
            webhook_url=settings.telegram_webhook_url,
        )
    else:
        application.run_polling()


if __name__ == "__main__":
    main()
