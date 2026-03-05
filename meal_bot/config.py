from dotenv import load_dotenv
import os

load_dotenv()

def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value

TELEGRAM_BOT_TOKEN: str = _require("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY: str = _require("GEMINI_API_KEY")
NOTION_TOKEN: str = _require("NOTION_TOKEN")
NOTION_DATABASE_ID: str = _require("NOTION_DATABASE_ID")

_raw_usernames = os.getenv("ALLOWED_USERNAMES", "")
ALLOWED_USERNAMES: frozenset[str] = frozenset(
    u.strip().lower() for u in _raw_usernames.split(",") if u.strip()
)
