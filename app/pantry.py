import json
import logging
import os

logger = logging.getLogger(__name__)

PANTRY_PATH = os.environ.get("PANTRY_PATH", "/home/tim/receipt-printer/pantry.json")


def get_pantry() -> dict:
    with open(PANTRY_PATH) as f:
        return json.load(f)


def get_ingredients_summary() -> str:
    items = get_pantry().get("pantry", {})
    parts = [
        f"{name} ({data['portions']} portions)"
        for name, data in items.items()
        if isinstance(data, dict) and data.get("portions")
    ]
    return ", ".join(parts)


def get_cuisines() -> list:
    prefs = get_pantry().get("preferences", {})
    return [c for c in prefs.get("cuisines", []) if c]


def get_favourites() -> list:
    prefs = get_pantry().get("preferences", {})
    return prefs.get("favourite recipes", [])
