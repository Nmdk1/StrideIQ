"""
Comprehensive verification script for ADR-038: N=1 Long Run Progression.

Tests all distances and timelines to ensure no dangerous jumps.
"""

from core.database import SessionLocal
from models import Athlete
from services.fitness_bank import get_fitness_bank
from services.workout_prescription import WorkoutPrescriptionGenerator
from services.week_theme_generator import WeekTheme, WeekThemeGenerator
from datetime import date, timedelta

def test_distance(bank, distance, weeks):
    """Test a specific distance and timeline."""
    gen = WorkoutPrescriptionGenerator(bank, race_distance=distance)
    theme_gen = WeekThemeGenerator()
    
    race_date = date.today() + timedelta(weeks=weeks)
    themes = theme_gen.generate(bank=bank, race_date=race_date, race_distance=distance)
    
    # Calculate long run progression
    long_runs = []
    for t in themes:
        lr = gen.calculate_long_run_for_week(t.week_number, len(themes), t.theme)
        long_runs.append((t.week_number, t.theme.value, lr))
    
    # Find max jump in build phase only
    max_jump = 0
    prev = None
    for w, theme, lr in long_runs:
        if theme.startswith(('rebuild', 'build', 'peak')):
            if prev is not None:
                jump = lr - prev
                if jump > max_jump:
                    max_jump = jump
            prev = lr
    
    return {
        'distance': distance,
        'weeks': weeks,
        'current': gen.long_run_current,
        'peak': gen.long_run_peak,
        'max_jump': max_jump,
        'progression': long_runs,
        'pass': max_jump <= 3.0
    }


def main():
    db = SessionLocal()
    
    try:
        athlete = db.query(Athlete).filter(Athlete.email == 'mbshaf@gmail.com').first()
        if not athlete:
            print("Athlete not found")
            return
        
        bank = get_fitness_bank(athlete.id, db)
        
        print("=" * 70)
        print("COMPREHENSIVE ADR-038 VERIFICATION")
        print("=" * 70)
        print()
        print(f"Athlete: {athlete.email}")
        print(f"Current Long Run: {bank.current_long_run_miles:.1f} mi")
        print(f"Average Long Run: {bank.average_long_run_miles:.1f} mi")
        print(f"Peak Long Run: {bank.peak_long_run_miles:.1f} mi")
        print()
        
        # Test all distances
        distances = ['5k', '10k', '10_mile', 'half', 'marathon']
        timelines = [8, 12, 16]
        
        all_results = []
        
        print("=" * 70)
        print("PART 1: ALL DISTANCES (12-week standard)")
        print("=" * 70)
        
        for distance in distances:
            result = test_distance(bank, distance, 12)
            all_results.append(result)
            
            status = "PASS" if result['pass'] else "FAIL"
            print(f"\n{distance.upper()} | current: {result['current']:.1f}mi | peak: {result['peak']:.1f}mi | max_jump: {result['max_jump']:.1f}mi | {status}")
            
            # Show first 6 weeks of progression
            print("  Week  Theme             Long Run")
            for w, theme, lr in result['progression'][:6]:
                print(f"    {w}     {theme:18} {lr:.1f} mi")
        
        print()
        print("=" * 70)
        print("PART 2: DIFFERENT TIMELINES (Marathon)")
        print("=" * 70)
        
        for weeks in timelines:
            result = test_distance(bank, 'marathon', weeks)
            all_results.append(result)
            
            status = "PASS" if result['pass'] else "FAIL"
            print(f"\n{weeks}-WEEK MARATHON | current: {result['current']:.1f}mi | peak: {result['peak']:.1f}mi | max_jump: {result['max_jump']:.1f}mi | {status}")
            
            # Show build weeks
            build_weeks = [(w, t, lr) for w, t, lr in result['progression'] if t.startswith(('rebuild', 'build', 'peak'))]
            print("  Week  Theme             Long Run")
            for w, theme, lr in build_weeks[:7]:
                print(f"    {w}     {theme:18} {lr:.1f} mi")
        
        print()
        print("=" * 70)
        print("PART 3: EDGE CASE - SHORT TIMELINE (6 weeks)")
        print("=" * 70)
        
        for distance in ['10k', 'half', 'marathon']:
            result = test_distance(bank, distance, 6)
            all_results.append(result)
            
            status = "PASS" if result['pass'] else "FAIL"
            print(f"\n6-WEEK {distance.upper()} | current: {result['current']:.1f}mi | peak: {result['peak']:.1f}mi | max_jump: {result['max_jump']:.1f}mi | {status}")
        
        print()
        print("=" * 70)
        print("FINAL SUMMARY")
        print("=" * 70)
        
        passed = sum(1 for r in all_results if r['pass'])
        failed = sum(1 for r in all_results if not r['pass'])
        
        print(f"\nTotal tests: {len(all_results)}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        
        if failed > 0:
            print("\nFAILED TESTS:")
            for r in all_results:
                if not r['pass']:
                    print(f"  - {r['distance']} ({r['weeks']} weeks): max_jump = {r['max_jump']:.1f}mi")
        
        print()
        if failed == 0:
            print("STATUS: ALL TESTS PASS")
        else:
            print("STATUS: SOME TESTS FAIL - NEEDS INVESTIGATION")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
