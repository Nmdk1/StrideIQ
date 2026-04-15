"""
Extract real athlete fitness profiles from the production database.

Run inside the API container:
  docker exec strideiq_api python scripts/extract_athlete_profiles.py

Outputs Python dict literals that can be pasted into the V2 evaluation harness.
"""
import os
import sys
import json
sys.path.insert(0, ".")

from database import SessionLocal
from models import Athlete
from services.fitness_bank import get_fitness_bank, ExperienceLevel
from services.plan_framework.fingerprint_bridge import compute_fingerprint
from services.plan_framework.load_context import build_load_context

TARGET_EMAILS = [
    e.strip()
    for e in os.environ.get("STRIDEIQ_TARGET_EMAILS", "").split(",")
    if e.strip()
]

TARGET_NAMES = ["brian", "larry", "josh", "mark", "adam"]


def extract():
    db = SessionLocal()
    athletes = db.query(Athlete).all()

    for a in athletes:
        name = (a.display_name or a.email or "").lower()
        email = (a.email or "").lower()

        is_target = email in [e.lower() for e in TARGET_EMAILS]
        if not is_target:
            is_target = any(n in name for n in TARGET_NAMES)

        if not is_target:
            continue

        try:
            bank = get_fitness_bank(a.id, db)
        except Exception as e:
            print(f"# SKIP {a.display_name or a.email}: {e}")
            continue

        try:
            fp = compute_fingerprint(a.id, db)
        except Exception:
            fp = None

        try:
            lc = build_load_context(a.id, db)
        except Exception:
            lc = None

        print(f"\n# === {a.display_name or a.email} (id={a.id}) ===")
        print(f"{{")
        print(f'    "name": "{a.display_name or email}",')
        print(f'    "email": "{a.email}",')
        print(f'    "rpi": {bank.best_rpi:.1f},')
        print(f'    "current_weekly_miles": {bank.current_weekly_miles:.1f},')
        print(f'    "peak_weekly_miles": {bank.peak_weekly_miles:.1f},')
        print(f'    "peak_long_run_miles": {bank.peak_long_run_miles:.1f},')
        print(f'    "current_long_run_miles": {bank.current_long_run_miles:.1f},')
        print(f'    "average_long_run_miles": {bank.average_long_run_miles:.1f},')
        print(f'    "sustainable_peak_weekly": {bank.sustainable_peak_weekly:.1f},')
        print(f'    "experience_level": "{bank.experience_level.value}",')
        print(f'    "peak_ctl": {bank.peak_ctl:.1f},')
        print(f'    "current_ctl": {bank.current_ctl:.1f},')
        print(f'    "tau1": {bank.tau1:.1f},')
        print(f'    "tau2": {bank.tau2:.1f},')
        print(f'    "recent_quality_sessions_28d": {bank.recent_quality_sessions_28d},')
        print(f'    "recent_8w_median_weekly_miles": {bank.recent_8w_median_weekly_miles:.1f},')
        print(f'    "recent_16w_p90_weekly_miles": {bank.recent_16w_p90_weekly_miles:.1f},')
        print(f'    "recent_8w_p75_long_run_miles": {bank.recent_8w_p75_long_run_miles:.1f},')
        print(f'    "recent_16w_p50_long_run_miles": {bank.recent_16w_p50_long_run_miles:.1f},')
        print(f'    "typical_long_run_day": {bank.typical_long_run_day},')
        print(f'    "typical_quality_day": {bank.typical_quality_day},')
        print(f'    "typical_rest_days": {bank.typical_rest_days},')
        if fp:
            print(f'    "cutback_frequency": {fp.cutback_frequency},')
            print(f'    "quality_spacing_min_hours": {fp.quality_spacing_min_hours},')
            print(f'    "limiter": {repr(fp.limiter)},')
        if lc:
            print(f'    "l30_max_easy_long_mi": {lc.l30_max_easy_long_mi:.1f},')
            print(f'    "observed_recent_weekly_miles": {lc.observed_recent_weekly_miles:.1f},')
        print(f"}}")

    db.close()


if __name__ == "__main__":
    extract()
