import logging
import tempfile

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

import config
from ffmpeg_utils import extract_audio, extract_frames
from gemini_client import analyze_meal
from notion_logger import log_meal

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def handle_video_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process a Telegram video note through the full nutrition pipeline."""
    message = update.message
    if message is None:
        return

    vn = message.video_note
    await message.reply_text("⏳ Processing your meal video...")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Download video note
            tg_file = await vn.get_file()
            video_path = f"{tmpdir}/video.mp4"
            await tg_file.download_to_drive(video_path)

            # Extract audio and frames via FFmpeg
            audio_path = f"{tmpdir}/audio.wav"
            await extract_audio(video_path, audio_path)
            frame_paths = await extract_frames(
                video_path, tmpdir, duration=float(vn.duration)
            )

            # Analyze with Gemini
            entry = await analyze_meal(audio_path, frame_paths)

            # Log to Notion
            log_meal(entry)

        # Build confirmation message
        items_str = ', '.join(entry.food_items[:5])
        if len(entry.food_items) > 5:
            items_str += f' +{len(entry.food_items) - 5} more'

        reply = (
            f"✅ Logged: {entry.meal_name}\n"
            f"🍽 {entry.meal_type} · {entry.calories} kcal\n"
            f"💪 P: {entry.protein_g}g · C: {entry.carbs_g}g · F: {entry.fat_g}g\n"
            f"🥗 {items_str}"
        )
        await message.reply_text(reply)

    except Exception as e:
        logger.exception("Pipeline failed for video note")
        await message.reply_text(
            f"❌ Sorry, something went wrong: {type(e).__name__}. Please try again."
        )


def main() -> None:
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.VIDEO_NOTE, handle_video_note))
    logger.info("Bot started, polling for updates...")
    app.run_polling(allowed_updates=["message"])


if __name__ == '__main__':
    main()
