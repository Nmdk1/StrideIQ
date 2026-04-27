import inspect
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from services.ai_coach import AICoach
from services.coaching import core as coach_core
from services.coaching.runtime_v2 import (
    COACH_RUNTIME_V2_SHADOW_FLAG,
    COACH_RUNTIME_V2_VISIBLE_FLAG,
    RUNTIME_MODE_FALLBACK,
    RUNTIME_MODE_OFF,
    RUNTIME_MODE_SHADOW,
    RUNTIME_MODE_VISIBLE,
    RUNTIME_VERSION_V1,
    RUNTIME_VERSION_V2,
    CoachRuntimeV2State,
    assert_runtime_metadata_consistent,
    is_coach_runtime_v2_enabled,
    resolve_coach_runtime_v2_state,
)
from services.coaching.runtime_v2_packet import (
    V2PacketInvariantError,
    assemble_v2_packet,
    classify_conversation_mode,
    extract_same_turn_overrides,
    packet_to_prompt,
)
from services.coaching import runtime_v2
from services.coaching import runtime_v2_packet as packet_module
from routers.ai_coach import ChatResponse


class _FlagService:
    def __init__(self, flags):
        self.flags = flags

    def is_enabled(self, flag_key, athlete_id):
        return self.flags.get(flag_key, False)


def _coach_with_v1_path() -> AICoach:
    coach = AICoach(db=MagicMock())
    coach.router = MagicMock()
    coach.router.classify = MagicMock(return_value=(None, False))
    coach.gemini_client = None
    coach.anthropic_client = object()
    coach.classify_query_complexity = MagicMock(return_value="high")
    coach.get_model_for_query = MagicMock(return_value=(coach.MODEL_HIGH_STAKES, True))
    coach.is_athlete_vip = MagicMock(return_value=False)
    coach.check_budget = MagicMock(return_value=(True, "ok"))
    coach._is_profile_edit_intent = MagicMock(return_value=False)
    coach._maybe_update_units_preference = MagicMock()
    coach._maybe_update_intent_snapshot = MagicMock()
    coach._thin_history_and_baseline_flags = MagicMock(
        return_value=(False, {}, None, False)
    )
    coach.get_or_create_thread_with_state = MagicMock(return_value=("thread-1", False))
    coach.get_thread_history = MagicMock(return_value={"messages": []})
    coach._build_athlete_state_for_opus = MagicMock(return_value="state")
    coach._query_kimi_with_fallback = AsyncMock(
        return_value={"response": "kimi", "error": False, "model": "kimi-k2.6"}
    )
    coach.query_kimi_v2_packet = AsyncMock(
        return_value={
            "response": "v2 answer",
            "error": False,
            "model": "kimi-k2.6",
            "tools_called": [],
        }
    )
    coach.query_opus = AsyncMock(
        return_value={
            "response": "sonnet",
            "error": False,
            "model": "claude-sonnet-4-6",
        }
    )
    coach._finalize_response_with_turn_guard = AsyncMock(
        side_effect=lambda **kwargs: kwargs["response_text"]
    )
    coach._normalize_response_for_ui = MagicMock(
        side_effect=lambda user_message, assistant_message: assistant_message
    )
    coach._record_turn_guard_event = MagicMock()
    coach._save_chat_messages = MagicMock()
    return coach


def test_v2_flag_helper_fails_closed_on_exception(monkeypatch):
    class ExplodingFlagService:
        def __init__(self, db):
            pass

        def is_enabled(self, flag_key, athlete_id):
            raise RuntimeError("database unavailable")

    monkeypatch.setattr(runtime_v2, "FeatureFlagService", ExplodingFlagService)

    assert (
        is_coach_runtime_v2_enabled(COACH_RUNTIME_V2_SHADOW_FLAG, uuid4(), MagicMock())
        is False
    )


def test_v2_flag_helper_requires_explicit_true(monkeypatch):
    class WeirdFlagService:
        def __init__(self, db):
            pass

        def is_enabled(self, flag_key, athlete_id):
            return MagicMock()

    monkeypatch.setattr(runtime_v2, "FeatureFlagService", WeirdFlagService)

    assert (
        is_coach_runtime_v2_enabled(COACH_RUNTIME_V2_VISIBLE_FLAG, uuid4(), MagicMock())
        is False
    )


def test_v2_flag_helper_does_not_delegate_to_generic_fail_open_helper():
    source = inspect.getsource(is_coach_runtime_v2_enabled)
    assert "core.feature_flags import" not in source
    assert "is_feature_enabled(" not in source


def test_runtime_resolver_uses_visible_over_shadow(monkeypatch):
    flags = {
        COACH_RUNTIME_V2_SHADOW_FLAG: True,
        COACH_RUNTIME_V2_VISIBLE_FLAG: True,
    }
    monkeypatch.setattr(
        runtime_v2, "FeatureFlagService", lambda db: _FlagService(flags)
    )

    state = resolve_coach_runtime_v2_state(uuid4(), MagicMock())

    assert state.runtime_mode == RUNTIME_MODE_VISIBLE
    assert state.runtime_version == RUNTIME_VERSION_V2
    assert state.shadow_enabled is True
    assert state.visible_enabled is True


