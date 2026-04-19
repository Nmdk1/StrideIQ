"""
Unit tests for services/sync/fit_run_parser.

Synthesizes minimal in-memory FIT files using fitparse-compatible structures
via the official Garmin FIT SDK encoder if available, otherwise falls back
to mocking fitparse.FitFile directly. The latter is the more reliable path
in CI (no SDK dep), so these tests exercise the projection logic with mock
messages.
"""

from unittest.mock import MagicMock, patch

import pytest

from services.sync.fit_run_parser import (
    _decode_feel,
    _double_cadence,
    _mm_to_cm,
    parse_run_fit,
)


# ---------------------------------------------------------------------------
# Coercion helpers (pure functions, no fitparse needed)
# ---------------------------------------------------------------------------


def test_double_cadence_converts_single_foot_to_total():
    # Garmin watch reports 85 spm per foot — should become 170 total.
    assert _double_cadence(85) == 170


def test_double_cadence_passes_through_total():
    # Already total cadence (>= 120) — leave alone.
    assert _double_cadence(170) == 170


def test_double_cadence_zero_returns_none():
    assert _double_cadence(0) is None
    assert _double_cadence(None) is None


def test_mm_to_cm_converts_and_rounds():
    # Vertical osc reported in mm by fitparse; we expose cm.
    assert _mm_to_cm(95) == 9.5
    assert _mm_to_cm(93.4567) == 9.35


def test_mm_to_cm_handles_none():
    assert _mm_to_cm(None) is None


def test_decode_feel_known_enum():
    assert _decode_feel(0) == "very_strong"
    assert _decode_feel(50) == "normal"
    assert _decode_feel(100) == "very_weak"


def test_decode_feel_unknown_returns_none():
    assert _decode_feel(13) is None


def test_decode_feel_string_passthrough():
    assert _decode_feel("Strong") == "strong"


# ---------------------------------------------------------------------------
# Top-level parser using mock fitparse
# ---------------------------------------------------------------------------


def _mock_message(values: dict) -> MagicMock:
    """Build a mock fitparse message that returns `values` from get_values()."""
    msg = MagicMock()
    msg.get_values.return_value = values
    return msg


def _mock_fit_file(session_values: dict | None, lap_values_list: list[dict]) -> MagicMock:
    """Build a mock FitFile that yields the given session/lap messages."""
    fit_file = MagicMock()

    def _get_messages(name):
        if name == "session":
            return [_mock_message(session_values)] if session_values is not None else []
        if name == "lap":
            return [_mock_message(v) for v in lap_values_list]
        return []

    fit_file.get_messages.side_effect = _get_messages
    return fit_file


def test_parse_run_fit_session_full_shape():
    """A realistic running session message projects to all the expected fields."""
    session = {
        "sport": "running",
        "sub_sport": "trail",
        "total_elapsed_time": 3600,
        "total_timer_time": 3540,        # moving_time
        "total_distance": 12057.5,
        "total_ascent": 167.0,
        "total_descent": 152.0,
        "avg_heart_rate": 158,
        "max_heart_rate": 184,
        "avg_running_cadence": 84,        # single-foot — should double
        "max_running_cadence": 95,
        "enhanced_avg_speed": 3.36,       # m/s
        "enhanced_max_speed": 4.8,
        "avg_power": 285,
        "max_power": 420,
        "normalized_power": 295,
        "avg_stride_length": 1.21,
        "avg_stance_time": 248.0,
        "avg_stance_time_balance": 49.8,
        "avg_vertical_oscillation": 93.0,  # mm → 9.3 cm
        "avg_vertical_ratio": 7.7,
        "total_calories": 720,
        "total_moderate_intensity_minutes": 12,
        "total_vigorous_intensity_minutes": 28,
        "avg_temperature": 18.0,
        "min_temperature": 16.0,
        "max_temperature": 21.0,
        "feel": 25,
        "perceived_effort": 7,
        "num_laps": 4,
        "total_strides": 4960,
    }
    fit_file = _mock_fit_file(session, [])

    with patch("fitparse.FitFile", return_value=fit_file):
        result = parse_run_fit(b"...irrelevant bytes...")

    s = result["session"]
    assert s["sport"] == "running"
    assert s["sub_sport"] == "trail"
    assert s["moving_time_s"] == 3540
    assert s["elapsed_time_s"] == 3600
    assert s["total_ascent_m"] == 167.0
    assert s["total_descent_m"] == 152.0
    assert s["avg_run_cadence_spm"] == 168       # 84 * 2
    assert s["max_run_cadence_spm"] == 190       # 95 * 2
    assert s["avg_speed_mps"] == 3.36
    assert s["avg_power_w"] == 285
    assert s["max_power_w"] == 420
    assert s["normalized_power_w"] == 295
    assert s["avg_stride_length_m"] == 1.21
    assert s["avg_ground_contact_ms"] == 248.0
    assert s["avg_ground_contact_balance_pct"] == 49.8
    assert s["avg_vertical_oscillation_cm"] == 9.3
    assert s["avg_vertical_ratio_pct"] == 7.7
    assert s["total_calories"] == 720
    assert s["moderate_intensity_minutes"] == 12
    assert s["vigorous_intensity_minutes"] == 28
    assert s["avg_temperature_c"] == 18.0
    assert s["max_temperature_c"] == 21.0
    assert s["min_temperature_c"] == 16.0
    assert s["garmin_feel"] == "strong"
    assert s["garmin_perceived_effort"] == 7
    assert s["num_laps"] == 4
    assert result["laps"] == []


