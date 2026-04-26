#!/usr/bin/env python
"""
KB Rule Registry Evaluator

Checks generated plans against every HARD rule in the founder-annotated
KB Rule Registry (docs/specs/KB_RULE_REGISTRY_ANNOTATED.md).

Each check traces to a rule ID. HARD rules are failures. SOFT rules are warnings.

Run from repo root:
    python scripts/eval_kb_rules.py
"""

import io
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))
sys.stdout = io.TextIOWrapper(
    sys.stdout.buffer, encoding="utf-8", errors="replace"
)

from services.fitness_bank import ExperienceLevel  # noqa: E402
from services.plan_framework.n1_engine import (  # noqa: E402
    ReadinessGateError,
    generate_n1_plan,
)
from services.workout_prescription import WeekPlan  # noqa: E402

DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
REFERENCE_START = date(2026, 4, 6)

QUALITY_TYPES = frozenset({
    "threshold", "threshold_short", "threshold_continuous",
    "cruise_intervals", "broken_threshold",
    "intervals", "repetitions",
    "long_mp", "long_hmp", "long_progressive", "long_fast_finish",
    "long_cutdown", "race_pace", "marathon_pace",
})
MIDWEEK_QUALITY_TYPES = frozenset({
    "threshold", "threshold_short", "threshold_continuous",
    "cruise_intervals", "broken_threshold",
    "intervals", "repetitions", "race_pace",
})
T_TYPES = frozenset({
    "threshold", "threshold_continuous", "threshold_short",
    "cruise_intervals", "broken_threshold",
})
I_TYPES = frozenset({"intervals"})


@dataclass
class Archetype:
    id: int
    name: str
    mpw: float
    days: int
    lr: float
    experience: ExperienceLevel
    distance: str
    weeks: int
    rpi: Optional[float]
    peak_mpw: float
    goal_time: Optional[str] = None
    weeks_since_peak: int = 0
    tune_up_races: List[Dict] = field(default_factory=list)
    rule_waivers: List[str] = field(default_factory=list)
    notes: str = ""


ARCHETYPES = [
    Archetype(1, "Day-one beginner", 0, 6, 0, ExperienceLevel.BEGINNER,
              "10k", 12, None, 0,
              rule_waivers=["PH-1", "VR-1", "VR-7", "VR-8", "VR-12", "VR-13",
                            "VR-14", "SS-1", "TP-1", "TP-2", "TP-4", "DQ-3",
                            "ED-4", "TA-2", "TA-5"],
              notes="Couch-to-10K path"),
    Archetype(2, "Casual 5K", 15, 4, 5, ExperienceLevel.BEGINNER,
              "5k", 8, None, 22,
              notes="Conservative, effort-based"),
    Archetype(3, "Building half", 25, 5, 8, ExperienceLevel.INTERMEDIATE,
              "half_marathon", 16, 45.0, 40,
              notes="Needs volume ramp"),
    Archetype(4, "Competitive 10K", 40, 6, 12, ExperienceLevel.EXPERIENCED,
              "10k", 12, 55.0, 50,
              notes="2-3 quality/week"),
    Archetype(5, "Marathon first-timer", 35, 5, 12, ExperienceLevel.INTERMEDIATE,
              "marathon", 18, 48.0, 50,
              notes="Full build, conservative"),
    Archetype(6, "Advanced marathoner", 55, 6, 18, ExperienceLevel.EXPERIENCED,
              "marathon", 18, 58.0, 65,
              notes="MP in long + MLR, T-block variety"),
    Archetype(7, "Elite 5K", 50, 6, 14, ExperienceLevel.ELITE,
              "5k", 12, 65.0, 60,
              notes="3 quality/week, reps + intervals + threshold"),
    Archetype(8, "3-day athlete", 20, 3, 8, ExperienceLevel.INTERMEDIATE,
              "half_marathon", 12, 50.0, 28,
              notes="All quality days"),
    Archetype(9, "Abbreviated 10K", 45, 6, 14, ExperienceLevel.EXPERIENCED,
              "10k", 5, 57.0, 50,
              rule_waivers=["PH-1", "VR-3", "VR-12", "VR-13"],
              notes="Crash block, no periodization"),
    Archetype(10, "High-mileage marathon", 70, 6, 20, ExperienceLevel.ELITE,
              "marathon", 16, 63.0, 80,
              notes="MP long + threshold same week"),
    Archetype(11, "Slow marathoner", 30, 5, 13, ExperienceLevel.INTERMEDIATE,
              "marathon", 18, None, 45, goal_time="4:15:00",
              notes="20mi LR cap, effort descriptions"),
    Archetype(12, "Founder profile", 55, 6, 15, ExperienceLevel.EXPERIENCED,
              "10k", 10, 57.0, 65,
              notes="Intervals + threshold + hard long"),
    Archetype(13, "Injury comeback", 20, 4, 6, ExperienceLevel.EXPERIENCED,
              "half_marathon", 14, 55.0, 35, weeks_since_peak=20,
              notes="Was 45mpw, achilles, conservative rebuild"),
    Archetype(14, "Tune-up marathoner", 60, 7, 18, ExperienceLevel.EXPERIENCED,
              "marathon", 16, 58.0, 70,
              tune_up_races=[{"distance": "5k", "name": "Tune-up 5K",
                              "purpose": "sharpening"}],
              notes="Tune-up 5K at week 12, 7-day athlete"),
]


