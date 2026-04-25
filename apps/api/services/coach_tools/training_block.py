from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from statistics import median
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models import Activity
from services.coach_tools._utils import _M_PER_MI, _iso, _mi_from_m, _pace_str_mi
from services.run_intelligence import _get_interval_analysis


_QUALITY_WORKOUT_TYPES = {
    "interval",
    "intervals",
    "track",
    "track_workout",
    "tempo",
    "tempo_run",
    "tempo_intervals",
    "threshold",
    "threshold_run",
    "cruise_intervals",
    "vo2max_intervals",
    "progression",
    "race",
}

_QUALITY_NAME_TOKENS = (
    "race",
    "5k",
    "10k",
    "mile",
    "tempo",
    "threshold",
    "interval",
    "repeat",
    "repeats",
    "workout",
    "progression",
    "400",
    "800",
    "1200",
)

_REP_PATTERN_RE = re.compile(
    r"\b(?:(?P<count>\d{1,2})\s*(?:x|by)\s*)?(?P<distance>200|300|400|600|800|1000|1200|1600|1609|1\s*mile)s?\s*m?\b",
    re.IGNORECASE,
)


def _snap_rep_distance(distance_m: float) -> int:
    common = (200, 300, 400, 600, 800, 1000, 1200, 1600, 1609, 2000)
    nearest = min(common, key=lambda candidate: abs(candidate - distance_m))
    if abs(nearest - distance_m) <= max(35.0, nearest * 0.06):
        return 1600 if nearest == 1609 else nearest
    return int(round(distance_m))


def _energy_system_for_rep_distance(rep_distance_m: Optional[int]) -> str:
    if rep_distance_m is None:
        return "quality"
    if rep_distance_m <= 500:
        return "speed"
    if rep_distance_m <= 1300:
        return "vo2_lactate"
    if rep_distance_m <= 2200:
        return "threshold_speed_endurance"
    return "tempo"


def parse_structured_workout_query(text: str) -> Optional[Dict[str, Any]]:
    normalized = (text or "").strip().lower()
    if not normalized:
        return None
    normalized = normalized.replace("×", "x")
    normalized = re.sub(r"(\d)\s+x\s+(\d)", r"\1x\2", normalized)
    match = _REP_PATTERN_RE.search(normalized)
    if not match:
        if any(token in normalized for token in ("interval", "repeat", "repeats", "rep", "reps")):
            return {"structured": True, "rep_count": None, "rep_distance_m": None}
        return None

    raw_distance = (match.group("distance") or "").replace(" ", "")
    rep_distance_m = 1600 if raw_distance in {"1609", "1mile"} else int(raw_distance)
    raw_count = match.group("count")
    return {
        "structured": True,
        "rep_count": int(raw_count) if raw_count else None,
        "rep_distance_m": rep_distance_m,
    }


def split_summary_matches_query(
    split_summary: Optional[Dict[str, Any]],
    intent: Optional[Dict[str, Any]],
) -> bool:
    if not split_summary or not intent:
        return False
    expected_distance = intent.get("rep_distance_m")
    expected_count = intent.get("rep_count")
    actual_distance = split_summary.get("rep_distance_m")
    actual_count = split_summary.get("total_reps")

    if expected_distance is not None:
        if actual_distance is None:
            return False
        if abs(int(actual_distance) - int(expected_distance)) > max(35, int(expected_distance) * 0.08):
            return False
    if expected_count is not None and actual_count is not None:
        if abs(int(actual_count) - int(expected_count)) > 1:
            return False
    return True


def summarize_activity_split_structure(db: Session, activity: Activity) -> Optional[Dict[str, Any]]:
    """Return split-derived workout structure for coach retrieval/ranking."""
    interval = _get_interval_analysis(activity, db)
    if not interval:
        return None

    reps = list(interval.get("reps") or [])
    if len(reps) < 2:
        return None

    rep_distances = [
        float(rep["distance_m"])
        for rep in reps
        if rep.get("distance_m") is not None and float(rep["distance_m"]) > 0
    ]
    rep_distance_m = _snap_rep_distance(median(rep_distances)) if rep_distances else None
    classification = _energy_system_for_rep_distance(rep_distance_m)
    rep_label = f"{rep_distance_m}m" if rep_distance_m is not None else "reps"
    signature = f"{len(reps)} x {rep_label}"

    return {
        "is_structured": True,
        "source": "activity_splits",
        "total_reps": len(reps),
        "clean_reps": interval.get("clean_reps"),
        "busted_reps": interval.get("busted_reps") or [],
        "rep_distance_m": rep_distance_m,
        "signature": signature,
        "classification": classification,
        "avg_work_pace_per_mile": interval.get("clean_avg_pace_per_mile"),
        "derived_from_pace": bool(interval.get("derived_from_pace")),
    }


def activity_quality_keyword_score(activity: Activity) -> int:
    workout_type = (activity.workout_type or "").strip().lower()
    if workout_type in _QUALITY_WORKOUT_TYPES:
        return 45
    label = f"{activity.name or ''} {activity.athlete_title or ''} {activity.shape_sentence or ''}".lower()
    return 35 if any(token in label for token in _QUALITY_NAME_TOKENS) else 0


