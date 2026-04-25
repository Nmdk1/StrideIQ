from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from models import (
    Activity,
    Athlete,
    AthleteFact,
    AthleteRaceResultAnchor,
    PerformanceEvent,
    PersonalBest,
    PlannedWorkout,
    TrainingPlan,
)
from services.coach_tools._utils import _M_PER_MI, _iso, _mi_from_m, _pace_str_mi
from services.coach_tools.training_block import activity_row_with_training_structure


_RACE_MEMORY_TYPES = {
    "race_psychology",
    "injury_context",
    "invalid_race_anchor",
    "training_intent",
    "fatigue_strategy",
    "sleep_baseline",
    "stress_boundary",
    "coaching_preference",
    "strength_training_context",
}

_DISTANCE_ALIASES = {
    "5k": 5000,
    "5 k": 5000,
    "10k": 10000,
    "10 k": 10000,
    "half": 21097,
    "half marathon": 21097,
    "marathon": 42195,
    "mile": 1609,
}


def _fmt_time(seconds: Optional[int]) -> Optional[str]:
    if seconds is None:
        return None
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _parse_date(value: str) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except Exception:
        return None


def _distance_m_from_text(value: str) -> Optional[int]:
    text = (value or "").strip().lower().replace("-", " ")
    if not text:
        return None
    for alias, meters in _DISTANCE_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", text):
            return meters
    return None


def _infer_distance_m(race_distance: str, race_name: str, plan: Optional[TrainingPlan]) -> Optional[int]:
    explicit = _distance_m_from_text(race_distance) or _distance_m_from_text(race_name)
    if explicit:
        return explicit
    if plan and plan.goal_race_distance_m:
        return int(plan.goal_race_distance_m)
    return None


def _pace_for_activity(activity: Activity) -> Optional[str]:
    return _pace_str_mi(activity.duration_s, activity.distance_m)


def _activity_row(activity: Activity) -> Dict[str, Any]:
    distance_m = int(activity.distance_m) if activity.distance_m is not None else None
    return {
        "activity_id": str(activity.id),
        "name": activity.name,
        "date": _iso(activity.start_time)[:10] if activity.start_time else None,
        "distance_m": distance_m,
        "distance_mi": round(_mi_from_m(activity.distance_m), 2) if activity.distance_m is not None else None,
        "duration_s": int(activity.duration_s) if activity.duration_s is not None else None,
        "time": _fmt_time(activity.duration_s),
        "pace_per_mile": _pace_for_activity(activity),
        "workout_type": activity.workout_type,
        "is_race": bool(activity.user_verified_race or activity.is_race_candidate or activity.workout_type == "race"),
        "avg_hr": int(activity.avg_hr) if activity.avg_hr is not None else None,
        "max_hr": int(activity.max_hr) if activity.max_hr is not None else None,
        "elevation_gain_m": (
            round(float(activity.total_elevation_gain), 1)
            if activity.total_elevation_gain is not None
            else None
        ),
        "weather": {
            "temperature_f": round(float(activity.temperature_f), 1) if activity.temperature_f is not None else None,
            "humidity_pct": round(float(activity.humidity_pct), 0) if activity.humidity_pct is not None else None,
            "condition": activity.weather_condition,
            "dew_point_f": round(float(activity.dew_point_f), 1) if activity.dew_point_f is not None else None,
        },
        "shape_sentence": activity.shape_sentence,
        "route_id": str(activity.route_id) if getattr(activity, "route_id", None) else None,
    }


def _active_plan(db: Session, athlete_id: UUID) -> Optional[TrainingPlan]:
    return (
        db.query(TrainingPlan)
        .filter(TrainingPlan.athlete_id == athlete_id, TrainingPlan.status == "active")
        .order_by(TrainingPlan.created_at.desc().nullslast())
        .first()
    )


def _plan_week(db: Session, athlete_id: UUID, plan: Optional[TrainingPlan]) -> Dict[str, Any]:
    if not plan:
        return {"plan": None, "workouts": []}
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
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
    return {
        "plan": {
            "plan_id": str(plan.id),
            "name": plan.name,
            "goal_race_name": plan.goal_race_name,
            "goal_race_date": plan.goal_race_date.isoformat() if plan.goal_race_date else None,
            "goal_race_distance_m": plan.goal_race_distance_m,
            "goal_time_seconds": plan.goal_time_seconds,
            "goal_time": _fmt_time(plan.goal_time_seconds),
            "total_weeks": plan.total_weeks,
        },
        "workouts": [
            {
                "planned_workout_id": str(workout.id),
                "scheduled_date": workout.scheduled_date.isoformat(),
                "title": workout.title,
                "workout_type": workout.workout_type,
                "workout_subtype": workout.workout_subtype,
                "completed": bool(workout.completed),
                "skipped": bool(workout.skipped),
                "target_distance_km": (
                    float(workout.target_distance_km)
                    if workout.target_distance_km is not None
                    else None
                ),
            }
            for workout in workouts
        ],
    }


