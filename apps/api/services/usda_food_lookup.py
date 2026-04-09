"""
USDA FoodData Central lookup service.

Three-tier lookup: local Postgres → USDA API → None (caller falls back to LLM).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from models import USDAFood

logger = logging.getLogger(__name__)

USDA_API_BASE = "https://api.nal.usda.gov/fdc/v1"

_NUTRIENT_IDS = {
    "Energy": 1008,
    "Protein": 1003,
    "Carbohydrate, by difference": 1005,
    "Total lipid (fat)": 1004,
    "Fiber, total dietary": 1079,
}


@dataclass
class FoodMatch:
    fdc_id: int
    description: str
    calories_per_100g: float
    protein_per_100g: float
    carbs_per_100g: float
    fat_per_100g: float
    fiber_per_100g: float
    source: str


def lookup_food(search_term: str, db: Session) -> Optional[FoodMatch]:
    """Three-tier food lookup: local → USDA API → None."""
    if not search_term or not search_term.strip():
        return None

    result = _lookup_local(search_term, db)
    if result:
        return result

    result = _lookup_api(search_term, db)
    if result:
        return result

    return None


def _lookup_local(search_term: str, db: Session) -> Optional[FoodMatch]:
    row = db.execute(
        text(
            "SELECT fdc_id, description, calories_per_100g, protein_per_100g, "
            "carbs_per_100g, fat_per_100g, fiber_per_100g, source "
            "FROM usda_food "
            "WHERE to_tsvector('english', description) @@ plainto_tsquery('english', :term) "
            "ORDER BY ts_rank(to_tsvector('english', description), plainto_tsquery('english', :term)) DESC "
            "LIMIT 1"
        ),
        {"term": search_term},
    ).fetchone()

    if not row:
        return None

    return FoodMatch(
        fdc_id=row.fdc_id,
        description=row.description,
        calories_per_100g=row.calories_per_100g or 0,
        protein_per_100g=row.protein_per_100g or 0,
        carbs_per_100g=row.carbs_per_100g or 0,
        fat_per_100g=row.fat_per_100g or 0,
        fiber_per_100g=row.fiber_per_100g or 0,
        source="usda_local",
    )


def _lookup_api(search_term: str, db: Session) -> Optional[FoodMatch]:
    api_key = os.getenv("USDA_API_KEY")
    if not api_key:
        logger.debug("USDA_API_KEY not set, skipping API lookup")
        return None

    try:
        resp = httpx.post(
            f"{USDA_API_BASE}/foods/search",
            params={"api_key": api_key},
            json={
                "query": search_term,
                "dataType": ["SR Legacy", "Foundation"],
                "pageSize": 1,
            },
            timeout=5.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        logger.warning("USDA API lookup failed for '%s'", search_term, exc_info=True)
        return None

    foods = data.get("foods", [])
    if not foods:
        return None

    food = foods[0]
    nutrients = {n.get("nutrientId"): n.get("value", 0) for n in food.get("foodNutrients", [])}

    match = FoodMatch(
        fdc_id=food["fdcId"],
        description=food.get("description", search_term),
        calories_per_100g=nutrients.get(_NUTRIENT_IDS["Energy"], 0),
        protein_per_100g=nutrients.get(_NUTRIENT_IDS["Protein"], 0),
        carbs_per_100g=nutrients.get(_NUTRIENT_IDS["Carbohydrate, by difference"], 0),
        fat_per_100g=nutrients.get(_NUTRIENT_IDS["Total lipid (fat)"], 0),
        fiber_per_100g=nutrients.get(_NUTRIENT_IDS["Fiber, total dietary"], 0),
        source="usda_api",
    )

    _cache_result(match, db)
    return match


def _cache_result(match: FoodMatch, db: Session) -> None:
    existing = db.query(USDAFood).filter(USDAFood.fdc_id == match.fdc_id).first()
    if existing:
        return
    db.add(USDAFood(
        fdc_id=match.fdc_id,
        description=match.description,
        calories_per_100g=match.calories_per_100g,
        protein_per_100g=match.protein_per_100g,
        carbs_per_100g=match.carbs_per_100g,
        fat_per_100g=match.fat_per_100g,
        fiber_per_100g=match.fiber_per_100g,
        source="api_cached",
    ))
    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.debug("Cache insert race for fdc_id=%s", match.fdc_id)
