"""
Distance-Specific Plan Verification Tests (ADR-036)

Tests guardrails (NOT rules) for each distance:
- Long run caps are respected
- Appropriate quality focus by distance
- Taper exists and is τ1-informed
- No absurd combinations (5K with 20mi long runs)
"""

import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from services.fitness_bank import FitnessBank, ExperienceLevel, ConstraintType
from services.workout_prescription import WorkoutPrescriptionGenerator
from services.week_theme_generator import WeekThemeGenerator, WeekTheme


class TestN1LongRunLogic:
    """Test that long run caps follow N=1 principles, not arbitrary rules."""
    
    def _create_bank(self, 
                     rpi: float = 50,
                     experience: ExperienceLevel = ExperienceLevel.EXPERIENCED,
                     peak_weekly: float = 50,
                     peak_long: float = 18,
                     tau1: float = 42) -> FitnessBank:
        """Create a FitnessBank for testing."""
        bank = MagicMock(spec=FitnessBank)
        bank.best_rpi = rpi
        bank.experience_level = experience
        bank.peak_weekly_miles = peak_weekly
        bank.peak_long_run_miles = peak_long
        bank.peak_mp_long_run_miles = 14
        bank.current_weekly_miles = peak_weekly * 0.8
        # ADR-038: N=1 long run progression fields
        bank.current_long_run_miles = peak_long * 0.8
        bank.average_long_run_miles = peak_long * 0.9
        bank.tau1 = tau1
        bank.tau2 = 15
        bank.typical_long_run_day = 6
        bank.typical_quality_day = 3
        bank.typical_rest_days = [0]
        bank.constraint_type = ConstraintType.NONE
        bank.weeks_since_peak = 0
        return bank
    
    # =========================================================================
    # N=1 LONG RUN TESTS - Volume, Time, Proven capability drive the cap
    # =========================================================================
    
    def test_high_volume_runner_gets_appropriate_long_run_any_distance(self):
        """A 70mpw runner should get substantial long runs regardless of race distance."""
        # 70mpw * 0.30 = 21mi volume cap
        # Long-run targets are distance-specific; 5K is intentionally capped (~14-16mi range).
        bank = self._create_bank(peak_weekly=70, peak_long=18)
        
        for distance in ["5k", "10k", "half_marathon", "marathon"]:
            gen = WorkoutPrescriptionGenerator(bank, race_distance=distance)
            # Not artificially capped at 12mi for 5K
            if distance == "5k":
                # 5K peak target is 14mi with a 15% stretch cap => 16.1 max.
                assert gen.long_run_cap >= 16.0, \
                    f"70mpw runner should get 16+mi long run for {distance}, got {gen.long_run_cap}"
            else:
                assert gen.long_run_cap >= 17.0, \
                    f"High-volume runner should get 17+mi long run for {distance}, got {gen.long_run_cap}"
    
    def test_low_volume_runner_gets_progressive_long_runs(self):
        """A 25mpw runner should start conservatively but progress to race-appropriate distances."""
        # New design: We don't cap at static percentage, we progress from start to peak
        bank = self._create_bank(peak_weekly=25, peak_long=10)
        gen = WorkoutPrescriptionGenerator(bank, race_distance="marathon")
        
        # Start should be conservative (10mi proven or 10mi default)
        assert gen.long_run_start == 10, f"Start should be 10mi, got {gen.long_run_start}"
        
        # Peak is stretched conservatively from proven history (+4mi max when not near target)
        assert gen.long_run_peak_target == pytest.approx(14.0, abs=0.1), \
            f"Target should be proven+4 (=14mi), got {gen.long_run_peak_target}"
        
        # Week 1 should be at the start point
        from services.week_theme_generator import WeekTheme
        week1 = gen.calculate_long_run_for_week(1, 16, WeekTheme.BUILD_T_EMPHASIS)
        assert week1 == 10, f"Week 1 should be 10mi, got {week1}"
    
    def test_low_proven_uses_population_fallback(self):
        """
        Athletes with low proven capability (< 15mi) should use population fallback.
        
        N=1 Philosophy (ADR-037):
        - Proven capability >= 15mi: athlete data overrides population rules
        - Proven capability < 15mi: population rules apply (athlete hasn't proven long runs)
        
        An athlete with only 12mi proven but 70 mpw has the endurance base to 
        safely do longer runs. Population guidelines help them progress.
        """
        bank = self._create_bank(peak_weekly=70, peak_long=12)
        gen = WorkoutPrescriptionGenerator(bank, race_distance="marathon")
        
        # With 12mi proven (< 15mi threshold), population fallback is used
        # Population cap = min(70 * 0.30, 150 / ~8.5) ≈ min(21, 17.6) = 17.6
        assert gen._proven_capability_used is False, "Low proven should use population fallback"
        assert gen.long_run_cap > 14, f"Population fallback should allow > 14mi, got {gen.long_run_cap}"
    
    def test_high_proven_uses_proven_cap(self):
        """
        Athletes with high proven capability (>= 15mi) use their proven data.
        
        This is the N=1 core: athlete history IS the answer.
        """
        bank = self._create_bank(peak_weekly=70, peak_long=20)
        gen = WorkoutPrescriptionGenerator(bank, race_distance="marathon")
        
        # With 20mi proven (close to marathon target), proven capability is used.
        assert gen._proven_capability_used is True, "High proven should use proven capability"
        assert gen.long_run_cap == pytest.approx(20.0, abs=0.1), \
            f"Proven 20mi should give ~20mi cap (no arbitrary bump), got {gen.long_run_cap}"
    
    def test_slow_runner_with_proven_capability_not_time_limited(self):
        """
        Slow runners with proven capability should NOT be time-limited.
        
        N=1 Philosophy (ADR-037):
        The 150-minute rule is a population guideline for athletes WITHOUT proven
        long run capability. If an athlete has PROVEN they can do 20mi runs,
        their data overrides the time constraint.
        """
        # Slow runner (rpi=35) but with proven 20mi capability
        bank = self._create_bank(peak_weekly=60, peak_long=20, rpi=35)
        gen = WorkoutPrescriptionGenerator(bank, race_distance="marathon")
        
        # Proven capability (20mi >= 15mi threshold) overrides time constraint
        # Cap should follow proven capability (not time-limited)
        assert gen._proven_capability_used is True
        assert gen.long_run_cap == pytest.approx(20.0, abs=0.1), \
            f"Proven 20mi should give ~20mi cap, not time-limited. Got {gen.long_run_cap}"
    
    def test_slow_runner_without_proven_starts_conservative(self):
        """
        Slow runners WITHOUT proven capability should start conservatively.
        
        The time limit is applied during weekly progression, not as a static cap.
        """
        # Slow runner (rpi=35) with only 12mi proven (< 15mi threshold)
        bank = self._create_bank(peak_weekly=60, peak_long=12, rpi=35)
        gen = WorkoutPrescriptionGenerator(bank, race_distance="marathon")
        
        # Start should be conservative and based on *recent* long run capability.
        # With ADR-038 fields, current_long_run_miles is ~80% of peak (9.6mi), but marathon has a 10mi minimum.
        assert gen.long_run_start == pytest.approx(10.0, abs=0.1), \
            f"Start should respect the 10mi minimum, got {gen.long_run_start}"
        
        # Time limit is applied during progression (in calculate_long_run_for_week)
        # For slow runner (rpi=35, ~11min/mi), time limit = 180/11 ≈ 16.4mi
        from services.week_theme_generator import WeekTheme
        week6 = gen.calculate_long_run_for_week(6, 16, WeekTheme.BUILD_T_EMPHASIS)
        assert week6 <= 20, f"Week 6 should be time-limited during build, got {week6}"
    
    def test_different_race_distances_have_appropriate_targets(self):
        """Different race distances have different peak long run targets."""
        bank = self._create_bank(peak_weekly=60, peak_long=18)
        
        gen_5k = WorkoutPrescriptionGenerator(bank, race_distance="5k")
        gen_marathon = WorkoutPrescriptionGenerator(bank, race_distance="marathon")
        
        # 5K doesn't need 22mi long runs, marathon does.
        # 5K peak target is 14mi, but can stretch up to +15% when athlete history supports it.
        assert gen_5k.long_run_peak_target == pytest.approx(16.1, abs=0.1), \
            f"5K cap should be ~16.1mi (14 * 1.15), got {gen_5k.long_run_peak_target}"
        assert gen_marathon.long_run_peak_target == pytest.approx(22.0, abs=0.1), \
            f"Marathon cap should be 22mi, got {gen_marathon.long_run_peak_target}"
        
        # Start is based on recent capability (ADR-038 current_long_run_miles), not peak.
        assert gen_5k.long_run_start == pytest.approx(14.4, abs=0.1)
        assert gen_marathon.long_run_start == pytest.approx(14.4, abs=0.1)
    
    # =========================================================================
    # QUALITY FOCUS BY DISTANCE
    # =========================================================================
    
    def test_5k_quality_focus_includes_vo2max(self):
        """5K should emphasize VO2max work."""
        bank = self._create_bank()
        gen = WorkoutPrescriptionGenerator(bank, race_distance="5k")
        
        assert "vo2max" in gen.quality_focus or "speed" in gen.quality_focus
    
    def test_5k_no_race_pace_long_runs(self):
        """5K plans should not include race pace long runs (different stimulus)."""
        bank = self._create_bank()
        gen = WorkoutPrescriptionGenerator(bank, race_distance="5k")
        
        assert gen.use_mp_long_runs is False
    
    def test_10k_quality_focus_includes_threshold(self):
        """10K should emphasize threshold work."""
        bank = self._create_bank()
        gen = WorkoutPrescriptionGenerator(bank, race_distance="10k")
        
        assert "threshold" in gen.quality_focus
    
    def test_marathon_quality_focus_includes_mp(self):
        """Marathon should emphasize marathon pace work."""
        bank = self._create_bank()
        gen = WorkoutPrescriptionGenerator(bank, race_distance="marathon")
        
        assert "mp" in gen.quality_focus
    
    def test_marathon_race_pace_long_runs_enabled(self):
        """Marathon should include MP long runs."""
        bank = self._create_bank()
        gen = WorkoutPrescriptionGenerator(bank, race_distance="marathon")
        
        assert gen.use_mp_long_runs is True


