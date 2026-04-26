from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from models import Activity, TrainingPlan
from services.coaching.runtime_v2 import PACKET_SCHEMA_VERSION
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

    patterns = (
        (
            "subjective_state.fatigue",
            ("i'm tired", "im tired", "i am tired", "fatigued", "exhausted"),
        ),
        (
            "subjective_state.pain",
            ("pain", "hurts", "sore", "niggle", "calf", "knee", "achilles"),
        ),
        (
            "correction.current_turn",
            ("that's wrong", "that is wrong", "not true", "actually", "you missed"),
        ),
        (
            "race_context.current_turn",
            ("race today", "race day", "racing today", "5k today", "marathon today"),
        ),
    )
    for field_path, triggers in patterns:
        if any(trigger in lower for trigger in triggers):
            overrides.append(
                {
                    "field_path": field_path,
                    "override_value": True,
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
                            "derivation_chain": ["same_turn_regex"],
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
        "athlete_context": {
            "legacy_context_bridge": legacy_context[:12000],
            "bridge_note": (
                "Temporary V2.0-a bridge: deterministic packet carries precomputed "
                "V1 athlete state with temporal/race/current-day prose removed. "
                "The calendar_context block is authoritative for dates, races, "
                "completed activities, and current-day status. LLM tools are disabled."
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
            "packet_block_count": 3,
            "omitted_block_count": 0,
            "unknown_count": len(calendar_context["unknowns"]),
            "permission_redaction_count": 0,
            "coupling_count": 0,
            "multimodal_attachment_count": 0,
            "temporal_bridge_lines_removed": removed_temporal_lines_count,
        },
    }
    if token_estimate > 5000:
        raise V2PacketInvariantError("packet_token_budget_exceeded")
    return packet


def packet_to_prompt(packet: dict[str, Any]) -> str:
    return json.dumps(packet, ensure_ascii=True, sort_keys=True, default=str)