def _target_race(
    *,
    race_name: str,
    race_date: str,
    race_distance: str,
    plan: Optional[TrainingPlan],
) -> Dict[str, Any]:
    name = (race_name or "").strip() or (plan.goal_race_name if plan else None)
    target_date = _parse_date(race_date) or (plan.goal_race_date if plan else None)
    distance_m = _infer_distance_m(race_distance, name or "", plan)
    goal_time_seconds = int(plan.goal_time_seconds) if plan and plan.goal_time_seconds else None
    days_until = (target_date - date.today()).days if target_date else None
    return {
        "name": name,
        "date": target_date.isoformat() if target_date else None,
        "days_until": days_until,
        "distance_m": distance_m,
        "distance_mi": round(distance_m / _M_PER_MI, 2) if distance_m else None,
        "goal_time_seconds": goal_time_seconds,
        "goal_time": _fmt_time(goal_time_seconds),
        "goal_pace_per_mile": (
            _fmt_time(int(goal_time_seconds / (distance_m / _M_PER_MI)))
            if goal_time_seconds and distance_m
            else None
        ),
        "source": "request" if race_name or race_date or race_distance else ("active_plan" if plan else "unknown"),
    }


def _name_tokens(name: str) -> List[str]:
    tokens = re.findall(r"[a-z0-9]+", (name or "").lower())
    stop = {"the", "a", "an", "race", "run", "road", "classic"}
    return [token for token in tokens if len(token) > 2 and token not in stop]


def _prior_course_candidates(
    db: Session,
    athlete_id: UUID,
    target: Dict[str, Any],
    limit: int = 5,
) -> List[Activity]:
    filters = [Activity.athlete_id == athlete_id, Activity.sport == "run"]
    name = target.get("name") or ""
    tokens = _name_tokens(name)
    distance_m = target.get("distance_m")

    query = db.query(Activity).filter(*filters)
    if tokens:
        query = query.filter(or_(*[Activity.name.ilike(f"%{token}%") for token in tokens]))
    elif distance_m:
        query = query.filter(
            Activity.distance_m >= int(distance_m * 0.85),
            Activity.distance_m <= int(distance_m * 1.15),
            or_(
                Activity.user_verified_race.is_(True),
                Activity.is_race_candidate.is_(True),
                Activity.workout_type == "race",
            ),
        )
    else:
        return []

    return (
        query.order_by(
            Activity.user_verified_race.desc().nullslast(),
            Activity.is_race_candidate.desc().nullslast(),
            Activity.start_time.desc().nullslast(),
        )
        .limit(limit)
        .all()
    )


def _same_route_activities(db: Session, athlete_id: UUID, prior: Optional[Activity]) -> List[Dict[str, Any]]:
    if not prior or not getattr(prior, "route_id", None):
        return []
    matches = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.route_id == prior.route_id,
            Activity.id != prior.id,
        )
        .order_by(Activity.start_time.desc().nullslast())
        .limit(5)
        .all()
    )
    return [_activity_row(activity) for activity in matches]


def _recent_relevant_workouts(
    db: Session,
    athlete_id: UUID,
    *,
    distance_m: Optional[int],
    lookback_days: int,
) -> List[Dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    activities = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.sport == "run",
            Activity.start_time >= cutoff,
        )
        .order_by(Activity.start_time.desc().nullslast())
        .limit(80)
        .all()
    )
    keywords = ("race", "5k", "10k", "mile", "tempo", "threshold", "interval", "repeat", "workout", "progression")
    rows: List[Dict[str, Any]] = []
    for activity in activities:
        label = f"{activity.name or ''} {activity.workout_type or ''}".lower()
        distance_ok = bool(
            distance_m
            and activity.distance_m
            and 0.8 * distance_m <= activity.distance_m <= max(distance_m * 4.0, distance_m + 5000)
        )
        keyword_ok = any(token in label for token in keywords)
        row = activity_row_with_training_structure(
            db,
            activity,
            race_distance_m=distance_m,
        )
        quality_ok = bool((row.get("quality_rank") or 0) > 0)
        if not (distance_ok or keyword_ok or quality_ok):
            continue
        if distance_ok and not quality_ok:
            row["quality_rank"] = 10
            row["selection_reason"] = "broad_distance_match"
        rows.append(row)
    rows.sort(
        key=lambda row: (
            row.get("quality_rank") or 0,
            row.get("date") or "",
        ),
        reverse=True,
    )
    return rows[:15]


