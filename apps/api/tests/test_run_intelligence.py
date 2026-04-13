"""
Unit tests for Run Intelligence Synthesis Service (LLM-powered)
"""

import pytest
from unittest.mock import MagicMock, patch, ANY
from datetime import datetime, date
from uuid import uuid4

from services.run_intelligence import (
    generate_run_intelligence,
    _fmt_pace_per_mile,
    _fmt_duration,
    _fmt_distance_mi,
    _workout_label,
    _build_headline,
    _build_highlights,
    _build_data_context,
    _get_pre_state,
    _is_interval_workout,
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
    a.is_race_candidate = overrides.get("is_race_candidate", False)
    a.start_time = overrides.get("start_time", datetime(2026, 4, 10, 7, 0))
    a.total_elevation_gain = overrides.get("total_elevation_gain", 50)
    a.pre_sleep_h = overrides.get("pre_sleep_h", 7.2)
    a.pre_sleep_score = overrides.get("pre_sleep_score", None)
    a.pre_resting_hr = overrides.get("pre_resting_hr", 52)
    a.pre_recovery_hrv = overrides.get("pre_recovery_hrv", 55)
    a.pre_overnight_hrv = overrides.get("pre_overnight_hrv", None)
    a.temperature_f = overrides.get("temperature_f", None)
    a.humidity_pct = overrides.get("humidity_pct", None)
    a.heat_adjustment_pct = overrides.get("heat_adjustment_pct", None)
    a.weather_condition = overrides.get("weather_condition", None)
    a.avg_cadence = overrides.get("avg_cadence", None)
    return a


class TestFormatHelpers:
    def test_fmt_pace_per_mile(self):
        result = _fmt_pace_per_mile(320)
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


class TestIsIntervalWorkout:
    def test_interval(self):
        a = _make_activity(workout_type="interval")
        assert _is_interval_workout(a) is True

    def test_track(self):
        a = _make_activity(workout_type="track")
        assert _is_interval_workout(a) is True

    def test_easy_run(self):
        a = _make_activity(workout_type="easy_run")
        assert _is_interval_workout(a) is False

    def test_none(self):
        a = _make_activity(workout_type=None)
        assert _is_interval_workout(a) is False


class TestGetPreState:
    def test_full_prestate(self):
        a = _make_activity(pre_sleep_h=7.2, pre_resting_hr=52, pre_recovery_hrv=55)
        state = _get_pre_state(a)
        assert state["sleep_hours"] == 7.2
        assert state["resting_hr"] == 52
        assert state["recovery_hrv"] == 55

    def test_partial_prestate(self):
        a = _make_activity(pre_sleep_h=6.5, pre_resting_hr=None, pre_recovery_hrv=None)
        state = _get_pre_state(a)
        assert state["sleep_hours"] == 6.5
        assert "resting_hr" not in state

    def test_no_prestate(self):
        a = _make_activity(pre_sleep_h=None, pre_resting_hr=None, pre_recovery_hrv=None)
        assert _get_pre_state(a) is None


class TestBuildHeadline:
    def test_normal_run(self):
        activity = _make_activity()
        h = _build_headline(activity, None)
        assert "mi" in h
        assert "easy run" in h

    def test_race_long(self):
        activity = _make_activity(
            workout_type="race", is_race_candidate=True,
            distance_m=21097, duration_s=5254,
        )
        h = _build_headline(activity, None)
        assert "race" in h

    def test_interval_headline_with_busted(self):
        activity = _make_activity(workout_type="interval")
        interval_data = {
            "reps": [{"distance_m": 400}],
            "clean_reps": 10,
            "total_reps": 12,
            "busted_reps": [3, 5],
            "clean_avg_pace_per_mile": "6:15/mi",
        }
        h = _build_headline(activity, interval_data)
        assert "10 of 12" in h
        assert "400m" in h

    def test_interval_headline_clean(self):
        activity = _make_activity(workout_type="interval")
        interval_data = {
            "reps": [{"distance_m": 800}],
            "clean_reps": 6,
            "total_reps": 6,
            "busted_reps": [],
            "clean_avg_pace_per_mile": "5:45/mi",
        }
        h = _build_headline(activity, interval_data)
        assert "6x800m" in h


class TestBuildHighlights:
    def test_basic_highlights(self):
        activity = _make_activity(avg_hr=142, total_elevation_gain=200)
        hl = _build_highlights(
            activity,
            {"cardiac_drift_pct": 2.5},
            {"decay_pct": 1.0},
            None,
        )
        labels = [h.label for h in hl]
        assert "Avg HR" in labels
        assert "Cardiac Drift" in labels
        assert "Pacing" in labels
        assert "Elevation" in labels

    def test_interval_highlights(self):
        activity = _make_activity(workout_type="interval")
        interval_data = {
            "max_spread_pct": 3.2,
            "clean_reps": 5,
            "total_reps": 6,
            "busted_reps": [3],
            "avg_hr_work": 172,
        }
        hl = _build_highlights(activity, None, None, None, interval_data)
        labels = [h.label for h in hl]
        assert "Rep Consistency" in labels
        assert "Reps" in labels
        assert "Avg HR (work)" in labels
        reps_hl = next(h for h in hl if h.label == "Reps")
        assert reps_hl.value == "5/6"


class TestBuildDataContext:
    @patch("services.run_intelligence._get_athlete_notes", return_value=None)
    @patch("services.run_intelligence._get_drift_history_avg", return_value=None)
    @patch("services.run_intelligence._get_efficiency_vs_peers", return_value=None)
    @patch("services.run_intelligence._get_stream_drift", return_value=None)
    @patch("services.run_intelligence._get_split_pacing", return_value=None)
    def test_basic_context(self, *mocks):
        a = _make_activity()
        db = MagicMock()
        ctx = _build_data_context(a, db)
        assert ctx["workout_type"] == "easy run"
        assert ctx["avg_hr"] == 140
        assert "distance_miles" in ctx
        assert "duration" in ctx
        assert "avg_pace_per_mile" in ctx

    @patch("services.run_intelligence._get_athlete_notes", return_value=None)
    @patch("services.run_intelligence._get_drift_history_avg", return_value=None)
    @patch("services.run_intelligence._get_efficiency_vs_peers", return_value=None)
    @patch("services.run_intelligence._get_stream_drift", return_value={"cardiac_drift_pct": 2.1})
    @patch("services.run_intelligence._get_split_pacing", return_value=None)
    def test_context_includes_drift(self, *mocks):
        a = _make_activity()
        db = MagicMock()
        ctx = _build_data_context(a, db)
        assert ctx["cardiac_drift"]["cardiac_drift_pct"] == 2.1

    @patch("services.run_intelligence._get_athlete_notes", return_value=None)
    @patch("services.run_intelligence._get_drift_history_avg", return_value=None)
    @patch("services.run_intelligence._get_efficiency_vs_peers", return_value=None)
    @patch("services.run_intelligence._get_stream_drift", return_value=None)
    @patch("services.run_intelligence._get_split_pacing", return_value=None)
    def test_context_includes_heat(self, *mocks):
        a = _make_activity(temperature_f=92, heat_adjustment_pct=4.5)
        db = MagicMock()
        ctx = _build_data_context(a, db)
        assert ctx["temperature_f"] == 92
        assert ctx["heat_adjustment_pct"] == 4.5

    @patch("services.run_intelligence._get_athlete_notes", return_value=None)
    @patch("services.run_intelligence._get_drift_history_avg", return_value=None)
    @patch("services.run_intelligence._get_efficiency_vs_peers", return_value=None)
    @patch("services.run_intelligence._get_stream_drift", return_value=None)
    @patch("services.run_intelligence._get_split_pacing", return_value=None)
    def test_context_pre_state(self, *mocks):
        a = _make_activity(pre_sleep_h=7.2, pre_resting_hr=52)
        db = MagicMock()
        ctx = _build_data_context(a, db)
        assert ctx["pre_run_state"]["sleep_hours"] == 7.2


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

    @patch("services.run_intelligence._call_intelligence_llm", return_value="Your easy run showed stable HR throughout with only +1.2% cardiac drift.")
    @patch("services.run_intelligence._get_athlete_notes", return_value=None)
    @patch("services.run_intelligence._get_drift_history_avg", return_value=None)
    @patch("services.run_intelligence._get_efficiency_vs_peers", return_value=None)
    @patch("services.run_intelligence._get_stream_drift", return_value={"cardiac_drift_pct": 1.2})
    @patch("services.run_intelligence._get_split_pacing", return_value=None)
    def test_returns_result_with_llm_body(self, *mocks):
        db = MagicMock()
        activity = _make_activity()
        db.query.return_value.filter.return_value.first.return_value = activity
        result = generate_run_intelligence(str(activity.id), str(activity.athlete_id), db)
        assert result is not None
        assert "easy run" in result.headline
        assert "cardiac drift" in result.body.lower()
        assert len(result.highlights) > 0

    @patch("services.run_intelligence._call_intelligence_llm", return_value=None)
    @patch("services.run_intelligence._get_athlete_notes", return_value=None)
    @patch("services.run_intelligence._get_drift_history_avg", return_value=None)
    @patch("services.run_intelligence._get_efficiency_vs_peers", return_value=None)
    @patch("services.run_intelligence._get_stream_drift", return_value={"cardiac_drift_pct": 1.2})
    @patch("services.run_intelligence._get_split_pacing", return_value=None)
    def test_returns_result_even_if_llm_returns_none(self, *mocks):
        """Highlights still show even when LLM fails."""
        db = MagicMock()
        activity = _make_activity()
        db.query.return_value.filter.return_value.first.return_value = activity
        result = generate_run_intelligence(str(activity.id), str(activity.athlete_id), db)
        assert result is not None
        assert result.body == ""
        assert len(result.highlights) > 0