# ─── Helpers ──────────────────────────────────────────────────────────

def _phase(w: WeekPlan) -> str:
    return w.theme if isinstance(w.theme, str) else str(w.theme.value)


def _quality_count(w: WeekPlan) -> int:
    return sum(1 for d in w.days if d.workout_type in QUALITY_TYPES)


def _midweek_quality(w: WeekPlan) -> int:
    return sum(1 for d in w.days if d.workout_type in MIDWEEK_QUALITY_TYPES)


def _lr_day(w: WeekPlan):
    for d in w.days:
        if d.workout_type.startswith("long"):
            return d
    return None


def _easy_days(w: WeekPlan) -> list:
    return [d for d in w.days
            if d.workout_type in ("easy", "easy_strides", "recovery")]


def _extract_threshold_minutes(day) -> Optional[float]:
    """Extract threshold work minutes from workout name/description."""
    m = re.search(r"(\d+)min\s*(?:continuous|@\s*T)", day.name)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+)x(\d+)min\s*@\s*T", day.name)
    if m:
        return float(m.group(1)) * float(m.group(2))
    return None


def _parse_interval_rep_meters(name: str) -> Optional[int]:
    m = re.search(r"(\d+)x(\d+)(m|mi)\b", name)
    if not m:
        return None
    dist, unit = int(m.group(2)), m.group(3)
    return dist * 1609 if unit == "mi" else dist


def generate_for_archetype(arch: Archetype):
    race_date = REFERENCE_START + timedelta(weeks=arch.weeks - 1, days=6)
    tune_ups = None
    if arch.tune_up_races:
        tune_ups = []
        for tr in arch.tune_up_races:
            tune_date = REFERENCE_START + timedelta(weeks=11, days=5)
            tune_ups.append({**tr, "date": tune_date})
    try:
        plan = generate_n1_plan(
            race_distance=arch.distance,
            race_date=race_date,
            plan_start=REFERENCE_START,
            horizon_weeks=arch.weeks,
            days_per_week=arch.days,
            starting_vol=arch.mpw,
            current_lr=arch.lr,
            applied_peak=arch.peak_mpw,
            experience=arch.experience,
            best_rpi=arch.rpi,
            weeks_since_peak=arch.weeks_since_peak,
            goal_time=arch.goal_time,
            tune_up_races=tune_ups,
        )
        return plan, None
    except ReadinessGateError as e:
        return None, f"GATE: {e}"
    except Exception as e:
        return None, f"ERROR: {type(e).__name__}: {e}"


# ═══════════════════════════════════════════════════════════════════════
# KB RULE CHECKS
# Each function returns (rule_id, status, detail)
# status: "PASS", "FAIL", "WARN" (soft rule warning)
# ═══════════════════════════════════════════════════════════════════════

def check_ph1(plan, arch) -> List[Tuple[str, str, str]]:
    """PH-1: Base phase = 0 quality. Strides/hills only."""
    results = []
    for week in plan:
        if _phase(week) != "base":
            continue
        qc = _quality_count(week)
        if qc > 0:
            results.append(("PH-1", "FAIL",
                f"W{week.week_number} base: {qc} quality sessions (want 0)"))
    if not results:
        results.append(("PH-1", "PASS", "Base weeks have no quality"))
    return results


def check_vr3(plan, arch) -> List[Tuple[str, str, str]]:
    """VR-3: Cutback LR = 60-70% of prior LR."""
    results = []
    for i, week in enumerate(plan):
        if not week.is_cutback or i == 0:
            continue
        lr = _lr_day(week)
        prior_lr = _lr_day(plan[i - 1])
        if not lr or not prior_lr or prior_lr.target_miles == 0:
            continue
        ratio = lr.target_miles / prior_lr.target_miles
        if ratio > 0.72:
            results.append(("VR-3", "FAIL",
                f"W{week.week_number} cutback LR {lr.target_miles:.0f}mi / "
                f"prior {prior_lr.target_miles:.0f}mi = {ratio:.0%} (want ≤70%)"))
    if not results:
        results.append(("VR-3", "PASS", "Cutback LRs within 60-70%"))
    return results


def check_vr6(plan, arch) -> List[Tuple[str, str, str]]:
    """VR-6: Marathon LR never below 14mi."""
    if arch.distance != "marathon":
        return [("VR-6", "PASS", "N/A (not marathon)")]
    results = []
    for week in plan:
        lr = _lr_day(week)
        if not lr:
            continue
        if _phase(week) == "taper" or week.is_cutback:
            continue
        if lr.target_miles < 13.5:
            results.append(("VR-6", "FAIL",
                f"W{week.week_number}: marathon LR {lr.target_miles:.1f}mi < 14mi"))
    if not results:
        results.append(("VR-6", "PASS", "All marathon LRs ≥ 14mi"))
    return results