def _race_history(db: Session, athlete_id: UUID) -> Dict[str, Any]:
    pbs = (
        db.query(PersonalBest)
        .filter(PersonalBest.athlete_id == athlete_id)
        .order_by(PersonalBest.achieved_at.desc().nullslast())
        .limit(8)
        .all()
    )
    events = (
        db.query(PerformanceEvent)
        .filter(PerformanceEvent.athlete_id == athlete_id)
        .order_by(PerformanceEvent.event_date.desc().nullslast())
        .limit(8)
        .all()
    )
    anchors = (
        db.query(AthleteRaceResultAnchor)
        .filter(AthleteRaceResultAnchor.athlete_id == athlete_id)
        .order_by(AthleteRaceResultAnchor.race_date.desc().nullslast())
        .limit(8)
        .all()
    )
    return {
        "personal_bests": [
            {
                "distance": pb.distance_category,
                "time_seconds": pb.time_seconds,
                "time": _fmt_time(pb.time_seconds),
                "date": pb.achieved_at.date().isoformat() if pb.achieved_at else None,
                "is_race": bool(pb.is_race),
                "activity_id": str(pb.activity_id),
            }
            for pb in pbs
        ],
        "performance_events": [
            {
                "event_id": str(event.id),
                "activity_id": str(event.activity_id),
                "distance": event.distance_category,
                "event_type": event.event_type,
                "date": event.event_date.isoformat() if event.event_date else None,
                "time_seconds": event.effective_time_seconds,
                "time": _fmt_time(event.effective_time_seconds),
                "pace_per_mile": float(event.pace_per_mile) if event.pace_per_mile is not None else None,
                "tsb_at_event": float(event.tsb_at_event) if event.tsb_at_event is not None else None,
                "user_confirmed": event.user_confirmed,
            }
            for event in events
        ],
        "race_result_anchors": [
            {
                "anchor_id": str(anchor.id),
                "distance": anchor.distance_key,
                "distance_m": anchor.distance_meters,
                "time_seconds": anchor.time_seconds,
                "time": _fmt_time(anchor.time_seconds),
                "race_date": anchor.race_date.isoformat() if anchor.race_date else None,
                "source": anchor.source,
            }
            for anchor in anchors
        ],
    }


def _athlete_memory(db: Session, athlete_id: UUID) -> Dict[str, List[Dict[str, Any]]]:
    facts = (
        db.query(AthleteFact)
        .filter(
            AthleteFact.athlete_id == athlete_id,
            AthleteFact.is_active.is_(True),
            AthleteFact.fact_type.in_(sorted(_RACE_MEMORY_TYPES)),
        )
        .order_by(AthleteFact.confirmed_by_athlete.desc(), AthleteFact.extracted_at.desc())
        .limit(20)
        .all()
    )
    now = datetime.now(timezone.utc)
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for fact in facts:
        if fact.temporal and fact.ttl_days and fact.extracted_at:
            extracted = fact.extracted_at
            if extracted.tzinfo is None:
                extracted = extracted.replace(tzinfo=timezone.utc)
            if extracted < now - timedelta(days=int(fact.ttl_days)):
                continue
        grouped.setdefault(fact.fact_type, []).append(
            {
                "key": fact.fact_key,
                "value": fact.fact_value,
                "source_excerpt": fact.source_excerpt,
                "confirmed_by_athlete": bool(fact.confirmed_by_athlete),
            }
        )
    return grouped


def _safe_tool_payload(fn, *args, **kwargs) -> Dict[str, Any]:
    try:
        result = fn(*args, **kwargs)
        if isinstance(result, dict):
            return result
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": False, "error": "tool returned non-dict payload"}


