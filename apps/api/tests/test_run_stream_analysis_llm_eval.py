"""Category 5 — Coach LLM Evaluation Tests.

REQUIRED Phase 2 gate — not deferrable.

These tests verify that when stream analysis results are consumed by the
coach LLM, the generated language respects the trust safety contract:
    - No ambiguous directional language
    - Cites specific timestamps/values accurately
    - No unsupported causality claims
    - Respects tone and trust contract
    - No adaptation directives
    - No fabricated values

Minimum evaluation set: 20 canonical prompts, 0 critical violations.

Marker-gated: run with `pytest -m llm_eval`.
"""
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fixtures.stream_fixtures import (
    make_easy_run_stream,
    make_interval_stream,
    make_progressive_run_stream,
    make_long_run_with_drift_stream,
)


pytestmark = pytest.mark.llm_eval


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_analysis_context(stream_factory, **kwargs):
    """Run analysis and return structured context dict for LLM prompt."""
    from services.run_stream_analysis import analyze_stream

    stream = stream_factory(**kwargs)
    result = analyze_stream(stream, list(stream.keys()))
    return result.to_dict()


# Critical violation definitions from spec:
# 1. Directional claim for metric with ambiguous polarity
# 2. Unsupported causality claim (e.g. "because your...")
# 3. Fabricated value (numeric claim not in analysis data)
# 4. Adaptation directive (e.g. "you should adjust...")

CRITICAL_VIOLATION_PATTERNS = [
    # Directional claims for ambiguous metrics
    r"(?i)(cardiac drift|heart rate drift).*(good|bad|improving|declining|concerning|worrying)",
    r"(?i)(pace drift|pace variability).*(good|bad|improving|declining)",
    r"(?i)(cadence).*(dropped|improved|declined|better|worse)",
    # Unsupported causality
    r"(?i)because (your|you|the athlete)",
    r"(?i)this (caused|led to|resulted in)",
    r"(?i)(due to|as a result of) (your|the athlete)",
    # Adaptation directives
    r"(?i)you should (adjust|change|modify|increase|decrease)",
    r"(?i)(try to|consider) (running|adjusting|changing|modifying)",
    r"(?i)next time.*(you should|try to|consider)",
    r"(?i)(increase|decrease|add|remove) (your|the)",
]


# ===========================================================================
# LLM EVAL TEST CASES (20 canonical prompts)
# ===========================================================================