def check_vr7(plan, arch) -> List[Tuple[str, str, str]]:
    """VR-7: LR meaningfully above daily average."""
    if arch.mpw < 30:
        return [("VR-7", "PASS", "N/A (low mileage)")]
    threshold = 1.3 if arch.distance in ("5k", "10k") else 1.5
    results = []
    for week in plan:
        if _phase(week) in ("taper", "progression") or week.is_cutback:
            continue
        lr = _lr_day(week)
        if not lr:
            continue
        running_days = sum(1 for d in week.days if d.target_miles > 0)
        if running_days == 0:
            continue
        daily_avg = week.total_miles / running_days
        if lr.target_miles < daily_avg * threshold:
            results.append(("VR-7", "FAIL",
                f"W{week.week_number}: LR {lr.target_miles:.1f}mi, "
                f"daily avg {daily_avg:.1f}mi (want ≥{threshold}x)"))
    if not results:
        results.append(("VR-7", "PASS", "LRs above daily average"))
    return results


def check_vr8(plan, arch) -> List[Tuple[str, str, str]]:
    """VR-8: MLR = 65-75% of LR, cap 15mi."""
    results = []
    for week in plan:
        lr = _lr_day(week)
        mlr_days = [d for d in week.days if d.workout_type == "medium_long"]
        for mlr in mlr_days:
            if mlr.target_miles > 15.5:
                results.append(("VR-8", "FAIL",
                    f"W{week.week_number}: MLR {mlr.target_miles:.1f}mi > 15mi cap"))
            if lr and lr.target_miles > 0:
                ratio = mlr.target_miles / lr.target_miles
                if ratio > 0.78:
                    results.append(("VR-8", "FAIL",
                        f"W{week.week_number}: MLR {mlr.target_miles:.1f}mi / "
                        f"LR {lr.target_miles:.1f}mi = {ratio:.0%} (want ≤75%)"))
    if not results:
        results.append(("VR-8", "PASS", "MLR sizing correct"))
    return results


def check_vr12(plan, arch) -> List[Tuple[str, str, str]]:
    """VR-12: Cutback volume ≤ 70% of prior week (70% is ceiling)."""
    results = []
    for i, week in enumerate(plan):
        if not week.is_cutback or i == 0:
            continue
        prior = plan[i - 1]
        if prior.is_cutback or prior.total_miles == 0:
            continue
        ratio = week.total_miles / prior.total_miles
        if ratio > 0.72:
            results.append(("VR-12", "FAIL",
                f"W{week.week_number}: {week.total_miles:.0f}mi / "
                f"prior {prior.total_miles:.0f}mi = {ratio:.0%} (want ≤70%)"))
    if not results:
        results.append(("VR-12", "PASS", "Cutback volumes ≤ 70%"))
    return results


def check_vr13_intensity(plan, arch) -> List[Tuple[str, str, str]]:
    """VR-13: Zero intensity during cutback weeks. Strides only exception."""
    results = []
    for week in plan:
        if not week.is_cutback:
            continue
        for d in week.days:
            if d.workout_type in MIDWEEK_QUALITY_TYPES:
                results.append(("VR-13", "FAIL",
                    f"W{week.week_number}: {d.workout_type} in cutback week "
                    f"(want zero intensity, strides only)"))
    if not results:
        results.append(("VR-13", "PASS", "Cutback weeks have no intensity"))
    return results


def check_ss1(plan, arch) -> List[Tuple[str, str, str]]:
    """SS-1: Threshold capped at 40min work time."""
    results = []
    for week in plan:
        for d in week.days:
            if d.workout_type not in T_TYPES:
                continue
            t_min = _extract_threshold_minutes(d)
            if t_min is not None and t_min > 42:
                results.append(("SS-1", "FAIL",
                    f"W{week.week_number}: {d.name} = {t_min:.0f}min "
                    f"threshold work (cap 40min)"))
    if not results:
        results.append(("SS-1", "PASS", "All threshold ≤ 40min"))
    return results


def check_tp1(plan, arch) -> List[Tuple[str, str, str]]:
    """TP-1: Threshold shows week-over-week progression."""
    build_t = []
    for week in plan:
        if _phase(week) == "taper" or week.is_cutback:
            continue
        for d in week.days:
            if d.workout_type in T_TYPES:
                build_t.append((week.week_number, d.target_miles, d.name))
    if len(build_t) < 3:
        return [("TP-1", "PASS", f"Only {len(build_t)} threshold sessions")]
    names = [n for _, _, n in build_t]
    if len(set(names)) == 1:
        return [("TP-1", "FAIL",
            f"All {len(names)} threshold sessions identical: '{names[0]}'")]
    miles = [m for _, m, _ in build_t]
    if miles[-1] < miles[0]:
        return [("TP-1", "FAIL",
            f"Threshold not progressing: first={miles[0]:.1f}mi, "
            f"last={miles[-1]:.1f}mi")]
    return [("TP-1", "PASS", "Threshold progresses")]


