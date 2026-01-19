"""
Unit tests for the Fitness Bank Framework (ADR-030, ADR-031).

Tests:
1. Fitness Bank calculation
2. Week theme generation
3. Workout prescription
4. Constraint-aware planning
"""

import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

from services.fitness_bank import (
    FitnessBank,
    FitnessBankCalculator,
    RacePerformance,
    ConstraintType,
    ExperienceLevel,
    calculate_vdot,
)
from services.week_theme_generator import (
    WeekTheme,
    WeekThemeGenerator,
    WeekThemePlan,
    ThemeConstraints,
)
from services.workout_prescription import (
    WorkoutPrescriptionGenerator,
    DayPlan,
    WeekPlan,
    calculate_paces_from_vdot,
)
from services.constraint_aware_planner import (
    ConstraintAwarePlanner,
    ConstraintAwarePlan,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def elite_fitness_bank():
    """Fixture for an elite athlete fitness bank."""
    return FitnessBank(
        athlete_id="test-athlete-123",
        peak_weekly_miles=71.0,
        peak_monthly_miles=276.0,
        peak_long_run_miles=22.0,
        peak_mp_long_run_miles=18.0,
        peak_threshold_miles=10.0,
        peak_ctl=100.0,
        race_performances=[
            RacePerformance(
                date=date(2025, 12, 13),
                distance="10k",
                distance_m=10000,
                finish_time_seconds=2350,  # 39:10
                pace_per_mile=6.30,
                vdot=53.2,
                conditions=None,
                confidence=1.0,
                name="10K PR"
            ),
            RacePerformance(
                date=date(2025, 11, 29),
                distance="half",
                distance_m=21097,
                finish_time_seconds=5260,  # 1:27:40
                pace_per_mile=6.65,
                vdot=52.9,
                conditions=None,
                confidence=1.0,
                name="Half Marathon"
            ),
        ],
        best_vdot=53.2,
        best_race=RacePerformance(
            date=date(2025, 12, 13),
            distance="10k",
            distance_m=10000,
            finish_time_seconds=2350,
            pace_per_mile=6.30,
            vdot=53.2,
            conditions=None,
            confidence=1.0,
        ),
        current_weekly_miles=16.0,
        current_ctl=30.0,
        current_atl=39.0,
        weeks_since_peak=8,
        current_long_run_miles=12.0,
        average_long_run_miles=14.6,
        tau1=25.0,
        tau2=18.0,
        experience_level=ExperienceLevel.ELITE,
        constraint_type=ConstraintType.INJURY,
        constraint_details="sharp volume drop",
        is_returning_from_break=True,
        typical_long_run_day=6,  # Sunday
        typical_quality_day=3,   # Thursday
        typical_rest_days=[0],   # Monday
        weeks_to_80pct_ctl=4,
        weeks_to_race_ready=3,
        sustainable_peak_weekly=66.0,
    )


@pytest.fixture
def intermediate_fitness_bank():
    """Fixture for an intermediate athlete fitness bank."""
    return FitnessBank(
        athlete_id="test-athlete-456",
        peak_weekly_miles=45.0,
        peak_monthly_miles=180.0,
        peak_long_run_miles=16.0,
        peak_mp_long_run_miles=8.0,
        peak_threshold_miles=6.0,
        peak_ctl=60.0,
        race_performances=[],
        best_vdot=45.0,
        best_race=None,
        current_weekly_miles=40.0,
        current_ctl=55.0,
        current_atl=50.0,
        weeks_since_peak=2,
        current_long_run_miles=14.0,
        average_long_run_miles=12.0,
        tau1=42.0,
        tau2=7.0,
        experience_level=ExperienceLevel.INTERMEDIATE,
        constraint_type=ConstraintType.NONE,
        constraint_details=None,
        is_returning_from_break=False,
        typical_long_run_day=6,
        typical_quality_day=3,
        typical_rest_days=[0],
        weeks_to_80pct_ctl=0,
        weeks_to_race_ready=0,
        sustainable_peak_weekly=40.0,
    )


# =============================================================================
# VDOT CALCULATION TESTS
# =============================================================================

class TestVDOTCalculation:
    """Tests for VDOT calculation."""
    
    def test_10k_vdot(self):
        """Test VDOT calculation for 10K race."""
        # 39:10 10K should be ~VDOT 53
        vdot = calculate_vdot(10000, 2350)
        assert 52 <= vdot <= 55
    
    def test_half_marathon_vdot(self):
        """Test VDOT calculation for half marathon."""
        # 1:30:00 half should be ~VDOT 50
        vdot = calculate_vdot(21097, 5400)
        assert 48 <= vdot <= 52
    
    def test_marathon_vdot(self):
        """Test VDOT calculation for marathon."""
        # 3:00:00 marathon should be ~VDOT 53
        vdot = calculate_vdot(42195, 10800)
        assert 51 <= vdot <= 55


class TestPaceCalculation:
    """Tests for pace zone calculation."""
    
    def test_paces_from_vdot_53(self):
        """Test pace calculation from VDOT 53."""
        paces = calculate_paces_from_vdot(53.0)
        
        # Easy should be ~7:45-8:15 (from lookup service)
        assert 7.7 <= paces["easy"] <= 8.3
        
        # Marathon should be ~6:30-7:00 (from lookup service)
        assert 6.5 <= paces["marathon"] <= 7.0
        
        # Threshold should be ~6:20-6:30
        assert 6.2 <= paces["threshold"] <= 6.6
    
    def test_paces_from_vdot_45(self):
        """Test pace calculation from VDOT 45."""
        paces = calculate_paces_from_vdot(45.0)
        
        # Easy should be slower than VDOT 53
        assert paces["easy"] > 8.3


# =============================================================================
# WEEK THEME GENERATOR TESTS
# =============================================================================

class TestWeekThemeGenerator:
    """Tests for week theme generation."""
    
    def test_theme_alternation(self, elite_fitness_bank):
        """Test that themes alternate properly."""
        generator = WeekThemeGenerator()
        race_date = date.today() + timedelta(weeks=12)
        
        themes = generator.generate(
            bank=elite_fitness_bank,
            race_date=race_date,
            race_distance="marathon"
        )
        
        # Check no consecutive same-emphasis (except rebuild)
        theme_values = [t.theme.value for t in themes]
        for i in range(1, len(theme_values)):
            if theme_values[i] in ('build_t', 'build_mp'):
                # Should not be same as previous build week
                if theme_values[i-1] in ('build_t', 'build_mp'):
                    assert theme_values[i] != theme_values[i-1]
    
    def test_race_week_at_end(self, elite_fitness_bank):
        """Test that race week is at the end."""
        generator = WeekThemeGenerator()
        race_date = date.today() + timedelta(weeks=10)
        
        themes = generator.generate(
            bank=elite_fitness_bank,
            race_date=race_date,
            race_distance="marathon"
        )
        
        assert themes[-1].theme == WeekTheme.RACE
    
    def test_injury_protection(self, elite_fitness_bank):
        """Test that injury returns get rebuild weeks."""
        generator = WeekThemeGenerator()
        race_date = date.today() + timedelta(weeks=12)
        
        themes = generator.generate(
            bank=elite_fitness_bank,
            race_date=race_date,
            race_distance="marathon"
        )
        
        # First week should be rebuild (injury return)
        assert themes[0].theme in (WeekTheme.REBUILD_EASY, WeekTheme.REBUILD_STRIDES)
    
    def test_tune_up_race_insertion(self, elite_fitness_bank):
        """Test that tune-up races are inserted."""
        generator = WeekThemeGenerator()
        race_date = date.today() + timedelta(weeks=10)
        tune_up_date = date.today() + timedelta(weeks=8)
        
        tune_up_races = [
            {"date": tune_up_date, "distance": "10_mile", "name": "Tune Up", "purpose": "threshold"}
        ]
        
        themes = generator.generate(
            bank=elite_fitness_bank,
            race_date=race_date,
            race_distance="marathon",
            tune_up_races=tune_up_races
        )
        
        theme_values = [t.theme.value for t in themes]
        assert "tune_up" in theme_values
    
    def test_volume_targets(self, elite_fitness_bank):
        """Test that volume targets are set correctly."""
        generator = WeekThemeGenerator()
        race_date = date.today() + timedelta(weeks=10)
        
        themes = generator.generate(
            bank=elite_fitness_bank,
            race_date=race_date,
            race_distance="marathon"
        )
        
        # Recovery week should have lower volume
        for theme in themes:
            if theme.theme == WeekTheme.RECOVERY:
                assert theme.target_volume_pct < 0.7
            elif theme.theme == WeekTheme.PEAK:
                assert theme.target_volume_pct >= 0.95


# =============================================================================
# WORKOUT PRESCRIPTION TESTS
# =============================================================================

class TestWorkoutPrescription:
    """Tests for specific workout prescription."""
    
    def test_threshold_workout_structure(self, elite_fitness_bank):
        """Test that threshold workouts have specific structure."""
        generator = WorkoutPrescriptionGenerator(elite_fitness_bank, race_distance="marathon")
        
        week = generator.generate_week(
            theme=WeekTheme.BUILD_T_EMPHASIS,
            week_number=5,
            total_weeks=12,
            target_miles=65.0,
            start_date=date.today()
        )
        
        # Find threshold workout
        threshold_workout = None
        for day in week.days:
            if day.workout_type == "threshold":
                threshold_workout = day
                break
        
        assert threshold_workout is not None
        # Should have specific structure like "2x4mi @ T"
        assert "@" in threshold_workout.description or "@ T" in threshold_workout.name
        # Should have pace
        assert "threshold" in threshold_workout.paces
    
    def test_mp_long_run_progression(self, elite_fitness_bank):
        """Test that MP long runs scale based on week."""
        generator = WorkoutPrescriptionGenerator(elite_fitness_bank, race_distance="marathon")
        
        # Early build week
        early_week = generator.generate_week(
            theme=WeekTheme.BUILD_MP_EMPHASIS,
            week_number=3,
            total_weeks=12,
            target_miles=55.0,
            start_date=date.today()
        )
        
        # Peak week
        peak_week = generator.generate_week(
            theme=WeekTheme.PEAK,
            week_number=10,
            total_weeks=12,
            target_miles=72.0,
            start_date=date.today() + timedelta(weeks=7)
        )
        
        # Find long runs
        early_long = None
        peak_long = None
        
        for day in early_week.days:
            if day.workout_type in ("long", "long_mp"):
                early_long = day
                break
        
        for day in peak_week.days:
            if day.workout_type in ("long", "long_mp"):
                peak_long = day
                break
        
        # Peak long run should be longer
        assert peak_long is not None
        assert early_long is not None
        assert peak_long.target_miles > early_long.target_miles
    
    def test_personal_paces(self, elite_fitness_bank):
        """Test that workouts use personal VDOT paces."""
        generator = WorkoutPrescriptionGenerator(elite_fitness_bank, race_distance="marathon")
        
        week = generator.generate_week(
            theme=WeekTheme.BUILD_T_EMPHASIS,
            week_number=5,
            total_weeks=12,
            target_miles=65.0,
            start_date=date.today()
        )
        
        # All workouts with paces should have values
        for day in week.days:
            if day.paces:
                for zone, pace in day.paces.items():
                    # Pace should be in format "M:SS"
                    assert ":" in pace


# =============================================================================
# CONSTRAINT-AWARE PLANNER TESTS
# =============================================================================

class TestConstraintAwarePlanner:
    """Tests for the constraint-aware orchestrator."""
    
    def test_injury_ramp_protection(self, elite_fitness_bank):
        """Test that injury returns have protected ramp."""
        # This would need DB mocking for full test
        # Here we test the constraint application logic
        constraints = ThemeConstraints(
            is_injury_return=True,
            injury_weeks=8,
            weeks_to_race=12,
            tune_up_races=[],
            tau1=25.0,
            experience=ExperienceLevel.ELITE,
            current_volume_pct=0.22  # 16/71
        )
        
        assert constraints.needs_rebuild is True
        assert constraints.recovery_frequency == 4  # Fast adapter
    
    def test_no_constraint_for_healthy(self, intermediate_fitness_bank):
        """Test that healthy athletes don't get unnecessary constraints."""
        constraints = ThemeConstraints(
            is_injury_return=False,
            injury_weeks=0,
            weeks_to_race=12,
            tune_up_races=[],
            tau1=42.0,
            experience=ExperienceLevel.INTERMEDIATE,
            current_volume_pct=0.89  # 40/45
        )
        
        assert constraints.needs_rebuild is False


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests for the full framework."""
    
    def test_full_plan_generation(self, elite_fitness_bank):
        """Test generating a full plan from fitness bank."""
        theme_generator = WeekThemeGenerator()
        race_date = date.today() + timedelta(weeks=10)
        
        # Generate themes
        themes = theme_generator.generate(
            bank=elite_fitness_bank,
            race_date=race_date,
            race_distance="marathon"
        )
        
        # Generate workouts for each theme
        workout_generator = WorkoutPrescriptionGenerator(elite_fitness_bank, race_distance="marathon")
        weeks = []
        
        for theme_plan in themes[:3]:  # Just test first 3 weeks
            target_miles = theme_plan.target_volume_pct * elite_fitness_bank.peak_weekly_miles
            
            week = workout_generator.generate_week(
                theme=theme_plan.theme,
                week_number=theme_plan.week_number,
                total_weeks=len(themes),
                target_miles=target_miles,
                start_date=theme_plan.start_date
            )
            weeks.append(week)
        
        # Validate
        assert len(weeks) == 3
        assert all(len(w.days) == 7 for w in weeks)
        assert all(w.total_miles > 0 for w in weeks)
    
    def test_tune_up_race_coordination(self, elite_fitness_bank):
        """Test that tune-up races are properly coordinated."""
        theme_generator = WeekThemeGenerator()
        race_date = date.today() + timedelta(weeks=10)
        tune_up_date = date.today() + timedelta(weeks=8)
        
        tune_up_races = [
            {"date": tune_up_date, "distance": "10_mile", "name": "10 Mile", "purpose": "threshold"}
        ]
        
        themes = theme_generator.generate(
            bank=elite_fitness_bank,
            race_date=race_date,
            race_distance="marathon",
            tune_up_races=tune_up_races
        )
        
        # Find tune-up week
        tune_up_week = None
        for theme in themes:
            if theme.theme == WeekTheme.TUNE_UP_RACE:
                tune_up_week = theme
                break
        
        assert tune_up_week is not None
        # Tune-up week should have reduced volume
        assert tune_up_week.target_volume_pct < 0.6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
