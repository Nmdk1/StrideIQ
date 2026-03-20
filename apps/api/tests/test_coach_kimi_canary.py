import inspect
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from services.ai_coach import AICoach


def _make_openai_module(create_impl):
    class _Completions:
        async def create(self, **kwargs):
            return await create_impl(**kwargs)

    class _Chat:
        def __init__(self):
            self.completions = _Completions()

    class _Client:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.chat = _Chat()

    return SimpleNamespace(AsyncOpenAI=_Client)


def _oai_response(*, content="", tool_calls=None, prompt_tokens=1, completion_tokens=1):
    message = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    choice = SimpleNamespace(message=message)
    usage = SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    return SimpleNamespace(choices=[choice], usage=usage)


def test_kimi_tools_format_matches_openai_spec():
    coach = AICoach.__new__(AICoach)
    coach._opus_tools = MagicMock(
        return_value=[
            {
                "name": "get_recent_runs",
                "description": "desc",
                "input_schema": {"type": "object", "properties": {}},
            }
        ]
    )
    tools = coach._kimi_tools()
    assert len(tools) == 1
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "get_recent_runs"
    assert tools[0]["function"]["parameters"]["type"] == "object"


@pytest.mark.asyncio
async def test_kimi_coach_tool_call_loop(monkeypatch):
    coach = AICoach.__new__(AICoach)
    coach._build_coach_system_prompt = MagicMock(return_value="system")
    coach._kimi_tools = MagicMock(return_value=[{"type": "function", "function": {"name": "get_recent_runs"}}])
    coach._execute_opus_tool = MagicMock(return_value='{"ok": true}')
    coach._validate_tool_usage = MagicMock(return_value=(True, "ok"))
    coach.track_usage = MagicMock()
    coach.query_opus = AsyncMock(return_value={"response": "fallback", "error": False, "model": "claude-sonnet-4-6"})

    tool_call = SimpleNamespace(
        id="call-1",
        function=SimpleNamespace(name="get_recent_runs", arguments="{}"),
    )
    responses = iter(
        [
            _oai_response(tool_calls=[tool_call], prompt_tokens=10, completion_tokens=5),
            _oai_response(content="Evidence-backed answer.", prompt_tokens=11, completion_tokens=6),
        ]
    )
    captured = []

    async def _create(**kwargs):
        captured.append(kwargs)
        return next(responses)

    monkeypatch.setitem(sys.modules, "openai", _make_openai_module(_create))
    from services import ai_coach as ai_coach_module
    monkeypatch.setattr(ai_coach_module.settings, "KIMI_API_KEY", "kimi-key", raising=False)
    monkeypatch.setattr(ai_coach_module.settings, "KIMI_BASE_URL", "https://api.moonshot.ai/v1", raising=False)
    monkeypatch.setattr(ai_coach_module.settings, "COACH_CANARY_MODEL", "kimi-k2.5", raising=False)

    result = await coach.query_kimi_coach(
        athlete_id=uuid4(),
        message="Analyze my week.",
        athlete_state="",
        conversation_context=[],
    )
    assert result["error"] is False
    assert result["response"] == "Evidence-backed answer."
    assert result["tools_called"] == ["get_recent_runs"]
    assert "temperature" not in captured[0]


@pytest.mark.asyncio
async def test_kimi_empty_content_falls_back_to_sonnet(monkeypatch):
    coach = AICoach.__new__(AICoach)
    coach._build_coach_system_prompt = MagicMock(return_value="system")
    coach._kimi_tools = MagicMock(return_value=[])
    coach._execute_opus_tool = MagicMock()
    coach._validate_tool_usage = MagicMock(return_value=(True, "ok"))
    coach.track_usage = MagicMock()
    coach.query_opus = AsyncMock(return_value={"response": "sonnet fallback", "error": False, "model": "claude-sonnet-4-6"})

    async def _create(**kwargs):
        message = SimpleNamespace(content="", tool_calls=[], reasoning_content="internal chain")
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message)],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
        )

    monkeypatch.setitem(sys.modules, "openai", _make_openai_module(_create))
    from services import ai_coach as ai_coach_module
    monkeypatch.setattr(ai_coach_module.settings, "KIMI_API_KEY", "kimi-key", raising=False)
    monkeypatch.setattr(ai_coach_module.settings, "KIMI_BASE_URL", "https://api.moonshot.ai/v1", raising=False)
    monkeypatch.setattr(ai_coach_module.settings, "COACH_CANARY_MODEL", "kimi-k2.5", raising=False)

    result = await coach.query_kimi_coach(
        athlete_id=uuid4(),
        message="Question",
        athlete_state="",
        conversation_context=[],
    )
    assert result["response"] == "sonnet fallback"
    assert "internal chain" not in result["response"]
    coach.query_opus.assert_awaited_once()


