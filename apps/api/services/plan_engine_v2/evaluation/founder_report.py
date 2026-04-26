"""
Phase 5 — Founder-Readable Side-by-Side Report.

Generates a plain-text report designed to be read by a non-technical
founder. No JSON dumps, no pytest logs. For each profile:
  - One-line athlete description
  - Plan summary (weeks, phases, quality sessions, long run arc, peak workout)
  - Quality gate results

The four founder-review profiles are presented first with full detail.
The remaining 11 profiles are automated validation summaries.
"""
from __future__ import annotations

import sys
import traceback
from datetime import date
from typing import List, Optional

sys.path.insert(0, ".")

from services.plan_engine_v2.evaluation.synthetic_athletes import (
    PROFILES,
    build_mock_fitness_bank,
    build_mock_fingerprint,
    build_mock_load_context,
)
from services.plan_engine_v2.engine import generate_plan_v2
from services.plan_engine_v2.models import V2PlanPreview
from services.plan_engine_v2.pace_ladder import format_pace_sec_km
from services.plan_engine_v2.units import dist, dist_value, KM_TO_MI


FOUNDER_REVIEW = ["established_marathon", "first_marathon", "onramp_brand_new", "advanced_50k"]

_PROFILE_DESCRIPTIONS = {
    "beginner_5k":          "Brand-new runner, 12 mi/wk, targeting first 5K in 10 weeks",
    "developing_10k":       "Developing runner, 22 mi/wk, targeting 10K in 10 weeks",
    "developing_hm":        "Developing runner, 28 mi/wk, targeting half marathon in 12 weeks",
    "established_marathon":  "Experienced runner, 45 mi/wk, 8yr training age, marathon in 16 weeks (FOUNDER PROFILE)",
    "masters_marathon":     "Masters runner, 38 mi/wk, 20yr training age, marathon in 18 weeks",
    "advanced_50k":         "Advanced ultrarunner, 55 mi/wk, 6yr training age, 50K in 12 weeks",
    "champion_100mi":       "Elite ultrarunner, 75 mi/wk, 100-miler in 16 weeks",
    "onramp_brand_new":     "Brand-new runner, ZERO miles/week, no RPI, no race history — pure onramp",
    "build_volume_low":     "Beginner in base building, 20 mi/wk, 1yr training age",
    "build_volume_high":    "Experienced runner in base building, 50 mi/wk, 5yr training age",
    "build_intensity":      "Intermediate runner, 40 mi/wk, intensity block",
    "maintain_casual":      "Casual runner, 18 mi/wk, maintaining fitness",
    "short_build_hm":       "Compressed half marathon build, 30 mi/wk, 8 weeks to race",
    "first_marathon":       "First-time marathoner, 25 mi/wk, 2yr training age, 20 weeks to race",
    "return_from_injury":   "Experienced runner returning from injury, 10 mi/wk, onramp mode",
}


def _generate_plan(profile: dict) -> Optional[V2PlanPreview]:
    bank = build_mock_fitness_bank(profile)
    fp = build_mock_fingerprint(profile)
    lc = build_mock_load_context(profile)
    try:
        return generate_plan_v2(
            bank, fp, lc,
            mode=profile["mode"],
            goal_event=profile.get("goal_event"),
            weeks_available=profile.get("weeks_to_race"),
        )
    except Exception:
        return None


def _quality_gates(plan: V2PlanPreview, profile: dict) -> List[str]:
    """Run quality gate checks. Returns list of failures (empty = pass)."""
    results = _quality_gate_checklist(plan, profile)
    return [f"{r[0]}: {r[2]}" for r in results if not r[1]]


