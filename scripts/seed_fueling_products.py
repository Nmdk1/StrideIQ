#!/usr/bin/env python3
"""
Seed the fueling_product table with common endurance products.

STOP: Do NOT run this script until the founder has verified every number
against manufacturer labels or websites. Wrong seed data corrupts the
correlation engine permanently.

Idempotent: matches on (brand, product_name, variant).

Usage: docker exec strideiq_api python scripts/seed_fueling_products.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "api"))
os.chdir(str(Path(__file__).resolve().parent.parent / "apps" / "api"))

from core.database import SessionLocal
from models import FuelingProduct

PRODUCTS = [
    {"brand": "Maurten", "product_name": "Gel 100", "category": "gel", "carbs_g": 25, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 0.8, "serving_size_g": 40, "calories": 100},
    {"brand": "Maurten", "product_name": "Gel 160", "category": "gel", "carbs_g": 40, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 0.8, "serving_size_g": 65, "calories": 160},
    {"brand": "Maurten", "product_name": "Gel 100", "variant": "Caf 100", "category": "gel", "carbs_g": 25, "caffeine_mg": 100, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 0.8, "serving_size_g": 40, "calories": 100},
    {"brand": "Maurten", "product_name": "Drink Mix 160", "category": "drink_mix", "carbs_g": 40, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 0.8, "serving_size_g": 40, "calories": 160, "fluid_ml": 500},
    {"brand": "Maurten", "product_name": "Drink Mix 320", "category": "drink_mix", "carbs_g": 80, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 0.8, "serving_size_g": 80, "calories": 320, "fluid_ml": 500},
    {"brand": "SiS", "product_name": "Beta Fuel Gel", "category": "gel", "carbs_g": 40, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 1.25, "serving_size_g": 60, "calories": 160},
    {"brand": "SiS", "product_name": "Beta Fuel Gel", "variant": "Nootropics", "category": "gel", "carbs_g": 40, "caffeine_mg": 200, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 1.25, "serving_size_g": 60, "calories": 160},
    {"brand": "SiS", "product_name": "Beta Fuel Drink Mix", "category": "drink_mix", "carbs_g": 80, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 1.25, "serving_size_g": 84, "calories": 320, "fluid_ml": 500},
    {"brand": "GU", "product_name": "Energy Gel", "category": "gel", "carbs_g": 22, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "serving_size_g": 32, "calories": 100},
    {"brand": "GU", "product_name": "Roctane Gel", "category": "gel", "carbs_g": 21, "caffeine_mg": 35, "carb_source": "maltodextrin_fructose", "serving_size_g": 32, "calories": 100},
    {"brand": "GU", "product_name": "Roctane Gel", "variant": "Caffeine", "category": "gel", "carbs_g": 21, "caffeine_mg": 70, "carb_source": "maltodextrin_fructose", "serving_size_g": 32, "calories": 100},
    {"brand": "Spring Energy", "product_name": "Awesome Sauce", "category": "gel", "carbs_g": 22, "caffeine_mg": 0, "carb_source": "whole_food", "serving_size_g": 50, "calories": 100},
    {"brand": "Spring Energy", "product_name": "Canaberry", "category": "gel", "carbs_g": 23, "caffeine_mg": 65, "carb_source": "whole_food", "serving_size_g": 50, "calories": 110},
    {"brand": "Precision Fuel", "product_name": "PF 30 Gel", "category": "gel", "carbs_g": 30, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "serving_size_g": 51, "calories": 120},
    {"brand": "Precision Fuel", "product_name": "PF 30 Gel", "variant": "Caffeine", "category": "gel", "carbs_g": 30, "caffeine_mg": 100, "carb_source": "maltodextrin_fructose", "serving_size_g": 51, "calories": 120},
    {"brand": "Skratch", "product_name": "Sport Hydration Mix", "category": "drink_mix", "carbs_g": 20, "caffeine_mg": 0, "carb_source": "glucose_fructose", "serving_size_g": 22, "calories": 80, "fluid_ml": 500},
    {"brand": "Tailwind", "product_name": "Endurance Fuel", "category": "drink_mix", "carbs_g": 25, "caffeine_mg": 0, "carb_source": "glucose_sucrose", "serving_size_g": 27, "calories": 100, "fluid_ml": 350},
    {"brand": "Tailwind", "product_name": "Endurance Fuel", "variant": "Caffeinated", "category": "drink_mix", "carbs_g": 25, "caffeine_mg": 35, "carb_source": "glucose_sucrose", "serving_size_g": 27, "calories": 100, "fluid_ml": 350},
    {"brand": "Clif", "product_name": "Bloks Energy Chews", "variant": "3pc", "category": "chew", "carbs_g": 24, "caffeine_mg": 0, "carb_source": "sugar", "serving_size_g": 30, "calories": 100},
    {"brand": "Clif", "product_name": "Bloks Energy Chews", "variant": "Caffeine 3pc", "category": "chew", "carbs_g": 24, "caffeine_mg": 50, "carb_source": "sugar", "serving_size_g": 30, "calories": 100},
    {"brand": "Nuun", "product_name": "Sport Hydration Tab", "category": "electrolyte", "carbs_g": 1, "caffeine_mg": 0, "sodium_mg": 300, "serving_size_g": 5.5, "calories": 10, "fluid_ml": 500},
    {"brand": "LMNT", "product_name": "Electrolyte Mix", "category": "electrolyte", "carbs_g": 0, "caffeine_mg": 0, "sodium_mg": 1000, "serving_size_g": 6, "calories": 0, "fluid_ml": 500},
]


def main():
    db = SessionLocal()
    try:
        inserted = 0
        for p in PRODUCTS:
            existing = db.query(FuelingProduct).filter(
                FuelingProduct.brand == p["brand"],
                FuelingProduct.product_name == p["product_name"],
                FuelingProduct.variant == p.get("variant"),
            ).first()
            if existing:
                continue
            db.add(FuelingProduct(**p))
            inserted += 1

        db.commit()
        total = db.query(FuelingProduct).count()
        print(f"Inserted {inserted} new products. Total: {total}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
