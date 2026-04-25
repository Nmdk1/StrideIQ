import asyncio
from uuid import uuid4
from unittest.mock import MagicMock, patch, AsyncMock

from services.ai_coach import AICoach
from services.coaching._constants import count_hedge_phrases, _check_response_quality


def _coach_stub() -> AICoach:
    mock_db = MagicMock()
    with patch.object(AICoach, "__init__", lambda self, db: None):
        coach = AICoach(mock_db)
    return coach


def test_chat_normalizer_strips_internal_fact_labels():
    coach = _coach_stub()
    coach._UUID_RE = AICoach._UUID_RE
    coach._user_explicitly_requested_ids = AICoach._user_explicitly_requested_ids.__get__(coach, AICoach)
    normalize = AICoach._normalize_response_for_ui.__get__(coach, AICoach)

    raw = (
        "Date: 2026-02-10 (Tuesday)\n"
        "Recorded pace vs marathon pace: slower by 0:09/mi.\n"
        "Strong controlled execution and you should keep tomorrow easy."
    )
    out = normalize(user_message="How was run today?", assistant_message=raw)
    assert "Date:" not in out
    assert "Recorded pace vs marathon pace" not in out
    assert "Strong controlled execution" in out


def test_pace_relation_rewritten_in_evidence_bullets():
    """The internal 'Recorded pace vs marathon pace:' must never appear in output,
    even inside Evidence bullet lists. It should be rewritten to athlete-friendly
    phrasing like 'Pace sat about X off marathon rhythm'.
    """
    coach = _coach_stub()
    coach._UUID_RE = AICoach._UUID_RE
    coach._user_explicitly_requested_ids = AICoach._user_explicitly_requested_ids.__get__(coach, AICoach)
    normalize = AICoach._normalize_response_for_ui.__get__(coach, AICoach)

    raw = (
        "Great controlled effort today.\n\n"
        "## Evidence\n"
        "- Planned workout for 2026-02-10: 5mi + 8x hill strides.\n"
        "- Actual activity: 10 mile run, 10.0 mi @ 7:06/mi (avg HR 152 bpm).\n"
        "- Recorded pace vs marathon pace: slower by 0:09/mi.\n"
    )
    out = normalize(user_message="How was my run?", assistant_message=raw)

    # Internal system language must be gone
    assert "Recorded pace vs marathon pace" not in out
    # Athlete-friendly rewrite must be present
    assert "marathon rhythm" in out
    # Coaching content must survive
    assert "Great controlled effort" in out
    assert "Planned workout" in out


def test_pace_relation_faster_direction():
    """When the athlete ran faster than marathon pace, the rewrite should say so."""
    coach = _coach_stub()
    coach._UUID_RE = AICoach._UUID_RE
    coach._user_explicitly_requested_ids = AICoach._user_explicitly_requested_ids.__get__(coach, AICoach)
    normalize = AICoach._normalize_response_for_ui.__get__(coach, AICoach)

    raw = (
        "Strong tempo session.\n\n"
        "## Evidence\n"
        "- Recorded pace vs marathon pace: faster by 0:15/mi.\n"
    )
    out = normalize(user_message="How was my tempo?", assistant_message=raw)
    assert "Recorded pace vs marathon pace" not in out
    assert "quicker than marathon rhythm" in out


def test_system_instructions_include_conversational_aia_requirement():
    assert "Conversational A->I->A requirement" in AICoach.SYSTEM_INSTRUCTIONS


def test_phase7_prompt_distinguishes_general_knowledge_from_athlete_facts():
    coach = _coach_stub()
    coach.db = MagicMock()
    prompt = AICoach._build_coach_system_prompt(coach, uuid4())

    assert "Every number, distance, pace, date, and training fact ABOUT THIS ATHLETE" in prompt
    assert "GENERAL KNOWLEDGE RULE" in prompt
    assert "standard sports science" in prompt.lower()
    assert "I don't have that data" not in prompt
    assert "I don't have that in your history" in prompt


