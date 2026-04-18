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
    _workout_name_suggests_intervals,
    _label_cooldown,
    STRUCTURED_SHAPE_CLASSIFICATIONS,
    _derive_reps_from_unmarked_splits,
    _get_interval_analysis,
    INTERVAL_WORKOUT_TYPES,
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
    a.dew_point_f = overrides.get("dew_point_f", None)
    a.heat_adjustment_pct = overrides.get("heat_adjustment_pct", None)
    a.weather_condition = overrides.get("weather_condition", None)
    a.avg_cadence = overrides.get("avg_cadence", None)
    a.run_shape = overrides.get("run_shape", None)
    return a


def _shape(classification):
    """Build a minimal run_shape JSONB dict with the given classification."""
    return {"summary": {"workout_classification": classification}}


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
        # heat_adjustment_pct is stored as a fraction (0.045 == 4.5% slowdown).
        # The LLM context exposes it as a percent for readability.
        a = _make_activity(temperature_f=92, heat_adjustment_pct=0.045)
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

    # ---- Heat / dew-point context (regression for the founder's complaint
    # that the LLM was looking only at temperature and ignoring dew point,
    # which is the actual heat-stress signal for runners) ----

    @patch("services.run_intelligence._get_athlete_notes", return_value=None)
    @patch("services.run_intelligence._get_drift_history_avg", return_value=None)
    @patch("services.run_intelligence._get_efficiency_vs_peers", return_value=None)
    @patch("services.run_intelligence._get_stream_drift", return_value=None)
    @patch("services.run_intelligence._get_split_pacing", return_value=None)
    def test_context_includes_dew_point_when_present(self, *mocks):
        # Today's actual values for activity a5799370-7c54-4a72-909a-9e492398fb30:
        # temp 83.3 F, humidity 45%, dew point 59.7 F, heat_adjustment_pct 0.0304.
        a = _make_activity(
            temperature_f=83.3, humidity_pct=45,
            dew_point_f=59.7, heat_adjustment_pct=0.0304,
        )
        db = MagicMock()
        ctx = _build_data_context(a, db)
        assert ctx["temperature_f"] == 83
        assert ctx["humidity_pct"] == 45
        assert ctx["dew_point_f"] == 59.7
        # Combined value (input to heat-adjustment model) must be in context
        # so the LLM can map it onto the validated tier table.
        assert ctx["temp_plus_dew_combined"] == 143.0
        # heat_adjustment_pct stored as fraction; surfaced as percent.
        assert ctx["heat_adjustment_pct"] == 3.0

    @patch("services.run_intelligence._get_athlete_notes", return_value=None)
    @patch("services.run_intelligence._get_drift_history_avg", return_value=None)
    @patch("services.run_intelligence._get_efficiency_vs_peers", return_value=None)
    @patch("services.run_intelligence._get_stream_drift", return_value=None)
    @patch("services.run_intelligence._get_split_pacing", return_value=None)
    def test_heat_adjustment_unit_bug_regression(self, *mocks):
        # Specific regression: heat_adjustment_pct is stored as a decimal
        # fraction by services.heat_adjustment.compute_activity_heat_fields
        # (e.g. 0.0304 == 3.04% slowdown).  The previous code checked
        # `if > 2`, suppressing every realistic heat condition.  The fix
        # lowers the threshold to 0.01 (1%) and converts to percent.
        a = _make_activity(
            temperature_f=83, dew_point_f=60, heat_adjustment_pct=0.0304,
        )
        db = MagicMock()
        ctx = _build_data_context(a, db)
        # Old code would have omitted heat_adjustment_pct entirely (0.0304 < 2).
        assert "heat_adjustment_pct" in ctx
        assert ctx["heat_adjustment_pct"] == 3.0

    @patch("services.run_intelligence._get_athlete_notes", return_value=None)
    @patch("services.run_intelligence._get_drift_history_avg", return_value=None)
    @patch("services.run_intelligence._get_efficiency_vs_peers", return_value=None)
    @patch("services.run_intelligence._get_stream_drift", return_value=None)
    @patch("services.run_intelligence._get_split_pacing", return_value=None)
    def test_heat_adjustment_below_threshold_is_suppressed(self, *mocks):
        # A 0.5% heat adjustment is noise -- don't surface it.  Suppression
        # over noise (founder rule).
        a = _make_activity(
            temperature_f=70, dew_point_f=50, heat_adjustment_pct=0.005,
        )
        db = MagicMock()
        ctx = _build_data_context(a, db)
        assert "heat_adjustment_pct" not in ctx
        # But dew point itself is still useful context whenever present.
        assert ctx["dew_point_f"] == 50.0

    @patch("services.run_intelligence._get_athlete_notes", return_value=None)
    @patch("services.run_intelligence._get_drift_history_avg", return_value=None)
    @patch("services.run_intelligence._get_efficiency_vs_peers", return_value=None)
    @patch("services.run_intelligence._get_stream_drift", return_value=None)
    @patch("services.run_intelligence._get_split_pacing", return_value=None)
    def test_temp_plus_dew_combined_only_when_both_present(self, *mocks):
        a = _make_activity(temperature_f=70, dew_point_f=None)
        db = MagicMock()
        ctx = _build_data_context(a, db)
        assert "temp_plus_dew_combined" not in ctx
        assert "dew_point_f" not in ctx


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


