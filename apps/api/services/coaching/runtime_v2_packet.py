from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from services.coaching.runtime_v2 import PACKET_SCHEMA_VERSION

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


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _estimated_tokens(value: Any) -> int:
    text = json.dumps(value, ensure_ascii=True, sort_keys=True, default=str)
    return max(1, len(text) // 4)


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
    message: str,
    conversation_context: list[dict[str, str]],
    legacy_athlete_state: str,
    finding_id: str | None = None,
) -> dict[str, Any]:
    generated_at = _utc_now_iso()
    same_turn_overrides = extract_same_turn_overrides(message)
    conversation_mode = classify_conversation_mode(message, same_turn_overrides)
    if conversation_mode["primary"] not in ARTIFACT5_MODES:
        raise V2PacketInvariantError(f"invalid_mode:{conversation_mode['primary']}")

    legacy_context = (legacy_athlete_state or "").strip()
    if not legacy_context:
        raise V2PacketInvariantError("missing_athlete_context")

    data = {
        "conversation": {
            "user_message": message,
            "recent_context": conversation_context[-8:],
            "finding_id": finding_id,
        },
        "athlete_context": {
            "legacy_context_bridge": legacy_context[:12000],
            "bridge_note": "Temporary V2.0-a bridge: deterministic packet carries precomputed V1 athlete state; LLM tools are disabled.",
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
            "packet_block_count": 2,
            "omitted_block_count": 0,
            "unknown_count": 0,
            "permission_redaction_count": 0,
            "coupling_count": 0,
            "multimodal_attachment_count": 0,
        },
    }
    if token_estimate > 5000:
        raise V2PacketInvariantError("packet_token_budget_exceeded")
    return packet


def packet_to_prompt(packet: dict[str, Any]) -> str:
    return json.dumps(packet, ensure_ascii=True, sort_keys=True, default=str)
