import json
import re

import google.genai as genai
from google.genai import types

import config
from models import MealEntry


NUTRITION_PROMPT = """You are a nutrition analysis assistant. The user has sent a video note describing their meal.
Analyze the audio description and the video frames showing the food.
Return a JSON object with the meal details. Be precise with calorie and macro estimates based on typical serving sizes.
Meal type should be one of: Breakfast, Lunch, Dinner, Snack.
For food_items, list each distinct food item or ingredient separately.
For notes, include any relevant observations from the audio or video."""

_client: genai.Client | None = None


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


async def analyze_meal(audio_path: str, frame_paths: list[str]) -> MealEntry:
    """Send audio + frames to Gemini 2.5 Flash Lite and return a parsed MealEntry."""
    client = _get_client()

    with open(audio_path, 'rb') as f:
        audio_bytes = f.read()

    parts: list = [
        types.Part.from_bytes(data=audio_bytes, mime_type='audio/wav'),
    ]

    for frame_path in frame_paths:
        with open(frame_path, 'rb') as f:
            frame_bytes = f.read()
        parts.append(types.Part.from_bytes(data=frame_bytes, mime_type='image/jpeg'))

    parts.append(NUTRITION_PROMPT)

    response = client.models.generate_content(
        model='gemini-3.1-flash-lite-preview',
        contents=parts,
        config=types.GenerateContentConfig(
            response_mime_type='application/json',
            response_schema=MealEntry.model_json_schema(),
        ),
    )

    raw = response.text
    raw = _strip_fences(raw)
    data = json.loads(raw)
    return MealEntry(**data)