class TestIntervalWorkoutTypeCoverage:
    """The interval-workout-type set must include every workout type that is
    structured as discrete reps in the canonical WORKOUT_TYPE_OPTIONS list,
    not just the legacy {interval, intervals, track, track_workout}.

    This is the regression that broke the activity-page intelligence on
    cruise_intervals runs (the founder's threshold workout was treated as a
    continuous run because cruise_intervals was missing from the set).
    """

    def test_cruise_intervals_is_recognized(self):
        a = _make_activity(workout_type="cruise_intervals")
        assert _is_interval_workout(a) is True

    def test_tempo_intervals_is_recognized(self):
        a = _make_activity(workout_type="tempo_intervals")
        assert _is_interval_workout(a) is True

    def test_vo2max_intervals_is_recognized(self):
        a = _make_activity(workout_type="vo2max_intervals")
        assert _is_interval_workout(a) is True

    def test_hill_repetitions_is_recognized(self):
        a = _make_activity(workout_type="hill_repetitions")
        assert _is_interval_workout(a) is True

    def test_track_workout_is_recognized(self):
        a = _make_activity(workout_type="track_workout")
        assert _is_interval_workout(a) is True

    def test_easy_run_is_not_an_interval(self):
        a = _make_activity(workout_type="easy_run")
        assert _is_interval_workout(a) is False

    def test_long_run_is_not_an_interval(self):
        a = _make_activity(workout_type="long_run")
        assert _is_interval_workout(a) is False

    def test_tempo_run_is_not_an_interval_workout(self):
        # tempo_run is a continuous tempo, not a rep workout.  This is the
        # boundary case -- "tempo" without "intervals" stays continuous.
        a = _make_activity(workout_type="tempo_run")
        assert _is_interval_workout(a) is False


def _make_split(distance_m, elapsed_s, hr=None, lap_type=None, split_number=1):
    """Build a MagicMock split that quacks like models.ActivitySplit."""
    s = MagicMock()
    s.split_number = split_number
    s.distance = distance_m
    s.elapsed_time = elapsed_s
    s.average_heartrate = hr
    s.lap_type = lap_type
    return s


# Real split data for activity a5799370-7c54-4a72-909a-9e492398fb30
# (founder's "Lauderdale County - 4 x 10 minutes at T" run, 2026-04-16).
# workout_type=cruise_intervals, every split has lap_type=NULL.
# The actual workout was 3 reps of ~10 min at threshold pace, but the watch
# auto-lapped at every 1 mile, so each rep was cut into TWO consecutive
# fast-pace splits.  This is the run that the bug originally broke on.
LAUDERDALE_2026_04_16_SPLITS = [
    # split_number, distance_m, elapsed_s, avg_hr   -- role
    (1,  1609.34, 532, 118),  # warmup mile
    (2,  1609.34, 479, 131),  # warmup mile
    (3,   604.90, 635, 136),  # warmup tail / pause
    (4,  1609.34, 379, 128),  # rep 1 (auto-lap mid-rep) - 6:19/mi
    (5,   932.23, 220, 160),  # rep 1 continuation       - 6:20/mi
    (6,   214.30, 179, 132),  # recovery jog
    (7,  1609.34, 378, 155),  # rep 2 (auto-lap mid-rep) - 6:18/mi
    (8,   928.83, 221, 169),  # rep 2 continuation       - 6:23/mi
    (9,   191.41, 303, 142),  # recovery jog (very slow)
    (10, 1609.34, 382, 161),  # rep 3 (auto-lap mid-rep) - 6:22/mi
    (11,  910.65, 218, 170),  # rep 3 continuation       - 6:25/mi
    (12,  189.44, 151, 148),  # cooldown
]