def test_phase7_prompt_replaces_forced_weekly_volume_mandate():
    coach = _coach_stub()
    coach.db = MagicMock()
    prompt = AICoach._build_coach_system_prompt(coach, uuid4())

    assert "YOU HAVE TOOLS -- USE THEM WHEN RELEVANT" in prompt
    assert "ALWAYS call get_weekly_volume first" not in prompt
    assert "get_training_block_narrative" in prompt
    assert "do NOT call tools for questions that don't need athlete data" in prompt


def test_phase7_prompt_contains_direct_voice_race_day_and_zone_discrepancy_rules():
    coach = _coach_stub()
    coach.db = MagicMock()
    prompt = AICoach._build_coach_system_prompt(coach, uuid4())

    assert "VOICE DIRECTIVE" in prompt
    assert "Lead with your position" in prompt
    assert "Race day is execution mode" in prompt
    assert "ZONE / WORKOUT EVIDENCE DISCREPANCY" in prompt
    assert "reason from what the athlete actually ran" in prompt


def test_hedge_phrase_counter_flags_overqualified_responses():
    text = (
        "That said, it's worth noting this is still aggressive. "
        "I would suggest considering caution."
    )

    assert count_hedge_phrases(text) >= 3
    with patch("services.coaching._constants.logger.warning") as warning:
        _check_response_quality(text, "test-model", "athlete-1")

    warning.assert_called()
    assert "hedge_overload" in warning.call_args.args[3]


def test_kimi_tool_choice_is_auto_for_general_knowledge_questions():
    coach = _coach_stub()
    helper = AICoach._requires_first_tool_call.__get__(coach, AICoach)

    assert helper("What is the standard Maurten bicarb timing protocol?") is False
    assert helper("How should I warm up for a hard 5K in general?") is False
    assert helper("Give me a race strategy for my 5K this morning.") is True
    assert helper("That 16 x 400 workout was on March 28th.") is True


# ---------------------------------------------------------------------------
# Integration-level tests: exercise chat() via mocked Gemini to verify
# normalization is wired in and fail-closed behaviour works.
# ---------------------------------------------------------------------------

def _build_chat_coach() -> AICoach:
    """Build an AICoach instance with enough stubs to run chat() without DB."""
    coach = _coach_stub()
    # Minimal attributes that chat() accesses
    coach.db = MagicMock()
    coach.gemini_client = MagicMock()  # non-None so the Gemini branch is entered
    coach.anthropic_client = None
    coach.router = MagicMock()
    # router.classify returns (MessageType, bool) — mock it as a tuple
    from services.coach_modules import MessageType
    coach.router.classify.return_value = (MessageType.GENERAL, False)
    coach.context_builder = MagicMock()
    coach.conversation_manager = MagicMock()
    coach.model_routing_enabled = True
    coach.high_stakes_routing_enabled = False
    coach.VIP_ATHLETE_IDS = set()
    coach._UUID_RE = AICoach._UUID_RE
    coach._DATE_RE = AICoach._DATE_RE
    # Bind instance methods that chat() calls
    coach._maybe_update_units_preference = MagicMock()
    coach._maybe_update_intent_snapshot = MagicMock()
    coach._save_chat_messages = MagicMock()
    coach.get_or_create_thread_with_state = MagicMock(return_value=("thread-1", False))
    coach.get_thread_history = MagicMock(return_value={"messages": []})
    coach.get_model_for_query = MagicMock(return_value=(AICoach.MODEL_HIGH_STAKES, True))
    coach.is_high_stakes_query = MagicMock(return_value=False)
    coach._build_athlete_state_for_opus = MagicMock(return_value="state")
    # _user_explicitly_requested_ids is needed by _normalize_response_for_ui
    coach._user_explicitly_requested_ids = AICoach._user_explicitly_requested_ids.__get__(coach, AICoach)
    coach._normalize_response_for_ui = AICoach._normalize_response_for_ui.__get__(coach, AICoach)
    return coach


