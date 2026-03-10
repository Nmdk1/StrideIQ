"""Tests for A3: Moment Narrator.

Covers:
- Validation (banned terms, sycophancy, causal language)
- Output count mismatch fail-closed
- Context window extraction
- Integration with analyze_stream (single call, cache skip)
"""
import json
import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass
from typing import Optional

from services.moment_narrator import (
    validate_moment_narrative,
    extract_moment_windows,
    generate_moment_narratives,
    _parse_narrative_array,
    CAUSAL_ALLOWED_TYPES,
)
from services.run_stream_analysis import (
    Moment,
    Segment,
    analyze_stream,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_moment(type_: str = "pace_surge", index: int = 100, time_s: int = 100, value: float = 5.0):
    return Moment(type=type_, index=index, time_s=time_s, value=value, context="test")


def _make_segments():
    return [
        Segment(type="warmup", start_index=0, end_index=200, start_time_s=0, end_time_s=200,
                duration_s=200, avg_pace_s_km=360.0, avg_hr=130.0, avg_cadence=168.0, avg_grade=0.5),
        Segment(type="work", start_index=200, end_index=400, start_time_s=200, end_time_s=400,
                duration_s=200, avg_pace_s_km=300.0, avg_hr=165.0, avg_cadence=178.0, avg_grade=1.0),
    ]


def _make_stream_data(n: int = 500):
    return {
        "time": list(range(n)),
        "velocity_smooth": [3.0 + 0.002 * i for i in range(n)],
        "heartrate": [120.0 + 0.1 * i for i in range(n)],
        "cadence": [84.0 + 0.01 * i for i in range(n)],  # half-cadence
        "grade_smooth": [0.5 * (i % 10 - 5) for i in range(n)],
    }


def _mock_gemini_response(narratives: list):
    """Create a mock Gemini client that returns the given narratives as JSON."""
    client = MagicMock()
    response = MagicMock()
    candidate = MagicMock()
    part = MagicMock()
    part.text = json.dumps(narratives)
    candidate.content.parts = [part]
    response.candidates = [candidate]
    response.usage_metadata = MagicMock()
    response.usage_metadata.prompt_token_count = 100
    response.usage_metadata.candidates_token_count = 50
    client.models.generate_content.return_value = response
    return client


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

class TestValidateMomentNarrative:

    def test_valid_narrative_passes(self):
        text = "Your pace dropped from 5:30 to 5:10 at 32:00 as you settled into the second half."
        assert validate_moment_narrative(text, "pace_surge") == text

    def test_empty_returns_none(self):
        assert validate_moment_narrative("", "pace_surge") is None
        assert validate_moment_narrative(None, "pace_surge") is None

    def test_too_short_returns_none(self):
        assert validate_moment_narrative("Hi.", "pace_surge") is None

    def test_banned_metric_tsb(self):
        assert validate_moment_narrative("Your TSB is looking good here.", "pace_surge") is None

    def test_banned_metric_vdot(self):
        assert validate_moment_narrative("This suggests a VDOT of 55.", "pace_surge") is None

    def test_banned_metric_ef(self):
        assert validate_moment_narrative("Your EF: 1.45 is excellent.", "pace_surge") is None

    def test_sycophantic_great_job(self):
        assert validate_moment_narrative("Great job holding pace through this segment.", "pace_surge") is None

    def test_sycophantic_amazing(self):
        assert validate_moment_narrative("This is an amazing negative split.", "pace_surge") is None

    def test_causal_blocked_for_pace_surge(self):
        text = "Your pace dropped because you were fatigued."
        assert validate_moment_narrative(text, "pace_surge") is None

    def test_causal_allowed_for_grade_adjusted_anomaly(self):
        text = "Your pace dropped because you hit a 4.7% grade — your effort was steady."
        result = validate_moment_narrative(text, "grade_adjusted_anomaly")
        assert result is not None

    def test_causal_allowed_for_recovery_hr_delay(self):
        text = "HR took longer to drop because you sustained a harder effort in that rep."
        result = validate_moment_narrative(text, "recovery_hr_delay")
        assert result is not None


# ---------------------------------------------------------------------------
# Parse tests
# ---------------------------------------------------------------------------

class TestParseNarrativeArray:

    def test_valid_json_array(self):
        raw = '["sentence one", "sentence two"]'
        assert _parse_narrative_array(raw, 2) == ["sentence one", "sentence two"]

    def test_count_mismatch_returns_none(self):
        raw = '["sentence one", "sentence two", "sentence three"]'
        assert _parse_narrative_array(raw, 2) is None

    def test_invalid_json_returns_none(self):
        assert _parse_narrative_array("not json at all", 2) is None

    def test_non_list_returns_none(self):
        assert _parse_narrative_array('{"key": "value"}', 1) is None

    def test_empty_string_returns_none(self):
        assert _parse_narrative_array("", 1) is None

    def test_markdown_fenced_json(self):
        raw = '```json\n["sentence one", "sentence two"]\n```'
        assert _parse_narrative_array(raw, 2) == ["sentence one", "sentence two"]


# ---------------------------------------------------------------------------
# Context window extraction tests
# ---------------------------------------------------------------------------

class TestExtractMomentWindows:

    def test_extracts_values_at_index(self):
        stream = _make_stream_data(200)
        moment = _make_moment(index=100)
        windows = extract_moment_windows([moment], stream)
        assert len(windows) == 1
        w = windows[0]
        assert w["hr_at"] is not None
        assert w["hr_before"] is not None
        assert w["pace_at_s_km"] is not None
        assert w["cadence_at"] is not None

    def test_cadence_normalized(self):
        """Cadence below 120 is doubled (half-cadence normalization)."""
        stream = _make_stream_data(200)
        moment = _make_moment(index=100)
        windows = extract_moment_windows([moment], stream)
        w = windows[0]
        # Raw cadence is ~85 (half-cadence), should be doubled to ~170
        assert w["cadence_at"] is not None
        assert w["cadence_at"] >= 160  # 84 * 2 ≈ 168

    def test_handles_empty_stream(self):
        windows = extract_moment_windows([_make_moment()], {})
        assert len(windows) == 1
        assert windows[0]["hr_at"] is None


# ---------------------------------------------------------------------------
# Integration: generate_moment_narratives
# ---------------------------------------------------------------------------

class TestGenerateMomentNarratives:

    def test_returns_narratives_on_success(self):
        moments = [_make_moment(), _make_moment(type_="cadence_surge", index=200, time_s=200)]
        client = _mock_gemini_response([
            "Your pace surged at 1:40 as you opened up.",
            "Cadence shifted from 168 to 174 spm at 3:20.",
        ])
        narratives, result = generate_moment_narratives(
            moments=moments,
            segments=_make_segments(),
            stream_data=_make_stream_data(),
            gemini_client=client,
        )
        assert len(narratives) == 2
        assert narratives[0] is not None
        assert narratives[1] is not None
        assert result.success is True

    def test_no_gemini_client_returns_all_none(self):
        moments = [_make_moment()]
        narratives, result = generate_moment_narratives(
            moments=moments,
            segments=_make_segments(),
            stream_data=_make_stream_data(),
            gemini_client=None,
        )
        assert all(n is None for n in narratives)
        assert result.error == "no_gemini_client"

    def test_empty_moments_returns_empty(self):
        narratives, result = generate_moment_narratives(
            moments=[],
            segments=_make_segments(),
            stream_data=_make_stream_data(),
        )
        assert narratives == []
        assert result.success is True

    def test_output_length_mismatch_fails_closed(self):
        """If LLM returns wrong number of narratives, ALL become None."""
        moments = [_make_moment(), _make_moment(type_="cadence_surge", index=200, time_s=200)]
        # Return 3 narratives for 2 moments
        client = _mock_gemini_response(["one", "two", "three"])
        narratives, result = generate_moment_narratives(
            moments=moments,
            segments=_make_segments(),
            stream_data=_make_stream_data(),
            gemini_client=client,
        )
        assert all(n is None for n in narratives)
        assert result.error == "parse_failed"

    def test_banned_terms_fail_closed_per_moment(self):
        """If one narrative has banned terms, only that one becomes None."""
        moments = [_make_moment(), _make_moment(type_="cadence_surge", index=200, time_s=200)]
        client = _mock_gemini_response([
            "Your pace surged at 1:40 as you opened up.",
            "Your VDOT improved to 55 here.",  # banned
        ])
        narratives, result = generate_moment_narratives(
            moments=moments,
            segments=_make_segments(),
            stream_data=_make_stream_data(),
            gemini_client=client,
        )
        assert narratives[0] is not None  # Valid — survives
        assert narratives[1] is None  # Banned — fails closed
        assert result.fallback_count == 1

    def test_llm_exception_returns_all_none(self):
        """If LLM call throws, all narratives are None."""
        client = MagicMock()
        client.models.generate_content.side_effect = RuntimeError("API down")
        narratives, result = generate_moment_narratives(
            moments=[_make_moment()],
            segments=_make_segments(),
            stream_data=_make_stream_data(),
            gemini_client=client,
        )
        assert all(n is None for n in narratives)
        assert "API down" in result.error


# ---------------------------------------------------------------------------
# Integration: analyze_stream calls narrator once per activity
# ---------------------------------------------------------------------------

class TestAnalyzeStreamNarratorIntegration:

    def test_analyze_stream_calls_narrator_once(self):
        """analyze_stream should call the narrator exactly once, regardless of moment count."""
        stream_data = _make_stream_data(500)
        stream_data["time"] = list(range(500))

        client = _mock_gemini_response([])

        with patch("services.run_stream_analysis.detect_moments") as mock_detect:
            # Return 3 moments
            mock_detect.return_value = [
                _make_moment(index=50, time_s=50),
                _make_moment(type_="cadence_surge", index=150, time_s=150),
                _make_moment(type_="pace_fade", index=300, time_s=300),
            ]
            # Mock narrator response for 3 moments
            client = _mock_gemini_response([
                "Pace surged at 0:50.",
                "Cadence shifted at 2:30.",
                "Pace faded at 5:00.",
            ])

            result = analyze_stream(
                stream_data=stream_data,
                channels_available=["time", "velocity_smooth", "heartrate", "cadence", "grade_smooth"],
                gemini_client=client,
            )

            # Narrator should have been called exactly once
            assert client.models.generate_content.call_count == 1

    def test_analyze_stream_without_gemini_skips_narrator(self):
        """Without a Gemini client, moments should have narrative=None."""
        stream_data = _make_stream_data(500)
        stream_data["time"] = list(range(500))

        with patch("services.run_stream_analysis.detect_moments") as mock_detect:
            mock_detect.return_value = [_make_moment(index=50, time_s=50)]

            result = analyze_stream(
                stream_data=stream_data,
                channels_available=["time", "velocity_smooth", "heartrate", "cadence", "grade_smooth"],
                gemini_client=None,
            )

            for m in result.moments:
                assert m.narrative is None