def race_specificity(distance_m: Optional[int], split_summary: Optional[Dict[str, Any]]) -> str:
    if not split_summary:
        return "low"
    rep_distance_m = split_summary.get("rep_distance_m")
    if distance_m and distance_m <= 5000 and rep_distance_m and 250 <= int(rep_distance_m) <= 1800:
        return "high"
    return "medium"


def quality_rank_for_activity(
    db: Session,
    activity: Activity,
    *,
    race_distance_m: Optional[int] = None,
) -> Dict[str, Any]:
    split_summary = summarize_activity_split_structure(db, activity)
    keyword_score = activity_quality_keyword_score(activity)
    specificity = race_specificity(race_distance_m, split_summary)

    score = keyword_score
    selection_reason = "broad_distance_match"
    if split_summary:
        score += 100
        selection_reason = "split_confirmed_quality_session"
    elif keyword_score:
        selection_reason = "name_or_type_quality_match"

    if specificity == "high":
        score += 30
    elif specificity == "medium":
        score += 15

    if getattr(activity, "user_verified_race", False) or getattr(activity, "is_race_candidate", False):
        score += 50
        selection_reason = "race_result_or_candidate"

    return {
        "quality_rank": score,
        "selection_reason": selection_reason,
        "race_specificity": specificity,
        "split_summary": split_summary,
    }


def activity_row_with_training_structure(
    db: Session,
    activity: Activity,
    *,
    race_distance_m: Optional[int] = None,
) -> Dict[str, Any]:
    structure = quality_rank_for_activity(db, activity, race_distance_m=race_distance_m)
    distance_m = int(activity.distance_m) if activity.distance_m is not None else None
    split_summary = structure["split_summary"]
    return {
        "activity_id": str(activity.id),
        "name": activity.name,
        "date": _iso(activity.start_time)[:10] if activity.start_time else None,
        "distance_m": distance_m,
        "distance_mi": round(_mi_from_m(activity.distance_m), 2) if activity.distance_m is not None else None,
        "duration_s": int(activity.duration_s) if activity.duration_s is not None else None,
        "pace_per_mile": _pace_str_mi(activity.duration_s, activity.distance_m),
        "workout_type": activity.workout_type,
        "is_race": bool(activity.user_verified_race or activity.is_race_candidate or activity.workout_type == "race"),
        "shape_sentence": activity.shape_sentence,
        "classification": split_summary.get("classification") if split_summary else None,
        "split_summary": split_summary,
        "selection_reason": structure["selection_reason"],
        "quality_rank": structure["quality_rank"],
        "race_specificity": structure["race_specificity"],
    }


def get_training_block_narrative(
    db: Session,
    athlete_id: UUID,
    days: int = 42,
    limit: int = 12,
) -> Dict[str, Any]:
    now = datetime.utcnow()
    days = max(14, min(int(days or 42), 120))
    limit = max(1, min(int(limit or 12), 25))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    activities = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.sport == "run",
            Activity.start_time >= cutoff,
        )
        .order_by(Activity.start_time.desc().nullslast())
        .limit(120)
        .all()
    )

    quality_sessions: List[Dict[str, Any]] = []
    for activity in activities:
        row = activity_row_with_training_structure(db, activity)
        if row["split_summary"] or row["quality_rank"] > 0:
            quality_sessions.append(row)

    quality_sessions.sort(
        key=lambda row: (
            row.get("date") or "",
            row.get("quality_rank") or 0,
        )
    )
    quality_sessions = quality_sessions[-limit:]

    arc_bits = []
    for row in quality_sessions:
        split_summary = row.get("split_summary") or {}
        signature = split_summary.get("signature")
        label = signature or row.get("workout_type") or row.get("name") or "quality run"
        arc_bits.append(f"{row.get('date')}: {label}")

    if arc_bits:
        narrative = "Training block quality arc: " + " -> ".join(arc_bits) + "."
    else:
        narrative = f"No structured quality sessions found in the last {days} days."

    classifications = {
        row["classification"]
        for row in quality_sessions
        if row.get("classification")
    }
    missing = []
    if "speed" not in classifications:
        missing.append("speed reps")
    if "threshold_speed_endurance" not in classifications and "tempo" not in classifications:
        missing.append("continuous threshold / 5K-specific work")

    return {
        "ok": True,
        "tool": "get_training_block_narrative",
        "generated_at": _iso(now),
        "narrative": narrative,
        "data": {
            "window_days": days,
            "quality_sessions": quality_sessions,
            "missing_or_limited": missing,
            "preferred_distance_unit": "mi",
            "meters_per_mile": _M_PER_MI,
        },
        "evidence": [
            {
                "type": "activity",
                "id": row["activity_id"],
                "date": row.get("date"),
                "value": (
                    (row.get("split_summary") or {}).get("signature")
                    or row.get("name")
                    or "quality run"
                ),
            }
            for row in quality_sessions[:5]
        ],
    }
