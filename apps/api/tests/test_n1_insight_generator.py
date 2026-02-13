"""Tests for N=1 insight generator (Phase 3C).

Covers:
- Output uses "YOUR ..." and data-derived labeling.
- Banned acronyms never leak.
- Bonferroni correction applied.
- Confidence scales with effect strength + volume.
- Categorization (what_works / what_doesnt).
- Empty/no-correlation edge cases.
"""
import pytest
from unittest.mock import patch, MagicMock
from uuid import uuid4

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.n1_insight_generator import (
    generate_n1_insights,
    _build_insight_text,
    _compute_confidence,
    _friendly,
    BANNED_PATTERN,
    N1Insight,
)


# ---------------------------------------------------------------------------
# Text generation
# ---------------------------------------------------------------------------

class TestInsightTextGeneration:

    def test_text_starts_with_based_on_your_data(self):
        text = _build_insight_text(
            input_name="weekly_volume_km",
            direction="positive",
            strength="moderate",
            r=0.5,
            lag_days=2,
        )
        assert text.startswith("Based on your data:")

    def test_text_contains_your(self):
        text = _build_insight_text(
            input_name="sleep_hours",
            direction="positive",
            strength="moderate",
            r=0.4,
            lag_days=0,
        )
        assert "YOUR" in text

    def test_text_is_non_prescriptive(self):
        """Insight should be observational, not prescriptive."""
        text = _build_insight_text(
            input_name="weekly_volume_km",
            direction="positive",
            strength="strong",
            r=0.7,
            lag_days=0,
        )
        # Should say "tends to" (observation), not "you should" (prescription)
        assert "tends to" in text
        assert "you should" not in text.lower()

    def test_lag_phrasing_zero(self):
        text = _build_insight_text("sleep_hours", "positive", "moderate", 0.4, lag_days=0)
        assert "following day" not in text
        assert "within" not in text

    def test_lag_phrasing_one_day(self):
        text = _build_insight_text("sleep_hours", "positive", "moderate", 0.4, lag_days=1)
        assert "following day" in text

    def test_lag_phrasing_multi_day(self):
        text = _build_insight_text("sleep_hours", "positive", "moderate", 0.4, lag_days=3)
        assert "within 3 days" in text

    def test_negative_direction(self):
        text = _build_insight_text("intensity_score", "negative", "moderate", -0.5, lag_days=0)
        assert "decline" in text.lower()


# ---------------------------------------------------------------------------
# No banned acronyms
# ---------------------------------------------------------------------------

class TestBannedAcronyms:

    def test_no_banned_acronyms_in_generated_text(self):
        """All friendly-name mapped inputs produce clean text."""
        inputs = [
            "weekly_volume_km", "avg_hr", "sleep_hours", "daily_protein_g",
            "hrv_rmssd", "intensity_score", "efficiency", "completion_rate",
        ]
        for inp in inputs:
            text = _build_insight_text(inp, "positive", "moderate", 0.5, 0)
            assert not BANNED_PATTERN.search(text), f"Banned acronym in text for {inp}: {text}"

    def test_friendly_name_for_hrv(self):
        """HRV maps to human-readable, not rMSSD."""
        assert "variability" in _friendly("hrv_rmssd").lower()

    def test_friendly_name_for_ef(self):
        """efficiency maps to something human-readable, not EF."""
        assert "efficiency" in _friendly("efficiency").lower()


# ---------------------------------------------------------------------------
# Confidence scaling
# ---------------------------------------------------------------------------

class TestConfidence:

    def test_strong_effect_high_n_high_confidence(self):
        conf = _compute_confidence(r=0.7, p_adj=0.001, n=80)
        assert conf > 0.7

    def test_weak_effect_low_n_low_confidence(self):
        conf = _compute_confidence(r=0.31, p_adj=0.04, n=11)
        assert conf < 0.6  # low r + low n → modest confidence

    def test_confidence_between_0_and_1(self):
        for r in [0.3, 0.5, 0.7, 0.9]:
            for n in [10, 50, 100]:
                conf = _compute_confidence(r=r, p_adj=0.01, n=n)
                assert 0.0 <= conf <= 1.0


# ---------------------------------------------------------------------------
# Full generation pipeline
# ---------------------------------------------------------------------------

