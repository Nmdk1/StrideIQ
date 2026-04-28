from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, replace
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from services.plan_framework.feature_flags import FeatureFlagService

logger = logging.getLogger(__name__)

COACH_RUNTIME_V2_SHADOW_FLAG = "coach.runtime_v2.shadow"
COACH_RUNTIME_V2_VISIBLE_FLAG = "coach.runtime_v2.visible"
COACH_RUNTIME_V2_DEFAULT_SITEWIDE = True

RUNTIME_MODE_OFF = "off"
RUNTIME_MODE_SHADOW = "shadow"
RUNTIME_MODE_VISIBLE = "visible"
RUNTIME_MODE_FALLBACK = "fallback"

RUNTIME_VERSION_V1 = "v1"
RUNTIME_VERSION_V2 = "v2"

PACKET_SCHEMA_VERSION = "coach_runtime_v2.packet.v1"


def _athlete_hash(athlete_id: UUID | str | None) -> str | None:
    if not athlete_id:
        return None
    return hashlib.sha256(str(athlete_id).encode("utf-8")).hexdigest()[:12]


def is_coach_runtime_v2_enabled(
    flag_key: str, athlete_id: UUID | str | None, db: Session
) -> bool:
    """Fail-closed V2 flag check.

    Do not use ``core.feature_flags.is_feature_enabled`` here. That convenience
    wrapper intentionally fails open for legacy feature surfaces, which is not
    safe for coach runtime selection.
    """

    athlete_hash = _athlete_hash(athlete_id)
    try:
        if not athlete_id:
            enabled = False
        else:
            enabled = FeatureFlagService(db).is_enabled(flag_key, athlete_id) is True
    except Exception as exc:
        enabled = False
        logger.warning(
            "coach_runtime_v2_flag_exception",
            extra={
                "extra_fields": {
                    "event": "coach_runtime_v2_flag_exception",
                    "flag_key": flag_key,
                    "athlete_id_hash": athlete_hash,
                    "enabled": False,
                    "error_class": exc.__class__.__name__,
                }
            },
        )

    logger.info(
        "coach_runtime_v2_flag_decision",
        extra={
            "extra_fields": {
                "event": "coach_runtime_v2_flag_decision",
                "flag_key": flag_key,
                "athlete_id_hash": athlete_hash,
                "enabled": enabled,
            }
        },
    )
    return enabled


@dataclass(frozen=True)
class CoachRuntimeV2State:
    runtime_mode: str
    runtime_version: str
    shadow_enabled: bool
    visible_enabled: bool
    fallback_reason: str | None = None

    def as_metadata(self) -> dict[str, Any]:
        return {
            "runtime_version": self.runtime_version,
            "runtime_mode": self.runtime_mode,
            "fallback_reason": self.fallback_reason,
        }

    def as_fallback(self, reason: str) -> "CoachRuntimeV2State":
        return replace(
            self,
            runtime_mode=RUNTIME_MODE_FALLBACK,
            runtime_version=RUNTIME_VERSION_V1,
            fallback_reason=reason,
        )

    def with_failure_reason(self, reason: str) -> "CoachRuntimeV2State":
        return replace(self, fallback_reason=reason)


def resolve_coach_runtime_v2_state(
    athlete_id: UUID | str | None, db: Session
) -> CoachRuntimeV2State:
    if COACH_RUNTIME_V2_DEFAULT_SITEWIDE and athlete_id:
        # V2 is now the production coach, not a founder/pilot rollout. Keep the
        # flag rows for audit/config visibility, but never block a real athlete
        # from the only supported chat runtime because a rollout allowlist drifted.
        return CoachRuntimeV2State(
            runtime_mode=RUNTIME_MODE_VISIBLE,
            runtime_version=RUNTIME_VERSION_V2,
            shadow_enabled=True,
            visible_enabled=True,
        )

    shadow_enabled = is_coach_runtime_v2_enabled(
        COACH_RUNTIME_V2_SHADOW_FLAG, athlete_id, db
    )
    visible_enabled = is_coach_runtime_v2_enabled(
        COACH_RUNTIME_V2_VISIBLE_FLAG, athlete_id, db
    )

    if visible_enabled:
        return CoachRuntimeV2State(
            runtime_mode=RUNTIME_MODE_VISIBLE,
            runtime_version=RUNTIME_VERSION_V2,
            shadow_enabled=shadow_enabled,
            visible_enabled=True,
        )
    if shadow_enabled:
        return CoachRuntimeV2State(
            runtime_mode=RUNTIME_MODE_SHADOW,
            runtime_version=RUNTIME_VERSION_V1,
            shadow_enabled=True,
            visible_enabled=False,
        )
    return CoachRuntimeV2State(
        runtime_mode=RUNTIME_MODE_OFF,
        runtime_version=RUNTIME_VERSION_V1,
        shadow_enabled=False,
        visible_enabled=False,
    )


