"""
ADR-16: Coach Context Architecture Tests

Phase 1: Running math calculator + goal race context
Phase 2+: Brief builder, tool narratives (added incrementally)
"""

import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4
from datetime import date, datetime, timedelta


# =============================================================================
# PHASE 1: Running Math Calculator
# =============================================================================


class TestComputeRunningMath:
    """Test the compute_running_math tool for pace/distance/time calculations."""

    @pytest.fixture
    def db(self):
        return MagicMock()

    @pytest.fixture
    def athlete_id(self):
        return uuid4()

    def test_pace_to_finish_marathon_imperial(self, db, athlete_id):
        """7:15/mi pace for 26.2 miles should give ~3:09:56."""
        from services.coach_tools import compute_running_math

        result = compute_running_math(
            db, athlete_id,
            pace_per_mile="7:15",
            distance_miles=26.2,
            operation="pace_to_finish",
        )
        assert result["ok"] is True
        data = result["data"]
        # 7:15/mi = 435s/mi × 26.2 = 11397s = 3:09:57
        assert data["finish_time"] in ("3:09:57", "3:09:56", "3:09:58")  # rounding tolerance
        assert data["pace_per_mile"] == "7:15/mi"
        assert data["distance_miles"] == 26.2

    def test_pace_to_finish_half_marathon(self, db, athlete_id):
        """6:40/mi pace for 13.1 miles should give ~1:27:24."""
        from services.coach_tools import compute_running_math

        result = compute_running_math(
            db, athlete_id,
            pace_per_mile="6:40",
            distance_miles=13.1,
            operation="pace_to_finish",
        )
        assert result["ok"] is True
        data = result["data"]
        # 6:40/mi = 400s × 13.1 = 5240s = 1:27:20
        assert "1:27" in data["finish_time"]

    def test_pace_to_finish_metric(self, db, athlete_id):
        """5:00/km pace for 42.195 km should give ~3:30:59."""
        from services.coach_tools import compute_running_math

        result = compute_running_math(
            db, athlete_id,
            pace_per_km="5:00",
            distance_km=42.195,
            operation="pace_to_finish",
        )
        assert result["ok"] is True
        data = result["data"]
        # 300s × 42.195 = 12658.5s = 3:30:59
        assert "3:30" in data["finish_time"] or "3:31" in data["finish_time"]

    def test_finish_to_pace(self, db, athlete_id):
        """3:10:00 marathon should give ~7:15/mi pace."""
        from services.coach_tools import compute_running_math

        result = compute_running_math(
            db, athlete_id,
            time_seconds=3 * 3600 + 10 * 60,  # 11400s
            distance_miles=26.2,
            operation="finish_to_pace",
        )
        assert result["ok"] is True
        data = result["data"]
        # 11400 / 26.2 = 435.1s = 7:15
        assert "7:15" in data["pace_per_mile"]

    def test_split_calc_negative_split(self, db, athlete_id):
        """7:30 first half, 7:00 second half for marathon."""
        from services.coach_tools import compute_running_math

        result = compute_running_math(
            db, athlete_id,
            pace_per_mile="7:30,7:00",
            distance_miles=26.2,
            operation="split_calc",
        )
        assert result["ok"] is True
        data = result["data"]
        assert data["first_half_pace"] == "7:30/mi"
        assert data["second_half_pace"] == "7:00/mi"
        # Average should be ~7:15
        assert "7:15" in data["average_pace"]
        assert data["negative_split_seconds"] > 0  # first half slower = positive diff

    def test_missing_pace_returns_error(self, db, athlete_id):
        """Missing pace should return an error, not crash."""
        from services.coach_tools import compute_running_math

        result = compute_running_math(
            db, athlete_id,
            distance_miles=26.2,
            operation="pace_to_finish",
        )
        assert result["ok"] is False
        assert "error" in result

    def test_missing_distance_returns_error(self, db, athlete_id):
        """Missing distance should return an error, not crash."""
        from services.coach_tools import compute_running_math

        result = compute_running_math(
            db, athlete_id,
            pace_per_mile="7:15",
            operation="pace_to_finish",
        )
        assert result["ok"] is False
        assert "error" in result

    def test_unknown_operation_returns_error(self, db, athlete_id):
        """Unknown operation should return an error."""
        from services.coach_tools import compute_running_math

        result = compute_running_math(
            db, athlete_id,
            pace_per_mile="7:15",
            distance_miles=26.2,
            operation="unknown_op",
        )
        assert result["ok"] is False

    def test_pace_format_with_unit_suffix(self, db, athlete_id):
        """Pace strings with /mi or /km suffix should parse correctly."""
        from services.coach_tools import compute_running_math

        result = compute_running_math(
            db, athlete_id,
            pace_per_mile="7:15/mi",
            distance_miles=26.2,
            operation="pace_to_finish",
        )
        assert result["ok"] is True
        assert "3:09" in result["data"]["finish_time"] or "3:10" in result["data"]["finish_time"]


