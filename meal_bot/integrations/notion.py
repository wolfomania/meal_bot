from datetime import date

from notion_client import Client

from meal_bot import config
from meal_bot.core.models import MealEntry


_notion: Client | None = None


def _get_client() -> Client:
    global _notion
    if _notion is None:
        _notion = Client(auth=config.NOTION_TOKEN)
    return _notion


def log_meal(entry: MealEntry) -> None:
    """Write one MealEntry to the Notion database."""
    client = _get_client()
    client.pages.create(
        parent={"database_id": config.NOTION_DATABASE_ID},
        properties={
            "Meal": {
                "title": [{"text": {"content": entry.meal_name}}]
            },
            "Date": {
                "date": {"start": date.today().isoformat()}
            },
            "Calories": {
                "number": entry.calories
            },
            "Protein (g)": {
                "number": entry.protein_g
            },
            "Carbs (g)": {
                "number": entry.carbs_g
            },
            "Fat (g)": {
                "number": entry.fat_g
            },
            "Meal Type": {
                "select": {"name": entry.meal_type}
            },
            "Food Items": {
                "multi_select": [{"name": item} for item in entry.food_items]
            },
            "Notes": {
                "rich_text": [{"text": {"content": entry.notes[:2000]}}]
            },
        },
    )


def log_meals(entries: list[MealEntry]) -> None:
    """Write all detected meals to the Notion database."""
    for entry in entries:
        log_meal(entry)