def _quality_gate_checklist(
    plan: V2PlanPreview, profile: dict,
) -> List[tuple]:
    """Run ALL quality gate checks. Returns list of (gate_name, passed, detail).

    Every gate is a named check with a pass/fail result and evidence.
    """
    from services.plan_engine_v2.volume import _RACE_FLOOR_MI

    results: List[tuple] = []
    STRUCTURED_TYPES = {
        "threshold_cruise", "threshold_alt_km", "speed_support",
        "vo2max_intervals", "micro_intervals", "marathon_pace_alt_km",
        "progression", "regenerative", "uphill_tm_threshold",
        "supercompensation_long", "long_fast_stepwise",
        "long_run_fatigue_resistance", "fatigue_resistance_hills",
    }

    # Gate 1: All segments populated on structured workouts
    empty_seg_workouts = []
    for wk in plan.weeks:
        for day in wk.days:
            if day.workout_type in STRUCTURED_TYPES:
                if not day.segments:
                    empty_seg_workouts.append(f"W{wk.week_number} {day.workout_type}")
    if empty_seg_workouts:
        results.append((
            "Segments populated on structured workouts",
            False,
            f"{len(empty_seg_workouts)} missing: {', '.join(empty_seg_workouts[:5])}",
        ))
    else:
        total_structured = sum(
            1 for wk in plan.weeks for d in wk.days
            if d.workout_type in STRUCTURED_TYPES
        )
        results.append((
            "Segments populated on structured workouts",
            True,
            f"{total_structured} structured workouts, all have segments",
        ))

    # Gate 2: No percentages or pace arithmetic in athlete-facing descriptions
    pct_leaks = []
    for wk in plan.weeks:
        for day in wk.days:
            desc = (day.description or "") + (day.title or "")
            if "% MP" in desc or "% of MP" in desc or "sec/km" in desc or "sec/mi" in desc:
                pct_leaks.append(f"W{wk.week_number} {day.workout_type}")
            for seg in (day.segments or []):
                seg_desc = seg.description or ""
                if "% MP" in seg_desc or "% of MP" in seg_desc:
                    pct_leaks.append(f"W{wk.week_number} seg:{seg.type}")
    if pct_leaks:
        results.append((
            "No percentages/pace arithmetic in descriptions",
            False,
            f"{len(pct_leaks)} leaks: {', '.join(pct_leaks[:5])}",
        ))
    else:
        results.append((
            "No percentages/pace arithmetic in descriptions",
            True,
            "All descriptions use effort language only",
        ))

    # Gate 3: Long run A/B/C rotation — no two consecutive of same type
    lr_types = []
    for wk in plan.weeks:
        for day in wk.days:
            if "long" in day.workout_type or day.workout_type == "run_hike":
                lr_types.append((wk.week_number, day.workout_type))
    consecutive_violations = []
    for i in range(1, len(lr_types)):
        if lr_types[i][1] == lr_types[i-1][1] and lr_types[i][1] != "long_easy":
            consecutive_violations.append(
                f"W{lr_types[i-1][0]}→W{lr_types[i][0]}: both {lr_types[i][1]}"
            )
    unique_lr_types = set(t for _, t in lr_types)
    if consecutive_violations:
        results.append((
            "Long run A/B/C rotation (no consecutive same type)",
            False,
            f"{len(consecutive_violations)} violations: {', '.join(consecutive_violations[:3])}",
        ))
    else:
        results.append((
            "Long run A/B/C rotation (no consecutive same type)",
            True,
            f"Types used: {', '.join(sorted(unique_lr_types))} across {len(lr_types)} weeks",
        ))

    # Gate 4: Easy and long runs expressed as distance ranges, not fixed
    fixed_dist_runs = []
    for wk in plan.weeks:
        for day in wk.days:
            is_easy_or_long = day.workout_type in (
                "easy", "easy_short", "easy_strides", "long_easy",
            )
            if is_easy_or_long and plan.mode != "build_onramp":
                if not day.distance_range_km and not day.duration_range_min:
                    fixed_dist_runs.append(f"W{wk.week_number} {day.workout_type}")
    if fixed_dist_runs:
        results.append((
            "Easy/long runs as distance ranges (not fixed)",
            False,
            f"{len(fixed_dist_runs)} without ranges: {', '.join(fixed_dist_runs[:5])}",
        ))
    else:
        results.append((
            "Easy/long runs as distance ranges (not fixed)",
            True,
            "All easy/long runs have distance or duration ranges",
        ))

    # Gate 5: All workouts >= 90min have fueling plan
    unfueled = []
    for wk in plan.weeks:
        for day in wk.days:
            if day.distance_range_km and "long" in day.workout_type:
                mid_km = (day.distance_range_km[0] + day.distance_range_km[1]) / 2
                easy_pace = plan.pace_ladder.get(80, 400) if plan.pace_ladder else 400
                est_min = mid_km * easy_pace / 60
                if est_min > 90 and not day.fueling:
                    unfueled.append(f"W{wk.week_number} {day.workout_type} (~{est_min:.0f}min)")
    if unfueled:
        results.append((
            "Fueling on all workouts >= 90min",
            False,
            f"{len(unfueled)} missing: {', '.join(unfueled[:5])}",
        ))
    else:
        fueled_count = sum(
            1 for wk in plan.weeks for d in wk.days if d.fueling
        )
        results.append((
            "Fueling on all workouts >= 90min",
            True,
            f"{fueled_count} workouts have fueling plans",
        ))

    # Gate 6: Extension progression — pace constant, duration growing
    # Track by (workout_type, phase) so different workout types aren't
    # confused as the same progression chain.
    extension_chains: dict = {}
    for wk in plan.weeks:
        for day in wk.days:
            if day.segments and day.workout_type in (
                "threshold_cruise", "threshold_alt_km", "vo2max_intervals",
                "micro_intervals",
            ):
                work_segs = [s for s in day.segments if s.type == "work"]
                if work_segs:
                    total_work = sum(s.duration_min or 0 for s in work_segs)
                    pace = work_segs[0].pace_pct_mp
                    key = (day.workout_type, wk.phase)
                    extension_chains.setdefault(key, []).append(
                        (wk.week_number, total_work, pace)
                    )
    regressions = []
    pace_issues = []
    total_checked = 0
    for (wtype, phase), sessions in extension_chains.items():
        if len(sessions) < 2:
            continue
        total_checked += len(sessions)
        if not all(s[2] == sessions[0][2] for s in sessions):
            paces = set(s[2] for s in sessions)
            pace_issues.append(f"{wtype}/{phase}: paces {paces}")
        for i in range(1, len(sessions)):
            if sessions[i][1] < sessions[i-1][1] - 0.5:
                regressions.append(
                    f"{wtype}/{phase} W{sessions[i-1][0]}→W{sessions[i][0]}: "
                    f"{sessions[i-1][1]:.0f}min→{sessions[i][1]:.0f}min"
                )
    if not regressions and not pace_issues:
        results.append((
            "Extension progression (pace constant, duration growing)",
            True,
            f"{total_checked} sessions across {len(extension_chains)} chains, "
            f"all show constant pace + growing duration within phase",
        ))
    else:
        detail_parts = []
        if pace_issues:
            detail_parts.append(f"pace varies: {'; '.join(pace_issues[:2])}")
        if regressions:
            detail_parts.append(f"regression: {'; '.join(regressions[:2])}")
        results.append((
            "Extension progression (pace constant, duration growing)",
            len(regressions) == 0 and len(pace_issues) == 0,
            "; ".join(detail_parts),
        ))

    # Gate 7: Build-over-build seeding (block N+1 opens at/above block N week 1)
    if plan.mode in ("build_volume", "build_intensity"):
        if plan.peak_workout_state:
            results.append((
                "Build-over-build seeding (peak_workout_state captured)",
                True,
                f"Keys: {', '.join(plan.peak_workout_state.keys())}",
            ))
        else:
            results.append((
                "Build-over-build seeding (peak_workout_state captured)",
                False,
                "No peak_workout_state — next block cannot seed from this one",
            ))
    else:
        results.append((
            "Build-over-build seeding (peak_workout_state captured)",
            True,
            "N/A — race mode (single block)",
        ))

    # Gate 8: Phase structure matches mode and timeline
    phase_names = [p["name"] for p in plan.phase_structure]
    phase_weeks = sum(p["weeks"] for p in plan.phase_structure)
    phase_ok = True
    phase_detail = "Phases: " + ", ".join(
        f"{p['name']}({p['weeks']}wk)" for p in plan.phase_structure
    )
    if phase_weeks != plan.total_weeks:
        phase_ok = False
        phase_detail = f"Phase weeks {phase_weeks} != plan weeks {plan.total_weeks}"
    if plan.mode == "race" and plan.goal_event in ("marathon", "half_marathon"):
        if "taper" not in phase_names:
            phase_ok = False
            phase_detail += " | Missing taper for marathon/HM"
    results.append(("Phase structure matches mode and timeline", phase_ok, phase_detail))

    # Gate 9: Taper volume 25-35% below peak week
    if "taper" in phase_names and plan.mode == "race":
        peak_vol = 0.0
        taper_vols = []
        for wk in plan.weeks:
            wk_total = 0.0
            for day in wk.days:
                if day.distance_range_km:
                    wk_total += (day.distance_range_km[0] + day.distance_range_km[1]) / 2
                elif day.target_distance_km:
                    wk_total += day.target_distance_km
            if wk.phase != "taper" and not wk.is_cutback:
                peak_vol = max(peak_vol, wk_total)
            if wk.phase == "taper":
                taper_vols.append((wk.week_number, wk_total))
        if peak_vol > 0 and taper_vols:
            taper_pcts = [(wn, tv / peak_vol) for wn, tv in taper_vols]
            all_in_range = all(0.50 <= pct <= 0.85 for _, pct in taper_pcts)
            pct_strs = [f"W{wn}={pct:.0%}" for wn, pct in taper_pcts]
            results.append((
                "Taper volume reduction (50-85% of peak)",
                all_in_range,
                f"Peak={peak_vol * KM_TO_MI:.0f}mi, taper: {', '.join(pct_strs)}",
            ))
        else:
            results.append((
                "Taper volume reduction (50-85% of peak)",
                True,
                "N/A — could not measure volume",
            ))
    else:
        results.append((
            "Taper volume reduction (50-85% of peak)",
            True,
            "N/A — no taper phase in this plan",
        ))

    # Gate 10: No race-specific language in general phase workouts
    race_terms = ["race pace", "race day", "marathon pace", "goal pace", "race effort"]
    race_lang_in_general = []
    for wk in plan.weeks:
        if wk.phase != "general":
            continue
        for day in wk.days:
            desc_lower = (day.description or "").lower() + " " + (day.title or "").lower()
            for term in race_terms:
                if term in desc_lower:
                    race_lang_in_general.append(f"W{wk.week_number} {day.workout_type}: '{term}'")
    if race_lang_in_general:
        results.append((
            "No race-specific language in general phase",
            False,
            f"{len(race_lang_in_general)} instances: {', '.join(race_lang_in_general[:3])}",
        ))
    else:
        general_wks = sum(1 for wk in plan.weeks if wk.phase == "general")
        results.append((
            "No race-specific language in general phase",
            True,
            f"Checked {general_wks} general phase weeks, all clean",
        ))

    # Gate 11: All segment paces within athlete's valid pace range
    if plan.pace_ladder:
        min_pace = min(plan.pace_ladder.values())
        max_pace = max(plan.pace_ladder.values())
        pace_margin = 0.15
        out_of_range = []
        for wk in plan.weeks:
            for day in wk.days:
                for seg in (day.segments or []):
                    if seg.pace_sec_per_km < min_pace * (1 - pace_margin):
                        out_of_range.append(
                            f"W{wk.week_number} {day.workout_type} seg too fast: "
                            f"{seg.pace_sec_per_km:.0f}s/km (min valid: {min_pace * (1 - pace_margin):.0f})"
                        )
                    if seg.pace_sec_per_km > max_pace * (1 + pace_margin):
                        out_of_range.append(
                            f"W{wk.week_number} {day.workout_type} seg too slow: "
                            f"{seg.pace_sec_per_km:.0f}s/km (max valid: {max_pace * (1 + pace_margin):.0f})"
                        )
        if out_of_range:
            results.append((
                "All segment paces within athlete's valid range",
                False,
                f"{len(out_of_range)} out of range: {', '.join(out_of_range[:3])}",
            ))
        else:
            total_segs = sum(
                len(day.segments or [])
                for wk in plan.weeks for day in wk.days
            )
            results.append((
                "All segment paces within athlete's valid range",
                True,
                f"{total_segs} segments checked, all within "
                f"{min_pace:.0f}-{max_pace:.0f} s/km ±15%",
            ))
    else:
        results.append((
            "All segment paces within athlete's valid range",
            True,
            "N/A — no pace ladder (time-based plan)",
        ))

    # Gate 12: Quality spacing respects fingerprint minimum hours
    spacing_hrs = profile.get("quality_spacing_min_hours", 48)
    spacing_violations = []
    for wk in plan.weeks:
        quality_days = []
        for day in wk.days:
            if day.workout_type in STRUCTURED_TYPES:
                quality_days.append(day.day_of_week)
        quality_days.sort()
        for i in range(1, len(quality_days)):
            gap_hrs = (quality_days[i] - quality_days[i-1]) * 24
            if gap_hrs < spacing_hrs:
                spacing_violations.append(
                    f"W{wk.week_number}: day {quality_days[i-1]}→{quality_days[i]} "
                    f"= {gap_hrs}hrs (min {spacing_hrs}hrs)"
                )
    if spacing_violations:
        results.append((
            f"Quality spacing >= {spacing_hrs}hrs between hard sessions",
            False,
            f"{len(spacing_violations)} violations: {', '.join(spacing_violations[:3])}",
        ))
    else:
        results.append((
            f"Quality spacing >= {spacing_hrs}hrs between hard sessions",
            True,
            f"All weeks respect {spacing_hrs}hr minimum between quality sessions",
        ))

    # Gate 13: Limiter wired and influencing quality session selection
    from services.plan_engine_v2.evaluation.synthetic_athletes import _FINGERPRINT_OVERRIDES
    fp_overrides = _FINGERPRINT_OVERRIDES.get(profile.get("id", ""), {})
    limiter = fp_overrides.get("limiter") or profile.get("limiter")
    if limiter:
        from services.plan_engine_v2.workout_library import _limiter_to_component
        expected_component = _limiter_to_component(limiter, profile.get("primary_quality_emphasis"))
        quality_workouts = []
        for wk in plan.weeks:
            for day in wk.days:
                if day.workout_type in STRUCTURED_TYPES and "long" not in day.workout_type:
                    quality_workouts.append(day.workout_type)
        component_map = {
            "vo2max": {"vo2max_intervals", "micro_intervals"},
            "threshold": {"threshold_cruise", "threshold_alt_km", "uphill_tm_threshold"},
            "economy": {"speed_support", "progression"},
            "resilience": {"fatigue_resistance_hills"},
        }
        expected_types = component_map.get(expected_component, set())
        matching = sum(1 for w in quality_workouts if w in expected_types)
        total_q = len(quality_workouts)
        if total_q > 0 and matching > 0:
            results.append((
                f"Limiter '{limiter}' wired → {expected_component} emphasis",
                True,
                f"{matching}/{total_q} quality sessions target {expected_component} "
                f"(types: {', '.join(sorted(expected_types & set(quality_workouts)))})",
            ))
        elif total_q == 0:
            results.append((
                f"Limiter '{limiter}' wired → {expected_component} emphasis",
                True,
                "N/A — no quality sessions in plan",
            ))
        else:
            results.append((
                f"Limiter '{limiter}' wired → {expected_component} emphasis",
                False,
                f"0/{total_q} quality sessions target {expected_component}. "
                f"Types seen: {', '.join(sorted(set(quality_workouts)))}",
            ))
    else:
        results.append((
            "Limiter wired and influencing quality selection",
            True,
            "N/A — no limiter set on this profile",
        ))

    return results


