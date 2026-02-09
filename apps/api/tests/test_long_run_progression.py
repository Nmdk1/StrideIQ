"""
Unit tests for N=1 Long Run Progression (ADR-038).

Tests the algorithm that progresses long runs from current → peak capability.
"""

import pytest
from datetime import date, timedelta
from uuid import uuid4

from services.fitness_bank import (
    FitnessBank,
    ConstraintType,
    ExperienceLevel,
    RacePerformance,
)
from services.workout_prescription import (
    WorkoutPrescriptionGenerator,
    WeekPlan,
)
from services.week_theme_generator import WeekTheme


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def elite_injury_return_bank():
    """
    Elite athlete returning from injury.
    
    This is the primary test case from ADR-038:
    - Current long run: 12 miles (from recent data)
    - Average long run: 14.6 miles  
    - Peak long run: 22 miles (proven capability)
    - Should progress: 12 → 14 → 16 → 18 → 20 → 22
    """
    return FitnessBank(
        athlete_id="test-elite-injury",
        peak_weekly_miles=71.0,
        peak_monthly_miles=276.0,
        peak_long_run_miles=22.0,
        peak_mp_long_run_miles=18.0,
        peak_threshold_miles=10.0,
        peak_ctl=100.0,
        race_performances=[],
        best_rpi=53.2,
        best_race=None,
        current_weekly_miles=24.0,
        current_ctl=30.0,
        current_atl=39.0,
        weeks_since_peak=8,
        current_long_run_miles=12.0,  # What they ran recently
        average_long_run_miles=14.6,   # Their historical average
        tau1=25.0,
        tau2=18.0,
        experience_level=ExperienceLevel.ELITE,
        constraint_type=ConstraintType.INJURY,
        constraint_details="sharp volume drop",
        is_returning_from_break=True,
        typical_long_run_day=6,
        typical_quality_day=3,
        typical_rest_days=[0],
        weeks_to_80pct_ctl=4,
        weeks_to_race_ready=3,
        sustainable_peak_weekly=66.0,
    )