# =============================================================================
# PHASE 1: Goal Race Context in get_plan_week
# =============================================================================


class TestGoalRaceContext:
    """Test that get_plan_week surfaces goal_time_seconds, distance, pace, countdown."""

    @pytest.fixture
    def db(self):
        return MagicMock()

    def test_goal_fields_present_in_plan_output(self, db):
        """get_plan_week should include goal time, distance, pace, and countdown."""
        from services.coach_tools import get_plan_week

        athlete_id = uuid4()

        # Mock plan
        mock_plan = MagicMock()
        mock_plan.id = uuid4()
        mock_plan.name = "Marathon Build"
        mock_plan.goal_race_name = "Boston Marathon"
        mock_plan.goal_race_date = date(2026, 3, 15)
        mock_plan.goal_race_distance_m = 42195
        mock_plan.goal_time_seconds = 11400  # 3:10:00
        mock_plan.total_weeks = 16

        # Mock DB queries
        db.query.return_value.filter.return_value.first.return_value = mock_plan
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        result = get_plan_week(db, athlete_id)
        plan_data = result["data"]["plan"]

        assert plan_data["goal_race_distance_m"] == 42195
        assert plan_data["goal_time_seconds"] == 11400
        assert plan_data["goal_time_formatted"] == "3:10:00"
        assert plan_data["goal_pace_per_mile"] is not None
        assert "7:15" in plan_data["goal_pace_per_mile"] or "7:14" in plan_data["goal_pace_per_mile"]
        assert plan_data["days_until_race"] is not None
        assert isinstance(plan_data["days_until_race"], int)

    def test_goal_fields_none_when_no_goal_time(self, db):
        """If no goal_time_seconds, formatted fields should be None."""
        from services.coach_tools import get_plan_week

        athlete_id = uuid4()

        mock_plan = MagicMock()
        mock_plan.id = uuid4()
        mock_plan.name = "Base Build"
        mock_plan.goal_race_name = "Local 10K"
        mock_plan.goal_race_date = date(2026, 5, 1)
        mock_plan.goal_race_distance_m = 10000
        mock_plan.goal_time_seconds = None
        mock_plan.total_weeks = 12

        db.query.return_value.filter.return_value.first.return_value = mock_plan
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        result = get_plan_week(db, athlete_id)
        plan_data = result["data"]["plan"]

        assert plan_data["goal_time_formatted"] is None
        assert plan_data["goal_pace_per_mile"] is None
        assert plan_data["days_until_race"] is not None

    def test_no_plan_returns_none(self, db):
        """If no active plan, plan field should be None."""
        from services.coach_tools import get_plan_week

        athlete_id = uuid4()

        db.query.return_value.filter.return_value.first.return_value = None

        result = get_plan_week(db, athlete_id)
        assert result["data"]["plan"] is None


# =============================================================================
# PHASE 2: Athlete Brief Builder
# =============================================================================