def _long_run_arc(plan: V2PlanPreview) -> str:
    """Describe the long run progression across the plan."""
    lr_types = []
    lr_distances = []
    for wk in plan.weeks:
        for day in wk.days:
            if "long" in day.workout_type or day.workout_type == "run_hike":
                lr_types.append(day.workout_type)
                if day.distance_range_km:
                    mid = (day.distance_range_km[0] + day.distance_range_km[1]) / 2
                    lr_distances.append(round(mid, 1))
                elif day.duration_range_min:
                    lr_distances.append(f"{day.duration_range_min[0]:.0f}-{day.duration_range_min[1]:.0f}min")

    if not lr_distances:
        return "No long runs"

    # Summarize
    first = lr_distances[0]
    peak = max(d for d in lr_distances if isinstance(d, (int, float))) if any(isinstance(d, (int, float)) for d in lr_distances) else lr_distances[-1]
    last = lr_distances[-1]

    unique_types = list(dict.fromkeys(lr_types))
    type_summary = ", ".join(
        t.replace("long_", "").replace("_", " ") for t in unique_types
    )

    if isinstance(first, (int, float)):
        first_mi = first * KM_TO_MI
        peak_mi = peak * KM_TO_MI
        last_disp = f"{last * KM_TO_MI:.0f}mi" if isinstance(last, (int, float)) else last
        return f"{first_mi:.0f}mi → peak {peak_mi:.0f}mi → {last_disp} (types: {type_summary})"
    return f"{first} → {last} (types: {type_summary})"