class TestTaperIndividualization:
    """Test that taper length is τ1-informed, not hard-coded by distance."""
    
    def _create_bank(self, tau1: float) -> FitnessBank:
        bank = MagicMock(spec=FitnessBank)
        bank.best_rpi = 50
        bank.experience_level = ExperienceLevel.EXPERIENCED
        bank.peak_weekly_miles = 50
        bank.current_weekly_miles = 45
        bank.peak_long_run_miles = 18
        bank.current_long_run_miles = 18 * 0.8
        bank.average_long_run_miles = 18 * 0.9
        bank.tau1 = tau1
        bank.tau2 = 15
        bank.constraint_type = ConstraintType.NONE
        bank.weeks_since_peak = 0
        return bank
    
    def test_fast_adapter_shorter_taper(self):
        """Fast adapters (τ1 < 30) should have shorter tapers."""
        bank = self._create_bank(tau1=25)
        generator = WeekThemeGenerator()
        
        race_date = date.today() + timedelta(weeks=12)
        themes = generator.generate(bank, race_date, "marathon")
        
        taper_weeks = sum(1 for t in themes if t.theme in [WeekTheme.TAPER_1, WeekTheme.TAPER_2])
        
        # Fast adapter marathon taper should be 2 weeks (base 2, no extension)
        assert taper_weeks <= 2, f"Fast adapter should have ≤2 week taper, got {taper_weeks}"
    
    def test_slow_adapter_longer_taper(self):
        """Slow adapters (τ1 > 45) should have longer tapers."""
        bank = self._create_bank(tau1=50)
        generator = WeekThemeGenerator()
        
        race_date = date.today() + timedelta(weeks=12)
        themes = generator.generate(bank, race_date, "marathon")
        
        # Extended taper includes SHARPEN as first week of 3-week taper
        taper_themes = [WeekTheme.SHARPEN, WeekTheme.TAPER_1, WeekTheme.TAPER_2]
        taper_weeks = sum(1 for t in themes if t.theme in taper_themes)
        
        # Slow adapter marathon taper should be 3 weeks (base 2 + 1 extension)
        assert taper_weeks >= 3, f"Slow adapter should have ≥3 week taper, got {taper_weeks}"