def _lauderdale_splits():
    return [
        _make_split(distance_m=d, elapsed_s=e, hr=h, lap_type=None, split_number=n)
        for (n, d, e, h) in LAUDERDALE_2026_04_16_SPLITS
    ]


class TestDeriveRepsFromUnmarkedSplits:
    """Pace-pattern fallback for the common Garmin case where the watch
    didn't tag splits with lap_type='work'.  Every assertion below is keyed
    to the founder's actual 2026-04-16 cruise-intervals run."""

    def test_lauderdale_reconstructs_three_reps(self):
        reps = _derive_reps_from_unmarked_splits(_lauderdale_splits())
        assert reps is not None
        assert len(reps) == 3, (
            f"expected 3 reps from the Lauderdale fixture, got {len(reps)}: {reps}"
        )

    def test_lauderdale_each_rep_is_about_one_and_a_half_miles(self):
        reps = _derive_reps_from_unmarked_splits(_lauderdale_splits())
        for r in reps:
            mi = r["distance_m"] / 1609.34
            assert 1.4 <= mi <= 1.7, f"rep {r['rep']} was {mi:.2f}mi: {r}"

    def test_lauderdale_each_rep_pace_is_threshold(self):
        # All three reps were at ~6:20/mi, which is ~236 s/km.
        reps = _derive_reps_from_unmarked_splits(_lauderdale_splits())
        for r in reps:
            assert 230 <= r["pace_s_km"] <= 245, (
                f"rep {r['rep']} pace was {r['pace_s_km']} s/km, "
                f"expected ~236 s/km (6:20/mi): {r}"
            )

    def test_lauderdale_rep_consistency_is_tight(self):
        reps = _derive_reps_from_unmarked_splits(_lauderdale_splits())
        paces = [r["pace_s_km"] for r in reps]
        avg = sum(paces) / len(paces)
        max_spread_pct = max(abs((p - avg) / avg * 100) for p in paces)
        assert max_spread_pct < 3.0, (
            f"reps were {paces}, spread={max_spread_pct:.2f}% -- "
            "should be <3% for these threshold reps"
        )

    def test_lauderdale_each_rep_has_hr(self):
        reps = _derive_reps_from_unmarked_splits(_lauderdale_splits())
        for r in reps:
            assert r["avg_hr"] is not None, f"rep {r['rep']} missing HR"
            assert 120 <= r["avg_hr"] <= 200

    def test_lauderdale_via_full_interval_analysis_returns_three_reps(self):
        # End-to-end: feed the full split list to _get_interval_analysis,
        # which should fall through the lap_type='work' branch and pick up
        # the pace-derived path.
        activity = _make_activity(workout_type="cruise_intervals")
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
            _lauderdale_splits()
        )
        # _get_interval_history makes its own queries; stub it to None so we
        # don't try to compare against an empty mock history.
        with patch(
            "services.run_intelligence._get_interval_history", return_value=None
        ):
            result = _get_interval_analysis(activity, db)
        assert result is not None
        assert result["total_reps"] == 3
        assert result["clean_reps"] == 3
        assert result["busted_reps"] == []
        assert result["derived_from_pace"] is True
        # Average pace should land at ~6:20/mi.
        assert 230 <= result["clean_avg_pace_s_km"] <= 245

    def test_easy_run_pattern_returns_no_reps(self):
        # 8 splits all at ~5:30/km easy-run pace.  No fast cluster, so the
        # gap-finder should suppress and return None rather than fabricate.
        easy_splits = [
            _make_split(distance_m=1000, elapsed_s=330 + (i % 3) * 5, hr=140, split_number=i + 1)
            for i in range(8)
        ]
        assert _derive_reps_from_unmarked_splits(easy_splits) is None

    def test_too_few_splits_returns_none(self):
        splits = [
            _make_split(distance_m=1000, elapsed_s=240, hr=170, split_number=1),
            _make_split(distance_m=1000, elapsed_s=242, hr=171, split_number=2),
        ]
        assert _derive_reps_from_unmarked_splits(splits) is None

    def test_lap_type_work_path_still_wins_when_present(self):
        # When the watch DID tag work splits (structured workout file), the
        # legacy path must take precedence and produce non-derived output.
        splits = [
            _make_split(distance_m=400, elapsed_s=78, hr=170, lap_type="work", split_number=1),
            _make_split(distance_m=400, elapsed_s=79, hr=171, lap_type="work", split_number=2),
            _make_split(distance_m=400, elapsed_s=80, hr=172, lap_type="work", split_number=3),
            _make_split(distance_m=200, elapsed_s=80, hr=130, lap_type="rest", split_number=4),
        ]
        activity = _make_activity(workout_type="track_workout")
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = splits
        with patch(
            "services.run_intelligence._get_interval_history", return_value=None
        ):
            result = _get_interval_analysis(activity, db)
        assert result is not None
        assert result["total_reps"] == 3
        assert result["derived_from_pace"] is False