class TestBuildAthleteBrief:
    """Test build_athlete_brief() produces a comprehensive, human-readable brief."""

    @pytest.fixture
    def db(self):
        return MagicMock()

    @pytest.fixture
    def athlete_id(self):
        return uuid4()

    def test_brief_returns_string(self, db, athlete_id):
        """Brief should always return a string, even if all calls fail."""
        from services.coach_tools import build_athlete_brief

        # All DB queries return None
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        result = build_athlete_brief(db, athlete_id)
        assert isinstance(result, str)
        assert len(result) > 0

    @patch("services.coach_tools.get_training_load")
    @patch("services.coach_tools.get_recovery_status")
    @patch("services.coach_tools.get_weekly_volume")
    @patch("services.coach_tools.get_recent_runs")
    @patch("services.coach_tools.get_race_predictions")
    @patch("services.coach_tools.get_training_paces")
    @patch("services.coach_tools.get_pb_patterns")
    @patch("services.coach_tools.get_correlations")
    @patch("services.coach_tools.get_efficiency_trend")
    @patch("services.coach_tools.get_coach_intent_snapshot")
    def test_brief_includes_all_sections(
        self, mock_intent, mock_eff, mock_corr, mock_pbs, mock_paces,
        mock_preds, mock_runs, mock_volume, mock_recovery, mock_load,
        db, athlete_id,
    ):
        """A fully populated athlete should produce a brief with all sections."""
        from services.coach_tools import build_athlete_brief

        from models import Athlete, TrainingPlan, DailyCheckin

        mock_athlete = MagicMock()
        mock_athlete.display_name = "Mike"
        mock_athlete.birthdate = date(1968, 6, 15)
        mock_athlete.sex = "male"
        mock_athlete.preferred_units = "imperial"

        mock_plan = MagicMock(
            goal_race_name="Boston Marathon",
            goal_race_date=date(2026, 3, 15),
            goal_race_distance_m=42195,
            goal_time_seconds=11400,
            total_weeks=16,
            name="Marathon Build",
            status="active",
        )

        def _route_query(model_cls):
            chain = MagicMock()
            if model_cls is Athlete:
                chain.filter.return_value.first.return_value = mock_athlete
            elif model_cls is TrainingPlan:
                chain.filter.return_value.first.return_value = mock_plan
            elif model_cls is DailyCheckin:
                chain.filter.return_value.order_by.return_value.first.return_value = None
            else:
                chain.filter.return_value.first.return_value = None
                chain.filter.return_value.count.return_value = 0
                chain.filter.return_value.order_by.return_value.first.return_value = None
                chain.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
                chain.filter.return_value.all.return_value = []
            return chain

        db.query.side_effect = _route_query

        # Mock tool returns
        mock_load.return_value = {"ok": True, "data": {
            "ctl": 30.6, "atl": 43.1, "tsb": -12.5,
            "tsb_zone": {"label": "fatigued"}, "training_phase": "building",
            "recommendation": "Maintain current load"
        }}
        mock_recovery.return_value = {"ok": True, "data": {
            "status": "moderate", "injury_risk_score": 0.4,
            "durability_index": 45.4, "recovery_half_life_hours": 2.1,
        }}
        mock_volume.return_value = {"ok": True, "data": {"weeks_data": [
            {"week_start": "2026-01-12", "total_distance_mi": 36.1, "run_count": 5},
            {"week_start": "2026-01-19", "total_distance_mi": 45.1, "run_count": 6},
            {"week_start": "2026-01-26", "total_distance_mi": 50.3, "run_count": 5},
            {"week_start": "2026-02-02", "total_distance_mi": 31.0, "run_count": 3,
             "is_current_week": True, "days_elapsed": 4, "days_remaining": 3},
        ]}}
        mock_runs.return_value = {"ok": True, "data": {"runs": [
            {"start_time": "2026-02-06", "name": "Lunch Run", "distance_mi": 8.0,
             "pace_per_mile": "9:04/mi", "avg_hr": 127},
        ]}}
        mock_preds.return_value = {"ok": True, "data": {"predictions": {
            "Marathon": {"prediction": {"time_formatted": "3:00:56", "confidence": "moderate"}},
            "Half Marathon": {"prediction": {"time_formatted": "1:27:12", "confidence": "high"}},
            "5K": {"prediction": {"time_formatted": "18:54", "confidence": "high"}},
            "10K": {"prediction": {"time_formatted": "39:12", "confidence": "high"}},
        }}}
        mock_paces.return_value = {"ok": True, "data": {
            "rpi": 53.2, "paces": {
                "easy": "8:05/mi", "marathon": "6:57/mi",
                "threshold": "6:32/mi", "interval": "5:45/mi",
                "repetition": "5:20/mi",
            }
        }}
        mock_pbs.return_value = {"ok": True, "data": {"pbs": [
            {"category": "Half Marathon", "distance_km": 21.1, "time_min": 87.2, "date": "2025-11-29"},
            {"category": "10K", "distance_km": 10.0, "time_min": 39.2, "date": "2025-12-13"},
        ]}}
        mock_corr.return_value = {"ok": True, "data": {"correlations": [
            {"input_name": "HRV", "output_name": "next-day performance",
             "correlation_coefficient": -0.6, "sample_size": 47},
        ]}}
        mock_eff.return_value = {"ok": True, "data": {
            "trend_direction": "stable", "average_ef": 13.1, "best_ef": 7.99,
        }}
        mock_intent.return_value = {"ok": True, "data": {
            "training_intent": "race_preparation", "pain_flag": "none",
            "weekly_mileage_target": "55-60",
        }}

        result = build_athlete_brief(db, athlete_id)

        # Verify all key sections are present
        assert "## Identity" in result
        assert "Mike" in result
        assert "57" in result  # age from 1968 birthdate

        assert "## Goal Race" in result
        assert "3:10:00" in result  # formatted goal time
        assert "7:15" in result or "7:14" in result  # goal pace

        assert "## Training State" in result
        assert "30.6" in result  # CTL

        assert "## Recovery" in result
        assert "45.4" in result  # durability

        assert "## Volume Trajectory" in result
        assert "Current week" in result
        assert "31.0" in result or "31" in result

        assert "## Recent Runs" in result
        assert "Lunch Run" in result

        assert "## Race Predictions" in result
        assert "3:00:56" in result

        assert "## Training Paces" in result
        assert "53.2" in result  # RPI

        assert "## Personal Bests" in result
        assert "Half Marathon" in result

        assert ("## Personal Fingerprint" in result or "## N-of-1 Insights" in result)

        assert "## Efficiency Trend" in result

    @patch("services.coach_tools.get_training_load")
    @patch("services.coach_tools.get_recovery_status")
    @patch("services.coach_tools.get_weekly_volume")
    @patch("services.coach_tools.get_recent_runs")
    @patch("services.coach_tools.get_race_predictions")
    @patch("services.coach_tools.get_training_paces")
    @patch("services.coach_tools.get_pb_patterns")
    @patch("services.coach_tools.get_correlations")
    @patch("services.coach_tools.get_efficiency_trend")
    @patch("services.coach_tools.get_coach_intent_snapshot")
    def test_brief_age_is_correct(
        self, mock_intent, mock_eff, mock_corr, mock_pbs, mock_paces,
        mock_preds, mock_runs, mock_volume, mock_recovery, mock_load,
        db, athlete_id,
    ):
        """Age should be correctly computed from birthdate — the exact failure from Feb 6."""
        from services.coach_tools import build_athlete_brief

        mock_athlete = MagicMock()
        mock_athlete.display_name = "Mike"
        mock_athlete.birthdate = date(1968, 6, 15)  # 57 years old as of Feb 2026
        mock_athlete.sex = "male"
        mock_athlete.preferred_units = "imperial"

        db.query.return_value.filter.return_value.first.return_value = mock_athlete
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        # All tools return empty/failed
        for mock in [mock_load, mock_recovery, mock_volume, mock_runs,
                     mock_preds, mock_paces, mock_pbs, mock_corr, mock_eff, mock_intent]:
            mock.return_value = {"ok": False}

        result = build_athlete_brief(db, athlete_id)

        assert "Age: 57" in result
        assert "58" not in result  # the exact error from the failed conversation


