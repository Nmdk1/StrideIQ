from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from services.ai_coach import AICoach
from services.coaching import _guardrails


def _coach_for_v2_guard() -> AICoach:
    coach = AICoach(db=MagicMock())
    coach._normalize_response_for_ui = MagicMock(
        side_effect=lambda user_message, assistant_message: assistant_message
    )
    coach._record_turn_guard_event = MagicMock()
    return coach


def test_v2_guard_normalizes_and_strips_emojis():
    coach = _coach_for_v2_guard()
    coach._normalize_response_for_ui = MagicMock(
        return_value="Late pace drift likely came from fatigue. ✅"
    )

    ok, response, reason = coach._finalize_v2_response_with_turn_guard(
        athlete_id=uuid4(),
        user_message="Why did my pace drift late?",
        response_text="raw response",
        conversation_context=[],
        turn_id="turn-1",
        is_synthetic_probe=False,
        is_organic=True,
    )

    assert ok is True
    assert response == "Late pace drift likely came from fatigue."
    assert reason is None
    coach._normalize_response_for_ui.assert_called_once()
    coach._record_turn_guard_event.assert_called_once()
    assert coach._record_turn_guard_event.call_args.kwargs["event"] == "pass_v2_packet"


def test_v2_guard_rejects_profile_edit_answer_without_route():
    coach = _coach_for_v2_guard()

    ok, response, reason = coach._finalize_v2_response_with_turn_guard(
        athlete_id=uuid4(),
        user_message="Where do I change my birthdate?",
        response_text="Your birthdate will not change today's workout.",
        conversation_context=[],
        turn_id="turn-2",
        is_synthetic_probe=False,
        is_organic=True,
    )

    assert ok is False
    assert response == "Your birthdate will not change today's workout."
    assert reason == "latest_turn_mismatch"
    assert (
        coach._record_turn_guard_event.call_args.kwargs["event"]
        == "v2_guardrail_failed:latest_turn_mismatch"
    )


def test_v2_guard_accepts_profile_edit_route_answer():
    coach = _coach_for_v2_guard()

    ok, response, reason = coach._finalize_v2_response_with_turn_guard(
        athlete_id=uuid4(),
        user_message="Where can I update my birthdate?",
        response_text="Go to /settings -> Personal Information -> Birthdate.",
        conversation_context=[],
        turn_id="turn-3",
        is_synthetic_probe=False,
        is_organic=True,
    )

    assert ok is True
    assert response == "Go to /settings -> Personal Information -> Birthdate."
    assert reason is None


def test_v2_guard_does_not_classify_race_answer_as_profile_from_age_language():
    coach = _coach_for_v2_guard()

    ok, response, reason = coach._finalize_v2_response_with_turn_guard(
        athlete_id=uuid4(),
        user_message="Is 39:15 realistic for Saturday with 253 feet of gain?",
        response_text=(
            "At 57, this is where I would set the target: 39:15 is realistic "
            "if you keep the first mile controlled. The 253 feet of course gain "
            "means the pacing should be effort-based on the early hill, then close."
        ),
        conversation_context=[],
        turn_id="turn-race",
        is_synthetic_probe=False,
        is_organic=True,
    )

    assert ok is True
    assert "253 feet" in response
    assert reason is None


def test_v2_guard_allows_decision_point_without_structural_gate():
    # DECISION_POINT structural validation was removed — the guard uses intent-band
    # matching and voice enforcement, not rigid output structure enforcement.
    coach = _coach_for_v2_guard()

    ok, response, reason = coach._finalize_v2_response_with_turn_guard(
        athlete_id=uuid4(),
        user_message="Should I postpone threshold tomorrow?",
        response_text="Skip it. The tradeoff: one missed threshold won't cost fitness, and compounding fatigue will.",
        conversation_context=[],
        turn_id="turn-4",
        is_synthetic_probe=False,
        is_organic=True,
    )

    assert ok is True
    assert reason is None


def test_v2_guard_enforces_conversation_contract_output(monkeypatch):
    coach = _coach_for_v2_guard()
    enforce_spy = MagicMock(return_value="enforced response")
    monkeypatch.setattr(
        _guardrails,
        "enforce_conversation_contract_output",
        enforce_spy,
    )

    ok, response, reason = coach._finalize_v2_response_with_turn_guard(
        athlete_id=uuid4(),
        user_message="Why did my pace drift late?",
        response_text="Late pace drift likely came from fatigue.",
        conversation_context=[],
        turn_id="turn-5",
        is_synthetic_probe=False,
        is_organic=True,
    )

    assert ok is True
    assert response == "enforced response"
    assert reason is None
    enforce_spy.assert_called_once_with(
        "Why did my pace drift late?",
        "Late pace drift likely came from fatigue.",
        conversation_context=[],
    )


def test_v2_guard_trims_quick_check_before_contract_validation():
    coach = _coach_for_v2_guard()
    long_response = " ".join(
        ["Focus the next easy run on recovery and relaxed mechanics."] * 12
    )

    ok, response, reason = coach._finalize_v2_response_with_turn_guard(
        athlete_id=uuid4(),
        user_message="Quick check — what should my next easy run focus on? Keep it brief.",
        response_text=long_response,
        conversation_context=[],
        turn_id="turn-6",
        is_synthetic_probe=False,
        is_organic=True,
    )

    assert ok is True
    assert len(response.split()) <= 80
    assert reason is None
    assert coach._record_turn_guard_event.call_args.kwargs["event"] == "pass_v2_packet"
