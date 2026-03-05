import asyncio
import json
import logging
import random
import re

import aiofiles
import google.genai as genai
from google.genai import types

from meal_bot import config
from meal_bot.core.models import MealAnalysis


NUTRITION_PROMPT = """You are an expert nutrition analyst.
Analyze the provided video and spoken content to detect meal occasions and estimate nutrition per occasion.
Critical rule:
- Each distinct eating occasion must be a separate item in `meals`.
- If 2+ meals are detected, output 2+ `meals` entries (never merge them).
- Use visual + spoken boundary cues (scene/time/context shifts, explicit meal transitions, different food sets).
- If boundary is ambiguous, prefer splitting into separate meals and note uncertainty in `notes`.
Additional rules:
- Keep meal entries in chronological order.
- Use realistic serving-size assumptions and grounded calorie/macro estimates.
- Keep names concise and human-readable.
- Return only valid JSON that strictly matches the provided schema (no markdown, no extra keys, no extra text)."""

PRIMARY_MODEL = "gemini-3.1-flash-lite-preview"
FALLBACK_MODEL = "gemini-2.5-flash-lite"
GEMINI_MAX_RETRIES = 5
GEMINI_BASE_DELAY_SECONDS = 1.0
GEMINI_MAX_DELAY_SECONDS = 12.0
GEMINI_THINKING_LEVEL = types.ThinkingLevel.MEDIUM

_client: genai.Client | None = None
logger = logging.getLogger(__name__)


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def _strip_fences(text: str) -> str:
    """Remove markdown code fences that Gemini occasionally wraps around JSON."""
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()


def _is_retryable_gemini_error(error: Exception) -> bool:
    msg = str(error).lower()
    retryable_markers = (
        "503",
        "unavailable",
        "high demand",
        "resource exhausted",
        "429",
        "deadline exceeded",
        "internal",
        "temporar",
        "timeout",
    )
    return any(marker in msg for marker in retryable_markers)


async def _generate_content_with_retries(
    client: genai.Client,
    parts: list,
    model_name: str,
) -> types.GenerateContentResponse:
    delay = GEMINI_BASE_DELAY_SECONDS

    for attempt in range(1, GEMINI_MAX_RETRIES + 1):
        try:
            return await asyncio.to_thread(
                client.models.generate_content,
                model=model_name,
                contents=parts,
                config=types.GenerateContentConfig(
                    response_mime_type='application/json',
                    response_schema=MealAnalysis.model_json_schema(),
                    thinking_config=types.ThinkingConfig(
                        thinking_level=GEMINI_THINKING_LEVEL,
                    ),
                ),
            )
        except Exception as error:
            is_last_attempt = attempt == GEMINI_MAX_RETRIES
            if is_last_attempt or not _is_retryable_gemini_error(error):
                raise

            sleep_for = min(
                GEMINI_MAX_DELAY_SECONDS,
                delay + random.uniform(0.0, delay * 0.25),
            )
            logger.warning(
                "Gemini transient error on model %s attempt %s/%s (%s). Retrying in %.2fs",
                model_name,
                attempt,
                GEMINI_MAX_RETRIES,
                type(error).__name__,
                sleep_for,
            )
            await asyncio.sleep(sleep_for)
            delay = min(GEMINI_MAX_DELAY_SECONDS, delay * 2)

    raise RuntimeError("Unreachable retry state")


async def analyze_meal(video_path: str) -> MealAnalysis:
    """Send full MP4 video note to Gemini and return parsed meal entries."""
    client = _get_client()

    async with aiofiles.open(video_path, 'rb') as f:
        video_bytes = await f.read()

    parts: list = [
        types.Part.from_bytes(data=video_bytes, mime_type='video/mp4'),
        NUTRITION_PROMPT,
    ]

    try:
        response = await _generate_content_with_retries(client, parts, PRIMARY_MODEL)
    except Exception as primary_error:
        logger.warning(
            "Primary model %s failed after retries (%s). Falling back to %s.",
            PRIMARY_MODEL,
            type(primary_error).__name__,
            FALLBACK_MODEL,
        )
        response = await _generate_content_with_retries(client, parts, FALLBACK_MODEL)

    raw = response.text
    raw = _strip_fences(raw)
    data = json.loads(raw)
    return MealAnalysis(**data)