def test_runtime_resolver_distinguishes_off_and_shadow(monkeypatch):
    flags = {
        COACH_RUNTIME_V2_SHADOW_FLAG: True,
        COACH_RUNTIME_V2_VISIBLE_FLAG: False,
    }
    monkeypatch.setattr(
        runtime_v2, "FeatureFlagService", lambda db: _FlagService(flags)
    )

    shadow_state = resolve_coach_runtime_v2_state(uuid4(), MagicMock())
    assert shadow_state.runtime_mode == RUNTIME_MODE_SHADOW
    assert shadow_state.runtime_version == RUNTIME_VERSION_V1

    monkeypatch.setattr(runtime_v2, "FeatureFlagService", lambda db: _FlagService({}))
    off_state = resolve_coach_runtime_v2_state(uuid4(), MagicMock())
    assert off_state.runtime_mode == RUNTIME_MODE_OFF
    assert off_state.runtime_version == RUNTIME_VERSION_V1


def test_runtime_metadata_consistency_contract():
    assert_runtime_metadata_consistent(
        {"runtime_mode": RUNTIME_MODE_VISIBLE, "runtime_version": RUNTIME_VERSION_V2}
    )
    assert_runtime_metadata_consistent(
        {"runtime_mode": RUNTIME_MODE_FALLBACK, "runtime_version": RUNTIME_VERSION_V1}
    )

    with pytest.raises(ValueError):
        assert_runtime_metadata_consistent(
            {
                "runtime_mode": RUNTIME_MODE_FALLBACK,
                "runtime_version": RUNTIME_VERSION_V2,
            }
        )


def test_chat_response_exposes_runtime_metadata_defaults_and_overrides():
    default_response = ChatResponse(response="ok")
    assert default_response.runtime_version == RUNTIME_VERSION_V1
    assert default_response.runtime_mode == RUNTIME_MODE_OFF
    assert default_response.fallback_reason is None

    fallback_response = ChatResponse(
        response="ok",
        runtime_version=RUNTIME_VERSION_V1,
        runtime_mode=RUNTIME_MODE_FALLBACK,
        fallback_reason="timeout",
    )
    assert fallback_response.runtime_mode == RUNTIME_MODE_FALLBACK
    assert fallback_response.fallback_reason == "timeout"


def _visible_state():
    return CoachRuntimeV2State(
        runtime_mode=RUNTIME_MODE_VISIBLE,
        runtime_version=RUNTIME_VERSION_V2,
        shadow_enabled=True,
        visible_enabled=True,
    )


@pytest.mark.asyncio
async def test_flags_off_chat_fails_closed_without_v1(monkeypatch):
    import services.consent as consent_module

    coach = _coach_with_v1_path()
    extract_spy = AsyncMock(return_value=[])
    monkeypatch.setattr(consent_module, "has_ai_consent", lambda athlete_id, db: True)
    monkeypatch.setattr(
        coach_core,
        "extract_facts_from_turn_with_optional_llm",
        extract_spy,
    )
    monkeypatch.setattr(
        coach_core,
        "resolve_coach_runtime_v2_state",
        lambda athlete_id, db: CoachRuntimeV2State(
            runtime_mode=RUNTIME_MODE_OFF,
            runtime_version=RUNTIME_VERSION_V1,
            shadow_enabled=False,
            visible_enabled=False,
        ),
    )

    result = await coach.chat(uuid4(), "My knee hurts. Should I run?")

    assert "legacy coach" in result["response"]
    assert result["error"] is True
    assert result["runtime_version"] == RUNTIME_VERSION_V1
    assert result["runtime_mode"] == RUNTIME_MODE_OFF
    assert result["fallback_reason"] is None
    coach._query_kimi_with_fallback.assert_not_awaited()
    coach.query_opus.assert_not_awaited()
    extract_spy.assert_not_awaited()
    coach._save_chat_messages.assert_not_called()


@pytest.mark.asyncio
async def test_shadow_mode_fails_closed_without_v1(monkeypatch):
    import services.consent as consent_module

    coach = _coach_with_v1_path()
    monkeypatch.setattr(consent_module, "has_ai_consent", lambda athlete_id, db: True)
    monkeypatch.setattr(
        coach_core,
        "resolve_coach_runtime_v2_state",
        lambda athlete_id, db: CoachRuntimeV2State(
            runtime_mode=RUNTIME_MODE_SHADOW,
            runtime_version=RUNTIME_VERSION_V1,
            shadow_enabled=True,
            visible_enabled=False,
        ),
    )

    result = await coach.chat(uuid4(), "How should I adjust today?")

    assert result["runtime_mode"] == RUNTIME_MODE_SHADOW
    assert result["runtime_version"] == RUNTIME_VERSION_V1
    assert result["error"] is True
    coach._query_kimi_with_fallback.assert_not_awaited()


