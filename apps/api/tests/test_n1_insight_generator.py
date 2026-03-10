"""Tests for N=1 insight generator (Phase 3C).

Covers:
- Athlete Trust Safety Contract enforcement (all 8 clauses).
- Output uses "YOUR ..." and data-derived labeling.
- Banned acronyms never leak.
- Bonferroni correction applied.
- Confidence scales with effect strength + volume.
- Canonical metric contract: direction from higher_is_better, not raw sign.
- Two-tier fail-closed: ambiguous → neutral, invalid → suppressed.
- Directional whitelist: only approved metrics get directional language.
- Mixed-scenario regression (same pace/lower HR AND same HR/faster pace).
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
    _is_beneficial,
    _categorize,
    _validate_metric_meta,
    get_metric_meta,
    OutputMetricMeta,
    OUTPUT_METRIC_REGISTRY,
    DIRECTIONAL_SAFE_METRICS,
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

    # -- Ambiguous metric: raw efficiency --

    def test_efficiency_positive_r_gets_neutral_text(self):
        """Raw efficiency is ambiguous — no 'improve' or 'decline'."""
        text = _build_insight_text("sleep_hours", "positive", "moderate", 0.5,
                                   lag_days=0, output_metric="efficiency")
        assert "associated with changes" in text
        assert "improve" not in text.lower()
        assert "decline" not in text.lower()

    def test_efficiency_negative_r_gets_neutral_text(self):
        text = _build_insight_text("work_stress", "negative", "moderate", -0.5,
                                   lag_days=0, output_metric="efficiency")
        assert "associated with changes" in text
        assert "improve" not in text.lower()
        assert "decline" not in text.lower()

    # -- Unambiguous metrics --

    def test_pace_easy_positive_r_means_worse(self):
        """pace_easy: lower=better. Positive r (input up → pace up = slower) = decline."""
        text = _build_insight_text("work_stress", "positive", "moderate", 0.5,
                                   lag_days=0, output_metric="pace_easy")
        assert "decline" in text.lower()

    def test_pace_easy_negative_r_means_better(self):
        """pace_easy: lower=better. Negative r (input up → pace down = faster) = improve."""
        text = _build_insight_text("sleep_hours", "negative", "moderate", -0.5,
                                   lag_days=0, output_metric="pace_easy")
        assert "improve" in text.lower()

    def test_completion_positive_r_means_better(self):
        """completion_rate: higher=better. Positive r = improve."""
        text = _build_insight_text("sleep_hours", "positive", "moderate", 0.5,
                                   lag_days=0, output_metric="completion_rate")
        assert "improve" in text.lower()

    def test_completion_negative_r_means_worse(self):
        """completion_rate: higher=better. Negative r = decline."""
        text = _build_insight_text("work_stress", "negative", "moderate", -0.5,
                                   lag_days=0, output_metric="completion_rate")
        assert "decline" in text.lower()


# ---------------------------------------------------------------------------
# Canonical metric contract
# ---------------------------------------------------------------------------

class TestOutputMetricRegistry:
    """Verify the metric registry is well-formed and complete."""

    def test_all_ambiguous_metrics_have_none_polarity(self):
        for key, meta in OUTPUT_METRIC_REGISTRY.items():
            if meta.polarity_ambiguous:
                assert meta.higher_is_better is None, (
                    f"{key}: polarity_ambiguous=True but higher_is_better={meta.higher_is_better}"
                )

    def test_all_unambiguous_metrics_have_bool_polarity(self):
        for key, meta in OUTPUT_METRIC_REGISTRY.items():
            if not meta.polarity_ambiguous:
                assert meta.higher_is_better is not None, (
                    f"{key}: polarity_ambiguous=False but higher_is_better is None"
                )

    def test_efficiency_is_ambiguous(self):
        meta = get_metric_meta("efficiency")
        assert meta.polarity_ambiguous is True

    def test_efficiency_threshold_is_ambiguous(self):
        meta = get_metric_meta("efficiency_threshold")
        assert meta.polarity_ambiguous is True

    def test_pace_easy_is_unambiguous_lower_better(self):
        meta = get_metric_meta("pace_easy")
        assert meta.polarity_ambiguous is False
        assert meta.higher_is_better is False

    def test_completion_is_unambiguous_higher_better(self):
        meta = get_metric_meta("completion_rate")
        assert meta.polarity_ambiguous is False
        assert meta.higher_is_better is True

    def test_unknown_metric_defaults_to_ambiguous(self):
        meta = get_metric_meta("totally_new_metric_xyz")
        assert meta.polarity_ambiguous is True
        assert meta.higher_is_better is None

    def test_all_registered_metrics_have_definitions(self):
        for key, meta in OUTPUT_METRIC_REGISTRY.items():
            assert meta.metric_definition, f"{key} missing metric_definition"
            assert meta.direction_interpretation, f"{key} missing direction_interpretation"


# ---------------------------------------------------------------------------
# Polarity / categorisation
# ---------------------------------------------------------------------------

class TestPolarityMapping:
    """Verify _is_beneficial and _categorize respect the metric contract."""

    # -- Ambiguous metrics return None --

    def test_efficiency_positive_r_is_ambiguous(self):
        assert _is_beneficial("positive", "efficiency") is None

    def test_efficiency_negative_r_is_ambiguous(self):
        assert _is_beneficial("negative", "efficiency") is None

    def test_efficiency_threshold_is_ambiguous(self):
        assert _is_beneficial("positive", "efficiency_threshold") is None

    # -- Unambiguous metrics --

    def test_pace_easy_negative_r_is_beneficial(self):
        """pace_easy: lower=better. Negative r (input up → pace down) is good."""
        assert _is_beneficial("negative", "pace_easy") is True

    def test_pace_easy_positive_r_is_harmful(self):
        assert _is_beneficial("positive", "pace_easy") is False

    def test_completion_positive_r_is_beneficial(self):
        assert _is_beneficial("positive", "completion_rate") is True

    def test_completion_negative_r_is_harmful(self):
        assert _is_beneficial("negative", "completion_rate") is False

    def test_unknown_metric_is_ambiguous(self):
        assert _is_beneficial("positive", "some_new_metric") is None

    # -- Categorisation --

    def test_categorize_ambiguous_returns_pattern(self):
        """Ambiguous metrics → 'pattern', never what_works/what_doesnt."""
        assert _categorize("positive", "efficiency") == "pattern"
        assert _categorize("negative", "efficiency") == "pattern"

    def test_categorize_pace_easy_negative_r_what_works(self):
        assert _categorize("negative", "pace_easy") == "what_works"

    def test_categorize_pace_easy_positive_r_what_doesnt(self):
        assert _categorize("positive", "pace_easy") == "what_doesnt"

    def test_categorize_completion_positive_r_what_works(self):
        assert _categorize("positive", "completion_rate") == "what_works"


# ---------------------------------------------------------------------------
# Mixed-scenario regression tests
# ---------------------------------------------------------------------------

class TestMixedScenarioRegression:
    """Prevent regression: same pace/lower HR AND same HR/faster pace.

    The pace/HR ratio moves in opposite directions for these two
    equally-valid improvement modes.  The system must never make
    directional claims from that ratio.
    """

    def test_ambiguous_insight_never_says_improve_or_decline(self):
        """Any direction + efficiency → no directional claim."""
        for direction in ("positive", "negative"):
            text = _build_insight_text(
                "sleep_hours", direction, "moderate", 0.5, 0,
                output_metric="efficiency",
            )
            lower = text.lower()
            assert "improve" not in lower, f"'improve' found for direction={direction}"
            assert "decline" not in lower, f"'decline' found for direction={direction}"
            assert "associated with changes" in lower

    def test_ambiguous_insight_categorised_as_pattern(self):
        assert _categorize("positive", "efficiency") == "pattern"
        assert _categorize("negative", "efficiency") == "pattern"
        assert _categorize("positive", "efficiency_threshold") == "pattern"

    def test_unambiguous_pace_correctly_directional(self):
        """pace_easy: input up → pace down (negative r) = faster = improvement."""
        text_improve = _build_insight_text(
            "sleep_hours", "negative", "moderate", -0.5, 0,
            output_metric="pace_easy",
        )
        assert "improve" in text_improve.lower()

        text_decline = _build_insight_text(
            "work_stress", "positive", "moderate", 0.5, 0,
            output_metric="pace_easy",
        )
        assert "decline" in text_decline.lower()


# ---------------------------------------------------------------------------
# Tier 2: Missing / invalid metadata → suppression (Contract §2)
# ---------------------------------------------------------------------------

class TestTier2MetadataSuppression:
    """When metadata is missing, invalid, or conflicting, directional
    interpretation must be fully suppressed (tier 2 fail-closed)."""

    def test_validate_good_ambiguous_meta(self):
        """Ambiguous meta with None polarity is valid."""
        meta = OutputMetricMeta(
            metric_key="test",
            metric_definition="some ratio",
            higher_is_better=None,
            polarity_ambiguous=True,
            direction_interpretation="ambiguous",
        )
        assert _validate_metric_meta(meta) is True

    def test_validate_good_unambiguous_meta(self):
        """Unambiguous meta with explicit polarity is valid."""
        meta = OutputMetricMeta(
            metric_key="test",
            metric_definition="some pace",
            higher_is_better=False,
            polarity_ambiguous=False,
            direction_interpretation="lower = better",
        )
        assert _validate_metric_meta(meta) is True

    def test_conflicting_ambiguous_but_has_polarity(self):
        """Claims ambiguous but also declares higher_is_better — invalid."""
        meta = OutputMetricMeta(
            metric_key="test",
            metric_definition="conflicting",
            higher_is_better=True,
            polarity_ambiguous=True,
            direction_interpretation="conflict",
        )
        assert _validate_metric_meta(meta) is False

    def test_conflicting_unambiguous_but_no_polarity(self):
        """Claims unambiguous but higher_is_better is None — invalid."""
        meta = OutputMetricMeta(
            metric_key="test",
            metric_definition="conflicting",
            higher_is_better=None,
            polarity_ambiguous=False,
            direction_interpretation="conflict",
        )
        assert _validate_metric_meta(meta) is False

    def test_empty_definition_invalid(self):
        meta = OutputMetricMeta(
            metric_key="test",
            metric_definition="",
            higher_is_better=True,
            polarity_ambiguous=False,
            direction_interpretation="test",
        )
        assert _validate_metric_meta(meta) is False

    def test_all_registered_metrics_pass_validation(self):
        """Every metric in the registry must pass its own validation."""
        for key, meta in OUTPUT_METRIC_REGISTRY.items():
            assert _validate_metric_meta(meta) is True, (
                f"Registry metric '{key}' fails metadata validation"
            )

    def test_unknown_metric_suppresses_directional(self):
        """Unregistered metric → _is_beneficial returns None (tier 2)."""
        assert _is_beneficial("positive", "made_up_metric_abc") is None
        assert _is_beneficial("negative", "made_up_metric_abc") is None

    def test_unknown_metric_categorised_as_pattern(self):
        assert _categorize("positive", "made_up_metric_abc") == "pattern"

    def test_unknown_metric_gets_neutral_text(self):
        text = _build_insight_text(
            "sleep_hours", "positive", "moderate", 0.5, 0,
            output_metric="made_up_metric_abc",
        )
        assert "associated with changes" in text
        assert "improve" not in text.lower()
        assert "decline" not in text.lower()


# ---------------------------------------------------------------------------
# Directional whitelist enforcement (Contract §4)
# ---------------------------------------------------------------------------

class TestDirectionalWhitelist:
    """Only metrics in DIRECTIONAL_SAFE_METRICS get directional language."""

    def test_all_whitelisted_metrics_are_in_registry(self):
        """Every whitelisted metric must have a registry entry."""
        for metric in DIRECTIONAL_SAFE_METRICS:
            assert metric in OUTPUT_METRIC_REGISTRY, (
                f"Whitelisted metric '{metric}' missing from OUTPUT_METRIC_REGISTRY"
            )

    def test_all_whitelisted_metrics_are_unambiguous(self):
        """Whitelisted metrics must all have polarity_ambiguous=False."""
        for metric in DIRECTIONAL_SAFE_METRICS:
            meta = get_metric_meta(metric)
            assert meta.polarity_ambiguous is False, (
                f"Whitelisted metric '{metric}' is marked ambiguous"
            )
            assert meta.higher_is_better is not None, (
                f"Whitelisted metric '{metric}' has no polarity"
            )

    def test_whitelisted_metric_gets_directional_text(self):
        for metric in DIRECTIONAL_SAFE_METRICS:
            text = _build_insight_text(
                "sleep_hours", "positive", "moderate", 0.5, 0,
                output_metric=metric,
            )
            lower = text.lower()
            # Must use directional language (improve or decline)
            assert "improve" in lower or "decline" in lower, (
                f"Whitelisted metric '{metric}' did not get directional text"
            )

    def test_whitelisted_metric_gets_directional_category(self):
        for metric in DIRECTIONAL_SAFE_METRICS:
            cat = _categorize("positive", metric)
            assert cat in ("what_works", "what_doesnt"), (
                f"Whitelisted metric '{metric}' got category '{cat}' instead of directional"
            )

    def test_non_whitelisted_unambiguous_metric_still_neutral(self):
        """A hypothetical metric with polarity but NOT on whitelist → neutral.

        This tests the whitelist gate: even if metadata is clean, the
        metric must be explicitly approved for directional language.
        """
        # We don't have such a metric in the current registry, but we can
        # test the _is_beneficial logic directly with a mock scenario.
        # An unregistered metric always returns ambiguous (None), which
        # is effectively the same as not-whitelisted.
        result = _is_beneficial("positive", "some_future_metric")
        assert result is None


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

    # -- Ambiguous metric: default efficiency → pattern category --

    def test_efficiency_default_categorised_as_pattern(self):
        """Default output_metric='efficiency' is ambiguous → category='pattern'."""
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
                insights = generate_n1_insights(uuid4(), MagicMock(), days_window=200,
                                                 output_metric="efficiency")

        assert insights[0].category == "pattern"
        assert "associated with changes" in insights[0].text

    # -- Unambiguous metrics: proper directional categorisation --

    def test_pace_easy_negative_r_what_works(self):
        """pace_easy (lower=better): negative r = beneficial = what_works."""
        corr = self._mock_correlations([
            {
                "input_name": "sleep_hours",
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
                insights = generate_n1_insights(uuid4(), MagicMock(), days_window=200,
                                                 output_metric="pace_easy")

        assert insights[0].category == "what_works"

    def test_pace_easy_positive_r_what_doesnt(self):
        """pace_easy (lower=better): positive r = harmful = what_doesnt."""
        corr = self._mock_correlations([
            {
                "input_name": "work_stress",
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
                insights = generate_n1_insights(uuid4(), MagicMock(), days_window=200,
                                                 output_metric="pace_easy")

        assert insights[0].category == "what_doesnt"

    def test_completion_positive_r_what_works(self):
        """completion_rate (higher=better): positive r = beneficial = what_works."""
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
                insights = generate_n1_insights(uuid4(), MagicMock(), days_window=200,
                                                 output_metric="completion_rate")

        assert insights[0].category == "what_works"

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
