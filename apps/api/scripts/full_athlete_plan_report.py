#!/usr/bin/env python3
"""
Full Athlete × Plan Matrix Report
===================================

Generates every plan for every athlete and writes a human-readable
week-by-week report to stdout (and optionally a file).

Usage:
    cd apps/api
    python scripts/full_athlete_plan_report.py
    python scripts/full_athlete_plan_report.py --out report.txt
    python scripts/full_athlete_plan_report.py --athlete "founder_mirror"
    python scripts/full_athlete_plan_report.py --distance marathon
    python scripts/full_athlete_plan_report.py --generator semi_custom

Output shows:
  - Athlete profile summary
  - Week-by-week plan for every variant
  - Coaching rule validation result (PASS / FAIL with details)
"""
from __future__ import annotations

import argparse
import sys
import os
from datetime import date, timedelta
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.constraint_aware_planner import generate_constraint_aware_plan
from services.plan_framework.generator import PlanGenerator
from tests.plan_validation_helpers import validate_plan
from tests.fake_athletes import ALL_ATHLETES


# ---------------------------------------------------------------------------
DISTANCES = ["5k", "10k", "half_marathon", "marathon"]

STANDARD_VARIANTS = [
    ("5k",            "low",     8,  5),
    ("5k",            "mid",    12,  6),
    ("5k",            "high",   12,  6),
    ("10k",           "low",    12,  5),
    ("10k",           "mid",    12,  6),
    ("10k",           "high",   12,  6),
    ("half_marathon", "low",    16,  5),
    ("half_marathon", "mid",    16,  6),
    ("half_marathon", "high",   16,  6),
    ("marathon",      "builder",18,  5),
    ("marathon",      "low",    18,  5),
    ("marathon",      "mid",    18,  6),
    ("marathon",      "high",   18,  6),
]

SEMI_CUSTOM_DURATIONS = {
    "5k":            [(8, 5), (12, 6)],
    "10k":           [(8, 5), (12, 6)],
    "half_marathon": [(12, 5), (16, 6)],
    "marathon":      [(12, 6), (18, 6)],
}

CA_HORIZON = 12   # weeks


def _race_date(weeks: int) -> date:
    return date.today() + timedelta(weeks=weeks)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _separator(char: str = "=", width: int = 76) -> str:
    return char * width


def _athlete_summary(athlete: dict) -> list[str]:
    sc = athlete["semi_custom"]
    mpw = sc["current_weekly_miles"]
    race_d = sc.get("recent_race_distance") or "none"
    race_t = sc.get("recent_race_time_seconds")
    if race_t:
        h, m, s = race_t // 3600, (race_t % 3600) // 60, race_t % 60
        race_str = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
    else:
        race_str = "no race on file"

    return [
        _separator("-"),
        f"  ATHLETE: {athlete['label']}",
        f"  Notes  : {athlete['notes']}",
        f"  Volume : {mpw:.0f} mpw  |  Best race: {race_d} {race_str}",
        _separator("-"),
    ]