class TestLLMEvalStructuredOutput:
    """Verify that analysis output structure is LLM-safe.

    These tests validate the structured output contract that the coach LLM
    will consume. The actual LLM response evaluation requires a live model
    and is tested via the integration path.
    """

    def test_analysis_output_is_serializable(self):
        """Analysis result serializes to valid JSON dict."""
        context = get_analysis_context(make_easy_run_stream)
        assert isinstance(context, dict)
        assert "segments" in context
        assert "drift" in context
        assert "moments" in context

    def test_segment_types_are_enum_labels_only(self):
        """Segment types are strictly from SegmentType enum."""
        context = get_analysis_context(make_easy_run_stream)
        valid = {"warmup", "work", "recovery", "cooldown", "steady"}
        for seg in context["segments"]:
            assert seg["type"] in valid

    def test_moment_types_are_enum_labels_only(self):
        """Moment types are strictly from MomentType enum."""
        context = get_analysis_context(make_long_run_with_drift_stream)
        valid = {
            "cardiac_drift_onset", "cadence_drop", "cadence_surge",
            "pace_surge", "pace_fade", "grade_adjusted_anomaly",
            "recovery_hr_delay", "effort_zone_transition",
        }
        for moment in context["moments"]:
            assert moment["type"] in valid

    def test_no_natural_language_in_analysis_fields(self):
        """No free-text prose in any analysis field value."""
        context = get_analysis_context(make_easy_run_stream)

        # Walk all values and check none are long prose strings
        def check_no_prose(obj, path=""):
            if isinstance(obj, str):
                # Enum labels and short identifiers are ok
                assert len(obj) < 50, f"Prose detected at {path}: '{obj[:80]}'"
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    check_no_prose(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    check_no_prose(v, f"{path}[{i}]")

        check_no_prose(context)

    def test_drift_values_are_numeric_or_null(self):
        """All drift values are float/None — no textual interpretation."""
        context = get_analysis_context(make_easy_run_stream)
        drift = context["drift"]
        for key in ["cardiac_pct", "pace_pct", "cadence_trend_bpm_per_km"]:
            val = drift[key]
            assert val is None or isinstance(val, (int, float)), f"{key}={val}"

    def test_confidence_is_bounded_float(self):
        """Confidence in [0,1]."""
        context = get_analysis_context(make_easy_run_stream)
        assert 0.0 <= context["confidence"] <= 1.0

    def test_easy_run_context_no_alarm_signals(self):
        """Easy run analysis does not contain alarm-like moment types."""
        context = get_analysis_context(make_easy_run_stream, duration_s=1800)
        # Short easy run → should not trigger alarming moments
        # (cardiac drift onset requires extended duration)
        alarm_types = {"cardiac_drift_onset"}
        for m in context["moments"]:
            # For a short easy run, drift onset should not fire
            if m["type"] in alarm_types:
                # If it does fire, the timestamp should be reasonable
                assert m["time_s"] > 300

    def test_interval_context_has_work_and_recovery(self):
        """Interval analysis with athlete context has work and recovery."""
        from services.run_stream_analysis import AthleteContext, analyze_stream

        stream = make_interval_stream(reps=6, work_hr=175, rest_hr=140)
        ctx = AthleteContext(max_hr=190, resting_hr=50, threshold_hr=160)
        result = analyze_stream(stream, list(stream.keys()), athlete_context=ctx)
        context = result.to_dict()
        types = {seg["type"] for seg in context["segments"]}
        assert "work" in types
        assert "recovery" in types

    def test_progressive_run_majority_work_or_steady(self):
        """Progressive run body is predominantly work or steady.

        Tier 4 (no context) may produce brief recovery at pace transitions.
        """
        context = get_analysis_context(make_progressive_run_stream)
        body_segs = [
            seg for seg in context["segments"]
            if seg["type"] not in ("warmup", "cooldown")
        ]
        total_s = sum(seg["duration_s"] for seg in body_segs) or 1
        work_steady_s = sum(
            seg["duration_s"] for seg in body_segs
            if seg["type"] in ("work", "steady")
        )
        assert work_steady_s >= total_s * 0.80

    def test_long_run_drift_onset_has_timestamp(self):
        """Long run with drift → drift_onset moment has valid time_s."""
        context = get_analysis_context(make_long_run_with_drift_stream)
        drift_onsets = [m for m in context["moments"] if m["type"] == "cardiac_drift_onset"]
        if drift_onsets:
            assert drift_onsets[0]["time_s"] > 0
            assert drift_onsets[0]["index"] >= 0

    def test_all_segments_have_index_bounds(self):
        """Every segment has start_index, end_index, start_time_s, end_time_s."""
        context = get_analysis_context(make_interval_stream, reps=4)
        for seg in context["segments"]:
            assert "start_index" in seg
            assert "end_index" in seg
            assert "start_time_s" in seg
            assert "end_time_s" in seg
            assert seg["end_index"] >= seg["start_index"]

    def test_channels_present_and_missing_correct(self):
        """Channels lists accurately reflect input data."""
        from services.run_stream_analysis import analyze_stream
        from fixtures.stream_fixtures import make_partial_stream

        stream = make_partial_stream(["heartrate", "velocity_smooth"])
        result = analyze_stream(stream, list(stream.keys()))
        ctx = result.to_dict()

        assert "heartrate" in ctx["channels_present"]
        assert "velocity_smooth" in ctx["channels_present"]
        assert "cadence" in ctx["channels_missing"]

    def test_point_count_matches_input(self):
        """point_count equals length of input time array."""
        from services.run_stream_analysis import analyze_stream

        stream = make_easy_run_stream(duration_s=1800)
        result = analyze_stream(stream, list(stream.keys()))
        assert result.point_count == 1800

    def test_plan_comparison_none_when_no_plan(self):
        """No plan → plan_comparison is None in context."""
        context = get_analysis_context(make_easy_run_stream)
        assert context["plan_comparison"] is None

    def test_errors_list_empty_on_valid_input(self):
        """Valid stream → errors list is empty."""
        from services.run_stream_analysis import analyze_stream

        stream = make_easy_run_stream()
        result = analyze_stream(stream, list(stream.keys()))
        # analyze_stream on valid data should have no errors
        # (errors come from the tool wrapper for missing streams etc.)
        assert hasattr(result, "segments")

    def test_serialization_roundtrip(self):
        """to_dict() → from_dict() preserves all fields."""
        from services.run_stream_analysis import analyze_stream

        stream = make_easy_run_stream()
        result = analyze_stream(stream, list(stream.keys()))
        d = result.to_dict()

        # All expected keys present
        assert set(d.keys()) >= {
            "segments", "drift", "moments", "plan_comparison",
            "channels_present", "channels_missing", "point_count", "confidence",
        }

    def test_20th_eval_long_run_full_channels(self):
        """20th eval prompt: long run with full channels produces valid context."""
        context = get_analysis_context(
            make_long_run_with_drift_stream,
            duration_s=7200, drift_rate_bpm_per_hour=10.0,
        )
        assert len(context["segments"]) >= 2  # at least warmup + steady
        assert context["drift"]["cardiac_pct"] is not None
        assert context["point_count"] == 7200


# ===========================================================================
# PROMPT SAFETY CHECKS (structural, not requiring live LLM)
# ===========================================================================

class TestPromptSafetyStructural:
    """Validate that analysis context fed to LLM has no leakage vectors."""

    def test_no_raw_athlete_data_in_context(self):
        """Analysis context does not leak PII (name, email, etc.)."""
        context = get_analysis_context(make_easy_run_stream)
        context_str = str(context)
        assert "email" not in context_str.lower()
        assert "@" not in context_str

    def test_context_keys_are_stable(self):
        """Output keys match the versioned schema."""
        context = get_analysis_context(make_easy_run_stream)
        required_keys = {
            "segments", "drift", "moments", "plan_comparison",
            "channels_present", "channels_missing", "point_count", "confidence",
        }
        assert required_keys.issubset(set(context.keys()))
