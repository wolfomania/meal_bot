import logging
import tempfile

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
from ffmpeg_utils import extract_audio, extract_frames
from gemini_client import analyze_meal
from models import MealEntry
from notion_logger import log_meal

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

ALLOWED_USERNAME = "wolfomania"
RETRY_CALLBACK_DATA = "retry_last_video"


def _is_authorized_user(update: Update) -> bool:
    user = update.effective_user
    if user is None:
        return False

    username = (user.username or "").lower()
    return username == ALLOWED_USERNAME


def _format_logged_entry(entry: MealEntry) -> str:
    items_str = ', '.join(entry.food_items[:5])
    if len(entry.food_items) > 5:
        items_str += f' +{len(entry.food_items) - 5} more'

    return (
        f"Logged: {entry.meal_name}\n"
        f"{entry.meal_type} | {entry.calories} kcal\n"
        f"P: {entry.protein_g}g | C: {entry.carbs_g}g | F: {entry.fat_g}g\n"
        f"Items: {items_str}"
    )


def _retry_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Retry", callback_data=RETRY_CALLBACK_DATA)]]
    )


async def _process_video_note(file_id: str, duration: float, context: ContextTypes.DEFAULT_TYPE) -> MealEntry:
    with tempfile.TemporaryDirectory() as tmpdir:
        # Download video note
        tg_file = await context.bot.get_file(file_id)
        video_path = f"{tmpdir}/video.mp4"
        await tg_file.download_to_drive(video_path)

        # Extract audio and frames via FFmpeg
        audio_path = f"{tmpdir}/audio.wav"
        await extract_audio(video_path, audio_path)
        frame_paths = await extract_frames(video_path, tmpdir, duration=duration)

        # Analyze with Gemini
        entry = await analyze_meal(audio_path, frame_paths)

        # Log to Notion
        log_meal(entry)

    return entry


async def handle_video_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process a Telegram video note through the full nutrition pipeline."""
    message = update.message
    if message is None:
        return

    if not _is_authorized_user(update):
        logger.warning(
            "Rejected message from unauthorized user: id=%s username=%s",
            update.effective_user.id if update.effective_user else None,
            update.effective_user.username if update.effective_user else None,
        )
        await message.reply_text("Unauthorized user.")
        return

    vn = message.video_note
    if vn is None:
        await message.reply_text("Please send a video note.")
        return

    duration = float(vn.duration)
    context.user_data["last_video_note"] = {
        "file_id": vn.file_id,
        "duration": duration,
    }

    await message.reply_text("Processing your meal video...")

    try:
        entry = await _process_video_note(vn.file_id, duration, context)
        await message.reply_text(_format_logged_entry(entry))

    except Exception as e:
        logger.exception("Pipeline failed for video note")
        await message.reply_text(
            f"Sorry, something went wrong: {type(e).__name__}. Please try again.",
            reply_markup=_retry_keyboard(),
        )


async def handle_retry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return

    await query.answer()

    if not _is_authorized_user(update):
        logger.warning(
            "Rejected retry from unauthorized user: id=%s username=%s",
            update.effective_user.id if update.effective_user else None,
            update.effective_user.username if update.effective_user else None,
        )
        if query.message is not None:
            await query.message.reply_text("Unauthorized user.")
        return

    last_video_note = context.user_data.get("last_video_note")
    if not last_video_note:
        if query.message is not None:
            await query.message.reply_text("No previous video note to retry.")
        return

    file_id = last_video_note.get("file_id")
    duration = float(last_video_note.get("duration", 0))

    if not file_id or duration <= 0:
        if query.message is not None:
            await query.message.reply_text("Saved retry data is invalid. Send a new video note.")
        return

    if query.message is not None:
        await query.message.reply_text("Retrying your last meal video...")

    try:
        entry = await _process_video_note(file_id, duration, context)
        if query.message is not None:
            await query.message.reply_text(_format_logged_entry(entry))
        await query.edit_message_reply_markup(reply_markup=None)

    except Exception as e:
        logger.exception("Retry failed")
        if query.message is not None:
            await query.message.reply_text(
                f"Retry failed: {type(e).__name__}. Try again.",
                reply_markup=_retry_keyboard(),
            )


def main() -> None:
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.VIDEO_NOTE, handle_video_note))
    app.add_handler(CallbackQueryHandler(handle_retry, pattern=f"^{RETRY_CALLBACK_DATA}$"))
    logger.info("Bot started, polling for updates...")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == '__main__':
    main()
