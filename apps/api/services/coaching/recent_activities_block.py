from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from models import Activity, ActivityFeedback, ActivitySplit

M_PER_MI = 1609.344
HARD_WORKOUT_TYPES = {
    "race",
    "tempo",
    "tempo_run",
    "threshold",
    "threshold_run",
    "threshold_intervals",
    "interval",
    "intervals",
    "track_workout",
    "vo2max_intervals",
    "hill_repetitions",
    "cruise_intervals",
}
LONG_WORKOUT_TYPES = {"long", "long_run"}
EASY_WORKOUT_TYPES = {"easy", "easy_run", "recovery", "recovery_run"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _estimated_tokens(value: Any) -> int:
    text = json.dumps(value, ensure_ascii=True, sort_keys=True, default=str)
    return max(1, len(text) // 4)


def _pace_s_per_mile(
    distance_m: float | None, duration_s: float | None
) -> float | None:
    if not distance_m or not duration_s or distance_m <= 0:
        return None
    return float(duration_s) / (float(distance_m) / M_PER_MI)


def _pace_label(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    rounded = int(round(seconds))
    return f"{rounded // 60}:{rounded % 60:02d}/mi"


def _activity_type(activity: Any) -> str:
    workout_type = (getattr(activity, "workout_type", None) or "").lower()
    if workout_type:
        return workout_type
    if getattr(activity, "user_verified_race", None) is True or getattr(
        activity, "is_race_candidate", None
    ):
        return "race"
    return "easy_default"


def _is_hard(activity: Any) -> bool:
    workout_type = _activity_type(activity)
    intensity = getattr(activity, "intensity_score", None)
    if workout_type in HARD_WORKOUT_TYPES:
        return True
    if intensity is not None and float(intensity) >= 60:
        return True
    return False


def _split_paces(splits: list[Any]) -> list[tuple[Any, float]]:
    rows = []
    for split in splits:
        pace = _pace_s_per_mile(
            float(getattr(split, "distance", 0) or 0),
            getattr(split, "moving_time", None) or getattr(split, "elapsed_time", None),
        )
        if pace is not None:
            rows.append((split, pace))
    return rows


def _planned_rep_count(activity: Any) -> int | None:
    text = f"{getattr(activity, 'name', '') or ''} {getattr(activity, 'workout_type', '') or ''}"
    match = re.search(r"\b(\d{1,2})\s*x\s*\d+", text.lower())
    if match:
        return int(match.group(1))
    return None


def _work_reps(splits: list[Any]) -> list[list[Any]]:
    work = [s for s in splits if (getattr(s, "lap_type", None) or "").lower() == "work"]
    if not work:
        return []
    reps: dict[int, list[Any]] = {}
    fallback_index = 0
    for split in work:
        interval_number = getattr(split, "interval_number", None)
        if interval_number is None:
            fallback_index += 1
            interval_number = fallback_index
        reps.setdefault(int(interval_number), []).append(split)
    return [reps[key] for key in sorted(reps)]


def _rep_summary(rep_splits: list[Any]) -> dict[str, Any]:
    distance = sum(float(getattr(split, "distance", 0) or 0) for split in rep_splits)
    duration = sum(
        int(
            getattr(split, "moving_time", None)
            or getattr(split, "elapsed_time", 0)
            or 0
        )
        for split in rep_splits
    )
    pace = _pace_s_per_mile(distance, duration)
    return {
        "distance_m": round(distance, 1),
        "duration_s": duration,
        "avg_pace": _pace_label(pace),
        "avg_pace_s_per_mile": round(pace, 1) if pace is not None else None,
    }


def _structured_workout_summary(
    activity: Any, splits: list[Any]
) -> dict[str, Any] | None:
    reps = _work_reps(splits)
    if not reps:
        return None
    rep_rows = [_rep_summary(rep) for rep in reps]
    return {
        "workout_type": _activity_type(activity),
        "planned_rep_count": _planned_rep_count(activity),
        "observed_work_rep_count": len(rep_rows),
        "reps": rep_rows,
    }


def _notable_features(activity: Any, splits: list[Any]) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    paces = _split_paces(splits)
    work_paces = [
        pace
        for split, pace in paces
        if (getattr(split, "lap_type", None) or "").lower() == "work"
    ]
    if len(work_paces) >= 2 and work_paces[-1] > work_paces[0] * 1.05:
        features.append(
            {
                "type": "pace_drift",
                "detail": "Later work reps slowed by at least 5 percent.",
                "value_pct": round(((work_paces[-1] / work_paces[0]) - 1) * 100, 1),
            }
        )

    all_paces = [pace for _, pace in paces]
    if len(all_paces) >= 4:
        cut = max(1, int(len(all_paces) * 0.75))
        early = mean(all_paces[:cut])
        late = mean(all_paces[cut:])
        if late > early * 1.05:
            features.append(
                {
                    "type": "fade",
                    "detail": "Final quarter slowed materially versus earlier splits.",
                    "value_pct": round(((late / early) - 1) * 100, 1),
                }
            )
        elif late < early * 0.97:
            features.append(
                {
                    "type": "strong_finish",
                    "detail": "Final quarter was faster than the earlier average.",
                    "value_pct": round((1 - (late / early)) * 100, 1),
                }
            )

    planned = _planned_rep_count(activity)
    observed = len(_work_reps(splits))
    if planned is not None and observed and observed < planned:
        features.append(
            {
                "type": "missed_rep",
                "detail": f"Observed {observed} work reps against {planned} planned.",
                "planned_reps": planned,
                "observed_reps": observed,
            }
        )
    return features


def _query_splits(db: Session, activity_id: UUID) -> list[Any]:
    return (
        db.query(ActivitySplit)
        .filter(ActivitySplit.activity_id == activity_id)
        .order_by(ActivitySplit.split_number)
        .all()
    )


def _query_feedback(db: Session, activity_id: UUID) -> Any | None:
    return (
        db.query(ActivityFeedback)
        .filter(ActivityFeedback.activity_id == activity_id)
        .first()
    )


def _activity_atom(db: Session, activity: Any) -> dict[str, Any]:
    splits = _query_splits(db, activity.id)
    feedback = _query_feedback(db, activity.id)
    distance_m = float(getattr(activity, "distance_m", 0) or 0)
    duration_s = getattr(activity, "moving_time_s", None) or getattr(
        activity, "duration_s", None
    )
    pace = _pace_s_per_mile(distance_m, duration_s)
    return {
        "activity_id": str(activity.id),
        "type": _activity_type(activity),
        "date": activity.start_time.date().isoformat(),
        "distance": {
            "meters": round(distance_m, 1) if distance_m else None,
            "miles": round(distance_m / M_PER_MI, 2) if distance_m else None,
        },
        "duration": {"seconds": int(duration_s) if duration_s else None},
        "avg_pace": {
            "seconds_per_mile": round(pace, 1) if pace is not None else None,
            "display": _pace_label(pace),
        },
        "avg_hr": getattr(activity, "avg_hr", None),
        "perceived_effort": (
            getattr(feedback, "perceived_effort", None)
            if feedback is not None
            else getattr(activity, "garmin_perceived_effort", None)
        ),
        "planned_vs_executed_delta": None,
        "notable_features": _notable_features(activity, splits),
        "structured_workout_summary": _structured_workout_summary(activity, splits),
    }


def _week_start(value: datetime) -> datetime:
    day = value.date()
    start = day - timedelta(days=day.weekday())
    return datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)


def _aggregates(activities: list[Any], now_utc: datetime) -> dict[str, Any]:
    weeks = []
    for offset in range(3, -1, -1):
        start = _week_start(now_utc) - timedelta(days=offset * 7)
        end = start + timedelta(days=7)
        week_activities = [
            activity
            for activity in activities
            if start <= activity.start_time.astimezone(timezone.utc) < end
        ]
        volume_mi = (
            sum(float(getattr(a, "distance_m", 0) or 0) for a in week_activities)
            / M_PER_MI
        )
        hard_count = sum(1 for activity in week_activities if _is_hard(activity))
        easy_count = max(0, len(week_activities) - hard_count)
        weeks.append(
            {
                "week_start": start.date().isoformat(),
                "weekly_volume_miles": round(volume_mi, 2),
                "weekly_hard_day_count": hard_count,
                "weekly_easy_hard_ratio": (
                    round(easy_count / hard_count, 2) if hard_count else None
                ),
            }
        )

    previous = weeks[-2]["weekly_volume_miles"] if len(weeks) >= 2 else 0
    current = weeks[-1]["weekly_volume_miles"] if weeks else 0
    change_pct = None
    if previous:
        change_pct = round(((current - previous) / previous) * 100, 1)

    last_by_type: dict[str, dict[str, Any]] = {}
    for activity in sorted(activities, key=lambda item: item.start_time, reverse=True):
        workout_type = _activity_type(activity)
        bucket = "easy_default"
        if workout_type in HARD_WORKOUT_TYPES:
            bucket = (
                "threshold"
                if "threshold" in workout_type or "tempo" in workout_type
                else "interval"
            )
        if workout_type in LONG_WORKOUT_TYPES:
            bucket = "long"
        if workout_type in EASY_WORKOUT_TYPES or workout_type == "easy_default":
            bucket = "easy_default"
        last_by_type.setdefault(
            bucket,
            {
                "activity_id": str(activity.id),
                "date": activity.start_time.date().isoformat(),
                "type": workout_type,
            },
        )

    return {
        "last_4_weeks": weeks,
        "weekly_volume_change_pct": change_pct,
        "last_session_by_major_type": last_by_type,
    }


def compute_recent_activities(
    db: Session,
    athlete_id: UUID,
    *,
    window_days: int = 14,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    generated_at = (_now() if now_utc is None else now_utc).replace(microsecond=0)
    now = (
        generated_at
        if generated_at.tzinfo
        else generated_at.replace(tzinfo=timezone.utc)
    )
    start = now - timedelta(days=window_days)
    activities = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.sport == "run",
            Activity.start_time >= start,
        )
        .order_by(Activity.start_time.desc())
        .all()
    )
    activities = [
        activity
        for activity in activities
        if getattr(activity, "start_time", None)
        and activity.start_time.astimezone(timezone.utc) >= start
    ]
    activities = sorted(activities, key=lambda item: item.start_time, reverse=True)
    atoms = [_activity_atom(db, activity) for activity in activities]
    data = {
        "recent_activities": atoms,
        "aggregates": _aggregates(list(activities), now),
    }
    while atoms and _estimated_tokens(data) > 2500:
        atoms.pop()
        data = {
            "recent_activities": atoms,
            "aggregates": _aggregates(list(activities), now),
        }

    return {
        "schema_version": "coach_runtime_v2.recent_activities.v1",
        "status": "complete",
        "generated_at": generated_at.isoformat(),
        "window_days": window_days,
        "ordered": "most_recent_first",
        "data": data,
        "token_budget": {
            "target_tokens": 1500,
            "max_tokens": 2500,
            "estimated_tokens": _estimated_tokens(data),
        },
        "provenance": [
            {
                "field_path": "recent_activities",
                "source_system": "activity_store",
                "source_id": str(athlete_id),
                "source_timestamp": generated_at.isoformat(),
                "observed_at": generated_at.isoformat(),
                "confidence": "high",
                "derivation_chain": ["Activity", "ActivitySplit", "ActivityFeedback"],
            }
        ],
        "unknowns": [],
    }