@pytest.mark.asyncio
async def test_kimi_coach_fallback_to_sonnet_on_error():
    coach = AICoach.__new__(AICoach)
    coach.query_kimi_coach = AsyncMock(side_effect=RuntimeError("network down"))
    coach.query_opus = AsyncMock(return_value={"response": "sonnet fallback", "error": False, "model": "claude-sonnet-4-6"})

    result = await coach._query_kimi_with_fallback(
        athlete_id=uuid4(),
        message="Question",
        athlete_state="",
        conversation_context=[],
    )
    assert result["response"] == "sonnet fallback"
    coach.query_opus.assert_awaited_once()


def test_system_prompt_shared_between_opus_and_kimi():
    opus_source = inspect.getsource(AICoach.query_opus)
    kimi_source = inspect.getsource(AICoach.query_kimi_coach)
    assert "_build_coach_system_prompt" in opus_source
    assert "_build_coach_system_prompt" in kimi_source


def test_kimi_path_omits_temperature():
    kimi_source = inspect.getsource(AICoach.query_kimi_coach)
    assert "temperature=" not in kimi_source


@pytest.mark.asyncio
async def test_canary_routing_premium_lane_to_kimi(monkeypatch):
    coach = AICoach(db=MagicMock())
    coach.router = MagicMock()
    coach.router.classify = MagicMock(return_value=(None, False))
    coach.gemini_client = object()
    coach.anthropic_client = object()
    coach.classify_query_complexity = MagicMock(return_value="high")
    coach.get_model_for_query = MagicMock(return_value=(coach.MODEL_HIGH_STAKES, True))
    coach.is_athlete_vip = MagicMock(return_value=False)
    coach.check_budget = MagicMock(return_value=(True, "ok"))
    coach._is_profile_edit_intent = MagicMock(return_value=False)
    coach._maybe_update_units_preference = MagicMock()
    coach._maybe_update_intent_snapshot = MagicMock()
    coach._thin_history_and_baseline_flags = MagicMock(return_value=(False, {}, None, False))
    coach.get_or_create_thread_with_state = MagicMock(return_value=("thread-1", False))
    coach.get_thread_history = MagicMock(return_value={"messages": []})
    coach._build_athlete_state_for_opus = MagicMock(return_value="state")
    coach._query_kimi_with_fallback = AsyncMock(return_value={"response": "kimi", "error": False})
    coach.query_opus = AsyncMock(return_value={"response": "sonnet", "error": False})
    coach._finalize_response_with_turn_guard = AsyncMock(side_effect=lambda **kwargs: kwargs["response_text"])
    coach._save_chat_messages = MagicMock()

    import services.consent as consent_module
    monkeypatch.setattr(consent_module, "has_ai_consent", lambda athlete_id, db: True)
    import core.llm_client as llm_module
    monkeypatch.setattr(llm_module, "is_canary_athlete", lambda athlete_id: True)

    result = await coach.chat(uuid4(), "My knee hurts. Should I run?")
    assert result["error"] is False
    coach._query_kimi_with_fallback.assert_awaited_once()
    coach.query_opus.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_canary_keeps_existing_premium_lane_behavior(monkeypatch):
    coach = AICoach(db=MagicMock())
    coach.router = MagicMock()
    coach.router.classify = MagicMock(return_value=(None, False))
    coach.gemini_client = object()
    coach.anthropic_client = object()
    coach.classify_query_complexity = MagicMock(return_value="high")
    coach.get_model_for_query = MagicMock(return_value=(coach.MODEL_HIGH_STAKES, True))
    coach.is_athlete_vip = MagicMock(return_value=False)
    coach.check_budget = MagicMock(return_value=(True, "ok"))
    coach._is_profile_edit_intent = MagicMock(return_value=False)
    coach._maybe_update_units_preference = MagicMock()
    coach._maybe_update_intent_snapshot = MagicMock()
    coach._thin_history_and_baseline_flags = MagicMock(return_value=(False, {}, None, False))
    coach.get_or_create_thread_with_state = MagicMock(return_value=("thread-1", False))
    coach.get_thread_history = MagicMock(return_value={"messages": []})
    coach._build_athlete_state_for_opus = MagicMock(return_value="state")
    coach._query_kimi_with_fallback = AsyncMock(return_value={"response": "kimi", "error": False})
    coach.query_opus = AsyncMock(return_value={"response": "sonnet", "error": False})
    coach._finalize_response_with_turn_guard = AsyncMock(side_effect=lambda **kwargs: kwargs["response_text"])
    coach._save_chat_messages = MagicMock()

    import services.consent as consent_module
    monkeypatch.setattr(consent_module, "has_ai_consent", lambda athlete_id, db: True)
    import core.llm_client as llm_module
    monkeypatch.setattr(llm_module, "is_canary_athlete", lambda athlete_id: False)

    result = await coach.chat(uuid4(), "My knee hurts. Should I run?")
    assert result["error"] is False
    coach.query_opus.assert_awaited_once()
    coach._query_kimi_with_fallback.assert_not_awaited()
