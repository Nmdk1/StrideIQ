from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from models import Activity, ActivitySplit, TrainingPlan
from services.coaching.runtime_v2 import PACKET_SCHEMA_VERSION
from services.coaching.unknowns_block import compute_unknowns, detect_query_class
from services.timezone_utils import (
    athlete_local_today,
    get_athlete_timezone_from_db,
    to_activity_local_date,
)

ASSEMBLER_VERSION = "coach_runtime_v2_0_a_packet_assembler_001"
MODE_CLASSIFIER_VERSION = "coach_mode_classifier_v2_0_a"

ARTIFACT5_MODES = (
    "observe_and_ask",
    "engage_and_reason",
    "acknowledge_and_redirect",
    "pattern_observation",
    "pushback",
    "celebration",
    "uncertainty_disclosure",
    "asking_after_work",
    "racing_preparation_judgment",
    "brief_status_update",
    "correction",
    "mode_uncertain",
)


class V2PacketInvariantError(RuntimeError):
    """Raised when a visible V2 request cannot safely build a packet."""


_TEMPORAL_BRIDGE_PATTERN = re.compile(
    r"\b("
    r"today|tonight|tomorrow|yesterday|race|raced|racing|race[- ]?day|"
    r"race[- ]?week|taper|days? until|days? out|this morning|this week|"
    r"last night|last run|recent run|upcoming|"
    r"one day|two days|three days|four days|five days|six days|seven days|"
    r"eight days|nine days|ten days"
    r")\b",
    flags=re.IGNORECASE,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _estimated_tokens(value: Any) -> int:
    text = json.dumps(value, ensure_ascii=True, sort_keys=True, default=str)
    return max(1, len(text) // 4)


def _relative_date(target: date, today: date) -> str:
    delta = (target - today).days
    if delta == 0:
        return "today"
    if delta == -1:
        return "yesterday"
    if delta == 1:
        return "tomorrow"
    if delta < 0:
        return f"{abs(delta)} days ago"
    return f"in {delta} days"


def _activity_is_race(activity: Activity) -> bool:
    return bool(
        getattr(activity, "user_verified_race", None) is True
        or getattr(activity, "is_race_candidate", None) is True
        or (getattr(activity, "workout_type", "") or "").lower() == "race"
    )


def _distance_miles(activity: Activity) -> float | None:
    if getattr(activity, "distance_m", None) is None:
        return None
    return float(activity.distance_m) / 1609.344


def _pace_seconds_per_mile(activity: Activity) -> float | None:
    distance_miles = _distance_miles(activity)
    duration_s = getattr(activity, "duration_s", None)
    if not distance_miles or not duration_s or distance_miles <= 0:
        return None
    return float(duration_s) / distance_miles


def _pace_display(seconds_per_mile: float | None) -> str | None:
    if seconds_per_mile is None:
        return None
    total = int(round(seconds_per_mile))
    return f"{total // 60}:{total % 60:02d}/mi"


def _parse_activity_classification_override(message: str) -> dict[str, Any] | None:
    lower = (message or "").lower()
    if "race" not in lower or not any(
        term in lower for term in ("was", "label", "tag", "3.1", "5k")
    ):
        return None

    target_distance_m = None
    distance_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:mile|mi|miler)", lower)
    if distance_match:
        target_distance_m = round(float(distance_match.group(1)) * 1609.344)
    elif "5k" in lower or "5 k" in lower:
        target_distance_m = 5000

    return {
        "classification": "race_effort",
        "reason": "athlete_same_turn_correction",
        "target_distance_m": target_distance_m,
        "scope": "current_turn",
    }


def _activity_matches_override(
    activity: Activity, override: dict[str, Any] | None
) -> bool:
    if not override:
        return False
    target_distance_m = override.get("target_distance_m")
    if target_distance_m is None:
        return True
    distance_m = getattr(activity, "distance_m", None)
    if distance_m is None:
        return False
    return abs(float(distance_m) - float(target_distance_m)) <= 900


def _classify_activity_hardness(
    activity: Activity,
    *,
    effort_class: str | None,
    override: dict[str, Any] | None,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    pace_s_mile = _pace_seconds_per_mile(activity)
    distance_m = float(getattr(activity, "distance_m", 0) or 0)
    duration_s = float(getattr(activity, "duration_s", 0) or 0)
    workout_type = (getattr(activity, "workout_type", None) or "").lower()
    name = (getattr(activity, "name", None) or "").lower()
    intensity_score = getattr(activity, "intensity_score", None)

    if _activity_matches_override(activity, override):
        return "race_effort", ["athlete_same_turn_override"]

    if _activity_is_race(activity):
        return "race_effort", ["race_flag"]

    if pace_s_mile is not None and 4500 <= distance_m <= 5600 and duration_s <= 1500:
        return "race_effort", ["5k_distance_fast_duration"]

    if pace_s_mile is not None and duration_s <= 900 and pace_s_mile <= 430:
        return "short_fast", ["short_fast_pace_duration"]

    if workout_type in {
        "threshold",
        "threshold_run",
        "tempo_run",
        "tempo",
        "threshold_intervals",
    }:
        return "threshold", ["workout_type_threshold"]

    if effort_class == "hard":
        reasons.append("effort_classifier_hard")
        if pace_s_mile is not None and pace_s_mile <= 420:
            return "threshold", reasons + ["fast_average_pace"]
        return "hard", reasons

    if intensity_score is not None:
        if float(intensity_score) >= 70:
            return "hard", ["intensity_score_high"]
        if float(intensity_score) >= 55:
            return "threshold", ["intensity_score_moderate_high"]

    if effort_class == "moderate":
        return "moderate", ["effort_classifier_moderate"]

    if any(term in name for term in ("tempo", "threshold", "race", "5k")):
        return "moderate", ["name_signal_weak"]

    return "easy", ["default_easy"]


def _split_pace_seconds_per_mile(split: ActivitySplit) -> float | None:
    distance_m = float(getattr(split, "distance", 0) or 0)
    time_s = getattr(split, "moving_time", None) or getattr(split, "elapsed_time", None)
    if distance_m <= 0 or not time_s:
        return None
    return float(time_s) / (distance_m / 1609.344)


def _build_execution_quality(
    activity: Activity,
    *,
    db: Session | None,
    same_turn_execution_override: dict[str, Any] | None,
) -> dict[str, Any]:
    if same_turn_execution_override and _activity_matches_override(
        activity, same_turn_execution_override
    ):
        return {
            "status": same_turn_execution_override["status"],
            "confidence": "high",
            "source": "athlete_same_turn_correction",
            "split_count": None,
            "pace_decay_pct": None,
            "can_claim_controlled": False,
            "must_ask_followup": False,
            "evidence": same_turn_execution_override["evidence"],
        }

    if db is None:
        return {
            "status": "unknown",
            "confidence": "low",
            "source": "missing_db",
            "split_count": 0,
            "pace_decay_pct": None,
            "can_claim_controlled": False,
            "must_ask_followup": True,
            "evidence": "No split evidence available.",
        }

    try:
        splits = (
            db.query(ActivitySplit)
            .filter(ActivitySplit.activity_id == activity.id)
            .order_by(ActivitySplit.split_number.asc())
            .all()
        )
    except Exception:
        splits = []

    paces = [
        pace
        for pace in (_split_pace_seconds_per_mile(split) for split in splits or [])
        if pace is not None
    ]
    if len(paces) < 2:
        return {
            "status": "unknown",
            "confidence": "low",
            "source": "insufficient_splits",
            "split_count": len(paces),
            "pace_decay_pct": None,
            "can_claim_controlled": False,
            "must_ask_followup": True,
            "evidence": "Split evidence is insufficient; ask how the effort went after checking available activity data.",
        }

    mid = len(paces) // 2
    first_half = sum(paces[:mid]) / len(paces[:mid])
    second_half = sum(paces[mid:]) / len(paces[mid:])
    decay_pct = ((second_half - first_half) / first_half) * 100 if first_half else 0
    if decay_pct > 6:
        status = "pacing_suffered"
        can_claim_controlled = False
    elif decay_pct > 3:
        status = "late_fade"
        can_claim_controlled = False
    elif decay_pct >= -3:
        status = "even_pacing"
        can_claim_controlled = True
    else:
        status = "negative_split"
        can_claim_controlled = True

    return {
        "status": status,
        "confidence": "medium",
        "source": "activity_splits",
        "split_count": len(paces),
        "pace_decay_pct": round(decay_pct, 1),
        "can_claim_controlled": can_claim_controlled,
        "must_ask_followup": False,
        "evidence": (
            f"First-half average {_pace_display(first_half)}, second-half average "
            f"{_pace_display(second_half)}, decay {decay_pct:+.1f}%."
        ),
    }


def _parse_execution_quality_override(message: str) -> dict[str, Any] | None:
    lower = (message or "").lower()
    negative_terms = (
        "wasn't controlled",
        "was not controlled",
        "not controlled",
        "pacing suffered",
        "pacing fell apart",
        "blew up",
        "faded",
        "didn't have a good go",
        "did not have a good go",
        "bad race",
        "went badly",
    )
    if not any(term in lower for term in negative_terms):
        return None

    activity_override = _parse_activity_classification_override(message) or {}
    return {
        "status": "athlete_reported_pacing_suffered",
        "reason": "athlete_same_turn_correction",
        "target_distance_m": activity_override.get("target_distance_m"),
        "scope": "current_turn",
        "evidence": message,
    }


def _override_value(value: Any, *, duration: str) -> dict[str, Any]:
    return {
        "value": value,
        "duration": duration,
    }


def _unwrap_override_value(override_value: Any) -> Any:
    if isinstance(override_value, dict) and "value" in override_value:
        return override_value.get("value")
    return override_value


def _activity_summary(
    activity: Activity, *, today: date, athlete_tz: Any
) -> dict[str, Any]:
    local_date = to_activity_local_date(activity, athlete_tz)
    return {
        "activity_id": str(activity.id),
        "date": local_date.isoformat(),
        "relative_date": _relative_date(local_date, today),
        "sport": getattr(activity, "sport", None),
        "name": getattr(activity, "name", None),
        "workout_type": getattr(activity, "workout_type", None),
        "distance_m": (
            int(activity.distance_m) if activity.distance_m is not None else None
        ),
        "is_race": _activity_is_race(activity),
        "race_confidence": (
            float(activity.race_confidence)
            if activity.race_confidence is not None
            else None
        ),
    }


def build_activity_evidence_state(
    *,
    athlete_id: UUID,
    db: Session | None,
    calendar_context: dict[str, Any],
    activity_override: dict[str, Any] | None,
    execution_override: dict[str, Any] | None,
) -> dict[str, Any]:
    generated_at = _utc_now_iso()
    today_local = (calendar_context.get("data") or {}).get("today_local")
    if db is None or not today_local:
        return {
            "schema_version": "coach_runtime_v2.activity_evidence.v1",
            "status": "unavailable",
            "generated_at": generated_at,
            "data": {
                "recent_activities": [],
                "yesterday": None,
                "activity_classification_override": activity_override,
                "execution_quality_override": execution_override,
            },
            "unknowns": [
                {
                    "reason": "service_unavailable",
                    "field": "activity_evidence",
                    "detail": "Database session or calendar context unavailable.",
                    "retryable": True,
                }
            ],
            "provenance": [],
        }

    try:
        athlete_tz = get_athlete_timezone_from_db(db, athlete_id)
        today = date.fromisoformat(today_local)
        activities = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete_id,
                Activity.sport == "run",
            )
            .order_by(Activity.start_time.desc())
            .limit(12)
            .all()
        )
    except Exception as exc:
        return {
            "schema_version": "coach_runtime_v2.activity_evidence.v1",
            "status": "unavailable",
            "generated_at": generated_at,
            "data": {
                "recent_activities": [],
                "yesterday": None,
                "activity_classification_override": activity_override,
                "execution_quality_override": execution_override,
            },
            "unknowns": [
                {
                    "reason": "service_unavailable",
                    "field": "activity_evidence",
                    "detail": exc.__class__.__name__,
                    "retryable": True,
                }
            ],
            "provenance": [],
        }

    effort_classes: dict[Any, str] = {}
    try:
        from services.effort_classification import classify_effort_bulk

        effort_classes = classify_effort_bulk(
            list(activities or []), str(athlete_id), db
        )
    except Exception:
        effort_classes = {}

    rows = []
    for activity in list(activities or []):
        try:
            local_date = to_activity_local_date(activity, athlete_tz)
            effort_class = effort_classes.get(activity.id)
            hardness, reasons = _classify_activity_hardness(
                activity,
                effort_class=effort_class,
                override=activity_override,
            )
            execution_quality = _build_execution_quality(
                activity,
                db=db,
                same_turn_execution_override=execution_override,
            )
            pace_s_mile = _pace_seconds_per_mile(activity)
            rows.append(
                {
                    "activity_id": str(activity.id),
                    "date": local_date.isoformat(),
                    "relative_date": _relative_date(local_date, today),
                    "name": getattr(activity, "name", None),
                    "distance_m": (
                        int(activity.distance_m)
                        if activity.distance_m is not None
                        else None
                    ),
                    "distance_mi": (
                        round(_distance_miles(activity), 2)
                        if _distance_miles(activity) is not None
                        else None
                    ),
                    "duration_s": (
                        int(activity.duration_s)
                        if activity.duration_s is not None
                        else None
                    ),
                    "pace_per_mile": _pace_display(pace_s_mile),
                    "pace_seconds_per_mile": (
                        round(pace_s_mile, 1) if pace_s_mile is not None else None
                    ),
                    "avg_hr": (
                        int(getattr(activity, "avg_hr"))
                        if getattr(activity, "avg_hr", None) is not None
                        else None
                    ),
                    "workout_type_label": getattr(activity, "workout_type", None),
                    "effort_class": effort_class,
                    "hardness": hardness,
                    "classification_reasons": reasons,
                    "execution_quality": execution_quality,
                    "is_race": hardness == "race_effort",
                    "source_label_is_authoritative": False,
                }
            )
        except Exception:
            continue

    yesterday = today - timedelta(days=1)
    yesterday_rows = [row for row in rows if row["date"] == yesterday.isoformat()]
    quality_hardness = {"race_effort", "threshold", "short_fast", "hard", "moderate"}
    yesterday_quality = [
        row for row in yesterday_rows if row["hardness"] in quality_hardness
    ]
    race_quality_rows = [
        row for row in yesterday_quality if row["hardness"] == "race_effort"
    ]
    execution_rows = [
        row["execution_quality"]
        for row in race_quality_rows
        if row.get("execution_quality")
    ]
    execution_negative = any(
        row["status"]
        in {"pacing_suffered", "late_fade", "athlete_reported_pacing_suffered"}
        for row in execution_rows
    )
    execution_unknown = any(row["status"] == "unknown" for row in execution_rows)
    can_claim_confidence = bool(execution_rows) and all(
        row.get("can_claim_controlled") for row in execution_rows
    )

    return {
        "schema_version": "coach_runtime_v2.activity_evidence.v1",
        "status": "complete",
        "generated_at": generated_at,
        "data": {
            "recent_activities": rows[:8],
            "activity_classification_override": activity_override,
            "execution_quality_override": execution_override,
            "yesterday": {
                "date": yesterday.isoformat(),
                "activity_count": len(yesterday_rows),
                "total_distance_mi": round(
                    sum((row.get("distance_mi") or 0) for row in yesterday_rows), 2
                ),
                "all_easy": bool(yesterday_rows) and not yesterday_quality,
                "race_effort_present": any(
                    row["hardness"] == "race_effort" for row in yesterday_rows
                ),
                "threshold_effort_present": any(
                    row["hardness"] == "threshold" for row in yesterday_rows
                ),
                "short_fast_effort_present": any(
                    row["hardness"] == "short_fast" for row in yesterday_rows
                ),
                "quality_effort_count": len(yesterday_quality),
                "race_execution_quality": {
                    "status": (
                        "negative"
                        if execution_negative
                        else (
                            "unknown"
                            if execution_unknown or not execution_rows
                            else (
                                "controlled_or_even"
                                if can_claim_confidence
                                else "mixed"
                            )
                        )
                    ),
                    "can_claim_controlled_or_confident": can_claim_confidence,
                    "must_ask_how_it_went": bool(
                        race_quality_rows
                        and (
                            execution_unknown
                            or not execution_rows
                            or not can_claim_confidence
                        )
                    ),
                    "forbidden_claims_without_more_evidence": (
                        [
                            "controlled",
                            "executed well",
                            "banked confidence",
                            "good go",
                            "sharpest tool in the box",
                        ]
                        if race_quality_rows and not can_claim_confidence
                        else []
                    ),
                    "evidence": execution_rows,
                },
                "quality_summary": [
                    {
                        "activity_id": row["activity_id"],
                        "distance_mi": row["distance_mi"],
                        "pace_per_mile": row["pace_per_mile"],
                        "hardness": row["hardness"],
                        "classification_reasons": row["classification_reasons"],
                        "execution_quality": row["execution_quality"],
                    }
                    for row in yesterday_quality
                ],
            },
        },
        "unknowns": [],
        "provenance": [
            {
                "field_path": "blocks.activity_evidence.data",
                "source_system": "deterministic_computation",
                "source_id": None,
                "source_timestamp": generated_at,
                "observed_at": generated_at,
                "confidence": "high",
                "derivation_chain": [
                    "Activity",
                    "effort_classification",
                    "pace_duration_rules",
                    "same_turn_activity_override",
                ],
            }
        ],
    }