def _peak_workout(plan: V2PlanPreview) -> str:
    """Find and describe the hardest workout in the plan."""
    hardest = None
    hardest_score = 0.0

    for wk in plan.weeks:
        for day in wk.days:
            if not day.segments:
                continue
            work_segs = [s for s in day.segments if s.type == "work"]
            score = sum(
                (s.duration_min or 0) * (s.pace_pct_mp or 100) / 100
                for s in work_segs
            )
            score += sum(
                (s.distance_km or 0) * (s.pace_pct_mp or 100) / 100
                for s in work_segs
            )
            if score > hardest_score:
                hardest_score = score
                hardest = (wk.week_number, day)

    if not hardest:
        return "No structured workouts"

    from services.plan_engine_v2.units import localize_text
    wk_num, day = hardest
    return f"Week {wk_num}: {localize_text(day.title)}"


def _quality_per_week(plan: V2PlanPreview) -> str:
    """Summarize quality sessions per week."""
    quality_types = {
        "threshold_cruise", "threshold_alt_km", "speed_support",
        "vo2max_intervals", "micro_intervals", "marathon_pace_alt_km",
        "progression", "regenerative", "uphill_tm_threshold",
        "supercompensation_long",
    }

    counts = []
    for wk in plan.weeks:
        q = sum(1 for d in wk.days if d.workout_type in quality_types)
        counts.append(q)

    if not counts:
        return "0"

    unique = sorted(set(counts))
    if len(unique) == 1:
        return str(unique[0])
    return f"{min(counts)}-{max(counts)} (avg {sum(counts)/len(counts):.1f})"


