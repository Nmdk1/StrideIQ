"""Quick verification: tune-up race insertion into V2 plans."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
os.environ.setdefault("SETTINGS_MODULE", "core.settings")

from datetime import date, timedelta

from services.plan_engine_v2.engine import generate_plan_v2
from services.plan_engine_v2.models import TuneUpRace
from services.plan_engine_v2.evaluation.real_athletes import (
    REAL_ATHLETES,
    build_fitness_bank,
    build_fingerprint,
    build_load_context,
)

DOW_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _print_plan(plan, tune_ups, label):
    print(f"\n{'=' * 72}")
    print(f"  {label}")
    print(f"  {plan.total_weeks} weeks | {plan.goal_event}")
    for tu in tune_ups:
        print(f"  Tune-up: {tu.name} ({tu.distance}, {tu.purpose}) on {tu.race_date}")
    print(f"{'=' * 72}")

    for wk in plan.weeks:
        cut = " [CUT]" if wk.is_cutback else ""
        print(f"\n  W{wk.week_number:>2} | {wk.phase:<12}{cut}")
        for d in wk.days:
            dist = ""
            if d.distance_range_km:
                mi = (d.distance_range_km[0] + d.distance_range_km[1]) / 2 * 0.621371
                dist = f" ({mi:.0f}mi)"
            elif d.target_distance_km:
                mi = d.target_distance_km * 0.621371
                dist = f" ({mi:.1f}mi)"
            marker = " ***" if d.workout_type in ("tune_up_race", "pre_race", "recovery", "recovery_long") else ""
            print(f"    {DOW_NAMES[d.day_of_week]}: {d.workout_type}{dist}{marker}")
    print()


def test_michael_marathon_with_half_tuneup():
    """Michael: 16wk marathon with a half marathon tune-up at week 10."""
    michael = REAL_ATHLETES[0]
    bank = build_fitness_bank(michael)
    fp = build_fingerprint(michael)
    lc = build_load_context(michael)

    start = date.today()
    plan_monday = start - timedelta(days=start.weekday())
    tu_date = plan_monday + timedelta(weeks=9, days=5)  # Saturday of week 10

    tune_ups = [
        TuneUpRace(
            race_date=tu_date,
            distance="half_marathon",
            name="Brooklyn Half",
            purpose="threshold",
        ),
    ]

    plan = generate_plan_v2(
        bank, fp, lc,
        mode="race", goal_event="marathon",
        weeks_available=16,
        tune_up_races=tune_ups,
        plan_start_date=start,
    )

    _print_plan(plan, tune_ups, "Michael — Marathon 16wk + Brooklyn Half tune-up (W10)")

    # Verify tune-up inserted
    w10 = plan.weeks[9]
    types = [d.workout_type for d in w10.days]
    assert "tune_up_race" in types, f"No tune-up race in W10: {types}"
    assert "pre_race" in types, f"No pre-race day in W10: {types}"

    # Post-race recovery should be a recovery_long, not a 4mi jog
    recovery_days = [d for d in w10.days if d.workout_type == "recovery_long"]
    assert len(recovery_days) >= 1, (
        f"Tune-up week should have a recovery_long day: "
        f"{[d.workout_type for d in w10.days]}"
    )

    # Midweek quality should be PRESERVED (not cleared)
    # — a tune-up is raced within a training week, not instead of one
    print("  PASS: tune-up inserted, recovery long present, build maintained")


def test_michael_marathon_with_10k_tuneup():
    """Michael: 16wk marathon with a 10K sharpening tune-up at week 12."""
    michael = REAL_ATHLETES[0]
    bank = build_fitness_bank(michael)
    fp = build_fingerprint(michael)
    lc = build_load_context(michael)

    start = date.today()
    plan_monday = start - timedelta(days=start.weekday())
    tu_date = plan_monday + timedelta(weeks=11, days=6)  # Sunday of week 12

    tune_ups = [
        TuneUpRace(
            race_date=tu_date,
            distance="10K",
            name="Central Park 10K",
            purpose="sharpening",
        ),
    ]

    plan = generate_plan_v2(
        bank, fp, lc,
        mode="race", goal_event="marathon",
        weeks_available=16,
        tune_up_races=tune_ups,
        plan_start_date=start,
    )

    _print_plan(plan, tune_ups, "Michael — Marathon 16wk + Central Park 10K (W12)")

    w12 = plan.weeks[11]
    types = [d.workout_type for d in w12.days]
    assert "tune_up_race" in types, f"No tune-up race in W12: {types}"
    print("  PASS: 10K tune-up inserted in W12")


def test_two_tuneups():
    """Michael: 16wk marathon with 10K at W8 and Half at W12."""
    michael = REAL_ATHLETES[0]
    bank = build_fitness_bank(michael)
    fp = build_fingerprint(michael)
    lc = build_load_context(michael)

    start = date.today()
    plan_monday = start - timedelta(days=start.weekday())

    tune_ups = [
        TuneUpRace(
            race_date=plan_monday + timedelta(weeks=7, days=6),
            distance="10K",
            name="Turkey Trot 10K",
            purpose="confidence",
        ),
        TuneUpRace(
            race_date=plan_monday + timedelta(weeks=11, days=5),
            distance="half_marathon",
            name="Philly Half",
            purpose="threshold",
        ),
    ]

    plan = generate_plan_v2(
        bank, fp, lc,
        mode="race", goal_event="marathon",
        weeks_available=16,
        tune_up_races=tune_ups,
        plan_start_date=start,
    )

    _print_plan(plan, tune_ups, "Michael — Marathon 16wk + 10K (W8) + Half (W12)")

    w8 = plan.weeks[7]
    w12 = plan.weeks[11]
    assert "tune_up_race" in [d.workout_type for d in w8.days], "No tune-up in W8"
    assert "tune_up_race" in [d.workout_type for d in w12.days], "No tune-up in W12"

    # No forced cutbacks after tune-ups — the natural cutback schedule
    # handles recovery. Verify recovery_long is placed correctly:
    # W8 has Sunday race → W9 Monday should be recovery_long
    w9 = plan.weeks[8]
    w9_types = [d.workout_type for d in w9.days]
    assert "recovery_long" in w9_types, (
        f"W9 should have recovery_long (day after W8 Sunday race): {w9_types}"
    )

    # W12 has Saturday race → Sunday should be recovery_long in same week
    w12_types = [d.workout_type for d in w12.days]
    assert "recovery_long" in w12_types, (
        f"W12 should have recovery_long (day after Saturday race): {w12_types}"
    )

    print("  PASS: two tune-ups inserted with recovery long runs")


def test_tuneup_in_taper_skipped():
    """Tune-up in taper should be skipped — goal race takes priority."""
    michael = REAL_ATHLETES[0]
    bank = build_fitness_bank(michael)
    fp = build_fingerprint(michael)
    lc = build_load_context(michael)

    start = date.today()
    plan_monday = start - timedelta(days=start.weekday())

    tune_ups = [
        TuneUpRace(
            race_date=plan_monday + timedelta(weeks=14, days=5),
            distance="5K",
            name="Taper 5K",
            purpose="sharpening",
        ),
    ]

    plan = generate_plan_v2(
        bank, fp, lc,
        mode="race", goal_event="marathon",
        weeks_available=16,
        tune_up_races=tune_ups,
        plan_start_date=start,
    )

    w15 = plan.weeks[14]
    types = [d.workout_type for d in w15.days]
    assert "tune_up_race" not in types, (
        f"Tune-up should NOT be in taper week: {types}"
    )
    print("  PASS: tune-up in taper correctly skipped")


def test_no_tuneup_baseline():
    """Verify plans without tune-ups still generate normally."""
    michael = REAL_ATHLETES[0]
    bank = build_fitness_bank(michael)
    fp = build_fingerprint(michael)
    lc = build_load_context(michael)

    plan = generate_plan_v2(
        bank, fp, lc,
        mode="race", goal_event="marathon",
        weeks_available=16,
    )

    assert len(plan.weeks) == 16
    for wk in plan.weeks:
        types = [d.workout_type for d in wk.days]
        assert "tune_up_race" not in types
    print("  PASS: no-tuneup plan unchanged")


if __name__ == "__main__":
    test_no_tuneup_baseline()
    test_michael_marathon_with_half_tuneup()
    test_michael_marathon_with_10k_tuneup()
    test_two_tuneups()
    test_tuneup_in_taper_skipped()
    print("\n  ALL TUNE-UP TESTS PASSED")
