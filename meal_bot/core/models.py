from typing import Literal

from pydantic import BaseModel, Field


class MealEntry(BaseModel):
    meal_name: str = Field(description="Short human-readable meal name.")
    meal_type: Literal["Breakfast", "Lunch", "Dinner", "Snack"] = Field(
        description="Meal category."
    )
    calories: int = Field(ge=0, description="Estimated total calories (kcal).")
    protein_g: float = Field(ge=0, description="Estimated protein in grams.")
    carbs_g: float = Field(ge=0, description="Estimated carbohydrates in grams.")
    fat_g: float = Field(ge=0, description="Estimated fat in grams.")
    fiber_g: float | None = Field(
        default=None, ge=0, description="Estimated fiber in grams when available."
    )
    food_items: list[str] = Field(
        description="Distinct foods or ingredients included in the meal."
    )
    notes: str = Field(description="Additional observations and assumptions.")


class MealAnalysis(BaseModel):
    meals: list[MealEntry] = Field(
        min_length=1,
        description=(
            "One or more meal entries detected from the video. "
            "Split into multiple entries when the clip contains separate meals."
        ),
    )
