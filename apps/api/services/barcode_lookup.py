"""
Barcode (UPC/GTIN) lookup.

Tier 1: Local USDA Branded Foods cache (1.8M products with GTIN-14 UPCs).
Tier 2: Open Food Facts API (crowdsourced, good coverage for consumer products).
Tier 3: USDA FoodData Central API (official, slower).

Handles UPC-A (12 digit) → GTIN-14 (14 digit) normalization automatically.
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional

import httpx
from sqlalchemy import or_
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


def _upc_variants(upc: str) -> List[str]:
    """Generate GTIN format variants for a scanned UPC."""
    digits = upc.lstrip("0") or "0"
    variants = [upc]
    for length in (8, 12, 13, 14):
        padded = digits.zfill(length)
        if padded != upc:
            variants.append(padded)
    full_padded = upc.zfill(14)
    if full_padded not in variants:
        variants.append(full_padded)
    return variants


def _lookup_openfoodfacts(upc: str) -> Optional[FoodMatch]:
    """Tier 2: Open Food Facts — crowdsourced, covers most consumer packaged goods."""
    try:
        resp = httpx.get(
            f"https://world.openfoodfacts.org/api/v0/product/{upc}.json",
            timeout=5.0,
            headers={"User-Agent": "StrideIQ/1.0 (contact@strideiq.run)"},
        )
        data = resp.json()
        if data.get("status") != 1:
            return None

        product = data.get("product", {})
        nutr = product.get("nutriments", {})

        cal = nutr.get("energy-kcal_100g")
        if cal is None:
            return None

        name_parts = []
        if product.get("brands"):
            name_parts.append(product["brands"].split(",")[0].strip())
        if product.get("product_name"):
            name_parts.append(product["product_name"])
        description = " ".join(name_parts) or upc

        return FoodMatch(
            fdc_id=0,
            description=description,
            calories_per_100g=float(cal or 0),
            protein_per_100g=float(nutr.get("proteins_100g", 0) or 0),
            carbs_per_100g=float(nutr.get("carbohydrates_100g", 0) or 0),
            fat_per_100g=float(nutr.get("fat_100g", 0) or 0),
            fiber_per_100g=float(nutr.get("fiber_100g", 0) or 0),
            source="openfoodfacts",
        )
    except Exception:
        logger.debug("Open Food Facts lookup failed for UPC '%s'", upc, exc_info=True)
        return None


def lookup_barcode(upc: str, db: Session) -> Optional[FoodMatch]:
    if not upc or not upc.strip():
        return None

    upc = upc.strip()
    variants = _upc_variants(upc)

    # Tier 1: Local DB (GTIN-14 normalized, prefer entries with calorie data)
    cached = (
        db.query(USDAFood)
        .filter(or_(*(USDAFood.upc_gtin == v for v in variants)))
        .order_by(USDAFood.calories_per_100g.desc().nullslast())
        .first()
    )
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

    # Tier 2: Open Food Facts
    off_match = _lookup_openfoodfacts(upc)
    if off_match:
        _cache_result(db, upc, off_match)
        return off_match

    # Tier 3: USDA API
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

    _cache_result(db, upc, match)
    return match


def _cache_result(db: Session, upc: str, match: FoodMatch) -> None:
    """Cache a successful lookup in the local DB for future instant retrieval."""
    try:
        if match.fdc_id:
            existing = db.query(USDAFood).filter(USDAFood.fdc_id == match.fdc_id).first()
            if existing:
                existing.upc_gtin = upc.zfill(14)
                db.commit()
                return

        db.add(USDAFood(
            fdc_id=match.fdc_id or hash(upc) % 900_000_000 + 100_000_000,
            description=match.description,
            calories_per_100g=match.calories_per_100g,
            protein_per_100g=match.protein_per_100g,
            carbs_per_100g=match.carbs_per_100g,
            fat_per_100g=match.fat_per_100g,
            fiber_per_100g=match.fiber_per_100g,
            upc_gtin=upc.zfill(14),
            source=match.source,
        ))
        db.commit()
    except Exception:
        db.rollback()
