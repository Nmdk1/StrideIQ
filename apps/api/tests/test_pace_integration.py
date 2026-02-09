"""
Tests for Pace Calculator Integration

Tests the full data flow:
1. RPI calculation from race times
2. Training pace generation
3. Pace description formatting
4. Plan generation with paces
"""

import pytest
from datetime import date, timedelta
from uuid import uuid4

from services.plan_framework.pace_engine import PaceEngine, TrainingPaces
from services.plan_framework.generator import PlanGenerator


class TestPaceEngine:
    """Tests for the PaceEngine class."""
    
    def setup_method(self):
        self.engine = PaceEngine()
    
    def test_calculate_from_5k_race(self):
        """Test RPI calculation from a 5K race time."""
        # 20:00 5K = approximately RPI 50
        paces = self.engine.calculate_from_race(
            distance="5k",
            time_seconds=1200  # 20:00
        )
        
        assert paces is not None
        assert paces.rpi is not None
        assert 48 <= paces.rpi <= 52  # Reasonable range for 20min 5K
        assert paces.easy_pace_low > 0
        assert paces.threshold_pace > 0
        assert paces.marathon_pace > 0
    
    def test_calculate_from_marathon_race(self):
        """Test RPI calculation from a marathon time."""
        # 4:00:00 marathon
        paces = self.engine.calculate_from_race(
            distance="marathon",
            time_seconds=14400  # 4 hours
        )
        
        assert paces is not None
        assert paces.rpi is not None
        assert paces.marathon_pace > 0
    
    def test_calculate_from_half_marathon(self):
        """Test RPI calculation from half marathon."""
        # 1:45:00 half marathon
        paces = self.engine.calculate_from_race(
            distance="half_marathon",
            time_seconds=6300  # 1:45:00
        )
        
        assert paces is not None
        assert paces.rpi is not None
    
    def test_invalid_distance_returns_none(self):
        """Test that invalid distance returns None."""
        paces = self.engine.calculate_from_race(
            distance="invalid",
            time_seconds=1200
        )
        
        assert paces is None
    
    def test_invalid_time_returns_none(self):
        """Test that invalid time returns None."""
        paces = self.engine.calculate_from_race(
            distance="5k",
            time_seconds=0
        )
        
        assert paces is None


class TestTrainingPaces:
    """Tests for TrainingPaces pace descriptions."""
    
    def setup_method(self):
        # Create a sample TrainingPaces object (approximately 50 RPI)
        self.paces = TrainingPaces(
            rpi=50.0,
            race_distance="5k",
            race_time_seconds=1200,
            easy_pace_low=570,   # 9:30
            easy_pace_high=600,  # 10:00
            marathon_pace=495,   # 8:15
            threshold_pace=450,  # 7:30
            interval_pace=405,   # 6:45
            repetition_pace=360, # 6:00
            easy_pace_per_km_low=354,
            easy_pace_per_km_high=373,
            marathon_pace_per_km=308,
            threshold_pace_per_km=280,
            interval_pace_per_km=252,
            repetition_pace_per_km=224,
        )
    
    def test_easy_pace_description(self):
        """Test easy pace includes effort context."""
        desc = self.paces.get_pace_description("easy")
        assert "9:30" in desc
        assert "10:00" in desc
        assert "conversational" in desc.lower()
    
    def test_long_run_pace_description(self):
        """Test long run pace includes effort context."""
        desc = self.paces.get_pace_description("long")
        assert "9:30" in desc or "10:00" in desc
        assert "easy" in desc.lower() or "sustainable" in desc.lower()
    
    def test_marathon_pace_description(self):
        """Test marathon pace includes effort context."""
        desc = self.paces.get_pace_description("marathon_pace")
        assert "8:15" in desc
        assert "goal" in desc.lower() or "race" in desc.lower()
    
    def test_threshold_pace_description(self):
        """Test threshold pace includes effort context."""
        desc = self.paces.get_pace_description("threshold")
        assert "7:30" in desc
        assert "comfortably hard" in desc.lower()
    
    def test_interval_pace_description(self):
        """Test interval pace includes effort context."""
        desc = self.paces.get_pace_description("intervals")
        assert "6:45" in desc
        assert "hard" in desc.lower()
    
    def test_strides_pace_description(self):
        """Test strides pace includes effort context."""
        desc = self.paces.get_pace_description("strides")
        assert "6:00" in desc
        assert "quick" in desc.lower() or "controlled" in desc.lower()
    
    def test_unknown_workout_type(self):
        """Test unknown workout type returns default."""
        desc = self.paces.get_pace_description("unknown_type")
        assert "conversational" in desc.lower()


class TestPaceFormat:
    """Tests for pace formatting."""
    
    def test_format_pace_minutes_seconds(self):
        """Test pace formatting with minutes and seconds."""
        paces = TrainingPaces(
            rpi=50.0,
            race_distance="5k",
            race_time_seconds=1200,
            easy_pace_low=570,   # 9:30
            easy_pace_high=605,  # 10:05
            marathon_pace=495,
            threshold_pace=450,
            interval_pace=405,
            repetition_pace=360,
            easy_pace_per_km_low=354,
            easy_pace_per_km_high=376,
            marathon_pace_per_km=308,
            threshold_pace_per_km=280,
            interval_pace_per_km=252,
            repetition_pace_per_km=224,
        )
        
        formatted = paces._format_pace(570)
        assert formatted == "9:30"
        
        formatted = paces._format_pace(605)
        assert formatted == "10:05"
        
        formatted = paces._format_pace(360)
        assert formatted == "6:00"


class TestPlanGeneratorWithPaces:
    """Tests for plan generation with paces."""
    
    def test_semi_custom_with_race_time(self):
        """Test semi-custom plan generation with user-provided race time."""
        generator = PlanGenerator(db=None)
        
        plan = generator.generate_semi_custom(
            distance="marathon",
            duration_weeks=12,
            current_weekly_miles=40,
            days_per_week=6,
            race_date=date.today() + timedelta(weeks=12),
            recent_race_distance="5k",
            recent_race_time_seconds=1200,  # 20:00 5K
        )
        
        assert plan is not None
        assert plan.rpi is not None
        assert len(plan.workouts) > 0
        
        # Check that workouts have personalized paces
        easy_workouts = [w for w in plan.workouts if w.workout_type == "easy"]
        if easy_workouts:
            pace_desc = easy_workouts[0].pace_description
            # Should have actual pace, not just "conversational"
            assert "/" in pace_desc or ":" in pace_desc
    
    def test_standard_plan_no_paces(self):
        """Test standard plan has effort descriptions, not personalized paces."""
        generator = PlanGenerator(db=None)
        
        plan = generator.generate_standard(
            distance="marathon",
            duration_weeks=12,
            tier="mid",
            days_per_week=6,
            start_date=date.today()
        )
        
        assert plan is not None
        assert plan.rpi is None  # No RPI for standard plans
        assert len(plan.workouts) > 0
        
        # Check that workouts have effort descriptions
        easy_workouts = [w for w in plan.workouts if w.workout_type == "easy"]
        if easy_workouts:
            pace_desc = easy_workouts[0].pace_description
            # Should be effort-based
            assert "conversational" in pace_desc.lower() or "relaxed" in pace_desc.lower()