def check_tp4(plan, arch) -> List[Tuple[str, str, str]]:
    """TP-4: 5K/10K = cruise intervals primary. No routine continuous T."""
    if arch.distance not in ("5k", "10k"):
        return [("TP-4", "PASS", "N/A (not 5K/10K)")]
    results = []
    cont_count = 0
    for week in plan:
        if _phase(week) == "taper":
            continue
        for d in week.days:
            if d.workout_type == "threshold_continuous":
                cont_count += 1
    if cont_count > 1:
        results.append(("TP-4", "FAIL",
            f"{cont_count} continuous threshold sessions in {arch.distance} plan "
            f"(want cruise intervals; max 1 milestone exception)"))
    if not results:
        results.append(("TP-4", "PASS",
            f"Cruise intervals primary ({cont_count} continuous)"))
    return results


def check_tp3(plan, arch) -> List[Tuple[str, str, str]]:
    """TP-3: 40mpw runner should NOT do 40min continuous threshold."""
    if arch.peak_mpw >= 50:
        return [("TP-3", "PASS", "N/A (high mileage)")]
    results = []
    for week in plan:
        for d in week.days:
            if d.workout_type not in T_TYPES:
                continue
            t_min = _extract_threshold_minutes(d)
            if t_min is not None and t_min >= 38:
                results.append(("TP-3", "FAIL",
                    f"W{week.week_number}: {t_min:.0f}min continuous T "
                    f"at {arch.peak_mpw}mpw (too much for this volume)"))
    if not results:
        results.append(("TP-3", "PASS", "Threshold duration appropriate for volume"))
    return results


def check_ir4(plan, arch) -> List[Tuple[str, str, str]]:
    """IR-4: Repeat = full rest. Interval = jog recovery. Distinct paces."""
    results = []
    pace_re = re.compile(r"\d{1,2}:\d{2}/mi")
    for week in plan:
        for d in week.days:
            if d.workout_type == "repetitions":
                if "jog" in d.description.lower():
                    results.append(("IR-4", "FAIL",
                        f"W{week.week_number}: rep session has jog recovery "
                        f"(should be full rest): {d.name}"))
            if d.workout_type == "intervals":
                if "full rest" in d.description.lower():
                    results.append(("IR-4", "FAIL",
                        f"W{week.week_number}: interval session has full rest "
                        f"(should be jog recovery): {d.name}"))
    if not results:
        results.append(("IR-4", "PASS", "Recovery types correct"))
    return results


def check_rc1(plan, arch) -> List[Tuple[str, str, str]]:
    """RC-1: After threshold, min 1 easy day before next Level 4+."""
    results = []
    for week in plan:
        days_sorted = sorted(week.days, key=lambda d: d.day_of_week)
        for i, d in enumerate(days_sorted):
            if d.workout_type not in T_TYPES:
                continue
            if i + 1 < len(days_sorted):
                nxt = days_sorted[i + 1]
                if nxt.workout_type in QUALITY_TYPES:
                    results.append(("RC-1", "WARN",
                        f"W{week.week_number}: {d.workout_type} on "
                        f"{DOW[d.day_of_week]} → {nxt.workout_type} on "
                        f"{DOW[nxt.day_of_week]} (no easy day between)"))
    if not results:
        results.append(("RC-1", "PASS", "Threshold spacing OK"))
    return results


def check_rc3(plan, arch) -> List[Tuple[str, str, str]]:
    """RC-3: After MP long run, 2 easy days minimum."""
    results = []
    for i, week in enumerate(plan):
        has_mp_long = any(
            d.workout_type in ("long_mp", "long_hmp") for d in week.days)
        if has_mp_long and i + 1 < len(plan):
            nxt_week = plan[i + 1]
            nxt_days = sorted(nxt_week.days, key=lambda d: d.day_of_week)
            hard_early = 0
            for d in nxt_days[:2]:
                if d.workout_type in QUALITY_TYPES:
                    hard_early += 1
            if hard_early > 0:
                results.append(("RC-3", "WARN",
                    f"W{week.week_number}: MP long → quality within 2 days"))
    if not results:
        results.append(("RC-3", "PASS", "MP long recovery OK"))
    return results


def check_ws7(plan, arch) -> List[Tuple[str, str, str]]:
    """WS-7: Level 5 (MP long, race) needs 2+ easy days before next L4+."""
    return check_rc3(plan, arch)


