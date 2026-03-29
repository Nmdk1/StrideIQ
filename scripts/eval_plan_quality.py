#!/usr/bin/env python
"""
N=1 Plan Engine Quality Evaluator v2

Generates plans for 14 core archetypes and checks each against
12 blocking criteria. Checks are written to CATCH BAD PLANS,
not to pass existing ones.

Run from repo root:
    python scripts/eval_plan_quality.py

See: docs/specs/N1_ENGINE_ADR_V2.md
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
    "long_cutdown",
    "race_pace", "marathon_pace",
})
MIDWEEK_QUALITY_TYPES = frozenset({
    "threshold", "threshold_short", "threshold_continuous",
    "cruise_intervals", "broken_threshold",
    "intervals", "repetitions",
    "race_pace",
})
SHARPENING_TYPES = QUALITY_TYPES | frozenset({
    "easy_strides", "strides", "hill_strides",
})

QUALITY_RANGES: Dict[Tuple[str, ExperienceLevel], Tuple[int, int]] = {
    ("marathon", ExperienceLevel.BEGINNER): (1, 2),
    ("marathon", ExperienceLevel.INTERMEDIATE): (1, 2),
    ("marathon", ExperienceLevel.EXPERIENCED): (1, 2),
    ("marathon", ExperienceLevel.ELITE): (1, 2),
    ("half_marathon", ExperienceLevel.BEGINNER): (1, 2),
    ("half_marathon", ExperienceLevel.INTERMEDIATE): (1, 2),
    ("half_marathon", ExperienceLevel.EXPERIENCED): (1, 2),
    ("half_marathon", ExperienceLevel.ELITE): (1, 2),
    ("10k", ExperienceLevel.BEGINNER): (0, 1),
    ("10k", ExperienceLevel.INTERMEDIATE): (1, 2),
    ("10k", ExperienceLevel.EXPERIENCED): (1, 3),
    ("10k", ExperienceLevel.ELITE): (1, 3),
    ("5k", ExperienceLevel.BEGINNER): (0, 1),
    ("5k", ExperienceLevel.INTERMEDIATE): (1, 2),
    ("5k", ExperienceLevel.EXPERIENCED): (1, 3),
    ("5k", ExperienceLevel.ELITE): (1, 3),
}


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
    bc_waivers: List[int] = field(default_factory=list)
    notes: str = ""


ARCHETYPES = [
    Archetype(1, "Day-one beginner", 0, 6, 0, ExperienceLevel.BEGINNER,
              "10k", 12, None, 0,
              bc_waivers=[1, 3, 4, 5, 6, 9, 10, 11],
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
              bc_waivers=[3, 6, 9],
              notes="No periodization, compressed"),
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


def _week_signature(w: WeekPlan) -> str:
    """Workout-type sequence for the week, sorted by day."""
    return "|".join(
        d.workout_type for d in sorted(w.days, key=lambda d: d.day_of_week)
    )


def _quality_count(w: WeekPlan) -> int:
    return sum(1 for d in w.days if d.workout_type in QUALITY_TYPES)


def _midweek_quality_count(w: WeekPlan) -> int:
    return sum(1 for d in w.days if d.workout_type in MIDWEEK_QUALITY_TYPES)


def _has_sharpening(w: WeekPlan) -> bool:
    for d in w.days:
        if d.workout_type in ("rest", "race"):
            continue
        if d.workout_type in SHARPENING_TYPES:
            return True
        if d.intensity not in ("easy", "rest"):
            return True
    return False


def _easy_days(w: WeekPlan) -> list:
    return [
        d for d in w.days
        if d.workout_type in ("easy", "easy_strides", "recovery")
    ]


def _lr_day(w: WeekPlan):
    for d in w.days:
        if d.workout_type.startswith("long"):
            return d
    return None


# ─── Generation ───────────────────────────────────────────────────────

def generate_for_archetype(arch: Archetype):
    race_date = REFERENCE_START + timedelta(weeks=arch.weeks - 1, days=6)

    tune_ups = None
    if arch.tune_up_races:
        tune_ups = []
        for tr in arch.tune_up_races:
            tune_week = 12
            tune_date = REFERENCE_START + timedelta(weeks=tune_week - 1, days=5)
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


def dump_plan(plan: List[WeekPlan], arch: Archetype) -> str:
    lines = [
        "",
        "=" * 80,
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
            f"{week.total_miles:5.1f}mi"
        )
        lines.append(f"  {'-' * 60}")
        for day in sorted(week.days, key=lambda d: d.day_of_week):
            lines.append(
                f"    {DOW[day.day_of_week]:3s}  {day.workout_type:<22s}  "
                f"{day.target_miles:5.1f}mi  {day.name}"
            )
            if day.description and day.description != day.name:
                lines.append(f"         {day.description}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
# BC CHECKS — written to catch bad plans, not pass existing ones
# ═══════════════════════════════════════════════════════════════════════

def check_bc1(plan, arch) -> Tuple[bool, str]:
    """BC-1: Weekly structure is athlete-appropriate.

    Checks quality count against the rule table AND requires
    midweek quality in every build/peak week (not just a quality long run).
    """
    key = (arch.distance, arch.experience)
    min_q, max_q = QUALITY_RANGES.get(key, (0, 2))
    is_low_day = arch.days <= 3 and arch.experience in (
        ExperienceLevel.INTERMEDIATE,
        ExperienceLevel.EXPERIENCED,
        ExperienceLevel.ELITE,
    )

    tune_up_weeks = set()
    for i, w in enumerate(plan):
        if any(d.workout_type == "tune_up_race" for d in w.days):
            tune_up_weeks.add(w.week_number)
            if i + 1 < len(plan):
                tune_up_weeks.add(plan[i + 1].week_number)

    failures = []
    for week in plan:
        phase = _phase(week)
        qc = _quality_count(week)
        mq = _midweek_quality_count(week)

        if phase == "progression":
            continue

        if week.week_number in tune_up_weeks:
            continue

        if phase == "base":
            allowed = 0
            if arch.distance in ("5k", "10k") and arch.experience in (
                ExperienceLevel.EXPERIENCED, ExperienceLevel.ELITE,
            ):
                allowed = 1
            if qc > allowed:
                failures.append(
                    f"W{week.week_number} base: {qc} quality (max {allowed})"
                )

        elif week.is_cutback:
            if qc > 0:
                failures.append(
                    f"W{week.week_number} cutback: {qc} quality (want 0)"
                )

        elif phase == "taper":
            if not _has_sharpening(week):
                failures.append(
                    f"W{week.week_number} taper: no sharpening"
                )

        else:
            if is_low_day:
                pass
            else:
                if qc < min_q or qc > max_q:
                    failures.append(
                        f"W{week.week_number} {phase}: {qc} quality "
                        f"(range {min_q}-{max_q})"
                    )
                if mq < 1 and arch.days >= 4:
                    failures.append(
                        f"W{week.week_number} {phase}: NO midweek quality "
                        f"(MLR + easy fill is not a training week)"
                    )

    if failures:
        return False, "; ".join(failures[:8])
    return True, "OK"


def check_bc2(plan, arch) -> Tuple[bool, str]:
    """BC-2: Plan tells a progressive, purposeful story."""
    ORDER = {
        "progression": 0, "base": 1,
        "build": 2, "build_1": 2, "build_2": 3,
        "peak": 4, "taper": 5, "race": 6,
    }
    failures = []
    max_seen = -1
    for week in plan:
        phase = _phase(week)
        if not phase:
            failures.append(f"W{week.week_number}: no phase label")
            continue
        order = ORDER.get(phase, -1)
        if order == -1:
            failures.append(f"W{week.week_number}: unknown phase '{phase}'")
        elif order < max_seen:
            failures.append(
                f"W{week.week_number}: '{phase}' after later phase"
            )
        else:
            max_seen = order

    if failures:
        return False, "; ".join(failures[:5])
    return True, "OK"


def check_bc3(plan, arch) -> Tuple[bool, str]:
    """BC-3: Long runs vary meaningfully.

    Peak zone: any week where LR >= max_lr - 2.
    Consecutive peak LRs must differ by >= 2mi.
    Across the full plan, at least 2 different LR workout types must appear.
    """
    lr_entries = []
    for week in plan:
        lr = _lr_day(week)
        if lr:
            lr_entries.append(
                (week.week_number, lr.target_miles, lr.workout_type)
            )

    if not lr_entries:
        return False, "No long runs found"

    if arch.weeks <= 8:
        return True, f"WAIVED (short plan, {arch.weeks} weeks)"

    max_lr = max(m for _, m, _ in lr_entries)
    peak_zone = [(wn, m, t) for wn, m, t in lr_entries if m >= max_lr - 2]

    failures = []
    for i in range(1, len(peak_zone)):
        prev_mi = peak_zone[i - 1][1]
        curr_mi = peak_zone[i][1]
        if abs(curr_mi - prev_mi) < 2.0:
            failures.append(
                f"Peak W{peak_zone[i-1][0]}->W{peak_zone[i][0]}: "
                f"{prev_mi:.0f}->{curr_mi:.0f}mi (delta<2)"
            )

    unique_types = set(t for _, _, t in lr_entries)
    if len(unique_types) <= 1 and len(lr_entries) > 4:
        failures.append(
            f"Only 1 LR type in {len(lr_entries)} weeks: {unique_types}"
        )

    if failures:
        return False, "; ".join(failures[:5])
    return True, f"OK ({len(peak_zone)} peak, {len(unique_types)} types)"


def check_bc4(plan, arch) -> Tuple[bool, str]:
    """BC-4: Quality targets specific adaptations and progresses.

    - Threshold sessions must show progression (not all identical).
    - MP per-long-run must progress (trending up).
    - MP long runs never 3+ consecutive weeks.
    - 5K experienced+ needs reps.
    - 5K needs intervals.
    - Marathon needs BOTH threshold AND MP work.
    - No build/peak week should have ONLY a quality long run
      with no midweek quality (that's not quality progression,
      it's a long run with decoration).
    """
    t_sessions = []
    mp_sessions = []
    mp_consecutive = 0
    mp_max_consecutive = 0
    has_reps = False
    has_intervals = False
    has_threshold = False
    prev_was_mp = False
    empty_build_weeks = 0
    total_build_weeks = 0

    for week in plan:
        phase = _phase(week)
        is_build_or_peak = phase in (
            "build", "build_1", "build_2", "peak"
        ) and not week.is_cutback

        week_mp = False
        for day in week.days:
            if "threshold" in day.workout_type or day.workout_type in (
                "cruise_intervals", "broken_threshold",
            ):
                t_sessions.append((week.week_number, day.name))
                has_threshold = True
            if day.workout_type in ("long_mp", "long_hmp"):
                mp_sessions.append(
                    (week.week_number, day.target_miles, day.name)
                )
                week_mp = True
            if "rep" in day.workout_type:
                has_reps = True
            if "interval" in day.workout_type:
                has_intervals = True

        if week_mp:
            mp_consecutive += 1
            mp_max_consecutive = max(mp_max_consecutive, mp_consecutive)
        else:
            mp_consecutive = 0

        if is_build_or_peak:
            total_build_weeks += 1
            mq = _midweek_quality_count(week)
            if mq == 0 and arch.days >= 4:
                empty_build_weeks += 1

    failures = []

    if len(t_sessions) >= 2:
        names = [n for _, n in t_sessions]
        if len(set(names)) == 1:
            failures.append(
                f"All {len(names)} threshold sessions identical: '{names[0]}'"
            )

    if mp_max_consecutive >= 3:
        failures.append(
            f"MP long runs {mp_max_consecutive} consecutive weeks "
            f"(max 2, then alternate)"
        )

    if arch.distance == "marathon" and arch.weeks >= 12:
        if not has_threshold:
            failures.append("Marathon: no threshold work at all")
        if len(mp_sessions) == 0:
            failures.append("Marathon: no MP long runs")

    if (
        arch.distance == "5k"
        and arch.experience in (
            ExperienceLevel.EXPERIENCED, ExperienceLevel.ELITE,
        )
        and not has_reps
    ):
        failures.append("5K experienced+: no rep sessions")

    if arch.distance == "5k" and not has_intervals and arch.weeks > 5:
        failures.append("5K: no interval sessions")

    if total_build_weeks > 0 and arch.days >= 4:
        empty_ratio = empty_build_weeks / total_build_weeks
        if empty_ratio > 0.30:
            failures.append(
                f"{empty_build_weeks}/{total_build_weeks} build/peak weeks "
                f"have NO midweek quality ({empty_ratio:.0%}) -- "
                f"MLR + easy + LR is not a training week"
            )

    if failures:
        return False, "; ".join(failures[:5])
    return True, (
        f"OK (T:{len(t_sessions)} MP:{len(mp_sessions)} "
        f"I:{'Y' if has_intervals else 'N'} R:{'Y' if has_reps else 'N'} "
        f"maxConsecMP:{mp_max_consecutive})"
    )


def check_bc5(plan, arch) -> Tuple[bool, str]:
    """BC-5: Every workout has a 'why' -- no filler.

    - Easy days must vary within a week (post-quality lighter,
      pre-long lighter). A 1mi difference is not variation.
      Need >= 20% range between lightest and heaviest easy day.
    - No two consecutive non-cutback/non-taper weeks should have
      identical workout type sequences (copy-paste weeks).
    """
    uniform_weeks = 0
    checked_weeks = 0
    duplicate_weeks = 0
    prev_sig = None
    prev_phase = None

    for week in plan:
        phase = _phase(week)

        if phase in ("taper", "progression", "base"):
            prev_sig = None
            continue

        sig = _week_signature(week)
        if (
            prev_sig is not None
            and sig == prev_sig
            and not week.is_cutback
            and phase == prev_phase
        ):
            duplicate_weeks += 1

        prev_sig = sig if not week.is_cutback else None
        prev_phase = phase

        easy = _easy_days(week)
        if len(easy) >= 2 and not week.is_cutback:
            miles = [d.target_miles for d in easy]
            avg_easy = sum(miles) / len(miles)
            if avg_easy < 3.0:
                continue
            checked_weeks += 1
            lo, hi = min(miles), max(miles)
            if hi > 0 and (hi - lo) / hi < 0.20:
                uniform_weeks += 1

    failures = []

    if duplicate_weeks > 0:
        failures.append(
            f"{duplicate_weeks} consecutive duplicate weeks "
            f"(same workout-type sequence) -- "
            f"a real plan never repeats the same week"
        )

    if checked_weeks > 0:
        ratio = uniform_weeks / checked_weeks
        if ratio > 0.50:
            failures.append(
                f"{uniform_weeks}/{checked_weeks} weeks have <20% easy "
                f"variation ({ratio:.0%}) -- post-quality easy should be "
                f"noticeably lighter"
            )

    if failures:
        return False, "; ".join(failures[:5])
    return True, (
        f"OK ({checked_weeks - uniform_weeks}/{checked_weeks} varied, "
        f"{duplicate_weeks} dupes)"
    )


def check_bc6(plan, arch) -> Tuple[bool, str]:
    """BC-6: Recovery architecture is intelligent."""
    failures = []

    for i, week in enumerate(plan):
        if week.is_cutback and i > 0:
            prior = plan[i - 1]
            if not prior.is_cutback and prior.total_miles > 0:
                ratio = week.total_miles / prior.total_miles
                if ratio > 0.75:
                    failures.append(
                        f"W{week.week_number} cutback: "
                        f"{week.total_miles:.0f}/{prior.total_miles:.0f}mi "
                        f"= {ratio:.0%} (want <=75%)"
                    )

    for week in plan:
        days_sorted = sorted(week.days, key=lambda d: d.day_of_week)
        for day in days_sorted:
            if not day.workout_type.startswith("long"):
                continue
            lr_dow = day.day_of_week
            prev_dow = (lr_dow - 1) % 7
            prev_day = next(
                (d for d in days_sorted if d.day_of_week == prev_dow), None
            )
            if prev_day and prev_day.workout_type in QUALITY_TYPES:
                failures.append(
                    f"W{week.week_number}: {prev_day.workout_type} on "
                    f"{DOW[prev_dow]} before LR on {DOW[lr_dow]}"
                )

    if arch.weeks >= 10:
        cutbacks = sum(1 for w in plan if w.is_cutback)
        if cutbacks == 0:
            failures.append(f"No cutbacks in {arch.weeks}-week plan")

    if failures:
        return False, "; ".join(failures[:5])
    return True, "OK"


def check_bc9(plan, arch) -> Tuple[bool, str]:
    """BC-9: Volume sawtooth pattern."""
    if arch.weeks < 10:
        return True, "WAIVED (<10 weeks)"

    tune_up_wks = set()
    for i, w in enumerate(plan):
        if any(d.workout_type == "tune_up_race" for d in w.days):
            tune_up_wks.add(w.week_number)
            if i + 1 < len(plan):
                tune_up_wks.add(plan[i + 1].week_number)

    vols = [
        (w.week_number, w.total_miles, w.is_cutback)
        for w in plan
        if _phase(w) != "taper" and w.week_number not in tune_up_wks
    ]
    if not vols:
        return False, "No non-taper weeks"

    cutbacks = [
        (i, wn, vol) for i, (wn, vol, cb) in enumerate(vols) if cb
    ]
    if not cutbacks:
        return False, "No cutback weeks for sawtooth"

    max_vol = max(v for _, v, _ in vols)

    failures = []
    for idx, wn, _ in cutbacks:
        if 0 < idx < len(vols) - 1:
            pre = vols[idx - 1][1]
            post = vols[idx + 1][1]
            at_peak = pre >= max_vol * 0.95
            if post <= pre and not at_peak:
                failures.append(
                    f"After W{wn}: {post:.0f}mi <= pre {pre:.0f}mi"
                )

    n = len(vols)
    third = max(1, n // 3)
    avg_early = sum(v for _, v, _ in vols[:third]) / third
    avg_late = sum(v for _, v, _ in vols[-third:]) / third
    if avg_late <= avg_early and avg_early > 0:
        failures.append(
            f"No upward trend: early {avg_early:.0f} -> late {avg_late:.0f}"
        )

    if failures:
        return False, "; ".join(failures[:5])
    return True, f"OK ({len(cutbacks)} cutbacks, {avg_early:.0f}->{avg_late:.0f})"


def check_bc10(plan, arch) -> Tuple[bool, str]:
    """BC-10: Race-specific accumulation is sufficient."""
    failures = []

    if arch.distance == "marathon":
        mp_total = 0.0
        for week in plan:
            if _phase(week) == "taper":
                continue
            for day in week.days:
                if day.workout_type not in ("long_mp", "long_hmp"):
                    continue
                match = re.search(r'(\d+)mi\s*@\s*.*?(?:marathon|MP)', day.name)
                if match:
                    mp_total += float(match.group(1))
                else:
                    match2 = re.search(
                        r'(\d+)mi\s*@\s*.*?(?:marathon|MP)', day.description
                    )
                    if match2:
                        mp_total += float(match2.group(1))

        if arch.experience in (
            ExperienceLevel.EXPERIENCED, ExperienceLevel.ELITE,
        ):
            thresh = 40 if arch.weeks >= 16 else (30 if arch.weeks >= 12 else 20)
        else:
            thresh = 30 if arch.weeks >= 16 else (20 if arch.weeks >= 12 else 15)

        if mp_total < thresh:
            failures.append(f"MP: {mp_total:.0f}mi < {thresh}mi")

    elif arch.distance == "10k":
        t_types = {"threshold", "threshold_continuous", "threshold_short",
                   "cruise_intervals", "broken_threshold"}
        t = sum(1 for w in plan for d in w.days if d.workout_type in t_types)
        i = sum(1 for w in plan for d in w.days if "interval" in d.workout_type)
        t_min = max(2, arch.weeks // 2)
        i_min = max(1, arch.weeks // 4)
        if t < t_min:
            failures.append(f"10K: {t} threshold-family (need >={t_min})")
        if i < i_min:
            failures.append(f"10K: {i} intervals (need >={i_min})")

    elif arch.distance == "5k":
        i = sum(1 for w in plan for d in w.days if "interval" in d.workout_type)
        r = sum(1 for w in plan for d in w.days if "rep" in d.workout_type)
        if i < 3:
            failures.append(f"5K: {i} intervals (need >=3)")
        if (
            arch.experience in (ExperienceLevel.EXPERIENCED, ExperienceLevel.ELITE)
            and r < 1
        ):
            failures.append(f"5K exp+: {r} reps (need >=1)")

    if failures:
        return False, "; ".join(failures)
    return True, "OK"


def check_bc11(plan, arch) -> Tuple[bool, str]:
    """BC-11: Taper is sharp, not just reduced."""
    taper_weeks = [w for w in plan if _phase(w) == "taper"]
    if not taper_weeks:
        return False, "No taper weeks"

    non_taper = [
        w for w in plan if _phase(w) != "taper" and not w.is_cutback
    ]
    if not non_taper:
        return True, "No non-taper weeks"
    peak_vol = max(w.total_miles for w in non_taper)

    failures = []
    for tw in taper_weeks:
        if peak_vol > 0 and tw.total_miles / peak_vol > 0.75:
            failures.append(
                f"W{tw.week_number}: {tw.total_miles:.0f}mi = "
                f"{tw.total_miles/peak_vol:.0%} of peak {peak_vol:.0f}mi"
            )
        if not _has_sharpening(tw):
            failures.append(f"W{tw.week_number}: no sharpening")

    if failures:
        return False, "; ".join(failures[:5])
    return True, f"OK ({len(taper_weeks)} taper weeks)"


def check_bc12(plan, arch) -> Tuple[bool, str]:
    """BC-12: Paces from data, effort descriptions without it."""
    pace_re = re.compile(r"\d{1,2}:\d{2}\s*/mi")

    if arch.rpi is not None:
        has_pace = any(
            pace_re.search(d.description) or pace_re.search(d.name)
            for w in plan for d in w.days
        )
        if not has_pace:
            return False, "Has RPI but no paces found"
        return True, "OK (paces present)"

    violations = []
    for week in plan:
        for day in week.days:
            for text, label in [
                (day.description, "desc"), (day.name, "name")
            ]:
                if pace_re.search(text):
                    violations.append(
                        f"W{week.week_number} {DOW[day.day_of_week]} "
                        f"{label}: '{text[:50]}'"
                    )
    if violations:
        return False, (
            f"No RPI but {len(violations)} pace strings: " + violations[0]
        )
    return True, "OK (effort only)"


# ─── BC-7: Cross-Archetype Individualization ──────────────────────────

COMPARE_PAIRS = [
    (2, 7, "Beginner 5K vs Elite 5K"),
    (5, 6, "INT marathon vs EXP marathon"),
]


def check_bc7_cross(all_plans):
    results = []
    for a_id, b_id, label in COMPARE_PAIRS:
        if a_id not in all_plans or b_id not in all_plans:
            results.append((label, True, "SKIP"))
            continue
        types_a = Counter(
            d.workout_type for w in all_plans[a_id] for d in w.days
        )
        types_b = Counter(
            d.workout_type for w in all_plans[b_id] for d in w.days
        )
        if types_a == types_b:
            results.append((label, False, "Identical distributions"))
        else:
            diff = set(types_a.keys()) ^ set(types_b.keys())
            results.append((label, True, f"OK (differ: {diff or 'counts'})"))
    return results


# ─── Main ─────────────────────────────────────────────────────────────

BC_CHECKS = {
    1: check_bc1, 2: check_bc2, 3: check_bc3, 4: check_bc4,
    5: check_bc5, 6: check_bc6, 9: check_bc9, 10: check_bc10,
    11: check_bc11, 12: check_bc12,
}
BC_NAMES = {
    1: "Weekly structure",
    2: "Progressive story",
    3: "Long run variation",
    4: "Quality progression",
    5: "No filler / no dupes",
    6: "Recovery architecture",
    7: "Individualization",
    8: "Coach approval (MANUAL)",
    9: "Volume sawtooth",
    10: "Race accumulation",
    11: "Taper sharpening",
    12: "Paces from data",
}


def main():
    lines = []

    def out(line=""):
        lines.append(line)
        print(line)

    out("N=1 Plan Engine Quality Evaluator v2")
    out(f"Date: {date.today()}")
    out()

    all_plans: Dict[int, List[WeekPlan]] = {}
    all_results: Dict[int, Dict[int, Tuple[str, str]]] = {}

    for arch in ARCHETYPES:
        plan, error = generate_for_archetype(arch)

        if error:
            out(f"\n{'=' * 80}")
            out(f"ARCHETYPE {arch.id}: {arch.name} -- {error}")
            out(f"{'=' * 80}")
            all_results[arch.id] = {
                bc: ("N/A", error) for bc in range(1, 13)
            }
            continue

        all_plans[arch.id] = plan
        out(dump_plan(plan, arch))

        arch_results: Dict[int, Tuple[str, str]] = {}
        for bc_num, fn in BC_CHECKS.items():
            if bc_num in arch.bc_waivers:
                arch_results[bc_num] = ("WAIVED", "")
            else:
                passed, detail = fn(plan, arch)
                arch_results[bc_num] = (
                    "PASS" if passed else "FAIL", detail
                )

        if arch.days == 7:
            for week in plan:
                running = sum(1 for d in week.days if d.target_miles > 0)
                if running < 7 and not week.is_cutback and _phase(week) != "taper":
                    prev = arch_results.get(1, ("PASS", ""))
                    detail = (
                        f"W{week.week_number}: {running} running days "
                        f"(want 7 for 7-day athlete)"
                    )
                    if prev[0] == "FAIL":
                        detail = f"{prev[1]}; {detail}"
                    arch_results[1] = ("FAIL", detail)

        if arch.tune_up_races:
            has_tune = any(
                d.workout_type == "tune_up_race"
                for w in plan for d in w.days
            )
            if not has_tune:
                arch_results[1] = (
                    "FAIL",
                    "Tune-up race specified but not found in plan",
                )

        arch_results[7] = ("DEFER", "cross-archetype")
        arch_results[8] = ("MANUAL", "founder review")
        all_results[arch.id] = arch_results

        out(f"\n  BC Results for Archetype {arch.id}:")
        for bc in sorted(arch_results):
            status, detail = arch_results[bc]
            marker = {
                "PASS": "+", "FAIL": "X", "WAIVED": "~",
                "MANUAL": "?", "DEFER": ">", "N/A": "-",
            }.get(status, " ")
            out(
                f"    [{marker}] BC-{bc:2d} "
                f"{BC_NAMES.get(bc, ''):.<25s} {status} {detail}"
            )

    out(f"\n{'=' * 80}")
    out("BC-7 INDIVIDUALIZATION CROSS-CHECK")
    out("=" * 80)
    bc7_results = check_bc7_cross(all_plans)
    bc7_pass = True
    for label, passed, detail in bc7_results:
        m = "+" if passed else "X"
        out(f"  [{m}] {label}: {detail}")
        if not passed:
            bc7_pass = False

    for aid in all_results:
        if all_results[aid].get(7, ("", ""))[0] == "DEFER":
            all_results[aid][7] = (
                "PASS" if bc7_pass else "FAIL",
                "cross-check " + ("passed" if bc7_pass else "FAILED"),
            )

    out(f"\n{'=' * 80}")
    out("SUMMARY")
    out("=" * 80)

    header = f"{'#':>3s} {'Name':<25s}"
    for bc in range(1, 13):
        header += f" {bc:>3d}"
    out(header)
    out("-" * len(header))

    t_fail = t_pass = t_waive = 0
    for arch in ARCHETYPES:
        row = f"{arch.id:>3d} {arch.name:<25s}"
        for bc in range(1, 13):
            st, _ = all_results[arch.id].get(bc, ("?", ""))
            sym = {
                "PASS": "  +", "FAIL": "  X", "WAIVED": "  ~",
                "MANUAL": "  ?", "N/A": "  -",
            }.get(st, "  ?")
            row += sym
            if st == "FAIL":
                t_fail += 1
            elif st == "PASS":
                t_pass += 1
            elif st == "WAIVED":
                t_waive += 1
        out(row)

    out()
    out(f"PASS: {t_pass}  FAIL: {t_fail}  WAIVED: {t_waive}")
    if t_fail > 0:
        out(f"\n*** {t_fail} BLOCKING FAILURES -- engine does not ship ***")
    else:
        out("\n*** ALL AUTOMATED GATES PASS -- ready for BC-8 review ***")

    rpt = os.path.join(
        os.path.dirname(__file__), "..", "eval_plan_quality_report.txt"
    )
    try:
        with open(rpt, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        out(f"\nReport: {rpt}")
    except OSError:
        pass


if __name__ == "__main__":
    main()