class TestWeekThemeSequence:
    """Test week theme generation produces valid sequences."""
    
    def _create_bank(self, 
                     tau1: float = 42,
                     constraint: ConstraintType = ConstraintType.NONE,
                     current_pct: float = 0.8) -> FitnessBank:
        bank = MagicMock(spec=FitnessBank)
        bank.best_rpi = 50
        bank.experience_level = ExperienceLevel.EXPERIENCED
        bank.peak_weekly_miles = 50
        bank.current_weekly_miles = 50 * current_pct
        bank.peak_long_run_miles = 18
        bank.current_long_run_miles = 18 * 0.8
        bank.average_long_run_miles = 18 * 0.9
        bank.tau1 = tau1
        bank.tau2 = 15
        bank.constraint_type = constraint
        bank.weeks_since_peak = 4 if constraint == ConstraintType.INJURY else 0
        return bank
    
    def test_race_week_is_last(self):
        """Race week should always be the final week."""
        bank = self._create_bank()
        generator = WeekThemeGenerator()
        
        race_date = date.today() + timedelta(weeks=10)
        themes = generator.generate(bank, race_date, "marathon")
        
        assert themes[-1].theme == WeekTheme.RACE
    
    def test_peak_precedes_taper(self):
        """Peak week should come before taper."""
        bank = self._create_bank()
        generator = WeekThemeGenerator()
        
        race_date = date.today() + timedelta(weeks=12)
        themes = generator.generate(bank, race_date, "marathon")
        
        # Find peak and first taper
        peak_idx = None
        taper_idx = None
        for i, t in enumerate(themes):
            if t.theme == WeekTheme.PEAK and peak_idx is None:
                peak_idx = i
            if t.theme in [WeekTheme.TAPER_1, WeekTheme.TAPER_2] and taper_idx is None:
                taper_idx = i
        
        if peak_idx is not None and taper_idx is not None:
            assert peak_idx < taper_idx, "Peak should come before taper"
    
    def test_no_recovery_week_right_before_taper(self):
        """Recovery week should not immediately precede taper."""
        bank = self._create_bank()
        generator = WeekThemeGenerator()
        
        race_date = date.today() + timedelta(weeks=12)
        themes = generator.generate(bank, race_date, "marathon")
        
        for i in range(len(themes) - 1):
            if themes[i].theme == WeekTheme.RECOVERY:
                next_theme = themes[i + 1].theme
                assert next_theme not in [WeekTheme.TAPER_1, WeekTheme.TAPER_2], \
                    f"Recovery at week {i+1} followed by taper at week {i+2}"
    
    def test_injury_return_starts_with_rebuild(self):
        """Injury return should start with rebuild phases."""
        bank = self._create_bank(constraint=ConstraintType.INJURY, current_pct=0.3)
        generator = WeekThemeGenerator()
        
        race_date = date.today() + timedelta(weeks=12)
        themes = generator.generate(bank, race_date, "marathon")
        
        # First week should be rebuild
        assert themes[0].theme in [WeekTheme.REBUILD_EASY, WeekTheme.REBUILD_STRIDES]
    
    def test_short_plan_has_quality_weeks(self):
        """Even short plans should have quality build weeks."""
        bank = self._create_bank()
        generator = WeekThemeGenerator()
        
        race_date = date.today() + timedelta(weeks=6)
        themes = generator.generate(bank, race_date, "marathon")
        
        quality_themes = [WeekTheme.BUILD_T_EMPHASIS, WeekTheme.BUILD_MP_EMPHASIS, 
                         WeekTheme.BUILD_MIXED, WeekTheme.PEAK]
        quality_weeks = sum(1 for t in themes if t.theme in quality_themes)
        
        assert quality_weeks >= 2, f"Short plan should have ≥2 quality weeks, got {quality_weeks}"