# ─────────────────────────────────────────────────────────────────────────────
# Multi-signal interval gate (regression: founder's 2026-04-18 run)
#
# The activity that triggered this work:
#   • workout_type = NULL on Activity row (Garmin never tagged it)
#   • activity.name = "Meridian - 2 x 2 x mile"
#   • run_shape.summary.workout_classification = "anomaly"
#   • splits show clean 4 x 1mi @ ~6:00-6:05/mi with full standing recoveries
#
# Old gate (workout_type only) returned False -> fell through to the
# continuous-run branch -> Kimi wrote a "you faded late" narrative for what
# was actually a textbook interval session with a planned cooldown.
#
# The new gate must accept ANY of these signals to keep the LLM from being
# fed pacing decay context for structured workouts.
# ─────────────────────────────────────────────────────────────────────────────


class TestWorkoutNameSuggestsIntervals:
    """Pure-string parser. No DB, no model."""

    @pytest.mark.parametrize(
        "name",
        [
            # The exact name on the founder's run that broke this:
            "Meridian - 2 x 2 x mile",
            # Common Garmin / TrainingPeaks naming patterns:
            "4 x 1 mile",
            "4x1mi @ T",
            "8 x 400m",
            "6x800",
            "10 x 200m",
            "3 x 1k",
            "5x1km repeats",
            "Mile Repeats",
            "400 repeats",
            "Track intervals",
            "Threshold intervals",
            "Cruise intervals",
            "Fartlek 8x1min",
            "Hill repeats",
            "Hill repeats x10",
        ],
    )
    def test_recognized_patterns(self, name):
        assert _workout_name_suggests_intervals(name) is True, (
            f"name {name!r} should be flagged as intervals"
        )

    @pytest.mark.parametrize(
        "name",
        [
            "Morning Run",
            "Easy 6 miler",
            "Long run",
            "Sunday long",
            "Recovery jog",
            "Marathon pace 8mi",
            "Road race",
            "",
            None,
        ],
    )
    def test_non_interval_names_are_not_flagged(self, name):
        assert _workout_name_suggests_intervals(name) is False, (
            f"name {name!r} should NOT be flagged as intervals"
        )


class TestStructuredShapeClassifications:
    """The set of run_shape.workout_classification values that mean
    'this run had structured work, treat it as intervals downstream'."""

    @pytest.mark.parametrize(
        "cls",
        [
            "anomaly",  # the founder's case
            "intervals",
            "track_intervals",
            "threshold_intervals",
            "tempo",
            "over_under",
            "hill_repeats",
            "progression",
            "fartlek",
        ],
    )
    def test_structured_classifications_are_in_set(self, cls):
        assert cls in STRUCTURED_SHAPE_CLASSIFICATIONS

    @pytest.mark.parametrize(
        "cls",
        ["easy_run", "long_run", "medium_long_run", "gray_zone_run", "strides"],
    )
    def test_easy_classifications_are_NOT_in_set(self, cls):
        assert cls not in STRUCTURED_SHAPE_CLASSIFICATIONS