class TestBuildAthleteBriefRespectsUnits:
    """Regression: build_athlete_brief must format distances/paces in the
    athlete's preferred units. Imperial athletes see 'mi' and '/mi'; metric
    athletes see 'km' and '/km'. Mixing units in the brief is the root cause
    of the LLM emitting the wrong unit downstream.
    """

    @pytest.fixture
    def db(self):
        return MagicMock()

    @pytest.fixture
    def athlete_id(self):
        return uuid4()

    def _build_full_brief(self, db, athlete_id, *, preferred_units: str):
        from models import Athlete, TrainingPlan, DailyCheckin

        mock_athlete = MagicMock()
        mock_athlete.display_name = "Test Runner"
        mock_athlete.birthdate = date(1990, 1, 1)
        mock_athlete.sex = "male"
        mock_athlete.preferred_units = preferred_units

        mock_plan = MagicMock(
            goal_race_name="Boston Marathon",
            goal_race_date=date(2026, 4, 20),
            goal_race_distance_m=42195,
            goal_time_seconds=11400,
            total_weeks=16,
            name="Marathon Build",
            status="active",
        )

        def _route_query(model_cls):
            chain = MagicMock()
            if model_cls is Athlete:
                chain.filter.return_value.first.return_value = mock_athlete
            elif model_cls is TrainingPlan:
                chain.filter.return_value.first.return_value = mock_plan
            elif model_cls is DailyCheckin:
                chain.filter.return_value.order_by.return_value.first.return_value = None
            else:
                chain.filter.return_value.first.return_value = None
                chain.filter.return_value.count.return_value = 0
                chain.filter.return_value.order_by.return_value.first.return_value = None
                chain.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
                chain.filter.return_value.all.return_value = []
            return chain

        db.query.side_effect = _route_query

        # Stub fitness bank so 'Athlete Experience Calibration' renders.
        bank = MagicMock()
        bank.experience_level.value = "intermediate"
        bank.peak_weekly_miles = 50.0
        bank.current_weekly_miles = 30.0
        bank.current_long_run_miles = 12.0
        bank.is_returning_from_break = False

        weekly_data = {"weeks_data": [
            {"week_start": "2026-01-12", "total_distance_mi": 36.0, "total_distance_km": 57.9, "run_count": 5},
            {"week_start": "2026-01-19", "total_distance_mi": 45.0, "total_distance_km": 72.4, "run_count": 6},
            {"week_start": "2026-01-26", "total_distance_mi": 50.0, "total_distance_km": 80.5, "run_count": 5},
            {"week_start": "2026-02-02", "total_distance_mi": 31.0, "total_distance_km": 49.9, "run_count": 3,
             "is_current_week": True, "days_elapsed": 4, "days_remaining": 3},
        ]}
        runs_data = {"runs": [
            {
                "start_time": "2026-02-06",
                "name": "Lunch Run",
                "distance_mi": 8.0,
                "distance_km": 12.87,
                "pace_per_mile": "9:04/mi",
                "pace_per_km": "5:38/km",
                "avg_hr": 127,
                "elevation_gain_ft": 200,
                "elevation_gain_m": 61,
                "temperature_f": 50,
            },
        ]}

        from services.coach_tools import build_athlete_brief

        # Use a unique cache key per call by changing athlete_id-derived units in the cache.
        # Patch get_cache to always miss and set_cache as no-op so tests are isolated.
        with patch("services.fitness_bank.FitnessBankCalculator") as mock_fb, \
             patch("services.coach_tools.get_training_load", return_value={"ok": False}), \
             patch("services.coach_tools.get_recovery_status", return_value={"ok": False}), \
             patch("services.coach_tools.get_weekly_volume", return_value={"ok": True, "data": weekly_data}), \
             patch("services.coach_tools.get_recent_runs", return_value={"ok": True, "data": runs_data}), \
             patch("services.coach_tools.get_race_predictions", return_value={"ok": False}), \
             patch("services.coach_tools.get_training_paces", return_value={"ok": False}), \
             patch("services.coach_tools.get_pb_patterns", return_value={"ok": False}), \
             patch("services.coach_tools.get_correlations", return_value={"ok": False}), \
             patch("services.coach_tools.get_efficiency_trend", return_value={"ok": False}), \
             patch("services.coach_tools.get_coach_intent_snapshot",
                   return_value={"ok": True, "data": {"weekly_mileage_target": 40}}), \
             patch("core.cache.get_cache", return_value=None), \
             patch("core.cache.set_cache", return_value=None):
            mock_fb.return_value.calculate.return_value = bank
            return build_athlete_brief(db, athlete_id)

    def test_brief_imperial_uses_miles(self, db, athlete_id):
        result = self._build_full_brief(db, athlete_id, preferred_units="imperial")

        # Calibration
        assert "Peak proven weekly volume: 50 mi" in result
        assert "Current weekly volume: 30 mi" in result
        assert "Recent long run: 12.0 mi" in result
        # Goal race
        assert "26.2 miles" in result
        assert "/mi" in result
        # Volume trajectory
        assert "(mi)" in result
        assert "31.0mi" in result
        # Recent runs
        assert "8.0mi @ 9:04/mi" in result
        assert "+200ft" in result
        assert "50\u00b0F" in result
        # Intent
        assert "Weekly volume target: 40 mi" in result
        # NEVER show metric units to imperial athlete
        assert "/km" not in result.replace("distance_km", "")  # safety guard
        assert "km total" not in result

    def test_brief_metric_uses_kilometers(self, db, athlete_id):
        result = self._build_full_brief(db, athlete_id, preferred_units="metric")

        # Calibration (50 mi → ~80 km, 30 mi → ~48 km, 12 mi → ~19.3 km)
        assert "Peak proven weekly volume: 80 km" in result
        assert "Current weekly volume: 48 km" in result
        assert "Recent long run: 19.3 km" in result
        # Goal race
        assert "42.2 km" in result
        assert "/km" in result
        # Volume trajectory
        assert "(km)" in result
        assert "49.9km" in result
        # Recent runs
        assert "12.9km @ 5:38/km" in result
        assert "+61m" in result
        assert "10\u00b0C" in result  # 50°F = 10°C
        # Intent (40 mi → 64 km)
        assert "Weekly volume target: 64 km" in result
        # NEVER show imperial units to metric athlete
        assert "/mi" not in result
        assert " mi" not in result.replace(" miles", "")  # allow no imperial "mi" tokens
        assert "ft" not in result
        assert "°F" not in result
