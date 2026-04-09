#!/usr/bin/env python3
"""
Seed the usda_food table from USDA FoodData Central SR Legacy + Foundation datasets.

Downloads CSV data, extracts per-100g nutrients, and inserts into Postgres.
Idempotent: skips rows where fdc_id already exists.

Usage: docker exec strideiq_api python scripts/seed_usda_foods.py
"""
import csv
import io
import logging
import os
import sys
import zipfile
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "api"))
os.chdir(str(Path(__file__).resolve().parent.parent / "apps" / "api"))

from core.database import SessionLocal
from models import USDAFood

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

SR_LEGACY_URL = "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_csv_2018-04.zip"
FOUNDATION_URL = "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_foundation_food_csv_2025-12-18.zip"

NUTRIENT_IDS = {
    1008: "calories_per_100g",
    1003: "protein_per_100g",
    1005: "carbs_per_100g",
    1004: "fat_per_100g",
    1079: "fiber_per_100g",
}


def download_and_extract(url: str, label: str) -> dict:
    """Download USDA zip, return {fdc_id: {description, category, nutrients}}."""
    logger.info("Downloading %s from %s ...", label, url)
    resp = httpx.get(url, timeout=120, follow_redirects=True)
    resp.raise_for_status()

    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()

    food_file = next((n for n in names if n.endswith("food.csv")), None)
    nutrient_file = next((n for n in names if n.endswith("food_nutrient.csv")), None)

    if not food_file or not nutrient_file:
        logger.error("Could not find food.csv or food_nutrient.csv in %s", names)
        return {}

    foods = {}
    with zf.open(food_file) as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
        for row in reader:
            fdc_id = int(row["fdc_id"])
            foods[fdc_id] = {
                "fdc_id": fdc_id,
                "description": row.get("description", ""),
                "food_category": row.get("food_category_id", ""),
            }

    with zf.open(nutrient_file) as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
        for row in reader:
            fdc_id = int(row["fdc_id"])
            nutrient_id = int(row.get("nutrient_id", 0))
            if fdc_id in foods and nutrient_id in NUTRIENT_IDS:
                try:
                    val = float(row.get("amount", 0))
                except (ValueError, TypeError):
                    val = 0.0
                foods[fdc_id][NUTRIENT_IDS[nutrient_id]] = val

    logger.info("%s: parsed %d foods", label, len(foods))
    return foods


def seed(foods: dict, source: str, db) -> int:
    existing_ids = set(
        r[0] for r in db.query(USDAFood.fdc_id).filter(
            USDAFood.source.in_(["sr_legacy", "foundation"])
        ).all()
    )

    inserted = 0
    batch = []
    for fdc_id, data in foods.items():
        if fdc_id in existing_ids:
            continue
        batch.append(USDAFood(
            fdc_id=fdc_id,
            description=data.get("description", ""),
            food_category=data.get("food_category", ""),
            calories_per_100g=data.get("calories_per_100g"),
            protein_per_100g=data.get("protein_per_100g"),
            carbs_per_100g=data.get("carbs_per_100g"),
            fat_per_100g=data.get("fat_per_100g"),
            fiber_per_100g=data.get("fiber_per_100g"),
            source=source,
        ))
        if len(batch) >= 500:
            db.bulk_save_objects(batch)
            db.commit()
            inserted += len(batch)
            batch = []

    if batch:
        db.bulk_save_objects(batch)
        db.commit()
        inserted += len(batch)

    return inserted


def main():
    db = SessionLocal()
    try:
        sr_foods = download_and_extract(SR_LEGACY_URL, "SR Legacy")
        sr_count = seed(sr_foods, "sr_legacy", db)
        logger.info("SR Legacy: inserted %d new foods", sr_count)

        fn_foods = download_and_extract(FOUNDATION_URL, "Foundation")
        fn_count = seed(fn_foods, "foundation", db)
        logger.info("Foundation: inserted %d new foods", fn_count)

        total = db.query(USDAFood).count()
        logger.info("Total usda_food rows: %d", total)
    finally:
        db.close()


if __name__ == "__main__":
    main()