@pytest.mark.asyncio
async def test_visible_mode_uses_v2_packet_path_when_success(monkeypatch):
    import services.consent as consent_module

    coach = _coach_with_v1_path()
    proposed_fact = SimpleNamespace(field="age", value=57)
    extract_spy = AsyncMock(return_value=[proposed_fact])
    persist_spy = MagicMock(return_value=[])
    monkeypatch.setattr(consent_module, "has_ai_consent", lambda athlete_id, db: True)
    monkeypatch.setattr(
        coach_core,
        "extract_facts_from_turn_with_optional_llm",
        extract_spy,
    )
    monkeypatch.setattr(coach_core, "persist_proposed_facts", persist_spy)
    monkeypatch.setattr(
        coach_core,
        "resolve_coach_runtime_v2_state",
        lambda athlete_id, db: _visible_state(),
    )

    result = await coach.chat(uuid4(), "Talk me through race week.")

    assert result["response"] == "v2 answer"
    assert result["runtime_mode"] == RUNTIME_MODE_VISIBLE
    assert result["runtime_version"] == RUNTIME_VERSION_V2
    assert result["fallback_reason"] is None
    coach.query_kimi_v2_packet.assert_awaited_once()
    coach._query_kimi_with_fallback.assert_not_awaited()
    coach._finalize_response_with_turn_guard.assert_not_awaited()
    extract_spy.assert_awaited_once()
    persist_spy.assert_called_once()
    coach.db.commit.assert_called_once()
    _, kwargs = coach._save_chat_messages.call_args
    assert kwargs["runtime_metadata"] == {
        "runtime_version": RUNTIME_VERSION_V2,
        "runtime_mode": RUNTIME_MODE_VISIBLE,
        "fallback_reason": None,
        "template_phrase_count": 0,
        "anchor_atoms_per_answer": 0,
        "unasked_surfacing": False,
        "ledger_field_coverage": 0.0,
        "unknowns_count": 0,
    }


@pytest.mark.asyncio
async def test_visible_mode_fails_closed_when_v2_turn_guard_fails(monkeypatch):
    import services.consent as consent_module

    coach = _coach_with_v1_path()
    coach.query_kimi_v2_packet = AsyncMock(
        return_value={
            "response": "You have been training a lot lately, so think about how you feel.",
            "error": False,
            "model": "kimi-k2.6",
            "tools_called": [],
        }
    )
    monkeypatch.setattr(consent_module, "has_ai_consent", lambda athlete_id, db: True)
    monkeypatch.setattr(
        coach_core,
        "extract_facts_from_turn_with_optional_llm",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        coach_core,
        "resolve_coach_runtime_v2_state",
        lambda athlete_id, db: _visible_state(),
    )

    result = await coach.chat(uuid4(), "Should I postpone threshold tomorrow?")

    assert "stopped instead of guessing" in result["response"]
    assert result["runtime_mode"] == RUNTIME_MODE_VISIBLE
    assert result["runtime_version"] == RUNTIME_VERSION_V2
    assert result["fallback_reason"] == "v2_guardrail_failed"
    coach.query_kimi_v2_packet.assert_awaited_once()
    coach._query_kimi_with_fallback.assert_not_awaited()


@pytest.mark.asyncio
async def test_visible_packet_assembly_failure_fails_closed_without_v1(monkeypatch):
    import services.consent as consent_module

    coach = _coach_with_v1_path()
    monkeypatch.setattr(consent_module, "has_ai_consent", lambda athlete_id, db: True)
    monkeypatch.setattr(
        coach_core,
        "resolve_coach_runtime_v2_state",
        lambda athlete_id, db: _visible_state(),
    )
    monkeypatch.setattr(
        coach_core,
        "assemble_v2_packet",
        MagicMock(side_effect=V2PacketInvariantError("missing_athlete_context")),
    )

    result = await coach.chat(uuid4(), "Talk me through race week.")

    assert "stopped instead of guessing" in result["response"]
    assert result["runtime_mode"] == RUNTIME_MODE_VISIBLE
    assert result["runtime_version"] == RUNTIME_VERSION_V2
    assert result["fallback_reason"] == "packet_assembly_error"
    coach.query_kimi_v2_packet.assert_not_awaited()
    coach._query_kimi_with_fallback.assert_not_awaited()


@pytest.mark.asyncio
async def test_visible_v2_empty_response_fails_closed_without_v1(monkeypatch):
    import services.consent as consent_module

    coach = _coach_with_v1_path()
    coach.query_kimi_v2_packet = AsyncMock(
        return_value={
            "response": "",
            "error": True,
            "model": "kimi-k2.6",
            "fallback_reason": "v2_empty_response",
        }
    )
    monkeypatch.setattr(consent_module, "has_ai_consent", lambda athlete_id, db: True)
    monkeypatch.setattr(
        coach_core,
        "resolve_coach_runtime_v2_state",
        lambda athlete_id, db: _visible_state(),
    )

    result = await coach.chat(uuid4(), "Talk me through race week.")

    assert "stopped instead of guessing" in result["response"]
    assert result["runtime_mode"] == RUNTIME_MODE_VISIBLE
    assert result["runtime_version"] == RUNTIME_VERSION_V2
    assert result["fallback_reason"] == "v2_empty_response"
    coach.query_kimi_v2_packet.assert_awaited_once()
    coach._query_kimi_with_fallback.assert_not_awaited()


@pytest.mark.asyncio
async def test_visible_v2_timeout_fails_closed_without_v1(monkeypatch):
    import services.consent as consent_module

    coach = _coach_with_v1_path()
    coach.query_kimi_v2_packet = AsyncMock(
        return_value={
            "response": "",
            "error": True,
            "model": "kimi-k2.6",
            "fallback_reason": "v2_timeout",
            "kimi_latency_ms": 120000,
        }
    )
    monkeypatch.setattr(consent_module, "has_ai_consent", lambda athlete_id, db: True)
    monkeypatch.setattr(
        coach_core,
        "resolve_coach_runtime_v2_state",
        lambda athlete_id, db: _visible_state(),
    )

    result = await coach.chat(uuid4(), "Talk me through race week.")

    assert "stopped instead of guessing" in result["response"]
    assert result["runtime_mode"] == RUNTIME_MODE_VISIBLE
    assert result["runtime_version"] == RUNTIME_VERSION_V2
    assert result["fallback_reason"] == "v2_timeout"
    coach.query_kimi_v2_packet.assert_awaited_once()
    coach._query_kimi_with_fallback.assert_not_awaited()


