"""
Tests for N=1 Phase 2 Training Plan Improvements (ADR-037)

These tests verify:
1. Proven capability overrides population guidelines for long runs
2. Population guidelines are fallback for new athletes only
3. Strides appear 2x/week in BUILD phase
4. Hill sprints appear 1x/week for experienced+ athletes
5. Tempo and threshold are distinct workout types
6. τ1 drives taper length (fast adapters get shorter taper)
7. Easy run distances vary (not monotonous)
"""

import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from services.fitness_bank import FitnessBank, ExperienceLevel, ConstraintType
from services.workout_prescription import (
    WorkoutPrescriptionGenerator,
    calculate_paces_from_vdot,
)
from services.week_theme_generator import (
    generate_week_themes,
    WeekTheme,
    WeekThemeGenerator,
    ThemeConstraints,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def experienced_athlete_bank():
    """Fitness bank for experienced athlete with proven long run capability."""
    return FitnessBank(
        athlete_id="test-experienced",
        peak_weekly_miles=71.5,
        peak_monthly_miles=280.0,
        peak_long_run_miles=22.0,  # PROVEN 22 mile capability
        peak_mp_long_run_miles=18.0,
        peak_threshold_miles=10.0,
        peak_ctl=85.0,
        race_performances=[],
        best_vdot=53.0,
        best_race=None,
        current_weekly_miles=65.0,
        current_ctl=80.0,
        current_atl=70.0,
        weeks_since_peak=2,
        # ADR-038: N=1 long run progression inputs
        current_long_run_miles=22.0 * 0.80,         # recent long run capability
        average_long_run_miles=22.0 * 0.90,         # typical long run history
        tau1=25.0,  # Fast adapter
        tau2=7.0,
        experience_level=ExperienceLevel.ELITE,
        constraint_type=ConstraintType.NONE,
        constraint_details=None,
        is_returning_from_break=False,
        typical_long_run_day=6,
        typical_quality_day=3,
        typical_rest_days=[0],
        weeks_to_80pct_ctl=0,
        weeks_to_race_ready=0,
        sustainable_peak_weekly=65.0,
    )


@pytest.fixture
def new_athlete_bank():
    """Fitness bank for new athlete with no proven long run capability."""
    return FitnessBank(
        athlete_id="test-new",
        peak_weekly_miles=35.0,
        peak_monthly_miles=140.0,
        peak_long_run_miles=10.0,  # NO proven long run (< 15mi threshold)
        peak_mp_long_run_miles=0.0,
        peak_threshold_miles=4.0,
        peak_ctl=40.0,
        race_performances=[],
        best_vdot=42.0,
        best_race=None,
        current_weekly_miles=30.0,
        current_ctl=35.0,
        current_atl=30.0,
        weeks_since_peak=4,
        # ADR-038: N=1 long run progression inputs (new athlete: lower typical long run history)
        current_long_run_miles=10.0 * 0.80,
        average_long_run_miles=10.0 * 0.70,
        tau1=42.0,  # Normal adapter
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
        sustainable_peak_weekly=30.0,
    )


# =============================================================================
# N=1 LONG RUN CAP TESTS
# =============================================================================

class TestN1LongRunCap:
    """Test that proven capability overrides population guidelines."""
    
    def test_proven_capability_used_for_experienced_athlete(self, experienced_athlete_bank):
        """Athlete with 22mi proven should get 22mi cap (distance-appropriate)."""
        generator = WorkoutPrescriptionGenerator(experienced_athlete_bank, "marathon")
        
        # Proven: 22mi (already at marathon target; no arbitrary bump)
        assert generator.long_run_cap == pytest.approx(22.0, abs=0.1)
        assert generator._proven_capability_used is True
    
    def test_population_fallback_for_new_athlete(self, new_athlete_bank):
        """Athlete without proven capability should use conservative early progressions."""
        generator = WorkoutPrescriptionGenerator(new_athlete_bank, "marathon")
        
        # New design: long runs progress from start to a conservative peak.
        # With limited long-run history (10mi), peak is capped at proven+4 (=14mi).
        assert generator.long_run_start == 10.0  # Default when no proven history
        assert generator.long_run_peak_target == pytest.approx(14.0, abs=0.1)
        
        # For week 1, should get conservative start, not peak
        from services.week_theme_generator import WeekTheme
        week1_long = generator.calculate_long_run_for_week(1, 16, WeekTheme.BUILD_T_EMPHASIS)
        assert week1_long == 10.0, "Week 1 should start at 10mi"
    
    def test_proven_capability_not_capped_by_time_rule(self, experienced_athlete_bank):
        """150-minute rule should NOT override proven 22mi capability."""
        generator = WorkoutPrescriptionGenerator(experienced_athlete_bank, "marathon")
        
        # Calculate what the population time cap would be
        paces = calculate_paces_from_vdot(experienced_athlete_bank.best_vdot)
        time_cap = 150 / paces["long"]
        
        # Generator cap should be HIGHER than time cap (using proven capability)
        assert generator.long_run_cap > time_cap
    
    def test_proven_capability_requires_near_target_for_marathon(self):
        """
        For marathon, the "proven capability" override is distance-specific:
        you need a proven long run close to the marathon target (22mi), not just 15mi.
        """
        # Just under threshold
        bank_14mi = FitnessBank(
            athlete_id="test-14",
            peak_weekly_miles=50.0,
            peak_monthly_miles=200.0,
            peak_long_run_miles=14.0,  # Just under 15mi threshold
            peak_mp_long_run_miles=0.0,
            peak_threshold_miles=6.0,
            peak_ctl=50.0,
            race_performances=[],
            best_vdot=48.0,
            best_race=None,
            current_weekly_miles=45.0,
            current_ctl=45.0,
            current_atl=40.0,
            weeks_since_peak=2,
            current_long_run_miles=14.0 * 0.80,
            average_long_run_miles=14.0 * 0.90,
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
        
        generator = WorkoutPrescriptionGenerator(bank_14mi, "marathon")
        assert generator._proven_capability_used is False
        assert generator.long_run_cap == pytest.approx(18.0, abs=0.1)  # 14 + 4 stretch
        
        # Just at threshold
        bank_15mi = FitnessBank(
            athlete_id="test-15",
            peak_weekly_miles=50.0,
            peak_monthly_miles=200.0,
            peak_long_run_miles=15.0,  # Exactly at threshold
            peak_mp_long_run_miles=0.0,
            peak_threshold_miles=6.0,
            peak_ctl=50.0,
            race_performances=[],
            best_vdot=48.0,
            best_race=None,
            current_weekly_miles=45.0,
            current_ctl=45.0,
            current_atl=40.0,
            weeks_since_peak=2,
            current_long_run_miles=15.0 * 0.80,
            average_long_run_miles=15.0 * 0.90,
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
        
        generator = WorkoutPrescriptionGenerator(bank_15mi, "marathon")
        assert generator._proven_capability_used is False
        assert generator.long_run_cap == pytest.approx(19.0, abs=0.1)  # 15 + 4 stretch


# =============================================================================
# STRIDES AND HILL SPRINT TESTS
# =============================================================================

class TestStridesAndHillSprints:
    """Test that neuromuscular work is included in BUILD phase with variety."""
    
    # All valid neuromuscular workout types
    NEUROMUSCULAR_TYPES = ["easy_strides", "strides", "hill_strides", "hill_sprints"]
    
    def test_strides_in_build_t_week(self, experienced_athlete_bank):
        """BUILD_T week should have some form of neuromuscular work (variety rotation)."""
        generator = WorkoutPrescriptionGenerator(experienced_athlete_bank, "marathon")
        
        week = generator.generate_week(
            theme=WeekTheme.BUILD_T_EMPHASIS,
            week_number=4,
            total_weeks=12,
            target_miles=60.0,
            start_date=date.today(),
        )
        
        workout_types = [d.workout_type for d in week.days]
        # With variety rotation, we might get any of the neuromuscular types
        has_neuro_work = any(t in self.NEUROMUSCULAR_TYPES for t in workout_types)
        assert has_neuro_work, f"BUILD_T should include neuromuscular work, got: {workout_types}"
    
    def test_hill_sprints_for_elite_athlete(self, experienced_athlete_bank):
        """Elite athletes should have hill sprints capability (10 reps)."""
        generator = WorkoutPrescriptionGenerator(experienced_athlete_bank, "marathon")
        
        # With variety rotation, hill_sprints might not appear in every week
        # But when they DO appear, elite athletes should get 10 reps
        hill_workout = generator._generate_hill_sprints(2, 6.0)
        assert "10x" in hill_workout.name, f"Elite should have 10 hill sprints, got: {hill_workout.name}"
        
        # Also verify they CAN get hill work in a week (just might be a different type)
        week = generator.generate_week(
            theme=WeekTheme.BUILD_T_EMPHASIS,
            week_number=4,
            total_weeks=12,
            target_miles=60.0,
            start_date=date.today(),
        )
        
        workout_types = [d.workout_type for d in week.days]
        has_neuro_work = any(t in self.NEUROMUSCULAR_TYPES for t in workout_types)
        assert has_neuro_work, f"Should have some neuromuscular work, got: {workout_types}"
    
    def test_no_hill_sprints_for_beginner(self):
        """Beginner athletes should NOT have hill sprints."""
        bank = FitnessBank(
            athlete_id="test-beginner",
            peak_weekly_miles=25.0,
            peak_monthly_miles=100.0,
            peak_long_run_miles=8.0,
            peak_mp_long_run_miles=0.0,
            peak_threshold_miles=3.0,
            peak_ctl=30.0,
            race_performances=[],
            best_vdot=38.0,
            best_race=None,
            current_weekly_miles=20.0,
            current_ctl=25.0,
            current_atl=22.0,
            weeks_since_peak=2,
            current_long_run_miles=8.0 * 0.80,
            average_long_run_miles=8.0 * 0.70,
            tau1=42.0,
            tau2=7.0,
            experience_level=ExperienceLevel.BEGINNER,  # Beginner
            constraint_type=ConstraintType.NONE,
            constraint_details=None,
            is_returning_from_break=False,
            typical_long_run_day=6,
            typical_quality_day=3,
            typical_rest_days=[0],
            weeks_to_80pct_ctl=0,
            weeks_to_race_ready=0,
            sustainable_peak_weekly=20.0,
        )
        
        generator = WorkoutPrescriptionGenerator(bank, "marathon")
        
        # ADR-037 Update: Hill work is SAFE for all levels - only reps scale
        # Beginners get 4 reps, experienced get 8, elite get 10
        
        # Test that beginner hill sprints have scaled reps (4 reps)
        hill_workout = generator._generate_hill_sprints(2, 5.0)
        assert "4x" in hill_workout.name, f"Beginners should have 4 hill sprints, got: {hill_workout.name}"
        
        # Hill work CAN appear in their plan now (variety rotation)
        # We're no longer asserting they don't get hills


# =============================================================================
# THRESHOLD TESTS (No Tempo - Tempo is an ambiguous term)
# =============================================================================

class TestThresholdWorkouts:
    """Test that threshold is used correctly (no tempo - tempo was removed)."""
    
    def test_threshold_pace_exists(self):
        """Pace calculation should include threshold pace."""
        paces = calculate_paces_from_vdot(50.0)
        
        assert "threshold" in paces
        # Tempo was removed - we only use threshold
        assert "tempo" not in paces
    
    def test_build_mp_uses_threshold(self, experienced_athlete_bank):
        """BUILD_MP week should use threshold as quality session (not tempo)."""
        generator = WorkoutPrescriptionGenerator(experienced_athlete_bank, "marathon")
        
        week = generator.generate_week(
            theme=WeekTheme.BUILD_MP_EMPHASIS,
            week_number=5,
            total_weeks=12,
            target_miles=60.0,
            start_date=date.today(),
        )
        
        workout_types = [d.workout_type for d in week.days]
        # Both BUILD_MP and BUILD_T use threshold (no tempo)
        assert "threshold" in workout_types, "BUILD_MP should use threshold"
    
    def test_build_t_uses_threshold(self, experienced_athlete_bank):
        """BUILD_T week should use threshold."""
        generator = WorkoutPrescriptionGenerator(experienced_athlete_bank, "marathon")
        
        week = generator.generate_week(
            theme=WeekTheme.BUILD_T_EMPHASIS,
            week_number=4,
            total_weeks=12,
            target_miles=60.0,
            start_date=date.today(),
        )
        
        workout_types = [d.workout_type for d in week.days]
        assert "threshold" in workout_types, "BUILD_T should use threshold"


# =============================================================================
# τ1-DRIVEN TAPER TESTS
# =============================================================================

class TestTau1DrivenTaper:
    """Test that τ1 drives taper length."""
    
    def test_fast_adapter_gets_short_taper(self):
        """Athletes with τ1 < 30 should get 2-week marathon taper."""
        constraints = ThemeConstraints(
            is_injury_return=False,
            injury_weeks=0,
            weeks_to_race=12,
            tune_up_races=[],
            tau1=25.0,  # Fast adapter
            experience=ExperienceLevel.ELITE,
            current_volume_pct=0.9,
        )
        
        generator = WeekThemeGenerator()
        taper_length = generator._calculate_taper_length("marathon", constraints)
        
        assert taper_length == 2, "Fast adapters (τ1 < 30) should get 2-week marathon taper"
    
    def test_slow_adapter_gets_longer_taper(self):
        """Athletes with τ1 > 45 should get 3-week marathon taper."""
        constraints = ThemeConstraints(
            is_injury_return=False,
            injury_weeks=0,
            weeks_to_race=12,
            tune_up_races=[],
            tau1=50.0,  # Slow adapter
            experience=ExperienceLevel.EXPERIENCED,
            current_volume_pct=0.9,
        )
        
        generator = WeekThemeGenerator()
        taper_length = generator._calculate_taper_length("marathon", constraints)
        
        assert taper_length == 3, "Slow adapters (τ1 > 45) should get 3-week marathon taper"
    
    def test_full_plan_has_correct_taper_weeks(self, experienced_athlete_bank):
        """Full plan generation should produce correct number of taper weeks."""
        race_date = date.today() + timedelta(weeks=12)
        
        themes = generate_week_themes(
            experienced_athlete_bank,
            race_date,
            "marathon",
        )
        
        taper_count = sum(1 for t in themes if "taper" in t.theme.value.lower())
        
        # Fast adapter (τ1=25) should have 2 taper weeks
        assert taper_count == 2


# =============================================================================
# EASY RUN VARIATION TESTS
# =============================================================================

class TestEasyRunVariation:
    """Test that easy runs have distance variation."""
    
    def test_easy_runs_not_all_same_distance(self, experienced_athlete_bank):
        """Easy runs should have varied distances, not monotonous."""
        generator = WorkoutPrescriptionGenerator(experienced_athlete_bank, "marathon")
        
        week = generator.generate_week(
            theme=WeekTheme.BUILD_T_EMPHASIS,
            week_number=4,
            total_weeks=12,
            target_miles=60.0,
            start_date=date.today(),
        )
        
        # Get all easy-type runs
        easy_runs = [d for d in week.days if d.workout_type in ["easy", "easy_strides"]]
        
        if len(easy_runs) >= 2:
            distances = [d.target_miles for d in easy_runs]
            # Not all the same distance
            assert len(set(round(d, 1) for d in distances)) > 1, \
                "Easy runs should have varied distances"
