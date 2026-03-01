import json
import logging
import re

import anthropic

from app.pantry import get_favourites, get_ingredients_summary, get_cuisines

logger = logging.getLogger(__name__)

MODEL = "claude-opus-4-6"

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from environment


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def build_discovery_prompt(comfort_mode: bool) -> str:
    ingredients = get_ingredients_summary()
    cuisines = get_cuisines()
    favourites = get_favourites()

    cuisine_str = ", ".join(cuisines) if cuisines else "any"
    fav_str = ", ".join(favourites) if favourites else "none"

    if comfort_mode:
        preference_instruction = (
            "STRONGLY prefer the user's favourite recipes if the pantry supports them. "
            "Only suggest non-favourites if there are not enough favourites that work."
        )
    else:
        preference_instruction = (
            "Suggest varied, interesting recipes. Occasionally include a favourite if the "
            "pantry supports it, but prioritise variety."
        )

    return f"""You are a recipe suggestion assistant. Suggest 4 recipes based on the user's pantry.

PANTRY (proteins are critical — if a recipe requires a protein not listed here, exclude it):
{ingredients}

PREFERENCES:
- Cuisines: {cuisine_str}
- Favourite recipes: {fav_str}

INSTRUCTIONS:
- {preference_instruction}
- Proteins in the pantry are the ONLY proteins available. A missing required protein = exclude the recipe.
- Non-protein ingredients (spices, sauces, oils, vegetables, dairy, etc.) can be assumed available.
- Return ONLY a valid JSON array. No explanation, no markdown fences.

RESPONSE FORMAT:
[
  {{
    "name": "Recipe Name",
    "description": "One sentence description",
    "uses": ["pantry ingredient used"],
    "youll_need": ["extra ingredient to buy"],
    "comfort_match": true
  }}
]

Set "comfort_match" to true only if the recipe is one of the user's listed favourites."""


def build_recipe_prompt(recipe_name: str) -> str:
    return f"""You are a recipe assistant. Provide the full recipe for "{recipe_name}".

Return ONLY a valid JSON object. No explanation, no markdown fences.

RESPONSE FORMAT:
{{
  "name": "Recipe Name",
  "serves": 2,
  "ingredients": [
    {{"item": "ingredient name", "quantity": "amount"}}
  ],
  "steps": [
    "Step 1 instruction.",
    "Step 2 instruction."
  ],
  "youll_need": ["any special equipment or hard-to-find ingredients"]
}}"""


def get_suggestions(comfort_mode: bool) -> list:
    prompt = build_discovery_prompt(comfort_mode)
    logger.debug("Fetching recipe suggestions (comfort_mode=%s)", comfort_mode)

    with client.messages.stream(
        model=MODEL,
        max_tokens=2048,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        response = stream.get_final_message()

    text = next((b.text for b in response.content if b.type == "text"), "")
    logger.debug("Discovery raw response: %.200s", text)
    return json.loads(_strip_fences(text))


def get_recipe(recipe_name: str) -> dict:
    prompt = build_recipe_prompt(recipe_name)
    logger.debug("Fetching recipe for: %s", recipe_name)

    with client.messages.stream(
        model=MODEL,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        response = stream.get_final_message()

    text = next((b.text for b in response.content if b.type == "text"), "")
    logger.debug("Recipe raw response: %.200s", text)
    return json.loads(_strip_fences(text))