def _plan_lines(plan, tag: str) -> list[str]:
    """Render a full week-by-week plan as text.

    Handles two plan shapes:
      - GeneratedPlan (standard/semi-custom): has .workouts list with .week/.day attrs
      - ConstraintAwarePlan: has .weeks list with .days attrs
    """
    lines = [f"\n  >> {tag}"]

    # --- Shape 1: GeneratedPlan (standard / semi-custom) ---
    workouts = getattr(plan, "workouts", None)
    if workouts is not None:
        by_week: dict = {}
        for w in workouts:
            wk = getattr(w, "week", 0)
            by_week.setdefault(wk, []).append(w)
        total_miles = getattr(plan, "total_miles", 0)
        dur = getattr(plan, "duration_weeks", max(by_week) if by_week else 0)
        lines.append(f"    Total: {total_miles:.1f}mi over {dur}w")
        for wnum in sorted(by_week):
            ws = sorted(by_week[wnum], key=lambda x: getattr(x, "day", 0))
            weekly_miles = sum(getattr(w, "distance_miles", 0) or 0 for w in ws)
            # phase from first non-rest workout
            phase = next(
                (getattr(w, "phase_name", getattr(w, "phase", "?")) for w in ws
                 if getattr(w, "workout_type", "rest") != "rest"),
                "?",
            )
            parts = []
            for w in ws:
                wt = getattr(w, "workout_type", "?")
                if wt == "rest":
                    continue
                mi = getattr(w, "distance_miles", 0) or 0
                parts.append(f"{wt}({mi:.1f})")
            lines.append(
                f"    W{wnum:02d}  [{phase:28s}]  {weekly_miles:5.1f}mi   "
                f"{' | '.join(parts)}"
            )
        return lines

    # --- Shape 2: ConstraintAwarePlan / ModelDrivenPlan ---
    weeks = getattr(plan, "weeks", None)
    if not weeks:
        lines.append("    (no weeks or workouts on plan object)")
        return lines

    total_miles = sum(
        sum(getattr(d, "target_miles", 0) or 0 for d in getattr(w, "days", []))
        for w in weeks
    )
    dist = getattr(plan, "race_distance", getattr(plan, "distance", "?"))
    lines.append(f"    Total: {total_miles:.1f}mi over {len(weeks)}w  [{dist}]")
    for w in weeks:
        wnum   = getattr(w, "week_number", "?")
        # ConstraintAwarePlan uses .theme (WeekTheme enum); others use .phase (str)
        phase_raw = getattr(w, "phase", None) or getattr(w, "theme", None)
        phase = phase_raw.value if hasattr(phase_raw, "value") else str(phase_raw or "?")
        days   = getattr(w, "days", [])
        miles  = sum(getattr(d, "target_miles", 0) or 0 for d in days)
        parts  = []
        for d in days:
            wt = getattr(d, "workout_type", "?")
            if wt == "rest":
                continue
            mi = getattr(d, "target_miles", 0) or 0
            parts.append(f"{wt}({mi:.1f})")
        lines.append(
            f"    W{wnum:02d}  [{phase:28s}]  {miles:5.1f}mi   "
            f"{' | '.join(parts)}"
        )
    return lines


def _validation_lines(plan, tag: str) -> list[str]:
    try:
        result = validate_plan(plan, strict=False)
        status = "PASS" if result.passed else "FAIL"
        lines = [f"    Validation: {status}"]
        for f in result.failures:
            lines.append(f"      FAIL [{f.rule_id}] W{f.week or '?'}: {f.message}")
        for w in result.warnings[:5]:   # cap warnings at 5 for brevity
            lines.append(f"      WARN [{w.rule_id}] W{w.week or '?'}: {w.message}")
        if len(result.warnings) > 5:
            lines.append(f"      ... {len(result.warnings)-5} more warnings")
        return lines
    except Exception as ex:
        return [f"    Validation: ERROR - {ex}"]


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def run_standard(out, args):
    out.append("\n" + _separator() + "\n" + "  STANDARD GENERATOR (tier-based, no athlete data)" + "\n" + _separator())

    for distance, tier, weeks, days in STANDARD_VARIANTS:
        if args.distance and distance != args.distance:
            continue
        tag = f"standard | {distance} | {tier} | {weeks}w | {days}d/w"
        try:
            generator = PlanGenerator(db=None)
            plan = generator.generate_standard(
                distance=distance,
                duration_weeks=weeks,
                tier=tier,
                days_per_week=days,
                start_date=date(2026, 3, 2),
            )
            out.extend(_plan_lines(plan, tag))
            out.extend(_validation_lines(plan, tag))
        except Exception as ex:
            out.append(f"\n  ▶ {tag}")
            out.append(f"    ERROR: {ex}")