@pytest.mark.asyncio
async def test_visible_profile_short_circuit_persists_v2_metadata(monkeypatch):
    import services.consent as consent_module

    coach = _coach_with_v1_path()
    coach._is_profile_edit_intent = MagicMock(return_value=True)
    coach._infer_profile_field_from_message = MagicMock(return_value="birthdate")
    coach._normalize_response_for_ui = MagicMock(
        side_effect=lambda user_message, assistant_message: assistant_message
    )
    coach._record_turn_guard_event = MagicMock()
    monkeypatch.setattr(consent_module, "has_ai_consent", lambda athlete_id, db: True)
    monkeypatch.setattr(
        coach_core,
        "resolve_coach_runtime_v2_state",
        lambda athlete_id, db: _visible_state(),
    )

    result = await coach.chat(uuid4(), "Where do I change my birthdate?")

    assert result["runtime_mode"] == RUNTIME_MODE_VISIBLE
    assert result["runtime_version"] == RUNTIME_VERSION_V2
    assert result["fallback_reason"] is None
    _, kwargs = coach._save_chat_messages.call_args
    assert kwargs["runtime_metadata"] == {
        "runtime_version": RUNTIME_VERSION_V2,
        "runtime_mode": RUNTIME_MODE_VISIBLE,
        "fallback_reason": None,
    }


@pytest.mark.asyncio
async def test_visible_consent_disabled_response_fails_closed_without_v1(monkeypatch):
    import services.consent as consent_module

    coach = _coach_with_v1_path()
    monkeypatch.setattr(consent_module, "has_ai_consent", lambda athlete_id, db: False)
    monkeypatch.setattr(
        coach_core,
        "resolve_coach_runtime_v2_state",
        lambda athlete_id, db: _visible_state(),
    )

    result = await coach.chat(uuid4(), "Can you coach me?")

    assert result["runtime_mode"] == RUNTIME_MODE_VISIBLE
    assert result["runtime_version"] == RUNTIME_VERSION_V2
    assert result["fallback_reason"] == "consent_disabled"
    coach._query_kimi_with_fallback.assert_not_awaited()


@pytest.mark.asyncio
async def test_visible_budget_exceeded_response_fails_closed_without_v1(monkeypatch):
    import services.consent as consent_module

    coach = _coach_with_v1_path()
    coach.check_budget = MagicMock(return_value=(False, "daily_limit"))
    monkeypatch.setattr(consent_module, "has_ai_consent", lambda athlete_id, db: True)
    monkeypatch.setattr(
        coach_core,
        "resolve_coach_runtime_v2_state",
        lambda athlete_id, db: _visible_state(),
    )

    result = await coach.chat(uuid4(), "What should I run today?")

    assert result["runtime_mode"] == RUNTIME_MODE_VISIBLE
    assert result["runtime_version"] == RUNTIME_VERSION_V2
    assert result["fallback_reason"] == "budget_exceeded"
    coach._query_kimi_with_fallback.assert_not_awaited()


@pytest.mark.asyncio
async def test_v2_eligible_request_emits_redacted_umbrella_log(monkeypatch):
    import services.consent as consent_module

    coach = _coach_with_v1_path()
    log_spy = MagicMock()
    monkeypatch.setattr(consent_module, "has_ai_consent", lambda athlete_id, db: True)
    monkeypatch.setattr(
        coach_core,
        "resolve_coach_runtime_v2_state",
        lambda athlete_id, db: _visible_state(),
    )
    monkeypatch.setattr(coach_core, "log_coach_runtime_v2_request", log_spy)

    raw_message = "My DEXA says 11.2 percent body fat and my knee hurts."
    await coach.chat(uuid4(), raw_message)

    log_spy.assert_called_once()
    kwargs = log_spy.call_args.kwargs
    assert kwargs["state"].runtime_mode == RUNTIME_MODE_VISIBLE
    assert kwargs["state"].runtime_version == RUNTIME_VERSION_V2
    assert kwargs["state"].shadow_enabled is True
    assert kwargs["state"].visible_enabled is True
    assert kwargs["state"].fallback_reason is None
    assert kwargs["llm_model"] == "kimi-k2.6"
    assert kwargs["thread_id"] == "thread-1"
    assert kwargs["tool_count"] == 0
    assert kwargs["packet_telemetry"]["artifact_mode"] == "observe_and_ask"
    assert kwargs["packet_telemetry"]["deterministic_check_status"] == "passed"
    assert kwargs["packet_telemetry"]["latency_ms_packet"] >= 0
    assert kwargs["packet_telemetry"]["latency_ms_llm"] == 0
    assert raw_message not in str(kwargs)
    assert "11.2" not in str(kwargs)