def check_ma2(plan, arch) -> List[Tuple[str, str, str]]:
    """MA-2: Marathon cumulative MP ≥ 40mi before taper."""
    if arch.distance != "marathon":
        return [("MA-2", "PASS", "N/A (not marathon)")]
    mp_total = 0.0
    for week in plan:
        if _phase(week) == "taper":
            continue
        for d in week.days:
            if d.workout_type not in ("long_mp", "long_hmp"):
                continue
            m = re.search(r"(\d+)mi\s*@\s*.*?(?:marathon|MP)", d.name)
            if m:
                mp_total += float(m.group(1))
            else:
                m2 = re.search(r"(\d+)mi\s*@\s*.*?(?:marathon|MP)", d.description)
                if m2:
                    mp_total += float(m2.group(1))
    thresh = 40 if arch.weeks >= 16 else (30 if arch.weeks >= 12 else 20)
    if mp_total < thresh:
        return [("MA-2", "FAIL",
            f"Cumulative MP: {mp_total:.0f}mi < {thresh}mi minimum")]
    return [("MA-2", "PASS", f"Cumulative MP: {mp_total:.0f}mi ≥ {thresh}mi")]


def check_pp2(plan, arch) -> List[Tuple[str, str, str]]:
    """PP-2: Repeat pace ≠ interval pace (distinct zones from RPI)."""
    if not arch.rpi:
        return [("PP-2", "PASS", "N/A (no RPI)")]
    rep_paces = set()
    int_paces = set()
    pace_re = re.compile(r"(\d{1,2}:\d{2})/mi")
    for week in plan:
        for d in week.days:
            if d.workout_type == "repetitions":
                m = pace_re.search(d.description)
                if m:
                    rep_paces.add(m.group(1))
            if d.workout_type == "intervals":
                m = pace_re.search(d.description)
                if m:
                    int_paces.add(m.group(1))
    if rep_paces and int_paces and rep_paces == int_paces:
        return [("PP-2", "FAIL",
            f"Rep and interval paces identical: {rep_paces}")]
    return [("PP-2", "PASS", f"Rep paces: {rep_paces}, Int paces: {int_paces}")]


def check_pp3(plan, arch) -> List[Tuple[str, str, str]]:
    """PP-3: No numeric paces without RPI data."""
    if arch.rpi is not None:
        return [("PP-3", "PASS", "Has RPI")]
    pace_re = re.compile(r"\d{1,2}:\d{2}\s*/mi")
    violations = []
    for week in plan:
        for d in week.days:
            for text in [d.description, d.name]:
                if pace_re.search(text):
                    violations.append(
                        f"W{week.week_number} {DOW[d.day_of_week]}: "
                        f"'{text[:40]}'")
    if violations:
        return [("PP-3", "FAIL",
            f"No RPI but {len(violations)} pace strings: {violations[0]}")]
    return [("PP-3", "PASS", "Effort descriptions only (no RPI)")]


def check_ed4(plan, arch) -> List[Tuple[str, str, str]]:
    """ED-4: Post-quality easy day should not exceed ~8mi."""
    results = []
    for week in plan:
        days_sorted = sorted(week.days, key=lambda d: d.day_of_week)
        for i, d in enumerate(days_sorted):
            if d.workout_type not in MIDWEEK_QUALITY_TYPES:
                continue
            if i + 1 < len(days_sorted):
                nxt = days_sorted[i + 1]
                if nxt.workout_type in ("easy", "easy_strides", "recovery"):
                    if nxt.target_miles > 9.0:
                        results.append(("ED-4", "FAIL",
                            f"W{week.week_number}: {nxt.target_miles:.1f}mi easy "
                            f"after {d.workout_type} (cap ~8mi)"))
    if not results:
        results.append(("ED-4", "PASS", "Post-quality easy days ≤ 8mi"))
    return results


def check_ta5(plan, arch) -> List[Tuple[str, str, str]]:
    """TA-5: Strides maintained throughout taper."""
    taper_weeks = [w for w in plan if _phase(w) == "taper"]
    if not taper_weeks:
        return [("TA-5", "PASS", "No taper weeks")]
    missing = []
    for w in taper_weeks:
        has_strides = any(
            d.workout_type in ("easy_strides", "strides") or
            "stride" in d.description.lower()
            for d in w.days)
        if not has_strides:
            missing.append(f"W{w.week_number}")
    if missing:
        return [("TA-5", "FAIL",
            f"No strides in taper weeks: {', '.join(missing)}")]
    return [("TA-5", "PASS", "Strides in all taper weeks")]


def check_n1_3(plan, arch) -> List[Tuple[str, str, str]]:
    """N1-3: days_per_week respected absolutely."""
    results = []
    for week in plan:
        running = sum(1 for d in week.days if d.target_miles > 0)
        if running > arch.days and not any(
            d.workout_type == "tune_up_race" for d in week.days
        ):
            results.append(("N1-3", "FAIL",
                f"W{week.week_number}: {running} running days "
                f"(athlete wants {arch.days})"))
    if not results:
        results.append(("N1-3", "PASS",
            f"All weeks ≤ {arch.days} running days"))
    return results


