"""
Phase 3 Tool Data Expansion Tests

Tests for:
1. get_recent_runs - expanded with elevation, weather, max_hr
2. get_wellness_trends - sleep/stress/soreness/HRV trends
3. get_athlete_profile - thresholds, runner_type, HR zones
4. get_training_load_history - ATL/CTL/TSB trends
"""

import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4
from datetime import datetime, date, timedelta
from decimal import Decimal


class TestGetRecentRunsExpanded:
    """Test expanded get_recent_runs with elevation, weather, max_hr."""

    def test_includes_max_hr(self):
        """Runs should include max_hr field."""
        from services.coach_tools import get_recent_runs
        
        mock_db = MagicMock()
        athlete_id = uuid4()
        
        # Mock activity with max_hr
        mock_activity = MagicMock()
        mock_activity.id = uuid4()
        mock_activity.athlete_id = athlete_id
        mock_activity.start_time = datetime.utcnow()
        mock_activity.name = "Morning Run"
        mock_activity.distance_m = 5000
        mock_activity.duration_s = 1500
        mock_activity.avg_hr = 145
        mock_activity.max_hr = 175
        mock_activity.total_elevation_gain = None
        mock_activity.temperature_f = None
        mock_activity.humidity_pct = None
        mock_activity.weather_condition = None
        mock_activity.workout_type = "easy_run"
        mock_activity.intensity_score = 50
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_activity]
        
        # Mock athlete for units
        mock_athlete = MagicMock()
        mock_athlete.preferred_units = "imperial"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_athlete
        
        result = get_recent_runs(mock_db, athlete_id, days=7)
        
        assert result["ok"] is True
        assert len(result["data"]["runs"]) == 1
        assert result["data"]["runs"][0]["max_hr"] == 175

    def test_includes_elevation_gain(self):
        """Runs should include elevation_gain_m and elevation_gain_ft fields."""
        from services.coach_tools import get_recent_runs
        
        mock_db = MagicMock()
        athlete_id = uuid4()
        
        mock_activity = MagicMock()
        mock_activity.id = uuid4()
        mock_activity.athlete_id = athlete_id
        mock_activity.start_time = datetime.utcnow()
        mock_activity.name = "Hill Run"
        mock_activity.distance_m = 8000
        mock_activity.duration_s = 2400
        mock_activity.avg_hr = 155
        mock_activity.max_hr = 180
        mock_activity.total_elevation_gain = Decimal("150.5")  # 150.5 meters
        mock_activity.temperature_f = None
        mock_activity.humidity_pct = None
        mock_activity.weather_condition = None
        mock_activity.workout_type = "tempo_run"
        mock_activity.intensity_score = 70
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_activity]
        mock_athlete = MagicMock()
        mock_athlete.preferred_units = "imperial"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_athlete
        
        result = get_recent_runs(mock_db, athlete_id, days=7)
        
        assert result["ok"] is True
        run = result["data"]["runs"][0]
        assert run["elevation_gain_m"] == 150.5
        assert run["elevation_gain_ft"] == 494  # ~150.5 * 3.28084

    def test_includes_weather_data(self):
        """Runs should include weather fields."""
        from services.coach_tools import get_recent_runs
        
        mock_db = MagicMock()
        athlete_id = uuid4()
        
        mock_activity = MagicMock()
        mock_activity.id = uuid4()
        mock_activity.athlete_id = athlete_id
        mock_activity.start_time = datetime.utcnow()
        mock_activity.name = "Hot Run"
        mock_activity.distance_m = 10000
        mock_activity.duration_s = 3000
        mock_activity.avg_hr = 160
        mock_activity.max_hr = 185
        mock_activity.total_elevation_gain = Decimal("50")
        mock_activity.temperature_f = 85.5
        mock_activity.humidity_pct = 75.0
        mock_activity.weather_condition = "cloudy"
        mock_activity.workout_type = "long_run"
        mock_activity.intensity_score = 60
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_activity]
        mock_athlete = MagicMock()
        mock_athlete.preferred_units = "metric"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_athlete
        
        result = get_recent_runs(mock_db, athlete_id, days=7)
        
        assert result["ok"] is True
        run = result["data"]["runs"][0]
        assert run["temperature_f"] == 85.5
        assert run["humidity_pct"] == 75
        assert run["weather_condition"] == "cloudy"