def test_runtime_request_log_payload_is_structured_and_redacted(monkeypatch):
    logger_info = MagicMock()
    monkeypatch.setattr(runtime_v2.logger, "info", logger_info)

    runtime_v2.log_coach_runtime_v2_request(
        athlete_id=uuid4(),
        state=_visible_state().with_failure_reason("packet_assembly_error"),
        thread_id="thread-1",
        latency_ms_total=12,
        llm_model="kimi-k2.6",
        tool_count=0,
        error_class=None,
        packet_telemetry={
            "latency_ms_packet": 7,
            "latency_ms_llm": 11,
            "deterministic_check_status": "passed",
        },
    )

    logger_info.assert_called_once()
    event = logger_info.call_args.kwargs["extra"]["extra_fields"]
    assert event["event"] == "coach_runtime_v2_request"
    assert event["runtime_mode"] == RUNTIME_MODE_VISIBLE
    assert event["runtime_version"] == RUNTIME_VERSION_V2
    assert event["flag_shadow"] is True
    assert event["flag_visible"] is True
    assert event["artifact_packet_schema_version"] == "coach_runtime_v2.packet.v1"
    assert event["packet_block_count"] == 0
    assert event["latency_ms_packet"] == 7
    assert event["latency_ms_llm"] == 11
    assert event["deterministic_check_status"] == "passed"
    assert event["fallback_reason"] == "packet_assembly_error"
    assert event["llm_model"] == "kimi-k2.6"
    assert "athlete_id_hash" in event
    assert "DEXA" not in str(event)
    assert "body fat" not in str(event)


def test_v2_mode_classifier_uses_locked_modes_and_precedence():
    overrides = extract_same_turn_overrides(
        "That's wrong, my calf hurts. Should I run today?"
    )
    mode = classify_conversation_mode(
        "That's wrong, my calf hurts. Should I run today?", overrides
    )

    assert mode["primary"] == "correction"
    assert mode["source"] == "deterministic_mode_classifier"
    assert mode["classifier_version"] == "coach_mode_classifier_v2_0_a"
    assert mode["screen_privacy"]["framing"] in ("direct", "adjacent", "elsewhere")


def test_same_turn_overrides_carry_value_and_duration_not_boolean():
    overrides = extract_same_turn_overrides(
        "That's wrong. No population models. The 3.1 mile run was a race."
    )

    assert overrides
    assert all(
        not isinstance(override["override_value"], bool) for override in overrides
    )
    by_path = {override["field_path"]: override for override in overrides}
    assert by_path["correction.current_turn"]["override_value"] == {
        "value": {
            "athlete_statement": "That's wrong. No population models. The 3.1 mile run was a race."
        },
        "duration": "current_turn",
    }
    assert (
        by_path["standing_overrides.coaching_boundary"]["override_value"]["duration"]
        == "standing"
    )
    assert (
        by_path["activity_classification_override.recent_activity"]["override_value"][
            "value"
        ]["classification"]
        == "race_effort"
    )


def test_v2_packet_assembler_builds_packet_without_raw_tools():
    packet = assemble_v2_packet(
        athlete_id=uuid4(),
        message="Should I race this 5K?",
        conversation_context=[{"role": "assistant", "content": "Earlier answer"}],
        legacy_athlete_state="ATHLETE STATE",
    )

    assert packet["schema_version"] == "coach_runtime_v2.packet.v1"
    assert packet["conversation_mode"]["primary"] == "racing_preparation_judgment"
    assert packet["telemetry"]["packet_block_count"] == 9
    assert "activity_evidence_state" in packet["blocks"]
    assert "training_adaptation_context" in packet["blocks"]
    assert "athlete_facts" in packet["blocks"]
    assert "recent_activities" in packet["blocks"]
    assert "recent_threads" in packet["blocks"]
    assert "unknowns" in packet["blocks"]
    assert "athlete_context" not in packet["blocks"]
    assert "_legacy_context_bridge_deprecated" in packet["blocks"]
    assert "tools" not in packet


def test_v2_packet_empties_deprecated_legacy_shim_when_ledger_coverage_high(
    monkeypatch,
):
    facts = {
        field: {
            "value": f"value:{field}",
            "confidence": "athlete_stated",
            "source": "test",
            "asserted_at": "2026-04-26T12:00:00+00:00",
        }
        for field in packet_module.VALID_FACT_FIELDS
    }
    monkeypatch.setattr(
        packet_module, "_athlete_facts_payload", lambda db, athlete_id: facts
    )

    packet = assemble_v2_packet(
        athlete_id=uuid4(),
        message="Should I race?",
        conversation_context=[],
        legacy_athlete_state="LEGACY STATE THAT SHOULD NOT BE PRIMARY",
    )

    shim = packet["blocks"]["_legacy_context_bridge_deprecated"]
    assert shim["status"] == "empty"
    assert shim["data"]["legacy_context_bridge"] == ""
    assert packet["telemetry"]["ledger_field_coverage"] == 1.0


def test_v2_packet_caps_deprecated_legacy_shim_under_packet_budget(monkeypatch):
    monkeypatch.setattr(
        packet_module,
        "_athlete_facts_payload",
        lambda db, athlete_id: {},
    )
    monkeypatch.setattr(packet_module.settings, "COACH_LEDGER_COVERAGE_SHIM_THRESHOLD", 0.5)
    legacy_context = "\n".join(
        f"Durable non-temporal legacy context line {index}."
        for index in range(800)
    )

    packet = assemble_v2_packet(
        athlete_id=uuid4(),
        message="Quick check — what should my next easy run focus on? Keep it brief.",
        conversation_context=[],
        legacy_athlete_state=legacy_context,
    )

    shim = packet["blocks"]["_legacy_context_bridge_deprecated"]
    assert shim["status"] == "deprecated_fallback"
    assert len(shim["data"]["legacy_context_bridge"]) <= (
        packet_module.LEGACY_CONTEXT_BRIDGE_MAX_CHARS
    )
    assert packet["telemetry"]["estimated_tokens"] <= 5000


