from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)

from models import Activity, TrainingPlan, PlannedWorkout, Athlete
from core.date_utils import calculate_age
from services.coach_tools._utils import (
    _iso, _mi_from_m, _pace_str_mi, _pace_str, _relative_date,
    _preferred_units, _fmt_mmss, _pace_seconds_from_text,
    _guardrails_from_pain, _M_PER_MI,
)


def get_plan_week(db: Session, athlete_id: UUID) -> Dict[str, Any]:
    """
    Current week's plan.
    """
    from services.timezone_utils import get_athlete_timezone_from_db, athlete_local_today
    _tz = get_athlete_timezone_from_db(db, athlete_id)
    today = athlete_local_today(_tz)
    week_start = today - timedelta(days=today.weekday())  # Monday
    week_end = week_start + timedelta(days=6)

    plan = (
        db.query(TrainingPlan)
        .filter(TrainingPlan.athlete_id == athlete_id, TrainingPlan.status == "active")
        .first()
    )

    workouts: List[PlannedWorkout] = []
    if plan:
        workouts = (
            db.query(PlannedWorkout)
            .filter(
                PlannedWorkout.plan_id == plan.id,
                PlannedWorkout.scheduled_date >= week_start,
                PlannedWorkout.scheduled_date <= week_end,
            )
            .order_by(PlannedWorkout.scheduled_date.asc())
            .all()
        )

    workout_rows: List[Dict[str, Any]] = []
    evidence: List[Dict[str, Any]] = []

    for w in workouts:
        _w_rel = _relative_date(w.scheduled_date, today)
        workout_rows.append(
            {
                "planned_workout_id": str(w.id),
                "scheduled_date": f"{w.scheduled_date.isoformat()} {_w_rel}",
                "title": w.title,
                "workout_type": w.workout_type,
                "workout_subtype": w.workout_subtype,
                "completed": bool(w.completed),
                "skipped": bool(w.skipped),
                "target_distance_km": float(w.target_distance_km) if w.target_distance_km is not None else None,
                "target_duration_minutes": int(w.target_duration_minutes)
                if w.target_duration_minutes is not None
                else None,
            }
        )
        evidence.append(
            {
                "type": "planned_workout",
                "id": str(w.id),
                "date": f"{w.scheduled_date.isoformat()} {_w_rel}",
                "value": f"{w.title} ({w.workout_type})",
                "planned_workout_id": str(w.id),
                "scheduled_date": f"{w.scheduled_date.isoformat()} {_w_rel}",
            }
        )

    # --- Narrative ---
    pw_parts: List[str] = []
    if plan:
        pw_parts.append(f"Active plan: {plan.name or 'Unnamed'}.")
        if plan.goal_race_name:
            pw_parts.append(f"Goal race: {plan.goal_race_name}.")
        if plan.goal_race_date:
            days_until = (plan.goal_race_date - today).days
            pw_parts.append(f"Race date: {plan.goal_race_date.isoformat()} ({days_until} days away).")
        if plan.goal_time_seconds:
            h = plan.goal_time_seconds // 3600
            m = (plan.goal_time_seconds % 3600) // 60
            s = plan.goal_time_seconds % 60
            goal_fmt = f"{h}:{m:02d}:{s:02d}"
            pw_parts.append(f"Goal time: {goal_fmt}.")
        if plan.goal_time_seconds and plan.goal_race_distance_m:
            sec_per_mi = plan.goal_time_seconds / (plan.goal_race_distance_m / _M_PER_MI)
            pm = int(sec_per_mi // 60)
            ps = int(round(sec_per_mi % 60))
            pw_parts.append(f"Required pace: {pm}:{ps:02d}/mi.")
    else:
        pw_parts.append("No active training plan.")

    completed = sum(1 for w in workout_rows if w.get("completed"))
    total_wo = len(workout_rows)
    if total_wo:
        pw_parts.append(f"This week: {total_wo} workouts scheduled, {completed} completed.")
    else:
        pw_parts.append("No workouts scheduled this week.")
    plan_narrative = " ".join(pw_parts)

    return {
        "ok": True,
        "tool": "get_plan_week",
        "generated_at": _iso(datetime.utcnow()),
        "narrative": plan_narrative,
        "data": {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "plan": (
                {
                    "plan_id": str(plan.id),
                    "name": plan.name,
                    "goal_race_name": plan.goal_race_name,
                    "goal_race_date": plan.goal_race_date.isoformat() if plan.goal_race_date else None,
                    "goal_race_distance_m": plan.goal_race_distance_m,
                    "goal_time_seconds": plan.goal_time_seconds,
                    "goal_time_formatted": (
                        f"{plan.goal_time_seconds // 3600}:{(plan.goal_time_seconds % 3600) // 60:02d}:{plan.goal_time_seconds % 60:02d}"
                        if plan.goal_time_seconds else None
                    ),
                    "goal_pace_per_mile": (
                        f"{int((plan.goal_time_seconds / (plan.goal_race_distance_m / _M_PER_MI)) // 60)}:{int(round((plan.goal_time_seconds / (plan.goal_race_distance_m / _M_PER_MI)) % 60)):02d}/mi"
                        if plan.goal_time_seconds and plan.goal_race_distance_m else None
                    ),
                    "days_until_race": (plan.goal_race_date - today).days if plan.goal_race_date else None,
                    "total_weeks": plan.total_weeks,
                }
                if plan
                else None
            ),
            "workouts": workout_rows,
        },
        "evidence": evidence,
    }



def get_training_prescription_window(
    db: Session,
    athlete_id: UUID,
    *,
    start_date: Optional[str] = None,
    days: int = 1,
    time_available_min: Optional[int] = None,
    weekly_mileage_target: Optional[float] = None,
    facilities: Optional[List[str]] = None,
    pain_flag: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Deterministic N=1 prescription for up to 7 days.

    This uses:
    - athlete trailing history (baseline + recent volume trends)
    - athlete-stated constraints (time/mileage/pain) via intent snapshot or params
    - deterministic plan generator primitives (paces + template selection)
    """
    from services.timezone_utils import get_athlete_timezone_from_db, to_activity_local_date, athlete_local_today
    _tz = get_athlete_timezone_from_db(db, athlete_id)
    _today_local = athlete_local_today(_tz)
    now = datetime.utcnow()
    try:
        days = max(1, min(int(days), 7))
        units = _preferred_units(db, athlete_id)

        # Resolve date window
        if start_date:
            try:
                start = date.fromisoformat(start_date)
            except Exception:
                start = _today_local
        else:
            start = _today_local
        end = start + timedelta(days=days - 1)

        # Pull intent snapshot as default athlete input (self-guided coaching).
        snap = _get_intent_snapshot(db, athlete_id)
        if pain_flag is None and snap and snap.pain_flag:
            pain_flag = snap.pain_flag
        if time_available_min is None and snap and snap.time_available_min is not None:
            time_available_min = int(snap.time_available_min)
        if weekly_mileage_target is None and snap and snap.weekly_mileage_target is not None:
            weekly_mileage_target = float(snap.weekly_mileage_target)

        pain_flag_norm = (pain_flag or "none").strip().lower()
        if pain_flag_norm not in ("none", "niggle", "pain"):
            pain_flag_norm = "none"

        # Baseline + paces from plan generator (reused).
        from services.model_driven_plan_generator import ModelDrivenPlanGenerator
        from services.optimal_load_calculator import TrainingPhase as GenPhase
        from models import TrainingPlan, PlannedWorkout, Activity

        gen = ModelDrivenPlanGenerator(db, feature_flags=None)
        baseline = gen._get_established_baseline(athlete_id)
        paces = gen._get_training_paces(athlete_id, goal_time=None, distance_m=42195)

        # Recent volume trends (last 4 full weeks, athlete-derived).
        def _weekly_miles_for_last_n_weeks(n: int = 4) -> List[float]:
            today = _today_local
            end_week_start = today - timedelta(days=today.weekday())  # Monday
            start_week_start = end_week_start - timedelta(days=7 * (n - 1))
            start_dt = datetime.combine(start_week_start, datetime.min.time())
            end_dt = datetime.combine(end_week_start + timedelta(days=7), datetime.min.time())
            runs = (
                db.query(Activity)
                .filter(
                    Activity.athlete_id == athlete_id,
                    Activity.sport == "run",
                    Activity.start_time >= start_dt,
                    Activity.start_time < end_dt,
                )
                .all()
            )
            buckets: Dict[str, float] = {}
            for w in range(n):
                ws = start_week_start + timedelta(days=7 * w)
                buckets[ws.isoformat()] = 0.0
            for a in runs:
                d = to_activity_local_date(a, _tz)
                ws = d - timedelta(days=d.weekday())
                key = ws.isoformat()
                if key in buckets:
                    buckets[key] += float(a.distance_m or 0) / _M_PER_MI
            return [round(buckets[k], 1) for k in sorted(buckets.keys())]

        last4 = _weekly_miles_for_last_n_weeks(4)
        recent_weekly_avg = round(sum(last4) / len(last4), 1) if last4 else None

        # Weekly mileage target: athlete input wins; else derive from trailing history.
        # This is intentionally conservative: we follow the athlete's reality, not a population ramp.
        target_weekly_miles = weekly_mileage_target
        if target_weekly_miles is None:
            if recent_weekly_avg and recent_weekly_avg > 0:
                target_weekly_miles = recent_weekly_avg
            else:
                target_weekly_miles = float(baseline.get("weekly_miles") or 30.0)

        # Active plan for ownership: if plan exists, use it as intent for days that are scheduled.
        plan = (
            db.query(TrainingPlan)
            .filter(TrainingPlan.athlete_id == athlete_id, TrainingPlan.status == "active")
            .first()
        )

        planned_by_date: Dict[date, PlannedWorkout] = {}
        if plan:
            planned = (
                db.query(PlannedWorkout)
                .filter(
                    PlannedWorkout.plan_id == plan.id,
                    PlannedWorkout.scheduled_date >= start,
                    PlannedWorkout.scheduled_date <= end,
                )
                .all()
            )
            planned_by_date = {w.scheduled_date: w for w in planned if w.scheduled_date}

        # Determine athlete-preferred training pattern days from baseline (athlete-derived).
        pattern_days = baseline.get("training_patterns") or []
        quality_day_name = None
        long_day_name = None
        for p in pattern_days:
            if p.startswith("intervals_"):
                quality_day_name = p.replace("intervals_", "")
            if p.startswith("long_"):
                long_day_name = p.replace("long_", "")

        weekday_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

        def _day_name(d: date) -> str:
            return weekday_names[d.weekday()]

        # Day-type allocation for unscheduled days.
        # We do NOT infer taper from fatigue. Fatigue only influences guardrails/variants.
        # Phase defaults:
        # - returning-from-break => BASE
        # - otherwise BUILD
        phase_default = GenPhase.BASE if baseline.get("is_returning_from_injury") else GenPhase.BUILD

        # Very simple weekly structure: 1 quality + 1 long unless athlete says pain, then easy/rest only.
        structure_quality_day = quality_day_name or "thursday"
        structure_long_day = long_day_name or "sunday"

        # Allocate daily miles proportionally (80/20-ish) using target_weekly_miles.
        # This gives exact distances, but derived from trailing history and athlete target.
        # Rest day Monday default; adjust if window doesn't include it.
        default_split = {
            "rest": 0.0,
            "easy": 0.14,
            "easy_strides": 0.12,
            "quality": 0.14,
            "long": 0.30,
        }

        def _miles_for_kind(kind: str) -> float:
            pct = default_split.get(kind, 0.12)
            miles = float(target_weekly_miles) * pct
            return max(0.0, round(miles, 1))

        # Build day prescriptions
        out_days: List[Dict[str, Any]] = []
        evidence: List[Dict[str, Any]] = []

        # Evidence: trailing volume and baseline
        if last4:
            evidence.append(
                {
                    "type": "derived",
                    "id": f"weekly_volume:{str(athlete_id)}:4w",
                    "date": _today_local.isoformat(),
                    "value": f"Last 4 weeks volume (mi): {last4} (avg {recent_weekly_avg} mi/week)",
                }
            )
        evidence.append(
            {
                "type": "derived",
                "id": f"baseline:{str(athlete_id)}",
                "date": _today_local.isoformat(),
                "value": (
                    f"Established baseline: {baseline.get('weekly_miles', 0):.0f} mpw, "
                    f"typical long {baseline.get('long_run_miles', 0):.0f} mi, "
                    f"peak long {baseline.get('peak_long_run_miles', 0):.0f} mi"
                ),
            }
        )

        # Iterate dates
        for i in range(days):
            d = start + timedelta(days=i)
            dn = _day_name(d)

            # If the athlete already completed a run on this date, surface ACTUAL first.
            actuals = (
                db.query(Activity)
                .filter(Activity.athlete_id == athlete_id, Activity.sport == "run")
                .filter(func.date(Activity.start_time) == d)
                .order_by(Activity.start_time.desc())
                .limit(3)
                .all()
            )
            actual = actuals[0] if actuals else None

            planned = planned_by_date.get(d)
            if planned:
                if actual:
                    # Return the completed workout as primary, but include planned for mismatch visibility.
                    distance_mi = _mi_from_m(actual.distance_m) if actual.distance_m is not None else None
                    distance_km = (float(actual.distance_m) / 1000.0) if actual.distance_m is not None else None
                    primary = {
                        "source": "actual",
                        "date": d.isoformat(),
                        "day_of_week": dn,
                        "workout_type": actual.workout_type or "run",
                        "title": (actual.name or "").strip() or "Run",
                        "description": "Completed activity logged today.",
                        "target_distance_mi": round(distance_mi, 1) if distance_mi is not None else None,
                        "target_distance_km": round(distance_km, 1) if distance_km is not None else None,
                        "pace_per_mile": _pace_str_mi(actual.duration_s, actual.distance_m),
                        "pace_per_km": _pace_str(actual.duration_s, actual.distance_m),
                        "avg_hr": int(actual.avg_hr) if actual.avg_hr is not None else None,
                        "activity_id": str(actual.id),
                        "planned": {
                            "title": planned.title,
                            "workout_type": planned.workout_type,
                            "target_distance_km": float(planned.target_distance_km) if planned.target_distance_km is not None else None,
                            "target_distance_mi": _mi_from_m((planned.target_distance_km or 0) * 1000.0) if planned.target_distance_km else None,
                        },
                    }

                    out_days.append(
                        {
                            "date": d.isoformat(),
                            "day_of_week": dn,
                            "primary": primary,
                            "variants": [],
                            "guardrails": _guardrails_from_pain(pain_flag_norm),
                        }
                    )
                    # Also cite it as evidence (facts only)
                    dist_val = (
                        f"{distance_mi:.1f} mi" if units == "imperial" and distance_mi is not None else f"{distance_km:.1f} km" if distance_km is not None else "distance n/a"
                    )
                    pace_val = _pace_str_mi(actual.duration_s, actual.distance_m) if units == "imperial" else _pace_str(actual.duration_s, actual.distance_m)
                    hr_val = f" (avg HR {int(actual.avg_hr)} bpm)" if actual.avg_hr is not None else ""
                    evidence.insert(
                        0,
                        {
                            "type": "activity",
                            "id": str(actual.id),
                            "date": d.isoformat(),
                            "value": f"{(actual.name or 'Run').strip() or 'Run'} {dist_val} @ {pace_val}{hr_val}",
                        },
                    )
                    continue

                # Convert planned workout into a prescriptive object, adding derived paces and variants.
                planned_mi = _mi_from_m((planned.target_distance_km or 0) * 1000.0) if planned.target_distance_km else None
                primary = {
                    "source": "plan",
                    "date": d.isoformat(),
                    "day_of_week": dn,
                    "workout_type": planned.workout_type,
                    "title": planned.title,
                    "description": planned.description,
                    "target_distance_mi": round(planned_mi, 1) if planned_mi is not None else None,
                    "target_distance_km": float(planned.target_distance_km) if planned.target_distance_km is not None else None,
                    "target_duration_minutes": planned.target_duration_minutes,
                    "segments": planned.segments,
                    "phase": planned.phase,
                }

                # Variants: time-crunched and low-impact variants (exact)
                variants = []
                if planned_mi is not None:
                    variants.append(
                        {
                            "name": "Time-crunched",
                            "description": f"Keep the intent but shorten: {max(3.0, planned_mi * 0.7):.1f} mi total (reduce warmup/cooldown).",
                        }
                    )
                variants.append(
                    {
                        "name": "Low-impact",
                        "description": "Swap to easy run only at easy pace; skip quality stimulus today.",
                    }
                )

                out_days.append(
                    {
                        "date": d.isoformat(),
                        "day_of_week": dn,
                        "primary": primary,
                        "variants": variants,
                        "guardrails": _guardrails_from_pain(pain_flag_norm),
                    }
                )
                continue

            # No planned workout: generate deterministically.
            if pain_flag_norm == "pain":
                out_days.append(
                    {
                        "date": d.isoformat(),
                        "day_of_week": dn,
                        "primary": {
                            "source": "coach",
                            "workout_type": "rest",
                            "title": "Rest / Active Recovery",
                            "description": "Pain flagged: do not run today. If pain persists, consult a clinician.",
                            "target_distance_mi": 0,
                            "target_duration_minutes": 0,
                        },
                        "variants": [],
                        "guardrails": _guardrails_from_pain(pain_flag_norm),
                    }
                )
                continue

            # Choose day kind based on athlete pattern days.
            if dn == "monday":
                kind = "rest"
            elif dn == structure_quality_day:
                kind = "quality"
            elif dn == structure_long_day:
                kind = "long"
            elif dn in ("tuesday", "friday"):
                kind = "easy_strides"
            else:
                kind = "easy"

            # Convert miles->TSS proxy using same constants as model-driven generator.
            # We use TSS as an internal scaling so day_plan produces consistent descriptions.
            from services.model_driven_plan_generator import TSS_TO_MILES_EASY, TSS_TO_MILES_QUALITY
            miles = _miles_for_kind(kind)
            if kind in ("quality", "sharpening"):
                target_tss = miles / max(0.01, TSS_TO_MILES_QUALITY)
            elif kind == "rest":
                target_tss = 0.0
            else:
                target_tss = miles / max(0.01, TSS_TO_MILES_EASY)

            # Apply athlete-stated time constraint as a hard cap on distance.
            if time_available_min and time_available_min > 0 and miles > 0:
                # Rough pace cap using easy pace; we do NOT assume the athlete's exact pace here.
                # The workout description still has exact pace targets; this only bounds volume.
                # Assume easy pace ~9:00/mi fallback if parsing fails.
                try:
                    e = paces.get("e_pace", "9:00/mi")
                    mins, secs = e.split("/")[0].split(":")
                    pace_min = int(mins) + (int(secs) / 60.0)
                except Exception:
                    pace_min = 9.0
                max_miles = round(float(time_available_min) / max(1.0, pace_min), 1)
                miles = min(miles, max_miles)

            day_plan = gen._create_day_plan(
                date=d,
                day_of_week=dn.title(),
                workout_type=kind,
                target_tss=float(target_tss),
                paces=paces,
                race_distance="marathon",
                phase=phase_default,
                baseline=baseline,
                week_number=1,
                total_weeks=16,
            )

            def _pace_mi_to_km(p: Optional[str]) -> Optional[str]:
                """
                Convert pace like '7:30/mi' -> '4:40/km' (rounded).
                """
                if not p or "/mi" not in p:
                    return p
                try:
                    raw = p.split("/")[0]
                    mm, ss = raw.split(":")
                    pace_min_mi = int(mm) + (int(ss) / 60.0)
                    pace_min_km = pace_min_mi / 1.609344
                    m = int(pace_min_km)
                    s = int(round((pace_min_km - m) * 60))
                    if s == 60:
                        m += 1
                        s = 0
                    return f"{m}:{s:02d}/km"
                except Exception:
                    return None

            def _convert_text_paces_to_metric(txt: str) -> str:
                if not txt:
                    return txt
                # Replace occurrences like '7:15/mi' with converted values.
                def repl(match):
                    return _pace_mi_to_km(match.group(0)) or match.group(0)
                return re.sub(r"\b\d{1,2}:\d{2}/mi\b", repl, txt)

            miles_val = float(day_plan.target_miles or 0)
            km_val = miles_val * 1.609344
            desc = day_plan.description
            pace = day_plan.target_pace
            if units != "imperial":
                desc = _convert_text_paces_to_metric(desc)
                pace = _pace_mi_to_km(pace) if pace else pace

            # Convert to a stable payload (units honored; numbers included in both).
            primary = {
                "source": "coach",
                "date": d.isoformat(),
                "day_of_week": dn,
                "workout_type": day_plan.workout_type,
                "title": day_plan.name,
                "description": desc,
                "target_distance_mi": round(miles_val, 1),
                "target_distance_km": round(km_val, 1),
                "target_pace": pace,
                "notes": day_plan.notes,
                "rationale": day_plan.rationale,
            }

            variants = []
            if primary["target_distance_mi"] and primary["target_distance_mi"] > 0:
                if units == "imperial":
                    dist_txt = f"{max(2.5, primary['target_distance_mi'] * 0.75):.1f} mi"
                else:
                    dist_txt = f"{max(4.0, primary['target_distance_km'] * 0.75):.1f} km"
                variants.append(
                    {
                        "name": "Time-crunched",
                        "description": f"{dist_txt} total at easy pace.",
                    }
                )
            if pain_flag_norm == "niggle":
                variants.append(
                    {
                        "name": "Protect the niggle",
                        "description": "Easy only; skip any quality stimulus and keep cadence relaxed.",
                    }
                )

            out_days.append(
                {
                    "date": d.isoformat(),
                    "day_of_week": dn,
                    "primary": primary,
                    "variants": variants,
                    "guardrails": _guardrails_from_pain(pain_flag_norm),
                }
            )

        # Return in preferred units (do not hide the other unit, but keep it out of the main copy).
        # --- Narrative ---
        rx_parts: List[str] = [f"Training prescription for {start.isoformat()} to {end.isoformat()} ({len(out_days)} day(s)):"]
        for od in out_days:
            d_date = od.get("date", "?")
            title = od.get("title") or od.get("workout_type") or "Rest"
            dist = od.get("distance_mi") if units == "imperial" else od.get("distance_km")
            u = "mi" if units == "imperial" else "km"
            if dist:
                rx_parts.append(f"  {d_date}: {title} — {dist:.1f} {u}.")
            else:
                rx_parts.append(f"  {d_date}: {title}.")
        rx_parts.append(f"Based on target {target_weekly_miles:.0f} mi/week, pain: {pain_flag_norm}.")
        rx_narrative = " ".join(rx_parts)

        return {
            "ok": True,
            "tool": "get_training_prescription_window",
            "generated_at": _iso(now),
            "narrative": rx_narrative,
            "data": {
                "preferred_units": units,
                "window": {
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                    "days": out_days,
                },
                "inputs_used": {
                    "time_available_min": time_available_min,
                    "weekly_mileage_target": target_weekly_miles,
                    "pain_flag": pain_flag_norm,
                    "facilities": facilities or [],
                },
            },
            "evidence": evidence[:6],
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "get_training_prescription_window", "error": str(e)}



