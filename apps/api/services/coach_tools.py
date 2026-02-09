"""
Coach Tools (ADR-044 Phase 2 — Bounded Tools)

These tools provide *structured*, evidence-backed athlete data to the AI Coach.
The coach should only reference metrics that come from these tools (or explicitly
state that the metric is unavailable).

Each tool returns:
  {
    "ok": bool,
    "tool": "<tool_name>",
    "generated_at": "<iso8601>",
    "data": {...},
    "evidence": [{...}]
  }
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, date

logger = logging.getLogger(__name__)
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func

from models import Activity, TrainingPlan, PlannedWorkout, Athlete
from services.efficiency_analytics import (
    get_efficiency_trends,
    is_quality_activity,
    calculate_efficiency_factor,
)
from services.training_load import TrainingLoadCalculator
from services.correlation_engine import analyze_correlations
from services.race_predictor import RacePredictor
from services.recovery_metrics import (
    calculate_recovery_half_life,
    calculate_durability_index,
    detect_false_fitness,
    detect_masked_fatigue,
)
from services.insight_aggregator import get_active_insights as fetch_insights, generate_insights_for_athlete
from services.correlation_engine import (
    aggregate_pre_pb_state,
    aggregate_efficiency_by_effort_zone,
    aggregate_efficiency_trend,
)
from services.rpi_calculator import calculate_race_time_from_rpi


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()

_M_PER_MI = 1609.344


def _mi_from_m(meters: Optional[int | float]) -> Optional[float]:
    if meters is None:
        return None
    try:
        return float(meters) / _M_PER_MI
    except Exception:
        return None


def _pace_str_mi(seconds: Optional[int], meters: Optional[int]) -> Optional[str]:
    if not seconds or not meters or meters <= 0:
        return None
    pace_s_per_mi = seconds / (meters / _M_PER_MI)
    m = int(pace_s_per_mi // 60)
    s = int(round(pace_s_per_mi % 60))
    return f"{m}:{s:02d}/mi"


def _preferred_units(db: Session, athlete_id: UUID) -> str:
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    units = (athlete.preferred_units if athlete else None) or "metric"
    return units if units in ("metric", "imperial") else "metric"


def _pace_str(seconds: Optional[int], meters: Optional[int]) -> Optional[str]:
    if not seconds or not meters or meters <= 0:
        return None
    pace_s_per_km = seconds / (meters / 1000.0)
    m = int(pace_s_per_km // 60)
    s = int(round(pace_s_per_km % 60))
    return f"{m}:{s:02d}/km"


def get_recent_runs(db: Session, athlete_id: UUID, days: int = 7) -> Dict[str, Any]:
    """
    Last N days of run activities.
    """
    now = datetime.utcnow()
    # Allow ~2 years so injury-return + baseline can be compared.
    days = max(1, min(int(days), 730))
    cutoff = now - timedelta(days=days)
    units = _preferred_units(db, athlete_id)

    runs = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.sport == "run",
            Activity.start_time >= cutoff,
        )
        .order_by(Activity.start_time.desc())
        .limit(50)
        .all()
    )

    run_rows: List[Dict[str, Any]] = []
    evidence: List[Dict[str, Any]] = []

    for a in runs:
        distance_km = (float(a.distance_m) / 1000.0) if a.distance_m is not None else None
        distance_mi = _mi_from_m(a.distance_m) if a.distance_m is not None else None
        pace = _pace_str(a.duration_s, a.distance_m)
        pace_mi = _pace_str_mi(a.duration_s, a.distance_m)
        date_str = a.start_time.date().isoformat()

        # Phase 3: Add elevation, weather, max_hr for richer context
        elevation_gain_m = float(a.total_elevation_gain) if a.total_elevation_gain is not None else None
        elevation_gain_ft = round(elevation_gain_m * 3.28084, 0) if elevation_gain_m is not None else None

        run_rows.append(
            {
                "activity_id": str(a.id),
                "start_time": _iso(a.start_time),
                "name": a.name,
                "distance_m": int(a.distance_m) if a.distance_m is not None else None,
                "distance_mi": round(distance_mi, 2) if distance_mi is not None else None,
                "distance_km": round(distance_km, 2) if distance_km is not None else None,
                "duration_s": int(a.duration_s) if a.duration_s is not None else None,
                "avg_hr": int(a.avg_hr) if a.avg_hr is not None else None,
                "max_hr": int(a.max_hr) if a.max_hr is not None else None,  # Phase 3
                "pace_per_km": _pace_str(a.duration_s, a.distance_m),
                "pace_per_mile": pace_mi,
                "workout_type": a.workout_type,
                "intensity_score": float(a.intensity_score) if a.intensity_score is not None else None,
                # Phase 3: Environmental context
                "elevation_gain_m": round(elevation_gain_m, 1) if elevation_gain_m is not None else None,
                "elevation_gain_ft": int(elevation_gain_ft) if elevation_gain_ft is not None else None,
                "temperature_f": round(float(a.temperature_f), 1) if a.temperature_f is not None else None,
                "humidity_pct": round(float(a.humidity_pct), 0) if a.humidity_pct is not None else None,
                "weather_condition": a.weather_condition,
            }
        )

        parts: List[str] = []
        run_name = (a.name or "").strip() or "Run"
        parts.append(run_name)
        if units == "imperial":
            if distance_mi is not None:
                parts.append(f"{distance_mi:.1f} mi")
            if pace_mi:
                parts.append(f"@ {pace_mi}")
        else:
            if distance_km is not None:
                parts.append(f"{distance_km:.1f} km")
            if pace:
                parts.append(f"@ {pace}")
        if a.avg_hr is not None:
            parts.append(f"(avg HR {int(a.avg_hr)} bpm)")
        if a.max_hr is not None:
            parts.append(f"(max HR {int(a.max_hr)} bpm)")
        if a.workout_type:
            parts.append(f"[{a.workout_type}]")
        # Phase 3: Add elevation and weather to evidence
        if elevation_gain_ft is not None and elevation_gain_ft > 50:
            parts.append(f"+{int(elevation_gain_ft)}ft")
        if a.temperature_f is not None:
            parts.append(f"{int(a.temperature_f)}°F")
        if a.weather_condition:
            parts.append(f"({a.weather_condition})")
        value_str = " ".join(parts) if parts else "run"

        evidence.append(
            {
                "type": "activity",
                "id": str(a.id),
                "ref": str(a.id)[:8],
                "date": date_str,
                "value": value_str,
                # Back-compat keys (internal use in earlier phases)
                "activity_id": str(a.id),
                "start_time": _iso(a.start_time),
            }
        )

    total_distance_m = sum((a.distance_m or 0) for a in runs)
    total_duration_s = sum((a.duration_s or 0) for a in runs)

    # --- Narrative ---
    total_mi = round(total_distance_m / _M_PER_MI, 1)
    total_km = round(total_distance_m / 1000.0, 1)
    if units == "imperial":
        dist_str = f"{total_mi} miles"
    else:
        dist_str = f"{total_km} km"
    dur_hrs = round(total_duration_s / 3600.0, 1)

    rr_parts: List[str] = [
        f"{len(runs)} runs in the last {days} days totaling {dist_str} ({dur_hrs} hours)."
    ]
    if run_rows:
        latest = run_rows[0]
        l_name = latest.get("name") or "Run"
        l_date = latest.get("start_time", "")[:10]
        l_dist = latest.get("distance_mi") if units == "imperial" else latest.get("distance_km")
        l_unit = "mi" if units == "imperial" else "km"
        l_pace = latest.get("pace_per_mile") if units == "imperial" else latest.get("pace_per_km")
        rr_parts.append(
            f"Most recent: {l_name} on {l_date}, "
            f"{l_dist:.1f} {l_unit} @ {l_pace or 'N/A'}."
        )
    narrative = " ".join(rr_parts)

    return {
        "ok": True,
        "tool": "get_recent_runs",
        "generated_at": _iso(now),
        "narrative": narrative,
        "data": {
            "window_days": days,
            "preferred_units": units,
            "run_count": len(runs),
            "total_distance_km": round(total_distance_m / 1000.0, 2),
            "total_distance_mi": round(total_distance_m / _M_PER_MI, 2),
            "total_duration_min": round(total_duration_s / 60.0, 1),
            "runs": run_rows,
        },
        "evidence": evidence,
    }


def get_calendar_day_context(db: Session, athlete_id: UUID, day: str) -> Dict[str, Any]:
    """
    Calendar day context (plan + actual).

    Use this when the athlete asks about a specific day from the calendar.
    Returns planned workout + actual activities for that date with IDs for citations.
    """
    now = datetime.utcnow()
    try:
        day_date = date.fromisoformat(day)
    except Exception:
        return {
            "ok": False,
            "tool": "get_calendar_day_context",
            "generated_at": _iso(now),
            "error": "Invalid date format. Use YYYY-MM-DD.",
            "data": {},
            "evidence": [],
        }

    plan = (
        db.query(TrainingPlan)
        .filter(TrainingPlan.athlete_id == athlete_id, TrainingPlan.status == "active")
        .first()
    )
    units = _preferred_units(db, athlete_id)

    planned = None
    if plan:
        planned = (
            db.query(PlannedWorkout)
            .filter(PlannedWorkout.plan_id == plan.id, PlannedWorkout.scheduled_date == day_date)
            .first()
        )

    acts = (
        db.query(Activity)
        .filter(Activity.athlete_id == athlete_id, Activity.sport == "run")
        .filter(func.date(Activity.start_time) == day_date)
        .order_by(Activity.start_time.asc())
        .all()
    )

    planned_data: Optional[Dict[str, Any]] = None
    evidence: List[Dict[str, Any]] = []
    if planned:
        planned_mi = _mi_from_m(planned.target_distance_km * 1000.0) if planned.target_distance_km is not None else None
        planned_data = {
            "planned_workout_id": str(planned.id),
            "plan_id": str(planned.plan_id),
            "date": planned.scheduled_date.isoformat() if planned.scheduled_date else None,
            "week_number": planned.week_number,
            "phase": planned.phase,
            "workout_type": planned.workout_type,
            "workout_subtype": planned.workout_subtype,
            "title": planned.title,
            "coach_notes": planned.coach_notes,
            "description": planned.description,
            "target_distance_km": float(planned.target_distance_km) if planned.target_distance_km is not None else None,
            "target_distance_mi": round(planned_mi, 2) if planned_mi is not None else None,
            "target_duration_minutes": planned.target_duration_minutes,
            "completed": bool(planned.completed),
            "skipped": bool(planned.skipped),
        }
        evidence.append(
            {
                "type": "planned_workout",
                "id": str(planned.id),
                "date": day_date.isoformat(),
                "value": f"{planned.title} [{planned.workout_type}]",
            }
        )

    activity_rows: List[Dict[str, Any]] = []
    for a in acts:
        distance_km = (float(a.distance_m) / 1000.0) if a.distance_m is not None else None
        distance_mi = _mi_from_m(a.distance_m) if a.distance_m is not None else None
        activity_rows.append(
            {
                "activity_id": str(a.id),
                "start_time": _iso(a.start_time),
                "name": a.name,
                "distance_m": int(a.distance_m) if a.distance_m is not None else None,
                "distance_mi": round(distance_mi, 2) if distance_mi is not None else None,
                "distance_km": round(distance_km, 2) if distance_km is not None else None,
                "duration_s": int(a.duration_s) if a.duration_s is not None else None,
                "avg_hr": int(a.avg_hr) if a.avg_hr is not None else None,
                "pace_per_km": _pace_str(a.duration_s, a.distance_m),
                "pace_per_mile": _pace_str_mi(a.duration_s, a.distance_m),
                "workout_type": a.workout_type,
                "intensity_score": float(a.intensity_score) if a.intensity_score is not None else None,
            }
        )

        parts: List[str] = []
        run_name = (a.name or "").strip() or "Run"
        parts.append(run_name)
        if units == "imperial":
            if distance_mi is not None:
                parts.append(f"{distance_mi:.1f} mi")
            pace_mi = _pace_str_mi(a.duration_s, a.distance_m)
            if pace_mi:
                parts.append(f"@ {pace_mi}")
        else:
            if distance_km is not None:
                parts.append(f"{distance_km:.1f} km")
            pace = _pace_str(a.duration_s, a.distance_m)
            if pace:
                parts.append(f"@ {pace}")
        if a.avg_hr is not None:
            parts.append(f"(avg HR {int(a.avg_hr)} bpm)")
        if a.workout_type:
            parts.append(f"[{a.workout_type}]")
        evidence.append(
            {
                "type": "activity",
                "id": str(a.id),
                "ref": str(a.id)[:8],
                "date": day_date.isoformat(),
                "value": " ".join(parts) if parts else "run",
            }
        )

    # --- Narrative ---
    cd_parts: List[str] = [f"Calendar day {day_date.isoformat()}:"]
    if planned_data:
        status = "completed" if planned_data.get("completed") else ("skipped" if planned_data.get("skipped") else "not yet completed")
        cd_parts.append(
            f"Planned: {planned_data.get('title', 'workout')} ({planned_data.get('workout_type', 'N/A')}) — {status}."
        )
    else:
        cd_parts.append("No workout was planned for this day.")
    if activity_rows:
        for ar in activity_rows:
            d_val = ar.get("distance_mi") if units == "imperial" else ar.get("distance_km")
            d_unit = "mi" if units == "imperial" else "km"
            p_val = ar.get("pace_per_mile") if units == "imperial" else ar.get("pace_per_km")
            cd_parts.append(
                f"Actual: {ar.get('name', 'Run')} — {d_val:.1f} {d_unit} @ {p_val or 'N/A'}"
                + (f" (avg HR {ar['avg_hr']} bpm)" if ar.get("avg_hr") else "")
                + "."
            )
    else:
        cd_parts.append("No runs recorded on this day.")
    cd_narrative = " ".join(cd_parts)

    return {
        "ok": True,
        "tool": "get_calendar_day_context",
        "generated_at": _iso(now),
        "narrative": cd_narrative,
        "data": {
            "date": day_date.isoformat(),
            "preferred_units": units,
            "active_plan_id": str(plan.id) if plan else None,
            "planned_workout": planned_data,
            "activities": activity_rows,
        },
        "evidence": evidence,
    }


def get_efficiency_trend(db: Session, athlete_id: UUID, days: int = 30) -> Dict[str, Any]:
    """
    Efficiency over time.
    """
    now = datetime.utcnow()
    days = max(7, min(int(days), 365))

    # NOTE: efficiency_analytics expects the DB-native athlete_id type (UUID).
    # Passing a string can lead to no rows returned depending on dialect/casting.
    result = get_efficiency_trends(
        athlete_id=athlete_id,
        db=db,
        days=days,
        include_stability=False,
        include_load_response=False,
        include_annotations=False,
    )

    # Keep payload bounded
    time_series = result.get("time_series") or []
    trimmed_series = time_series[-50:] if isinstance(time_series, list) else time_series

    # Fallback: if the full efficiency pipeline can't compute EF (e.g., missing splits),
    # derive a basic EF directly from pace_per_mile + avg_hr so the coach can still
    # answer "Am I getting fitter?" with evidence-backed values.
    if not trimmed_series:
        cutoff = now - timedelta(days=days)
        activities = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete_id,
                Activity.sport == "run",
                Activity.start_time >= cutoff,
            )
            .order_by(Activity.start_time.asc())
            .limit(50)
            .all()
        )

        derived = []
        for a in activities:
            if not is_quality_activity(a):
                continue
            pace = a.pace_per_mile
            ef = calculate_efficiency_factor(pace_per_mile=pace, avg_hr=a.avg_hr, max_hr=None)
            if ef is None:
                continue
            derived.append(
                {
                    "date": _iso(a.start_time),
                    "efficiency_factor": ef,
                    "pace_per_mile": round(float(pace), 2) if pace is not None else None,
                    "avg_hr": int(a.avg_hr) if a.avg_hr is not None else None,
                    "activity_id": str(a.id),
                }
            )

        trimmed_series = derived[-50:]
        if derived:
            efficiencies = [p["efficiency_factor"] for p in derived if p.get("efficiency_factor") is not None]
            trend_direction = "insufficient_data"
            trend_magnitude = None
            if len(efficiencies) >= 6:
                early_avg = sum(efficiencies[:3]) / 3
                late_avg = sum(efficiencies[-3:]) / 3
                # EF = speed/HR. Higher EF is better.
                if late_avg > early_avg:
                    trend_direction = "improving"
                elif late_avg < early_avg:
                    trend_direction = "declining"
                else:
                    trend_direction = "stable"
                trend_magnitude = round(abs(late_avg - early_avg), 2)

            result = {
                "summary": {
                    "total_activities": len(derived),
                    "date_range": {"start": derived[0]["date"], "end": derived[-1]["date"]} if derived else None,
                    "current_efficiency": efficiencies[-1] if efficiencies else None,
                    "average_efficiency": round(sum(efficiencies) / len(efficiencies), 2) if efficiencies else None,
                    "best_efficiency": round(max(efficiencies), 4) if efficiencies else None,
                    "worst_efficiency": round(min(efficiencies), 4) if efficiencies else None,
                    "trend_direction": trend_direction,
                    "trend_magnitude": trend_magnitude,
                    "note": "Derived EF fallback (pace_per_mile + avg_hr). Higher EF is better.",
                },
                "trend_analysis": {
                    "method": "fallback_basic",
                    "slope_per_week": None,
                    "p_value": None,
                    "r_squared": None,
                },
                "time_series": trimmed_series,
            }

    units = _preferred_units(db, athlete_id)
    evidence: List[Dict[str, Any]] = []
    if isinstance(trimmed_series, list):
        for p in trimmed_series:
            if isinstance(p, dict) and p.get("activity_id") and p.get("date"):
                # date field in efficiency_analytics is ISO datetime string
                date_str = str(p.get("date"))[:10]
                ef = p.get("efficiency_factor")
                pace_mi = p.get("pace_per_mile")
                pace_km = p.get("pace_per_km")
                avg_hr = p.get("avg_hr")
                ef_part = f"EF {ef}" if ef is not None else "EF n/a"
                extras: List[str] = []
                if units == "imperial":
                    if pace_mi is not None:
                        extras.append(f"pace {pace_mi} min/mi")
                else:
                    if pace_km is not None:
                        extras.append(f"pace {pace_km} min/km")
                if avg_hr is not None:
                    extras.append(f"avg HR {avg_hr} bpm")
                value_str = ef_part + (f" ({', '.join(extras)})" if extras else "")

                evidence.append(
                    {
                        "type": "activity",
                        "id": str(p.get("activity_id")),
                        "date": date_str,
                        "value": value_str,
                        # Back-compat keys
                        "activity_id": str(p.get("activity_id")),
                        "start_time": str(p.get("date")),
                    }
                )

    # --- Narrative ---
    summ = result.get("summary") or {}
    ef_current = summ.get("current_efficiency")
    ef_best = summ.get("best_efficiency")
    ef_avg = summ.get("average_efficiency")
    ef_trend = summ.get("trend_direction", "unknown")
    ef_parts: List[str] = [f"Efficiency trend over {days} days: {ef_trend}."]
    if ef_current is not None:
        ef_parts.append(f"Current EF: {ef_current:.2f}.")
    if ef_best is not None:
        ef_parts.append(f"Best EF: {ef_best:.2f}.")
    if ef_avg is not None:
        ef_parts.append(f"Average EF: {ef_avg:.2f}.")
    ef_parts.append("Higher EF = more speed at the same heart rate = better.")
    ef_narrative = " ".join(ef_parts)

    return {
        "ok": True,
        "tool": "get_efficiency_trend",
        "generated_at": _iso(now),
        "narrative": ef_narrative,
        "data": {
            "window_days": days,
            "summary": result.get("summary"),
            "trend_analysis": result.get("trend_analysis"),
            "time_series": trimmed_series,
        },
        "evidence": evidence,
    }


def get_plan_week(db: Session, athlete_id: UUID) -> Dict[str, Any]:
    """
    Current week's plan.
    """
    today = date.today()
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
        workout_rows.append(
            {
                "planned_workout_id": str(w.id),
                "scheduled_date": w.scheduled_date.isoformat(),
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
                "date": w.scheduled_date.isoformat(),
                "value": f"{w.title} ({w.workout_type})",
                # Back-compat keys
                "planned_workout_id": str(w.id),
                "scheduled_date": w.scheduled_date.isoformat(),
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


def get_training_load(db: Session, athlete_id: UUID) -> Dict[str, Any]:
    """
    CTL/ATL/TSB summary using TrainingLoadCalculator.
    """
    now = datetime.utcnow()
    calc = TrainingLoadCalculator(db)
    summary = calc.calculate_training_load(athlete_id)
    zone_info = calc.get_tsb_zone(summary.current_tsb, athlete_id=athlete_id)

    # --- Narrative ---
    ctl_v = round(summary.current_ctl, 1) if summary.current_ctl is not None else "?"
    atl_v = round(summary.current_atl, 1) if summary.current_atl is not None else "?"
    tsb_v = round(summary.current_tsb, 1) if summary.current_tsb is not None else "?"
    ratio_note = ""
    if summary.current_ctl and summary.current_atl:
        ratio = summary.current_atl / summary.current_ctl if summary.current_ctl > 0 else 0
        if ratio > 1.3:
            ratio_note = " Acute:Chronic ratio is high — coach should recommend recovery."
        elif ratio > 1.1:
            ratio_note = " Acute:Chronic ratio is moderately elevated."

    narrative = (
        f"(INTERNAL — translate for athlete, never quote raw numbers.) "
        f"CTL: {ctl_v}, ATL: {atl_v}, TSB: {tsb_v}. "
        f"Zone: {zone_info.label} — {zone_info.description} "
        f"Phase: {summary.training_phase or 'N/A'}.{ratio_note}"
    )

    return {
        "ok": True,
        "tool": "get_training_load",
        "generated_at": _iso(now),
        "narrative": narrative,
        "data": {
            "atl": summary.current_atl,
            "ctl": summary.current_ctl,
            "tsb": summary.current_tsb,
            "atl_trend": summary.atl_trend,
            "ctl_trend": summary.ctl_trend,
            "tsb_trend": summary.tsb_trend,
            "training_phase": summary.training_phase,
            "recommendation": summary.recommendation,
            "tsb_zone": {
                "zone": zone_info.zone.value,
                "label": zone_info.label,
                "description": zone_info.description,
                "color": zone_info.color,
                "is_race_window": zone_info.is_race_window,
            },
        },
        "evidence": [
            {
                "type": "derived",
                "id": f"training_load:{str(athlete_id)}",
                "date": date.today().isoformat(),
                "value": f"ATL {summary.current_atl}, CTL {summary.current_ctl}, TSB {summary.current_tsb} ({zone_info.zone.value})",
                # Back-compat keys
                "metric_set": "training_load",
                "as_of_date": date.today().isoformat(),
                "source": "TrainingLoadCalculator.calculate_training_load",
            }
        ],
    }


def get_training_paces(db: Session, athlete_id: UUID) -> Dict[str, Any]:
    """
    Get RPI-based training paces for the athlete.

    Returns target paces for easy, threshold, interval, repetition, and marathon training.
    This is THE authoritative source for training paces - do not derive paces from other data.
    """
    now = datetime.utcnow()
    try:
        from services.rpi_calculator import calculate_training_paces as calc_paces

        athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            return {"ok": False, "tool": "get_training_paces", "error": "Athlete not found"}

        rpi = athlete.rpi
        if not rpi:
            return {
                "ok": False,
                "tool": "get_training_paces",
                "error": "No RPI on file. Athlete needs to complete a time trial or race to calculate training paces.",
            }

        units = athlete.preferred_units or "metric"
        paces = calc_paces(rpi)

        # Format for display
        def format_display(pace_key: str) -> str:
            """Format a pace for human-readable display."""
            if pace_key not in paces:
                return "N/A"
            val = paces[pace_key]
            if isinstance(val, dict):
                # Keys are "mi" and "km", not "display_mi"
                pace = val.get("mi" if units == "imperial" else "km")
                if pace:
                    return f"{pace}/mi" if units == "imperial" else f"{pace}/km"
                return "N/A"
            elif isinstance(val, str):
                return val
            return "N/A"

        # --- Narrative ---
        narrative = (
            f"Training paces based on RPI {rpi:.1f}: "
            f"Easy {format_display('easy')}, Marathon {format_display('marathon')}, "
            f"Threshold {format_display('threshold')}, Interval {format_display('interval')}, "
            f"Repetition {format_display('repetition')}. "
            f"These are THE authoritative paces — do not derive paces from other data."
        )

        return {
            "ok": True,
            "tool": "get_training_paces",
            "generated_at": _iso(now),
            "narrative": narrative,
            "data": {
                "rpi": rpi,  # Running Performance Index
                "rpi": rpi,  # Keep for backward compatibility
                "preferred_units": units,
                "paces": {
                    "easy": format_display("easy"),
                    "marathon": format_display("marathon"),
                    "threshold": format_display("threshold"),
                    "interval": format_display("interval"),
                    "repetition": format_display("repetition"),
                },
                "raw_seconds_per_mile": {
                    "easy_low": paces.get("easy_pace_low"),
                    "marathon": paces.get("marathon_pace"),
                    "threshold": paces.get("threshold_pace"),
                    "interval": paces.get("interval_pace"),
                    "repetition": paces.get("repetition_pace"),
                },
            },
            "evidence": [
                {
                    "type": "calculation",
                    "id": f"rpi_paces:{athlete_id}",
                    "date": date.today().isoformat(),
                    "value": f"RPI {rpi:.1f} → Threshold {format_display('threshold')}, Easy {format_display('easy')}",
                }
            ],
        }
    except Exception as e:
        logger.error(f"get_training_paces failed for {athlete_id}: {e}")
        return {"ok": False, "tool": "get_training_paces", "error": str(e)}


def get_correlations(db: Session, athlete_id: UUID, days: int = 30) -> Dict[str, Any]:
    """
    Correlation insights (what seems to be working / not working).
    """
    now = datetime.utcnow()
    days = max(14, min(int(days), 365))

    result = analyze_correlations(athlete_id=str(athlete_id), days=days, db=db)

    top = None
    correlations = result.get("correlations") if isinstance(result, dict) else None
    if isinstance(correlations, list) and correlations:
        top = correlations[0]

    top_value = "No significant correlations found" if not top else (
        f"{top.get('input_name')} r={top.get('correlation_coefficient')} p={top.get('p_value')} "
        f"(lag {top.get('time_lag_days')}d, n={top.get('sample_size')})"
    )

    # --- Narrative ---
    corr_list = result.get("correlations") if isinstance(result, dict) else None
    if isinstance(corr_list, list) and corr_list:
        narr_items: List[str] = []
        for c in corr_list[:3]:
            inp = c.get("input_name", "?")
            out = c.get("output_name", "?")
            r = c.get("correlation_coefficient")
            lag = c.get("time_lag_days", 0)
            interp = c.get("interpretation", "")
            r_str = f"r={r:.2f}" if r is not None else "r=?"
            narr_items.append(f"{inp} → {out} ({r_str}, lag {lag}d): {interp}")
        narrative = f"Top correlations over {days} days: " + " | ".join(narr_items)
    else:
        narrative = f"No significant correlations found over the last {days} days."

    return {
        "ok": True,
        "tool": "get_correlations",
        "generated_at": _iso(now),
        "narrative": narrative,
        "data": result,
        "evidence": [
            {
                "type": "derived",
                "id": f"correlations:{str(athlete_id)}:{days}d",
                "date": (result.get("analysis_period") or {}).get("end", _iso(now))[:10] if isinstance(result, dict) else _iso(now)[:10],
                "value": top_value,
                # Back-compat keys
                "metric_set": "correlations",
                "analysis_period": result.get("analysis_period"),
                "source": "correlation_engine.analyze_correlations",
            }
        ],
    }


def get_race_predictions(db: Session, athlete_id: UUID) -> Dict[str, Any]:
    """
    Race time predictions for standard distances.
    """
    now = datetime.utcnow()
    try:
        predictor = RacePredictor(db)
        athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()

        # Prefer the athlete's active plan goal race date (if present and in the future);
        # otherwise, project a near-term race to avoid "race today" taper artifacts.
        race_date = date.today() + timedelta(days=28)
        try:
            plan = (
                db.query(TrainingPlan)
                .filter(TrainingPlan.athlete_id == athlete_id, TrainingPlan.status == "active")
                .first()
            )
            if plan and plan.goal_race_date and plan.goal_race_date >= date.today():
                race_date = plan.goal_race_date
        except Exception:
            # If plan lookup fails for any reason, proceed with default race_date.
            pass

        distances: List[tuple[str, float]] = [
            ("5K", 5000.0),
            ("10K", 10000.0),
            ("Half Marathon", 21097.0),
            ("Marathon", 42195.0),
        ]

        def _fmt_time(seconds: int) -> str:
            h = seconds // 3600
            m = (seconds % 3600) // 60
            s = seconds % 60
            return f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m}:{s:02d}"

        predictions: Dict[str, Any] = {}
        evidence: List[Dict[str, Any]] = []

        def _best_rpi_from_personal_bests() -> Optional[Dict[str, Any]]:
            """
            Derive a RPI estimate from the athlete's PersonalBest table.

            Returns:
                {"rpi": float, "pb": PersonalBest} or None
            """
            try:
                from models import PersonalBest
                from services.rpi_calculator import calculate_rpi_from_race_time

                pbs = (
                    db.query(PersonalBest)
                    .filter(PersonalBest.athlete_id == athlete_id)
                    .order_by(PersonalBest.achieved_at.desc())
                    .limit(20)
                    .all()
                )
                if not pbs:
                    return None

                # Prefer race PBs and standard race distances (better anchors).
                candidates: List[tuple[float, Any]] = []
                for pb in pbs:
                    v = calculate_rpi_from_race_time(pb.distance_meters, pb.time_seconds)
                    if not v:
                        continue
                    weight = 0.0
                    if getattr(pb, "is_race", False):
                        weight += 0.3
                    if pb.distance_category in {"5k", "10k", "half_marathon", "marathon"}:
                        weight += 0.2
                    candidates.append((float(v) + weight, pb))

                if not candidates:
                    return None

                candidates.sort(key=lambda t: t[0], reverse=True)
                best_weighted, best_pb = candidates[0]

                # Remove weight for reporting a clean RPI value.
                base_rpi = float(best_weighted)
                if getattr(best_pb, "is_race", False):
                    base_rpi -= 0.3
                if best_pb.distance_category in {"5k", "10k", "half_marathon", "marathon"}:
                    base_rpi -= 0.2

                return {"rpi": round(base_rpi, 1), "pb": best_pb}
            except Exception:
                return None

        pb_rpi = _best_rpi_from_personal_bests()
        for label, dist_m in distances:
            try:
                pred = predictor.predict(athlete_id=athlete_id, race_date=race_date, distance_m=dist_m)
                predictions[label] = pred.to_dict() if pred else None
            except Exception as e:
                # If this was a DB error, the transaction may now be aborted; rollback so
                # subsequent tool calls (and other distances) can proceed.
                try:
                    db.rollback()
                except Exception:
                    pass
                # Fallback: if the calibrated model table isn't present in this environment,
                # use the athlete's stored RPI or derive one from PBs to provide a reasonable estimate.
                msg = str(e)
                fallback_rpi: Optional[float] = None
                fallback_source: Optional[str] = None

                if athlete and getattr(athlete, "rpi", None):
                    fallback_rpi = float(athlete.rpi)
                    fallback_source = "athlete_rpi"
                elif pb_rpi and pb_rpi.get("rpi"):
                    fallback_rpi = float(pb_rpi["rpi"])
                    fallback_source = "pb_rpi"

                if fallback_rpi and "athlete_calibrated_model" in msg:
                    seconds = calculate_race_time_from_rpi(float(fallback_rpi), dist_m)
                    if seconds:
                        predictions[label] = {
                            "prediction": {
                                "time_seconds": int(seconds),
                                "time_formatted": _fmt_time(int(seconds)),
                                "confidence_interval_seconds": None,
                                "confidence_interval_formatted": None,
                                "confidence": "Estimate",
                            },
                            "projections": {"rpi": round(float(fallback_rpi), 1), "ctl": None, "tsb": None},
                            "factors": [
                                "Calibrated performance model unavailable; using RPI-derived equivalent times.",
                                f"RPI source: {fallback_source or 'unknown'}",
                            ],
                            "notes": ["This estimate is less personalized than the calibrated model pipeline."],
                        }
                    else:
                        predictions[label] = {"error": msg}
                else:
                    predictions[label] = {"error": msg}

        # Evidence: cite the PB used for fallback (if any), plus a derived marker.
        if pb_rpi and pb_rpi.get("pb"):
            pb = pb_rpi["pb"]
            pb_date = (
                getattr(pb, "achieved_at", None).date().isoformat()
                if getattr(pb, "achieved_at", None)
                else date.today().isoformat()
            )
            evidence.append(
                {
                    "type": "personal_best",
                    "id": str(getattr(pb, "id", "")) or f"pb:{pb_date}:{getattr(pb, 'distance_category', 'unknown')}",
                    "date": pb_date,
                    "value": (
                        f"PB anchor for predictions: {getattr(pb, 'distance_category', 'pb')} "
                        f"in {getattr(pb, 'time_seconds', '?')}s (activity {getattr(pb, 'activity_id', '')})"
                    ),
                }
            )

        # --- Narrative ---
        pred_parts: List[str] = []
        for label_key in ["5K", "10K", "Half Marathon", "Marathon"]:
            p = predictions.get(label_key)
            if isinstance(p, dict) and "prediction" in p:
                t = p["prediction"].get("time_formatted")
                if t:
                    pred_parts.append(f"{label_key}: {t}")
        pred_summary = ", ".join(pred_parts) if pred_parts else "No predictions available"
        narrative = (
            f"Race predictions (target date {race_date.isoformat()}): {pred_summary}. "
            f"These are model-derived estimates — use compute_running_math for exact pace/time calculations."
        )

        return {
            "ok": True,
            "tool": "get_race_predictions",
            "generated_at": _iso(now),
            "narrative": narrative,
            "data": {
                "race_date": race_date.isoformat(),
                "predictions": predictions,
            },
            "evidence": evidence
            + [
                {
                    "type": "derived",
                    "id": f"race_predictions:{str(athlete_id)}",
                    "date": date.today().isoformat(),
                    "value": f"Predictions for {len(predictions)} distances (race_date={race_date.isoformat()})",
                }
            ],
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "get_race_predictions", "error": str(e)}


def get_recovery_status(db: Session, athlete_id: UUID) -> Dict[str, Any]:
    """
    Recovery metrics: half-life, durability, overtraining risk signals.
    """
    now = datetime.utcnow()
    try:
        athlete_id_str = str(athlete_id)

        # NOTE: recovery_metrics.calculate_recovery_half_life returns hours; convert to days for coach-facing output.
        half_life_hours = calculate_recovery_half_life(db, athlete_id_str)
        half_life_days = round(half_life_hours / 24.0, 2) if half_life_hours is not None else None

        durability = calculate_durability_index(db, athlete_id_str)
        false_fitness = detect_false_fitness(db, athlete_id_str)
        masked_fatigue = detect_masked_fatigue(db, athlete_id_str)

        # --- Narrative ---
        n_parts: List[str] = []
        if half_life_days is not None:
            n_parts.append(f"Recovery half-life: {half_life_days} days.")
        else:
            n_parts.append("Recovery half-life: insufficient data.")
        if durability is not None:
            dur_val = round(durability, 1) if isinstance(durability, (int, float)) else durability
            n_parts.append(f"Durability index: {dur_val}.")
        if false_fitness:
            n_parts.append("WARNING: False fitness signals detected.")
        if masked_fatigue:
            n_parts.append("WARNING: Masked fatigue signals detected.")
        if not false_fitness and not masked_fatigue:
            n_parts.append("No red flags in recovery signals.")
        narrative = " ".join(n_parts)

        return {
            "ok": True,
            "tool": "get_recovery_status",
            "generated_at": _iso(now),
            "narrative": narrative,
            "data": {
                "recovery_half_life_days": half_life_days,
                "durability_index": durability,
                "false_fitness_signals": false_fitness,
                "masked_fatigue_signals": masked_fatigue,
            },
            "evidence": [
                {
                    "type": "derived",
                    "id": f"recovery_status:{str(athlete_id)}",
                    "date": date.today().isoformat(),
                    "value": (
                        f"Recovery half-life: {half_life_days} days"
                        if half_life_days is not None
                        else "Recovery half-life: insufficient data"
                    ),
                }
            ],
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "get_recovery_status", "error": str(e)}


def get_active_insights(db: Session, athlete_id: UUID, limit: int = 5) -> Dict[str, Any]:
    """
    Prioritized actionable insights.
    """
    now = datetime.utcnow()
    try:
        limit = max(1, min(int(limit), 10))
        try:
            insights = fetch_insights(db, athlete_id, limit=limit)
            source = "calendar_insight"
        except Exception:
            # Fallback: if persisted insights are unavailable (e.g., table not present in env),
            # generate fresh insights without persisting.
            try:
                db.rollback()
            except Exception:
                pass
            athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
            if not athlete:
                raise
            generated = generate_insights_for_athlete(db=db, athlete=athlete, persist=False)
            generated = sorted(generated or [], key=lambda i: getattr(i, "priority", 0), reverse=True)[:limit]
            insights = generated
            source = "generated"

        insight_rows: List[Dict[str, Any]] = []
        evidence: List[Dict[str, Any]] = []

        for ins in insights or []:
            is_calendar = source == "calendar_insight"
            insight_type = getattr(ins, "insight_type", None)
            if hasattr(insight_type, "value"):
                insight_type = insight_type.value
            message = getattr(ins, "content", None) if is_calendar else getattr(ins, "content", None)

            insight_rows.append(
                {
                    "source": source,
                    "insight_id": str(getattr(ins, "id", "")) if getattr(ins, "id", None) else None,
                    "date": (getattr(ins, "insight_date", None) or date.today()).isoformat()
                    if getattr(ins, "insight_date", None) or not is_calendar
                    else None,
                    "type": insight_type,
                    "priority": getattr(ins, "priority", None),
                    "title": getattr(ins, "title", None),
                    "message": message,
                    "activity_id": str(getattr(ins, "activity_id", "")) if getattr(ins, "activity_id", None) else None,
                    "generation_data": getattr(ins, "generation_data", None) if is_calendar else getattr(ins, "data", None),
                    "confidence": getattr(ins, "confidence", None) if not is_calendar else None,
                }
            )

            evidence.append(
                {
                    "type": "calendar_insight" if source == "calendar_insight" else "generated_insight",
                    "id": str(getattr(ins, "id", "")) if getattr(ins, "id", None) else None,
                    "date": (getattr(ins, "insight_date", None) or date.today()).isoformat(),
                    "value": getattr(ins, "title", None) or "insight",
                }
            )

        # --- Narrative ---
        if insight_rows:
            ai_parts: List[str] = [f"{len(insight_rows)} insight(s) available:"]
            for ir in insight_rows[:3]:
                title = ir.get("title") or ir.get("message") or "Insight"
                ai_parts.append(f"• {title}")
            ai_narrative = " ".join(ai_parts)
        else:
            ai_narrative = "No active insights at this time."

        return {
            "ok": True,
            "tool": "get_active_insights",
            "generated_at": _iso(now),
            "narrative": ai_narrative,
            "data": {
                "insight_count": len(insight_rows),
                "insights": insight_rows,
            },
            "evidence": evidence,
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "get_active_insights", "error": str(e)}


def get_pb_patterns(db: Session, athlete_id: UUID) -> Dict[str, Any]:
    """
    Training patterns that preceded personal bests.

    Returns BOTH summary stats AND per-PB detail so coach can cite specifics.
    """
    from services.training_load import TrainingLoadCalculator
    from models import PersonalBest

    now = datetime.utcnow()
    try:
        start = now - timedelta(days=365)

        # Get all PBs
        pbs = db.query(PersonalBest).filter(
            PersonalBest.athlete_id == athlete_id,
            PersonalBest.achieved_at >= start,
            PersonalBest.achieved_at <= now
        ).all()

        if not pbs:
            return {
                "ok": True,
                "tool": "get_pb_patterns",
                "generated_at": _iso(now),
                "data": {"pb_count": 0, "pbs": []},
                "evidence": [],
            }

        # Get training load history for TSB lookup
        calc = TrainingLoadCalculator(db)
        try:
            history = calc.get_load_history(athlete_id, days=365)
        except Exception:
            history = []

        # Build date lookup
        load_by_date = {}
        items = history if isinstance(history, list) else history.get("daily_loads", [])
        for item in items:
            d = item.date if hasattr(item, 'date') else item.get('date')
            if hasattr(d, 'date'):
                d = d.date()
            elif isinstance(d, str):
                from datetime import datetime as dt
                d = dt.fromisoformat(d).date()
            load_by_date[d] = item

        # Build per-PB detail
        pb_details = []
        tsb_values = []

        for pb in sorted(pbs, key=lambda x: x.achieved_at or now):
            pb_date = pb.achieved_at.date() if pb.achieved_at else None
            if not pb_date:
                continue

            # Get TSB day before
            check_date = pb_date - timedelta(days=1)
            tsb = None
            ctl = None
            if check_date in load_by_date:
                item = load_by_date[check_date]
                tsb = item.tsb if hasattr(item, 'tsb') else item.get('tsb')
                ctl = item.ctl if hasattr(item, 'ctl') else item.get('ctl')
                if tsb is not None:
                    tsb = round(tsb, 1)
                    tsb_values.append(tsb)
                if ctl is not None:
                    ctl = round(ctl, 1)

            dist_km = round((pb.distance_meters or 0) / 1000, 2)
            time_min = round((pb.time_seconds or 0) / 60, 1)
            pace = round(time_min / dist_km, 2) if dist_km > 0 else None

            pb_details.append({
                "personal_best_id": str(pb.id),
                "activity_id": str(pb.activity_id) if getattr(pb, "activity_id", None) else None,
                "date": pb_date.isoformat(),
                "category": pb.distance_category,
                "distance_km": dist_km,
                "time_min": time_min,
                "pace_min_per_km": pace,
                "is_race": pb.is_race,
                "tsb_day_before": tsb,
                "ctl_day_before": ctl,
            })

        # Compute summary stats
        summary = {
            "pb_count": len(pb_details),
            "tsb_min": min(tsb_values) if tsb_values else None,
            "tsb_max": max(tsb_values) if tsb_values else None,
            "tsb_mean": round(sum(tsb_values) / len(tsb_values), 1) if tsb_values else None,
        }

        # Build evidence with actual citations
        evidence = []
        for pb in pb_details:
            anchor_id = pb.get("activity_id") or pb.get("personal_best_id") or f"pb:{pb['date']}:{pb['category']}"
            activity_part = f" (activity {pb.get('activity_id')})" if pb.get("activity_id") else ""
            evidence.append({
                "type": "personal_best",
                "id": anchor_id,
                "date": pb["date"],
                "value": f"{pb['category']} PR: {pb['distance_km']}km in {pb['time_min']}min{activity_part}, TSB was {pb['tsb_day_before']}",
            })

        # --- Narrative ---
        pb_narr_parts: List[str] = [f"{len(pb_details)} personal best(s) in the last year."]
        for pbd in pb_details[:3]:
            cat = pbd.get("category", "?")
            t_min = pbd.get("time_min")
            t_str = f"{t_min:.1f} min" if t_min else "?"
            pb_date_str = pbd.get("date", "?")
            tsb_str = f"TSB was {pbd['tsb_day_before']}" if pbd.get("tsb_day_before") is not None else "TSB unknown"
            pb_narr_parts.append(f"{cat} PR on {pb_date_str}: {t_str} ({tsb_str}).")
        if summary.get("tsb_mean") is not None:
            pb_narr_parts.append(f"Average TSB before PRs: {summary['tsb_mean']}.")
        pb_narrative = " ".join(pb_narr_parts)

        return {
            "ok": True,
            "tool": "get_pb_patterns",
            "generated_at": _iso(now),
            "narrative": pb_narrative,
            "data": {
                **summary,
                "pbs": pb_details,
            },
            "evidence": evidence,
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "get_pb_patterns", "error": str(e)}


def get_efficiency_by_zone(
    db: Session,
    athlete_id: UUID,
    effort_zone: str = "threshold",
    days: int = 90,
) -> Dict[str, Any]:
    """
    Efficiency trend for specific effort zones (comparable runs only).
    """
    now = datetime.utcnow()
    try:
        days = max(30, min(int(days), 365))
        start = now - timedelta(days=days)

        athlete_id_str = str(athlete_id)
        zone_data = aggregate_efficiency_by_effort_zone(
            athlete_id_str, start, now, db, effort_zone=effort_zone
        )
        trend_data = aggregate_efficiency_trend(
            athlete_id_str, start, now, db, effort_zone=effort_zone
        )

        efficiencies = [e for _, e in (zone_data or [])]
        current = efficiencies[-1] if efficiencies else None
        best = min(efficiencies) if efficiencies else None
        avg = (sum(efficiencies) / len(efficiencies)) if efficiencies else None

        # Evidence: include a few concrete, citable activities that match the zone filter.
        evidence: List[Dict[str, Any]] = []
        try:
            athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
            max_hr = int(athlete.max_hr) if athlete and athlete.max_hr else None
            if max_hr:
                if effort_zone == "easy":
                    hr_min, hr_max = 0, int(max_hr * 0.75)
                elif effort_zone == "threshold":
                    hr_min, hr_max = int(max_hr * 0.80), int(max_hr * 0.88)
                elif effort_zone == "race":
                    hr_min, hr_max = int(max_hr * 0.88), 999
                else:
                    hr_min, hr_max = None, None

                if hr_min is not None and hr_max is not None:
                    acts = (
                        db.query(Activity)
                        .filter(
                            Activity.athlete_id == athlete_id,
                            Activity.sport == "run",
                            Activity.start_time >= start,
                            Activity.start_time <= now,
                            Activity.avg_hr >= hr_min,
                            Activity.avg_hr <= hr_max,
                            Activity.distance_m >= 3000,
                            Activity.duration_s.isnot(None),
                            Activity.avg_hr.isnot(None),
                        )
                        .order_by(Activity.start_time.desc())
                        .limit(5)
                        .all()
                    )

                    for a in acts:
                        pace_sec_km = float(a.duration_s) / (float(a.distance_m) / 1000.0)
                        eff = pace_sec_km / float(a.avg_hr) if a.avg_hr else None
                        value_parts: List[str] = []
                        if eff is not None:
                            value_parts.append(f"zone_eff {eff:.6f} (sec/km per bpm)")
                        pace = _pace_str(a.duration_s, a.distance_m)
                        if pace:
                            value_parts.append(f"pace {pace}")
                        if a.avg_hr is not None:
                            value_parts.append(f"avg HR {int(a.avg_hr)} bpm")
                        value = ", ".join(value_parts) if value_parts else f"{effort_zone} zone run"

                        evidence.append(
                            {
                                "type": "activity",
                                "id": str(a.id),
                                "date": a.start_time.date().isoformat(),
                                "value": value,
                                # Back-compat keys
                                "activity_id": str(a.id),
                                "start_time": _iso(a.start_time),
                            }
                        )
        except Exception:
            # Don't fail the tool if evidence enrichment fails.
            pass

        # --- Narrative ---
        ez_parts: List[str] = [f"{effort_zone.capitalize()} zone efficiency over {days} days: {len(zone_data or [])} data points."]
        if current is not None:
            ez_parts.append(f"Current: {current:.4f}.")
        if best is not None:
            ez_parts.append(f"Best: {best:.4f}.")
        if avg is not None:
            ez_parts.append(f"Average: {avg:.4f}.")
        if trend_data:
            trend_pct = round(trend_data[-1][1], 1)
            direction = "improved" if trend_pct < 0 else ("declined" if trend_pct > 0 else "unchanged")
            ez_parts.append(f"Trend vs baseline: {trend_pct:+.1f}% ({direction}).")
        ez_parts.append("Lower = faster at same HR = better.")
        ez_narrative = " ".join(ez_parts)

        return {
            "ok": True,
            "tool": "get_efficiency_by_zone",
            "generated_at": _iso(now),
            "narrative": ez_narrative,
            "data": {
                "effort_zone": effort_zone,
                "window_days": days,
                "data_points": len(zone_data or []),
                "current_efficiency": round(current, 6) if current is not None else None,
                "best_efficiency": round(best, 6) if best is not None else None,
                "average_efficiency": round(avg, 6) if avg is not None else None,
                "recent_trend_pct": round(trend_data[-1][1], 2) if trend_data else None,
                "note": "Efficiency is Pace(sec/km)/HR(bpm). Lower = faster at same HR (better). Trend % is vs baseline (negative = improvement).",
            },
            "evidence": evidence
            + [
                {
                    "type": "derived",
                    "id": f"efficiency_zone:{str(athlete_id)}:{effort_zone}",
                    "date": date.today().isoformat(),
                    "value": (
                        f"{effort_zone} zone: {len(zone_data or [])} runs, current {current:.6f}"
                        if current is not None
                        else f"{effort_zone} zone: no data"
                    ),
                }
            ],
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "get_efficiency_by_zone", "error": str(e)}


def get_nutrition_correlations(
    db: Session,
    athlete_id: UUID,
    days: int = 90,
) -> Dict[str, Any]:
    """
    Get activity-linked nutrition correlations.
    """
    now = datetime.utcnow()
    try:
        days = max(30, min(int(days), 365))
        start = now - timedelta(days=days)

        # Local import to avoid circulars.
        from services.correlation_engine import aggregate_activity_nutrition

        data = aggregate_activity_nutrition(str(athlete_id), start, now, db)
        results: Dict[str, Any] = {}

        for key, pairs in (data or {}).items():
            if not pairs:
                results[key] = {
                    "sample_size": 0,
                    "correlation": None,
                    "note": "insufficient data",
                }
                continue

            if len(pairs) < 5:
                results[key] = {
                    "sample_size": len(pairs),
                    "correlation": None,
                    "note": "insufficient data",
                }
                continue

            x_vals = [p[1] for p in pairs]
            y_vals = [p[2] for p in pairs]

            n = len(x_vals)
            mean_x = sum(x_vals) / n
            mean_y = sum(y_vals) / n

            numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_vals, y_vals))
            denom_x = sum((x - mean_x) ** 2 for x in x_vals) ** 0.5
            denom_y = sum((y - mean_y) ** 2 for y in y_vals) ** 0.5

            if denom_x == 0 or denom_y == 0:
                r = 0.0
            else:
                r = numerator / (denom_x * denom_y)

            results[key] = {
                "sample_size": n,
                "correlation": round(float(r), 3),
                "interpretation": _interpret_nutrition_correlation(key, float(r)),
            }

        # --- Narrative ---
        nc_items: List[str] = []
        for key, val in results.items():
            if isinstance(val, dict) and val.get("correlation") is not None:
                interp = val.get("interpretation", "")
                nc_items.append(f"{key}: r={val['correlation']:.2f} ({interp})")
        if nc_items:
            nc_narrative = f"Nutrition correlations over {days} days: " + "; ".join(nc_items[:3]) + "."
        else:
            nc_narrative = f"No significant nutrition correlations found over {days} days."

        return {
            "ok": True,
            "tool": "get_nutrition_correlations",
            "generated_at": _iso(now),
            "narrative": nc_narrative,
            "data": results,
            "evidence": [
                {
                    "type": "derived",
                    "id": f"nutrition_correlations:{str(athlete_id)}",
                    "date": date.today().isoformat(),
                    "value": f"Activity-linked nutrition analysis over {days} days",
                }
            ],
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "get_nutrition_correlations", "error": str(e)}


def get_weekly_volume(db: Session, athlete_id: UUID, weeks: int = 12) -> Dict[str, Any]:
    """
    Weekly rollups of run volume (distance/time/count).

    This is designed for questions like:
    - "What were my highest-volume weeks recently?"
    - "How consistent have I been since returning from injury?"
    """
    now = datetime.utcnow()
    try:
        weeks = max(1, min(int(weeks), 104))  # cap at ~2 years
        units = _preferred_units(db, athlete_id)

        # Build week buckets aligned to Monday starts (ISO week).
        today = date.today()
        end_week_start = today - timedelta(days=today.weekday())  # Monday
        start_week_start = end_week_start - timedelta(days=7 * (weeks - 1))
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
            .order_by(Activity.start_time.asc())
            .all()
        )

        buckets: Dict[str, Dict[str, Any]] = {}
        for w in range(weeks):
            ws = start_week_start + timedelta(days=7 * w)
            key = ws.isoformat()
            buckets[key] = {
                "week_start": key,
                "week_end": (ws + timedelta(days=6)).isoformat(),
                "run_count": 0,
                "total_distance_m": 0.0,
                "total_duration_s": 0.0,
            }

        for a in runs:
            d = a.start_time.date()
            ws = d - timedelta(days=d.weekday())
            key = ws.isoformat()
            if key not in buckets:
                continue
            b = buckets[key]
            b["run_count"] += 1
            b["total_distance_m"] += float(a.distance_m or 0)
            b["total_duration_s"] += float(a.duration_s or 0)

        current_week_key = end_week_start.isoformat()
        week_rows: List[Dict[str, Any]] = []
        for key in sorted(buckets.keys()):
            b = buckets[key]
            dist_m = float(b["total_distance_m"])
            dur_s = float(b["total_duration_s"])
            row: Dict[str, Any] = {
                "week_start": b["week_start"],
                "week_end": b["week_end"],
                "run_count": int(b["run_count"]),
                "total_distance_km": round(dist_m / 1000.0, 2),
                "total_distance_mi": round(dist_m / _M_PER_MI, 2),
                "total_duration_hr": round(dur_s / 3600.0, 2),
            }
            # Mark the current (in-progress) week so the coach doesn't
            # confuse partial data with a completed week.
            if key == current_week_key:
                days_elapsed = (today - end_week_start).days + 1  # 1-7
                row["is_current_week"] = True
                row["days_elapsed"] = days_elapsed
                row["days_remaining"] = 7 - days_elapsed
                row["note"] = f"IN PROGRESS — only {days_elapsed} of 7 days completed"
            week_rows.append(row)

        # Evidence: cite the top 3 weeks by distance in preferred units
        def _week_magnitude(wr: Dict[str, Any]) -> float:
            return float(wr.get("total_distance_mi" if units == "imperial" else "total_distance_km") or 0)

        top_weeks = sorted(week_rows, key=_week_magnitude, reverse=True)[:3]
        evidence: List[Dict[str, Any]] = []
        for w in top_weeks:
            dist = w["total_distance_mi"] if units == "imperial" else w["total_distance_km"]
            unit = "mi" if units == "imperial" else "km"
            partial_note = " (IN PROGRESS — week not complete)" if w.get("is_current_week") else ""
            evidence.append(
                {
                    "type": "derived",
                    "id": f"weekly_volume:{str(athlete_id)}:{w['week_start']}",
                    "date": w["week_start"],
                    "value": f"Week of {w['week_start']}: {dist:.1f} {unit} across {w['run_count']} runs{partial_note}",
                }
            )

        # --- Narrative ---
        unit_label = "mi" if units == "imperial" else "km"
        dist_key = "total_distance_mi" if units == "imperial" else "total_distance_km"

        # Identify the current (partial) week and the last full week
        current_row = next((w for w in week_rows if w.get("is_current_week")), None)
        completed_rows = [w for w in week_rows if not w.get("is_current_week")]
        last_full = completed_rows[-1] if completed_rows else None

        lines: List[str] = []
        if current_row:
            lines.append(
                f"This week (in progress, {current_row['days_elapsed']} of 7 days): "
                f"{current_row[dist_key]:.1f} {unit_label} across {current_row['run_count']} runs. "
                f"DO NOT treat this as a full week."
            )
        if last_full:
            lines.append(
                f"Last full week ({last_full['week_start']}): "
                f"{last_full[dist_key]:.1f} {unit_label} across {last_full['run_count']} runs."
            )

        # 4-week trend
        recent_4 = completed_rows[-4:] if len(completed_rows) >= 4 else completed_rows
        if len(recent_4) >= 2:
            vols = [w[dist_key] for w in recent_4]
            trajectory = "rising" if vols[-1] > vols[0] else ("falling" if vols[-1] < vols[0] else "flat")
            lines.append(
                f"Last {len(recent_4)} full weeks trajectory: {trajectory} "
                f"({' → '.join(f'{v:.0f}' for v in vols)} {unit_label})."
            )

        # Peak week
        if completed_rows:
            peak = max(completed_rows, key=lambda w: w[dist_key])
            lines.append(
                f"Peak week in window: {peak['week_start']} at {peak[dist_key]:.1f} {unit_label}."
            )

        narrative = " ".join(lines) if lines else "No weekly volume data available."

        return {
            "ok": True,
            "tool": "get_weekly_volume",
            "generated_at": _iso(now),
            "narrative": narrative,
            "data": {
                "preferred_units": units,
                "weeks": weeks,
                "week_start_first": start_week_start.isoformat(),
                "week_start_last": end_week_start.isoformat(),
                "weeks_data": week_rows,
            },
            "evidence": evidence,
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "get_weekly_volume", "error": str(e)}


def get_best_runs(
    db: Session,
    athlete_id: UUID,
    days: int = 365,
    metric: str = "efficiency",
    limit: int = 5,
    effort_zone: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return the "best" runs by an explicit, auditable definition.

    Metrics:
      - efficiency: highest speed/HR (higher = better)
      - pace: fastest pace (min/mi or min/km depending on units)
      - distance: longest distance
      - intensity_score: highest intensity_score

    Optional effort_zone filters by athlete max_hr:
      - easy / threshold / race (same mapping used elsewhere)
    """
    now = datetime.utcnow()
    try:
        days = max(7, min(int(days), 730))
        limit = max(1, min(int(limit), 10))
        units = _preferred_units(db, athlete_id)

        cutoff = now - timedelta(days=days)
        q = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete_id,
                Activity.sport == "run",
                Activity.start_time >= cutoff,
                Activity.distance_m.isnot(None),
                Activity.duration_s.isnot(None),
            )
        )

        if effort_zone:
            ez = effort_zone.lower().strip()
            athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
            max_hr = int(athlete.max_hr) if athlete and athlete.max_hr else None
            if max_hr:
                if ez == "easy":
                    hr_min, hr_max = 0, int(max_hr * 0.75)
                elif ez == "threshold":
                    hr_min, hr_max = int(max_hr * 0.80), int(max_hr * 0.88)
                elif ez == "race":
                    hr_min, hr_max = int(max_hr * 0.88), 999
                else:
                    hr_min, hr_max = None, None
                if hr_min is not None and hr_max is not None:
                    q = q.filter(Activity.avg_hr.isnot(None), Activity.avg_hr >= hr_min, Activity.avg_hr <= hr_max)

        acts = q.order_by(Activity.start_time.desc()).limit(200).all()  # bounded

        rows: List[Dict[str, Any]] = []
        for a in acts:
            distance_m = float(a.distance_m or 0)
            duration_s = float(a.duration_s or 0)
            if distance_m <= 0 or duration_s <= 0:
                continue

            pace_s_per_km = duration_s / (distance_m / 1000.0)
            pace_mi = _pace_str_mi(int(a.duration_s) if a.duration_s else None, int(a.distance_m) if a.distance_m else None)
            pace_km = _pace_str(int(a.duration_s) if a.duration_s else None, int(a.distance_m) if a.distance_m else None)
            speed_mps = (distance_m / duration_s) if duration_s > 0 else None
            eff = (speed_mps / float(a.avg_hr)) if (speed_mps and a.avg_hr) else None

            rows.append(
                {
                    "activity_id": str(a.id),
                    "date": a.start_time.date().isoformat(),
                    "name": (a.name or "").strip() or "Run",
                    "distance_km": round(distance_m / 1000.0, 2),
                    "distance_mi": round(distance_m / _M_PER_MI, 2),
                    "duration_s": int(duration_s),
                    "avg_hr": int(a.avg_hr) if a.avg_hr is not None else None,
                    "pace_per_km": pace_km,
                    "pace_per_mile": pace_mi,
                    "intensity_score": float(a.intensity_score) if a.intensity_score is not None else None,
                    "efficiency_speed_per_hr": round(eff, 6) if eff is not None else None,
                }
            )

        def _score(r: Dict[str, Any]) -> float:
            if metric == "efficiency":
                v = r.get("efficiency_speed_per_hr")
                return -float(v) if v is not None else 1e9  # higher is better
            if metric == "pace":
                # lower seconds per km is better; derive from formatted pace if possible
                # fall back to distance/duration
                dur = r.get("duration_s") or 0
                dist_km = r.get("distance_km") or 0
                if dur and dist_km:
                    return float(dur) / float(dist_km)
                return 1e9
            if metric == "distance":
                return -float(r.get("distance_km") or 0)  # negative so sort ascending works
            if metric == "intensity_score":
                return -float(r.get("intensity_score") or 0)
            return 0.0

        # Sort: for some metrics we inverted the sign so "best" is still smallest _score.
        rows_sorted = sorted(rows, key=_score)
        best = rows_sorted[:limit]

        evidence: List[Dict[str, Any]] = []
        for r in best:
            dist = r["distance_mi"] if units == "imperial" else r["distance_km"]
            unit = "mi" if units == "imperial" else "km"
            pace = r["pace_per_mile"] if units == "imperial" else r["pace_per_km"]
            parts = [r["name"], f"{dist:.1f} {unit}", f"@ {pace}"]
            if r.get("avg_hr") is not None:
                parts.append(f"(avg HR {r['avg_hr']} bpm)")
            if metric == "efficiency" and r.get("efficiency_speed_per_hr") is not None:
                parts.append(f"[eff {r['efficiency_speed_per_hr']:.6f}]")
            evidence.append(
                {
                    "type": "activity",
                    "id": r["activity_id"],
                    "ref": r["activity_id"][:8],
                    "date": r["date"],
                    "value": " ".join(parts),
                }
            )

        # --- Narrative ---
        br_parts: List[str] = [f"Top {len(best)} runs by {metric} in the last {days} days:"]
        for i, r in enumerate(best, 1):
            d = r["distance_mi"] if units == "imperial" else r["distance_km"]
            u = "mi" if units == "imperial" else "km"
            p = r["pace_per_mile"] if units == "imperial" else r["pace_per_km"]
            hr_str = f", avg HR {r['avg_hr']}" if r.get("avg_hr") else ""
            br_parts.append(f"{i}. {r['name']} ({r['date']}): {d:.1f} {u} @ {p}{hr_str}.")
        br_narrative = " ".join(br_parts) if best else f"No qualifying runs found by {metric} in the last {days} days."

        return {
            "ok": True,
            "tool": "get_best_runs",
            "generated_at": _iso(now),
            "narrative": br_narrative,
            "data": {
                "preferred_units": units,
                "window_days": days,
                "metric": metric,
                "effort_zone": effort_zone,
                "results": best,
            },
            "evidence": evidence,
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "get_best_runs", "error": str(e)}