def test_v2_packet_omits_deprecated_legacy_shim_when_packet_still_over_budget(
    monkeypatch,
):
    original_estimated_tokens = packet_module._estimated_tokens

    def budget_spike(value):
        if (
            isinstance(value, dict)
            and (
                value.get("_legacy_context_bridge_deprecated") or {}
            ).get("legacy_context_bridge")
        ):
            return 5001
        return original_estimated_tokens(value)

    monkeypatch.setattr(packet_module, "_estimated_tokens", budget_spike)
    monkeypatch.setattr(
        packet_module,
        "_athlete_facts_payload",
        lambda db, athlete_id: {},
    )
    monkeypatch.setattr(packet_module.settings, "COACH_LEDGER_COVERAGE_SHIM_THRESHOLD", 0.5)

    packet = assemble_v2_packet(
        athlete_id=uuid4(),
        message="Should I run easy today?",
        conversation_context=[],
        legacy_athlete_state="Durable non-temporal legacy context.\n" * 200,
    )

    shim = packet["blocks"]["_legacy_context_bridge_deprecated"]
    assert shim["status"] == "empty"
    assert shim["data"]["legacy_context_bridge"] == ""
    assert packet["telemetry"]["legacy_context_bridge_omitted_for_budget"] is True
    assert packet["telemetry"]["estimated_tokens"] <= 5000


def test_v2_packet_preserves_pasted_table_by_trimming_older_context(monkeypatch):
    table_message = (
        "here is the race last year, it should help\n"
        "1\t6:28.9\t6:28.9\t1.00\t6:29\t6:21\t147\t161\t69\t10\t404\tNo Weight\n"
        "2\t6:38.3\t13:07\t1.00\t6:38\t6:40\t160\t165\t30\t46\t376\tNo Weight\n"
        "3\t6:34.5\t19:42\t1.00\t6:35\t6:34\t155\t159\t39\t39\t390\tNo Weight\n"
        "4\t6:38.0\t26:20\t1.00\t6:38\t6:38\t163\t167\t39\t52\t377\tNo Weight\n"
        "5\t6:46.1\t33:06\t1.00\t6:46\t6:41\t167\t173\t43\t13\t390\tNo Weight\n"
        "6\t6:38.0\t39:44\t1.00\t6:38\t6:43\t161\t169\t30\t79\t377\tNo Weight\n"
        "Summary\t51:19\t51:19\t6.37\t8:04\t8:02\t153\t173\t253\t253\t315\tNo Weight"
    )
    conversation_context = [
        {"role": "user", "content": f"prior user message {index} " * 80}
        for index in range(8)
    ]
    bulky_atoms = [
        {
            "activity_id": f"activity-{index}",
            "type": "threshold_intervals",
            "date": "2026-04-16",
            "distance": {"meters": 12000, "miles": 7.46},
            "duration": {"seconds": 3600},
            "avg_pace": {"display": "6:20/mi", "seconds_per_mile": 380},
            "notable_features": [{"type": "pace_drift", "detail": "x" * 500}],
            "structured_workout_summary": {
                "observed_work_rep_count": 4,
                "reps": [{"distance_m": 2538, "avg_pace": "6:20/mi"}] * 4,
            },
        }
        for index in range(10)
    ]
    monkeypatch.setattr(
        packet_module,
        "_empty_recent_activities",
        lambda generated_at: {
            "schema_version": "coach_runtime_v2.recent_activities.v1",
            "status": "complete",
            "generated_at": generated_at,
            "window_days": 14,
            "ordered": "most_recent_first",
            "data": {"recent_activities": bulky_atoms, "aggregates": {}},
            "token_budget": {
                "target_tokens": 1500,
                "max_tokens": 2500,
                "estimated_tokens": 4000,
            },
            "provenance": [],
            "unknowns": [],
        },
    )

    packet = assemble_v2_packet(
        athlete_id=uuid4(),
        message=table_message,
        conversation_context=conversation_context,
        legacy_athlete_state="Durable non-temporal legacy context.\n" * 200,
    )

    assert packet["blocks"]["conversation"]["data"]["user_message"] == table_message
    table_evidence = packet["blocks"]["conversation"]["data"][
        "same_turn_table_evidence"
    ]
    assert table_evidence["status"] == "parsed"
    assert table_evidence["derived"]["gain_by_split_ft"] == [69, 30, 39, 39, 43, 30]
    assert table_evidence["derived"]["total_elevation_gain_ft"] == 253
    assert table_evidence["derived"]["max_gain_split_number"] == 1
    assert packet["telemetry"]["estimated_tokens"] <= 5000
    assert packet["telemetry"]["omitted_block_count"] >= 1
    assert any(
        item["block"] == "conversation.recent_context"
        for item in packet["omitted_blocks"]
    )


def test_v2_packet_prompt_compacts_audit_metadata_for_llm():
    packet = assemble_v2_packet(
        athlete_id=uuid4(),
        message="Should I race this 10K?",
        conversation_context=[{"role": "assistant", "content": "Prior answer"}],
        legacy_athlete_state="Durable non-temporal context.",
    )

    prompt = packet_to_prompt(packet)
    audit_prompt = packet_to_prompt(packet, profile="audit")

    assert "Should I race this 10K?" in prompt
    assert "provenance" not in prompt
    assert "token_budget" not in prompt
    assert "_legacy_context_bridge_deprecated" not in prompt
    assert len(prompt) < len(audit_prompt)


