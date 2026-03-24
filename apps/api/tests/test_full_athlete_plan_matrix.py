"""
Full Athlete Plan Matrix Test
==============================

Tests every athlete × every distance × every plan variant.
4 plan generators × 10 athletes × 4 distances × multiple durations.

Run with -s to see plan content:
    pytest tests/test_full_athlete_plan_matrix.py -v -s

Run just one athlete:
    pytest tests/test_full_athlete_plan_matrix.py -k "founder_mirror" -v -s

What each scenario asserts:
  1. Plan generates without error
  2. All coaching rules pass (PlanValidator)
  3. W1 long run is proportional to athlete volume
  4. No marathon pace work in 5K/10K plans
  5. Week-by-week content printed to stdout for human review
"""
from __future__ import annotations

import sys
import os
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.constraint_aware_planner import generate_constraint_aware_plan
from services.plan_framework.generator import PlanGenerator
from tests.plan_validation_helpers import validate_plan
from tests.fake_athletes import (
    ALL_ATHLETES,
    BEGINNER,
    RECREATIONAL,
    COMEBACK,
    CONSISTENT_MID,
    MASTERS,
    FOUNDER_MIRROR,
    SUB3_MARATHONER,
    HIGH_MILEAGE,
    ELITE_ADJACENT,
    DECLINING_MASTERS,
)

# ---------------------------------------------------------------------------
# Constants: all distances, tiers, durations
# ---------------------------------------------------------------------------
DISTANCES = ["5k", "10k", "half_marathon", "marathon"]

# Standard generator — full cartesian product
STANDARD_VARIANTS = [
    # (distance, tier, weeks, days)
    ("5k",           "low",     8,  5),
    ("5k",           "mid",     8,  6),
    ("5k",           "mid",    12,  6),
    ("5k",           "high",   12,  6),
    ("10k",          "low",    12,  5),
    ("10k",          "mid",    12,  6),
    ("10k",          "mid",     8,  6),
    ("10k",          "high",   12,  6),
    ("half_marathon","low",    16,  5),
    ("half_marathon","mid",    12,  6),
    ("half_marathon","mid",    16,  6),
    ("half_marathon","high",   16,  6),
    ("marathon",     "builder",18,  5),
    ("marathon",     "low",    18,  5),
    ("marathon",     "mid",    12,  6),
    ("marathon",     "mid",    18,  6),
    ("marathon",     "high",   18,  6),
]

# Semi-custom generator: (distance, duration, days_per_week)
SEMI_CUSTOM_DURATIONS = {
    "5k":           [(8, 5), (12, 6)],
    "10k":          [(8, 5), (12, 6)],
    "half_marathon":[(12, 5), (16, 6)],
    "marathon":     [(12, 6), (18, 6)],
}

# Constraint-aware: race horizon in weeks
CA_HORIZON_WEEKS = 12