class TestRaceWeekMiles:
    """Test race week assigns correct miles for distance."""
    
    def _create_bank(self) -> FitnessBank:
        bank = MagicMock(spec=FitnessBank)
        bank.best_rpi = 50
        bank.experience_level = ExperienceLevel.EXPERIENCED
        bank.peak_weekly_miles = 50
        bank.peak_long_run_miles = 18
        bank.peak_mp_long_run_miles = 14
        bank.current_weekly_miles = 45
        bank.current_long_run_miles = 18 * 0.8
        bank.average_long_run_miles = 18 * 0.9
        bank.tau1 = 42
        bank.tau2 = 15
        bank.typical_long_run_day = 6
        bank.typical_quality_day = 3
        bank.typical_rest_days = [0]
        bank.constraint_type = ConstraintType.NONE
        return bank
    
    @pytest.mark.parametrize("distance,expected_miles", [
        ("5k", 3.1),
        ("10k", 6.2),
        ("half_marathon", 13.1),
        ("marathon", 26.2),
    ])
    def test_race_day_miles_match_distance(self, distance, expected_miles):
        """Race day should have correct miles for target distance."""
        bank = self._create_bank()
        gen = WorkoutPrescriptionGenerator(bank, race_distance=distance)
        
        week = gen.generate_week(
            theme=WeekTheme.RACE,
            week_number=12,
            total_weeks=12,
            target_miles=40,
            start_date=date.today()
        )
        
        race_day = next((d for d in week.days if d.workout_type == "race"), None)
        assert race_day is not None, "Race week should have a race day"
        assert abs(race_day.target_miles - expected_miles) < 0.1, \
            f"Race miles for {distance} should be {expected_miles}, got {race_day.target_miles}"