def compare_training_periods(db: Session, athlete_id: UUID, days: int = 28) -> Dict[str, Any]:
    """
    Compare the last N days to the previous N days.

    Designed for:
    - "Am I ramping too fast?"
    - "What changed in the last 4 weeks vs the prior 4 weeks?"
    """
    now = datetime.utcnow()
    try:
        days = max(7, min(int(days), 180))
        units = _preferred_units(db, athlete_id)

        end_a = now
        start_a = now - timedelta(days=days)
        end_b = start_a
        start_b = start_a - timedelta(days=days)

        def _fetch(start: datetime, end: datetime) -> List[Activity]:
            return (
                db.query(Activity)
                .filter(
                    Activity.athlete_id == athlete_id,
                    Activity.sport == "run",
                    Activity.start_time >= start,
                    Activity.start_time < end,
                )
                .order_by(Activity.start_time.desc())
                .all()
            )

        a = _fetch(start_a, end_a)
        b = _fetch(start_b, end_b)

        def _summ(acts: List[Activity]) -> Dict[str, Any]:
            total_m = sum(float(x.distance_m or 0) for x in acts)
            total_s = sum(float(x.duration_s or 0) for x in acts)
            run_count = sum(1 for x in acts if x.distance_m)
            avg_hr_vals = [int(x.avg_hr) for x in acts if x.avg_hr is not None]
            return {
                "run_count": run_count,
                "total_distance_km": round(total_m / 1000.0, 2),
                "total_distance_mi": round(total_m / _M_PER_MI, 2),
                "total_duration_hr": round(total_s / 3600.0, 2),
                "avg_hr": round(sum(avg_hr_vals) / len(avg_hr_vals), 1) if avg_hr_vals else None,
            }

        sa = _summ(a)
        sb = _summ(b)

        def _pct(new: float, old: float) -> Optional[float]:
            try:
                if old == 0:
                    return None
                return round(((new - old) / old) * 100.0, 1)
            except Exception:
                return None

        dist_a = sa["total_distance_mi"] if units == "imperial" else sa["total_distance_km"]
        dist_b = sb["total_distance_mi"] if units == "imperial" else sb["total_distance_km"]
        dist_delta_pct = _pct(float(dist_a), float(dist_b))

        # Evidence: cite a couple runs from each period, in preferred units
        def _fmt_run(act: Activity) -> str:
            distance_km = (float(act.distance_m) / 1000.0) if act.distance_m else None
            distance_mi = _mi_from_m(act.distance_m) if act.distance_m else None
            if units == "imperial":
                dist = f"{distance_mi:.1f} mi" if distance_mi is not None else "n/a"
                pace = _pace_str_mi(act.duration_s, act.distance_m) or "n/a"
            else:
                dist = f"{distance_km:.1f} km" if distance_km is not None else "n/a"
                pace = _pace_str(act.duration_s, act.distance_m) or "n/a"
            hr = f"(avg HR {int(act.avg_hr)} bpm)" if act.avg_hr is not None else ""
            name = (act.name or "").strip() or "Run"
            return f"{name} {dist} @ {pace} {hr}".strip()

        evidence: List[Dict[str, Any]] = []
        for act in (a[:2] if a else []):
            evidence.append(
                {
                    "type": "activity",
                    "id": str(act.id),
                    "ref": str(act.id)[:8],
                    "date": act.start_time.date().isoformat(),
                    "value": _fmt_run(act),
                }
            )
        for act in (b[:2] if b else []):
            evidence.append(
                {
                    "type": "activity",
                    "id": str(act.id),
                    "ref": str(act.id)[:8],
                    "date": act.start_time.date().isoformat(),
                    "value": _fmt_run(act),
                }
            )

        # --- Narrative ---
        unit_lbl = "mi" if units == "imperial" else "km"
        dist_a_val = sa["total_distance_mi"] if units == "imperial" else sa["total_distance_km"]
        dist_b_val = sb["total_distance_mi"] if units == "imperial" else sb["total_distance_km"]
        cp_parts: List[str] = [
            f"Last {days} days vs prior {days} days: "
            f"{dist_a_val:.0f} {unit_lbl} ({sa['run_count']} runs) vs "
            f"{dist_b_val:.0f} {unit_lbl} ({sb['run_count']} runs)."
        ]
        if dist_delta_pct is not None:
            direction = "increase" if dist_delta_pct > 0 else ("decrease" if dist_delta_pct < 0 else "no change")
            cp_parts.append(f"Volume change: {dist_delta_pct:+.0f}% ({direction}).")
            if abs(dist_delta_pct) > 30:
                cp_parts.append("This is a significant ramp — monitor for injury risk.")
        cp_narrative = " ".join(cp_parts)

        return {
            "ok": True,
            "tool": "compare_training_periods",
            "generated_at": _iso(now),
            "narrative": cp_narrative,
            "data": {
                "preferred_units": units,
                "days": days,
                "period_a": {
                    "start": start_a.date().isoformat(),
                    "end": (end_a.date()).isoformat(),
                    "summary": sa,
                },
                "period_b": {
                    "start": start_b.date().isoformat(),
                    "end": (end_b.date()).isoformat(),
                    "summary": sb,
                },
                "deltas": {
                    "distance_delta_pct": dist_delta_pct,
                    "run_count_delta": sa["run_count"] - sb["run_count"],
                },
            },
            "evidence": evidence,
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "compare_training_periods", "error": str(e)}