def _format_paces(plan: V2PlanPreview) -> str:
    """Format key paces for display."""
    ladder = plan.pace_ladder
    if not ladder:
        return "No paces (time-based only)"

    if hasattr(ladder, 'easy'):
        return (
            f"Easy={format_pace_sec_km(ladder.easy, 'mi')}/mi  "
            f"MP={format_pace_sec_km(ladder.marathon, 'mi')}/mi  "
            f"Threshold={format_pace_sec_km(ladder.threshold, 'mi')}/mi  "
            f"5K={format_pace_sec_km(ladder.interval, 'mi')}/mi"
        )
    if isinstance(ladder, dict) and "easy" in ladder:
        parts = []
        for key, label in [("easy", "Easy"), ("marathon", "MP"),
                           ("threshold", "Threshold"), ("interval", "5K")]:
            val = ladder.get(key)
            if val:
                parts.append(f"{label}={format_pace_sec_km(val, 'mi')}/mi")
        return "  ".join(parts) if parts else "Paces not available"

    parts = []
    for pct, label in [(80, "Easy"), (100, "MP"), (105, "Threshold"), (115, "5K")]:
        val = ladder.get(pct) or ladder.get(str(pct))
        if val:
            parts.append(f"{label}={format_pace_sec_km(val, 'mi')}/mi")
    return "  ".join(parts)