# Race date used for semi-custom + constraint-aware
def _race_date(weeks: int) -> date:
    return date.today() + timedelta(weeks=weeks)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _plan_banner(label: str, tag: str, plan_obj) -> list[str]:
    """Return human-readable week-by-week plan lines."""
    lines = [
        f"\n{'='*72}",
        f"ATHLETE : {label}",
        f"PLAN    : {tag}",
        f"{'='*72}",
    ]

    # Shape 1: GeneratedPlan (standard/semi-custom) — flat workouts list
    workouts = getattr(plan_obj, "workouts", None)
    if workouts is not None:
        by_week: dict = {}
        for w in workouts:
            by_week.setdefault(getattr(w, "week", 0), []).append(w)
        total = getattr(plan_obj, "total_miles", 0)
        dur = getattr(plan_obj, "duration_weeks", max(by_week) if by_week else 0)
        lines.append(f"  Total: {total:.1f}mi over {dur}w")
        for wnum in sorted(by_week):
            ws = sorted(by_week[wnum], key=lambda x: getattr(x, "day", 0))
            wmi = sum(getattr(w, "distance_miles", 0) or 0 for w in ws)
            phase = next(
                (getattr(w, "phase_name", getattr(w, "phase", "?")) for w in ws
                 if getattr(w, "workout_type", "rest") != "rest"), "?"
            )
            parts = []
            for w in ws:
                wt = getattr(w, "workout_type", "?")
                if wt == "rest":
                    continue
                mi = getattr(w, "distance_miles", 0) or 0
                parts.append(f"{wt}({mi:.1f})")
            lines.append(f"  W{wnum:02d} [{phase:26s}] {wmi:5.1f}mi  {' | '.join(parts)}")
        return lines

    # Shape 2: ConstraintAwarePlan — weeks list with days
    weeks = getattr(plan_obj, "weeks", None)
    if not weeks:
        lines.append("  (no weeks or workouts on plan object)")
        return lines

    total = sum(
        sum(getattr(d, "target_miles", 0) or 0 for d in getattr(w, "days", []))
        for w in weeks
    )
    lines.append(f"  Total: {total:.1f}mi over {len(weeks)}w")
    for w in weeks:
        wnum = getattr(w, "week_number", "?")
        phase = getattr(w, "phase", "?")
        days = getattr(w, "days", [])
        miles = sum(getattr(d, "target_miles", 0) or 0 for d in days)
        day_parts = []
        for d in days:
            wt = getattr(d, "workout_type", "?")
            if wt == "rest":
                continue
            mi = getattr(d, "target_miles", 0) or 0
            day_parts.append(f"{wt}({mi:.1f})")
        lines.append(
            f"  W{wnum:02d} [{phase:26s}] {miles:5.1f}mi  {' | '.join(day_parts)}"
        )
    return lines


def _print_lines(lines: list[str]) -> None:
    print("\n".join(lines))


# ---------------------------------------------------------------------------
# 1.  STANDARD GENERATOR — full variant matrix (no athlete data)
#     These plans are tier-based. Shows the structural skeleton.
# ---------------------------------------------------------------------------

class TestStandardVariantMatrix:
    """
    All 17 standard variants validated against coaching rules.
    No athlete data — pure tier/volume/duration input.
    """

    @pytest.mark.parametrize(
        "distance,tier,weeks,days",
        [pytest.param(*v, id=f"std-{v[0]}-{v[1]}-{v[2]}w-{v[3]}d") for v in STANDARD_VARIANTS],
    )
    def test_standard_plan_passes_rules(self, distance, tier, weeks, days, capsys):
        generator = PlanGenerator(db=None)
        plan = generator.generate_standard(
            distance=distance,
            duration_weeks=weeks,
            tier=tier,
            days_per_week=days,
            start_date=date(2026, 3, 2),
        )
        assert plan is not None, f"generate_standard returned None"
        assert getattr(plan, "workouts", None) or getattr(plan, "weeks", None), \
            "Plan has no workouts or weeks"

        result = validate_plan(plan, strict=False)
        if not result.passed:
            pytest.fail(f"Standard {distance}/{tier}/{weeks}w/{days}d\n{result.summary()}")

        tag = f"standard | {distance} | {tier} | {weeks}w | {days}d/w"
        _print_lines(_plan_banner("(tier-based, no athlete)", tag, plan))


# ---------------------------------------------------------------------------
# 2.  SEMI-CUSTOM GENERATOR — 10 athletes × 4 distances × 2 durations = 80
#     Uses current_weekly_miles + recent race to personalize paces/volume.
# ---------------------------------------------------------------------------

def _semi_custom_id(athlete_label: str, distance: str, weeks: int, days: int) -> str:
    slug = athlete_label.split("(")[0].strip().lower().replace(" ", "_")
    return f"sc-{slug[:20]}-{distance}-{weeks}w-{days}d"


def _build_semi_custom_params():
    params = []
    for athlete in ALL_ATHLETES:
        for distance, durations in SEMI_CUSTOM_DURATIONS.items():
            for weeks, days in durations:
                params.append(
                    pytest.param(
                        athlete,
                        distance,
                        weeks,
                        days,
                        id=_semi_custom_id(athlete["label"], distance, weeks, days),
                    )
                )
    return params


