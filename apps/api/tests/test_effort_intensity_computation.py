"""RSI-Alpha — AC-2 (Data Layer): Effort Intensity Computation Tests

Tests the tier-dispatched effort intensity scalar computation per ADR-064.

AC coverage:
    AC-2: Effort gradient data correctness per tier.

All tests expect RED (FAILED, not SKIPPED) until compute_effort_intensity exists.
"""
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fixtures.stream_fixtures import make_easy_run_stream, make_interval_stream
from services.run_stream_analysis import AthleteContext, analyze_stream


def _get_compute_effort_intensity():
    """Lazy import that produces a clear FAIL (not skip) when missing."""
    from services.run_stream_analysis import compute_effort_intensity
    return compute_effort_intensity


# ---------------------------------------------------------------------------
# Tier 1: threshold_hr anchored
# ---------------------------------------------------------------------------

class TestTier1Effort:
    """Tier 1: effort = HR / threshold_hr, clamped [0, 1]."""

    def test_at_threshold_effort_is_one(self):
        """HR == threshold_hr -> effort = 1.0."""
        compute = _get_compute_effort_intensity()
        ctx = AthleteContext(threshold_hr=165, max_hr=186, resting_hr=48)
        result = compute(hr=165, ctx=ctx, tier="tier1_threshold_hr")
        assert abs(result - 1.0) < 0.001

    def test_below_threshold(self):
        """HR=132, threshold=165 -> effort ~ 0.800."""
        compute = _get_compute_effort_intensity()
        ctx = AthleteContext(threshold_hr=165, max_hr=186, resting_hr=48)
        result = compute(hr=132, ctx=ctx, tier="tier1_threshold_hr")
        assert abs(result - 0.800) < 0.01

    def test_above_threshold_clamped_to_one(self):
        """HR=186 (above threshold) -> effort clamped to 1.0, not 1.127."""
        compute = _get_compute_effort_intensity()
        ctx = AthleteContext(threshold_hr=165, max_hr=186, resting_hr=48)
        result = compute(hr=186, ctx=ctx, tier="tier1_threshold_hr")
        assert result == 1.0


# ---------------------------------------------------------------------------
# Tier 2: Karvonen HRR estimated threshold
# ---------------------------------------------------------------------------

class TestTier2Effort:
    """Tier 2: effort = (HR - resting) / (est_threshold - resting), clamped."""

    def test_karvonen_hrr_mid_effort(self):
        """resting=48, max=186, est_threshold=48+0.88*(186-48)=169.44.
        HR=132 -> effort = (132-48)/(169.44-48) = 84/121.44 ~ 0.692."""
        compute = _get_compute_effort_intensity()
        ctx = AthleteContext(max_hr=186, resting_hr=48)
        result = compute(hr=132, ctx=ctx, tier="tier2_estimated_hrr")
        assert abs(result - 0.692) < 0.02

    def test_tier2_above_threshold_clamped(self):
        """HR above estimated threshold -> clamped to 1.0."""
        compute = _get_compute_effort_intensity()
        ctx = AthleteContext(max_hr=186, resting_hr=48)
        result = compute(hr=186, ctx=ctx, tier="tier2_estimated_hrr")
        assert result == 1.0


# ---------------------------------------------------------------------------
# Tier 3: %max_hr
# ---------------------------------------------------------------------------

class TestTier3Effort:
    """Tier 3: effort = HR / max_hr, clamped [0, 1]."""

    def test_pct_max_hr(self):
        """max_hr=186, HR=149 -> effort = 149/186 ~ 0.801."""
        compute = _get_compute_effort_intensity()
        ctx = AthleteContext(max_hr=186)
        result = compute(hr=149, ctx=ctx, tier="tier3_max_hr")
        assert abs(result - 0.801) < 0.01


# ---------------------------------------------------------------------------
# Tier 4: stream-relative percentile
# ---------------------------------------------------------------------------

class TestTier4Effort:
    """Tier 4: percentile rank of HR within run -> effort [0, 1]."""

    def test_percentile_rank(self):
        """Effort for a given HR is its rank within the stream's HR distribution."""
        compute = _get_compute_effort_intensity()
        stream = make_easy_run_stream(duration_s=3600)
        hr_series = stream["heartrate"]
        sorted_hr = sorted(hr_series)
        median_hr = sorted_hr[len(sorted_hr) // 2]

        result = compute(
            hr=median_hr,
            ctx=AthleteContext(),
            tier="tier4_stream_relative",
            hr_series=hr_series,
        )
        assert 0.3 < result < 0.7, f"Median HR effort={result}, expected ~0.5"

    def test_tier4_sets_cross_run_comparable_false(self):
        """Tier 4 cannot be compared across runs."""
        stream = make_easy_run_stream(duration_s=1800)
        channels = list(stream.keys())
        result = analyze_stream(stream, channels_available=channels, athlete_context=AthleteContext())
        assert result.cross_run_comparable is False
        assert result.tier_used == "tier4_stream_relative"


# ---------------------------------------------------------------------------
# Velocity fallback
# ---------------------------------------------------------------------------

class TestVelocityFallback:
    """When HR channel is missing, effort uses velocity-based formula."""

    def test_velocity_based_effort_when_no_hr(self):
        """Stream with no heartrate -> effort computed from velocity."""
        compute = _get_compute_effort_intensity()
        result = compute(
            hr=None,
            velocity=2.8,
            ctx=AthleteContext(threshold_pace_per_km=300.0),
            tier="tier1_threshold_hr",
        )
        assert 0.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------

class TestEffortInvariants:
    """Cross-cutting invariants for all tiers."""

    @pytest.mark.parametrize("tier", [
        "tier1_threshold_hr", "tier2_estimated_hrr", "tier3_max_hr", "tier4_stream_relative"
    ])
    def test_effort_always_clamped_0_1(self, tier):
        """Effort is always in [0.0, 1.0] regardless of tier or extreme inputs."""
        compute = _get_compute_effort_intensity()
        ctx = AthleteContext(threshold_hr=165, max_hr=186, resting_hr=48)
        stream = make_easy_run_stream(duration_s=600)
        hr_series = stream["heartrate"]

        for hr in [0, 50, 100, 165, 186, 220, 300]:
            result = compute(
                hr=hr,
                ctx=ctx,
                tier=tier,
                hr_series=hr_series,
            )
            assert 0.0 <= result <= 1.0, (
                f"Effort={result} out of [0,1] for tier={tier}, HR={hr}"
            )

    def test_effort_array_length_matches_point_count(self):
        """Full-stream analysis effort array matches point_count."""
        stream = make_easy_run_stream(duration_s=1800)
        channels = list(stream.keys())
        ctx = AthleteContext(threshold_hr=165, max_hr=186, resting_hr=48)
        result = analyze_stream(stream, channels_available=channels, athlete_context=ctx)

        assert result.point_count == 1800
        assert hasattr(result, "effort_intensity"), \
            "StreamAnalysisResult must include effort_intensity array"
        assert len(result.effort_intensity) == result.point_count