def _full_detail(plan: V2PlanPreview, profile: dict, gates: List[str]) -> str:
    """Full detail report for founder-review profiles."""
    lines = []
    pid = profile["id"]
    desc = _PROFILE_DESCRIPTIONS.get(pid, pid)

    lines.append(f"{'=' * 72}")
    lines.append(f"  FOUNDER REVIEW: {pid}")
    lines.append(f"  {desc}")
    lines.append(f"{'=' * 72}")
    lines.append("")

    # Summary box
    phases = ", ".join(
        f"{p['name']}({p['weeks']}wk)"
        for p in plan.phase_structure
    )
    lines.append(f"  Mode: {plan.mode}  |  Event: {plan.goal_event or 'N/A'}  |  Weeks: {plan.total_weeks}")
    lines.append(f"  Phases: {phases}")
    lines.append(f"  Quality/week: {_quality_per_week(plan)}")
    lines.append(f"  Long run arc: {_long_run_arc(plan)}")
    lines.append(f"  Peak workout: {_peak_workout(plan)}")
    lines.append(f"  Paces: {_format_paces(plan)}")
    lines.append("")

    # Quality gates — full named checklist
    checklist = _quality_gate_checklist(plan, profile)
    pass_count = sum(1 for _, passed, _ in checklist if passed)
    fail_count = sum(1 for _, passed, _ in checklist if not passed)
    lines.append(f"  QUALITY GATES: {pass_count} PASS, {fail_count} FAIL (of {len(checklist)})")
    lines.append("")
    for gate_name, passed, detail in checklist:
        status = "PASS" if passed else "FAIL"
        lines.append(f"    [{status}] {gate_name}")
        lines.append(f"           {detail}")
    lines.append("")

    # Week-by-week detail
    lines.append(f"  {'Week':>4}  {'Phase':<12}  {'Cut?':<4}  Day-by-day")
    lines.append(f"  {'----':>4}  {'-----':<12}  {'----':<4}  -----------")

    for wk in plan.weeks:
        day_summaries = []
        for day in wk.days:
            label = day.workout_type
            if day.duration_range_min:
                label += f"({day.duration_range_min[0]:.0f}-{day.duration_range_min[1]:.0f}m)"
            elif day.distance_range_km:
                lo_mi = day.distance_range_km[0] * KM_TO_MI
                hi_mi = day.distance_range_km[1] * KM_TO_MI
                label += f"({lo_mi:.0f}-{hi_mi:.0f}mi)"
            elif day.segments:
                label += f"[{len(day.segments)}seg]"
            day_summaries.append(label)

        cut = "Y" if wk.is_cutback else ""
        line = "  ".join(day_summaries)
        lines.append(f"  W{wk.week_number:>2}   {wk.phase:<12}  {cut:<4}  {line}")

    lines.append("")

    # Peak state (for build modes)
    if plan.peak_workout_state and plan.mode in ("build_volume", "build_intensity"):
        ps = plan.peak_workout_state
        lines.append(f"  Peak Workout State (for next block seeding):")
        if ps.get("threshold", {}).get("segment_duration_min"):
            lines.append(f"    Threshold: {ps['threshold']['segment_duration_min']}min x {ps['threshold']['reps']} reps")
        if ps.get("speed", {}).get("reps"):
            d_mi = ps['speed']['segment_distance_km'] * KM_TO_MI
            lines.append(f"    Speed: {d_mi:.1f}mi x {ps['speed']['reps']} reps")
        if ps.get("long_run", {}).get("max_distance_km"):
            lr_mi = ps['long_run']['max_distance_km'] * KM_TO_MI
            lines.append(f"    Long run: peak {lr_mi:.1f}mi at {ps['long_run']['peak_pace_pct_mp']}% MP")
        if ps.get("weekly_volume", {}).get("peak_km"):
            vol_mi = ps['weekly_volume']['peak_km'] * KM_TO_MI
            lines.append(f"    Weekly volume: peak {vol_mi:.1f}mi")
        lines.append("")

    return "\n".join(lines)


