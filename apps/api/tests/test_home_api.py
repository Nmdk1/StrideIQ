"""
Unit tests for Home API Router

Tests the Glance layer data:
- Today's workout with context
- Yesterday's insight
- Week progress with trajectory
"""

import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch
from routers.home import (
    generate_why_context,
    generate_yesterday_insight,
    generate_trajectory_sentence,
    format_phase,
    format_pace,
)


class TestFormatPhase:
    """Tests for phase display name formatting."""
    
    def test_base_phase(self):
        assert format_phase("base") == "Base"
    
    def test_threshold_phase(self):
        assert format_phase("threshold") == "Threshold"
    
    def test_marathon_specific_phase(self):
        assert format_phase("marathon_specific") == "Marathon Specific"
    
    def test_unknown_phase_formats_nicely(self):
        assert format_phase("custom_phase") == "Custom Phase"
    
    def test_none_returns_none(self):
        assert format_phase(None) is None


class TestFormatPace:
    """Tests for pace formatting."""
    
    def test_format_7_minute_pace(self):
        assert format_pace(420) == "7:00/mi"
    
    def test_format_8_30_pace(self):
        assert format_pace(510) == "8:30/mi"
    
    def test_format_sub_6_pace(self):
        assert format_pace(350) == "5:50/mi"


class TestGenerateTrajectory:
    """Tests for trajectory sentence generation."""
    
    def test_ahead_status(self):
        result = generate_trajectory_sentence("ahead", 30, 40)
        assert "Ahead of schedule" in result
        assert "30 mi done" in result
        assert "40 mi planned" in result
    
    def test_on_track_status(self):
        result = generate_trajectory_sentence("on_track", 20, 40)
        assert "On track" in result
        assert "20 mi remaining" in result
    
    def test_behind_status(self):
        result = generate_trajectory_sentence("behind", 10, 40)
        assert "Behind schedule" in result
        assert "30 mi to go" in result
    
    def test_no_plan_returns_none(self):
        result = generate_trajectory_sentence("no_plan", 0, 0)
        assert result is None


class TestGenerateWhyContext:
    """Tests for 'Why This Workout' context generation."""
    
    def test_threshold_workout_context(self):
        workout = MagicMock()
        workout.workout_type = "threshold"
        
        plan = MagicMock()
        plan.total_weeks = 12
        
        result = generate_why_context(workout, plan, 5, "threshold")
        
        assert "Week 5 of 12" in result
        assert "Threshold phase" in result
        assert "Builds lactate clearance" in result
    
    def test_long_run_context(self):
        workout = MagicMock()
        workout.workout_type = "long"
        
        plan = MagicMock()
        plan.total_weeks = 16
        
        result = generate_why_context(workout, plan, 8, "base")
        
        assert "Week 8 of 16" in result
        assert "Builds endurance and fat metabolism" in result
    
    def test_easy_run_context(self):
        workout = MagicMock()
        workout.workout_type = "easy"
        
        plan = MagicMock()
        plan.total_weeks = 12
        
        result = generate_why_context(workout, plan, 3, "base")
        
        assert "Active recovery day" in result
    
    def test_early_build_context(self):
        workout = MagicMock()
        workout.workout_type = "easy"
        
        plan = MagicMock()
        plan.total_weeks = 12
        
        result = generate_why_context(workout, plan, 1, "base")
        
        assert "Week 1" in result
        assert "Building foundation" in result
    
    def test_final_weeks_context(self):
        workout = MagicMock()
        workout.workout_type = "tempo"
        
        plan = MagicMock()
        plan.total_weeks = 12
        
        result = generate_why_context(workout, plan, 12, "taper")
        
        assert "Final push" in result


class TestGenerateYesterdayInsight:
    """Tests for yesterday's insight generation."""
    
    def test_efficiency_insight_positive(self):
        activity = MagicMock()
        activity.efficiency_score = 3.5
        activity.avg_hr = 145
        activity.distance_m = 10000
        activity.duration_s = 3600
        
        result = generate_yesterday_insight(activity)
        
        assert "Efficiency +3.5% vs baseline" in result
    
    def test_efficiency_insight_negative(self):
        activity = MagicMock()
        activity.efficiency_score = -2.1
        activity.avg_hr = 160
        activity.distance_m = 10000
        activity.duration_s = 3600
        
        result = generate_yesterday_insight(activity)
        
        assert "Efficiency -2.1% vs baseline" in result
    
    def test_low_hr_insight(self):
        activity = MagicMock()
        activity.efficiency_score = None
        activity.avg_hr = 135
        activity.distance_m = 10000
        activity.duration_s = 3600
        
        result = generate_yesterday_insight(activity)
        
        assert "HR stayed low" in result
        assert "135 avg" in result
    
    def test_high_hr_insight(self):
        activity = MagicMock()
        activity.efficiency_score = None
        activity.avg_hr = 170
        activity.distance_m = 10000
        activity.duration_s = 3600
        
        result = generate_yesterday_insight(activity)
        
        assert "HR ran high" in result
    
    def test_fallback_to_distance_pace(self):
        activity = MagicMock()
        activity.efficiency_score = None
        activity.avg_hr = 150  # Neither low nor high
        activity.distance_m = 8046.72  # 5 miles
        activity.duration_s = 2400  # 40 minutes
        
        # Mock hasattr to return False for optional fields
        activity.pace_variability = None
        
        result = generate_yesterday_insight(activity)
        
        assert "mi at" in result
        assert "/mi" in result
