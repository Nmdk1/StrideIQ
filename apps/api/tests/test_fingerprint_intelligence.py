"""
Tests for fingerprint intelligence wiring: confirmed CorrelationFinding
rows surfacing in the morning voice, coach brief, and coach_noticed.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from services.fingerprint_context import (
    build_fingerprint_prompt_section,
    format_finding_line,
    get_confirmed_findings,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_finding(**overrides):
    """Return a MagicMock CorrelationFinding with sensible defaults."""
    defaults = {
        "id": uuid4(),
        "athlete_id": uuid4(),
        "input_name": "sleep_hours",
        "output_metric": "efficiency",
        "direction": "positive",
        "time_lag_days": 1,
        "correlation_coefficient": 0.62,
        "p_value": 0.001,
        "sample_size": 45,
        "strength": "strong",
        "times_confirmed": 12,
        "first_detected_at": datetime.now(timezone.utc) - timedelta(days=90),
        "last_confirmed_at": datetime.now(timezone.utc) - timedelta(hours=3),
        "last_surfaced_at": None,
        "insight_text": "More sleep improves your next-day efficiency",
        "category": "what_works",
        "confidence": 0.85,
        "is_active": True,
        "lifecycle_state": None,
        "lifecycle_state_updated_at": None,
        "resolving_context": None,
        "threshold_value": 6.2,
        "threshold_direction": "below_hurts",
        "r_below_threshold": -0.71,
        "r_above_threshold": 0.15,
        "n_below_threshold": 18,
        "n_above_threshold": 27,
        "asymmetry_ratio": 3.1,
        "asymmetry_direction": "negative_dominant",
        "effect_below_baseline": -0.42,
        "effect_above_baseline": 0.14,
        "baseline_value": 7.0,
        "decay_half_life_days": 2.0,
        "decay_type": "exponential",
    }
    defaults.update(overrides)
    m = MagicMock()
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


ATHLETE_ID = uuid4()


# ---------------------------------------------------------------------------
# Unit: format_finding_line
# ---------------------------------------------------------------------------

class TestFormatFindingLine:

    def test_verbose_includes_threshold(self):
        f = _make_finding()
        line = format_finding_line(f, verbose=True)
        assert "cliff at 6.2 hours" in line
        assert "Below: 18 observations" in line

    def test_verbose_includes_asymmetry(self):
        f = _make_finding()
        line = format_finding_line(f, verbose=True)
        assert "3.1x" in line
        assert "downside hits harder" in line

    def test_verbose_includes_decay(self):
        f = _make_finding()
        line = format_finding_line(f, verbose=True)
        assert "half-life 2.0 days" in line
        assert "exponential" in line

    def test_compact_single_line(self):
        f = _make_finding()
        line = format_finding_line(f, verbose=False)
        assert "cliff at 6.2 hours" in line
        assert "\n" not in line

    def test_no_layers_omits_details(self):
        f = _make_finding(
            threshold_value=None,
            asymmetry_ratio=None,
            decay_half_life_days=None,
            time_lag_days=0,
            lifecycle_state=None,
        )
        line = format_finding_line(f, verbose=False)
        # Narration tier comes from times_confirmed (founder rule:
        # 3-5 EMERGING, 6-9 REPEATED, 10+ CONFIRMED). The legacy
        # strength label was the trust-rupture vector.
        assert "CONFIRMED 12x" in line
        assert "cliff" not in line
        assert "Asymmetry" not in line

    def test_includes_confirmation_count(self):
        f = _make_finding(times_confirmed=47, lifecycle_state=None)
        line = format_finding_line(f, verbose=False)
        assert "CONFIRMED 47x" in line


# ---------------------------------------------------------------------------
# Unit: build_fingerprint_prompt_section
# ---------------------------------------------------------------------------

class TestBuildFingerprintPromptSection:
    """Section assembly is what matters here; the eligibility chokepoint
    has its own dedicated tests in ``test_finding_eligibility``. We stub
    ``get_confirmed_findings`` so these tests stay focused on formatting
    and grouping behavior rather than re-asserting the chokepoint's
    query mechanics."""

    def test_returns_none_when_no_findings(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.nulls_last.return_value = MagicMock()
        with patch(
            "services.fingerprint_context.get_confirmed_findings",
            return_value=[],
        ):
            result = build_fingerprint_prompt_section(ATHLETE_ID, db)
        assert result is None

    def test_verbose_section_has_header(self):
        f = _make_finding()
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        with patch(
            "services.fingerprint_context.get_confirmed_findings",
            return_value=[f],
        ):
            result = build_fingerprint_prompt_section(ATHLETE_ID, db, verbose=True)
        assert "Personal Fingerprint" in result
        assert "ACTIVE" in result

    def test_compact_section_has_instruction(self):
        f = _make_finding()
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        with patch(
            "services.fingerprint_context.get_confirmed_findings",
            return_value=[f],
        ):
            result = build_fingerprint_prompt_section(ATHLETE_ID, db, verbose=False)
        assert "Treat ACTIVE as fact" in result

    def test_limits_findings(self):
        findings = [_make_finding(times_confirmed=50 - i) for i in range(12)]
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        with patch(
            "services.fingerprint_context.get_confirmed_findings",
            return_value=findings[:8],
        ):
            result = build_fingerprint_prompt_section(ATHLETE_ID, db, max_findings=8)
        assert result is not None
        assert result.count("→") == 8  # 8 finding lines, each with "→"


# ---------------------------------------------------------------------------
# Integration: coach_noticed fingerprint priority
# ---------------------------------------------------------------------------

class TestCoachNoticedFingerprint:

    def test_surfaces_recent_fingerprint(self):
        from routers.home import compute_coach_noticed

        f = _make_finding(
            athlete_id=ATHLETE_ID,
            last_confirmed_at=datetime.now(timezone.utc) - timedelta(hours=2),
            times_confirmed=15,
            insight_text="More sleep improves your efficiency",
            threshold_value=6.2,
            asymmetry_ratio=3.1,
        )

        mock_db = MagicMock()
        query_chain = MagicMock()
        query_chain.filter.return_value = query_chain
        query_chain.order_by.return_value = query_chain
        query_chain.limit.return_value = query_chain
        query_chain.all.return_value = [f]
        mock_db.query.return_value = query_chain

        with patch("routers.home._is_finding_in_cooldown", return_value=False):
            result = compute_coach_noticed(str(ATHLETE_ID), mock_db)

        assert result is not None
        assert result.source == "fingerprint"
        assert "r=" not in result.text
        assert "p-value" not in result.text
        assert "sleep" in result.text.lower()
        assert "threshold" in result.text.lower() or "6.2" in result.text
        assert "consistent across" in result.text
        assert "45" in result.text
        assert result.finding_id is not None

    def test_fingerprint_requires_recent_confirmation(self):
        from routers.home import compute_coach_noticed

        mock_db = MagicMock()
        query_chain = MagicMock()
        query_chain.filter.return_value = query_chain
        query_chain.order_by.return_value = query_chain
        query_chain.limit.return_value = query_chain
        query_chain.all.return_value = []
        mock_db.query.return_value = query_chain

        with patch("services.home_signals.aggregate_signals", side_effect=Exception("skip")), \
             patch("services.insight_feed.build_insight_feed_cards", side_effect=Exception("skip")):
            result = compute_coach_noticed(str(ATHLETE_ID), mock_db)

        assert result is None

    def test_fingerprint_requires_min_confirmations(self):
        from routers.home import compute_coach_noticed

        mock_db = MagicMock()
        query_chain = MagicMock()
        query_chain.filter.return_value = query_chain
        query_chain.order_by.return_value = query_chain
        query_chain.limit.return_value = query_chain
        query_chain.all.return_value = []
        mock_db.query.return_value = query_chain

        with patch("services.home_signals.aggregate_signals", side_effect=Exception("skip")), \
             patch("services.insight_feed.build_insight_feed_cards", side_effect=Exception("skip")):
            result = compute_coach_noticed(str(ATHLETE_ID), mock_db)

        assert result is None


# ---------------------------------------------------------------------------
# Integration: coach system prompt contains fingerprint instructions
# ---------------------------------------------------------------------------

class TestCoachPromptFingerprint:

    def test_gemini_prompt_has_fingerprint_section(self):
        import inspect
        from services.ai_coach import AICoach
        source = inspect.getsource(AICoach.query_gemini)
        assert "PERSONAL FINGERPRINT" in source

    def test_opus_prompt_has_fingerprint_section(self):
        import inspect
        from services.ai_coach import AICoach
        source = inspect.getsource(AICoach.query_opus)
        assert "PERSONAL FINGERPRINT" in source

    def test_home_briefing_prompt_has_fingerprint_contract(self):
        import inspect
        from routers.home import generate_coach_home_briefing
        source = inspect.getsource(generate_coach_home_briefing)
        assert "PERSONAL FINGERPRINT CONTRACT" in source
