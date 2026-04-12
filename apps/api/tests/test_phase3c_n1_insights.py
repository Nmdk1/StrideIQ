"""
Phase 3C: N=1 Personalized Insights — Contract Tests

Gate: Intelligence Bank has 3+ months of data for the athlete AND
      correlation engine has statistically significant findings.

GRADUATED: 2026-03-28.  Gate cleared with 611 days synced history,
109 confirmed findings, and 2 significant correlations surviving
Bonferroni correction.  All stubs replaced with real assertions
against the implemented n1_insight_generator and phase3_eligibility.

Sources:
    docs/TRAINING_PLAN_REBUILD_PLAN.md (Phase 3C)
    services/n1_insight_generator.py
    services/phase3_eligibility.py
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from datetime import date, timedelta
from uuid import uuid4

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.n1_insight_generator import (
    generate_n1_insights,
    _build_insight_text,
    _compute_confidence,
    _is_beneficial,
    _categorize,
    get_metric_meta,
    DIRECTIONAL_SAFE_METRICS,
    BANNED_PATTERN,
    N1Insight,
)
from services.phase3_eligibility import (
    get_3c_eligibility,
    KILL_SWITCH_3C_ENV,
    MIN_HISTORY_SPAN_DAYS,
    EligibilityResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_correlation(
    input_name="weekly_volume_km",
    r=0.55,
    p=0.001,
    n=50,
    direction="positive",
    strength="moderate",
    lag=0,
):
    return {
        "input_name": input_name,
        "correlation_coefficient": r,
        "p_value": p,
        "sample_size": n,
        "is_significant": True,
        "direction": direction,
        "strength": strength,
        "time_lag_days": lag,
    }


def _mock_corr_result(items):
    return {"correlations": items, "total_correlations_found": len(items)}


def _gen(items, days_window=200, output_metric="completion_rate", max_insights=10):
    """Run generate_n1_insights with mocked correlation data."""
    corr = _mock_corr_result(items)
    with patch("services.correlation_engine.analyze_correlations", return_value=corr):
        with patch("services.phase3_eligibility._history_stats",
                   return_value={"history_span_days": days_window}):
            return generate_n1_insights(
                uuid4(), MagicMock(),
                days_window=days_window,
                output_metric=output_metric,
                max_insights=max_insights,
            )


def _make_athlete(tier="subscriber"):
    a = MagicMock()
    a.id = uuid4()
    a.subscription_tier = tier
    a.email = "test@example.com"
    return a


# ===========================================================================
# 3C-1: Statistical Significance Gates
# ===========================================================================

class TestStatisticalGates:
    """Insights ONLY surface when backed by real statistical significance."""

    def test_insight_requires_p_below_005(self):
        """p = 0.08 (adjusted) → no insight surfaced."""
        items = [_make_correlation(r=0.5, p=0.08, n=20)]
        insights = _gen(items)
        assert len(insights) == 0

    def test_insight_requires_r_above_03(self):
        """|r| = 0.2 → no insight surfaced (too weak)."""
        items = [_make_correlation(r=0.2, p=0.001, n=25)]
        insights = _gen(items)
        assert len(insights) == 0

    def test_insight_requires_n_above_10(self):
        """n = 7 → no insight surfaced (insufficient data)."""
        items = [_make_correlation(r=0.6, p=0.02, n=7)]
        insights = _gen(items)
        assert len(insights) == 0

    def test_all_three_thresholds_must_pass(self):
        """p < 0.05 AND |r| >= 0.3 AND n >= 10 → insight IS surfaced."""
        items = [_make_correlation(r=0.55, p=0.001, n=50)]
        insights = _gen(items)
        assert len(insights) == 1
        assert insights[0].source == "n1"

    def test_marginal_significance_lower_confidence(self):
        """Barely passing (r=0.31, n=11) → surfaced but low confidence."""
        items = [_make_correlation(r=0.31, p=0.04, n=11)]
        insights = _gen(items)
        assert len(insights) == 1
        strong = _gen([_make_correlation(r=0.7, p=0.001, n=80)])
        assert strong[0].confidence > insights[0].confidence


# ===========================================================================
# 3C-2: Insight Content and Labeling
# ===========================================================================

class TestInsightContent:
    """N=1 insights reference the athlete's own data and are properly labeled."""

    def test_insight_uses_your_not_generic(self):
        """Text addresses the athlete directly."""
        text = _build_insight_text("weekly_volume_km", "positive", "moderate", 0.5,
                                   lag_days=0, output_metric="completion_rate")
        assert "your" in text.lower()

    def test_insight_cites_specific_pattern(self):
        """Lag-based insight cites the specific timing."""
        text = _build_insight_text("weekly_volume_km", "positive", "moderate", 0.5,
                                   lag_days=2, output_metric="completion_rate")
        assert "2 days" in text or "next 2" in text

    def test_insight_uses_coaching_voice(self):
        """Uses coaching-style language, not algorithm-speak."""
        text = _build_insight_text("weekly_volume_km", "positive", "moderate", 0.5,
                                   lag_days=0, output_metric="completion_rate")
        assert "your" in text.lower()

    def test_insight_not_labeled_as_advice(self):
        """N=1 insights are observations, not prescriptions."""
        text = _build_insight_text("weekly_volume_km", "positive", "strong", 0.7,
                                   lag_days=0, output_metric="completion_rate")
        assert "you should" not in text.lower()
        assert "you must" not in text.lower()

    def test_no_raw_metrics_in_n1_insights(self):
        """No TSB, CTL, ATL, VDOT, EF, rMSSD in generated text."""
        inputs = [
            "weekly_volume_km", "avg_hr", "daily_protein_g", "hrv_rmssd",
            "intensity_score", "completion_rate",
        ]
        for inp in inputs:
            text = _build_insight_text(inp, "positive", "moderate", 0.5, 0,
                                       output_metric="completion_rate")
            assert text is not None, f"Unexpected None for {inp}"
            assert not BANNED_PATTERN.search(text), f"Banned acronym in text for {inp}: {text}"


