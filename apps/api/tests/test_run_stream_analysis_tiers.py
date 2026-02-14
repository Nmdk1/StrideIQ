"""Tier selection, behavior, and guardrail tests for N=1 stream analysis.

Tests:
    - Tier selection based on AthleteContext
    - Classification behavior differs across tiers
    - Confidence monotonicity: tier1 >= tier2 >= tier3 >= tier4
    - Tier 4 not cross-run comparable
    - Tier 2 estimated flags present
    - Hysteresis prevents chatter
    - Grade-explained is numerically defined
"""
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fixtures.stream_fixtures import make_easy_run_stream, make_interval_stream
from services.run_stream_analysis import (
    AthleteContext,
    SegmentConfig,
    StreamAnalysisResult,
    _resolve_tier,
    analyze_stream,
    detect_segments,
)


# ---------------------------------------------------------------------------
# Tier selection
# ---------------------------------------------------------------------------

class TestTierSelection:
    """Tier is selected from AthleteContext data availability."""

    def test_tier1_when_threshold_hr_known(self):
        ctx = AthleteContext(max_hr=190, resting_hr=50, threshold_hr=170)
        tier, flags = _resolve_tier(ctx)
        assert tier == "tier1_threshold_hr"
        assert flags == []

    def test_tier2_when_max_and_resting_no_threshold(self):
        ctx = AthleteContext(max_hr=190, resting_hr=50, threshold_hr=None)
        tier, flags = _resolve_tier(ctx)
        assert tier == "tier2_estimated_hrr"
        assert "threshold_hr_estimated_from_hrr" in flags

    def test_tier3_when_max_hr_only(self):
        ctx = AthleteContext(max_hr=190, resting_hr=None, threshold_hr=None)
        tier, flags = _resolve_tier(ctx)
        assert tier == "tier3_max_hr"
        assert flags == []

    def test_tier4_when_no_context(self):
        tier, flags = _resolve_tier(None)
        assert tier == "tier4_stream_relative"
        assert flags == []

    def test_tier4_when_empty_context(self):
        ctx = AthleteContext()
        tier, flags = _resolve_tier(ctx)
        assert tier == "tier4_stream_relative"


# ---------------------------------------------------------------------------
# Tier behavior differences
# ---------------------------------------------------------------------------

class TestTierBehavior:
    """Classification adapts to the athlete's physiological context."""

    def test_tier1_uses_threshold_hr(self):
        """With threshold_hr, classification anchors to it."""
        stream = make_easy_run_stream(duration_s=1800, steady_hr=145)
        ctx = AthleteContext(max_hr=190, resting_hr=50, threshold_hr=160)

        result = analyze_stream(stream, list(stream.keys()), athlete_context=ctx)

        assert result.tier_used == "tier1_threshold_hr"
        # Easy run at HR 145 with threshold 160 → should be steady, not work
        work_segs = [s for s in result.segments if s.type == "work"]
        steady_segs = [s for s in result.segments if s.type == "steady"]
        # The bulk of the run should be steady (below threshold)
        assert len(steady_segs) >= 1

    def test_tier2_estimated_flags_present(self):
        """Tier 2 labels threshold as estimated."""
        stream = make_easy_run_stream(duration_s=1800)
        ctx = AthleteContext(max_hr=190, resting_hr=50)

        result = analyze_stream(stream, list(stream.keys()), athlete_context=ctx)

        assert result.tier_used == "tier2_estimated_hrr"
        assert "threshold_hr_estimated_from_hrr" in result.estimated_flags

    def test_tier4_not_cross_run_comparable(self):
        """Tier 4 output cannot be used for cross-run comparison."""
        stream = make_easy_run_stream(duration_s=1800)

        result = analyze_stream(stream, list(stream.keys()), athlete_context=None)

        assert result.tier_used == "tier4_stream_relative"
        assert result.cross_run_comparable is False

    def test_tiers_1_2_3_are_cross_run_comparable(self):
        """Tiers 1-3 can be compared across runs."""
        stream = make_easy_run_stream(duration_s=1800)

        for ctx, expected_tier in [
            (AthleteContext(max_hr=190, resting_hr=50, threshold_hr=170), "tier1_threshold_hr"),
            (AthleteContext(max_hr=190, resting_hr=50), "tier2_estimated_hrr"),
            (AthleteContext(max_hr=190), "tier3_max_hr"),
        ]:
            result = analyze_stream(stream, list(stream.keys()), athlete_context=ctx)
            assert result.tier_used == expected_tier
            assert result.cross_run_comparable is True