class TestGetWellnessTrends:
    """Test get_wellness_trends tool."""

    def test_returns_sleep_trends(self):
        """Should return sleep averages and trends."""
        from services.coach_tools import get_wellness_trends
        
        mock_db = MagicMock()
        athlete_id = uuid4()
        
        # Create mock check-ins
        checkins = []
        for i in range(14):
            checkin = MagicMock()
            checkin.date = date.today() - timedelta(days=i)
            checkin.sleep_h = Decimal(str(7.0 + (i % 3) * 0.5))  # Vary between 7-8h
            checkin.stress_1_5 = 3
            checkin.soreness_1_5 = 2
            checkin.hrv_rmssd = Decimal("45.0")
            checkin.hrv_sdnn = Decimal("55.0")
            checkin.resting_hr = 55
            checkin.overnight_avg_hr = Decimal("52.0")
            checkin.enjoyment_1_5 = 4
            checkin.confidence_1_5 = 4
            checkin.motivation_1_5 = 4
            checkins.append(checkin)
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = checkins
        
        result = get_wellness_trends(mock_db, athlete_id, days=28)
        
        assert result["ok"] is True
        assert result["data"]["checkin_count"] == 14
        assert result["data"]["sleep"]["avg_hours"] is not None
        assert result["data"]["sleep"]["data_points"] == 14

    def test_returns_stress_and_soreness(self):
        """Should return stress and soreness metrics."""
        from services.coach_tools import get_wellness_trends
        
        mock_db = MagicMock()
        athlete_id = uuid4()
        
        checkins = []
        for i in range(7):
            checkin = MagicMock()
            checkin.date = date.today() - timedelta(days=i)
            checkin.sleep_h = Decimal("7.5")
            checkin.stress_1_5 = 2 + (i % 2)  # Alternating 2-3
            checkin.soreness_1_5 = 3
            checkin.hrv_rmssd = None
            checkin.hrv_sdnn = None
            checkin.resting_hr = None
            checkin.overnight_avg_hr = None
            checkin.enjoyment_1_5 = None
            checkin.confidence_1_5 = None
            checkin.motivation_1_5 = None
            checkins.append(checkin)
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = checkins
        
        result = get_wellness_trends(mock_db, athlete_id, days=14)
        
        assert result["ok"] is True
        assert result["data"]["stress"]["avg"] is not None
        assert result["data"]["soreness"]["avg"] == 3.0

    def test_handles_no_checkins(self):
        """Should handle case with no check-ins gracefully."""
        from services.coach_tools import get_wellness_trends
        
        mock_db = MagicMock()
        athlete_id = uuid4()
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        
        result = get_wellness_trends(mock_db, athlete_id, days=28)
        
        assert result["ok"] is True
        assert result["data"]["checkin_count"] == 0
        assert "message" in result["data"]