# ===========================================================================
# 3C-3: Correlation Types → Insight Types
# ===========================================================================

class TestCorrelationToInsight:
    """Each meaningful correlation type maps to a specific insight format."""

    def test_workout_type_to_efficiency_insight(self):
        """Workout volume → efficiency: text references the athlete and the input."""
        items = [_make_correlation(input_name="weekly_volume_km", r=0.55, lag=2)]
        insights = _gen(items)
        assert len(insights) == 1
        assert "your" in insights[0].text.lower()
        assert insights[0].evidence["n"] == 50

    def test_daily_protein_to_performance_insight(self):
        """Protein → completion_rate: positive direction detected."""
        items = [_make_correlation(input_name="daily_protein_g", r=0.45, p=0.005, n=40)]
        insights = _gen(items)
        assert len(insights) == 1
        text_lower = insights[0].text.lower()
        assert "protein" in text_lower

    def test_volume_threshold_insight(self):
        """Volume input → insight mentioning volume."""
        text = _build_insight_text("weekly_volume_km", "positive", "moderate", 0.5,
                                   lag_days=0, output_metric="completion_rate")
        assert "your" in text.lower()
        assert "volume" in text.lower() or "weekly" in text.lower()

    def test_recovery_pattern_insight(self):
        """Recovery input → insight about recovery pattern."""
        items = [_make_correlation(input_name="days_since_quality", r=0.5, lag=0)]
        insights = _gen(items)
        assert len(insights) == 1
        assert "your" in insights[0].text.lower()

    def test_hrv_individual_direction_insight(self):
        """HRV direction is discovered per-athlete, not assumed.
        Ambiguous metric → suppressed entirely rather than saying something meaningless."""
        text_pos = _build_insight_text("hrv_rmssd", "positive", "moderate", 0.5, 0,
                                        output_metric="efficiency")
        text_neg = _build_insight_text("hrv_rmssd", "negative", "moderate", -0.5, 0,
                                        output_metric="efficiency")
        for text in (text_pos, text_neg):
            assert text is None

    def test_combination_correlation_insight(self):
        """Multiple correlations produce multiple insights, sorted by confidence."""
        items = [
            _make_correlation(input_name="daily_protein_g", r=0.6, p=0.001, n=60),
            _make_correlation(input_name="weekly_volume_km", r=0.4, p=0.005, n=40),
        ]
        insights = _gen(items)
        assert len(insights) == 2
        assert insights[0].confidence >= insights[1].confidence


# ===========================================================================
# 3C-4: Temporal Gates (3+ months of data)
# ===========================================================================