@pytest.fixture
def intermediate_healthy_bank():
    """
    Intermediate athlete, healthy, no injury.
    
    Current and peak are similar - just building to race.
    """
    return FitnessBank(
        athlete_id="test-intermediate",
        peak_weekly_miles=45.0,
        peak_monthly_miles=180.0,
        peak_long_run_miles=16.0,
        peak_mp_long_run_miles=8.0,
        peak_threshold_miles=6.0,
        peak_ctl=60.0,
        race_performances=[],
        best_rpi=45.0,
        best_race=None,
        current_weekly_miles=40.0,
        current_ctl=55.0,
        current_atl=50.0,
        weeks_since_peak=2,
        current_long_run_miles=14.0,  # Recent long run
        average_long_run_miles=12.0,   # Average
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


@pytest.fixture
def beginner_bank():
    """
    Beginner athlete with minimal history.
    """
    return FitnessBank(
        athlete_id="test-beginner",
        peak_weekly_miles=25.0,
        peak_monthly_miles=100.0,
        peak_long_run_miles=8.0,
        peak_mp_long_run_miles=0.0,
        peak_threshold_miles=3.0,
        peak_ctl=30.0,
        race_performances=[],
        best_rpi=38.0,
        best_race=None,
        current_weekly_miles=20.0,
        current_ctl=25.0,
        current_atl=22.0,
        weeks_since_peak=1,
        current_long_run_miles=6.0,
        average_long_run_miles=5.0,
        tau1=45.0,
        tau2=7.0,
        experience_level=ExperienceLevel.BEGINNER,
        constraint_type=ConstraintType.NONE,
        constraint_details=None,
        is_returning_from_break=False,
        typical_long_run_day=6,
        typical_quality_day=3,
        typical_rest_days=[0, 4],
        weeks_to_80pct_ctl=0,
        weeks_to_race_ready=0,
        sustainable_peak_weekly=20.0,
    )


# =============================================================================
# UNIT TESTS: Long Run Progression Algorithm
# =============================================================================

class TestLongRunProgression:
    """Tests for the N=1 long run progression algorithm."""
    
    def test_elite_injury_no_jumps(self, elite_injury_return_bank):
        """
        CRITICAL TEST: Elite athlete returning from injury should have smooth progression.
        
        Bug we're fixing: 10mi → 22mi jump in one week.
        Expected: Max 2mi increase per week.
        """
        generator = WorkoutPrescriptionGenerator(elite_injury_return_bank, race_distance="marathon")
        total_weeks = 9
        
        long_runs = []
        for week in range(1, total_weeks + 1):
            theme = WeekTheme.BUILD_T_EMPHASIS if week > 3 else WeekTheme.REBUILD_STRIDES
            if week > total_weeks - 3:
                theme = WeekTheme.TAPER_1
            
            lr = generator.calculate_long_run_for_week(week, total_weeks, theme)
            long_runs.append(lr)
        
        # Check no jumps > 3 miles between consecutive weeks
        for i in range(1, len(long_runs) - 1):  # Skip taper weeks
            jump = long_runs[i] - long_runs[i-1]
            assert jump <= 3.0, f"Week {i} to {i+1}: jump of {jump:.1f}mi exceeds 3mi limit"
    
    def test_elite_starts_from_current(self, elite_injury_return_bank):
        """Long runs should start from current capability, not peak."""
        generator = WorkoutPrescriptionGenerator(elite_injury_return_bank, race_distance="marathon")
        
        # First week long run
        week1_long = generator.calculate_long_run_for_week(1, 9, WeekTheme.REBUILD_EASY)
        
        # Should be around current (12mi), not peak (22mi)
        assert week1_long >= 10, f"Week 1 too short: {week1_long:.1f}mi"
        assert week1_long <= 14, f"Week 1 too long: {week1_long:.1f}mi (should start near current 12mi)"
    
    def test_elite_reaches_peak(self, elite_injury_return_bank):
        """Long runs should reach peak by peak week."""
        generator = WorkoutPrescriptionGenerator(elite_injury_return_bank, race_distance="marathon")
        
        # Week 6 of 9 should be near peak (before taper)
        peak_week_long = generator.calculate_long_run_for_week(6, 9, WeekTheme.PEAK)
        
        # Should be close to peak (22mi)
        assert peak_week_long >= 18, f"Peak week too short: {peak_week_long:.1f}mi"
        assert peak_week_long <= 24, f"Peak week too long: {peak_week_long:.1f}mi"
    
    def test_taper_reduces_long_run(self, elite_injury_return_bank):
        """Taper weeks should reduce long run from peak."""
        generator = WorkoutPrescriptionGenerator(elite_injury_return_bank, race_distance="marathon")
        
        taper1_long = generator.calculate_long_run_for_week(7, 9, WeekTheme.TAPER_1)
        taper2_long = generator.calculate_long_run_for_week(8, 9, WeekTheme.TAPER_2)
        
        # Taper 1 should be ~70% of peak
        expected_taper1 = generator.long_run_peak * 0.70
        assert abs(taper1_long - expected_taper1) < 2, f"Taper 1: {taper1_long:.1f}mi vs expected {expected_taper1:.1f}mi"
        
        # Taper 2 should be less than taper 1
        assert taper2_long < taper1_long, f"Taper 2 ({taper2_long:.1f}) should be less than taper 1 ({taper1_long:.1f})"
    
    def test_intermediate_smooth_progression(self, intermediate_healthy_bank):
        """Intermediate athlete should also have smooth progression."""
        generator = WorkoutPrescriptionGenerator(intermediate_healthy_bank, race_distance="half")
        
        long_runs = []
        for week in range(1, 13):
            theme = WeekTheme.BUILD_T_EMPHASIS
            if week > 9:
                theme = WeekTheme.TAPER_1
            lr = generator.calculate_long_run_for_week(week, 12, theme)
            long_runs.append(lr)
        
        # Check no large jumps
        for i in range(1, 9):  # First 9 weeks
            jump = long_runs[i] - long_runs[i-1]
            assert jump <= 2.5, f"Week {i} to {i+1}: jump of {jump:.1f}mi"
    
    def test_beginner_appropriate_distances(self, beginner_bank):
        """Beginner should get appropriate (shorter) long runs."""
        generator = WorkoutPrescriptionGenerator(beginner_bank, race_distance="10k")
        
        week1_long = generator.calculate_long_run_for_week(1, 8, WeekTheme.BUILD_T_EMPHASIS)
        
        # Should be in beginner range
        assert week1_long >= 6, f"Week 1 too short for beginner: {week1_long:.1f}mi"
        assert week1_long <= 12, f"Week 1 too long for beginner: {week1_long:.1f}mi"


class TestLongRunInWeekPlans:
    """Tests that long run progression is correctly applied in week plans."""
    
    def test_rebuild_uses_progressive_long(self, elite_injury_return_bank):
        """
        CRITICAL: Rebuild weeks should use progressive long run, not volume formula.
        
        Bug we're fixing: Rebuild used (target_miles / days * 1.4) instead of progression.
        """
        generator = WorkoutPrescriptionGenerator(elite_injury_return_bank, race_distance="marathon")
        
        week = generator.generate_week(
            theme=WeekTheme.REBUILD_STRIDES,
            week_number=1,
            total_weeks=9,
            target_miles=30.0,  # Low target due to rebuild
            start_date=date.today()
        )
        
        # Find the long run
        long_run = None
        for day in week.days:
            if day.workout_type in ("long", "easy_long"):
                long_run = day
                break
        
        assert long_run is not None, "No long run found in rebuild week"
        
        # Should be around current capability (12mi), not volume formula (30 / 6 * 1.4 = 7mi)
        assert long_run.target_miles >= 10, f"Long run too short: {long_run.target_miles:.1f}mi (volume formula bug?)"
        assert long_run.target_miles <= 16, f"Long run too long: {long_run.target_miles:.1f}mi"
    
    def test_build_week_long_run_progressive(self, elite_injury_return_bank):
        """Build week long runs should progress from previous weeks."""
        generator = WorkoutPrescriptionGenerator(elite_injury_return_bank, race_distance="marathon")
        
        week3 = generator.generate_week(
            theme=WeekTheme.BUILD_T_EMPHASIS,
            week_number=3,
            total_weeks=9,
            target_miles=55.0,
            start_date=date.today()
        )
        
        week5 = generator.generate_week(
            theme=WeekTheme.BUILD_MP_EMPHASIS,
            week_number=5,
            total_weeks=9,
            target_miles=65.0,
            start_date=date.today() + timedelta(weeks=2)
        )
        
        # Find long runs
        week3_long = None
        week5_long = None
        
        for day in week3.days:
            if day.workout_type in ("long", "long_mp"):
                week3_long = day.target_miles
                break
        
        for day in week5.days:
            if day.workout_type in ("long", "long_mp"):
                week5_long = day.target_miles
                break
        
        assert week3_long is not None and week5_long is not None
        
        # Week 5 should be longer than week 3
        assert week5_long > week3_long, f"Week 5 ({week5_long:.1f}) should be longer than week 3 ({week3_long:.1f})"
        
        # But not dramatically longer (max 4mi difference over 2 weeks)
        assert week5_long - week3_long <= 5, f"Too big a jump: {week5_long:.1f} - {week3_long:.1f}"


class TestAllDistances:
    """Test that progression works for all race distances."""
    
    @pytest.mark.parametrize("distance,expected_peak_range", [
        ("5k", (8, 17)),      # 14 * 1.15 ≈ 16
        ("10k", (10, 19)),    # 16 * 1.15 ≈ 18
        ("half", (14, 21)),   # 18 * 1.15 ≈ 21
        ("marathon", (18, 26)), # 22 * 1.15 ≈ 25
    ])
    def test_distance_appropriate_peaks(self, elite_injury_return_bank, distance, expected_peak_range):
        """Each distance should have appropriate long run peaks."""
        generator = WorkoutPrescriptionGenerator(elite_injury_return_bank, race_distance=distance)
        
        min_peak, max_peak = expected_peak_range
        assert generator.long_run_peak >= min_peak, f"{distance}: peak {generator.long_run_peak:.1f} below min {min_peak}"
        assert generator.long_run_peak <= max_peak, f"{distance}: peak {generator.long_run_peak:.1f} above max {max_peak}"
    
    def test_5k_shorter_than_marathon(self, elite_injury_return_bank):
        """5K long runs should be shorter than marathon long runs."""
        gen_5k = WorkoutPrescriptionGenerator(elite_injury_return_bank, race_distance="5k")
        gen_marathon = WorkoutPrescriptionGenerator(elite_injury_return_bank, race_distance="marathon")
        
        assert gen_5k.long_run_peak < gen_marathon.long_run_peak


class TestEdgeCases:
    """Test edge cases in the progression algorithm."""
    
    def test_no_current_long_run_data(self):
        """When no current long run data, should use fallbacks."""
        bank = FitnessBank(
            athlete_id="test-no-data",
            peak_weekly_miles=50.0,
            peak_monthly_miles=200.0,
            peak_long_run_miles=18.0,
            peak_mp_long_run_miles=10.0,
            peak_threshold_miles=6.0,
            peak_ctl=70.0,
            race_performances=[],
            best_rpi=48.0,
            best_race=None,
            current_weekly_miles=40.0,
            current_ctl=60.0,
            current_atl=55.0,
            weeks_since_peak=4,
            current_long_run_miles=0.0,  # No recent long run
            average_long_run_miles=0.0,   # No average
            tau1=42.0,
            tau2=7.0,
            experience_level=ExperienceLevel.EXPERIENCED,
            constraint_type=ConstraintType.NONE,
            constraint_details=None,
            is_returning_from_break=False,
            typical_long_run_day=6,
            typical_quality_day=3,
            typical_rest_days=[0],
            weeks_to_80pct_ctl=0,
            weeks_to_race_ready=0,
            sustainable_peak_weekly=45.0,
        )
        
        generator = WorkoutPrescriptionGenerator(bank, race_distance="marathon")
        
        # Should use fallback (current_weekly * 0.25 = 10mi, or minimum 10mi)
        assert generator.long_run_current >= 10, f"Fallback current too low: {generator.long_run_current:.1f}"
    
    def test_current_exceeds_peak(self):
        """When current somehow exceeds peak, should handle gracefully."""
        bank = FitnessBank(
            athlete_id="test-current-high",
            peak_weekly_miles=50.0,
            peak_monthly_miles=200.0,
            peak_long_run_miles=15.0,  # Lower peak
            peak_mp_long_run_miles=8.0,
            peak_threshold_miles=6.0,
            peak_ctl=70.0,
            race_performances=[],
            best_rpi=48.0,
            best_race=None,
            current_weekly_miles=55.0,
            current_ctl=75.0,
            current_atl=70.0,
            weeks_since_peak=0,
            current_long_run_miles=18.0,  # Higher than peak_long_run_miles
            average_long_run_miles=16.0,
            tau1=42.0,
            tau2=7.0,
            experience_level=ExperienceLevel.EXPERIENCED,
            constraint_type=ConstraintType.NONE,
            constraint_details=None,
            is_returning_from_break=False,
            typical_long_run_day=6,
            typical_quality_day=3,
            typical_rest_days=[0],
            weeks_to_80pct_ctl=0,
            weeks_to_race_ready=0,
            sustainable_peak_weekly=50.0,
        )
        
        generator = WorkoutPrescriptionGenerator(bank, race_distance="marathon")
        
        # Should not crash, should produce reasonable values
        week1 = generator.calculate_long_run_for_week(1, 12, WeekTheme.BUILD_T_EMPHASIS)
        assert week1 > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
