from pydantic import BaseModel

class MealEntry(BaseModel):
    meal_name: str
    meal_type: str          # "Breakfast", "Lunch", "Dinner", or "Snack"
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float | None = None
    food_items: list[str]
    notes: str
