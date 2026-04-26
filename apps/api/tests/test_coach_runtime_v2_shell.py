import inspect
from pathlib import Path
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
)
from services.coaching import runtime_v2
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
    coach._finalize_response_with_deterministic_guardrails = MagicMock(
        return_value=(True, "v2 answer")
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
async def test_flags_off_chat_is_v1_passthrough_with_metadata(monkeypatch):
    import services.consent as consent_module

    coach = _coach_with_v1_path()
    monkeypatch.setattr(consent_module, "has_ai_consent", lambda athlete_id, db: True)
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

    assert result["response"] == "kimi"
    assert result["runtime_version"] == RUNTIME_VERSION_V1
    assert result["runtime_mode"] == RUNTIME_MODE_OFF
    assert result["fallback_reason"] is None
    coach._query_kimi_with_fallback.assert_awaited_once()
    coach.query_opus.assert_not_awaited()
    _, kwargs = coach._save_chat_messages.call_args
    assert kwargs["runtime_metadata"] == {
        "runtime_version": RUNTIME_VERSION_V1,
        "runtime_mode": RUNTIME_MODE_OFF,
        "fallback_reason": None,
    }


@pytest.mark.asyncio
async def test_shadow_mode_does_not_call_coach_llm_twice(monkeypatch):
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
    coach._query_kimi_with_fallback.assert_awaited_once()


@pytest.mark.asyncio
async def test_visible_mode_uses_v2_packet_path_when_success(monkeypatch):
    import services.consent as consent_module

    coach = _coach_with_v1_path()
    monkeypatch.setattr(consent_module, "has_ai_consent", lambda athlete_id, db: True)
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
    coach._finalize_response_with_deterministic_guardrails.assert_called_once()
    _, kwargs = coach._save_chat_messages.call_args
    assert kwargs["runtime_metadata"] == {
        "runtime_version": RUNTIME_VERSION_V2,
        "runtime_mode": RUNTIME_MODE_VISIBLE,
        "fallback_reason": None,
    }


@pytest.mark.asyncio
async def test_visible_packet_assembly_failure_falls_back_to_v1(monkeypatch):
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

    assert result["response"] == "kimi"
    assert result["runtime_mode"] == RUNTIME_MODE_FALLBACK
    assert result["runtime_version"] == RUNTIME_VERSION_V1
    assert result["fallback_reason"] == "packet_assembly_error"
    coach.query_kimi_v2_packet.assert_not_awaited()
    coach._query_kimi_with_fallback.assert_awaited_once()


@pytest.mark.asyncio
async def test_visible_v2_empty_response_falls_back_to_v1(monkeypatch):
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

    assert result["response"] == "kimi"
    assert result["runtime_mode"] == RUNTIME_MODE_FALLBACK
    assert result["runtime_version"] == RUNTIME_VERSION_V1
    assert result["fallback_reason"] == "v2_empty_response"
    coach.query_kimi_v2_packet.assert_awaited_once()
    coach._query_kimi_with_fallback.assert_awaited_once()


@pytest.mark.asyncio
async def test_visible_v2_guardrail_failure_falls_back_to_v1(monkeypatch):
    import services.consent as consent_module

    coach = _coach_with_v1_path()
    coach._finalize_response_with_deterministic_guardrails = MagicMock(
        return_value=(False, "wrong-topic answer")
    )
    monkeypatch.setattr(consent_module, "has_ai_consent", lambda athlete_id, db: True)
    monkeypatch.setattr(
        coach_core,
        "resolve_coach_runtime_v2_state",
        lambda athlete_id, db: _visible_state(),
    )

    result = await coach.chat(uuid4(), "Talk me through race week.")

    assert result["response"] == "kimi"
    assert result["runtime_mode"] == RUNTIME_MODE_FALLBACK
    assert result["runtime_version"] == RUNTIME_VERSION_V1
    assert result["fallback_reason"] == "v2_guardrail_failed"
    coach.query_kimi_v2_packet.assert_awaited_once()
    coach._query_kimi_with_fallback.assert_awaited_once()


@pytest.mark.asyncio
async def test_visible_v2_timeout_falls_back_to_v1(monkeypatch):
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

    assert result["response"] == "kimi"
    assert result["runtime_mode"] == RUNTIME_MODE_FALLBACK
    assert result["runtime_version"] == RUNTIME_VERSION_V1
    assert result["fallback_reason"] == "v2_timeout"
    coach.query_kimi_v2_packet.assert_awaited_once()
    coach._query_kimi_with_fallback.assert_awaited_once()


@pytest.mark.asyncio
async def test_visible_profile_short_circuit_persists_fallback_metadata(monkeypatch):
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

    assert result["runtime_mode"] == RUNTIME_MODE_FALLBACK
    assert result["runtime_version"] == RUNTIME_VERSION_V1
    assert result["fallback_reason"] == "deterministic_short_circuit"
    _, kwargs = coach._save_chat_messages.call_args
    assert kwargs["runtime_metadata"] == {
        "runtime_version": RUNTIME_VERSION_V1,
        "runtime_mode": RUNTIME_MODE_FALLBACK,
        "fallback_reason": "deterministic_short_circuit",
    }


@pytest.mark.asyncio
async def test_visible_consent_disabled_response_does_not_claim_v2(monkeypatch):
    import services.consent as consent_module

    coach = _coach_with_v1_path()
    monkeypatch.setattr(consent_module, "has_ai_consent", lambda athlete_id, db: False)
    monkeypatch.setattr(
        coach_core,
        "resolve_coach_runtime_v2_state",
        lambda athlete_id, db: _visible_state(),
    )

    result = await coach.chat(uuid4(), "Can you coach me?")

    assert result["runtime_mode"] == RUNTIME_MODE_FALLBACK
    assert result["runtime_version"] == RUNTIME_VERSION_V1
    assert result["fallback_reason"] == "consent_disabled"
    coach._query_kimi_with_fallback.assert_not_awaited()


@pytest.mark.asyncio
async def test_visible_budget_exceeded_response_does_not_claim_v2(monkeypatch):
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

    assert result["runtime_mode"] == RUNTIME_MODE_FALLBACK
    assert result["runtime_version"] == RUNTIME_VERSION_V1
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
        state=_visible_state().as_fallback("packet_assembly_error"),
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
    assert event["runtime_mode"] == RUNTIME_MODE_FALLBACK
    assert event["runtime_version"] == RUNTIME_VERSION_V1
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


def test_v2_packet_assembler_builds_packet_without_raw_tools():
    packet = assemble_v2_packet(
        athlete_id=uuid4(),
        message="Should I race this 5K?",
        conversation_context=[{"role": "assistant", "content": "Earlier answer"}],
        legacy_athlete_state="ATHLETE STATE",
    )

    assert packet["schema_version"] == "coach_runtime_v2.packet.v1"
    assert packet["conversation_mode"]["primary"] == "racing_preparation_judgment"
    assert packet["telemetry"]["packet_block_count"] == 2
    assert "tools" not in packet


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