class TestWorkoutVariety:
    """Test that generated weeks have appropriate variety."""
    
    def _create_bank(self) -> FitnessBank:
        bank = MagicMock(spec=FitnessBank)
        bank.best_rpi = 50
        bank.experience_level = ExperienceLevel.EXPERIENCED
        bank.peak_weekly_miles = 50
        bank.peak_long_run_miles = 18
        bank.peak_mp_long_run_miles = 14
        bank.current_weekly_miles = 45
        bank.current_long_run_miles = 18 * 0.8
        bank.average_long_run_miles = 18 * 0.9
        bank.tau1 = 42
        bank.tau2 = 15
        bank.typical_long_run_day = 6
        bank.typical_quality_day = 3
        bank.typical_rest_days = [0]
        bank.constraint_type = ConstraintType.NONE
        return bank
    
    def test_build_week_has_quality_and_long(self):
        """Build weeks should have both quality work and long run."""
        bank = self._create_bank()
        gen = WorkoutPrescriptionGenerator(bank, race_distance="marathon")
        
        week = gen.generate_week(
            theme=WeekTheme.BUILD_T_EMPHASIS,
            week_number=5,
            total_weeks=12,
            target_miles=50,
            start_date=date.today()
        )
        
        workout_types = [d.workout_type for d in week.days]
        
        assert "threshold" in workout_types, "Build week should have threshold workout"
        assert "long" in workout_types or "long_mp" in workout_types, \
            "Build week should have long run"
    
    def test_easy_days_vary_in_distance(self):
        """Easy days should not all be exactly the same distance."""
        bank = self._create_bank()
        gen = WorkoutPrescriptionGenerator(bank, race_distance="marathon")
        
        week = gen.generate_week(
            theme=WeekTheme.BUILD_T_EMPHASIS,
            week_number=5,
            total_weeks=12,
            target_miles=50,
            start_date=date.today()
        )
        
        easy_miles = [d.target_miles for d in week.days if d.workout_type == "easy"]
        
        if len(easy_miles) >= 2:
            # Check that easy days aren't all identical
            unique_miles = set(round(m, 1) for m in easy_miles)
            # Allow some variation - at least 2 different distances if 3+ easy days
            if len(easy_miles) >= 3:
                assert len(unique_miles) >= 2, \
                    f"Easy days should vary in distance, got all {easy_miles}"