class TestGetAthleteProfile:
    """Test get_athlete_profile tool."""

    def test_returns_physiological_data(self):
        """Should return max_hr, thresholds, VDOT."""
        from services.coach_tools import get_athlete_profile
        
        mock_db = MagicMock()
        athlete_id = uuid4()
        
        mock_athlete = MagicMock()
        mock_athlete.id = athlete_id
        mock_athlete.preferred_units = "imperial"
        mock_athlete.birthdate = date(1985, 6, 15)
        mock_athlete.sex = "M"
        mock_athlete.height_cm = Decimal("180")
        mock_athlete.max_hr = 185
        mock_athlete.resting_hr = 52
        mock_athlete.threshold_hr = 165
        mock_athlete.threshold_pace_per_km = 270.0  # 4:30/km
        mock_athlete.vdot = 52.5
        mock_athlete.runner_type = "balanced"
        mock_athlete.runner_type_confidence = 0.85
        mock_athlete.runner_type_last_calculated = datetime.utcnow()
        mock_athlete.durability_index = 75.0
        mock_athlete.recovery_half_life_hours = 36.0
        mock_athlete.consistency_index = 82.0
        mock_athlete.current_streak_weeks = 8
        mock_athlete.longest_streak_weeks = 12
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_athlete
        
        result = get_athlete_profile(mock_db, athlete_id)
        
        assert result["ok"] is True
        assert result["data"]["physiological"]["max_hr"] == 185
        assert result["data"]["physiological"]["vdot"] == 52.5
        assert result["data"]["runner_typing"]["type"] == "balanced"

    def test_calculates_hr_zones(self):
        """Should calculate HR zones from max_hr."""
        from services.coach_tools import get_athlete_profile
        
        mock_db = MagicMock()
        athlete_id = uuid4()
        
        mock_athlete = MagicMock()
        mock_athlete.id = athlete_id
        mock_athlete.preferred_units = "metric"
        mock_athlete.birthdate = None
        mock_athlete.sex = None
        mock_athlete.height_cm = None
        mock_athlete.max_hr = 200
        mock_athlete.resting_hr = None
        mock_athlete.threshold_hr = None
        mock_athlete.threshold_pace_per_km = None
        mock_athlete.vdot = None
        mock_athlete.runner_type = None
        mock_athlete.runner_type_confidence = None
        mock_athlete.runner_type_last_calculated = None
        mock_athlete.durability_index = None
        mock_athlete.recovery_half_life_hours = None
        mock_athlete.consistency_index = None
        mock_athlete.current_streak_weeks = 0
        mock_athlete.longest_streak_weeks = 0
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_athlete
        
        result = get_athlete_profile(mock_db, athlete_id)
        
        assert result["ok"] is True
        zones = result["data"]["physiological"]["hr_zones"]
        assert zones is not None
        assert zones["zone_1_recovery"]["min"] == 100  # 50% of 200
        assert zones["zone_5_max"]["max"] == 200

    def test_handles_missing_athlete(self):
        """Should return error for missing athlete."""
        from services.coach_tools import get_athlete_profile
        
        mock_db = MagicMock()
        athlete_id = uuid4()
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = get_athlete_profile(mock_db, athlete_id)
        
        assert result["ok"] is False
        assert "error" in result


class TestGetTrainingLoadHistory:
    """Test get_training_load_history tool."""

    def test_returns_load_progression(self):
        """Should return ATL/CTL/TSB history."""
        from services.coach_tools import get_training_load_history
        
        mock_db = MagicMock()
        athlete_id = uuid4()
        
        # Create mock activities over 30 days
        activities = []
        for i in range(30):
            activity = MagicMock()
            activity.id = uuid4()
            activity.start_time = datetime.utcnow() - timedelta(days=30-i)
            activity.duration_s = 3600  # 1 hour
            activity.intensity_score = 50 + (i % 20)  # Vary intensity
            activities.append(activity)
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = activities
        
        result = get_training_load_history(mock_db, athlete_id, days=28)
        
        assert result["ok"] is True
        assert "history" in result["data"]
        assert len(result["data"]["history"]) > 0
        
        # Check that each entry has required fields
        entry = result["data"]["history"][-1]
        assert "atl" in entry
        assert "ctl" in entry
        assert "tsb" in entry
        assert "form_state" in entry
        assert "injury_risk" in entry

    def test_identifies_form_states(self):
        """Should correctly identify fresh/fatigued/balanced states."""
        from services.coach_tools import get_training_load_history
        
        mock_db = MagicMock()
        athlete_id = uuid4()
        
        # Create activities that produce clear TSB states
        activities = []
        for i in range(60):
            activity = MagicMock()
            activity.id = uuid4()
            activity.start_time = datetime.utcnow() - timedelta(days=60-i)
            # Heavy training early, taper later
            if i < 40:
                activity.duration_s = 5400  # 1.5 hours
                activity.intensity_score = 70
            else:
                activity.duration_s = 2400  # 40 min
                activity.intensity_score = 40
            activities.append(activity)
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = activities
        
        result = get_training_load_history(mock_db, athlete_id, days=42)
        
        assert result["ok"] is True
        # Should have a mix of form states due to training pattern
        form_states = [h["form_state"] for h in result["data"]["history"]]
        assert any(s in form_states for s in ["fresh", "fatigued", "balanced"])

    def test_handles_no_activities(self):
        """Should handle case with no activities gracefully."""
        from services.coach_tools import get_training_load_history
        
        mock_db = MagicMock()
        athlete_id = uuid4()
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        
        result = get_training_load_history(mock_db, athlete_id, days=28)
        
        assert result["ok"] is True
        assert "message" in result["data"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
