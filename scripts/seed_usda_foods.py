#!/usr/bin/env python3
"""
Seed the usda_food table from USDA FoodData Central datasets.

Downloads CSV data, extracts per-100g nutrients, and inserts into Postgres.
Datasets: SR Legacy (~7.8K whole foods), Foundation (~3.9K), Branded (~1.8M with UPC).
Idempotent: skips rows where fdc_id already exists for that source.

Usage: docker exec strideiq_api python scripts/seed_usda_foods.py [--skip-branded]
"""
import csv
import io
import logging
import os
import sys
import tempfile
import zipfile
from pathlib import Path

import httpx
from sqlalchemy import text as sa_text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "api"))
os.chdir(str(Path(__file__).resolve().parent.parent / "apps" / "api"))

from core.database import SessionLocal
from models import USDAFood

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

SR_LEGACY_URL = "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_csv_2018-04.zip"
FOUNDATION_URL = "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_foundation_food_csv_2025-12-18.zip"
BRANDED_URL = "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_branded_food_csv_2025-12-18.zip"

NUTRIENT_IDS = {
    1008: "calories_per_100g",
    1003: "protein_per_100g",
    1005: "carbs_per_100g",
    1004: "fat_per_100g",
    1079: "fiber_per_100g",
}


def download_and_extract_small(url: str, label: str) -> dict:
    """Download a small USDA zip (SR Legacy / Foundation), return parsed foods."""
    logger.info("Downloading %s ...", label)
    resp = httpx.get(url, timeout=120, follow_redirects=True)
    resp.raise_for_status()
    logger.info("Downloaded %s (%.1f MB)", label, len(resp.content) / 1e6)

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


def seed_small(foods: dict, source: str, db) -> int:
    """Insert SR Legacy / Foundation foods."""
    existing_ids = set(
        r[0] for r in db.query(USDAFood.fdc_id).filter(USDAFood.source == source).all()
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


def seed_branded(db) -> int:
    """Download and seed USDA Branded Foods (~420MB zip, ~1.8M products with UPC)."""
    tmpdir = tempfile.mkdtemp()
    zip_path = os.path.join(tmpdir, "branded.zip")

    try:
        logger.info("Downloading Branded Foods CSV (~420MB)...")
        with httpx.stream("GET", BRANDED_URL, timeout=600, follow_redirects=True) as resp:
            resp.raise_for_status()
            total = 0
            with open(zip_path, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=1024 * 1024):
                    f.write(chunk)
                    total += len(chunk)
                    if total % (50 * 1024 * 1024) == 0:
                        logger.info("  ... downloaded %.0f MB", total / 1e6)
        logger.info("Download complete: %.0f MB", total / 1e6)

        zf = zipfile.ZipFile(zip_path)
        names = zf.namelist()

        food_file = next((n for n in names if n.endswith("food.csv")), None)
        branded_file = next((n for n in names if n.endswith("branded_food.csv")), None)
        nutrient_file = next((n for n in names if n.endswith("food_nutrient.csv")), None)

        if not all([food_file, branded_file, nutrient_file]):
            logger.error("Missing CSV files in branded zip")
            return 0

        logger.info("Phase 1: Reading food.csv ...")
        foods = {}
        with zf.open(food_file) as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
            for row in reader:
                fdc_id = int(row["fdc_id"])
                foods[fdc_id] = {
                    "fdc_id": fdc_id,
                    "description": row.get("description", "")[:500],
                    "food_category": row.get("food_category_id", ""),
                }
        logger.info("  Loaded %d foods", len(foods))

        logger.info("Phase 2: Reading branded_food.csv (UPC + brand) ...")
        with zf.open(branded_file) as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
            for row in reader:
                fdc_id = int(row["fdc_id"])
                if fdc_id in foods:
                    upc = row.get("gtin_upc", "").strip()
                    brand = row.get("brand_owner", "") or row.get("brand_name", "")
                    if upc:
                        foods[fdc_id]["upc_gtin"] = upc
                    if brand:
                        foods[fdc_id]["food_category"] = brand[:200]

        logger.info("Phase 3: Streaming food_nutrient.csv ...")
        nutrient_rows = 0
        with zf.open(nutrient_file) as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
            for row in reader:
                nutrient_rows += 1
                fdc_id = int(row["fdc_id"])
                nutrient_id = int(row.get("nutrient_id", 0))
                if fdc_id in foods and nutrient_id in NUTRIENT_IDS:
                    try:
                        val = float(row.get("amount", 0))
                    except (ValueError, TypeError):
                        val = 0.0
                    foods[fdc_id][NUTRIENT_IDS[nutrient_id]] = val
                if nutrient_rows % 5_000_000 == 0:
                    logger.info("  ... processed %dM nutrient rows", nutrient_rows // 1_000_000)
        logger.info("  Processed %d nutrient rows", nutrient_rows)

        existing_ids = set()
        result = db.execute(sa_text("SELECT fdc_id FROM usda_food WHERE source = 'branded'"))
        for row in result:
            existing_ids.add(row[0])
        logger.info("Found %d existing branded foods, skipping", len(existing_ids))

        inserted = 0
        batch = []
        for fdc_id, data in foods.items():
            if fdc_id in existing_ids:
                continue
            if not data.get("calories_per_100g") and not data.get("carbs_per_100g"):
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
                upc_gtin=data.get("upc_gtin"),
                source="branded",
            ))
            if len(batch) >= 2000:
                db.bulk_save_objects(batch)
                db.commit()
                inserted += len(batch)
                batch = []
                if inserted % 50000 == 0:
                    logger.info("  ... inserted %d so far", inserted)

        if batch:
            db.bulk_save_objects(batch)
            db.commit()
            inserted += len(batch)

        return inserted
    finally:
        try:
            os.unlink(zip_path)
            os.rmdir(tmpdir)
        except Exception:
            pass


def main():
    skip_branded = "--skip-branded" in sys.argv
    db = SessionLocal()
    try:
        sr_foods = download_and_extract_small(SR_LEGACY_URL, "SR Legacy")
        sr_count = seed_small(sr_foods, "sr_legacy", db)
        logger.info("SR Legacy: inserted %d new foods", sr_count)

        fn_foods = download_and_extract_small(FOUNDATION_URL, "Foundation")
        fn_count = seed_small(fn_foods, "foundation", db)
        logger.info("Foundation: inserted %d new foods", fn_count)

        if skip_branded:
            logger.info("Skipping branded foods (--skip-branded flag)")
        else:
            branded_count = seed_branded(db)
            logger.info("Branded: inserted %d new foods", branded_count)

        total = db.execute(sa_text("SELECT count(*) FROM usda_food")).scalar()
        upc_count = db.execute(sa_text("SELECT count(*) FROM usda_food WHERE upc_gtin IS NOT NULL")).scalar()
        logger.info("Total usda_food rows: %d (with UPC: %d)", total, upc_count)
    finally:
        db.close()


if __name__ == "__main__":
    main()
