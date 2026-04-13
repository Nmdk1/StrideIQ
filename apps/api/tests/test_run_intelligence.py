"""
Unit tests for Run Intelligence Synthesis Service
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from uuid import uuid4

from services.run_intelligence import (
    generate_run_intelligence,
    _fmt_pace_per_mile,
    _fmt_duration,
    _fmt_distance_mi,
    _workout_label,
    _pacing_sentence,
    _coupling_sentence,
    _efficiency_sentence,
    _prestate_sentence,
    _conditions_sentence,
    _build_headline,
    _build_highlights,
    IntelligenceHighlight,
)


def _make_activity(**overrides):
    a = MagicMock()
    a.id = overrides.get("id", uuid4())
    a.athlete_id = overrides.get("athlete_id", uuid4())
    a.name = overrides.get("name", "Morning Run")
    a.distance_m = overrides.get("distance_m", 10000.0)
    a.duration_s = overrides.get("duration_s", 3000.0)
    a.avg_hr = overrides.get("avg_hr", 140)
    a.max_hr = overrides.get("max_hr", 165)
    a.workout_type = overrides.get("workout_type", "easy_run")
    a.is_race = overrides.get("is_race", False)
    a.start_time = overrides.get("start_time", datetime(2026, 4, 10, 7, 0))
    a.total_elevation_gain = overrides.get("total_elevation_gain", 50)
    a.pre_sleep_h = overrides.get("pre_sleep_h", 7.2)
    a.pre_resting_hr = overrides.get("pre_resting_hr", 52)
    a.pre_recovery_hrv = overrides.get("pre_recovery_hrv", 55)
    a.pre_sleep_score = overrides.get("pre_sleep_score", None)
    a.pre_overnight_hrv = overrides.get("pre_overnight_hrv", None)
    a.temperature_f = overrides.get("temperature_f", None)
    a.humidity_pct = overrides.get("humidity_pct", None)
    a.heat_adjustment_pct = overrides.get("heat_adjustment_pct", None)
    a.weather_condition = overrides.get("weather_condition", None)
    return a


class TestFormatHelpers:
    def test_fmt_pace_per_mile(self):
        result = _fmt_pace_per_mile(320)  # 5:20/km ≈ 8:35/mi
        assert "/mi" in result
        parts = result.replace("/mi", "").split(":")
        assert len(parts) == 2

    def test_fmt_duration_with_hours(self):
        assert _fmt_duration(3661) == "1:01:01"

    def test_fmt_duration_no_hours(self):
        assert _fmt_duration(305) == "5:05"

    def test_fmt_distance_mi(self):
        assert _fmt_distance_mi(16093.4) == "10.0"

    def test_workout_label_known(self):
        assert _workout_label("easy_run") == "easy run"
        assert _workout_label("race") == "race"
        assert _workout_label("interval") == "interval session"

    def test_workout_label_unknown(self):
        assert _workout_label("hill_sprints") == "hill sprints"

    def test_workout_label_none(self):
        assert _workout_label(None) == "run"


class TestPacingSentence:
    def test_negative_split(self):
        s = _pacing_sentence({"decay_pct": -3.5, "first_half_pace": 300, "second_half_pace": 290, "splits_count": 10})
        assert "negative split" in s.lower()
        assert "3.5%" in s

    def test_even_pacing(self):
        s = _pacing_sentence({"decay_pct": 1.0, "first_half_pace": 300, "second_half_pace": 303, "splits_count": 10})
        assert "even" in s.lower()

    def test_moderate_fade(self):
        s = _pacing_sentence({"decay_pct": 6.0, "first_half_pace": 300, "second_half_pace": 318, "splits_count": 10})
        assert "fade" in s.lower() or "slower" in s.lower()

    def test_significant_fade(self):
        s = _pacing_sentence({"decay_pct": 12.0, "first_half_pace": 300, "second_half_pace": 336, "splits_count": 10})
        assert "significant" in s.lower() or "too fast" in s.lower()

    def test_none_input(self):
        assert _pacing_sentence(None) is None


class TestCouplingSentence:
    @patch("services.run_analysis_engine.CONTROLLED_STEADY_TYPES", {"easy_run", "recovery"})
    def test_well_coupled(self):
        activity = _make_activity(workout_type="easy_run")
        s = _coupling_sentence({"cardiac_pct": 1.2}, None, activity)
        assert "stable" in s.lower()
        assert "+1.2%" in s

    @patch("services.run_analysis_engine.CONTROLLED_STEADY_TYPES", {"easy_run", "recovery"})
    def test_with_history_improving(self):
        activity = _make_activity(workout_type="easy_run")
        s = _coupling_sentence(
            {"cardiac_pct": 2.0},
            {"avg_drift": 5.0, "count": 7},
            activity,
        )
        assert "tightening" in s.lower()
        assert "7" in s

    def test_non_steady_returns_none(self):
        activity = _make_activity(workout_type="interval")
        s = _coupling_sentence({"cardiac_pct": 2.0}, None, activity)
        assert s is None


class TestEfficiencySentence:
    @patch("services.run_analysis_engine.CONTROLLED_STEADY_TYPES", {"easy_run", "recovery"})
    def test_above_average(self):
        activity = _make_activity(workout_type="tempo")
        s = _efficiency_sentence({"diff_pct": 6.0, "sample_size": 5, "label": "tempo"}, activity)
        assert "6.0%" in s
        assert "tempo" in s

    @patch("services.run_analysis_engine.CONTROLLED_STEADY_TYPES", {"easy_run", "recovery"})
    def test_controlled_steady_suppressed(self):
        activity = _make_activity(workout_type="easy_run")
        s = _efficiency_sentence({"diff_pct": 6.0, "sample_size": 5, "label": "easy run"}, activity)
        assert s is None


class TestPrestateSentence:
    def test_full_prestate(self):
        activity = _make_activity(pre_sleep_h=7.2, pre_resting_hr=52, pre_recovery_hrv=55)
        s = _prestate_sentence(activity)
        assert "7.2h sleep" in s
        assert "resting HR 52" in s
        assert "HRV 55" in s

    def test_partial_prestate(self):
        activity = _make_activity(pre_sleep_h=6.5, pre_resting_hr=None, pre_recovery_hrv=None)
        s = _prestate_sentence(activity)
        assert "6.5h sleep" in s
        assert "resting HR" not in s

    def test_no_prestate(self):
        activity = _make_activity(pre_sleep_h=None, pre_resting_hr=None, pre_recovery_hrv=None)
        assert _prestate_sentence(activity) is None


class TestConditionsSentence:
    def test_heat(self):
        activity = _make_activity(heat_adjustment_pct=5.0, temperature_f=88)
        s = _conditions_sentence(activity)
        assert "88°F" in s
        assert "5%" in s

    def test_elevation(self):
        activity = _make_activity(total_elevation_gain=200, heat_adjustment_pct=None)
        s = _conditions_sentence(activity)
        assert "ft" in s

    def test_nothing(self):
        activity = _make_activity(
            total_elevation_gain=30,
            heat_adjustment_pct=None,
            temperature_f=None,
        )
        assert _conditions_sentence(activity) is None


class TestBuildHeadline:
    def test_normal_run(self):
        activity = _make_activity()
        h = _build_headline("6.2", "8:42/mi", "52:30", "easy run", 6.2, activity)
        assert "6.2 mi" in h
        assert "8:42/mi" in h
        assert "easy run" in h

    def test_race_long(self):
        activity = _make_activity(workout_type="race", is_race=True)
        h = _build_headline("13.1", "6:39/mi", "1:27:34", "race", 13.1, activity)
        assert "13.1 mi in 1:27:34" in h


class TestBuildHighlights:
    def test_basic_highlights(self):
        activity = _make_activity(avg_hr=142, total_elevation_gain=200)
        hl = _build_highlights(
            activity,
            {"cardiac_pct": 2.5},
            {"decay_pct": 1.0},
            None,
        )
        labels = [h.label for h in hl]
        assert "Avg HR" in labels
        assert "Cardiac Drift" in labels
        assert "Pacing" in labels
        assert "Elevation" in labels


class TestGenerateRunIntelligence:
    def test_returns_none_for_missing_activity(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        result = generate_run_intelligence("fake-id", "fake-athlete", db)
        assert result is None

    def test_returns_none_for_no_distance(self):
        db = MagicMock()
        activity = _make_activity(distance_m=None)
        db.query.return_value.filter.return_value.first.return_value = activity
        result = generate_run_intelligence("id", "ath", db)
        assert result is None
