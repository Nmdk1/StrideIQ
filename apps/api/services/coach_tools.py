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

from datetime import datetime, timedelta, date
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
from services.vdot_calculator import calculate_race_time_from_vdot


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
                "pace_per_km": _pace_str(a.duration_s, a.distance_m),
                "pace_per_mile": pace_mi,
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
            if pace_mi:
                parts.append(f"@ {pace_mi}")
        else:
            if distance_km is not None:
                parts.append(f"{distance_km:.1f} km")
            if pace:
                parts.append(f"@ {pace}")
        if a.avg_hr is not None:
            parts.append(f"(avg HR {int(a.avg_hr)} bpm)")
        if a.workout_type:
            parts.append(f"[{a.workout_type}]")
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

    return {
        "ok": True,
        "tool": "get_recent_runs",
        "generated_at": _iso(now),
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

    return {
        "ok": True,
        "tool": "get_calendar_day_context",
        "generated_at": _iso(now),
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
                # Lower EF is better in the main analytics implementation.
                if late_avg < early_avg:
                    trend_direction = "improving"
                elif late_avg > early_avg:
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
                    "best_efficiency": round(min(efficiencies), 2) if efficiencies else None,
                    "worst_efficiency": round(max(efficiencies), 2) if efficiencies else None,
                    "trend_direction": trend_direction,
                    "trend_magnitude": trend_magnitude,
                    "note": "Derived EF fallback (pace_per_mile + avg_hr). Lower EF is better.",
                },
                "trend_analysis": {
                    "method": "fallback_basic",
                    "slope_per_week": None,
                    "p_value": None,
                    "r_squared": None,
                },
                "time_series": trimmed_series,
            }

    evidence: List[Dict[str, Any]] = []
    if isinstance(trimmed_series, list):
        for p in trimmed_series:
            if isinstance(p, dict) and p.get("activity_id") and p.get("date"):
                # date field in efficiency_analytics is ISO datetime string
                date_str = str(p.get("date"))[:10]
                ef = p.get("efficiency_factor")
                pace = p.get("pace_per_mile")
                avg_hr = p.get("avg_hr")
                ef_part = f"EF {ef}" if ef is not None else "EF n/a"
                extras: List[str] = []
                if pace is not None:
                    extras.append(f"pace {pace} min/mi")
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

    return {
        "ok": True,
        "tool": "get_efficiency_trend",
        "generated_at": _iso(now),
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

    return {
        "ok": True,
        "tool": "get_plan_week",
        "generated_at": _iso(datetime.utcnow()),
        "data": {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "plan": (
                {
                    "plan_id": str(plan.id),
                    "name": plan.name,
                    "goal_race_name": plan.goal_race_name,
                    "goal_race_date": plan.goal_race_date.isoformat() if plan.goal_race_date else None,
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

    return {
        "ok": True,
        "tool": "get_training_load",
        "generated_at": _iso(now),
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

    return {
        "ok": True,
        "tool": "get_correlations",
        "generated_at": _iso(now),
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

        def _best_vdot_from_personal_bests() -> Optional[Dict[str, Any]]:
            """
            Derive a VDOT estimate from the athlete's PersonalBest table.

            Returns:
                {"vdot": float, "pb": PersonalBest} or None
            """
            try:
                from models import PersonalBest
                from services.vdot_calculator import calculate_vdot_from_race_time

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
                    v = calculate_vdot_from_race_time(pb.distance_meters, pb.time_seconds)
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

                # Remove weight for reporting a clean VDOT value.
                base_vdot = float(best_weighted)
                if getattr(best_pb, "is_race", False):
                    base_vdot -= 0.3
                if best_pb.distance_category in {"5k", "10k", "half_marathon", "marathon"}:
                    base_vdot -= 0.2

                return {"vdot": round(base_vdot, 1), "pb": best_pb}
            except Exception:
                return None

        pb_vdot = _best_vdot_from_personal_bests()
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
                # use the athlete's stored VDOT or derive one from PBs to provide a reasonable estimate.
                msg = str(e)
                fallback_vdot: Optional[float] = None
                fallback_source: Optional[str] = None

                if athlete and getattr(athlete, "vdot", None):
                    fallback_vdot = float(athlete.vdot)
                    fallback_source = "athlete_vdot"
                elif pb_vdot and pb_vdot.get("vdot"):
                    fallback_vdot = float(pb_vdot["vdot"])
                    fallback_source = "pb_vdot"

                if fallback_vdot and "athlete_calibrated_model" in msg:
                    seconds = calculate_race_time_from_vdot(float(fallback_vdot), dist_m)
                    if seconds:
                        predictions[label] = {
                            "prediction": {
                                "time_seconds": int(seconds),
                                "time_formatted": _fmt_time(int(seconds)),
                                "confidence_interval_seconds": None,
                                "confidence_interval_formatted": None,
                                "confidence": f"{fallback_source}_fallback",
                            },
                            "projections": {"vdot": round(float(fallback_vdot), 1), "ctl": None, "tsb": None},
                            "factors": [
                                "Calibrated performance model unavailable; using VDOT-derived equivalent times.",
                                f"VDOT source: {fallback_source}",
                            ],
                            "notes": ["This estimate is less personalized than the calibrated model pipeline."],
                        }
                    else:
                        predictions[label] = {"error": msg}
                else:
                    predictions[label] = {"error": msg}

        # Evidence: cite the PB used for fallback (if any), plus a derived marker.
        if pb_vdot and pb_vdot.get("pb"):
            pb = pb_vdot["pb"]
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

        return {
            "ok": True,
            "tool": "get_race_predictions",
            "generated_at": _iso(now),
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

        return {
            "ok": True,
            "tool": "get_recovery_status",
            "generated_at": _iso(now),
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

        return {
            "ok": True,
            "tool": "get_active_insights",
            "generated_at": _iso(now),
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

        return {
            "ok": True,
            "tool": "get_pb_patterns",
            "generated_at": _iso(now),
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

        return {
            "ok": True,
            "tool": "get_efficiency_by_zone",
            "generated_at": _iso(now),
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

        return {
            "ok": True,
            "tool": "get_nutrition_correlations",
            "generated_at": _iso(now),
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

        week_rows: List[Dict[str, Any]] = []
        for key in sorted(buckets.keys()):
            b = buckets[key]
            dist_m = float(b["total_distance_m"])
            dur_s = float(b["total_duration_s"])
            week_rows.append(
                {
                    "week_start": b["week_start"],
                    "week_end": b["week_end"],
                    "run_count": int(b["run_count"]),
                    "total_distance_km": round(dist_m / 1000.0, 2),
                    "total_distance_mi": round(dist_m / _M_PER_MI, 2),
                    "total_duration_hr": round(dur_s / 3600.0, 2),
                }
            )

        # Evidence: cite the top 3 weeks by distance in preferred units
        def _week_magnitude(wr: Dict[str, Any]) -> float:
            return float(wr.get("total_distance_mi" if units == "imperial" else "total_distance_km") or 0)

        top_weeks = sorted(week_rows, key=_week_magnitude, reverse=True)[:3]
        evidence: List[Dict[str, Any]] = []
        for w in top_weeks:
            dist = w["total_distance_mi"] if units == "imperial" else w["total_distance_km"]
            unit = "mi" if units == "imperial" else "km"
            evidence.append(
                {
                    "type": "derived",
                    "id": f"weekly_volume:{str(athlete_id)}:{w['week_start']}",
                    "date": w["week_start"],
                    "value": f"Week of {w['week_start']}: {dist:.1f} {unit} across {w['run_count']} runs",
                }
            )

        return {
            "ok": True,
            "tool": "get_weekly_volume",
            "generated_at": _iso(now),
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
      - efficiency: lowest Pace(sec/km)/HR(bpm) (lower = better)
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
            eff = (pace_s_per_km / float(a.avg_hr)) if a.avg_hr else None

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
                    "efficiency_sec_per_km_per_bpm": round(eff, 6) if eff is not None else None,
                }
            )

        def _score(r: Dict[str, Any]) -> float:
            if metric == "efficiency":
                v = r.get("efficiency_sec_per_km_per_bpm")
                return float(v) if v is not None else 1e9  # lower is better
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
            if metric == "efficiency" and r.get("efficiency_sec_per_km_per_bpm") is not None:
                parts.append(f"[eff {r['efficiency_sec_per_km_per_bpm']:.6f}]")
            evidence.append(
                {
                    "type": "activity",
                    "id": r["activity_id"],
                    "ref": r["activity_id"][:8],
                    "date": r["date"],
                    "value": " ".join(parts),
                }
            )

        return {
            "ok": True,
            "tool": "get_best_runs",
            "generated_at": _iso(now),
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

        return {
            "ok": True,
            "tool": "compare_training_periods",
            "generated_at": _iso(now),
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

