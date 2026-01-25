from __future__ import annotations

from core.database import SessionLocal
from services.ai_coach import AICoach


def test_guardrail_does_not_trigger_on_prescription_numbers() -> None:
    db = SessionLocal()
    try:
        coach = AICoach(db)
        # Pure prescription: should not require receipts.
        assert coach._looks_like_uncited_numeric_answer("Do 2 easy runs, then 1 long run this week.") is False
        assert coach._looks_like_uncited_numeric_answer("Tomorrow: run 30 min easy, then 6x20s strides.") is False
    finally:
        db.close()


def test_guardrail_triggers_on_uncited_athlete_metric_claims() -> None:
    db = SessionLocal()
    try:
        coach = AICoach(db)
        assert coach._looks_like_uncited_numeric_answer("Your ATL is 50 and CTL is 42, so TSB is -8.") is True
        assert coach._looks_like_uncited_numeric_answer("In the last 30 days you ran 90 miles and your pace improved 4%.") is True
        assert coach._looks_like_uncited_numeric_answer("Your efficiency trend is down 12% over the last 6 weeks.") is True
    finally:
        db.close()


def test_guardrail_allows_metric_claims_with_receipts_markers() -> None:
    db = SessionLocal()
    try:
        coach = AICoach(db)
        assert coach._looks_like_uncited_numeric_answer("On 2026-01-15 your TSB was -8.\n\nReceipts:\n- 2026-01-15 (activity 123e4567-e89b-12d3-a456-426614174000)") is False
        assert coach._looks_like_uncited_numeric_answer("On 2026-01-15 (activity 123e4567-e89b-12d3-a456-426614174000), you ran 8.5 km @ 5:30/km (avg HR 152 bpm).") is False
    finally:
        db.close()


def test_longest_run_deterministic_gate_only_triggers_on_questions() -> None:
    db = SessionLocal()
    try:
        coach = AICoach(db)

        # Direct asks should be treated as comparison questions.
        assert coach._looks_like_direct_comparison_question("What's my longest run?", keyword="longest", noun="run") is True
        assert coach._looks_like_direct_comparison_question("Show me my longest run", keyword="longest", noun="run") is True
        assert coach._looks_like_direct_comparison_question("How far was my longest run", keyword="longest", noun="run") is True

        # Narrative statements must NOT trigger deterministic comparison answers.
        assert (
            coach._looks_like_direct_comparison_question(
                "Today's run was the longest run I've done since coming back. I feel slow.",
                keyword="longest",
                noun="run",
            )
            is False
        )
        assert coach._looks_like_direct_comparison_question("My longest run was today.", keyword="longest", noun="run") is False
    finally:
        db.close()


def test_return_context_phrase_detection() -> None:
    db = SessionLocal()
    try:
        coach = AICoach(db)
        assert coach._has_return_context("it was the longest run i've done since coming back") is True
        assert coach._has_return_context("since returning from injury i've felt slower") is True
        assert coach._has_return_context("my longest run this year") is False
    finally:
        db.close()


def test_context_injection_builder_is_pure_and_explicit() -> None:
    """
    Pure function behavior:
    - Given an ambiguous "since coming back" message + prior user history, the injection must
      include explicit scope/clarification instructions + flags + snippets.
    """
    db = SessionLocal()
    try:
        coach = AICoach(db)
        msg = "Today's run was the longest run I've done since coming back. I feel so slow."
        prior = [
            "I took 6 weeks off with a calf thing.",
            "I'm easing back in.",
        ]
        injected = coach._build_context_injection_pure(message=msg, prior_user_messages=prior)
        assert injected is not None
        lower = injected.lower()

        # Flags present
        assert "internal coach context" in lower
        assert "return_context_detected" in lower
        assert "comparison_language_detected" in lower

        # Explicit instruction must be present (production beta requirement)
        assert "do not assume 365-day or all-time scope" in lower
        assert "always ask for the exact return date" in lower
        assert "longest/slowest/fastest/best/worst/most/least/hardest/easiest" in lower

        # Snippets included
        assert "took 6 weeks off" in lower
        assert "easing back in" in lower
    finally:
        db.close()

