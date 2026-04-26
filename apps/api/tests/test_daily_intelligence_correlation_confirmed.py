from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from services.daily_intelligence import (
    DailyIntelligenceEngine,
    IntelligenceResult,
)


def _finding(
    *,
    times_confirmed: int = 4,
    confidence: float = 0.72,
    lag_days: int = 2,
    corr: float = 0.48,
):
    return SimpleNamespace(
        id=uuid4(),
        input_name="sleep_hours",
        output_metric="efficiency",
        direction="positive",
        time_lag_days=lag_days,
        correlation_coefficient=corr,
        times_confirmed=times_confirmed,
        strength="moderate",
        category="pattern",
        confidence=confidence,
        first_detected_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        insight_text=(
            "Based on your data: YOUR efficiency is noticeably associated with changes "
            "within 2 days when your sleep hours are higher."
        ),
    )


def test_correlation_confirmed_confidence_is_capped(monkeypatch):
    """Boosted confidence must never exceed 1.0."""
    engine = DailyIntelligenceEngine()
    athlete_id = uuid4()
    result = IntelligenceResult(athlete_id=athlete_id, target_date=date(2026, 2, 16))
    finding = _finding(times_confirmed=20, confidence=0.8)

    marked = {"ids": None}

    monkeypatch.setattr(
        "services.correlation_persistence.get_surfaceable_findings",
        lambda _athlete_id, _db: [finding],
    )
    monkeypatch.setattr(
        "services.correlation_persistence.mark_surfaced",
        lambda ids, _db: marked.update({"ids": ids}),
    )

    engine._rule_correlation_confirmed(athlete_id, date(2026, 2, 16), db=None, result=result)

    assert len(result.insights) == 1
    assert result.insights[0].confidence == 1.0
    assert marked["ids"] == [finding.id]


def test_correlation_confirmed_message_includes_specificity_anchors(monkeypatch):
    """Narration must cite lag, evidence weight, and numeric evidence.

    The wording for the evidence weight comes from
    ``services.intelligence.narration_tiers.evidence_phrase`` so that
    counts below ``CONFIRMED_THRESHOLD`` never carry confident wording.
    """
    engine = DailyIntelligenceEngine()
    athlete_id = uuid4()
    result = IntelligenceResult(athlete_id=athlete_id, target_date=date(2026, 2, 16))
    finding = _finding(times_confirmed=4, confidence=0.65, lag_days=2, corr=0.46)

    monkeypatch.setattr(
        "services.correlation_persistence.get_surfaceable_findings",
        lambda _athlete_id, _db: [finding],
    )
    monkeypatch.setattr(
        "services.correlation_persistence.mark_surfaced",
        lambda _ids, _db: None,
    )

    engine._rule_correlation_confirmed(athlete_id, date(2026, 2, 16), db=None, result=result)

    assert len(result.insights) == 1
    message = result.insights[0].message
    assert "within 2 days" in message
    assert "observed 4 times so far" in message
    assert "Confirmed 4 times" not in message, (
        "times_confirmed=4 must not carry 'confirmed' wording. See "
        "narration_tiers.CONFIRMED_THRESHOLD."
    )
    assert "Evidence: r=0.46." in message


def test_correlation_confirmed_message_uses_repeated_tier_for_mid_counts(monkeypatch):
    """At times_confirmed >= 6, the wording shifts from emerging to repeated."""
    engine = DailyIntelligenceEngine()
    athlete_id = uuid4()
    result = IntelligenceResult(athlete_id=athlete_id, target_date=date(2026, 2, 16))
    finding = _finding(times_confirmed=7, confidence=0.7, lag_days=1, corr=0.55)

    monkeypatch.setattr(
        "services.correlation_persistence.get_surfaceable_findings",
        lambda _athlete_id, _db: [finding],
    )
    monkeypatch.setattr(
        "services.correlation_persistence.mark_surfaced",
        lambda _ids, _db: None,
    )

    engine._rule_correlation_confirmed(athlete_id, date(2026, 2, 16), db=None, result=result)

    message = result.insights[0].message
    assert "repeated across 7 of your runs" in message
    assert "confirmed across" not in message.lower()


def test_correlation_confirmed_message_uses_confirmed_tier_for_high_counts(monkeypatch):
    """Only at times_confirmed >= 10 does the wording become 'confirmed'."""
    engine = DailyIntelligenceEngine()
    athlete_id = uuid4()
    result = IntelligenceResult(athlete_id=athlete_id, target_date=date(2026, 2, 16))
    finding = _finding(times_confirmed=12, confidence=0.85, lag_days=0, corr=0.6)

    monkeypatch.setattr(
        "services.correlation_persistence.get_surfaceable_findings",
        lambda _athlete_id, _db: [finding],
    )
    monkeypatch.setattr(
        "services.correlation_persistence.mark_surfaced",
        lambda _ids, _db: None,
    )

    engine._rule_correlation_confirmed(athlete_id, date(2026, 2, 16), db=None, result=result)

    message = result.insights[0].message
    assert "confirmed across 12 of your runs" in message