def test_v2_packet_prompt_surfaces_parsed_table_elevation_gain():
    message = (
        "69 30 39 39 43 30 that is the gain by mile\n"
        "1\t6:28.9\t6:28.9\t1.00\t6:29\t6:21\t147\t161\t69\t10\n"
        "2\t6:38.3\t13:07\t1.00\t6:38\t6:40\t160\t165\t30\t46\n"
        "3\t6:34.5\t19:42\t1.00\t6:35\t6:34\t155\t159\t39\t39\n"
        "4\t6:38.0\t26:20\t1.00\t6:38\t6:38\t163\t167\t39\t52\n"
        "5\t6:46.1\t33:06\t1.00\t6:46\t6:41\t167\t173\t43\t13\n"
        "6\t6:38.0\t39:44\t1.00\t6:38\t6:43\t161\t169\t30\t79\n"
        "Summary\t51:19\t51:19\t6.37\t8:04\t8:02\t153\t173\t253\t253"
    )

    packet = assemble_v2_packet(
        athlete_id=uuid4(),
        message=message,
        conversation_context=[],
        legacy_athlete_state="",
    )
    prompt = packet_to_prompt(packet)

    assert '"gain_by_split_ft": [69, 30, 39, 39, 43, 30]' in prompt
    assert '"total_elevation_gain_ft": 253' in prompt
    assert '"max_gain_split_number": 1' in prompt
    assert '"total_elevation_gain_ft": 682' not in prompt


def test_v2_packet_uses_recent_user_course_correction_over_poisoned_assistant_claim():
    conversation_context = [
        {
            "role": "user",
            "content": "wrong - you aren't looking at the elevation gain data",
        },
        {
            "role": "assistant",
            "content": "You're right. Last year's splits had 682 ft total gain.",
        },
        {
            "role": "user",
            "content": "69 30 39 39 43 30 that is the gain by mile",
        },
        {
            "role": "assistant",
            "content": "You're right. Gain by mile was 69, 30, 39, 39, 43, 30.",
        },
        {
            "role": "user",
            "content": "no it doesn't. it has 253 feet of gain and loss",
        },
    ]

    packet = assemble_v2_packet(
        athlete_id=uuid4(),
        message="is it realistic to set 39:15 as goal for Saturday",
        conversation_context=conversation_context,
        legacy_athlete_state="",
    )
    conversation = packet["blocks"]["conversation"]["data"]
    prompt = packet_to_prompt(packet)

    evidence = conversation["same_turn_table_evidence"]
    assert evidence["status"] == "parsed_partial"
    assert evidence["derived"]["gain_by_split_ft"] == [69, 30, 39, 39, 43, 30]
    assert evidence["derived"]["total_elevation_gain_ft"] == 253
    assert "682 ft total gain" not in str(conversation["recent_context"])
    assert '"total_elevation_gain_ft": 253' in prompt
    assert "682 ft total gain" not in prompt


def test_v2_packet_calendar_context_is_authoritative_and_quiets_bridge():
    athlete_id = uuid4()
    today = date(2026, 4, 26)
    race_date = today + timedelta(days=6)

    class FakeQuery:
        def __init__(self, *, first_value=None, all_values=None):
            self.first_value = first_value
            self.all_values = all_values or []

        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def limit(self, *args, **kwargs):
            return self

        def first(self):
            return self.first_value

        def all(self):
            return self.all_values

    class FakeDb:
        def query(self, model):
            if model.__name__ == "Athlete":
                return FakeQuery(first_value=SimpleNamespace(timezone="UTC"))
            if model.__name__ == "TrainingPlan":
                return FakeQuery(
                    first_value=SimpleNamespace(
                        id=uuid4(),
                        name="Coke 10K build",
                        goal_race_name="Coke 10K",
                        goal_race_date=race_date,
                        goal_race_distance_m=10000,
                    )
                )
            if model.__name__ == "Activity":
                return FakeQuery(
                    all_values=[
                        SimpleNamespace(
                            id=uuid4(),
                            start_time=datetime(
                                2026, 4, 25, 13, 0, tzinfo=timezone.utc
                            ),
                            sport="run",
                            name="Easy Run",
                            workout_type="easy",
                            distance_m=8400,
                            user_verified_race=False,
                            is_race_candidate=False,
                            race_confidence=None,
                            start_lat=None,
                            start_lng=None,
                        )
                    ]
                )
            return FakeQuery()

    packet = assemble_v2_packet(
        athlete_id=athlete_id,
        db=FakeDb(),
        message="I feel fine today and want a straight read: should I keep today easy?",
        conversation_context=[],
        legacy_athlete_state=(
            "ATHLETE BRIEF\n"
            "Six days to the Coke 10K.\n"
            "Today is race week and the athlete might race soon.\n"
            "Strength preference: keep instructions direct."
        ),
        now_utc=datetime(2026, 4, 26, 13, 0, tzinfo=timezone.utc),
    )

    calendar = packet["blocks"]["calendar_context"]["data"]
    bridge = packet["blocks"]["_legacy_context_bridge_deprecated"]["data"][
        "legacy_context_bridge"
    ]
    assert calendar["today_local"] == today.isoformat()
    assert calendar["today_has_completed_activity"] is False
    assert calendar["today_has_completed_race"] is False
    assert calendar["upcoming_race"]["name"] == "Coke 10K"
    assert calendar["upcoming_race"]["days_until_race"] == 6
    assert "Six days to the Coke 10K" not in bridge
    assert "race week" not in bridge
    assert "Strength preference" in bridge
    assert packet["telemetry"]["temporal_bridge_lines_removed"] == 2


