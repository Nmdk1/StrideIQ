"""
Test ADR-038 with different simulated athlete profiles.

Ensures the algorithm produces appropriate progression for all experience levels.
"""

from services.fitness_bank import (
    FitnessBank,
    ConstraintType,
    ExperienceLevel,
)
from services.workout_prescription import WorkoutPrescriptionGenerator
from services.week_theme_generator import WeekTheme, WeekThemeGenerator
from datetime import date, timedelta


def create_mock_bank(
    current_long: float,
    avg_long: float, 
    peak_long: float,
    current_weekly: float,
    peak_weekly: float,
    experience: ExperienceLevel,
    constraint: ConstraintType = ConstraintType.NONE,
    tau1: float = 42.0
):
    """Create a mock FitnessBank for testing."""
    return FitnessBank(
        athlete_id="test-athlete",
        peak_weekly_miles=peak_weekly,
        peak_monthly_miles=peak_weekly * 4,
        peak_long_run_miles=peak_long,
        peak_mp_long_run_miles=peak_long * 0.6,
        peak_threshold_miles=8.0,
        peak_ctl=peak_weekly * 1.5,
        race_performances=[],
        best_rpi=50.0,
        best_race=None,
        current_weekly_miles=current_weekly,
        current_ctl=current_weekly * 1.2,
        current_atl=current_weekly * 1.0,
        weeks_since_peak=4,
        current_long_run_miles=current_long,
        average_long_run_miles=avg_long,
        tau1=tau1,
        tau2=7.0,
        experience_level=experience,
        constraint_type=constraint,
        constraint_details=None,
        is_returning_from_break=constraint == ConstraintType.INJURY,
        typical_long_run_day=6,
        typical_quality_day=3,
        typical_rest_days=[0],
        weeks_to_80pct_ctl=4,
        weeks_to_race_ready=3,
        sustainable_peak_weekly=peak_weekly * 0.9,
    )


def test_profile(name, bank, distance, weeks):
    """Test a specific athlete profile."""
    gen = WorkoutPrescriptionGenerator(bank, race_distance=distance)
    theme_gen = WeekThemeGenerator()
    
    race_date = date.today() + timedelta(weeks=weeks)
    themes = theme_gen.generate(bank=bank, race_date=race_date, race_distance=distance)
    
    # Calculate progression
    long_runs = []
    for t in themes:
        lr = gen.calculate_long_run_for_week(t.week_number, len(themes), t.theme)
        long_runs.append((t.week_number, t.theme.value, lr))
    
    # Find max jump in build phase
    max_jump = 0
    prev = None
    for w, theme, lr in long_runs:
        if theme.startswith(('rebuild', 'build', 'peak')):
            if prev is not None:
                jump = lr - prev
                if jump > max_jump:
                    max_jump = jump
            prev = lr
    
    passed = max_jump <= 3.0
    status = "PASS" if passed else "FAIL"
    
    print(f"\n{name}")
    print(f"  Distance: {distance}, Weeks: {weeks}")
    print(f"  Current: {gen.long_run_current:.1f}mi, Peak: {gen.long_run_peak:.1f}mi")
    print(f"  Max Jump: {max_jump:.1f}mi - {status}")
    
    # Show first few weeks
    build_weeks = [(w, t, lr) for w, t, lr in long_runs if t.startswith(('rebuild', 'build', 'peak'))][:5]
    for w, theme, lr in build_weeks:
        print(f"    Week {w}: {theme:18} {lr:.1f} mi")
    
    return passed


def main():
    print("=" * 70)
    print("ADR-038 VERIFICATION: DIFFERENT ATHLETE PROFILES")
    print("=" * 70)
    
    results = []
    
    # Profile 1: Elite injury return (like Michael)
    bank = create_mock_bank(
        current_long=12.0, avg_long=14.6, peak_long=22.0,
        current_weekly=24.0, peak_weekly=71.0,
        experience=ExperienceLevel.ELITE,
        constraint=ConstraintType.INJURY,
        tau1=25.0
    )
    results.append(test_profile("ELITE INJURY RETURN (Michael-like)", bank, "marathon", 9))
    
    # Profile 2: Healthy experienced marathoner
    bank = create_mock_bank(
        current_long=18.0, avg_long=16.0, peak_long=20.0,
        current_weekly=55.0, peak_weekly=60.0,
        experience=ExperienceLevel.EXPERIENCED,
        constraint=ConstraintType.NONE
    )
    results.append(test_profile("HEALTHY EXPERIENCED MARATHONER", bank, "marathon", 12))
    
    # Profile 3: Intermediate half marathoner
    bank = create_mock_bank(
        current_long=10.0, avg_long=10.0, peak_long=14.0,
        current_weekly=35.0, peak_weekly=40.0,
        experience=ExperienceLevel.INTERMEDIATE
    )
    results.append(test_profile("INTERMEDIATE HALF MARATHONER", bank, "half", 12))
    
    # Profile 4: Beginner 10K runner
    bank = create_mock_bank(
        current_long=5.0, avg_long=5.0, peak_long=8.0,
        current_weekly=20.0, peak_weekly=25.0,
        experience=ExperienceLevel.BEGINNER
    )
    results.append(test_profile("BEGINNER 10K RUNNER", bank, "10k", 8))
    
    # Profile 5: New runner (no long run history)
    bank = create_mock_bank(
        current_long=0.0, avg_long=0.0, peak_long=6.0,
        current_weekly=15.0, peak_weekly=20.0,
        experience=ExperienceLevel.BEGINNER
    )
    results.append(test_profile("NEW RUNNER (no long run data)", bank, "5k", 8))
    
    # Profile 6: Coming back after long break
    bank = create_mock_bank(
        current_long=8.0, avg_long=14.0, peak_long=18.0,
        current_weekly=20.0, peak_weekly=50.0,
        experience=ExperienceLevel.EXPERIENCED,
        constraint=ConstraintType.INJURY
    )
    results.append(test_profile("RETURNING FROM LONG BREAK", bank, "half", 10))
    
    # Profile 7: Fast adapter (low tau1)
    bank = create_mock_bank(
        current_long=14.0, avg_long=15.0, peak_long=20.0,
        current_weekly=45.0, peak_weekly=55.0,
        experience=ExperienceLevel.EXPERIENCED,
        tau1=22.0  # Fast adapter
    )
    results.append(test_profile("FAST ADAPTER (tau1=22)", bank, "marathon", 10))
    
    # Profile 8: Slow adapter (high tau1)
    bank = create_mock_bank(
        current_long=14.0, avg_long=15.0, peak_long=20.0,
        current_weekly=45.0, peak_weekly=55.0,
        experience=ExperienceLevel.EXPERIENCED,
        tau1=55.0  # Slow adapter
    )
    results.append(test_profile("SLOW ADAPTER (tau1=55)", bank, "marathon", 12))
    
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    
    print(f"\nTotal: {total}, Passed: {passed}, Failed: {total - passed}")
    
    if passed == total:
        print("\nSTATUS: ALL ATHLETE PROFILES PASS")
    else:
        print("\nSTATUS: SOME PROFILES FAIL - NEEDS INVESTIGATION")


if __name__ == "__main__":
    main()
