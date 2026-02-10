from unittest.mock import MagicMock, patch

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


def test_system_instructions_include_conversational_aia_requirement():
    assert "Conversational A->I->A requirement" in AICoach.SYSTEM_INSTRUCTIONS