def log_coach_runtime_v2_request(
    *,
    athlete_id: UUID | str | None,
    state: CoachRuntimeV2State,
    thread_id: str | None,
    latency_ms_total: int,
    llm_model: str | None = None,
    tool_count: int = 0,
    error_class: str | None = None,
    packet_telemetry: dict[str, Any] | None = None,
) -> None:
    """Emit the umbrella V2 runtime event without raw athlete text."""

    if not (
        state.shadow_enabled
        or state.visible_enabled
        or state.runtime_mode == RUNTIME_MODE_FALLBACK
    ):
        return
    packet_telemetry = packet_telemetry or {}

    logger.info(
        "coach_runtime_v2_request",
        extra={
            "extra_fields": {
                "event": "coach_runtime_v2_request",
                "athlete_id_hash": _athlete_hash(athlete_id),
                "thread_id": thread_id,
                "runtime_mode": state.runtime_mode,
                "runtime_version": state.runtime_version,
                "flag_shadow": state.shadow_enabled,
                "flag_visible": state.visible_enabled,
                "artifact_packet_schema_version": PACKET_SCHEMA_VERSION,
                "artifact_mode": packet_telemetry.get("artifact_mode"),
                "artifact5_mode_confidence": packet_telemetry.get(
                    "artifact5_mode_confidence", 0.0
                ),
                "packet_estimated_tokens": int(
                    packet_telemetry.get("estimated_tokens", 0) or 0
                ),
                "packet_block_count": int(
                    packet_telemetry.get("packet_block_count", 0) or 0
                ),
                "omitted_block_count": int(
                    packet_telemetry.get("omitted_block_count", 0) or 0
                ),
                "unknown_count": int(packet_telemetry.get("unknown_count", 0) or 0),
                "permission_redaction_count": int(
                    packet_telemetry.get("permission_redaction_count", 0) or 0
                ),
                "coupling_count": int(packet_telemetry.get("coupling_count", 0) or 0),
                "multimodal_attachment_count": int(
                    packet_telemetry.get("multimodal_attachment_count", 0) or 0
                ),
                "deterministic_check_status": packet_telemetry.get(
                    "deterministic_check_status", "skipped"
                ),
                "fallback_reason": state.fallback_reason,
                "llm_model": llm_model,
                "latency_ms_total": max(0, int(latency_ms_total)),
                "latency_ms_packet": max(
                    0, int(packet_telemetry.get("latency_ms_packet", 0) or 0)
                ),
                "latency_ms_llm": max(
                    0, int(packet_telemetry.get("latency_ms_llm", 0) or 0)
                ),
                "tool_count": int(tool_count or 0),
                "error_class": error_class,
            }
        },
    )


def assert_runtime_metadata_consistent(metadata: dict[str, Any]) -> None:
    mode = metadata.get("runtime_mode")
    version = metadata.get("runtime_version")
    if mode == RUNTIME_MODE_FALLBACK and version != RUNTIME_VERSION_V1:
        raise ValueError("fallback runtime mode must serve V1")
    if mode == RUNTIME_MODE_VISIBLE and version != RUNTIME_VERSION_V2:
        raise ValueError("visible runtime mode must serve V2")