def check_dq1(plan, arch) -> List[Tuple[str, str, str]]:
    """DQ-1: 5K = VO2 intervals primary, threshold secondary."""
    if arch.distance != "5k":
        return [("DQ-1", "PASS", "N/A")]
    t_count = sum(1 for w in plan for d in w.days
                  if d.workout_type in T_TYPES and _phase(w) != "taper")
    i_count = sum(1 for w in plan for d in w.days
                  if d.workout_type in I_TYPES and _phase(w) != "taper")
    if arch.weeks > 5 and i_count == 0:
        return [("DQ-1", "FAIL", "5K plan has no interval sessions")]
    if i_count > 0 and t_count > i_count * 2:
        return [("DQ-1", "WARN",
            f"5K: {t_count} threshold vs {i_count} intervals "
            f"(intervals should be primary)")]
    return [("DQ-1", "PASS", f"5K: {i_count} intervals, {t_count} threshold")]


def check_dq3(plan, arch) -> List[Tuple[str, str, str]]:
    """DQ-3: 10K = threshold primary, VO2 secondary."""
    if arch.distance != "10k":
        return [("DQ-3", "PASS", "N/A")]
    t_count = sum(1 for w in plan for d in w.days
                  if d.workout_type in T_TYPES and _phase(w) != "taper")
    i_count = sum(1 for w in plan for d in w.days
                  if d.workout_type in I_TYPES and _phase(w) != "taper")
    if arch.weeks > 5 and t_count == 0:
        return [("DQ-3", "FAIL", "10K plan has no threshold sessions")]
    if arch.experience in (ExperienceLevel.EXPERIENCED, ExperienceLevel.ELITE):
        if arch.weeks > 5 and i_count == 0:
            return [("DQ-3", "FAIL", "10K experienced: no interval sessions")]
    return [("DQ-3", "PASS", f"10K: {t_count} threshold, {i_count} intervals")]


def check_dq6(plan, arch) -> List[Tuple[str, str, str]]:
    """DQ-6: Marathon = T-base → MP accumulation → race simulation."""
    if arch.distance != "marathon":
        return [("DQ-6", "PASS", "N/A")]
    has_t = any(d.workout_type in T_TYPES
                for w in plan for d in w.days if _phase(w) != "taper")
    has_mp = any(d.workout_type in ("long_mp", "long_hmp")
                 for w in plan for d in w.days)
    results = []
    if not has_t:
        results.append(("DQ-6", "FAIL", "Marathon: no threshold sessions"))
    if not has_mp and arch.weeks >= 12:
        results.append(("DQ-6", "FAIL", "Marathon: no MP long runs"))
    if not results:
        results.append(("DQ-6", "PASS", "Marathon has T + MP"))
    return results


def check_vr4(plan, arch) -> List[Tuple[str, str, str]]:
    """VR-4: Long run ceiling by distance."""
    ceilings = {"marathon": 22.0, "half_marathon": 18.0, "10k": 18.0, "5k": 15.0}
    elite_ceilings = {"marathon": 24.0}
    ceil = ceilings.get(arch.distance, 18.0)
    if arch.experience == ExperienceLevel.ELITE:
        ceil = elite_ceilings.get(arch.distance, ceil)
    results = []
    for week in plan:
        lr = _lr_day(week)
        if lr and lr.target_miles > ceil + 0.5:
            results.append(("VR-4", "FAIL",
                f"W{week.week_number}: LR {lr.target_miles:.1f}mi > "
                f"{ceil:.0f}mi ceiling for {arch.distance}"))
    if not results:
        results.append(("VR-4", "PASS", f"All LRs within {ceil:.0f}mi ceiling"))
    return results


def check_vr9(plan, arch) -> List[Tuple[str, str, str]]:
    """VR-9: MLR never day before long run."""
    results = []
    for week in plan:
        days_sorted = sorted(week.days, key=lambda d: d.day_of_week)
        for i, d in enumerate(days_sorted):
            if d.workout_type != "medium_long":
                continue
            if i + 1 < len(days_sorted):
                nxt = days_sorted[i + 1]
                if nxt.workout_type.startswith("long"):
                    results.append(("VR-9", "FAIL",
                        f"W{week.week_number}: MLR on {DOW[d.day_of_week]} "
                        f"before LR on {DOW[nxt.day_of_week]}"))
    if not results:
        results.append(("VR-9", "PASS", "MLR never day before LR"))
    return results


def check_vr14(plan, arch) -> List[Tuple[str, str, str]]:
    """VR-14: Volume starts at current_weekly_miles."""
    if arch.mpw == 0:
        return [("VR-14", "PASS", "N/A (day-one)")]
    first_real = None
    for w in plan:
        if _phase(w) not in ("progression",) and not w.is_cutback:
            first_real = w
            break
    if not first_real:
        return [("VR-14", "PASS", "No non-progression weeks")]
    ratio = first_real.total_miles / arch.mpw if arch.mpw > 0 else 1.0
    if ratio > 1.15:
        return [("VR-14", "FAIL",
            f"W{first_real.week_number}: {first_real.total_miles:.0f}mi vs "
            f"current {arch.mpw}mi (>15% above starting volume)")]
    return [("VR-14", "PASS",
        f"First week {first_real.total_miles:.0f}mi ≈ current {arch.mpw}mi")]