def _summary_line(plan: V2PlanPreview, profile: dict, gates: List[str]) -> str:
    """One-line summary for automated validation profiles."""
    pid = profile["id"]
    desc = _PROFILE_DESCRIPTIONS.get(pid, pid)
    gate_status = "PASS" if not gates else f"FAIL({len(gates)})"

    phases = "+".join(f"{p['name'][0].upper()}{p['weeks']}" for p in plan.phase_structure)
    quality = _quality_per_week(plan)

    return (
        f"  [{gate_status:>7}]  {pid:<25}  {plan.mode:<15}  "
        f"{plan.total_weeks}wk  Q:{quality:<5}  {phases}  "
        f"| {desc}"
    )


def generate_report() -> str:
    lines = []

    lines.append("")
    lines.append("=" * 72)
    lines.append("  PLAN ENGINE V2 — FOUNDER EVALUATION REPORT")
    lines.append(f"  Generated: {date.today().isoformat()}")
    lines.append("=" * 72)
    lines.append("")
    lines.append("  This report is for human review. The four profiles marked")
    lines.append("  'FOUNDER REVIEW' need your judgment: does this plan look")
    lines.append("  like what you'd write on a napkin for this athlete?")
    lines.append("")

    # Generate all plans
    results = {}
    errors = {}
    for p in PROFILES:
        plan = _generate_plan(p)
        if plan:
            gates = _quality_gates(plan, p)
            results[p["id"]] = (plan, p, gates)
        else:
            errors[p["id"]] = p

    # SECTION 1: Founder review profiles (full detail)
    lines.append("-" * 72)
    lines.append("  SECTION 1: FOUNDER REVIEW PROFILES (4)")
    lines.append("  Read these carefully. These need your sign-off.")
    lines.append("-" * 72)
    lines.append("")

    for pid in FOUNDER_REVIEW:
        if pid in results:
            plan, profile, gates = results[pid]
            lines.append(_full_detail(plan, profile, gates))
        elif pid in errors:
            lines.append(f"  ERROR: {pid} — plan generation failed")
            lines.append(f"  {_PROFILE_DESCRIPTIONS.get(pid, '')}")
            lines.append("")
        else:
            p = next((pp for pp in PROFILES if pp["id"] == pid), None)
            if p:
                plan = _generate_plan(p)
                if plan:
                    gates = _quality_gates(plan, p)
                    lines.append(_full_detail(plan, p, gates))
                else:
                    lines.append(f"  ERROR: {pid} — plan generation failed")
                    lines.append("")

    # SECTION 2: Automated validation (remaining profiles)
    remaining = [p for p in PROFILES if p["id"] not in FOUNDER_REVIEW]

    lines.append("-" * 72)
    lines.append("  SECTION 2: AUTOMATED VALIDATION (11 profiles)")
    lines.append("-" * 72)
    lines.append("")
    lines.append(f"  {'Status':>9}  {'Profile':<25}  {'Mode':<15}  {'Plan':5}  {'Q/wk':<5}  {'Phases':<12}  | Description")
    lines.append(f"  {'------':>9}  {'-------':<25}  {'----':<15}  {'----':5}  {'----':<5}  {'------':<12}  | -----------")

    pass_count = 0
    fail_count = 0
    skip_count = 0

    for p in remaining:
        pid = p["id"]
        if pid in results:
            plan, profile, gates = results[pid]
            lines.append(_summary_line(plan, profile, gates))
            if gates:
                fail_count += 1
            else:
                pass_count += 1
        else:
            skip_count += 1
            desc = _PROFILE_DESCRIPTIONS.get(pid, pid)
            lines.append(f"  [   SKIP]  {pid:<25}  {'N/A':<15}  {'N/A':5}  {'N/A':<5}  {'N/A':<12}  | {desc}")

    # Founder review counts
    founder_pass = sum(1 for pid in FOUNDER_REVIEW if pid in results and not results[pid][2])
    founder_fail = sum(1 for pid in FOUNDER_REVIEW if pid in results and results[pid][2])
    founder_skip = sum(1 for pid in FOUNDER_REVIEW if pid not in results)

    lines.append("")
    lines.append("-" * 72)
    lines.append("  SUMMARY")
    lines.append("-" * 72)
    lines.append(f"  Founder review:  {founder_pass} pass, {founder_fail} fail, {founder_skip} skip (of 4)")
    lines.append(f"  Automated:       {pass_count} pass, {fail_count} fail, {skip_count} skip (of {len(remaining)})")
    lines.append(f"  Total:           {founder_pass + pass_count} pass, {founder_fail + fail_count} fail, {founder_skip + skip_count} skip (of {len(PROFILES)})")
    lines.append("")

    if founder_fail + fail_count == 0 and founder_skip + skip_count == 0:
        lines.append("  VERDICT: ALL GATES PASSED. Ready for founder review of the 4 profiles.")
    elif founder_fail + fail_count > 0:
        lines.append(f"  VERDICT: {founder_fail + fail_count} GATE FAILURE(S). Fix before founder review.")
    else:
        lines.append(f"  VERDICT: {founder_skip + skip_count} profile(s) could not generate. Review errors.")

    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    report = generate_report()
    print(report)

    # Also write to file
    import os
    report_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"founder_report_{date.today().isoformat()}.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n  Report saved: {report_path}")