def test_parse_run_fit_with_laps():
    """Multi-lap interval workout produces one lap entry per FIT lap message."""
    session = {"sport": "running", "total_timer_time": 1800, "total_distance": 5000}
    laps = [
        {
            "total_elapsed_time": 600, "total_timer_time": 600,
            "total_distance": 1609, "avg_heart_rate": 142, "max_heart_rate": 158,
            "avg_running_cadence": 78, "avg_power": 220, "max_power": 280,
            "intensity": "warmup", "lap_trigger": "manual",
        },
        {
            "total_elapsed_time": 240, "total_timer_time": 240,
            "total_distance": 1000, "avg_heart_rate": 174, "max_heart_rate": 184,
            "avg_running_cadence": 92, "avg_power": 320, "max_power": 360,
            "avg_stride_length": 1.32, "intensity": "active", "lap_trigger": "distance",
        },
        {
            "total_elapsed_time": 90, "total_timer_time": 90,
            "total_distance": 250, "avg_heart_rate": 138,
            "intensity": "recovery", "lap_trigger": "manual",
        },
    ]
    fit_file = _mock_fit_file(session, laps)

    with patch("fitparse.FitFile", return_value=fit_file):
        result = parse_run_fit(b"...")

    assert len(result["laps"]) == 3
    warmup, work, rest = result["laps"]
    assert warmup["lap_number"] == 1
    assert warmup["distance_m"] == 1609
    assert warmup["intensity"] == "warmup"
    assert warmup["avg_run_cadence_spm"] == 156

    assert work["lap_number"] == 2
    assert work["intensity"] == "active"
    assert work["avg_power_w"] == 320
    assert work["max_power_w"] == 360
    assert work["avg_stride_length_m"] == 1.32

    assert rest["lap_number"] == 3
    assert rest["intensity"] == "recovery"
    # Missing fields stay None (not zero, not "")
    assert rest["avg_power_w"] is None
    assert rest["avg_stride_length_m"] is None


def test_parse_run_fit_no_session_returns_empty_session():
    fit_file = _mock_fit_file(None, [])
    with patch("fitparse.FitFile", return_value=fit_file):
        result = parse_run_fit(b"")
    assert result == {"session": None, "laps": []}


def test_parse_run_fit_corrupt_file_returns_empty_safely():
    """A FIT parse exception should be swallowed and return empty data."""
    with patch("fitparse.FitFile", side_effect=Exception("bad bytes")):
        result = parse_run_fit(b"\x00\x00\x00")
    assert result == {"session": None, "laps": []}


def test_parse_run_fit_skips_nan_values():
    """NaN or inf in raw FIT shouldn't pollute downstream aggregates."""
    session = {
        "sport": "running",
        "total_timer_time": 1800,
        "avg_power": float("nan"),
        "avg_stride_length": float("inf"),
        "avg_heart_rate": 158,
    }
    fit_file = _mock_fit_file(session, [])
    with patch("fitparse.FitFile", return_value=fit_file):
        result = parse_run_fit(b"")
    s = result["session"]
    assert s["avg_power_w"] is None      # NaN dropped
    assert s["avg_stride_length_m"] is None  # inf dropped
    assert s["avg_hr"] == 158             # valid kept