class TestIsIntervalWorkoutMultiSignal:
    """The expanded gate: any of (workout_type, run_shape, name) can flip it."""

    def test_workout_type_alone_still_works(self):
        a = _make_activity(workout_type="cruise_intervals", name=None, run_shape=None)
        assert _is_interval_workout(a) is True

    def test_run_shape_anomaly_flips_gate_when_workout_type_is_none(self):
        # The exact founder case.
        a = _make_activity(
            workout_type=None, name=None, run_shape=_shape("anomaly")
        )
        assert _is_interval_workout(a) is True

    def test_run_shape_threshold_intervals_flips_gate(self):
        a = _make_activity(
            workout_type=None, name=None, run_shape=_shape("threshold_intervals")
        )
        assert _is_interval_workout(a) is True

    def test_run_shape_easy_run_does_NOT_flip_gate(self):
        a = _make_activity(
            workout_type=None, name="Morning Run", run_shape=_shape("easy_run")
        )
        assert _is_interval_workout(a) is False

    def test_workout_name_flips_gate_when_other_signals_missing(self):
        # The other half of the founder case: even without run_shape, the
        # name "2 x 2 x mile" should be enough.
        a = _make_activity(
            workout_type=None,
            name="Meridian - 2 x 2 x mile",
            run_shape=None,
        )
        assert _is_interval_workout(a) is True

    def test_easy_run_with_easy_shape_and_easy_name_stays_continuous(self):
        a = _make_activity(
            workout_type="easy_run",
            name="Morning easy 6",
            run_shape=_shape("easy_run"),
        )
        assert _is_interval_workout(a) is False

    def test_long_run_with_no_signals_stays_continuous(self):
        a = _make_activity(
            workout_type="long_run", name="Sunday long", run_shape=_shape("long_run")
        )
        assert _is_interval_workout(a) is False


# ─────────────────────────────────────────────────────────────────────────────
# Cooldown labeling (rule agreed with founder):
#   A trailing split is cooldown ONLY IF all four hold:
#     1. Position: comes after the last detected work rep
#     2. Pace: slower than the avg work-rep pace
#     3. HR drop: avg HR >= 12 bpm below avg work-rep HR
#     4. Substantial: distance >= 0.4 mi OR duration >= 3 min
#
#  HR drop is the load-bearing signal. The founder's threshold workout-with-
#  floats case proved that a fixed 30% pace gap is too rigid (cruise-interval
#  floats look identical pace-wise to a true cooldown), but HR responds only
#  when an athlete genuinely eases off.
# ─────────────────────────────────────────────────────────────────────────────


def _split_obj(distance_m, elapsed_s, hr=None, lap_type=None, split_number=1):
    return _make_split(
        distance_m=distance_m, elapsed_s=elapsed_s, hr=hr,
        lap_type=lap_type, split_number=split_number,
    )


def _meridian_2026_04_18_splits():
    """Real splits for the founder's 2026-04-18 run that triggered this work.

    Workout was 4 x 1mi @ ~6:00-6:05 with a 1mi cooldown at 9:10/HR 137
    after work HR averaged 151. Split 18 (the cooldown mile) is the one
    we must label correctly.
    """
    return [
        # warmup 1-3
        _split_obj(1593, 506, hr=120, split_number=1),
        _split_obj(1593, 475, hr=133, split_number=2),
        _split_obj(1593, 459, hr=140, split_number=3),
        # standing rest
        _split_obj(26, 317, hr=None, split_number=4),
        # rep 1
        _split_obj(1593, 362, hr=144, split_number=5),
        _split_obj(6, 3, hr=None, split_number=6),
        # recovery jog
        _split_obj(161, 179, hr=131, split_number=7),
        # rep 2
        _split_obj(1593, 362, hr=143, split_number=8),
        _split_obj(8, 3, hr=None, split_number=9),
        # recovery jog
        _split_obj(145, 179, hr=139, split_number=10),
        # set break
        _split_obj(274, 475, hr=111, split_number=11),
        # rep 3
        _split_obj(1593, 356, hr=156, split_number=12),
        _split_obj(10, 3, hr=None, split_number=13),
        # recovery jog
        _split_obj(177, 237, hr=138, split_number=14),
        # rep 4
        _split_obj(1593, 361, hr=159, split_number=15),
        _split_obj(5, 2, hr=None, split_number=16),
        # recovery jog
        _split_obj(161, 374, hr=132, split_number=17),
        # cooldown mile (must be labeled cooldown)
        _split_obj(1593, 547, hr=137, split_number=18),
        # tail debris
        _split_obj(20, 30, hr=None, split_number=19),
        _split_obj(8, 12, hr=None, split_number=20),
    ]