# =============================================================================
# PHASE 3: NEW TOOLS - Wellness, Athlete Profile, Training Load History
# =============================================================================

def get_wellness_trends(db: Session, athlete_id: UUID, days: int = 28) -> Dict[str, Any]:
    """
    Phase 3: Wellness trends from DailyCheckin data.

    Returns sleep, stress, soreness, HRV, and mindset trends.
    Critical for understanding recovery context and readiness.
    """
    from models import DailyCheckin

    now = datetime.utcnow()
    days = max(7, min(int(days), 90))
    cutoff = now - timedelta(days=days)

    try:
        checkins = (
            db.query(DailyCheckin)
            .filter(
                DailyCheckin.athlete_id == athlete_id,
                DailyCheckin.date >= cutoff.date(),
            )
            .order_by(DailyCheckin.date.desc())
            .all()
        )

        if not checkins:
            return {
                "ok": True,
                "tool": "get_wellness_trends",
                "generated_at": _iso(now),
                "data": {
                    "window_days": days,
                    "checkin_count": 0,
                    "message": "No wellness check-ins recorded in this period.",
                },
                "evidence": [],
            }

        # Aggregate metrics
        sleep_values = [float(c.sleep_h) for c in checkins if c.sleep_h is not None]
        stress_values = [int(c.stress_1_5) for c in checkins if c.stress_1_5 is not None]
        soreness_values = [int(c.soreness_1_5) for c in checkins if c.soreness_1_5 is not None]
        hrv_values = [float(c.hrv_rmssd) for c in checkins if c.hrv_rmssd is not None]
        resting_hr_values = [int(c.resting_hr) for c in checkins if c.resting_hr is not None]
        enjoyment_values = [int(c.enjoyment_1_5) for c in checkins if c.enjoyment_1_5 is not None]
        confidence_values = [int(c.confidence_1_5) for c in checkins if c.confidence_1_5 is not None]
        motivation_values = [int(c.motivation_1_5) for c in checkins if c.motivation_1_5 is not None]

        def avg(vals: List) -> Optional[float]:
            return round(sum(vals) / len(vals), 2) if vals else None

        def trend(vals: List) -> Optional[str]:
            """Determine if values are trending up, down, or stable."""
            if len(vals) < 3:
                return None
            recent = vals[:len(vals)//2]
            older = vals[len(vals)//2:]
            if not recent or not older:
                return None
            recent_avg = sum(recent) / len(recent)
            older_avg = sum(older) / len(older)
            delta_pct = ((recent_avg - older_avg) / older_avg * 100) if older_avg else 0
            if delta_pct > 10:
                return "improving"
            elif delta_pct < -10:
                return "declining"
            return "stable"

        # Build recent entries for evidence
        evidence: List[Dict[str, Any]] = []
        for c in checkins[:7]:  # Last 7 entries
            parts = []
            if c.sleep_h:
                parts.append(f"sleep:{float(c.sleep_h):.1f}h")
            if c.stress_1_5:
                parts.append(f"stress:{c.stress_1_5}/5")
            if c.soreness_1_5:
                parts.append(f"soreness:{c.soreness_1_5}/5")
            if c.hrv_rmssd:
                parts.append(f"HRV:{float(c.hrv_rmssd):.0f}")
            if c.resting_hr:
                parts.append(f"RHR:{c.resting_hr}")

            evidence.append({
                "type": "wellness",
                "date": c.date.isoformat(),
                "value": " | ".join(parts) if parts else "check-in recorded",
            })

        # --- Narrative ---
        wt_parts: List[str] = [f"Wellness over {days} days ({len(checkins)} check-ins):"]
        if sleep_values:
            wt_parts.append(f"Sleep avg {avg(sleep_values):.1f}h (trend: {trend(sleep_values) or 'N/A'}).")
        if stress_values:
            wt_parts.append(f"Stress avg {avg(stress_values):.1f}/5 (trend: {trend(stress_values) or 'N/A'}).")
        if soreness_values:
            wt_parts.append(f"Soreness avg {avg(soreness_values):.1f}/5 (trend: {trend(soreness_values) or 'N/A'}).")
        if hrv_values:
            wt_parts.append(f"HRV avg {avg(hrv_values):.0f} ms (trend: {trend(hrv_values) or 'N/A'}). Higher = better recovery.")
        if resting_hr_values:
            wt_parts.append(f"Resting HR avg {avg(resting_hr_values):.0f} bpm (trend: {trend(resting_hr_values) or 'N/A'}).")
        wt_narrative = " ".join(wt_parts) if len(wt_parts) > 1 else "No wellness data available."

        return {
            "ok": True,
            "tool": "get_wellness_trends",
            "generated_at": _iso(now),
            "narrative": wt_narrative,
            "data": {
                "window_days": days,
                "checkin_count": len(checkins),
                "sleep": {
                    "avg_hours": avg(sleep_values),
                    "min_hours": round(min(sleep_values), 1) if sleep_values else None,
                    "max_hours": round(max(sleep_values), 1) if sleep_values else None,
                    "trend": trend(sleep_values),
                    "data_points": len(sleep_values),
                },
                "stress": {
                    "avg": avg(stress_values),
                    "trend": trend(stress_values),
                    "data_points": len(stress_values),
                    "note": "1=low stress, 5=high stress",
                },
                "soreness": {
                    "avg": avg(soreness_values),
                    "trend": trend(soreness_values),
                    "data_points": len(soreness_values),
                    "note": "1=no soreness, 5=very sore",
                },
                "hrv": {
                    "avg_rmssd": avg(hrv_values),
                    "trend": trend(hrv_values),
                    "data_points": len(hrv_values),
                    "note": "Higher HRV generally indicates better recovery",
                },
                "resting_hr": {
                    "avg_bpm": avg(resting_hr_values),
                    "trend": trend(resting_hr_values),
                    "data_points": len(resting_hr_values),
                    "note": "Lower resting HR often indicates better fitness/recovery",
                },
                "mindset": {
                    "avg_enjoyment": avg(enjoyment_values),
                    "avg_confidence": avg(confidence_values),
                    "avg_motivation": avg(motivation_values),
                    "note": "All scales 1-5, higher is better",
                },
            },
            "evidence": evidence,
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "get_wellness_trends", "error": str(e)}


def get_athlete_profile(db: Session, athlete_id: UUID) -> Dict[str, Any]:
    """
    Phase 3: Athlete profile with physiological thresholds and runner typing.

    Returns max_hr, threshold paces, RPI, runner type, and training metrics.
    Critical for personalized recommendations and goal setting.
    """
    now = datetime.utcnow()

    try:
        athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            return {"ok": False, "tool": "get_athlete_profile", "error": "Athlete not found"}

        units = (athlete.preferred_units or "metric")

        # Calculate age if birthdate available
        age = None
        if athlete.birthdate:
            today = date.today()
            age = today.year - athlete.birthdate.year - (
                (today.month, today.day) < (athlete.birthdate.month, athlete.birthdate.day)
            )

        # Convert threshold pace for display
        threshold_pace_display = None
        if athlete.threshold_pace_per_km:
            if units == "imperial":
                # Convert sec/km to min:sec/mile
                sec_per_mi = athlete.threshold_pace_per_km * 1.60934
                m = int(sec_per_mi // 60)
                s = int(round(sec_per_mi % 60))
                threshold_pace_display = f"{m}:{s:02d}/mi"
            else:
                m = int(athlete.threshold_pace_per_km // 60)
                s = int(round(athlete.threshold_pace_per_km % 60))
                threshold_pace_display = f"{m}:{s:02d}/km"

        # Calculate HR zones if max_hr available
        hr_zones = None
        if athlete.max_hr:
            max_hr = athlete.max_hr
            hr_zones = {
                "zone_1_recovery": {"min": int(max_hr * 0.50), "max": int(max_hr * 0.60)},
                "zone_2_easy": {"min": int(max_hr * 0.60), "max": int(max_hr * 0.70)},
                "zone_3_moderate": {"min": int(max_hr * 0.70), "max": int(max_hr * 0.80)},
                "zone_4_threshold": {"min": int(max_hr * 0.80), "max": int(max_hr * 0.90)},
                "zone_5_max": {"min": int(max_hr * 0.90), "max": max_hr},
            }

        # Build evidence
        evidence: List[Dict[str, Any]] = []
        if athlete.rpi:
            evidence.append({"type": "metric", "name": "RPI", "value": f"{athlete.rpi:.1f}"})
        if athlete.runner_type:
            evidence.append({"type": "classification", "name": "runner_type", "value": athlete.runner_type})
        if athlete.max_hr:
            evidence.append({"type": "metric", "name": "max_hr", "value": f"{athlete.max_hr} bpm"})

        # --- Narrative ---
        n_parts: List[str] = []
        if age is not None:
            n_parts.append(f"{age}-year-old")
        if athlete.sex:
            n_parts.append(f"{athlete.sex}")
        n_parts.append("runner.")
        if athlete.rpi:
            n_parts.append(f"RPI (Running Performance Index): {athlete.rpi:.1f}.")
        if athlete.runner_type:
            n_parts.append(f"Runner type: {athlete.runner_type}.")
        if athlete.max_hr:
            n_parts.append(f"Max HR: {athlete.max_hr} bpm.")
        if threshold_pace_display:
            n_parts.append(f"Threshold pace: {threshold_pace_display}.")
        if athlete.durability_index:
            n_parts.append(f"Durability index: {float(athlete.durability_index):.1f}.")
        if athlete.recovery_half_life_hours:
            rhl_days = round(float(athlete.recovery_half_life_hours) / 24.0, 1)
            n_parts.append(f"Recovery half-life: {rhl_days} days.")
        if athlete.current_streak_weeks:
            n_parts.append(f"Current training streak: {athlete.current_streak_weeks} weeks.")
        narrative = " ".join(n_parts) if n_parts else "Athlete profile data unavailable."

        return {
            "ok": True,
            "tool": "get_athlete_profile",
            "generated_at": _iso(now),
            "narrative": narrative,
            "data": {
                "preferred_units": units,
                "demographics": {
                    "age": age,
                    "sex": athlete.sex,
                    "height_cm": float(athlete.height_cm) if athlete.height_cm else None,
                },
                "physiological": {
                    "max_hr": athlete.max_hr,
                    "resting_hr": athlete.resting_hr,
                    "threshold_hr": athlete.threshold_hr,
                    "threshold_pace": threshold_pace_display,
                    "threshold_pace_sec_per_km": float(athlete.threshold_pace_per_km) if athlete.threshold_pace_per_km else None,
                    "rpi": float(athlete.rpi) if athlete.rpi else None,  # Running Performance Index
                    "rpi": float(athlete.rpi) if athlete.rpi else None,  # Keep for backward compatibility
                    "hr_zones": hr_zones,
                },
                "runner_typing": {
                    "type": athlete.runner_type,
                    "confidence": float(athlete.runner_type_confidence) if athlete.runner_type_confidence else None,
                    "last_calculated": _iso(athlete.runner_type_last_calculated) if athlete.runner_type_last_calculated else None,
                    "type_descriptions": {
                        "speedster": "Strong at shorter distances, may need endurance work for marathons",
                        "endurance_monster": "Excels at longer distances, may need speed work for 5K/10K",
                        "balanced": "Versatile across all distances",
                    },
                },
                "training_metrics": {
                    "durability_index": float(athlete.durability_index) if athlete.durability_index else None,
                    "recovery_half_life_hours": float(athlete.recovery_half_life_hours) if athlete.recovery_half_life_hours else None,
                    "consistency_index": float(athlete.consistency_index) if athlete.consistency_index else None,
                    "current_streak_weeks": athlete.current_streak_weeks,
                    "longest_streak_weeks": athlete.longest_streak_weeks,
                },
            },
            "evidence": evidence,
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "get_athlete_profile", "error": str(e)}


def get_training_load_history(db: Session, athlete_id: UUID, days: int = 42) -> Dict[str, Any]:
    """
    Phase 3: Training load history showing ATL/CTL/TSB trends over time.

    Returns daily snapshots of training load metrics to understand load progression.
    Critical for periodization analysis and injury risk assessment.
    """
    now = datetime.utcnow()
    days = max(7, min(int(days), 90))

    try:
        # Get activities for the window + buffer for CTL calculation (42 days for CTL)
        buffer_days = 42
        cutoff = now - timedelta(days=days + buffer_days)

        runs = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete_id,
                Activity.sport == "run",
                Activity.start_time >= cutoff,
            )
            .order_by(Activity.start_time.asc())
            .all()
        )

        if not runs:
            return {
                "ok": True,
                "tool": "get_training_load_history",
                "generated_at": _iso(now),
                "data": {
                    "window_days": days,
                    "message": "No training data available for load calculation.",
                },
                "evidence": [],
            }

        # Calculate daily TSS values
        daily_tss: Dict[date, float] = {}
        for a in runs:
            run_date = a.start_time.date()
            # Simple TSS approximation: (duration_min * intensity_score / 100) or duration-based fallback
            duration_min = (a.duration_s or 0) / 60
            intensity = (a.intensity_score or 50) / 100  # Default to moderate if unknown
            tss = duration_min * intensity
            daily_tss[run_date] = daily_tss.get(run_date, 0) + tss

        # Calculate ATL (7-day) and CTL (42-day) for each day in window
        atl_decay = 1 - (2 / 8)  # 7-day time constant
        ctl_decay = 1 - (2 / 43)  # 42-day time constant

        history: List[Dict[str, Any]] = []
        evidence: List[Dict[str, Any]] = []

        atl = 0.0
        ctl = 0.0

        start_date = (now - timedelta(days=days + buffer_days)).date()
        end_date = now.date()
        current_date = start_date

        while current_date <= end_date:
            day_tss = daily_tss.get(current_date, 0)

            # Exponential weighted moving average
            atl = atl * atl_decay + day_tss * (1 - atl_decay)
            ctl = ctl * ctl_decay + day_tss * (1 - ctl_decay)
            tsb = ctl - atl

            # Only include days within the requested window
            if current_date >= (now - timedelta(days=days)).date():
                # Determine form state
                form_state = "fresh" if tsb > 10 else ("fatigued" if tsb < -10 else "balanced")

                # Risk assessment
                if atl > ctl * 1.3:
                    risk = "high"
                elif atl > ctl * 1.1:
                    risk = "moderate"
                else:
                    risk = "low"

                history.append({
                    "date": current_date.isoformat(),
                    "atl": round(atl, 1),
                    "ctl": round(ctl, 1),
                    "tsb": round(tsb, 1),
                    "form_state": form_state,
                    "injury_risk": risk,
                    "day_tss": round(day_tss, 1),
                })

            current_date += timedelta(days=1)

        # Get current state (latest entry)
        current = history[-1] if history else None

        # Calculate trends
        if len(history) >= 7:
            recent_ctl = [h["ctl"] for h in history[-7:]]
            older_ctl = [h["ctl"] for h in history[-14:-7]] if len(history) >= 14 else []
            ctl_trend = None
            if older_ctl:
                recent_avg = sum(recent_ctl) / len(recent_ctl)
                older_avg = sum(older_ctl) / len(older_ctl)
                delta_pct = ((recent_avg - older_avg) / older_avg * 100) if older_avg else 0
                if delta_pct > 5:
                    ctl_trend = "building"
                elif delta_pct < -5:
                    ctl_trend = "tapering"
                else:
                    ctl_trend = "maintaining"
        else:
            ctl_trend = None

        # Build evidence from key dates
        for h in history[-7:]:
            evidence.append({
                "type": "load_snapshot",
                "date": h["date"],
                "value": f"ATL={h['atl']:.0f} CTL={h['ctl']:.0f} TSB={h['tsb']:+.0f} ({h['form_state']})",
            })

        # --- Narrative ---
        tlh_parts: List[str] = [f"Training load history over {days} days."]
        if current:
            tlh_parts.append(
                f"Current: ATL={current['atl']:.0f}, CTL={current['ctl']:.0f}, "
                f"TSB={current['tsb']:+.0f} ({current['form_state']}). "
                f"Injury risk: {current['injury_risk']}."
            )
        if ctl_trend:
            tlh_parts.append(f"CTL trend: {ctl_trend}.")
        tlh_narrative = " ".join(tlh_parts)

        return {
            "ok": True,
            "tool": "get_training_load_history",
            "generated_at": _iso(now),
            "narrative": tlh_narrative,
            "data": {
                "window_days": days,
                "current_state": current,
                "ctl_trend": ctl_trend,
                "ctl_trend_note": {
                    "building": "Fitness is increasing - good for base building",
                    "tapering": "Fitness is decreasing - expected before races or during recovery",
                    "maintaining": "Fitness is stable - good for maintenance phases",
                }.get(ctl_trend, None),
                "history": history,
                "guidance": {
                    "tsb_interpretation": "TSB > 10: Fresh/ready to race. TSB 0-10: Balanced. TSB < 0: Fatigued (training hard).",
                    "injury_risk_note": "High risk when ATL > 1.3x CTL (acute:chronic ratio too high).",
                },
            },
            "evidence": evidence,
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "get_training_load_history", "error": str(e)}


def _interpret_nutrition_correlation(key: str, r: float) -> str:
    """Interpret correlation coefficient for nutrition."""
    if abs(r) < 0.1:
        return "No meaningful relationship found"

    # NOTE: Efficiency in our system is pace(sec/km)/HR, so LOWER is better.
    # That means a NEGATIVE correlation between intake and efficiency can be a positive sign.
    if "efficiency" in key and "delta" not in key:
        if r < -0.3:
            return "Strong positive effect: higher intake -> better efficiency"
        elif r < -0.1:
            return "Moderate positive effect"
        elif r > 0.3:
            return "Possible negative effect: higher intake -> worse efficiency"
        elif r > 0.1:
            return "Slight negative effect"

    if "delta" in key:
        if r < -0.3:
            return "Strong recovery benefit: higher protein -> faster recovery"
        elif r < -0.1:
            return "Moderate recovery benefit"
        elif r > 0.1:
            return "No recovery benefit detected"

    return f"Correlation: {r:.2f}"


# =============================================================================
# SELF-GUIDED COACHING: ATHLETE INTENT SNAPSHOT + PRESCRIPTIONS
# =============================================================================

def _get_intent_snapshot(db: Session, athlete_id: UUID):
    from models import CoachIntentSnapshot

    snap = db.query(CoachIntentSnapshot).filter(CoachIntentSnapshot.athlete_id == athlete_id).first()
    return snap


def _is_snapshot_stale(snapshot, ttl_days: int = 7) -> bool:
    try:
        if not snapshot or not getattr(snapshot, "updated_at", None):
            return True
        cutoff = datetime.utcnow() - timedelta(days=int(ttl_days))
        # updated_at is tz-aware in DB; compare safely by casting to naive UTC if needed.
        updated = snapshot.updated_at
        if hasattr(updated, "replace") and getattr(updated, "tzinfo", None) is not None:
            updated = updated.replace(tzinfo=None)
        return updated < cutoff
    except Exception:
        return True


def get_coach_intent_snapshot(db: Session, athlete_id: UUID, ttl_days: int = 7) -> Dict[str, Any]:
    """
    Return the athlete's current intent snapshot (self-guided coaching state).
    """
    now = datetime.utcnow()
    try:
        snap = _get_intent_snapshot(db, athlete_id)
        stale = _is_snapshot_stale(snap, ttl_days=ttl_days)

        data = {
            "ttl_days": int(ttl_days),
            "is_stale": bool(stale),
            "snapshot": None,
        }

        if snap:
            data["snapshot"] = {
                "training_intent": snap.training_intent,
                "next_event_date": snap.next_event_date.isoformat() if snap.next_event_date else None,
                "next_event_type": snap.next_event_type,
                "pain_flag": snap.pain_flag,
                "time_available_min": snap.time_available_min,
                "weekly_mileage_target": float(snap.weekly_mileage_target) if snap.weekly_mileage_target is not None else None,
                "what_feels_off": snap.what_feels_off,
                "updated_at": _iso(snap.updated_at) if snap.updated_at else None,
            }

        # --- Narrative ---
        if snap:
            ci_parts: List[str] = ["Athlete intent:"]
            if snap.training_intent:
                ci_parts.append(f"Intent: {snap.training_intent}.")
            if snap.next_event_date:
                ci_parts.append(f"Next event: {snap.next_event_type or 'race'} on {snap.next_event_date.isoformat()}.")
            if snap.pain_flag:
                ci_parts.append(f"Pain flag: {snap.pain_flag}.")
            if snap.weekly_mileage_target is not None:
                ci_parts.append(f"Weekly mileage target: {float(snap.weekly_mileage_target):.0f}.")
            if snap.what_feels_off:
                ci_parts.append(f"What feels off: {snap.what_feels_off}.")
            if stale:
                ci_parts.append("(Snapshot is stale — may need refresh.)")
            ci_narrative = " ".join(ci_parts)
        else:
            ci_narrative = "No athlete intent snapshot set yet."

        return {
            "ok": True,
            "tool": "get_coach_intent_snapshot",
            "generated_at": _iso(now),
            "narrative": ci_narrative,
            "data": data,
            "evidence": [
                {
                    "type": "derived",
                    "id": f"coach_intent_snapshot:{str(athlete_id)}",
                    "date": date.today().isoformat(),
                    "value": "Intent snapshot present" if snap else "No intent snapshot set yet",
                }
            ],
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "get_coach_intent_snapshot", "error": str(e)}


def set_coach_intent_snapshot(
    db: Session,
    athlete_id: UUID,
    *,
    training_intent: Optional[str] = None,
    next_event_date: Optional[str] = None,
    next_event_type: Optional[str] = None,
    pain_flag: Optional[str] = None,
    time_available_min: Optional[int] = None,
    weekly_mileage_target: Optional[float] = None,
    what_feels_off: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update the athlete's intent snapshot.

    NOTE: This is athlete-led state. It should be set from athlete responses.
    """
    now = datetime.utcnow()
    try:
        from models import CoachIntentSnapshot

        snap = _get_intent_snapshot(db, athlete_id)
        if not snap:
            snap = CoachIntentSnapshot(athlete_id=athlete_id)
            db.add(snap)

        if training_intent is not None:
            snap.training_intent = (training_intent or "").strip() or None

        if next_event_date is not None:
            try:
                snap.next_event_date = date.fromisoformat(next_event_date) if next_event_date else None
            except Exception:
                # Ignore invalid date; caller should validate.
                snap.next_event_date = None

        if next_event_type is not None:
            snap.next_event_type = (next_event_type or "").strip() or None

        if pain_flag is not None:
            snap.pain_flag = (pain_flag or "").strip().lower() or None

        if time_available_min is not None:
            try:
                snap.time_available_min = int(time_available_min)
            except Exception:
                snap.time_available_min = None

        if weekly_mileage_target is not None:
            try:
                snap.weekly_mileage_target = float(weekly_mileage_target)
            except Exception:
                snap.weekly_mileage_target = None

        if what_feels_off is not None:
            snap.what_feels_off = (what_feels_off or "").strip() or None

        db.commit()

        return get_coach_intent_snapshot(db, athlete_id)
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "set_coach_intent_snapshot", "error": str(e)}


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
    now = datetime.utcnow()
    try:
        days = max(1, min(int(days), 7))
        units = _preferred_units(db, athlete_id)

        # Resolve date window
        if start_date:
            try:
                start = date.fromisoformat(start_date)
            except Exception:
                start = date.today()
        else:
            start = date.today()
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
            today = date.today()
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
                d = a.start_time.date()
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
                    "date": date.today().isoformat(),
                    "value": f"Last 4 weeks volume (mi): {last4} (avg {recent_weekly_avg} mi/week)",
                }
            )
        evidence.append(
            {
                "type": "derived",
                "id": f"baseline:{str(athlete_id)}",
                "date": date.today().isoformat(),
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


def build_athlete_brief(db: Session, athlete_id: UUID) -> str:
    """
    ADR-16: Build a comprehensive pre-computed athlete brief.

    This is the coach's preparation — everything they should know before
    the conversation starts. Pre-computed facts, not raw data. The LLM
    reads this and coaches from it.

    Returns a human-readable multi-section string (~3000-4000 tokens).
    """
    today = date.today()
    sections: List[str] = []

    # ── 1. IDENTITY ──────────────────────────────────────────────────
    try:
        athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if athlete:
            lines = [f"Name: {athlete.display_name or 'Athlete'}"]
            if athlete.birthdate:
                age = (today - athlete.birthdate).days // 365
                lines.append(f"Age: {age}")
            if athlete.sex:
                lines.append(f"Sex: {athlete.sex}")
            lines.append(f"Units: {athlete.preferred_units or 'metric'}")
            sections.append("## Identity\n" + "\n".join(lines))
    except Exception as e:
        logger.debug(f"Brief: identity failed: {e}")

    # ── 2. GOAL RACE ─────────────────────────────────────────────────
    try:
        plan = (
            db.query(TrainingPlan)
            .filter(TrainingPlan.athlete_id == athlete_id, TrainingPlan.status == "active")
            .first()
        )
        if plan:
            lines = [f"Race: {plan.goal_race_name or plan.name}"]
            if plan.goal_race_date:
                days_until = (plan.goal_race_date - today).days
                lines.append(f"Date: {plan.goal_race_date.isoformat()} ({days_until} days away)")
            if plan.goal_race_distance_m:
                dist_mi = plan.goal_race_distance_m / _M_PER_MI
                lines.append(f"Distance: {dist_mi:.1f} miles ({plan.goal_race_distance_m}m)")
            if plan.goal_time_seconds:
                h = plan.goal_time_seconds // 3600
                m = (plan.goal_time_seconds % 3600) // 60
                s = plan.goal_time_seconds % 60
                lines.append(f"Target time: {h}:{m:02d}:{s:02d}")
                if plan.goal_race_distance_m and plan.goal_race_distance_m > 0:
                    goal_pace_sec = plan.goal_time_seconds / (plan.goal_race_distance_m / _M_PER_MI)
                    gp_m = int(goal_pace_sec // 60)
                    gp_s = int(round(goal_pace_sec % 60))
                    lines.append(f"Target pace: {gp_m}:{gp_s:02d}/mi")
            sections.append("## Goal Race\n" + "\n".join(lines))
    except Exception as e:
        logger.debug(f"Brief: goal race failed: {e}")

    # ── 3. TRAINING STATE ────────────────────────────────────────────
    try:
        load_data = get_training_load(db, athlete_id)
        if load_data.get("ok"):
            d = load_data["data"]
            ctl = d.get("ctl", "N/A")
            atl = d.get("atl", "N/A")
            tsb = d.get("tsb", "N/A")
            zone = d.get("tsb_zone", {})
            zone_label = zone.get("label", "")
            phase = d.get("training_phase", "")
            rec = d.get("recommendation", "")
            lines = [
                "(INTERNAL — use to reason about their state but NEVER quote these numbers to the athlete. Translate into plain coaching language.)",
                f"Chronic load (CTL): {ctl}",
                f"Acute load (ATL): {atl}",
                f"Balance (TSB): {tsb} — {zone_label}",
            ]
            if phase:
                lines.append(f"Phase: {phase}")
            if rec:
                lines.append(f"Recommendation: {rec}")
            sections.append("## Training State\n" + "\n".join(lines))
    except Exception as e:
        logger.debug(f"Brief: training state failed: {e}")

    # ── 4. RECOVERY & DURABILITY ─────────────────────────────────────
    try:
        recovery = get_recovery_status(db, athlete_id)
        if recovery.get("ok"):
            d = recovery["data"]
            lines = [
                "(INTERNAL — reason from these but translate into coaching language for the athlete.)",
                f"Recovery status: {d.get('status', 'unknown')}",
                f"Injury risk score: {d.get('injury_risk_score', 'N/A')}",
            ]
            if d.get("durability_index") is not None:
                lines.append(f"Durability index: {d['durability_index']}")
            if d.get("recovery_half_life_hours") is not None:
                lines.append(f"Recovery half-life: {d['recovery_half_life_hours']:.1f}h")
            sections.append("## Recovery & Durability\n" + "\n".join(lines))
    except Exception as e:
        logger.debug(f"Brief: recovery failed: {e}")

    # ── 5. VOLUME TRAJECTORY ─────────────────────────────────────────
    try:
        weekly = get_weekly_volume(db, athlete_id, weeks=8)
        if weekly.get("ok"):
            weeks_data = weekly.get("data", {}).get("weeks_data", weekly.get("data", {}).get("weeks", []))
            if weeks_data:
                lines = []
                completed_weeks = []
                current_week_info = None
                for w in weeks_data:
                    dist = w.get("total_distance_mi", 0)
                    runs = w.get("run_count", 0)
                    if w.get("is_current_week"):
                        elapsed = w.get("days_elapsed", "?")
                        remaining = w.get("days_remaining", "?")
                        current_week_info = f"Current week: {dist:.1f}mi through {elapsed} of 7 days ({runs} runs, {remaining} days remaining)"
                    else:
                        completed_weeks.append((w.get("week_start", ""), dist, runs))

                # Show trajectory
                if completed_weeks:
                    recent = completed_weeks[-4:]  # last 4 completed weeks
                    trajectory = " → ".join(f"{d:.0f}" for _, d, _ in recent)
                    lines.append(f"Recent completed weeks (mi): {trajectory}")
                    if len(recent) >= 2:
                        first_val = recent[0][1]
                        last_val = recent[-1][1]
                        if first_val > 0:
                            pct_change = ((last_val - first_val) / first_val) * 100
                            direction = "up" if pct_change > 0 else "down"
                            lines.append(f"Trend: {direction} {abs(pct_change):.0f}% over {len(recent)} weeks")
                    # Peak volume
                    peak = max(completed_weeks, key=lambda x: x[1])
                    lines.append(f"Peak week: {peak[1]:.1f}mi (week of {peak[0]})")
                    if last_val > 0 and peak[1] > 0:
                        pct_of_peak = (last_val / peak[1]) * 100
                        lines.append(f"Current vs peak: {pct_of_peak:.0f}%")

                if current_week_info:
                    lines.append(current_week_info)

                sections.append("## Volume Trajectory\n" + "\n".join(lines))
    except Exception as e:
        logger.debug(f"Brief: volume trajectory failed: {e}")

    # ── 6. RECENT RUNS ───────────────────────────────────────────────
    try:
        recent = get_recent_runs(db, athlete_id, days=14)
        if recent.get("ok"):
            runs = recent.get("data", {}).get("runs", [])
            if runs:
                lines = [f"Last {len(runs)} runs (14 days):"]
                for run in runs[:10]:  # cap at 10
                    run_date = (run.get("start_time") or "")[:10]
                    name = run.get("name", "Run")
                    dist = run.get("distance_mi", 0)
                    pace = run.get("pace_per_mile", "N/A")
                    hr = run.get("avg_hr", "")
                    hr_str = f" | HR {hr}" if hr else ""
                    lines.append(f"  {run_date}: {name} — {dist:.1f}mi @ {pace}{hr_str}")
                sections.append("## Recent Runs\n" + "\n".join(lines))
    except Exception as e:
        logger.debug(f"Brief: recent runs failed: {e}")

    # ── 7. RACE PREDICTIONS ──────────────────────────────────────────
    try:
        preds = get_race_predictions(db, athlete_id)
        if preds.get("ok"):
            pred_data = preds.get("data", {}).get("predictions", {})
            if pred_data:
                lines = []
                for dist_name in ["5K", "10K", "Half Marathon", "Marathon"]:
                    p = pred_data.get(dist_name, {})
                    pred_info = p.get("prediction", {})
                    time_fmt = pred_info.get("time_formatted")
                    confidence = pred_info.get("confidence", "")
                    if time_fmt:
                        lines.append(f"  {dist_name}: {time_fmt} ({confidence} confidence)")
                if lines:
                    sections.append("## Race Predictions\n" + "\n".join(lines))
    except Exception as e:
        logger.debug(f"Brief: race predictions failed: {e}")

    # ── 8. TRAINING PACES ────────────────────────────────────────────
    try:
        paces = get_training_paces(db, athlete_id)
        if paces.get("ok"):
            d = paces["data"]
            pace_data = d.get("paces", {})
            rpi = d.get("rpi", "N/A")
            lines = [f"RPI (Running Performance Index): {rpi}"]
            for zone_name in ["easy", "marathon", "threshold", "interval", "repetition"]:
                val = pace_data.get(zone_name, "N/A")
                lines.append(f"  {zone_name.capitalize()}: {val}")
            sections.append("## Training Paces\n" + "\n".join(lines))
    except Exception as e:
        logger.debug(f"Brief: training paces failed: {e}")

    # ── 9. KEY PERSONAL BESTS ────────────────────────────────────────
    try:
        pbs = get_pb_patterns(db, athlete_id)
        if pbs.get("ok"):
            pb_list = pbs.get("data", {}).get("pbs", [])
            if pb_list:
                lines = []
                for pb in pb_list[:5]:
                    cat = pb.get("category", pb.get("distance_category", ""))
                    dist_km = pb.get("distance_km", "")
                    time_min = pb.get("time_min", "")
                    pb_date = (pb.get("date") or "")[:10]
                    if dist_km and time_min:
                        lines.append(f"  {cat}: {time_min:.1f}min / {dist_km:.1f}km ({pb_date})")
                if lines:
                    sections.append("## Personal Bests\n" + "\n".join(lines))
    except Exception as e:
        logger.debug(f"Brief: personal bests failed: {e}")

    # ── 10. N-OF-1 INSIGHTS (Correlations) ───────────────────────────
    try:
        corr = get_correlations(db, athlete_id, days=90)
        if corr.get("ok"):
            corr_data = corr.get("data", {})
            correlations = corr_data.get("correlations", []) if isinstance(corr_data, dict) else []
            if isinstance(correlations, list) and correlations:
                lines = []
                for c in correlations[:5]:
                    input_name = c.get("input_name", "?")
                    output_name = c.get("output_name", "?")
                    r = c.get("correlation_coefficient", 0)
                    n = c.get("sample_size", 0)
                    direction = "positively" if r > 0 else "inversely"
                    lines.append(
                        f"  {input_name} {direction} correlates with {output_name} "
                        f"(r={r:.2f}, n={n})"
                    )
                if lines:
                    sections.append("## N-of-1 Insights (Correlations)\n" + "\n".join(lines))
    except Exception as e:
        logger.debug(f"Brief: correlations failed: {e}")

    # ── 11. EFFICIENCY TREND ─────────────────────────────────────────
    try:
        eff = get_efficiency_trend(db, athlete_id, days=60)
        if eff.get("ok"):
            d = eff.get("data", {})
            if d:
                lines = []
                trend = d.get("trend_direction", "")
                avg_ef = d.get("average_ef")
                best_ef = d.get("best_ef")
                if trend:
                    lines.append(f"Trend: {trend}")
                if avg_ef:
                    lines.append(f"Average EF (60 days): {avg_ef}")
                if best_ef:
                    lines.append(f"Best recent EF: {best_ef}")
                if lines:
                    sections.append("## Efficiency Trend\n" + "\n".join(lines))
    except Exception as e:
        logger.debug(f"Brief: efficiency trend failed: {e}")

    # ── 12. INTENT & CHECK-IN ────────────────────────────────────────
    try:
        intent = get_coach_intent_snapshot(db, athlete_id)
        if intent.get("ok"):
            d = intent.get("data", {})
            lines = []
            if d.get("training_intent"):
                lines.append(f"Training intent: {d['training_intent']}")
            if d.get("pain_flag") and d["pain_flag"] != "none":
                lines.append(f"Pain flag: {d['pain_flag']}")
            if d.get("weekly_mileage_target"):
                lines.append(f"Weekly mileage target: {d['weekly_mileage_target']}")
            if d.get("next_event_date"):
                lines.append(f"Next event: {d['next_event_date']} ({d.get('next_event_type', '')})")
            if lines:
                sections.append("## Athlete Intent\n" + "\n".join(lines))
    except Exception as e:
        logger.debug(f"Brief: intent failed: {e}")

    try:
        from models import DailyCheckin
        checkin = (
            db.query(DailyCheckin)
            .filter(DailyCheckin.athlete_id == athlete_id)
            .order_by(DailyCheckin.date.desc())
            .first()
        )
        if checkin:
            lines = [f"Date: {checkin.date}"]
            if checkin.sleep_h is not None:
                lines.append(f"Sleep: {checkin.sleep_h}h")
            if checkin.motivation_1_5 is not None:
                motivation_map = {5: 'Great', 4: 'Fine', 2: 'Tired', 1: 'Rough'}
                lines.append(f"Feeling: {motivation_map.get(checkin.motivation_1_5, checkin.motivation_1_5)}")
            if checkin.soreness_1_5 is not None:
                soreness_map = {1: 'None', 2: 'Mild', 4: 'Yes'}
                lines.append(f"Soreness: {soreness_map.get(checkin.soreness_1_5, checkin.soreness_1_5)}/5")
            if checkin.stress_1_5 is not None:
                lines.append(f"Stress: {checkin.stress_1_5}/5")
            if checkin.notes:
                lines.append(f"Notes: {checkin.notes[:150]}")
            sections.append("## Latest Check-in\n" + "\n".join(lines))
    except Exception as e:
        logger.debug(f"Brief: checkin failed: {e}")

    if not sections:
        return "(No athlete data available)"

    return "\n\n".join(sections)


def compute_running_math(
    db: Session,
    athlete_id: UUID,
    pace_per_mile: str = "",
    pace_per_km: str = "",
    distance_miles: float = 0.0,
    distance_km: float = 0.0,
    time_seconds: int = 0,
    operation: str = "pace_to_finish",
) -> Dict[str, Any]:
    """
    General-purpose running math calculator. The LLM calls this instead of
    doing arithmetic.

    Operations:
      pace_to_finish  — given pace + distance, compute finish time
      finish_to_pace  — given finish time + distance, compute required pace
      split_calc      — given two split paces + half distance each, compute total

    Accepts either imperial (miles) or metric (km). Returns both.
    """
    now = datetime.utcnow()

    def _parse_pace(pace_str: str) -> Optional[float]:
        """Parse 'M:SS' or 'M:SS/mi' or 'M:SS/km' into seconds."""
        if not pace_str:
            return None
        cleaned = re.sub(r"/(mi|km|mile|k)\s*$", "", pace_str.strip())
        parts = cleaned.split(":")
        try:
            if len(parts) == 2:
                return int(parts[0]) * 60 + float(parts[1])
            elif len(parts) == 1:
                return float(parts[0])
        except (ValueError, TypeError):
            return None
        return None

    def _fmt_time(total_seconds: float) -> str:
        """Format seconds as H:MM:SS or M:SS."""
        total_seconds = round(total_seconds)
        h = int(total_seconds // 3600)
        m = int((total_seconds % 3600) // 60)
        s = int(total_seconds % 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    def _fmt_pace(seconds_per_unit: float) -> str:
        m = int(seconds_per_unit // 60)
        s = int(round(seconds_per_unit % 60))
        return f"{m}:{s:02d}"

    try:
        # Normalize distance to miles and km
        dist_mi = distance_miles or (distance_km / 1.60934 if distance_km else 0.0)
        dist_km = distance_km or (distance_miles * 1.60934 if distance_miles else 0.0)

        result: Dict[str, Any] = {"operation": operation}

        if operation == "pace_to_finish":
            pace_sec = _parse_pace(pace_per_mile)
            unit = "mi"
            dist = dist_mi
            if not pace_sec and pace_per_km:
                pace_sec = _parse_pace(pace_per_km)
                unit = "km"
                dist = dist_km
            if not pace_sec or dist <= 0:
                return {"ok": False, "tool": "compute_running_math",
                        "error": "Need a pace and distance to compute finish time."}
            if unit == "km":
                finish_sec = pace_sec * dist_km
                pace_per_mi_sec = pace_sec * 1.60934
            else:
                finish_sec = pace_sec * dist_mi
                pace_per_mi_sec = pace_sec
            pace_per_km_sec = pace_per_mi_sec / 1.60934
            result.update({
                "finish_time": _fmt_time(finish_sec),
                "finish_time_seconds": round(finish_sec),
                "pace_per_mile": _fmt_pace(pace_per_mi_sec) + "/mi",
                "pace_per_km": _fmt_pace(pace_per_km_sec) + "/km",
                "distance_miles": round(dist_mi, 2),
                "distance_km": round(dist_km, 2),
            })

        elif operation == "finish_to_pace":
            if not time_seconds or (dist_mi <= 0 and dist_km <= 0):
                return {"ok": False, "tool": "compute_running_math",
                        "error": "Need a finish time and distance to compute pace."}
            pace_mi = time_seconds / dist_mi if dist_mi > 0 else 0
            pace_km = time_seconds / dist_km if dist_km > 0 else 0
            result.update({
                "finish_time": _fmt_time(time_seconds),
                "pace_per_mile": _fmt_pace(pace_mi) + "/mi",
                "pace_per_km": _fmt_pace(pace_km) + "/km",
                "distance_miles": round(dist_mi, 2),
                "distance_km": round(dist_km, 2),
            })

        elif operation == "split_calc":
            # For split calculations, pace_per_mile = first half pace, pace_per_km = second half pace
            # (repurposing fields) or pass as "7:30,7:00" in pace_per_mile
            paces = pace_per_mile.split(",") if "," in pace_per_mile else [pace_per_mile, pace_per_km]
            p1 = _parse_pace(paces[0].strip() if len(paces) > 0 else "")
            p2 = _parse_pace(paces[1].strip() if len(paces) > 1 else "")
            if not p1 or not p2 or dist_mi <= 0:
                return {"ok": False, "tool": "compute_running_math",
                        "error": "Need two split paces and total distance."}
            half_dist = dist_mi / 2.0
            total_sec = (p1 * half_dist) + (p2 * half_dist)
            avg_pace = total_sec / dist_mi
            result.update({
                "first_half_pace": _fmt_pace(p1) + "/mi",
                "second_half_pace": _fmt_pace(p2) + "/mi",
                "average_pace": _fmt_pace(avg_pace) + "/mi",
                "finish_time": _fmt_time(total_sec),
                "finish_time_seconds": round(total_sec),
                "distance_miles": round(dist_mi, 2),
                "negative_split_seconds": round(p1 * half_dist - p2 * half_dist),
            })
        else:
            return {"ok": False, "tool": "compute_running_math",
                    "error": f"Unknown operation: {operation}. Use pace_to_finish, finish_to_pace, or split_calc."}

        # --- Narrative ---
        if operation == "pace_to_finish":
            math_narr = (
                f"At {result.get('pace_per_mile', '?')} pace over {result.get('distance_miles', '?')} miles: "
                f"finish time is {result.get('finish_time', '?')}."
            )
        elif operation == "finish_to_pace":
            math_narr = (
                f"To finish {result.get('distance_miles', '?')} miles in {result.get('finish_time', '?')}: "
                f"required pace is {result.get('pace_per_mile', '?')}."
            )
        elif operation == "split_calc":
            math_narr = (
                f"Split calculation over {result.get('distance_miles', '?')} miles: "
                f"first half at {result.get('first_half_pace', '?')}, "
                f"second half at {result.get('second_half_pace', '?')}, "
                f"finish time {result.get('finish_time', '?')}."
            )
        else:
            math_narr = f"Running math result: {result}"

        return {
            "ok": True,
            "tool": "compute_running_math",
            "generated_at": _iso(now),
            "narrative": math_narr,
            "data": result,
            "evidence": [{
                "type": "derived",
                "id": f"running_math:{operation}",
                "date": _iso(now)[:10],
                "value": f"{operation}: {result.get('finish_time', result.get('pace_per_mile', 'computed'))}",
            }],
        }
    except Exception as e:
        return {"ok": False, "tool": "compute_running_math", "error": str(e)}


def _guardrails_from_pain(pain_flag: str) -> List[str]:
    if pain_flag == "pain":
        return [
            "Stop condition: pain while running => do not run; consult a clinician if it persists.",
            "No intensity. No 'push through'.",
        ]
    if pain_flag == "niggle":
        return [
            "Stop condition: pain increases or alters gait => stop.",
            "Keep intensity easy; skip quality if it feels off.",
            "No ramp jumps this week.",
        ]
    return [
        "Stop condition: sharp pain or gait change => stop.",
        "Keep easy days easy; quality stays inside prescription.",
    ]