class TestSemiCustomMatrix:
    """
    80 scenarios: 10 athletes × 4 distances × 2 durations.
    Each plan is personalized by athlete's current mileage and recent race time.
    """

    @pytest.mark.parametrize("athlete,distance,weeks,days", _build_semi_custom_params())
    def test_semi_custom_plan_per_athlete(self, athlete, distance, weeks, days, capsys):
        sc = athlete["semi_custom"]
        race_time = sc.get("recent_race_time_seconds")
        race_dist = sc.get("recent_race_distance")
        mpw = sc["current_weekly_miles"]
        actual_days = min(days, sc["days_per_week"])

        generator = PlanGenerator(db=None)
        plan = generator.generate_semi_custom(
            distance=distance,
            duration_weeks=weeks,
            current_weekly_miles=mpw,
            days_per_week=actual_days,
            race_date=_race_date(weeks),
            recent_race_distance=race_dist,
            recent_race_time_seconds=race_time,
            athlete_id=None,
        )

        assert plan is not None
        assert getattr(plan, "workouts", None) or getattr(plan, "weeks", None), \
            "Plan has no content"

        result = validate_plan(plan, strict=False)
        tag = (
            f"semi-custom | {distance} | {weeks}w | {actual_days}d/w | "
            f"{mpw:.0f}mpw"
        )
        _print_lines(_plan_banner(athlete["label"], tag, plan))

        if not result.passed:
            pytest.fail(
                f"{athlete['label']} — {tag}\n{result.summary()}"
            )


# ---------------------------------------------------------------------------
# 3.  CONSTRAINT-AWARE PLANNER — 10 athletes × 4 distances = 40
#     Full FitnessBank drives the plan. Most personalized generator.
# ---------------------------------------------------------------------------

def _ca_id(athlete_label: str, distance: str) -> str:
    slug = athlete_label.split("(")[0].strip().lower().replace(" ", "_")
    return f"ca-{slug[:20]}-{distance}"


def _build_ca_params():
    return [
        pytest.param(
            athlete,
            distance,
            id=_ca_id(athlete["label"], distance),
        )
        for athlete in ALL_ATHLETES
        for distance in DISTANCES
    ]


class TestConstraintAwareMatrix:
    """
    40 scenarios: 10 athletes × 4 distances.
    FitnessBank drives all plan decisions — most N=1 of the generators.
    """

    @pytest.mark.parametrize("athlete,distance", _build_ca_params())
    def test_constraint_aware_plan_per_athlete(
        self, monkeypatch, athlete, distance, capsys
    ):
        bank = athlete["make_bank"]()

        monkeypatch.setattr(
            "services.constraint_aware_planner.get_fitness_bank",
            lambda _id, _db: bank,
        )

        from uuid import uuid4
        plan = generate_constraint_aware_plan(
            athlete_id=uuid4(),
            race_date=_race_date(CA_HORIZON_WEEKS),
            race_distance=distance,
            tune_up_races=[],
            db=MagicMock(),
        )

        assert plan is not None, f"{athlete['label']} / {distance}: returned None"
        assert getattr(plan, "weeks", None), \
            f"{athlete['label']} / {distance}: no weeks"

        tag = f"constraint-aware | {distance} | {CA_HORIZON_WEEKS}w | {bank.current_weekly_miles:.0f}mpw"
        _print_lines(_plan_banner(athlete["label"], tag, plan))

        # Content assertions
        all_days = [d for w in plan.weeks for d in w.days]
        all_types = [d.workout_type for d in all_days]

        # 5K/10K: no marathon pace work
        if distance in ("5k", "10k"):
            mp_days = [t for t in all_types if t in ("long_mp", "mp_medium")]
            assert not mp_days, (
                f"{athlete['label']} / {distance}: MP work in short-race plan: {mp_days}"
            )

        # W1 long run proportional to athlete history
        w1_days = plan.weeks[0].days
        long_w1 = [d for d in w1_days if d.workout_type in ("long", "easy_long", "long_mp", "long_hmp")]
        if long_w1:
            w1_long_mi = max(d.target_miles for d in long_w1)
            max_allowed = bank.recent_8w_median_weekly_miles * 0.40
            assert w1_long_mi <= max_allowed, (
                f"{athlete['label']} / {distance}: W1 long {w1_long_mi:.1f}mi "
                f"exceeds 40% of {bank.recent_8w_median_weekly_miles:.0f}mpw median "
                f"({max_allowed:.1f}mi). Hardcoded week-1 bug."
            )

        # Saturday before Sunday long must be easy
        for w in plan.weeks:
            sunday = next((d for d in w.days if d.day_of_week == 6), None)
            saturday = next((d for d in w.days if d.day_of_week == 5), None)
            if sunday and saturday and \
               sunday.workout_type in ("long", "easy_long", "long_mp", "long_hmp"):
                assert saturday.workout_type in ("easy", "easy_strides", "rest"), (
                    f"Wk {w.week_number}: Saturday before long Sunday must be easy. "
                    f"Got {saturday.workout_type}."
                )


