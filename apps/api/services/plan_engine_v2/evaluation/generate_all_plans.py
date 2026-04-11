"""
Generate full readable plans for every athlete × distance combination.

Output: one text file per athlete in evaluation/plans/
Each file shows every distance variant week-by-week so the founder
can read it like a coach and judge qualitative excellence.
"""
from __future__ import annotations

import os
import sys
import traceback
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
os.environ.setdefault("SETTINGS_MODULE", "core.settings")

from services.plan_engine_v2.engine import generate_plan_v2
from services.plan_engine_v2.models import V2PlanPreview, V2WeekPlan, V2DayPlan
from services.plan_engine_v2.pace_ladder import format_pace_sec_km
from services.plan_engine_v2.units import KM_TO_MI
from services.plan_engine_v2.evaluation.real_athletes import (
    REAL_ATHLETES, ALL_DISTANCES,
    build_fitness_bank, build_fingerprint, build_load_context,
)

PLAN_DIR = os.path.join(os.path.dirname(__file__), "plans")

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

TIMELINES = {
    "5K":           [8, 10, 14],
    "10K":          [8, 10, 14],
    "half_marathon": [10, 12, 18],
    "marathon":     [12, 16, 20, 24],
    "50K":          [12, 16, 20],
    "50_mile":      [16, 20, 28],
    "100K":         [16, 20, 28],
    "100_mile":     [18, 24, 32],
}


def _format_day(day: V2DayPlan) -> str:
    """One-line summary of a single day's workout."""
    parts = [DAY_NAMES[day.day_of_week]]

    wtype = day.workout_type
    if wtype == "rest":
        return f"{parts[0]:>3}: REST"

    title = day.title or wtype

    if day.distance_range_km:
        lo = day.distance_range_km[0] * KM_TO_MI
        hi = day.distance_range_km[1] * KM_TO_MI
        dist_str = f"{lo:.0f}-{hi:.0f}mi"
    elif day.duration_range_min:
        dist_str = f"{day.duration_range_min[0]:.0f}-{day.duration_range_min[1]:.0f}min"
    elif day.target_distance_km:
        dist_str = f"{day.target_distance_km * KM_TO_MI:.1f}mi"
    else:
        dist_str = ""

    seg_info = ""
    if day.segments:
        work_segs = [s for s in day.segments if s.type == "work"]
        if work_segs:
            total_work = sum(s.duration_min or 0 for s in work_segs)
            if total_work > 0:
                seg_info = f" [{len(work_segs)} work segs, {total_work:.0f}min total]"
            else:
                total_dist = sum(s.distance_km or 0 for s in work_segs)
                if total_dist > 0:
                    seg_info = f" [{len(work_segs)} work segs, {total_dist * KM_TO_MI:.1f}mi]"

    fuel = ""
    if day.fueling:
        fuel = f" [fuel: {day.fueling.during_run_carbs_g_per_hr}g/hr]"

    desc_preview = ""
    if day.description and len(day.description) > 5:
        d = day.description[:80]
        if len(day.description) > 80:
            d += "..."
        desc_preview = f"\n         {d}"

    return f"{parts[0]:>3}: {title} ({dist_str}){seg_info}{fuel}{desc_preview}"


def _format_week(wk: V2WeekPlan) -> str:
    """Full week display."""
    lines = []
    cut = " [CUTBACK]" if wk.is_cutback else ""
    lines.append(f"  Week {wk.week_number:>2}  |  {wk.phase}{cut}")
    lines.append(f"  {'─' * 60}")
    for day in sorted(wk.days, key=lambda d: d.day_of_week):
        lines.append(f"    {_format_day(day)}")
    return "\n".join(lines)


def _format_plan_header(
    athlete: dict, distance: str, weeks: int, plan: V2PlanPreview
) -> str:
    """Plan header with athlete context and plan summary."""
    lines = []
    lines.append(f"{'━' * 72}")
    lines.append(f"  {athlete['name']} — {distance} — {weeks} weeks")
    lines.append(f"{'━' * 72}")
    lines.append(f"  Athlete: {athlete['name']} ({athlete['tag']})")
    lines.append(f"    RPI: {athlete['rpi']}  |  Weekly: {athlete['current_weekly_miles']}mpw  |  "
                 f"Peak weekly: {athlete['peak_weekly_miles']}mpw  |  Sustainable: {athlete['sustainable_peak_weekly']}mpw")
    lines.append(f"    Current LR: {athlete['current_long_run_miles']}mi  |  "
                 f"Peak LR: {athlete['peak_long_run_miles']}mi  |  "
                 f"L30 max: {athlete['l30_max_easy_long_mi']}mi")
    lines.append(f"    Experience: {athlete['experience_level'].value}  |  "
                 f"Training age: {athlete['training_age']}yr  |  "
                 f"Limiter: {athlete.get('limiter', 'none')}")
    lines.append("")

    phases = ", ".join(
        f"{p['name']}({p['weeks']}wk)" for p in plan.phase_structure
    )
    lines.append(f"  Plan: {plan.total_weeks} weeks  |  Phases: {phases}")

    if plan.pace_ladder:
        pl = plan.pace_ladder
        pace_vals = {
            "Easy": pl.get("easy"),
            "MP": pl.get("marathon"),
            "Threshold": pl.get("threshold"),
            "5K": pl.get("interval"),
        }
        paces = []
        for name, val in pace_vals.items():
            if val:
                paces.append(f"{name}={format_pace_sec_km(val, 'mi')}/mi")
        if paces:
            lines.append(f"  Paces: {'  '.join(paces)}")

    lr_dists = []
    for wk in plan.weeks:
        for day in wk.days:
            if "long" in day.workout_type and day.distance_range_km:
                mid = (day.distance_range_km[0] + day.distance_range_km[1]) / 2
                lr_dists.append(round(mid * KM_TO_MI))
    if lr_dists:
        lines.append(f"  Long run staircase (mi): {' → '.join(str(d) for d in lr_dists)}")

    lines.append("")
    return "\n".join(lines)