def build_training_adaptation_context(
    *,
    calendar_context: dict[str, Any],
    activity_evidence: dict[str, Any],
) -> dict[str, Any]:
    generated_at = _utc_now_iso()
    calendar_data = calendar_context.get("data") or {}
    evidence_data = activity_evidence.get("data") or {}
    upcoming_race = calendar_data.get("upcoming_race") or {}
    days_until = upcoming_race.get("days_until_race")
    yesterday = evidence_data.get("yesterday") or {}
    race_effort = bool(yesterday.get("race_effort_present"))
    threshold_effort = bool(yesterday.get("threshold_effort_present"))
    short_fast = bool(yesterday.get("short_fast_effort_present"))
    quality_count = int(yesterday.get("quality_effort_count") or 0)
    race_execution = yesterday.get("race_execution_quality") or {}
    race_execution_status = race_execution.get("status")
    can_claim_confidence = bool(race_execution.get("can_claim_controlled_or_confident"))
    must_ask_how_it_went = bool(race_execution.get("must_ask_how_it_went"))
    close_to_target = isinstance(days_until, int) and 0 <= days_until <= 7

    if close_to_target and (race_effort or threshold_effort or short_fast):
        likely_effect = (
            "hard_stimulus_not_meaningful_new_fitness_before_target"
            if not can_claim_confidence
            else "sharpness_or_confidence_not_meaningful_new_fitness_before_target"
        )
        fitness_window = "mostly_after_target"
        fatigue_cost = "meaningful"
        recommendation_bias = (
            "ask_after_work_then_protect_freshness"
            if must_ask_how_it_went
            else "protect_freshness"
        )
    elif race_effort or threshold_effort or short_fast:
        likely_effect = "fitness_stimulus_possible_with_recovery_window"
        fitness_window = "future_adaptation_window_available"
        fatigue_cost = "meaningful"
        recommendation_bias = "absorb_before_next_quality"
    elif yesterday.get("all_easy"):
        likely_effect = "maintenance_volume"
        fitness_window = "minimal_new_fitness"
        fatigue_cost = "low"
        recommendation_bias = "continue_plan"
    else:
        likely_effect = "unknown"
        fitness_window = "unknown"
        fatigue_cost = "unknown"
        recommendation_bias = "ask_after_work"

    return {
        "schema_version": "coach_runtime_v2.training_adaptation.v1",
        "status": "complete",
        "generated_at": generated_at,
        "data": {
            "target_event_days_until": days_until,
            "target_event_name": upcoming_race.get("name"),
            "stimulus_window": "yesterday",
            "stimulus_event_mix": {
                "race_effort_present": race_effort,
                "threshold_effort_present": threshold_effort,
                "short_fast_effort_present": short_fast,
                "all_easy": bool(yesterday.get("all_easy")),
                "quality_effort_count": quality_count,
                "race_execution_quality": race_execution_status,
            },
            "likely_effect_before_target": likely_effect,
            "fatigue_cost": fatigue_cost,
            "fitness_adaptation_window": fitness_window,
            "recommendation_bias": recommendation_bias,
            "confidence_or_sharpness_claim_allowed": can_claim_confidence,
            "must_ask_execution_followup": must_ask_how_it_went,
            "ask_after_work_instruction": (
                "State the verified work first, then ask how the race actually went "
                "because execution quality is missing or negative. Do not infer "
                "controlled execution, confidence, or a good race from intensity alone."
                if must_ask_how_it_went
                else None
            ),
            "coach_interpretation": (
                "Close to a target race, yesterday quality was real stress, but "
                "meaningful new fitness is unlikely to arrive before the target. "
                "If execution quality is unknown or poor, ask how it went before "
                "claiming confidence or sharpness; manage fatigue and preserve freshness."
                if close_to_target and quality_count
                else None
            ),
        },
        "unknowns": [],
        "provenance": [
            {
                "field_path": "blocks.training_adaptation_context.data",
                "source_system": "deterministic_computation",
                "source_id": None,
                "source_timestamp": generated_at,
                "observed_at": generated_at,
                "confidence": "high" if days_until is not None else "medium",
                "derivation_chain": ["calendar_context", "activity_evidence"],
            }
        ],
    }


