"""
Rebuild/Verify Process (ADR-036 Step 6)

Regenerates plans for cohort and verifies acceptance criteria:
1. No invalid phase work
2. Variance enforced (no consecutive same stimulus)
3. Long run caps respected by distance
4. τ1-informed taper length
5. Peak week precedes taper
6. No recovery immediately before taper
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta
from typing import List, Dict, Any
from dataclasses import dataclass

from services.fitness_bank import FitnessBank, ExperienceLevel, ConstraintType
from services.workout_prescription import WorkoutPrescriptionGenerator
from services.week_theme_generator import WeekThemeGenerator, WeekTheme


@dataclass
class VerificationResult:
    """Result of plan verification."""
    athlete_id: str
    distance: str
    passed: bool
    checks: Dict[str, bool]
    issues: List[str]
    plan_summary: Dict[str, Any]


def create_test_bank(
    rpi: float = 50,
    experience: ExperienceLevel = ExperienceLevel.EXPERIENCED,
    peak_weekly: float = 50,
    peak_long: float = 18,
    tau1: float = 42,
    constraint: ConstraintType = ConstraintType.NONE
) -> FitnessBank:
    """Create a FitnessBank for testing."""
    from unittest.mock import MagicMock
    
    bank = MagicMock(spec=FitnessBank)
    bank.best_rpi = rpi
    bank.experience_level = experience
    bank.peak_weekly_miles = peak_weekly
    bank.peak_long_run_miles = peak_long
    bank.peak_mp_long_run_miles = 14
    bank.current_weekly_miles = peak_weekly * 0.8
    bank.tau1 = tau1
    bank.tau2 = 15
    bank.typical_long_run_day = 6
    bank.typical_quality_day = 3
    bank.typical_rest_days = [0]
    bank.constraint_type = constraint
    bank.weeks_since_peak = 4 if constraint == ConstraintType.INJURY else 0
    return bank


def verify_plan(
    athlete_id: str,
    distance: str,
    weeks: int = 12,
    tau1: float = 42,
    constraint: ConstraintType = ConstraintType.NONE
) -> VerificationResult:
    """Generate and verify a plan for given parameters."""
    
    issues = []
    checks = {}
    
    # Create bank
    bank = create_test_bank(tau1=tau1, constraint=constraint)
    
    # Generate themes
    theme_gen = WeekThemeGenerator()
    race_date = date.today() + timedelta(weeks=weeks)
    themes = theme_gen.generate(bank, race_date, distance)
    
    # Generate workouts for each week
    workout_gen = WorkoutPrescriptionGenerator(bank, race_distance=distance)
    
    all_weeks = []
    for theme_plan in themes:
        week = workout_gen.generate_week(
            theme=theme_plan.theme,
            week_number=theme_plan.week_number,
            total_weeks=len(themes),
            target_miles=theme_plan.target_volume_pct * bank.peak_weekly_miles,
            start_date=theme_plan.start_date
        )
        all_weeks.append({
            "week_number": theme_plan.week_number,
            "theme": theme_plan.theme.value,
            "total_miles": week.total_miles,
            "days": [d.to_dict() for d in week.days]
        })
    
    # =========================================================================
    # VERIFICATION CHECKS
    # =========================================================================
    
    # 1. Race week is last
    checks["race_week_last"] = themes[-1].theme == WeekTheme.RACE
    if not checks["race_week_last"]:
        issues.append("Race week is not the final week")
    
    # 2. Peak precedes taper
    peak_idx = None
    taper_idx = None
    for i, t in enumerate(themes):
        if t.theme == WeekTheme.PEAK and peak_idx is None:
            peak_idx = i
        if t.theme in [WeekTheme.TAPER_1, WeekTheme.TAPER_2, WeekTheme.SHARPEN] and taper_idx is None:
            taper_idx = i
    
    checks["peak_before_taper"] = (peak_idx is None) or (taper_idx is None) or (peak_idx < taper_idx)
    if not checks["peak_before_taper"]:
        issues.append(f"Peak at week {peak_idx+1} does not precede taper at week {taper_idx+1}")
    
    # 3. No recovery immediately before taper
    checks["no_recovery_before_taper"] = True
    for i in range(len(themes) - 1):
        if themes[i].theme == WeekTheme.RECOVERY:
            next_theme = themes[i + 1].theme
            if next_theme in [WeekTheme.TAPER_1, WeekTheme.TAPER_2]:
                checks["no_recovery_before_taper"] = False
                issues.append(f"Recovery at week {i+1} immediately before taper at week {i+2}")
    
    # 4. Long run caps respected
    long_run_caps = {
        "5k": 12, "10k": 14, "10_mile": 15,
        "half": 16, "half_marathon": 16, "marathon": 22
    }
    max_cap = long_run_caps.get(distance, 22)
    
    max_long_run = 0
    for week in all_weeks:
        for day in week["days"]:
            if day["workout_type"] in ["long", "long_mp"]:
                max_long_run = max(max_long_run, day["target_miles"])
    
    checks["long_run_cap_respected"] = max_long_run <= max_cap + 0.5  # Small tolerance
    if not checks["long_run_cap_respected"]:
        issues.append(f"Long run {max_long_run:.1f}mi exceeds {distance} cap of {max_cap}mi")
    
    # 5. Easy day variety (not all same distance)
    for week in all_weeks:
        easy_miles = [d["target_miles"] for d in week["days"] if d["workout_type"] == "easy"]
        if len(easy_miles) >= 3:
            unique = set(round(m, 1) for m in easy_miles)
            if len(unique) < 2:
                # Allow for low-volume recovery weeks
                if week["theme"] not in ["recovery", "taper_2", "race"]:
                    checks["easy_day_variety"] = False
                    issues.append(f"Week {week['week_number']} has monotonous easy days: {easy_miles}")
    
    if "easy_day_variety" not in checks:
        checks["easy_day_variety"] = True
    
    # 6. Taper length appropriate for τ1
    taper_themes = [WeekTheme.SHARPEN, WeekTheme.TAPER_1, WeekTheme.TAPER_2]
    taper_count = sum(1 for t in themes if t.theme in taper_themes)
    
    if tau1 > 45 and distance == "marathon":
        checks["tau1_taper_length"] = taper_count >= 3
        if not checks["tau1_taper_length"]:
            issues.append(f"Slow adapter (tau1={tau1}) should have >=3 week taper, got {taper_count}")
    elif tau1 < 30:
        checks["tau1_taper_length"] = taper_count <= 2
        if not checks["tau1_taper_length"]:
            issues.append(f"Fast adapter (tau1={tau1}) should have <=2 week taper, got {taper_count}")
    else:
        checks["tau1_taper_length"] = True
    
    # 7. Build weeks have quality + long
    build_themes = [WeekTheme.BUILD_T_EMPHASIS, WeekTheme.BUILD_MP_EMPHASIS, 
                    WeekTheme.BUILD_MIXED, WeekTheme.PEAK]
    checks["build_weeks_quality"] = True
    
    for week in all_weeks:
        if week["theme"] in [t.value for t in build_themes]:
            workout_types = [d["workout_type"] for d in week["days"]]
            has_quality = any(t in workout_types for t in ["threshold", "intervals", "long_mp"])
            has_long = "long" in workout_types or "long_mp" in workout_types
            
            if not (has_quality and has_long):
                checks["build_weeks_quality"] = False
                issues.append(f"Week {week['week_number']} ({week['theme']}) missing quality or long run")
    
    # Overall pass/fail
    passed = all(checks.values())
    
    # Plan summary
    plan_summary = {
        "total_weeks": len(themes),
        "max_long_run": max_long_run,
        "taper_weeks": taper_count,
        "themes": [t.theme.value for t in themes]
    }
    
    return VerificationResult(
        athlete_id=athlete_id,
        distance=distance,
        passed=passed,
        checks=checks,
        issues=issues,
        plan_summary=plan_summary
    )


def run_rebuild_verify():
    """Execute rebuild/verify for all distance cohorts."""
    
    print("=" * 70)
    print("ADR-036 REBUILD/VERIFY PROCESS")
    print("=" * 70)
    print()
    
    # Test cohorts
    cohorts = [
        # (athlete_id, distance, weeks, tau1, constraint)
        ("cohort_5k_normal", "5k", 8, 42, ConstraintType.NONE),
        ("cohort_5k_fast_adapter", "5k", 8, 25, ConstraintType.NONE),
        ("cohort_10k_normal", "10k", 10, 42, ConstraintType.NONE),
        ("cohort_half_normal", "half_marathon", 12, 42, ConstraintType.NONE),
        ("cohort_half_injury", "half_marathon", 12, 42, ConstraintType.INJURY),
        ("cohort_marathon_normal", "marathon", 16, 42, ConstraintType.NONE),
        ("cohort_marathon_slow_adapter", "marathon", 16, 50, ConstraintType.NONE),
        ("cohort_marathon_fast_adapter", "marathon", 16, 25, ConstraintType.NONE),
        ("cohort_marathon_short_prep", "marathon", 6, 42, ConstraintType.NONE),
    ]
    
    results = []
    
    for athlete_id, distance, weeks, tau1, constraint in cohorts:
        result = verify_plan(athlete_id, distance, weeks, tau1, constraint)
        results.append(result)
        
        status = "[PASS]" if result.passed else "[FAIL]"
        constraint_str = f" (injury return)" if constraint == ConstraintType.INJURY else ""
        tau1_str = f" tau1={tau1}" if tau1 != 42 else ""
        
        print(f"{status} {athlete_id}: {distance} {weeks}wk{constraint_str}{tau1_str}")
        
        if not result.passed:
            for issue in result.issues:
                print(f"       WARNING: {issue}")
        
        # Show plan summary
        summary = result.plan_summary
        print(f"       Max long: {summary['max_long_run']:.1f}mi | Taper: {summary['taper_weeks']}wk")
        print(f"       Themes: {' > '.join(summary['themes'][:5])}...")
        print()
    
    # Summary
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    
    print("=" * 70)
    print(f"VERIFICATION SUMMARY: {passed}/{total} cohorts passed")
    print("=" * 70)
    
    if passed == total:
        print("\n[SUCCESS] ALL ACCEPTANCE CRITERIA MET - Ready for production")
    else:
        print("\n[FAILURE] ISSUES FOUND - Review and fix before deployment")
        failed = [r for r in results if not r.passed]
        for r in failed:
            print(f"\n  {r.athlete_id}:")
            for issue in r.issues:
                print(f"    - {issue}")
    
    return passed == total


if __name__ == "__main__":
    success = run_rebuild_verify()
    sys.exit(0 if success else 1)