class TestLabelCooldown:
    def _reps_meridian(self):
        # Just enough for _label_cooldown to know what "work" looked like.
        return [
            {"rep": 1, "split_number": 5,  "pace_s_km": 225, "avg_hr": 144},
            {"rep": 2, "split_number": 8,  "pace_s_km": 225, "avg_hr": 143},
            {"rep": 3, "split_number": 12, "pace_s_km": 222, "avg_hr": 156},
            {"rep": 4, "split_number": 15, "pace_s_km": 224, "avg_hr": 159},
        ]

    def test_meridian_cooldown_mile_is_labeled(self):
        # Real founder run -- this is the regression that started this work.
        cd = _label_cooldown(self._reps_meridian(), _meridian_2026_04_18_splits())
        assert cd is not None, "split 18 (9:10/mi at HR 137) must be labeled cooldown"
        assert cd["split_number"] == 18
        assert cd["distance_m"] == 1593
        # Pace and HR should be surfaced for the LLM context.
        assert cd["avg_hr"] == 137
        assert "pace_per_mile" in cd

    def test_returns_none_when_no_trailing_split_after_last_rep(self):
        # Last rep is split 5 and there's nothing after it.
        reps = [{"rep": 1, "split_number": 5, "pace_s_km": 225, "avg_hr": 150}]
        splits = [_split_obj(1593, 362, hr=150, split_number=5)]
        assert _label_cooldown(reps, splits) is None

    def test_busted_final_rep_is_NOT_labeled_cooldown(self):
        # Final "trailing" split is slower-paced but HR is still elevated --
        # athlete was cooked, not cooling down. Must not get a cooldown pass.
        reps = [
            {"rep": 1, "split_number": 1, "pace_s_km": 225, "avg_hr": 155},
            {"rep": 2, "split_number": 2, "pace_s_km": 225, "avg_hr": 156},
            {"rep": 3, "split_number": 3, "pace_s_km": 225, "avg_hr": 158},
        ]
        splits = [
            _split_obj(1593, 362, hr=155, split_number=1),
            _split_obj(1593, 362, hr=156, split_number=2),
            _split_obj(1593, 362, hr=158, split_number=3),
            # "Final rep" but blew up: slower, HR went UP not down.
            _split_obj(1593, 405, hr=162, split_number=4),
        ]
        assert _label_cooldown(reps, splits) is None

    def test_cruise_intervals_with_real_cooldown(self):
        # The cruise-intervals-with-floats case the founder explicitly raised:
        # work 6:30 @ 165, floats between reps 7:30 @ 155 (excluded by
        # position), final cooldown 7:45 @ 135 (must be labeled).
        reps = [
            {"rep": 1, "split_number": 2, "pace_s_km": 242, "avg_hr": 165},
            {"rep": 2, "split_number": 4, "pace_s_km": 242, "avg_hr": 165},
            {"rep": 3, "split_number": 6, "pace_s_km": 242, "avg_hr": 165},
        ]
        splits = [
            _split_obj(1609, 390, hr=140, split_number=1),  # warmup
            _split_obj(1609, 390, hr=165, split_number=2),  # rep 1
            _split_obj(800,  220, hr=155, split_number=3),  # float
            _split_obj(1609, 390, hr=165, split_number=4),  # rep 2
            _split_obj(800,  220, hr=155, split_number=5),  # float
            _split_obj(1609, 390, hr=165, split_number=6),  # rep 3
            _split_obj(1609, 465, hr=135, split_number=7),  # cooldown
        ]
        cd = _label_cooldown(reps, splits)
        assert cd is not None and cd["split_number"] == 7

    def test_short_post_rep_jog_is_NOT_cooldown(self):
        # Trailing split is only 200m -- below the 0.4mi / 3min threshold.
        reps = [
            {"rep": 1, "split_number": 1, "pace_s_km": 225, "avg_hr": 160},
        ]
        splits = [
            _split_obj(1609, 362, hr=160, split_number=1),
            _split_obj(200,  90,  hr=130, split_number=2),  # too short
        ]
        assert _label_cooldown(reps, splits) is None

    def test_hr_missing_means_no_cooldown_label(self):
        reps = [
            {"rep": 1, "split_number": 1, "pace_s_km": 225, "avg_hr": 160},
        ]
        splits = [
            _split_obj(1609, 362, hr=160, split_number=1),
            _split_obj(1609, 600, hr=None, split_number=2),  # no HR
        ]
        assert _label_cooldown(reps, splits) is None