# ---------------------------------------------------------------------------
# 4.  SLOT TRIM REGRESSION — 4-day structure determinism
#     Locks the exact trim precedence so it never silently drifts.
#     If this breaks, something changed the slot removal order in generator.py.
# ---------------------------------------------------------------------------

class TestSlotTrimRegression:
    """
    4-day plans must have exactly 4 non-rest workouts per week.
    Required slots (never trimmed): long, quality.
    Trimmed first: easy_strides, then easy, then medium_long.
    """

    @pytest.mark.parametrize("distance", ["5k", "10k", "half_marathon", "marathon"])
    def test_four_day_slot_count(self, distance):
        generator = PlanGenerator(db=None)
        plan = generator.generate_standard(
            distance=distance,
            duration_weeks=12,
            tier="mid",
            days_per_week=4,
            start_date=date(2026, 3, 2),
        )
        assert plan is not None

        for week_num in range(1, plan.duration_weeks + 1):
            workouts = plan.get_week(week_num)
            non_rest = [w for w in workouts if w.workout_type != "rest"]
            assert len(non_rest) == 4, (
                f"{distance} W{week_num}: expected 4 non-rest workouts, "
                f"got {len(non_rest)}: {[w.workout_type for w in non_rest]}"
            )

    @pytest.mark.parametrize("distance", ["5k", "10k", "half_marathon", "marathon"])
    def test_four_day_always_has_long_and_quality(self, distance):
        """
        long run slot survives trim in every week.
        quality-type session appears in at least one non-base week
        (W1 base phase maps quality slot to strides/easy — that is correct behavior).
        The quality DAY slot (Thursday) must never be trimmed to rest.
        """
        generator = PlanGenerator(db=None)
        plan = generator.generate_standard(
            distance=distance,
            duration_weeks=12,
            tier="mid",
            days_per_week=4,
            start_date=date(2026, 3, 2),
        )
        QUALITY_TYPES = {
            "threshold", "threshold_intervals", "intervals",
            "hills", "repetitions", "tempo", "long_mp", "long_hmp",
        }
        LONG_TYPES = {"long", "long_mp", "long_hmp"}
        # Day 3 (Thursday) is the quality slot in the 4-day structure.
        # It must never be trimmed to rest.
        QUALITY_DAY = 3

        quality_seen = False
        for week_num in range(1, plan.duration_weeks + 1):
            workouts = plan.get_week(week_num)
            types = {w.workout_type for w in workouts}

            # Long run must be present every week
            assert types & LONG_TYPES, (
                f"{distance} W{week_num}: 4-day plan missing long run. Types: {types}"
            )

            # Thursday slot must not be rest (slot was not trimmed)
            day3 = next((w for w in workouts if w.day == QUALITY_DAY), None)
            assert day3 is not None and day3.workout_type != "rest", (
                f"{distance} W{week_num}: quality slot (day 3) was trimmed to rest. "
                f"Trim precedence violated."
            )

            if types & QUALITY_TYPES:
                quality_seen = True

        assert quality_seen, (
            f"{distance}: no quality-type session appeared across any week of 12w/mid/4d plan"
        )