def run_semi_custom(out, args):
    out.append("\n" + _separator() + "\n" + "  SEMI-CUSTOM GENERATOR (athlete mileage + recent race)" + "\n" + _separator())

    for athlete in ALL_ATHLETES:
        filter_key = (args.athlete or "").lower().replace("_", " ")
        label_key = athlete["label"].lower()
        if args.athlete and filter_key not in label_key:
            continue
        out.extend(_athlete_summary(athlete))
        sc = athlete["semi_custom"]
        mpw = sc["current_weekly_miles"]
        race_t = sc.get("recent_race_time_seconds")
        race_d = sc.get("recent_race_distance")
        actual_days = sc["days_per_week"]

        for distance in DISTANCES:
            if args.distance and distance != args.distance:
                continue
            for weeks, days in SEMI_CUSTOM_DURATIONS[distance]:
                used_days = min(days, actual_days)
                tag = f"semi-custom | {distance} | {weeks}w | {used_days}d/w | {mpw:.0f}mpw"
                try:
                    generator = PlanGenerator(db=None)
                    plan = generator.generate_semi_custom(
                        distance=distance,
                        duration_weeks=weeks,
                        current_weekly_miles=mpw,
                        days_per_week=used_days,
                        race_date=_race_date(weeks),
                        recent_race_distance=race_d,
                        recent_race_time_seconds=race_t,
                        athlete_id=None,
                    )
                    out.extend(_plan_lines(plan, tag))
                    out.extend(_validation_lines(plan, tag))
                except Exception as ex:
                    out.append(f"\n  ▶ {tag}")
                    out.append(f"    ERROR: {ex}")


def run_constraint_aware(out, args):
    out.append("\n" + _separator() + "\n" + "  CONSTRAINT-AWARE PLANNER (full FitnessBank, most N=1)" + "\n" + _separator())

    from unittest.mock import patch as mpatch
    from uuid import uuid4

    for athlete in ALL_ATHLETES:
        filter_key = (args.athlete or "").lower().replace("_", " ")
        label_key = athlete["label"].lower()
        if args.athlete and filter_key not in label_key:
            continue
        out.extend(_athlete_summary(athlete))

        bank = athlete["make_bank"]()

        for distance in DISTANCES:
            if args.distance and distance != args.distance:
                continue
            tag = f"constraint-aware | {distance} | {CA_HORIZON}w | {bank.current_weekly_miles:.0f}mpw"
            try:
                with mpatch(
                    "services.constraint_aware_planner.get_fitness_bank",
                    lambda _id, _db, b=bank: b,
                ):
                    plan = generate_constraint_aware_plan(
                        athlete_id=uuid4(),
                        race_date=_race_date(CA_HORIZON),
                        race_distance=distance,
                        tune_up_races=[],
                        db=MagicMock(),
                    )
                out.extend(_plan_lines(plan, tag))
                out.extend(_validation_lines(plan, tag))
            except Exception as ex:
                out.append(f"\n  ▶ {tag}")
                out.append(f"    ERROR: {ex}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate full athlete × plan matrix report")
    parser.add_argument("--out", default=None, help="Write report to file (default: stdout)")
    parser.add_argument("--athlete", default=None, help="Filter to athlete (substring match)")
    parser.add_argument("--distance", default=None, choices=DISTANCES, help="Filter to distance")
    parser.add_argument(
        "--generator",
        default="all",
        choices=["all", "standard", "semi_custom", "constraint_aware"],
        help="Which generator(s) to run",
    )
    args = parser.parse_args()

    out: list[str] = []
    out.append(_separator())
    out.append("  STRIDEIQ FULL ATHLETE × PLAN MATRIX REPORT")
    out.append(f"  Generated: {date.today()}")
    out.append(f"  Athletes : {len(ALL_ATHLETES)}")
    out.append(f"  Generator: {args.generator}")
    if args.athlete:
        out.append(f"  Filter   : athlete={args.athlete}")
    if args.distance:
        out.append(f"  Filter   : distance={args.distance}")
    out.append(_separator())

    g = args.generator
    if g in ("all", "standard"):
        run_standard(out, args)
    if g in ("all", "semi_custom"):
        run_semi_custom(out, args)
    if g in ("all", "constraint_aware"):
        run_constraint_aware(out, args)

    out.append("\n" + _separator())
    out.append("  END OF REPORT")
    out.append(_separator())

    text = "\n".join(out)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Report written to {args.out}")
    else:
        # Force UTF-8 on Windows stdout
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(text)


if __name__ == "__main__":
    main()