def test_chat_kimi_success_normalizes_response():
    """Kimi success path must run _normalize_response_for_ui before returning.

    This proves the Coach Output Contract v1 normalization is live for
    production chat responses (the critical gap fixed in this refactor).
    """
    coach = _build_chat_coach()

    dirty_response = (
        "authoritative fact capsule\n"
        "response contract\n"
        "Date: 2026-02-10\n"
        "Recorded pace vs marathon pace: slower by 0:09/mi.\n"
        "You had a strong controlled session today. Keep tomorrow easy to protect recovery."
    )
    coach._query_kimi_with_fallback = AsyncMock(return_value={
        "response": dirty_response,
        "error": False,
        "model": "kimi-k2.6",
    })

    result = asyncio.run(
        coach.chat(athlete_id=uuid4(), message="How was my run today?")
    )

    assert not result.get("error"), f"Expected success, got error: {result}"
    response = result["response"]

    assert "authoritative fact capsule" not in response
    assert "response contract" not in response
    assert "Recorded pace vs marathon pace" not in response

    assert "strong controlled session" in response
    assert "recovery" in response

    coach._save_chat_messages.assert_called_once()
    saved_text = coach._save_chat_messages.call_args[0][2]
    assert "authoritative fact capsule" not in saved_text


def test_chat_kimi_failure_returns_error_without_saving_chat():
    """When Kimi (and its Sonnet fallback) fails, chat() must fail closed."""
    coach = _build_chat_coach()

    coach._query_kimi_with_fallback = AsyncMock(return_value={
        "response": "Coach is temporarily unavailable. Please try again in a moment.",
        "error": True,
        "error_detail": "Kimi + Sonnet both failed",
    })

    result = asyncio.run(
        coach.chat(athlete_id=uuid4(), message="How is my training going?")
    )

    assert result.get("error") is True
    assert "unavailable" in result["response"].lower() or "error" in result["response"].lower()
    coach._save_chat_messages.assert_not_called()


def test_chat_kimi_success_saves_model_name():
    """Kimi success path must persist model name in _save_chat_messages call."""
    coach = _build_chat_coach()

    coach._query_kimi_with_fallback = AsyncMock(return_value={
        "response": "Manageable fatigue — keep tomorrow easy.",
        "error": False,
        "model": "kimi-k2.6",
    })

    result = asyncio.run(
        coach.chat(athlete_id=uuid4(), message="How is my training going?")
    )

    assert result.get("error") is False
    coach._save_chat_messages.assert_called_once()
    call_kwargs = coach._save_chat_messages.call_args
    assert call_kwargs.kwargs.get("model") == "kimi-k2.6" or (
        len(call_kwargs.args) > 3 and call_kwargs.args[3] == "kimi-k2.6"
    )


def test_turn_guard_retries_contract_failure_before_saving_response():
    coach = _build_chat_coach()
    coach.anthropic_client = object()
    coach.query_opus = AsyncMock(
        return_value={
            "response": "Decision: postpone threshold. Tradeoff: fresher legs but one less hard stimulus. Default: move it 24 hours.",
            "error": False,
            "model": "claude-sonnet-4-6",
        }
    )

    long_unframed_response = " ".join(["You have options."] * 80)
    coach._query_kimi_with_fallback = AsyncMock(
        return_value={
            "response": long_unframed_response,
            "error": False,
            "model": "kimi-k2.6",
        }
    )

    result = asyncio.run(
        coach.chat(athlete_id=uuid4(), message="Should I postpone threshold tomorrow?")
    )

    assert result.get("error") is False
    assert "Decision:" in result["response"]
    assert "Tradeoff:" in result["response"]
    assert "Default:" in result["response"]
    coach.query_opus.assert_awaited_once()
