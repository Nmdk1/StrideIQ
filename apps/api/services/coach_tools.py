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
    days = max(1, min(int(days), 365))
    cutoff = now - timedelta(days=days)

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
        pace = _pace_str(a.duration_s, a.distance_m)
        date_str = a.start_time.date().isoformat()

        run_rows.append(
            {
                "activity_id": str(a.id),
                "start_time": _iso(a.start_time),
                "name": a.name,
                "distance_m": int(a.distance_m) if a.distance_m is not None else None,
                "duration_s": int(a.duration_s) if a.duration_s is not None else None,
                "avg_hr": int(a.avg_hr) if a.avg_hr is not None else None,
                "pace_per_km": _pace_str(a.duration_s, a.distance_m),
                "workout_type": a.workout_type,
                "intensity_score": float(a.intensity_score) if a.intensity_score is not None else None,
            }
        )

        parts: List[str] = []
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
            "run_count": len(runs),
            "total_distance_km": round(total_distance_m / 1000.0, 2),
            "total_duration_min": round(total_duration_s / 60.0, 1),
            "runs": run_rows,
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
                # use the athlete's stored VDOT (if available) to provide a reasonable estimate.
                msg = str(e)
                if athlete and getattr(athlete, "vdot", None) and "athlete_calibrated_model" in msg:
                    seconds = calculate_race_time_from_vdot(float(athlete.vdot), dist_m)
                    if seconds:
                        predictions[label] = {
                            "prediction": {
                                "time_seconds": int(seconds),
                                "time_formatted": _fmt_time(int(seconds)),
                                "confidence_interval_seconds": None,
                                "confidence_interval_formatted": None,
                                "confidence": "vdot_fallback",
                            },
                            "projections": {"vdot": round(float(athlete.vdot), 1), "ctl": None, "tsb": None},
                            "factors": ["Athlete.vdot fallback (no calibrated model available)"],
                            "notes": ["This estimate is less personalized than the calibrated model pipeline."],
                        }
                    else:
                        predictions[label] = {"error": msg}
                else:
                    predictions[label] = {"error": msg}

        return {
            "ok": True,
            "tool": "get_race_predictions",
            "generated_at": _iso(now),
            "data": {
                "race_date": race_date.isoformat(),
                "predictions": predictions,
            },
            "evidence": [
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
    """
    now = datetime.utcnow()
    try:
        start = now - timedelta(days=365)
        result = aggregate_pre_pb_state(str(athlete_id), start, now, db)

        return {
            "ok": True,
            "tool": "get_pb_patterns",
            "generated_at": _iso(now),
            "data": result,
            "evidence": [
                {
                    "type": "derived",
                    "id": f"pb_patterns:{str(athlete_id)}",
                    "date": date.today().isoformat(),
                    "value": (
                        f"{(result or {}).get('pb_count', 0)} PBs analyzed, optimal TSB range: {(result or {}).get('optimal_tsb_range')}"
                    ),
                }
            ],
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
            "evidence": [
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