class TestGenerateN1Insights:

    def _mock_correlations(self, items):
        return {"correlations": items, "total_correlations_found": len(items)}

    def test_generates_insights_from_significant_correlations(self):
        corr = self._mock_correlations([
            {
                "input_name": "weekly_volume_km",
                "correlation_coefficient": 0.55,
                "p_value": 0.001,
                "sample_size": 50,
                "is_significant": True,
                "direction": "positive",
                "strength": "moderate",
                "time_lag_days": 2,
            },
        ])
        with patch("services.correlation_engine.analyze_correlations", return_value=corr):
            with patch("services.phase3_eligibility._history_stats", return_value={"history_span_days": 200}):
                insights = generate_n1_insights(uuid4(), MagicMock(), days_window=200)

        assert len(insights) == 1
        assert insights[0].source == "n1"
        assert "YOUR" in insights[0].text
        assert insights[0].evidence["r"] == 0.55

    def test_filters_out_weak_correlations(self):
        corr = self._mock_correlations([
            {
                "input_name": "sleep_hours",
                "correlation_coefficient": 0.15,  # below 0.3 threshold
                "p_value": 0.001,
                "sample_size": 100,
                "is_significant": True,
                "direction": "positive",
                "strength": "weak",
                "time_lag_days": 0,
            },
        ])
        with patch("services.correlation_engine.analyze_correlations", return_value=corr):
            with patch("services.phase3_eligibility._history_stats", return_value={"history_span_days": 200}):
                insights = generate_n1_insights(uuid4(), MagicMock(), days_window=200)

        assert len(insights) == 0

    def test_bonferroni_correction_filters(self):
        """10 tests with p=0.008 → p_adj = 0.08 → filtered."""
        items = [
            {
                "input_name": f"input_{i}",
                "correlation_coefficient": 0.4,
                "p_value": 0.008,
                "sample_size": 20,
                "is_significant": True,
                "direction": "positive",
                "strength": "moderate",
                "time_lag_days": 0,
            }
            for i in range(10)
        ]
        corr = self._mock_correlations(items)
        with patch("services.correlation_engine.analyze_correlations", return_value=corr):
            with patch("services.phase3_eligibility._history_stats", return_value={"history_span_days": 200}):
                insights = generate_n1_insights(uuid4(), MagicMock(), days_window=200)

        assert len(insights) == 0

    def test_empty_correlations_returns_empty(self):
        corr = self._mock_correlations([])
        with patch("services.correlation_engine.analyze_correlations", return_value=corr):
            with patch("services.phase3_eligibility._history_stats", return_value={"history_span_days": 200}):
                insights = generate_n1_insights(uuid4(), MagicMock(), days_window=200)

        assert insights == []

    def test_what_works_categorization(self):
        corr = self._mock_correlations([
            {
                "input_name": "sleep_hours",
                "correlation_coefficient": 0.5,
                "p_value": 0.001,
                "sample_size": 50,
                "is_significant": True,
                "direction": "positive",
                "strength": "moderate",
                "time_lag_days": 0,
            },
        ])
        with patch("services.correlation_engine.analyze_correlations", return_value=corr):
            with patch("services.phase3_eligibility._history_stats", return_value={"history_span_days": 200}):
                insights = generate_n1_insights(uuid4(), MagicMock(), days_window=200)

        assert insights[0].category == "what_works"

    def test_what_doesnt_categorization(self):
        corr = self._mock_correlations([
            {
                "input_name": "intensity_score",
                "correlation_coefficient": -0.5,
                "p_value": 0.001,
                "sample_size": 50,
                "is_significant": True,
                "direction": "negative",
                "strength": "moderate",
                "time_lag_days": 0,
            },
        ])
        with patch("services.correlation_engine.analyze_correlations", return_value=corr):
            with patch("services.phase3_eligibility._history_stats", return_value={"history_span_days": 200}):
                insights = generate_n1_insights(uuid4(), MagicMock(), days_window=200)

        assert insights[0].category == "what_doesnt"

    def test_evidence_includes_p_adjusted(self):
        corr = self._mock_correlations([
            {
                "input_name": "weekly_volume_km",
                "correlation_coefficient": 0.55,
                "p_value": 0.001,
                "sample_size": 50,
                "is_significant": True,
                "direction": "positive",
                "strength": "moderate",
                "time_lag_days": 0,
            },
        ])
        with patch("services.correlation_engine.analyze_correlations", return_value=corr):
            with patch("services.phase3_eligibility._history_stats", return_value={"history_span_days": 200}):
                insights = generate_n1_insights(uuid4(), MagicMock(), days_window=200)

        assert "p_adjusted" in insights[0].evidence
        assert insights[0].evidence["p_adjusted"] <= 0.05

    def test_max_insights_capped(self):
        items = [
            {
                "input_name": f"input_{i}",
                "correlation_coefficient": 0.5,
                "p_value": 0.0001,
                "sample_size": 50,
                "is_significant": True,
                "direction": "positive",
                "strength": "moderate",
                "time_lag_days": 0,
            }
            for i in range(20)
        ]
        corr = self._mock_correlations(items)
        with patch("services.correlation_engine.analyze_correlations", return_value=corr):
            with patch("services.phase3_eligibility._history_stats", return_value={"history_span_days": 200}):
                insights = generate_n1_insights(uuid4(), MagicMock(), days_window=200, max_insights=5)

        assert len(insights) <= 5
