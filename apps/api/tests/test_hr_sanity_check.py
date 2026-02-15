"""A2: HR Sanity Check — tests for detecting unreliable HR data.

Tests the hr_sanity_check function and its integration into analyze_stream.
Tests written FIRST (red → green → commit).

Test categories:
    1. Detection: unreliable HR is flagged (inverted, flatline, dropout)
    2. Passthrough: normal HR is NOT flagged
    3. Fallback: when HR unreliable, effort uses pace-based estimation
    4. Segments: when HR unreliable, segments use pace thresholds
    5. Result fields: hr_reliable and hr_note in StreamAnalysisResult
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fixtures.hr_sanity_fixtures import (
    make_inverted_hr_stream,
    make_flatline_hr_stream,
    make_dropout_hr_stream,
    make_normal_hr_stream,
)
from services.run_stream_analysis import (
    analyze_stream,
    hr_sanity_check,
    AthleteContext,
)


# ---------------------------------------------------------------------------
# 1. Detection tests
# ---------------------------------------------------------------------------

class TestHRSanityDetection:
    """Verify that unreliable HR patterns are correctly detected."""

    def test_inverted_hr_detected_as_unreliable(self):
        """HR inversely correlated with pace → unreliable.

        May be caught by low-median-HR check or inverse-correlation check —
        either way, the HR is flagged as unreliable.
        """
        stream = make_inverted_hr_stream()
        result = hr_sanity_check(
            heartrate=stream["heartrate"],
            velocity=stream["velocity_smooth"],
        )
        assert result["reliable"] is False
        assert len(result["reason"]) > 0

    def test_flatline_hr_detected_as_unreliable(self):
        """HR flatlined at resting level during hard effort → unreliable."""
        stream = make_flatline_hr_stream()
        result = hr_sanity_check(
            heartrate=stream["heartrate"],
            velocity=stream["velocity_smooth"],
        )
        assert result["reliable"] is False

    def test_dropout_hr_detected_as_unreliable(self):
        """HR drops to 0 for sustained period → unreliable."""
        stream = make_dropout_hr_stream()
        result = hr_sanity_check(
            heartrate=stream["heartrate"],
            velocity=stream["velocity_smooth"],
        )
        assert result["reliable"] is False
        assert "drop" in result["reason"].lower() or "zero" in result["reason"].lower()

    def test_normal_hr_passes_sanity_check(self):
        """Normal HR positively correlated with pace → reliable."""
        stream = make_normal_hr_stream()
        result = hr_sanity_check(
            heartrate=stream["heartrate"],
            velocity=stream["velocity_smooth"],
        )
        assert result["reliable"] is True

    def test_no_hr_data_returns_reliable_false(self):
        """Missing HR channel → reliable is False (no HR to trust)."""
        result = hr_sanity_check(
            heartrate=None,
            velocity=[3.0] * 100,
        )
        # No HR data means we can't trust it — default to pace
        assert result["reliable"] is False

    def test_empty_hr_returns_reliable_false(self):
        """Empty HR list → reliable is False."""
        result = hr_sanity_check(
            heartrate=[],
            velocity=[3.0] * 100,
        )
        assert result["reliable"] is False


# ---------------------------------------------------------------------------
# 2. Integration: analyze_stream with unreliable HR
# ---------------------------------------------------------------------------

class TestAnalyzeStreamHRFallback:
    """Verify analyze_stream falls back correctly when HR is unreliable."""

    def _ctx_with_threshold_hr(self) -> AthleteContext:
        """Athlete context that would normally resolve to Tier 1."""
        return AthleteContext(
            max_hr=190,
            resting_hr=55,
            threshold_hr=170,
            threshold_pace_per_km=300.0,  # ~5:00/km
        )

    def test_inverted_hr_overrides_tier_to_pace_based(self):
        """When HR is unreliable, tier_used should NOT be an HR-based tier."""
        stream = make_inverted_hr_stream()
        ctx = self._ctx_with_threshold_hr()
        result = analyze_stream(
            stream_data=stream,
            channels_available=list(stream.keys()),
            athlete_context=ctx,
        )
        # Should have fallen back from tier1 to tier4 (pace-based)
        assert result.hr_reliable is False
        assert result.tier_used == "tier4_stream_relative"

    def test_inverted_hr_has_note(self):
        """When HR is unreliable, hr_note should explain why."""
        stream = make_inverted_hr_stream()
        result = analyze_stream(
            stream_data=stream,
            channels_available=list(stream.keys()),
            athlete_context=self._ctx_with_threshold_hr(),
        )
        assert result.hr_note is not None
        assert len(result.hr_note) > 0

    def test_inverted_hr_effort_reflects_pace_not_hr(self):
        """Effort intensity should increase when pace increases, not when HR increases.

        In the inverted stream: fast finish has low HR but high pace.
        If effort followed HR, the fast finish would show LOW effort.
        With pace fallback, the fast finish should show HIGH effort.
        """
        stream = make_inverted_hr_stream(duration_s=5400)
        result = analyze_stream(
            stream_data=stream,
            channels_available=list(stream.keys()),
            athlete_context=self._ctx_with_threshold_hr(),
        )
        assert result.hr_reliable is False

        # Last 10% of effort (fast finish) should be higher than first 10% (slow warmup)
        n = len(result.effort_intensity)
        first_10_pct = result.effort_intensity[:n // 10]
        last_10_pct = result.effort_intensity[-(n // 10):]

        avg_first = sum(first_10_pct) / len(first_10_pct)
        avg_last = sum(last_10_pct) / len(last_10_pct)

        assert avg_last > avg_first, (
            f"Fast finish effort ({avg_last:.3f}) should be higher than "
            f"slow warmup effort ({avg_first:.3f}) when using pace fallback"
        )

    def test_flatline_hr_falls_back_to_pace(self):
        """Flatline HR triggers fallback; effort reflects the progressive pace."""
        stream = make_flatline_hr_stream()
        result = analyze_stream(
            stream_data=stream,
            channels_available=list(stream.keys()),
            athlete_context=self._ctx_with_threshold_hr(),
        )
        assert result.hr_reliable is False

        # Progressive run: effort should generally increase over time
        n = len(result.effort_intensity)
        first_quarter = result.effort_intensity[:n // 4]
        last_quarter = result.effort_intensity[-(n // 4):]
        assert sum(last_quarter) / len(last_quarter) > sum(first_quarter) / len(first_quarter)

    def test_normal_hr_preserves_original_tier(self):
        """Normal HR should NOT trigger fallback — original tier preserved."""
        stream = make_normal_hr_stream()
        ctx = self._ctx_with_threshold_hr()
        result = analyze_stream(
            stream_data=stream,
            channels_available=list(stream.keys()),
            athlete_context=ctx,
        )
        assert result.hr_reliable is True
        assert result.tier_used == "tier1_threshold_hr"
        assert result.hr_note is None

    def test_dropout_hr_segments_not_all_recovery(self):
        """With HR dropout, segments shouldn't all be classified as recovery.

        The dropout fixture has steady 3.0 m/s throughout — that's a real run.
        Without the sanity check, the 0-HR section gets classified as recovery.
        With the check, pace-based classification should give work/steady.
        """
        stream = make_dropout_hr_stream()
        result = analyze_stream(
            stream_data=stream,
            channels_available=list(stream.keys()),
            athlete_context=self._ctx_with_threshold_hr(),
        )
        assert result.hr_reliable is False

        segment_types = [s.type for s in result.segments]
        # Should NOT be all recovery — the athlete was actually running
        recovery_count = segment_types.count("recovery")
        assert recovery_count < len(segment_types), (
            f"All {len(segment_types)} segments classified as recovery — "
            f"pace-based fallback didn't work"
        )


# ---------------------------------------------------------------------------
# 3. Result field presence
# ---------------------------------------------------------------------------

class TestHRReliableFieldPresence:
    """Verify hr_reliable and hr_note are always present in results."""

    def test_hr_reliable_field_exists_on_result(self):
        """StreamAnalysisResult always has hr_reliable field."""
        stream = make_normal_hr_stream()
        result = analyze_stream(
            stream_data=stream,
            channels_available=list(stream.keys()),
        )
        assert hasattr(result, "hr_reliable")
        assert isinstance(result.hr_reliable, bool)

    def test_hr_note_field_exists_on_result(self):
        """StreamAnalysisResult always has hr_note field."""
        stream = make_normal_hr_stream()
        result = analyze_stream(
            stream_data=stream,
            channels_available=list(stream.keys()),
        )
        assert hasattr(result, "hr_note")

    def test_to_dict_includes_hr_fields(self):
        """to_dict() serialization includes hr_reliable and hr_note."""
        stream = make_inverted_hr_stream()
        result = analyze_stream(
            stream_data=stream,
            channels_available=list(stream.keys()),
        )
        d = result.to_dict()
        assert "hr_reliable" in d
        assert "hr_note" in d
        assert d["hr_reliable"] is False
        assert d["hr_note"] is not None