def _generate_athlete_plans(athlete: dict) -> str:
    """Generate all distance variants for one athlete. Returns full text."""
    lines = []
    name = athlete["name"]
    border = "=" * 72
    lines.append(border)
    lines.append(f"  {name} — {athlete['tag']}")
    lines.append(f"  {athlete['current_weekly_miles']}mpw | RPI {athlete['rpi']} | "
                 f"{athlete['experience_level'].value} | "
                 f"LR {athlete['current_long_run_miles']}mi | "
                 f"Limiter: {athlete.get('limiter', 'none')}")
    lines.append(border)
    lines.append("")

    bank = build_fitness_bank(athlete)
    fp = build_fingerprint(athlete)
    lc = build_load_context(athlete)

    for distance in ALL_DISTANCES:
        timelines = TIMELINES.get(distance, [12])

        for weeks in timelines:
            try:
                plan = generate_plan_v2(
                    bank, fp, lc,
                    mode="race",
                    goal_event=distance,
                    weeks_available=weeks,
                )

                lines.append(_format_plan_header(athlete, distance, weeks, plan))

                for wk in plan.weeks:
                    lines.append(_format_week(wk))
                    lines.append("")

                lines.append("")

            except ValueError as e:
                lines.append(f"{'━' * 72}")
                lines.append(f"  {name} — {distance} — {weeks} weeks")
                lines.append(f"{'━' * 72}")
                lines.append(f"  REFUSED: {e}")
                lines.append("")

            except Exception as e:
                lines.append(f"{'━' * 72}")
                lines.append(f"  {name} — {distance} — {weeks} weeks")
                lines.append(f"{'━' * 72}")
                lines.append(f"  ERROR: {e}")
                lines.append(f"  {traceback.format_exc()}")
                lines.append("")

    # Build/maintain modes
    for mode, mode_weeks in [("build_volume", 6), ("build_intensity", 4), ("maintain", 4)]:
        try:
            plan = generate_plan_v2(
                bank, fp, lc,
                mode=mode,
                goal_event=None,
                weeks_available=mode_weeks,
            )

            lines.append(_format_plan_header(athlete, mode, mode_weeks, plan))

            for wk in plan.weeks:
                lines.append(_format_week(wk))
                lines.append("")

            lines.append("")

        except ValueError as e:
            lines.append(f"{'━' * 72}")
            lines.append(f"  {name} — {mode} — {mode_weeks} weeks")
            lines.append(f"{'━' * 72}")
            lines.append(f"  REFUSED: {e}")
            lines.append("")

        except Exception as e:
            lines.append(f"{'━' * 72}")
            lines.append(f"  {name} — {mode} — {mode_weeks} weeks")
            lines.append(f"{'━' * 72}")
            lines.append(f"  ERROR: {e}")
            lines.append("")

    return "\n".join(lines)


def main():
    os.makedirs(PLAN_DIR, exist_ok=True)

    print(f"Generating plans for {len(REAL_ATHLETES)} athletes...")
    print(f"Output directory: {PLAN_DIR}")
    print()

    for athlete in REAL_ATHLETES:
        name = athlete["name"]
        print(f"  Generating {name}...", end=" ", flush=True)

        output = _generate_athlete_plans(athlete)

        filepath = os.path.join(PLAN_DIR, f"{name.lower()}_plans.txt")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(output)

        plan_count = output.count("Week  1") + output.count("Week 1")
        refused_count = output.count("REFUSED:")
        error_count = output.count("ERROR:")
        print(f"{plan_count} plans, {refused_count} refused, {error_count} errors → {filepath}")

    print()
    print(f"Done. Plans are in {PLAN_DIR}/")
    print("Open any file to read full week-by-week plans for that athlete.")


if __name__ == "__main__":
    main()