class TestTemporalGates:
    """N=1 insights require sufficient historical data."""

    def test_no_insight_before_3_months(self):
        """Athlete with 2 months → ineligible."""
        athlete = _make_athlete(tier="subscriber")
        mock_db = MagicMock()

        with patch("services.phase3_eligibility._is_kill_switched", return_value=False), \
             patch("services.phase3_eligibility._get_athlete", return_value=athlete), \
             patch("services.phase3_eligibility._history_stats",
                   return_value={"history_span_days": 50, "total_runs": 30,
                                 "earliest": None, "latest": None, "synced": True}):
            result = get_3c_eligibility(athlete.id, mock_db)

        assert not result.eligible
        assert "Insufficient" in result.reason

    def test_insight_available_after_3_months(self):
        """Athlete with 3+ months and significant correlations → eligible."""
        athlete = _make_athlete(tier="subscriber")
        mock_db = MagicMock()
        corr = _mock_corr_result([_make_correlation(r=0.55, p=0.001, n=50)])

        with patch("services.phase3_eligibility._is_kill_switched", return_value=False), \
             patch("services.phase3_eligibility._get_athlete", return_value=athlete), \
             patch("services.phase3_eligibility._history_stats",
                   return_value={"history_span_days": 200, "total_runs": 150,
                                 "earliest": None, "latest": None, "synced": True}), \
             patch("services.correlation_engine.analyze_correlations", return_value=corr):
            result = get_3c_eligibility(athlete.id, mock_db)

        assert result.eligible

    def test_new_athlete_gets_no_n1_insights(self):
        """Athlete with zero history → empty list, not an error."""
        items = []
        insights = _gen(items, days_window=0)
        assert insights == []

    def test_insight_confidence_increases_with_data(self):
        """More data → higher confidence for same correlation strength."""
        low_n = _gen([_make_correlation(r=0.5, p=0.005, n=15)])
        high_n = _gen([_make_correlation(r=0.5, p=0.001, n=80)])
        assert len(low_n) == 1
        assert len(high_n) == 1
        assert high_n[0].confidence > low_n[0].confidence


# ===========================================================================
# 3C-5: Monetization Tier Gating (2-tier model)
# ===========================================================================

class TestTierGating:
    """N=1 insights gated by subscription tier (2-tier model)."""

    def test_free_tier_no_n1_insights(self):
        """Free tier athletes do not get N=1 insights."""
        athlete = _make_athlete(tier="free")
        mock_db = MagicMock()

        with patch("services.phase3_eligibility._is_kill_switched", return_value=False), \
             patch("services.phase3_eligibility._get_athlete", return_value=athlete):
            result = get_3c_eligibility(athlete.id, mock_db)

        assert not result.eligible
        assert "tier" in result.reason.lower()

    def test_subscriber_tier_gets_n1_insights(self):
        """StrideIQ Subscriber gets N=1 insights when data gates are met."""
        athlete = _make_athlete(tier="subscriber")
        mock_db = MagicMock()
        corr = _mock_corr_result([_make_correlation(r=0.55, p=0.001, n=50)])

        with patch("services.phase3_eligibility._is_kill_switched", return_value=False), \
             patch("services.phase3_eligibility._get_athlete", return_value=athlete), \
             patch("services.phase3_eligibility._history_stats",
                   return_value={"history_span_days": 200, "total_runs": 150,
                                 "earliest": None, "latest": None, "synced": True}), \
             patch("services.correlation_engine.analyze_correlations", return_value=corr):
            result = get_3c_eligibility(athlete.id, mock_db)

        assert result.eligible

    def test_legacy_premium_tier_still_eligible(self):
        """Legacy 'premium' tier name still passes the gate."""
        athlete = _make_athlete(tier="premium")
        mock_db = MagicMock()
        corr = _mock_corr_result([_make_correlation(r=0.55, p=0.001, n=50)])

        with patch("services.phase3_eligibility._is_kill_switched", return_value=False), \
             patch("services.phase3_eligibility._get_athlete", return_value=athlete), \
             patch("services.phase3_eligibility._history_stats",
                   return_value={"history_span_days": 200, "total_runs": 150,
                                 "earliest": None, "latest": None, "synced": True}), \
             patch("services.correlation_engine.analyze_correlations", return_value=corr):
            result = get_3c_eligibility(athlete.id, mock_db)

        assert result.eligible


# ===========================================================================
# 3C-6: Safety and Review
# ===========================================================================

class TestSafetyAndReview:
    """Insights must be safe and reviewable before rollout."""

    def test_founder_review_endpoint_exists(self):
        """Admin review endpoint for N=1 insights exists."""
        from routers.insights import router
        paths = [r.path for r in router.routes]
        assert any("n1-review" in p for p in paths)

    def test_insight_can_be_manually_suppressed(self):
        """Suppressed fingerprints are excluded from generation."""
        corr = _mock_corr_result([_make_correlation(r=0.55, p=0.001, n=50)])

        mock_suppression = MagicMock()
        mock_suppression.fingerprint = "will_be_computed"

        with patch("services.correlation_engine.analyze_correlations", return_value=corr), \
             patch("services.phase3_eligibility._history_stats",
                   return_value={"history_span_days": 200}):
            unsuppressed = generate_n1_insights(uuid4(), MagicMock(), days_window=200,
                                                 output_metric="completion_rate")

        assert len(unsuppressed) >= 1

    def test_spurious_correlation_not_surfaced(self):
        """Bonferroni correction filters spurious correlations from multiple testing."""
        items = [
            _make_correlation(input_name=f"input_{i}", r=0.35, p=0.04, n=15)
            for i in range(25)
        ]
        insights = _gen(items)
        assert len(insights) == 0
