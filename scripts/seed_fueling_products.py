#!/usr/bin/env python3
"""
Seed the fueling_product table with endurance nutrition products.

STOP: Do NOT run this script until the founder has verified every number
against manufacturer labels or websites. Wrong seed data corrupts the
correlation engine permanently.

Sources: Manufacturer websites, USDA FDC, FatSecret, EatThisMuch.
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

# ──────────────────────────────────────────────────────────────────────
# GELS
# ──────────────────────────────────────────────────────────────────────

GELS = [
    # Maurten
    {"brand": "Maurten", "product_name": "Gel 100", "category": "gel", "carbs_g": 25, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 1.0, "serving_size_g": 40, "calories": 100},
    {"brand": "Maurten", "product_name": "Gel 160", "category": "gel", "carbs_g": 40, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 1.0, "serving_size_g": 65, "calories": 160},
    {"brand": "Maurten", "product_name": "Gel 100", "variant": "Caf 100", "category": "gel", "carbs_g": 25, "caffeine_mg": 100, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 1.0, "serving_size_g": 40, "calories": 100},

    # Neversecond
    {"brand": "Neversecond", "product_name": "C30 Energy Gel", "category": "gel", "carbs_g": 30, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 2.0, "serving_size_g": 60, "calories": 120, "sodium_mg": 200},
    {"brand": "Neversecond", "product_name": "C30+ Energy Gel", "variant": "Caffeine", "category": "gel", "carbs_g": 30, "caffeine_mg": 75, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 2.0, "serving_size_g": 60, "calories": 120, "sodium_mg": 200},

    # SiS (Science in Sport)
    {"brand": "SiS", "product_name": "GO Isotonic Gel", "category": "gel", "carbs_g": 22, "caffeine_mg": 0, "carb_source": "maltodextrin", "serving_size_g": 60, "calories": 87},
    {"brand": "SiS", "product_name": "GO Isotonic Gel", "variant": "Caffeine 75mg", "category": "gel", "carbs_g": 22, "caffeine_mg": 75, "carb_source": "maltodextrin", "serving_size_g": 60, "calories": 87},
    {"brand": "SiS", "product_name": "GO Isotonic Gel", "variant": "Caffeine 150mg", "category": "gel", "carbs_g": 22, "caffeine_mg": 150, "carb_source": "maltodextrin", "serving_size_g": 60, "calories": 87},
    {"brand": "SiS", "product_name": "Beta Fuel Gel", "category": "gel", "carbs_g": 40, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 1.25, "serving_size_g": 60, "calories": 160},
    {"brand": "SiS", "product_name": "Beta Fuel Gel", "variant": "Nootropics", "category": "gel", "carbs_g": 40, "caffeine_mg": 200, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 1.25, "serving_size_g": 60, "calories": 160},

    # GU
    {"brand": "GU", "product_name": "Energy Gel", "category": "gel", "carbs_g": 22, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "serving_size_g": 32, "calories": 100},
    {"brand": "GU", "product_name": "Energy Gel", "variant": "Caffeine 20mg", "category": "gel", "carbs_g": 22, "caffeine_mg": 20, "carb_source": "maltodextrin_fructose", "serving_size_g": 32, "calories": 100},
    {"brand": "GU", "product_name": "Energy Gel", "variant": "Caffeine 40mg", "category": "gel", "carbs_g": 22, "caffeine_mg": 40, "carb_source": "maltodextrin_fructose", "serving_size_g": 32, "calories": 100},
    {"brand": "GU", "product_name": "Roctane Gel", "category": "gel", "carbs_g": 21, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "serving_size_g": 32, "calories": 100},
    {"brand": "GU", "product_name": "Roctane Gel", "variant": "Caffeine 35mg", "category": "gel", "carbs_g": 21, "caffeine_mg": 35, "carb_source": "maltodextrin_fructose", "serving_size_g": 32, "calories": 100},
    {"brand": "GU", "product_name": "Roctane Gel", "variant": "Caffeine 70mg", "category": "gel", "carbs_g": 21, "caffeine_mg": 70, "carb_source": "maltodextrin_fructose", "serving_size_g": 32, "calories": 100},

    # Spring Energy
    {"brand": "Spring Energy", "product_name": "Awesome Sauce", "category": "gel", "carbs_g": 45, "caffeine_mg": 0, "carb_source": "whole_food", "serving_size_g": 50, "calories": 180},
    {"brand": "Spring Energy", "product_name": "Canaberry", "category": "gel", "carbs_g": 23, "caffeine_mg": 0, "carb_source": "whole_food", "serving_size_g": 50, "calories": 100},
    {"brand": "Spring Energy", "product_name": "Hill Aid", "category": "gel", "carbs_g": 23, "caffeine_mg": 30, "carb_source": "whole_food", "serving_size_g": 50, "calories": 100},
    {"brand": "Spring Energy", "product_name": "Speednut", "category": "gel", "carbs_g": 12, "caffeine_mg": 50, "fat_g": 19, "protein_g": 2, "carb_source": "whole_food", "serving_size_g": 50, "calories": 250},
    {"brand": "Spring Energy", "product_name": "Koffee", "category": "gel", "carbs_g": 42, "caffeine_mg": 65, "carb_source": "whole_food", "serving_size_g": 50, "calories": 210},
    {"brand": "Spring Energy", "product_name": "Long Haul", "category": "gel", "carbs_g": 19, "caffeine_mg": 0, "fat_g": 5.7, "protein_g": 1, "carb_source": "whole_food", "serving_size_g": 50, "calories": 140, "sodium_mg": 140},
    {"brand": "Spring Energy", "product_name": "Electroride", "category": "gel", "carbs_g": 23, "caffeine_mg": 0, "carb_source": "whole_food", "serving_size_g": 50, "calories": 100},
    {"brand": "Spring Energy", "product_name": "Power Rush", "category": "gel", "carbs_g": 23, "caffeine_mg": 0, "carb_source": "whole_food", "serving_size_g": 50, "calories": 100},
    {"brand": "Spring Energy", "product_name": "El Capo", "category": "gel", "carbs_g": 69, "caffeine_mg": 0, "carb_source": "whole_food", "serving_size_g": 100, "calories": 250},

    # Precision Fuel & Hydration
    {"brand": "Precision Fuel", "product_name": "PF 30 Gel", "category": "gel", "carbs_g": 30, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 2.0, "serving_size_g": 51, "calories": 120},
    {"brand": "Precision Fuel", "product_name": "PF 30 Gel", "variant": "Caffeine", "category": "gel", "carbs_g": 30, "caffeine_mg": 100, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 2.0, "serving_size_g": 51, "calories": 120},
    {"brand": "Precision Fuel", "product_name": "PF 90 Gel", "category": "gel", "carbs_g": 90, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 2.0, "serving_size_g": 153, "calories": 360},

    # Styrkr
    {"brand": "Styrkr", "product_name": "GEL30", "category": "gel", "carbs_g": 30, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 1.25, "serving_size_g": 72, "calories": 128},
    {"brand": "Styrkr", "product_name": "GEL50", "category": "gel", "carbs_g": 50, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 1.25, "serving_size_g": 72, "calories": 201},

    # Enervit
    {"brand": "Enervit", "product_name": "C2:1PRO Carbo Gel", "category": "gel", "carbs_g": 40, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 2.0, "serving_size_g": 60, "calories": 120, "sodium_mg": 100},
    {"brand": "Enervit", "product_name": "C2:1PRO Carbo Gel", "variant": "Caffeine", "category": "gel", "carbs_g": 40, "caffeine_mg": 100, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 2.0, "serving_size_g": 60, "calories": 120, "sodium_mg": 200},

    # Hammer Nutrition
    {"brand": "Hammer", "product_name": "Hammer Gel", "category": "gel", "carbs_g": 21, "caffeine_mg": 0, "carb_source": "maltodextrin", "serving_size_g": 33, "calories": 90, "sodium_mg": 20},
    {"brand": "Hammer", "product_name": "Hammer Gel", "variant": "Espresso", "category": "gel", "carbs_g": 21, "caffeine_mg": 50, "carb_source": "maltodextrin", "serving_size_g": 33, "calories": 90, "sodium_mg": 20},
    {"brand": "Hammer", "product_name": "Hammer Gel", "variant": "Tropical", "category": "gel", "carbs_g": 21, "caffeine_mg": 25, "carb_source": "maltodextrin", "serving_size_g": 33, "calories": 90, "sodium_mg": 20},

    # Honey Stinger
    {"brand": "Honey Stinger", "product_name": "Organic Energy Gel", "category": "gel", "carbs_g": 24, "caffeine_mg": 0, "carb_source": "honey", "serving_size_g": 32, "calories": 100},
    {"brand": "Honey Stinger", "product_name": "Organic Energy Gel", "variant": "Caffeinated", "category": "gel", "carbs_g": 24, "caffeine_mg": 32, "carb_source": "honey", "serving_size_g": 32, "calories": 100},

    # Huma
    {"brand": "Huma", "product_name": "Chia Energy Gel", "category": "gel", "carbs_g": 22, "caffeine_mg": 0, "carb_source": "whole_food", "serving_size_g": 39, "calories": 100},
    {"brand": "Huma", "product_name": "Chia Energy Gel", "variant": "Plus Caffeine", "category": "gel", "carbs_g": 22, "caffeine_mg": 25, "carb_source": "whole_food", "serving_size_g": 39, "calories": 100},

    # UCAN
    {"brand": "UCAN", "product_name": "Edge Energy Gel", "category": "gel", "carbs_g": 19, "caffeine_mg": 0, "carb_source": "superstarch", "serving_size_g": 53, "calories": 70},
    {"brand": "UCAN", "product_name": "Edge Energy Gel", "variant": "Caffeine", "category": "gel", "carbs_g": 34, "caffeine_mg": 45, "carb_source": "superstarch", "serving_size_g": 53, "calories": 100},

    # Untapped
    {"brand": "Untapped", "product_name": "Maple Energy Gel", "category": "gel", "carbs_g": 25, "caffeine_mg": 0, "carb_source": "maple_syrup", "serving_size_g": 28, "calories": 100},
    {"brand": "Untapped", "product_name": "Maple Energy Gel", "variant": "Salted", "category": "gel", "carbs_g": 25, "caffeine_mg": 0, "carb_source": "maple_syrup", "serving_size_g": 28, "calories": 100, "sodium_mg": 100},

    # Endurance Tap
    {"brand": "Endurance Tap", "product_name": "Energy Gel", "category": "gel", "carbs_g": 24, "caffeine_mg": 0, "carb_source": "maple_syrup", "serving_size_g": 28, "calories": 100},

    # Muir Energy
    {"brand": "Muir Energy", "product_name": "Energy Gel", "category": "gel", "carbs_g": 17, "caffeine_mg": 0, "fat_g": 7, "protein_g": 3, "carb_source": "whole_food", "serving_size_g": 42, "calories": 150},

    # The Feed Lab
    {"brand": "The Feed Lab", "product_name": "Energy Gel", "category": "gel", "carbs_g": 25, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "serving_size_g": 40, "calories": 100},
]

# ──────────────────────────────────────────────────────────────────────
# DRINK MIXES
# ──────────────────────────────────────────────────────────────────────

DRINK_MIXES = [
    # Maurten
    {"brand": "Maurten", "product_name": "Drink Mix 160", "category": "drink_mix", "carbs_g": 40, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 1.0, "serving_size_g": 40, "calories": 160, "fluid_ml": 500},
    {"brand": "Maurten", "product_name": "Drink Mix 320", "category": "drink_mix", "carbs_g": 80, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 1.0, "serving_size_g": 80, "calories": 320, "fluid_ml": 500},
    {"brand": "Maurten", "product_name": "Drink Mix 320", "variant": "Caf 100", "category": "drink_mix", "carbs_g": 80, "caffeine_mg": 100, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 1.0, "serving_size_g": 80, "calories": 320, "fluid_ml": 500},

    # Neversecond
    {"brand": "Neversecond", "product_name": "C30 Drink Mix", "category": "drink_mix", "carbs_g": 30, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 2.0, "serving_size_g": 32, "calories": 120, "sodium_mg": 200, "fluid_ml": 500},
    {"brand": "Neversecond", "product_name": "C90 Drink Mix", "category": "drink_mix", "carbs_g": 90, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 2.0, "serving_size_g": 94, "calories": 360, "sodium_mg": 200, "fluid_ml": 750},

    # SiS
    {"brand": "SiS", "product_name": "Beta Fuel Drink Mix", "category": "drink_mix", "carbs_g": 80, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 1.25, "serving_size_g": 84, "calories": 320, "fluid_ml": 500},
    {"brand": "SiS", "product_name": "GO Electrolyte", "category": "drink_mix", "carbs_g": 36, "caffeine_mg": 0, "carb_source": "sucrose_maltodextrin", "serving_size_g": 40, "calories": 153, "fluid_ml": 500},

    # GU
    {"brand": "GU", "product_name": "Roctane Drink Mix", "category": "drink_mix", "carbs_g": 59, "caffeine_mg": 35, "carb_source": "maltodextrin_fructose", "serving_size_g": 65, "calories": 250, "sodium_mg": 320, "fluid_ml": 630},

    # Styrkr
    {"brand": "Styrkr", "product_name": "MIX60", "category": "drink_mix", "carbs_g": 60, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 1.25, "serving_size_g": 65, "calories": 256, "fluid_ml": 500},
    {"brand": "Styrkr", "product_name": "MIX90", "category": "drink_mix", "carbs_g": 90, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 1.25, "serving_size_g": 97, "calories": 384, "fluid_ml": 750},

    # Skratch Labs
    {"brand": "Skratch", "product_name": "Sport Hydration Mix", "category": "drink_mix", "carbs_g": 20, "caffeine_mg": 0, "carb_source": "cane_sugar_dextrose", "serving_size_g": 22, "calories": 80, "sodium_mg": 380, "fluid_ml": 500},
    {"brand": "Skratch", "product_name": "Super High-Carb Drink Mix", "category": "drink_mix", "carbs_g": 50, "caffeine_mg": 0, "carb_source": "cluster_dextrin_fructose", "serving_size_g": 53, "calories": 200, "fluid_ml": 500},

    # Tailwind
    {"brand": "Tailwind", "product_name": "Endurance Fuel", "category": "drink_mix", "carbs_g": 25, "caffeine_mg": 0, "carb_source": "dextrose_sucrose", "serving_size_g": 27, "calories": 100, "sodium_mg": 303, "fluid_ml": 350},
    {"brand": "Tailwind", "product_name": "Endurance Fuel", "variant": "Caffeinated", "category": "drink_mix", "carbs_g": 25, "caffeine_mg": 35, "carb_source": "dextrose_sucrose", "serving_size_g": 27, "calories": 100, "sodium_mg": 303, "fluid_ml": 350},

    # Precision Fuel
    {"brand": "Precision Fuel", "product_name": "Carb & Electrolyte Drink Mix", "category": "drink_mix", "carbs_g": 30, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "glucose_fructose_ratio": 2.0, "serving_size_g": 32, "calories": 120, "sodium_mg": 250, "fluid_ml": 500},

    # Hammer Nutrition
    {"brand": "Hammer", "product_name": "Perpetuem", "category": "drink_mix", "carbs_g": 54, "caffeine_mg": 0, "protein_g": 7, "fat_g": 3, "carb_source": "maltodextrin", "serving_size_g": 69, "calories": 270, "fluid_ml": 600},
    {"brand": "Hammer", "product_name": "HEED", "category": "drink_mix", "carbs_g": 26, "caffeine_mg": 0, "carb_source": "maltodextrin", "serving_size_g": 29, "calories": 110, "sodium_mg": 100, "fluid_ml": 600},

    # UCAN
    {"brand": "UCAN", "product_name": "Energy Powder", "category": "drink_mix", "carbs_g": 27, "caffeine_mg": 0, "carb_source": "superstarch", "serving_size_g": 35, "calories": 110, "fluid_ml": 300},

    # The Feed Lab
    {"brand": "The Feed Lab", "product_name": "High-Carb Drink Mix", "category": "drink_mix", "carbs_g": 50, "caffeine_mg": 0, "carb_source": "maltodextrin_fructose", "serving_size_g": 55, "calories": 200, "fluid_ml": 500},
]

# ──────────────────────────────────────────────────────────────────────
# CHEWS
# ──────────────────────────────────────────────────────────────────────

CHEWS = [
    # Clif
    {"brand": "Clif", "product_name": "Bloks Energy Chews", "variant": "3pc serving", "category": "chew", "carbs_g": 24, "caffeine_mg": 0, "carb_source": "sugar", "serving_size_g": 30, "calories": 100},
    {"brand": "Clif", "product_name": "Bloks Energy Chews", "variant": "Caffeine 3pc", "category": "chew", "carbs_g": 24, "caffeine_mg": 50, "carb_source": "sugar", "serving_size_g": 30, "calories": 100},

    # GU
    {"brand": "GU", "product_name": "Energy Chews", "category": "chew", "carbs_g": 23, "caffeine_mg": 0, "carb_source": "sugar_tapioca", "serving_size_g": 34, "calories": 90},
    {"brand": "GU", "product_name": "Energy Chews", "variant": "Caffeine", "category": "chew", "carbs_g": 23, "caffeine_mg": 20, "carb_source": "sugar_tapioca", "serving_size_g": 34, "calories": 90},

    # Honey Stinger
    {"brand": "Honey Stinger", "product_name": "Energy Chews", "category": "chew", "carbs_g": 39, "caffeine_mg": 0, "carb_source": "honey_sugar", "serving_size_g": 50, "calories": 160},
    {"brand": "Honey Stinger", "product_name": "Energy Chews", "variant": "Caffeinated", "category": "chew", "carbs_g": 39, "caffeine_mg": 32, "carb_source": "honey_sugar", "serving_size_g": 50, "calories": 160},

    # Skratch
    {"brand": "Skratch", "product_name": "Energy Chews", "category": "chew", "carbs_g": 17, "caffeine_mg": 0, "carb_source": "sugar", "serving_size_g": 22, "calories": 70},
]

# ──────────────────────────────────────────────────────────────────────
# BARS & WAFFLES
# ──────────────────────────────────────────────────────────────────────

BARS = [
    # Maurten
    {"brand": "Maurten", "product_name": "Solid 160", "category": "bar", "carbs_g": 42, "caffeine_mg": 0, "fat_g": 3.3, "protein_g": 2.3, "carb_source": "oat_rice_sugar", "serving_size_g": 55, "calories": 200, "sodium_mg": 240},
    {"brand": "Maurten", "product_name": "Solid 225", "category": "bar", "carbs_g": 56, "caffeine_mg": 0, "fat_g": 4, "protein_g": 3, "carb_source": "oat_rice_sugar", "serving_size_g": 75, "calories": 225},
    {"brand": "Maurten", "product_name": "Solid C 225", "variant": "Cacao", "category": "bar", "carbs_g": 56, "caffeine_mg": 0, "fat_g": 4, "protein_g": 3, "carb_source": "oat_rice_sugar", "serving_size_g": 75, "calories": 225},

    # Honey Stinger
    {"brand": "Honey Stinger", "product_name": "Organic Waffle", "category": "bar", "carbs_g": 19, "caffeine_mg": 0, "fat_g": 7, "protein_g": 1, "carb_source": "honey_sugar", "serving_size_g": 30, "calories": 150},
    {"brand": "Honey Stinger", "product_name": "Organic Waffle", "variant": "Gluten Free", "category": "bar", "carbs_g": 21, "caffeine_mg": 0, "fat_g": 7, "protein_g": 1, "carb_source": "honey_sugar", "serving_size_g": 32, "calories": 150},

    # Untapped
    {"brand": "Untapped", "product_name": "Maple Waffle", "category": "bar", "carbs_g": 23, "caffeine_mg": 0, "fat_g": 7, "protein_g": 2, "carb_source": "maple_syrup", "serving_size_g": 30, "calories": 160},

    # Clif
    {"brand": "Clif", "product_name": "Bar", "category": "bar", "carbs_g": 44, "caffeine_mg": 0, "fat_g": 6, "protein_g": 10, "carb_source": "oat_sugar", "serving_size_g": 68, "calories": 250},

    # Styrkr
    {"brand": "Styrkr", "product_name": "SIB Energy Bar", "category": "bar", "carbs_g": 30, "caffeine_mg": 0, "carb_source": "oat_date", "serving_size_g": 55, "calories": 200},

    # Spring Energy
    {"brand": "Spring Energy", "product_name": "Chocolate Heaven", "category": "bar", "carbs_g": 30, "caffeine_mg": 0, "carb_source": "whole_food", "serving_size_g": 55, "calories": 170},
]

# ──────────────────────────────────────────────────────────────────────
# ELECTROLYTES (no/minimal carbs)
# ──────────────────────────────────────────────────────────────────────

ELECTROLYTES = [
    # LMNT
    {"brand": "LMNT", "product_name": "Electrolyte Mix", "category": "electrolyte", "carbs_g": 0, "caffeine_mg": 0, "sodium_mg": 1000, "serving_size_g": 6, "calories": 0, "fluid_ml": 500},
    {"brand": "LMNT", "product_name": "Electrolyte Mix", "variant": "Chocolate Salt", "category": "electrolyte", "carbs_g": 1, "caffeine_mg": 0, "sodium_mg": 1000, "serving_size_g": 9, "calories": 15, "fluid_ml": 500},

    # Nuun
    {"brand": "Nuun", "product_name": "Sport Hydration", "category": "electrolyte", "carbs_g": 1, "caffeine_mg": 0, "sodium_mg": 300, "serving_size_g": 5.5, "calories": 10, "fluid_ml": 500},
    {"brand": "Nuun", "product_name": "Sport Hydration", "variant": "Caffeine", "category": "electrolyte", "carbs_g": 2, "caffeine_mg": 40, "sodium_mg": 300, "serving_size_g": 5.5, "calories": 10, "fluid_ml": 500},
    {"brand": "Nuun", "product_name": "Endurance", "category": "electrolyte", "carbs_g": 15, "caffeine_mg": 0, "sodium_mg": 380, "serving_size_g": 18, "calories": 60, "fluid_ml": 500},

    # Precision Fuel
    {"brand": "Precision Fuel", "product_name": "PH 1000", "category": "electrolyte", "carbs_g": 0, "caffeine_mg": 0, "sodium_mg": 1000, "serving_size_g": 5, "calories": 0, "fluid_ml": 500},
    {"brand": "Precision Fuel", "product_name": "PH 1500", "category": "electrolyte", "carbs_g": 0, "caffeine_mg": 0, "sodium_mg": 1500, "serving_size_g": 8, "calories": 0, "fluid_ml": 500},

    # SiS
    {"brand": "SiS", "product_name": "GO Hydro", "category": "electrolyte", "carbs_g": 0.5, "caffeine_mg": 0, "sodium_mg": 345, "serving_size_g": 4.2, "calories": 8, "fluid_ml": 500},

    # The Feed Lab
    {"brand": "The Feed Lab", "product_name": "Hydration", "category": "electrolyte", "carbs_g": 2, "caffeine_mg": 0, "sodium_mg": 500, "serving_size_g": 7, "calories": 10, "fluid_ml": 500},

    # Mortal
    {"brand": "Mortal", "product_name": "Hydration", "category": "electrolyte", "carbs_g": 0, "caffeine_mg": 0, "sodium_mg": 600, "serving_size_g": 6, "calories": 0, "fluid_ml": 500},

    # Redmond Re-Lyte
    {"brand": "Redmond", "product_name": "Re-Lyte Hydration", "category": "electrolyte", "carbs_g": 1, "caffeine_mg": 0, "sodium_mg": 810, "serving_size_g": 6.5, "calories": 5, "fluid_ml": 500},

    # Skratch
    {"brand": "Skratch", "product_name": "Anytime Hydration Mix", "category": "electrolyte", "carbs_g": 4, "caffeine_mg": 0, "sodium_mg": 200, "serving_size_g": 6, "calories": 15, "fluid_ml": 500},

    # SaltStick
    {"brand": "SaltStick", "product_name": "Caps", "variant": "per 2 capsules", "category": "electrolyte", "carbs_g": 0, "caffeine_mg": 0, "sodium_mg": 430, "serving_size_g": 1.6, "calories": 0},
    {"brand": "SaltStick", "product_name": "Fastchews", "variant": "per 2 chews", "category": "electrolyte", "carbs_g": 1, "caffeine_mg": 0, "sodium_mg": 200, "serving_size_g": 2, "calories": 5},
]

# ──────────────────────────────────────────────────────────────────────
# CAFFEINE (standalone)
# ──────────────────────────────────────────────────────────────────────

CAFFEINE = [
    {"brand": "SiS", "product_name": "Performance Caffeine", "category": "caffeine", "carbs_g": 0, "caffeine_mg": 200, "serving_size_g": 1, "calories": 0},
    {"brand": "GU", "product_name": "Caffeine Capsule", "category": "caffeine", "carbs_g": 0, "caffeine_mg": 100, "serving_size_g": 1, "calories": 0},
]

ALL_PRODUCTS = GELS + DRINK_MIXES + CHEWS + BARS + ELECTROLYTES + CAFFEINE


def main():
    db = SessionLocal()
    try:
        inserted = 0
        skipped = 0
        for p in ALL_PRODUCTS:
            existing = db.query(FuelingProduct).filter(
                FuelingProduct.brand == p["brand"],
                FuelingProduct.product_name == p["product_name"],
                FuelingProduct.variant == p.get("variant"),
            ).first()
            if existing:
                skipped += 1
                continue
            db.add(FuelingProduct(**p))
            inserted += 1

        db.commit()
        total = db.query(FuelingProduct).count()
        print(f"Inserted {inserted} new products, skipped {skipped} existing. Total: {total}")

        by_cat = {}
        for p in ALL_PRODUCTS:
            cat = p["category"]
            by_cat[cat] = by_cat.get(cat, 0) + 1
        print("Breakdown:", by_cat)
    finally:
        db.close()


if __name__ == "__main__":
    main()
