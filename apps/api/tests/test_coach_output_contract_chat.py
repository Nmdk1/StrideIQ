import asyncio
from uuid import uuid4
from unittest.mock import MagicMock, patch, AsyncMock

from services.ai_coach import AICoach


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
    coach.get_model_for_query = MagicMock(return_value=(AICoach.MODEL_DEFAULT, "low"))
    coach.is_high_stakes_query = MagicMock(return_value=False)
    # _user_explicitly_requested_ids is needed by _normalize_response_for_ui
    coach._user_explicitly_requested_ids = AICoach._user_explicitly_requested_ids.__get__(coach, AICoach)
    coach._normalize_response_for_ui = AICoach._normalize_response_for_ui.__get__(coach, AICoach)
    return coach


def test_chat_gemini_success_normalizes_response():
    """Gemini success path must run _normalize_response_for_ui before returning.

    This proves the Coach Output Contract v1 normalization is live for
    production chat responses (the critical gap fixed in this refactor).
    """
    coach = _build_chat_coach()

    # Simulate Gemini returning a response with internal labels that should be stripped
    dirty_response = (
        "authoritative fact capsule\n"
        "response contract\n"
        "Date: 2026-02-10\n"
        "Recorded pace vs marathon pace: slower by 0:09/mi.\n"
        "You had a strong controlled session today. Keep tomorrow easy to protect recovery."
    )
    gemini_future = AsyncMock(return_value={
        "response": dirty_response,
        "error": False,
        "is_high_stakes": False,
        "input_tokens": 100,
        "output_tokens": 50,
    })
    coach.query_gemini = gemini_future

    result = asyncio.get_event_loop().run_until_complete(
        coach.chat(athlete_id=uuid4(), message="How was my run today?")
    )

    assert not result.get("error"), f"Expected success, got error: {result}"
    response = result["response"]

    # Internal labels must be stripped
    assert "authoritative fact capsule" not in response
    assert "response contract" not in response
    assert "Recorded pace vs marathon pace" not in response

    # Coaching content must survive
    assert "strong controlled session" in response
    assert "recovery" in response

    # Verify _save_chat_messages received the *normalized* text
    coach._save_chat_messages.assert_called_once()
    saved_text = coach._save_chat_messages.call_args[0][2]
    assert "authoritative fact capsule" not in saved_text


def test_chat_gemini_failure_returns_fail_closed_no_fallback():
    """When Gemini returns an error, chat() must return a safe fail-closed
    message with no attempt to fall back to OpenAI or any other backend.
    """
    coach = _build_chat_coach()

    # Simulate Gemini returning an error
    gemini_future = AsyncMock(return_value={
        "response": "Coach is temporarily unavailable. Please try again in a moment.",
        "error": True,
        "error_detail": "Gemini API quota exceeded",
    })
    coach.query_gemini = gemini_future

    result = asyncio.get_event_loop().run_until_complete(
        coach.chat(athlete_id=uuid4(), message="How is my training going?")
    )

    assert result.get("error") is True
    assert "unavailable" in result["response"].lower() or "error" in result["response"].lower()
    # Must NOT contain any OpenAI fallback signals
    assert "fallback_to_assistants" not in str(result)
    # Must NOT have attempted to save chat messages on error
    coach._save_chat_messages.assert_not_called()


def test_chat_no_gemini_client_returns_fail_closed():
    """When gemini_client is None, chat() must fail closed immediately."""
    coach = _build_chat_coach()
    coach.gemini_client = None  # No Gemini available

    result = asyncio.get_event_loop().run_until_complete(
        coach.chat(athlete_id=uuid4(), message="How is my training going?")
    )

    assert result.get("error") is True
    assert "not configured" in result["response"].lower() or "unavailable" in result["response"].lower()
    assert "fallback_to_assistants" not in str(result)
