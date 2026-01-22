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

