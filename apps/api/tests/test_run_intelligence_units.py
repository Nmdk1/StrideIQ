"""
Run-intelligence unit-awareness regression tests.

The bug this guards against (Dejan, 2026-04-22): a metric athlete opened
the Coach card on a 10mi run and saw "10.0 mi at 8:46/mi -- marathon
pace." plus an "Elevation 188ft" highlight. The cause was that
`run_intelligence.py` hardcoded imperial in `_build_headline`,
`_build_highlights`, and the JSON dict fed to Kimi (`distance_miles`,
`avg_pace_per_mile`, `elevation_gain_ft`, `pace_per_mile` on each rep).
The LLM faithfully echoed those imperial labels back to a metric user.

These tests pin the contract that:
  1. Headline distance + pace use the athlete's units.
  2. Elevation highlight uses the athlete's units.
  3. The LLM context dict has NO imperial-coded field names that would
     leak into the prose for metric athletes.
  4. The LLM context exposes a `display_units` field so the SYSTEM_PROMPT
     can instruct unit-correct output.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

from services.coach_units import coach_units
from services.run_intelligence import (
    _build_data_context,
    _build_headline,
    _build_highlights,
    _fmt_distance,
    _fmt_elevation,
    _fmt_pace,
    _fmt_temperature_from_f,
)


METRIC = coach_units("metric")
IMPERIAL = coach_units("imperial")


def _activity(**overrides):
    a = MagicMock()
    a.id = overrides.get("id", uuid4())
    a.athlete_id = overrides.get("athlete_id", uuid4())
    a.name = overrides.get("name", "Morning Run")
    a.distance_m = overrides.get("distance_m", 16093.4)  # 10.0 mi == 16.09 km
    a.duration_s = overrides.get("duration_s", 5260.0)   # 8:46/mi == 5:27/km
    a.avg_hr = overrides.get("avg_hr", 128)
    a.max_hr = overrides.get("max_hr", 143)
    a.workout_type = overrides.get("workout_type", "moderate")
    a.is_race_candidate = overrides.get("is_race_candidate", False)
    a.start_time = overrides.get("start_time", datetime(2026, 4, 20, 7, 0))
    a.total_elevation_gain = overrides.get("total_elevation_gain", 57.3)  # ~188 ft
    a.pre_sleep_h = None
    a.pre_sleep_score = None
    a.pre_resting_hr = None
    a.pre_recovery_hrv = None
    a.pre_overnight_hrv = None
    a.temperature_f = overrides.get("temperature_f", None)
    a.humidity_pct = overrides.get("humidity_pct", None)
    a.dew_point_f = overrides.get("dew_point_f", None)
    a.heat_adjustment_pct = overrides.get("heat_adjustment_pct", None)
    a.weather_condition = None
    a.avg_cadence = None
    a.run_shape = None
    return a


# ---------------------------------------------------------------- helpers


class TestUnitAwareFormatters:
    def test_fmt_pace_imperial(self):
        # 5260 / 16.0934 = 326.83 s/km -> 326.83 * 1.60934 = 526 s/mi == 8:46/mi
        result = _fmt_pace(326.83, IMPERIAL)
        assert result == "8:46/mi"

    def test_fmt_pace_metric(self):
        result = _fmt_pace(326.83, METRIC)
        assert result == "5:27/km"

    def test_fmt_pace_rounds_secs_60_to_next_minute(self):
        # 359.5 s/km rounds to 6:00/km, not 5:60/km.
        result = _fmt_pace(359.5, METRIC)
        assert result == "6:00/km"

    def test_fmt_distance_imperial(self):
        assert _fmt_distance(16093.4, IMPERIAL) == "10.0"

    def test_fmt_distance_metric(self):
        assert _fmt_distance(16093.4, METRIC) == "16.1"

    def test_fmt_elevation_imperial(self):
        # 57.3 m * 3.28084 = 188 ft
        assert _fmt_elevation(57.3, IMPERIAL) == "188ft"

    def test_fmt_elevation_metric(self):
        assert _fmt_elevation(57.3, METRIC) == "57m"

    def test_fmt_temperature_imperial(self):
        assert _fmt_temperature_from_f(60.0, IMPERIAL) == "60.0°F"

    def test_fmt_temperature_metric(self):
        # 60 F -> 15.6 C
        assert _fmt_temperature_from_f(60.0, METRIC) == "15.6°C"


# ------------------------------------------------------------ headline


class TestHeadlineUnitAwareness:
    def test_headline_imperial(self):
        a = _activity()
        headline = _build_headline(a, interval_data=None, units=IMPERIAL)
        assert "10.0 mi" in headline
        assert "8:46/mi" in headline
        assert "/km" not in headline
        assert " km " not in headline

    def test_headline_metric_dejan_regression(self):
        # Exactly the run from the founder-flagged screenshot.
        a = _activity()
        headline = _build_headline(a, interval_data=None, units=METRIC)
        # Metric athlete must see km and /km -- nothing imperial.
        assert "16.1 km" in headline
        assert "5:27/km" in headline
        assert "/mi" not in headline
        assert " mi " not in headline

    def test_headline_intervals_metric_uses_clean_avg_pace_s_km(self):
        # When interval_data carries the canonical s_km value, the headline
        # must derive the displayed pace from it (not from any pre-formatted
        # /mi string that happens to be on the same dict).
        a = _activity(workout_type="interval")
        interval_data = {
            "clean_reps": 4,
            "total_reps": 4,
            "busted_reps": [],
            "reps": [{"distance_m": 1609}],
            "clean_avg_pace_s_km": 240.0,           # 4:00/km == 6:26/mi
            "clean_avg_pace_per_mile": "6:26/mi",   # legacy key, must be ignored
        }
        headline = _build_headline(a, interval_data=interval_data, units=METRIC)
        assert "4:00/km" in headline
        assert "/mi" not in headline


# ------------------------------------------------------------ highlights


class TestHighlightUnitAwareness:
    def test_elevation_highlight_imperial(self):
        a = _activity(total_elevation_gain=57.3)
        hl = _build_highlights(
            a, drift=None, pacing=None, efficiency=None, interval_data=None,
            units=IMPERIAL,
        )
        elev = next(h for h in hl if h.label == "Elevation")
        assert elev.value == "188ft"

    def test_elevation_highlight_metric_dejan_regression(self):
        a = _activity(total_elevation_gain=57.3)
        hl = _build_highlights(
            a, drift=None, pacing=None, efficiency=None, interval_data=None,
            units=METRIC,
        )
        elev = next(h for h in hl if h.label == "Elevation")
        assert elev.value == "57m"
        # The exact bug: metric athlete saw "188ft" instead.
        assert "ft" not in elev.value

    def test_no_elevation_highlight_below_threshold(self):
        # Below 30m the chip is suppressed regardless of units.
        a = _activity(total_elevation_gain=10)
        hl = _build_highlights(
            a, drift=None, pacing=None, efficiency=None, interval_data=None,
            units=METRIC,
        )
        labels = [h.label for h in hl]
        assert "Elevation" not in labels


# ----------------------------------------------------------- LLM context


class TestDataContextUnitAwareness:
    @patch("services.run_intelligence._get_athlete_notes", return_value=None)
    @patch("services.run_intelligence._get_drift_history_avg", return_value=None)
    @patch("services.run_intelligence._get_efficiency_vs_peers", return_value=None)
    @patch("services.run_intelligence._get_stream_drift", return_value=None)
    @patch("services.run_intelligence._get_split_pacing", return_value=None)
    def test_metric_context_strips_imperial_field_names(self, *mocks):
        a = _activity()
        db = MagicMock()
        ctx = _build_data_context(a, db, units=METRIC)
        # The `display_units` flag is what the SYSTEM_PROMPT keys off of.
        assert ctx["display_units"] == "metric"
        # The new fields are pre-formatted in the athlete's units.
        assert ctx["distance"].endswith(" km")
        assert ctx["avg_pace"].endswith("/km")
        # The historical imperial-coded keys MUST NOT appear -- those were
        # the source of Kimi echoing "/mi" at metric athletes.
        assert "distance_miles" not in ctx
        assert "avg_pace_per_mile" not in ctx
        assert "elevation_gain_ft" not in ctx

    @patch("services.run_intelligence._get_athlete_notes", return_value=None)
    @patch("services.run_intelligence._get_drift_history_avg", return_value=None)
    @patch("services.run_intelligence._get_efficiency_vs_peers", return_value=None)
    @patch("services.run_intelligence._get_stream_drift", return_value=None)
    @patch("services.run_intelligence._get_split_pacing", return_value=None)
    def test_metric_context_elevation_display(self, *mocks):
        a = _activity(total_elevation_gain=57.3)
        db = MagicMock()
        ctx = _build_data_context(a, db, units=METRIC)
        # Display-formatted elevation in the athlete's units.
        assert ctx["elevation_display"] == "57m"

    @patch("services.run_intelligence._get_athlete_notes", return_value=None)
    @patch("services.run_intelligence._get_drift_history_avg", return_value=None)
    @patch("services.run_intelligence._get_efficiency_vs_peers", return_value=None)
    @patch("services.run_intelligence._get_stream_drift", return_value=None)
    @patch("services.run_intelligence._get_split_pacing", return_value=None)
    def test_metric_context_temperature_display_alongside_raw_f(self, *mocks):
        # We KEEP the raw `_f` fields because the SYSTEM_PROMPT's heat-stress
        # thresholds are F-anchored (validated science). We ADD a `_display`
        # in the athlete's units so the narrative quotes the right one.
        a = _activity(temperature_f=83.3, dew_point_f=59.7, heat_adjustment_pct=0.03)
        db = MagicMock()
        ctx = _build_data_context(a, db, units=METRIC)
        assert ctx["temperature_f"] == 83
        assert ctx["dew_point_f"] == 59.7
        assert ctx["temperature_display"].endswith("°C")
        assert ctx["dew_point_display"].endswith("°C")

    @patch("services.run_intelligence._get_athlete_notes", return_value=None)
    @patch("services.run_intelligence._get_drift_history_avg", return_value=None)
    @patch("services.run_intelligence._get_efficiency_vs_peers", return_value=None)
    @patch("services.run_intelligence._get_stream_drift", return_value=None)
    @patch("services.run_intelligence._get_split_pacing")
    def test_metric_context_pacing_block_strips_per_mile_keys(self, mock_pacing, *_):
        # Pacing splits live inside `pacing.splits`. Each split historically
        # carried `pace_per_mile` -- the LLM read those and quoted them.
        # After projection: `pace` is in athlete units, `pace_per_mile` is
        # gone, and `first_half_avg_pace`/`second_half_avg_pace` are
        # recomputed in athlete units.
        mock_pacing.return_value = {
            "type": "continuous",
            "splits": [
                {"split": 1, "distance_m": 1609, "pace_per_mile": "8:46/mi", "pace_s_km": 327.0},
                {"split": 2, "distance_m": 1609, "pace_per_mile": "8:50/mi", "pace_s_km": 329.5},
                {"split": 3, "distance_m": 1609, "pace_per_mile": "8:48/mi", "pace_s_km": 328.2},
            ],
            "first_half_avg_pace": "8:48/mi",
            "second_half_avg_pace": "8:49/mi",
            "decay_pct": 0.4,
        }
        a = _activity()
        db = MagicMock()
        ctx = _build_data_context(a, db, units=METRIC)
        assert "pacing" in ctx
        for s in ctx["pacing"]["splits"]:
            assert "pace_per_mile" not in s
            assert s["pace"].endswith("/km")
        assert ctx["pacing"]["first_half_avg_pace"].endswith("/km")
        assert ctx["pacing"]["second_half_avg_pace"].endswith("/km")

    @patch("services.run_intelligence._get_athlete_notes", return_value=None)
    @patch("services.run_intelligence._get_drift_history_avg", return_value=None)
    @patch("services.run_intelligence._get_efficiency_vs_peers", return_value=None)
    @patch("services.run_intelligence._get_stream_drift", return_value=None)
    @patch("services.run_intelligence._get_split_pacing", return_value=None)
    @patch("services.run_intelligence._get_interval_analysis")
    @patch("services.run_intelligence._is_interval_workout", return_value=True)
    def test_metric_context_interval_block_strips_per_mile_keys(
        self, _is_iv, mock_iv, *_
    ):
        mock_iv.return_value = {
            "type": "interval",
            "reps": [
                {"rep": 1, "distance_m": 1609, "elapsed_s": 360, "pace_per_mile": "6:00/mi", "pace_s_km": 224.0, "avg_hr": 168, "split_number": 3, "busted": False},
                {"rep": 2, "distance_m": 1609, "elapsed_s": 362, "pace_per_mile": "6:02/mi", "pace_s_km": 225.2, "avg_hr": 169, "split_number": 5, "busted": False},
            ],
            "clean_avg_pace_per_mile": "6:01/mi",
            "clean_avg_pace_s_km": 224.6,
            "max_spread_pct": 0.4,
            "total_reps": 2,
            "clean_reps": 2,
            "busted_reps": [],
            "avg_hr_work": 168,
            "history": None,
            "derived_from_pace": False,
        }
        a = _activity(workout_type="interval")
        db = MagicMock()
        ctx = _build_data_context(a, db, units=METRIC)
        assert "intervals" in ctx
        for r in ctx["intervals"]["reps"]:
            assert "pace_per_mile" not in r
            assert r["pace"].endswith("/km")
        assert ctx["intervals"]["clean_avg_pace"].endswith("/km")
        assert "clean_avg_pace_per_mile" not in ctx["intervals"]