def build_calendar_context_state(
    *,
    athlete_id: UUID,
    db: Session | None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    generated_at = (
        now_utc.astimezone(timezone.utc).replace(microsecond=0).isoformat()
        if now_utc
        else _utc_now_iso()
    )
    if db is None:
        return {
            "schema_version": "coach_runtime_v2.calendar_context.v1",
            "status": "unavailable",
            "generated_at": generated_at,
            "data": {
                "today_local": None,
                "today_has_completed_activity": None,
                "today_has_completed_race": None,
                "upcoming_race": None,
                "latest_completed_activity": None,
                "recent_activities": [],
            },
            "unknowns": [
                {
                    "reason": "service_unavailable",
                    "field": "calendar_context",
                    "detail": "Database session unavailable during packet assembly.",
                    "retryable": True,
                }
            ],
            "provenance": [],
        }

    try:
        athlete_tz = get_athlete_timezone_from_db(db, athlete_id)
        today = athlete_local_today(athlete_tz, now_utc=now_utc)
        active_plan = (
            db.query(TrainingPlan)
            .filter(
                TrainingPlan.athlete_id == athlete_id,
                TrainingPlan.status == "active",
                TrainingPlan.goal_race_date >= today,
            )
            .order_by(TrainingPlan.goal_race_date.asc())
            .first()
        )
        recent_activities = (
            db.query(Activity)
            .filter(Activity.athlete_id == athlete_id)
            .order_by(Activity.start_time.desc())
            .limit(8)
            .all()
        )
    except Exception as exc:
        return {
            "schema_version": "coach_runtime_v2.calendar_context.v1",
            "status": "unavailable",
            "generated_at": generated_at,
            "data": {
                "today_local": None,
                "today_has_completed_activity": None,
                "today_has_completed_race": None,
                "upcoming_race": None,
                "latest_completed_activity": None,
                "recent_activities": [],
            },
            "unknowns": [
                {
                    "reason": "service_unavailable",
                    "field": "calendar_context",
                    "detail": exc.__class__.__name__,
                    "retryable": True,
                }
            ],
            "provenance": [],
        }

    summaries = []
    for activity in list(recent_activities or []):
        try:
            summaries.append(
                _activity_summary(activity, today=today, athlete_tz=athlete_tz)
            )
        except Exception:
            continue

    today_summaries = [item for item in summaries if item["date"] == today.isoformat()]
    upcoming_race = None
    if active_plan and isinstance(getattr(active_plan, "goal_race_date", None), date):
        race_date = active_plan.goal_race_date
        upcoming_race = {
            "name": active_plan.goal_race_name or active_plan.name,
            "date": race_date.isoformat(),
            "distance_m": (
                int(active_plan.goal_race_distance_m)
                if active_plan.goal_race_distance_m is not None
                else None
            ),
            "days_until_race": (race_date - today).days,
            "is_today": race_date == today,
            "source": "training_plan",
            "plan_id": str(active_plan.id),
        }

    return {
        "schema_version": "coach_runtime_v2.calendar_context.v1",
        "status": "complete",
        "generated_at": generated_at,
        "data": {
            "today_local": today.isoformat(),
            "today_has_completed_activity": bool(today_summaries),
            "today_has_completed_race": any(
                item["is_race"] for item in today_summaries
            ),
            "upcoming_race": upcoming_race,
            "latest_completed_activity": summaries[0] if summaries else None,
            "recent_activities": summaries[:5],
            "temporal_authority": (
                "For dates, races, completed activities, and current-day status, "
                "this calendar_context block is authoritative. Do not infer temporal "
                "facts from legacy_context_bridge."
            ),
        },
        "unknowns": (
            []
            if upcoming_race
            else [
                {
                    "reason": "no_active_plan",
                    "field": "upcoming_race",
                    "detail": "No active future race plan found.",
                    "retryable": False,
                }
            ]
        ),
        "provenance": [
            {
                "field_path": "blocks.calendar_context.data",
                "source_system": "deterministic_computation",
                "source_id": None,
                "source_timestamp": generated_at,
                "observed_at": generated_at,
                "confidence": "high",
                "derivation_chain": ["TrainingPlan", "Activity", "athlete_timezone"],
            }
        ],
    }


def quiet_legacy_context_bridge(legacy_context: str) -> tuple[str, int]:
    kept_lines = []
    removed_count = 0
    for line in (legacy_context or "").splitlines():
        if _TEMPORAL_BRIDGE_PATTERN.search(line):
            removed_count += 1
            continue
        kept_lines.append(line)
    return "\n".join(kept_lines).strip(), removed_count


def extract_same_turn_overrides(message: str) -> list[dict[str, Any]]:
    lower = (message or "").lower()
    extracted_at = _utc_now_iso()
    overrides: list[dict[str, Any]] = []
    activity_override = _parse_activity_classification_override(message)
    execution_override = _parse_execution_quality_override(message)

    patterns = (
        (
            "subjective_state.fatigue",
            ("i'm tired", "im tired", "i am tired", "fatigued", "exhausted"),
            "current_turn",
        ),
        (
            "subjective_state.pain",
            ("pain", "hurts", "sore", "niggle", "calf", "knee", "achilles"),
            "current_turn",
        ),
        (
            "correction.current_turn",
            ("that's wrong", "that is wrong", "not true", "actually", "you missed"),
            "current_turn",
        ),
        (
            "race_context.current_turn",
            ("race today", "race day", "racing today", "5k today", "marathon today"),
            "current_turn",
        ),
        (
            "standing_overrides.coaching_boundary",
            (
                "no population models",
                "don't operate on population models",
                "do not operate on population models",
                "no fueling advice",
                "don't give me fueling advice",
                "do not give me fueling advice",
                "only do trap bar deadlifts",
                "my recovery is much faster",
            ),
            "standing",
        ),
    )
    for field_path, triggers, duration in patterns:
        if any(trigger in lower for trigger in triggers):
            overrides.append(
                {
                    "field_path": field_path,
                    "override_value": _override_value(
                        {"athlete_statement": message},
                        duration=duration,
                    ),
                    "athlete_statement": message,
                    "extracted_at": extracted_at,
                    "extractor_version": "coach_same_turn_extractor_v2_0_a",
                    "confidence": "high",
                    "expires": duration,
                    "provenance": [
                        {
                            "field_path": field_path,
                            "source_system": "athlete_stated",
                            "source_id": None,
                            "source_timestamp": extracted_at,
                            "observed_at": extracted_at,
                            "confidence": "high",
                            "derivation_chain": ["same_turn_regex"],
                        }
                    ],
                }
            )
    if activity_override is not None:
        field_path = "activity_classification_override.recent_activity"
        overrides.append(
            {
                "field_path": field_path,
                "override_value": _override_value(
                    activity_override,
                    duration="current_turn",
                ),
                "athlete_statement": message,
                "extracted_at": extracted_at,
                "extractor_version": "coach_same_turn_extractor_v2_0_a",
                "confidence": "high",
                "expires": "current_turn",
                "provenance": [
                    {
                        "field_path": field_path,
                        "source_system": "athlete_stated",
                        "source_id": None,
                        "source_timestamp": extracted_at,
                        "observed_at": extracted_at,
                        "confidence": "high",
                        "derivation_chain": ["same_turn_activity_regex"],
                    }
                ],
            }
        )
    if execution_override is not None:
        field_path = "execution_quality_override.recent_activity"
        overrides.append(
            {
                "field_path": field_path,
                "override_value": _override_value(
                    execution_override,
                    duration="current_turn",
                ),
                "athlete_statement": message,
                "extracted_at": extracted_at,
                "extractor_version": "coach_same_turn_extractor_v2_0_a",
                "confidence": "high",
                "expires": "current_turn",
                "provenance": [
                    {
                        "field_path": field_path,
                        "source_system": "athlete_stated",
                        "source_id": None,
                        "source_timestamp": extracted_at,
                        "observed_at": extracted_at,
                        "confidence": "high",
                        "derivation_chain": ["same_turn_execution_quality_regex"],
                    }
                ],
            }
        )
    return overrides


def classify_conversation_mode(
    message: str, same_turn_overrides: list[dict[str, Any]]
) -> dict[str, Any]:
    lower = (message or "").lower()
    triggers: list[str] = []
    secondary: list[str] = []

    correction_present = any(
        o["field_path"].startswith("correction.") for o in same_turn_overrides
    )
    pain_present = any(
        o["field_path"] == "subjective_state.pain" for o in same_turn_overrides
    )
    fatigue_present = any(
        o["field_path"] == "subjective_state.fatigue" for o in same_turn_overrides
    )

    if correction_present:
        primary = "correction"
        triggers.append("same_turn_correction")
    elif pain_present and any(
        term in lower for term in ("should i run", "run today", "race", "workout")
    ):
        primary = "pushback"
        triggers.append("pain_with_training_decision")
    elif any(
        term in lower
        for term in (
            "race",
            "5k",
            "10k",
            "marathon",
            "half marathon",
            "taper",
            "pace plan",
            "goal pace",
        )
    ):
        primary = "racing_preparation_judgment"
        triggers.append("race_language")
    elif any(
        term in lower
        for term in (
            "not sure",
            "confused",
            "doesn't make sense",
            "why",
            "should i",
            "what should",
        )
    ):
        primary = "engage_and_reason"
        triggers.append("reasoning_or_decision_request")
    elif any(
        term in lower
        for term in ("pb", "pr", "personal best", "nailed", "crushed", "win")
    ):
        primary = "celebration"
        triggers.append("celebration_language")
    elif any(term in lower for term in ("quick", "status", "how am i doing", "check")):
        primary = "brief_status_update"
        triggers.append("brief_status_language")
    else:
        primary = "observe_and_ask"
        triggers.append("default")

    if fatigue_present and primary != "engage_and_reason":
        secondary.append("engage_and_reason")
    if primary == "pushback":
        secondary.append("engage_and_reason")

    return {
        "primary": primary,
        "secondary": list(dict.fromkeys(secondary)),
        "query_class": detect_query_class(message),
        "confidence": "high" if triggers != ["default"] else "medium",
        "source": "deterministic_mode_classifier",
        "classifier_version": MODE_CLASSIFIER_VERSION,
        "triggers": triggers,
        "pushback": {
            "present": primary == "pushback",
            "basis": (
                "evidence_backed" if primary == "pushback" and pain_present else "none"
            ),
            "hunch_direction": "none",
            "max_repetitions_this_issue": (
                2 if primary == "pushback" and pain_present else 0
            ),
            "repeated_pushback_count": 0,
        },
        "emotional_content": {
            "present": any(
                term in lower
                for term in ("frustrated", "scared", "anxious", "excited", "stressed")
            ),
            "valence": (
                "frustrated"
                if "frustrated" in lower
                else (
                    "anxious"
                    if "anxious" in lower
                    else "positive" if "excited" in lower else "neutral"
                )
            ),
            "intensity": (
                "medium"
                if any(
                    term in lower
                    for term in (
                        "frustrated",
                        "scared",
                        "anxious",
                        "excited",
                        "stressed",
                    )
                )
                else "low"
            ),
        },
        "screen_privacy": {
            "framing": (
                "direct"
                if any(
                    term in lower
                    for term in (
                        "body fat",
                        "dexa",
                        "blood",
                        "period",
                        "stress",
                        "relationship",
                    )
                )
                else "elsewhere"
            ),
            "effect": (
                "soften_display"
                if any(
                    term in lower
                    for term in (
                        "body fat",
                        "dexa",
                        "blood",
                        "period",
                        "stress",
                        "relationship",
                    )
                )
                else "none"
            ),
        },
        "unknowns": [],
        "provenance": [
            {
                "field_path": "conversation_mode.primary",
                "source_system": "deterministic_computation",
                "source_id": None,
                "source_timestamp": _utc_now_iso(),
                "observed_at": _utc_now_iso(),
                "confidence": "high" if triggers != ["default"] else "medium",
                "derivation_chain": ["same_turn_overrides", "message_regex_precedence"],
            }
        ],
    }


def assemble_v2_packet(
    *,
    athlete_id: UUID,
    db: Session | None = None,
    message: str,
    conversation_context: list[dict[str, str]],
    legacy_athlete_state: str,
    finding_id: str | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    generated_at = _utc_now_iso()
    same_turn_overrides = extract_same_turn_overrides(message)
    conversation_mode = classify_conversation_mode(message, same_turn_overrides)
    if conversation_mode["primary"] not in ARTIFACT5_MODES:
        raise V2PacketInvariantError(f"invalid_mode:{conversation_mode['primary']}")

    calendar_context = build_calendar_context_state(
        athlete_id=athlete_id,
        db=db,
        now_utc=now_utc,
    )
    activity_override = next(
        (
            _unwrap_override_value(override["override_value"])
            for override in same_turn_overrides
            if override["field_path"]
            == "activity_classification_override.recent_activity"
        ),
        None,
    )
    execution_override = next(
        (
            _unwrap_override_value(override["override_value"])
            for override in same_turn_overrides
            if override["field_path"] == "execution_quality_override.recent_activity"
        ),
        None,
    )
    activity_evidence = build_activity_evidence_state(
        athlete_id=athlete_id,
        db=db,
        calendar_context=calendar_context,
        activity_override=activity_override,
        execution_override=execution_override,
    )
    training_adaptation_context = build_training_adaptation_context(
        calendar_context=calendar_context,
        activity_evidence=activity_evidence,
    )
    unknowns = compute_unknowns(
        db,
        athlete_id,
        conversation_mode.get("query_class") or "general",
        now_utc=now_utc,
    )
    legacy_context, removed_temporal_lines_count = quiet_legacy_context_bridge(
        (legacy_athlete_state or "").strip()
    )
    if not legacy_context:
        legacy_context = (
            "Legacy bridge intentionally quieted for V2.0-a because all temporal, "
            "race, and current-day facts must come from structured packet blocks."
        )

    data = {
        "conversation": {
            "user_message": message,
            "recent_context": conversation_context[-8:],
            "finding_id": finding_id,
        },
        "calendar_context": calendar_context["data"],
        "activity_evidence_state": activity_evidence["data"],
        "training_adaptation_context": training_adaptation_context["data"],
        "unknowns": unknowns,
        "athlete_context": {
            "legacy_context_bridge": legacy_context[:12000],
            "bridge_note": (
                "Temporary V2.0-a bridge: deterministic packet carries precomputed "
                "V1 athlete state with temporal/race/current-day prose removed. "
                "The calendar_context block is authoritative for dates and races. "
                "The activity_evidence_state and training_adaptation_context blocks "
                "are authoritative for recent effort mix and taper-fitness interpretation. "
                "LLM tools are disabled."
            ),
            "removed_temporal_lines_count": removed_temporal_lines_count,
        },
    }
    token_estimate = _estimated_tokens(data)
    packet = {
        "schema_version": PACKET_SCHEMA_VERSION,
        "packet_id": str(uuid4()),
        "packet_profile": "coach_runtime_v2.visible_founder_v0",
        "assembler_version": ASSEMBLER_VERSION,
        "tier1_registry_version": "coach_runtime_v2.tier1.v1",
        "permission_policy_version": "coach_runtime_v2.permissions.v1",
        "generated_at": generated_at,
        "as_of": generated_at,
        "conversation_mode": conversation_mode,
        "athlete_stated_overrides": same_turn_overrides,
        "blocks": {
            "conversation": {
                "schema_version": "coach_runtime_v2.block.conversation.v1",
                "status": "complete",
                "generated_at": generated_at,
                "as_of": generated_at,
                "selected_sections": ["current_turn", "recent_context"],
                "available_sections": ["current_turn", "recent_context"],
                "data": data["conversation"],
                "completeness": [],
                "unknowns": [],
                "provenance": [],
                "token_budget": {
                    "target_tokens": 250,
                    "max_tokens": 450,
                    "estimated_tokens": _estimated_tokens(data["conversation"]),
                },
            },
            "calendar_context": {
                "schema_version": "coach_runtime_v2.block.calendar_context.v1",
                "status": calendar_context["status"],
                "generated_at": generated_at,
                "as_of": generated_at,
                "selected_sections": [
                    "today",
                    "upcoming_race",
                    "completed_activity_status",
                    "recent_activity_dates",
                ],
                "available_sections": [
                    "today",
                    "upcoming_race",
                    "completed_activity_status",
                    "recent_activity_dates",
                ],
                "data": data["calendar_context"],
                "completeness": [
                    {
                        "section": "calendar_context",
                        "status": calendar_context["status"],
                        "coverage_start": data["calendar_context"].get("today_local"),
                        "coverage_end": data["calendar_context"].get("today_local"),
                        "expected_window": "today plus active race plan and recent activities",
                        "detail": "Authoritative temporal/race block for V2.0-a coach responses.",
                    }
                ],
                "unknowns": calendar_context["unknowns"],
                "provenance": calendar_context["provenance"],
                "token_budget": {
                    "target_tokens": 350,
                    "max_tokens": 650,
                    "estimated_tokens": _estimated_tokens(data["calendar_context"]),
                },
            },
            "activity_evidence_state": {
                "schema_version": "coach_runtime_v2.block.activity_evidence.v1",
                "status": activity_evidence["status"],
                "generated_at": generated_at,
                "as_of": generated_at,
                "selected_sections": [
                    "recent_activity_effort",
                    "yesterday_effort_mix",
                    "same_turn_activity_override",
                ],
                "available_sections": [
                    "recent_activity_effort",
                    "yesterday_effort_mix",
                    "same_turn_activity_override",
                ],
                "data": data["activity_evidence_state"],
                "completeness": [
                    {
                        "section": "activity_evidence",
                        "status": activity_evidence["status"],
                        "coverage_start": (
                            data["activity_evidence_state"].get("yesterday") or {}
                        ).get("date"),
                        "coverage_end": data["calendar_context"].get("today_local"),
                        "expected_window": "recent runs with yesterday grouped",
                        "detail": "Classifies activity effort from pace, duration, race flags, effort classifier output, and same-turn athlete corrections; labels alone are not authoritative.",
                    }
                ],
                "unknowns": activity_evidence["unknowns"],
                "provenance": activity_evidence["provenance"],
                "token_budget": {
                    "target_tokens": 650,
                    "max_tokens": 1000,
                    "estimated_tokens": _estimated_tokens(
                        data["activity_evidence_state"]
                    ),
                },
            },
            "training_adaptation_context": {
                "schema_version": "coach_runtime_v2.block.training_adaptation.v1",
                "status": training_adaptation_context["status"],
                "generated_at": generated_at,
                "as_of": generated_at,
                "selected_sections": [
                    "recent_stimulus_interpretation",
                    "target_race_timing",
                    "recommendation_bias",
                ],
                "available_sections": [
                    "recent_stimulus_interpretation",
                    "target_race_timing",
                    "recommendation_bias",
                ],
                "data": data["training_adaptation_context"],
                "completeness": [
                    {
                        "section": "training_adaptation",
                        "status": training_adaptation_context["status"],
                        "coverage_start": (
                            data["activity_evidence_state"].get("yesterday") or {}
                        ).get("date"),
                        "coverage_end": data["calendar_context"].get("today_local"),
                        "expected_window": "recent stimulus against active target race",
                        "detail": "Deterministic physiology interpretation: what the recent effort likely changes before the target race.",
                    }
                ],
                "unknowns": training_adaptation_context["unknowns"],
                "provenance": training_adaptation_context["provenance"],
                "token_budget": {
                    "target_tokens": 300,
                    "max_tokens": 550,
                    "estimated_tokens": _estimated_tokens(
                        data["training_adaptation_context"]
                    ),
                },
            },
            "unknowns": {
                "schema_version": "coach_runtime_v2.block.unknowns.v1",
                "status": "complete",
                "generated_at": generated_at,
                "as_of": generated_at,
                "selected_sections": ["required_ledger_fields"],
                "available_sections": ["required_ledger_fields"],
                "data": data["unknowns"],
                "completeness": [],
                "unknowns": data["unknowns"],
                "provenance": [
                    {
                        "field_path": "blocks.unknowns.data",
                        "source_system": "athlete_facts_ledger",
                        "source_id": str(athlete_id),
                        "source_timestamp": generated_at,
                        "observed_at": generated_at,
                        "confidence": "high",
                        "derivation_chain": [
                            "conversation_mode.query_class",
                            "unknowns_block.required_field_map",
                            "athlete_facts.confirm_after",
                        ],
                    }
                ],
                "token_budget": {
                    "target_tokens": 250,
                    "max_tokens": 450,
                    "estimated_tokens": _estimated_tokens(data["unknowns"]),
                },
            },
            "athlete_context": {
                "schema_version": "coach_runtime_v2.block.athlete_context.v1",
                "status": "partial",
                "generated_at": generated_at,
                "as_of": generated_at,
                "selected_sections": ["legacy_context_bridge"],
                "available_sections": ["legacy_context_bridge"],
                "data": data["athlete_context"],
                "completeness": [
                    {
                        "section": "tier1_native_state",
                        "status": "partial",
                        "coverage_start": None,
                        "coverage_end": None,
                        "expected_window": "V2.0-a first visible slice",
                        "detail": "Native Tier 1 modules are not all cut over; packet uses deterministic legacy context bridge without exposing tools to the LLM.",
                    }
                ],
                "unknowns": [],
                "provenance": [
                    {
                        "field_path": "blocks.athlete_context.data.legacy_context_bridge",
                        "source_system": "deterministic_computation",
                        "source_id": None,
                        "source_timestamp": generated_at,
                        "observed_at": generated_at,
                        "confidence": "medium",
                        "derivation_chain": [
                            "AICoach._build_athlete_state_for_opus",
                            "packet_bridge",
                        ],
                    }
                ],
                "token_budget": {
                    "target_tokens": 1800,
                    "max_tokens": 3200,
                    "estimated_tokens": _estimated_tokens(data["athlete_context"]),
                },
            },
        },
        "omitted_blocks": [],
        "telemetry": {
            "estimated_tokens": token_estimate,
            "packet_block_count": 6,
            "omitted_block_count": 0,
            "unknown_count": (
                len(calendar_context["unknowns"])
                + len(activity_evidence["unknowns"])
                + len(training_adaptation_context["unknowns"])
                + len(unknowns)
            ),
            "permission_redaction_count": 0,
            "coupling_count": 1,
            "multimodal_attachment_count": 0,
            "temporal_bridge_lines_removed": removed_temporal_lines_count,
        },
    }
    if token_estimate > 5000:
        raise V2PacketInvariantError("packet_token_budget_exceeded")
    return packet


def packet_to_prompt(packet: dict[str, Any]) -> str:
    return json.dumps(packet, ensure_ascii=True, sort_keys=True, default=str)
