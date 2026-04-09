"""
Barcode (UPC/GTIN) lookup via USDA Branded Foods.

Checks local cache first, then queries USDA API and caches the result.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from models import USDAFood
from services.usda_food_lookup import FoodMatch

logger = logging.getLogger(__name__)

USDA_API_BASE = "https://api.nal.usda.gov/fdc/v1"

_NUTRIENT_IDS = {
    1008: "calories",
    1003: "protein",
    1005: "carbs",
    1004: "fat",
    1079: "fiber",
}


def lookup_barcode(upc: str, db: Session) -> Optional[FoodMatch]:
    if not upc or not upc.strip():
        return None

    upc = upc.strip()

    cached = db.query(USDAFood).filter(USDAFood.upc_gtin == upc).first()
    if cached:
        return FoodMatch(
            fdc_id=cached.fdc_id,
            description=cached.description,
            calories_per_100g=cached.calories_per_100g or 0,
            protein_per_100g=cached.protein_per_100g or 0,
            carbs_per_100g=cached.carbs_per_100g or 0,
            fat_per_100g=cached.fat_per_100g or 0,
            fiber_per_100g=cached.fiber_per_100g or 0,
            source="branded_barcode",
        )

    api_key = os.getenv("USDA_API_KEY")
    if not api_key:
        return None

    try:
        resp = httpx.post(
            f"{USDA_API_BASE}/foods/search",
            params={"api_key": api_key},
            json={
                "query": upc,
                "dataType": ["Branded"],
                "pageSize": 1,
            },
            timeout=5.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        logger.warning("USDA branded lookup failed for UPC '%s'", upc, exc_info=True)
        return None

    foods = data.get("foods", [])
    if not foods:
        return None

    food = foods[0]
    nutrients = {}
    for n in food.get("foodNutrients", []):
        nid = n.get("nutrientId")
        if nid in _NUTRIENT_IDS:
            nutrients[_NUTRIENT_IDS[nid]] = n.get("value", 0)

    match = FoodMatch(
        fdc_id=food["fdcId"],
        description=food.get("description", upc),
        calories_per_100g=nutrients.get("calories", 0),
        protein_per_100g=nutrients.get("protein", 0),
        carbs_per_100g=nutrients.get("carbs", 0),
        fat_per_100g=nutrients.get("fat", 0),
        fiber_per_100g=nutrients.get("fiber", 0),
        source="branded_barcode",
    )

    existing = db.query(USDAFood).filter(USDAFood.fdc_id == food["fdcId"]).first()
    if existing:
        existing.upc_gtin = upc
    else:
        db.add(USDAFood(
            fdc_id=match.fdc_id,
            description=match.description,
            calories_per_100g=match.calories_per_100g,
            protein_per_100g=match.protein_per_100g,
            carbs_per_100g=match.carbs_per_100g,
            fat_per_100g=match.fat_per_100g,
            fiber_per_100g=match.fiber_per_100g,
            upc_gtin=upc,
            source="branded_barcode",
        ))

    try:
        db.commit()
    except Exception:
        db.rollback()

    return match