def get_race_strategy_packet(
    db: Session,
    athlete_id: UUID,
    race_name: str = "",
    race_date: str = "",
    race_distance: str = "",
    lookback_days: int = 120,
) -> Dict[str, Any]:
    """Build the deterministic context packet for race strategy conversations."""
    now = datetime.utcnow()
    try:
        lookback_days = max(30, min(int(lookback_days or 120), 365))
        athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            return {"ok": False, "tool": "get_race_strategy_packet", "error": "Athlete not found"}

        plan = _active_plan(db, athlete_id)
        target = _target_race(
            race_name=race_name,
            race_date=race_date,
            race_distance=race_distance,
            plan=plan,
        )

        prior_candidates = _prior_course_candidates(db, athlete_id, target)
        prior_course = prior_candidates[0] if prior_candidates else None
        history = _race_history(db, athlete_id)
        memory = _athlete_memory(db, athlete_id)
        workouts = _recent_relevant_workouts(
            db,
            athlete_id,
            distance_m=target.get("distance_m"),
            lookback_days=lookback_days,
        )
        from services.coach_tools.load import get_recovery_status, get_training_load
        from services.coach_tools.performance import get_race_predictions, get_training_paces

        training_load = _safe_tool_payload(get_training_load, db, athlete_id)
        recovery_status = _safe_tool_payload(get_recovery_status, db, athlete_id)
        training_paces = _safe_tool_payload(get_training_paces, db, athlete_id)
        race_predictions = _safe_tool_payload(get_race_predictions, db, athlete_id)

        availability = {
            "target_race": bool(target.get("name") or target.get("date") or target.get("distance_m")),
            "prior_course_activity": prior_course is not None,
            "same_route_history": bool(_same_route_activities(db, athlete_id, prior_course)),
            "recent_race_relevant_workouts": bool(workouts),
            "race_history": bool(
                history["personal_bests"]
                or history["performance_events"]
                or history["race_result_anchors"]
            ),
            "training_load": bool(training_load.get("ok")),
            "recovery_status": bool(recovery_status.get("ok")),
            "training_paces": bool(training_paces.get("ok")),
            "race_predictions": bool(race_predictions.get("ok")),
            "athlete_memory": bool(memory),
            "future_weather": False,
        }
        unavailable = []
        if not availability["prior_course_activity"]:
            unavailable.append("No prior same-course activity found from activity names or race-distance matches.")
        unavailable.append("Future race-day weather is not modeled; only prior activity weather is available.")

        data = {
            "target_race": target,
            "plan_week": _plan_week(db, athlete_id, plan),
            "prior_course_activity": _activity_row(prior_course) if prior_course else None,
            "prior_course_candidates": [_activity_row(activity) for activity in prior_candidates],
            "same_route_history": _same_route_activities(db, athlete_id, prior_course),
            "recent_race_relevant_workouts": workouts,
            "race_history": history,
            "training_load": training_load,
            "recovery_status": recovery_status,
            "training_paces": training_paces,
            "race_predictions": race_predictions,
            "athlete_memory": memory,
            "availability": availability,
            "unavailable": unavailable,
        }

        target_bits = []
        if target.get("name"):
            target_bits.append(str(target["name"]))
        if target.get("distance_mi"):
            target_bits.append(f"{target['distance_mi']} mi")
        if target.get("date"):
            target_bits.append(f"on {target['date']}")
        target_label = " ".join(target_bits) if target_bits else "target race"
        course_text = (
            "course evidence found"
            if prior_course
            else "no prior course evidence found"
        )
        narrative = (
            f"Race strategy packet for {target_label}: {course_text}; "
            f"{len(workouts)} recent race-relevant workout(s); "
            f"{len(history['performance_events'])} performance event(s), "
            f"{len(history['personal_bests'])} PB(s), "
            f"{len(history['race_result_anchors'])} race anchor(s); "
            f"load context {'available' if training_load.get('ok') else 'unavailable'}; "
            f"memory types: {', '.join(sorted(memory.keys())) or 'none'}. "
            "Use unavailable fields as explicit uncertainty, not guesses."
        )

        evidence: List[Dict[str, Any]] = []
        if prior_course:
            evidence.append(
                {
                    "type": "activity",
                    "id": str(prior_course.id),
                    "date": _iso(prior_course.start_time)[:10] if prior_course.start_time else None,
                    "value": f"Prior course: {prior_course.name or 'activity'}",
                }
            )
        for workout in workouts[:3]:
            evidence.append(
                {
                    "type": "activity",
                    "id": workout["activity_id"],
                    "date": workout["date"],
                    "value": f"Race-relevant workout: {workout['name']}",
                }
            )

        return {
            "ok": True,
            "tool": "get_race_strategy_packet",
            "generated_at": _iso(now),
            "narrative": narrative,
            "data": data,
            "evidence": evidence,
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "get_race_strategy_packet", "error": str(e)}