# ─────────────────────────────────────────────────────────────────────────────
# Data context surfaces workout name + shape classification to the LLM.
# Even when the gate misfires, the LLM should at least see the truth in the
# raw data so it doesn't write a confident wrong story.
# ─────────────────────────────────────────────────────────────────────────────


class TestBuildDataContextSurfacesWorkoutSignals:
    @patch("services.run_intelligence._get_athlete_notes", return_value=None)
    @patch("services.run_intelligence._get_drift_history_avg", return_value=None)
    @patch("services.run_intelligence._get_efficiency_vs_peers", return_value=None)
    @patch("services.run_intelligence._get_stream_drift", return_value=None)
    @patch("services.run_intelligence._get_split_pacing", return_value=None)
    @patch("services.run_intelligence._get_interval_analysis", return_value=None)
    def test_workout_name_surfaced_when_set(self, *mocks):
        a = _make_activity(name="Meridian - 2 x 2 x mile")
        ctx = _build_data_context(a, MagicMock())
        assert ctx["workout_name"] == "Meridian - 2 x 2 x mile"

    @patch("services.run_intelligence._get_athlete_notes", return_value=None)
    @patch("services.run_intelligence._get_drift_history_avg", return_value=None)
    @patch("services.run_intelligence._get_efficiency_vs_peers", return_value=None)
    @patch("services.run_intelligence._get_stream_drift", return_value=None)
    @patch("services.run_intelligence._get_split_pacing", return_value=None)
    @patch("services.run_intelligence._get_interval_analysis", return_value=None)
    def test_shape_classification_surfaced_when_present(self, *mocks):
        a = _make_activity(run_shape=_shape("anomaly"))
        ctx = _build_data_context(a, MagicMock())
        assert ctx["shape_classification"] == "anomaly"

    @patch("services.run_intelligence._get_athlete_notes", return_value=None)
    @patch("services.run_intelligence._get_drift_history_avg", return_value=None)
    @patch("services.run_intelligence._get_efficiency_vs_peers", return_value=None)
    @patch("services.run_intelligence._get_stream_drift", return_value=None)
    @patch("services.run_intelligence._get_split_pacing", return_value=None)
    @patch("services.run_intelligence._get_interval_analysis", return_value=None)
    def test_omitted_when_unset(self, *mocks):
        a = _make_activity(name=None, run_shape=None)
        ctx = _build_data_context(a, MagicMock())
        assert "workout_name" not in ctx
        assert "shape_classification" not in ctx

    @patch("services.run_intelligence._get_athlete_notes", return_value=None)
    @patch("services.run_intelligence._get_drift_history_avg", return_value=None)
    @patch("services.run_intelligence._get_efficiency_vs_peers", return_value=None)
    @patch("services.run_intelligence._get_stream_drift", return_value=None)
    @patch("services.run_intelligence._get_split_pacing", return_value=None)
    def test_intervals_branch_runs_for_anomaly_shape(self, *mocks):
        """End-to-end: shape=anomaly + meridian splits => interval analysis
        runs and produces reps + cooldown, NOT split_pacing decay."""
        a = _make_activity(
            workout_type=None,
            name="Meridian - 2 x 2 x mile",
            run_shape=_shape("anomaly"),
            distance_m=13837,
            duration_s=4626,
            avg_hr=146,
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
            _meridian_2026_04_18_splits()
        )
        with patch(
            "services.run_intelligence._get_interval_history", return_value=None
        ):
            ctx = _build_data_context(a, db)
        assert "intervals" in ctx, (
            "anomaly-shape + name-suggests-intervals + clean rep pattern "
            "must route to the intervals branch, not the continuous one"
        )
        assert ctx["intervals"]["total_reps"] == 4
        # And the cooldown mile must be tagged so the LLM doesn't read it as a fade.
        assert "cooldown" in ctx["intervals"]
        assert ctx["intervals"]["cooldown"]["split_number"] == 18