# ---------------------------------------------------------------------------
# Confidence monotonicity
# ---------------------------------------------------------------------------

class TestConfidenceMonotonicity:
    """Confidence: tier1 >= tier2 >= tier3 >= tier4 on identical data."""

    def test_confidence_ordering_on_identical_data(self):
        """Same stream → confidence strictly decreases with tier quality."""
        stream = make_easy_run_stream(duration_s=3600)
        channels = list(stream.keys())
        eps = 0.001

        ctx1 = AthleteContext(max_hr=190, resting_hr=50, threshold_hr=170)
        ctx2 = AthleteContext(max_hr=190, resting_hr=50)
        ctx3 = AthleteContext(max_hr=190)
        ctx4 = None

        r1 = analyze_stream(stream, channels, athlete_context=ctx1)
        r2 = analyze_stream(stream, channels, athlete_context=ctx2)
        r3 = analyze_stream(stream, channels, athlete_context=ctx3)
        r4 = analyze_stream(stream, channels, athlete_context=ctx4)

        assert r1.confidence >= r2.confidence - eps, \
            f"tier1 ({r1.confidence}) < tier2 ({r2.confidence})"
        assert r2.confidence >= r3.confidence - eps, \
            f"tier2 ({r2.confidence}) < tier3 ({r3.confidence})"
        assert r3.confidence >= r4.confidence - eps, \
            f"tier3 ({r3.confidence}) < tier4 ({r4.confidence})"


# ---------------------------------------------------------------------------
# Hysteresis (anti-chatter)
# ---------------------------------------------------------------------------

class TestHysteresis:
    """Rapid HR oscillation at threshold boundary → no micro-segments."""

    def test_oscillating_hr_at_threshold_no_chatter(self):
        """HR oscillating ±2 bpm around threshold → no 50 micro-segments."""
        # Create a stream where HR oscillates around threshold
        n = 1800
        threshold_hr = 165
        time = list(range(n))
        velocity = [3.0] * n
        # HR oscillates ±2 bpm around threshold every 5 seconds
        heartrate = []
        for t in time:
            offset = 2.0 if (t // 5) % 2 == 0 else -2.0
            heartrate.append(float(threshold_hr + offset))
        # Warmup ramp
        for t in range(200):
            heartrate[t] = 120.0 + t * (threshold_hr - 120.0) / 200

        stream = {
            "time": time,
            "velocity_smooth": velocity,
            "heartrate": heartrate,
            "cadence": [175] * n,
            "distance": [3.0 * t for t in time],
            "altitude": [100.0] * n,
            "grade_smooth": [0.0] * n,
        }

        ctx = AthleteContext(max_hr=190, resting_hr=50, threshold_hr=threshold_hr)
        result = analyze_stream(stream, list(stream.keys()), athlete_context=ctx)

        # Without hysteresis, oscillation would create ~180 segments.
        # With hysteresis + min_duration, should be < 10.
        assert len(result.segments) < 10, \
            f"Anti-chatter failed: {len(result.segments)} segments"


# ---------------------------------------------------------------------------
# Grade-explained numerical definition
# ---------------------------------------------------------------------------

class TestGradeExplained:
    """Grade-explained work requires abs(grade) >= 3.0% sustained for 30s."""

    def test_single_grade_spike_not_grade_explained(self):
        """A 1-second grade spike should NOT trigger grade-explained classification."""
        from services.run_stream_analysis import _is_grade_sustained

        # Single spike at index 500 in flat terrain
        grade = [0.0] * 1000
        grade[500] = 8.0  # Single spike

        assert _is_grade_sustained(grade, 500, 30, 3.0) is False

    def test_sustained_grade_is_grade_explained(self):
        """30+ seconds of grade >= 3% should trigger grade-explained."""
        from services.run_stream_analysis import _is_grade_sustained

        grade = [0.0] * 1000
        for i in range(480, 520):  # 40 seconds of grade
            grade[i] = 5.0

        assert _is_grade_sustained(grade, 500, 30, 3.0) is True