def test_v2_packet_activity_evidence_does_not_flatten_quality_day_to_easy():
    athlete_id = uuid4()
    today = date(2026, 4, 26)
    race_date = today + timedelta(days=6)
    yesterday = datetime(2026, 4, 25, 13, 0, tzinfo=timezone.utc)

    class FakeQuery:
        def __init__(self, *, first_value=None, all_values=None):
            self.first_value = first_value
            self.all_values = all_values or []

        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def limit(self, *args, **kwargs):
            return self

        def first(self):
            return self.first_value

        def all(self):
            return self.all_values

    race_run_id = uuid4()
    activity_rows = [
        SimpleNamespace(
            id=race_run_id,
            start_time=yesterday,
            sport="run",
            name="Morning Run",
            workout_type="easy",
            distance_m=5000,
            duration_s=19 * 60,
            avg_hr=178,
            intensity_score=None,
            user_verified_race=False,
            is_race_candidate=False,
            race_confidence=None,
            start_lat=None,
            start_lng=None,
        ),
        SimpleNamespace(
            id=uuid4(),
            start_time=yesterday + timedelta(hours=3),
            sport="run",
            name="Lunch Run",
            workout_type="easy",
            distance_m=3300,
            duration_s=21 * 60,
            avg_hr=166,
            intensity_score=61,
            user_verified_race=False,
            is_race_candidate=False,
            race_confidence=None,
            start_lat=None,
            start_lng=None,
        ),
        SimpleNamespace(
            id=uuid4(),
            start_time=yesterday + timedelta(hours=6),
            sport="run",
            name="Shakeout",
            workout_type="easy",
            distance_m=225,
            duration_s=50,
            avg_hr=150,
            intensity_score=None,
            user_verified_race=False,
            is_race_candidate=False,
            race_confidence=None,
            start_lat=None,
            start_lng=None,
        ),
    ]
    split_rows = [
        SimpleNamespace(
            split_number=1,
            distance=1609.344,
            moving_time=340,
            elapsed_time=340,
        ),
        SimpleNamespace(
            split_number=2,
            distance=1609.344,
            moving_time=370,
            elapsed_time=370,
        ),
        SimpleNamespace(
            split_number=3,
            distance=1609.344,
            moving_time=430,
            elapsed_time=430,
        ),
    ]

    class FakeDb:
        def query(self, model):
            if model.__name__ == "Athlete":
                return FakeQuery(first_value=SimpleNamespace(timezone="UTC"))
            if model.__name__ == "TrainingPlan":
                return FakeQuery(
                    first_value=SimpleNamespace(
                        id=uuid4(),
                        name="Coke 10K build",
                        goal_race_name="Coke 10K",
                        goal_race_date=race_date,
                        goal_race_distance_m=10000,
                    )
                )
            if model.__name__ == "Activity":
                return FakeQuery(all_values=activity_rows)
            if model.__name__ == "ActivitySplit":
                return FakeQuery(all_values=split_rows)
            return FakeQuery()

    packet = assemble_v2_packet(
        athlete_id=athlete_id,
        db=FakeDb(),
        message=(
            "That's because the labeling has a flaw and didn't let me label "
            "the 3.1 mile run as a race - it was a race"
        ),
        conversation_context=[],
        legacy_athlete_state="Strength preference: keep instructions direct.",
        now_utc=datetime(2026, 4, 26, 13, 0, tzinfo=timezone.utc),
    )

    overrides = packet["athlete_stated_overrides"]
    evidence = packet["blocks"]["activity_evidence_state"]["data"]
    adaptation = packet["blocks"]["training_adaptation_context"]["data"]

    assert any(
        override["field_path"] == "activity_classification_override.recent_activity"
        for override in overrides
    )
    assert evidence["activity_classification_override"]["target_distance_m"] == 4989
    assert evidence["yesterday"]["activity_count"] == 3
    assert evidence["yesterday"]["all_easy"] is False
    assert evidence["yesterday"]["race_effort_present"] is True
    assert evidence["yesterday"]["threshold_effort_present"] is True
    assert evidence["yesterday"]["short_fast_effort_present"] is True
    assert evidence["yesterday"]["quality_effort_count"] == 3
    assert evidence["yesterday"]["race_execution_quality"]["status"] == "negative"
    assert (
        evidence["yesterday"]["race_execution_quality"][
            "can_claim_controlled_or_confident"
        ]
        is False
    )
    assert (
        "controlled"
        in evidence["yesterday"]["race_execution_quality"][
            "forbidden_claims_without_more_evidence"
        ]
    )
    assert adaptation["stimulus_event_mix"]["all_easy"] is False
    assert (
        adaptation["likely_effect_before_target"]
        == "hard_stimulus_not_meaningful_new_fitness_before_target"
    )
    assert adaptation["recommendation_bias"] == "ask_after_work_then_protect_freshness"
    assert adaptation["confidence_or_sharpness_claim_allowed"] is False
    assert adaptation["must_ask_execution_followup"] is True


def test_v2_seed_migration_creates_required_flags_safely():
    migration = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "coach_runtime_v2_001_seed_flags.py"
    )
    text = migration.read_text(encoding="utf-8")

    assert "'coach.runtime_v2.shadow'" in text
    assert "'coach.runtime_v2.visible'" in text
    assert "enabled = false" in text
    assert "rollout_percentage = 0" in text
    assert "allowed_athlete_ids = '[]'::jsonb" in text