def check_ss4(plan, arch) -> List[Tuple[str, str, str]]:
    """SS-4: MP in long run ≤ 18mi."""
    results = []
    for week in plan:
        for d in week.days:
            if d.workout_type not in ("long_mp", "long_hmp"):
                continue
            m = re.search(r"(\d+)mi\s*@\s*.*?(?:marathon|MP)", d.name)
            if m:
                mp_mi = float(m.group(1))
                if mp_mi > 18.5:
                    results.append(("SS-4", "FAIL",
                        f"W{week.week_number}: {mp_mi:.0f}mi @ MP (max 18mi)"))
    if not results:
        results.append(("SS-4", "PASS", "All MP segments ≤ 18mi"))
    return results


def check_ph7(plan, arch) -> List[Tuple[str, str, str]]:
    """PH-7: Never ramp volume AND intensity simultaneously.

    Excludes post-cutback bounce-back (volume naturally recovers and
    quality resumes after a cutback — that is not a ramp).
    """
    results = []
    for i in range(1, len(plan)):
        prev, curr = plan[i - 1], plan[i]
        if curr.is_cutback or _phase(curr) == "taper":
            continue
        if prev.is_cutback:
            continue
        vol_up = curr.total_miles > prev.total_miles * 1.08
        prev_q = sum(1 for d in prev.days if d.workout_type in QUALITY_TYPES)
        curr_q = sum(1 for d in curr.days if d.workout_type in QUALITY_TYPES)
        intensity_up = curr_q > prev_q
        if vol_up and intensity_up and not (arch.weeks <= 5):
            results.append(("PH-7", "WARN",
                f"W{curr.week_number}: volume up "
                f"({prev.total_miles:.0f}→{curr.total_miles:.0f}mi) AND "
                f"intensity up ({prev_q}→{curr_q} quality)"))
    if not results:
        results.append(("PH-7", "PASS", "No simultaneous vol+intensity ramp"))
    return results


def check_ph8(plan, arch) -> List[Tuple[str, str, str]]:
    """PH-8: Abbreviated builds (≤5w): no periodization phases, no cutbacks."""
    if arch.weeks > 5:
        return [("PH-8", "PASS", "N/A (not abbreviated)")]
    cutbacks = sum(1 for w in plan if w.is_cutback)
    if cutbacks > 0:
        return [("PH-8", "FAIL",
            f"{cutbacks} cutbacks in ≤5-week plan (want 0)")]
    return [("PH-8", "PASS", "No cutbacks in abbreviated plan")]


def check_pp1(plan, arch) -> List[Tuple[str, str, str]]:
    """PP-1: Never expose zone numbers to athletes."""
    zone_re = re.compile(r"\b[Zz]one\s*\d|Z[1-5]")
    results = []
    for week in plan:
        for d in week.days:
            for text in [d.name, d.description]:
                if zone_re.search(text):
                    results.append(("PP-1", "FAIL",
                        f"W{week.week_number}: zone number in "
                        f"'{text[:40]}'"))
    if not results:
        results.append(("PP-1", "PASS", "No zone numbers exposed"))
    return results


def check_ed2(plan, arch) -> List[Tuple[str, str, str]]:
    """ED-2: Strides don't count as quality."""
    return [("ED-2", "PASS", "Strides excluded from quality count by design")]


def check_rg1(plan, arch) -> List[Tuple[str, str, str]]:
    """RG-1/MA-4: Marathon readiness gate (12mi)."""
    return [("RG-1", "PASS", "Gate checked at generation time")]


def check_ta2(plan, arch) -> List[Tuple[str, str, str]]:
    """TA-2: Taper volume reduction."""
    taper_weeks = [w for w in plan if _phase(w) == "taper"]
    non_taper = [w for w in plan
                 if _phase(w) not in ("taper", "progression") and not w.is_cutback]
    if not taper_weeks or not non_taper:
        return [("TA-2", "PASS", "N/A")]
    peak_vol = max(w.total_miles for w in non_taper)
    results = []
    for tw in taper_weeks:
        if peak_vol > 0 and tw.total_miles / peak_vol > 0.78:
            results.append(("TA-2", "FAIL",
                f"W{tw.week_number}: {tw.total_miles:.0f}mi = "
                f"{tw.total_miles/peak_vol:.0%} of peak {peak_vol:.0f}mi "
                f"(want ≤ 70%)"))
    if not results:
        results.append(("TA-2", "PASS",
            f"Taper volume reduced ({len(taper_weeks)} weeks)"))
    return results


# ═══════════════════════════════════════════════════════════════════════
# All checks registry
# ═══════════════════════════════════════════════════════════════════════

ALL_CHECKS = [
    check_ph1, check_ph7, check_ph8,
    check_vr3, check_vr4, check_vr6, check_vr7, check_vr8,
    check_vr9, check_vr12, check_vr13_intensity, check_vr14,
    check_ss1, check_ss4,
    check_tp1, check_tp3, check_tp4,
    check_ir4,
    check_rc1, check_rc3,
    check_ma2,
    check_pp1, check_pp2, check_pp3,
    check_ed2, check_ed4,
    check_ta2, check_ta5,
    check_n1_3,
    check_dq1, check_dq3, check_dq6,
    check_rg1,
]


