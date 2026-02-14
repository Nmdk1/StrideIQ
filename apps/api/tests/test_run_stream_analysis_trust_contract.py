"""Trust-Safety Contract Tests for run stream analysis.

Verifies that all new derived metrics are registered in OutputMetricMeta,
no directional claims are made for ambiguous metrics, and suppression
behavior works correctly.

AC coverage:
    Trust-safety gates from Phase 2 Test Spec section 2.
"""
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fixtures.stream_fixtures import make_easy_run_stream


# ===========================================================================
# METRIC REGISTRATION — OutputMetricMeta
# ===========================================================================

class TestMetricRegistration:
    """All Phase 2 derived metrics must be registered in OutputMetricMeta."""

    def test_cardiac_drift_registered(self):
        """cardiac_drift_pct metric is explicitly registered in OUTPUT_METRIC_REGISTRY."""
        from services.n1_insight_generator import OUTPUT_METRIC_REGISTRY, OutputMetricMeta

        assert "cardiac_drift_pct" in OUTPUT_METRIC_REGISTRY, \
            "cardiac_drift_pct not explicitly registered (would fall back to unknown-ambiguous default)"
        meta = OUTPUT_METRIC_REGISTRY["cardiac_drift_pct"]
        assert isinstance(meta, OutputMetricMeta)

    def test_pace_drift_registered(self):
        """pace_drift_pct metric is explicitly registered."""
        from services.n1_insight_generator import OUTPUT_METRIC_REGISTRY

        assert "pace_drift_pct" in OUTPUT_METRIC_REGISTRY

    def test_cadence_shift_registered(self):
        """cadence_trend_bpm_per_km metric is explicitly registered."""
        from services.n1_insight_generator import OUTPUT_METRIC_REGISTRY

        assert "cadence_trend_bpm_per_km" in OUTPUT_METRIC_REGISTRY

    def test_plan_execution_variance_registered(self):
        """plan_execution_variance metric is explicitly registered."""
        from services.n1_insight_generator import OUTPUT_METRIC_REGISTRY

        assert "plan_execution_variance" in OUTPUT_METRIC_REGISTRY

    def test_all_phase2_metrics_are_ambiguous_by_default(self):
        """Phase 2 metrics default to ambiguous polarity (trust posture)."""
        from services.n1_insight_generator import OUTPUT_METRIC_REGISTRY

        phase2_metrics = [
            "cardiac_drift_pct",
            "pace_drift_pct",
            "cadence_trend_bpm_per_km",
            "plan_execution_variance",
        ]

        for metric_name in phase2_metrics:
            assert metric_name in OUTPUT_METRIC_REGISTRY, f"{metric_name} not registered"
            meta = OUTPUT_METRIC_REGISTRY[metric_name]
            # Ambiguous polarity = directional claims NOT allowed
            assert meta.polarity_ambiguous is True, (
                f"{metric_name} polarity_ambiguous is {meta.polarity_ambiguous}, expected True"
            )


# ===========================================================================
# DIRECTIONAL LANGUAGE SUPPRESSION
# ===========================================================================

class TestDirectionalSuppression:
    """No directional claims for ambiguous metrics."""

    def test_analysis_output_has_no_natural_language_strings(self):
        """Structured output contains only typed fields, no prose."""
        from services.run_stream_analysis import analyze_stream

        stream = make_easy_run_stream()
        result = analyze_stream(stream, list(stream.keys()))

        # Check segments — should be typed, not prose
        for seg in result.segments:
            assert seg.type in ("warmup", "work", "recovery", "cooldown", "steady")
            # No free-text fields that could contain directional language

        # Check moments — typed enum only
        valid_types = {
            "cardiac_drift_onset", "cadence_drop", "cadence_surge",
            "pace_surge", "pace_fade", "grade_adjusted_anomaly",
            "recovery_hr_delay", "effort_zone_transition",
        }
        for m in result.moments:
            assert m.type in valid_types

    def test_drift_output_is_numeric_not_textual(self):
        """Drift output is numeric (float/None), never a text interpretation."""
        from services.run_stream_analysis import analyze_stream

        stream = make_easy_run_stream()
        result = analyze_stream(stream, list(stream.keys()))

        drift = result.drift
        assert drift.cardiac_pct is None or isinstance(drift.cardiac_pct, float)
        assert drift.pace_pct is None or isinstance(drift.pace_pct, float)
        assert drift.cadence_trend_bpm_per_km is None or isinstance(
            drift.cadence_trend_bpm_per_km, float
        )

    def test_plan_comparison_is_numeric_deltas(self):
        """Plan comparison fields are numeric deltas, not prose."""
        from services.run_stream_analysis import compare_plan_summary, detect_segments

        stream = make_easy_run_stream(duration_s=3480)
        segments = detect_segments(
            time=stream["time"],
            velocity=stream["velocity_smooth"],
            heartrate=stream["heartrate"],
            grade=stream.get("grade_smooth"),
        )

        planned = {
            "target_duration_minutes": 60.0,
            "target_distance_km": 10.0,
            "target_pace_per_km_seconds": 360,
            "segments": None,
        }

        result = compare_plan_summary(segments, stream, planned)
        assert result is not None
        assert isinstance(result.duration_delta_min, (int, float))
        assert isinstance(result.pace_delta_s_km, (int, float, type(None)))


# ===========================================================================
# FAIL-CLOSED BEHAVIOR
# ===========================================================================

class TestFailClosedBehavior:
    """Missing/invalid metadata → directional interpretation suppressed."""

    def test_unregistered_metric_treated_as_ambiguous(self):
        """If a metric is not in OUTPUT_METRIC_REGISTRY, get_metric_meta returns ambiguous default."""
        from services.n1_insight_generator import get_metric_meta

        # A metric that should NOT be explicitly registered
        meta = get_metric_meta("nonexistent_fake_metric_xyz")
        # get_metric_meta returns a default ambiguous OutputMetricMeta for unknown metrics
        assert meta.polarity_ambiguous is True
        assert meta.higher_is_better is None

    def test_analysis_confidence_is_deterministic_float(self):
        """Confidence score is a deterministic float in [0,1], not stochastic."""
        from services.run_stream_analysis import analyze_stream

        stream = make_easy_run_stream()
        result1 = analyze_stream(stream, list(stream.keys()))
        result2 = analyze_stream(stream, list(stream.keys()))

        assert isinstance(result1.confidence, float)
        assert 0.0 <= result1.confidence <= 1.0
        assert result1.confidence == result2.confidence  # deterministic