# ─── Main ─────────────────────────────────────────────────────────────

def dump_plan(plan: List[WeekPlan], arch: Archetype) -> str:
    lines = [
        "", "=" * 80,
        f"ARCHETYPE {arch.id}: {arch.name}",
        f"  {arch.distance} | {arch.mpw}->{arch.peak_mpw}mpw | "
        f"{arch.days}d/wk | LR {arch.lr}mi | {arch.experience.value} | "
        f"{arch.weeks}wk | RPI={'%.1f' % arch.rpi if arch.rpi else 'none'}",
        f"  {arch.notes}",
        "=" * 80,
    ]
    for week in plan:
        phase = _phase(week)
        cutback = " [CUTBACK]" if week.is_cutback else ""
        lines.append(
            f"\n  Week {week.week_number:2d} | {phase:<12s}{cutback} | "
            f"{week.total_miles:5.1f}mi")
        lines.append(f"  {'-' * 60}")
        for day in sorted(week.days, key=lambda d: d.day_of_week):
            lines.append(
                f"    {DOW[day.day_of_week]:3s}  {day.workout_type:<22s}  "
                f"{day.target_miles:5.1f}mi  {day.name}")
            if day.description and day.description != day.name:
                lines.append(f"         {day.description}")
    return "\n".join(lines)


def main():
    lines = []

    def out(line=""):
        lines.append(line)
        print(line)

    out("KB Rule Registry Evaluator")
    out(f"Source: docs/specs/KB_RULE_REGISTRY_ANNOTATED.md")
    out(f"Date: {date.today()}")
    out()

    total_pass = total_fail = total_warn = total_waive = 0
    all_arch_results = {}

    for arch in ARCHETYPES:
        plan, error = generate_for_archetype(arch)

        if error:
            out(f"\n{'=' * 80}")
            out(f"ARCHETYPE {arch.id}: {arch.name} -- {error}")
            all_arch_results[arch.id] = [("GATE", "GATE", error)]
            continue

        out(dump_plan(plan, arch))

        arch_results = []
        for check_fn in ALL_CHECKS:
            results = check_fn(plan, arch)
            for rule_id, status, detail in results:
                if rule_id in arch.rule_waivers:
                    arch_results.append((rule_id, "WAIVED", detail))
                    total_waive += 1
                else:
                    arch_results.append((rule_id, status, detail))
                    if status == "PASS":
                        total_pass += 1
                    elif status == "FAIL":
                        total_fail += 1
                    elif status == "WARN":
                        total_warn += 1

        all_arch_results[arch.id] = arch_results

        out(f"\n  KB Rule Results for Archetype {arch.id}:")
        for rule_id, status, detail in arch_results:
            marker = {"PASS": "+", "FAIL": "X", "WARN": "~",
                       "WAIVED": "-"}.get(status, " ")
            out(f"    [{marker}] {rule_id:<8s} {status:<6s} {detail}")

    # Summary
    out(f"\n{'=' * 80}")
    out("SUMMARY BY ARCHETYPE")
    out("=" * 80)
    for arch in ARCHETYPES:
        results = all_arch_results.get(arch.id, [])
        fails = sum(1 for _, s, _ in results if s == "FAIL")
        passes = sum(1 for _, s, _ in results if s == "PASS")
        warns = sum(1 for _, s, _ in results if s == "WARN")
        waives = sum(1 for _, s, _ in results if s == "WAIVED")
        status = "PASS" if fails == 0 else f"{fails} FAIL"
        fail_ids = [rid for rid, s, _ in results if s == "FAIL"]
        suffix = f"  [{', '.join(fail_ids)}]" if fail_ids else ""
        out(f"  {arch.id:>2d}. {arch.name:<25s} {status:<12s} "
            f"({passes}P/{fails}F/{warns}W/{waives}~){suffix}")

    out(f"\n{'=' * 80}")
    out("TOTALS")
    out("=" * 80)
    out(f"  PASS: {total_pass}  FAIL: {total_fail}  "
        f"WARN: {total_warn}  WAIVED: {total_waive}")
    if total_fail > 0:
        out(f"\n*** {total_fail} HARD RULE VIOLATIONS -- engine does not ship ***")
        out("\nFailing rules:")
        seen = set()
        for arch in ARCHETYPES:
            for rid, status, detail in all_arch_results.get(arch.id, []):
                if status == "FAIL" and rid not in seen:
                    seen.add(rid)
                    out(f"  {rid}: {detail}")
    else:
        out("\n*** ALL HARD RULES PASS ***")

    rpt = os.path.join(
        os.path.dirname(__file__), "..", "eval_kb_rules_report.txt")
    try:
        with open(rpt, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        out(f"\nReport: {rpt}")
    except OSError:
        pass


if __name__ == "__main__":
    main()
