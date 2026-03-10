#!/usr/bin/env python3
"""
Test Fitness Bank calculation against Michael's actual data.

Expected results based on known history:
- Peak weekly: 71 miles
- Peak monthly: 276 miles (October)
- Peak long run: 22 miles
- Peak MP long run: 18 miles
- Best race: 10K at 6:18 (RPI ~54-55) or HM at 6:39 (RPI ~52-53)
- Current: Reduced (injury)
- τ1: ~25 days (fast adapter)
- Experience: Elite or Experienced
- Constraint: Injury (returning)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SessionLocal
from models import Athlete
from services.fitness_bank import get_fitness_bank, FitnessBankCalculator


def main():
    db = SessionLocal()
    
    try:
        # Find athlete
        athlete = db.query(Athlete).filter(
            Athlete.display_name.ilike("%mbshaf%")
        ).first()
        
        if not athlete:
            print("Could not find athlete record")
            return
        
        print("=" * 80)
        print(f"TESTING FITNESS BANK FOR: {athlete.display_name}")
        print("=" * 80)
        
        # Calculate fitness bank
        bank = get_fitness_bank(athlete.id, db)
        
        # Display results
        print("\n📊 PEAK CAPABILITIES")
        print(f"  Peak Weekly:    {bank.peak_weekly_miles:.0f} miles")
        print(f"  Peak Monthly:   {bank.peak_monthly_miles:.0f} miles")
        print(f"  Peak Long Run:  {bank.peak_long_run_miles:.0f} miles")
        print(f"  Peak MP Long:   {bank.peak_mp_long_run_miles:.0f} miles @ MP")
        print(f"  Peak Threshold: {bank.peak_threshold_miles:.0f} miles")
        print(f"  Peak CTL:       {bank.peak_ctl:.0f}")
        
        print("\n📈 CURRENT STATE")
        print(f"  Current Weekly: {bank.current_weekly_miles:.0f} miles")
        print(f"  Current CTL:    {bank.current_ctl:.0f}")
        print(f"  Current ATL:    {bank.current_atl:.0f}")
        print(f"  Weeks Since Peak: {bank.weeks_since_peak}")
        
        print("\n🏃 RACE PERFORMANCES")
        print(f"  Best RPI: {bank.best_rpi:.1f}")
        if bank.best_race:
            r = bank.best_race
            pace_min = int(r.pace_per_mile)
            pace_sec = int((r.pace_per_mile - pace_min) * 60)
            cond = f" ({r.conditions})" if r.conditions else ""
            print(f"  Best Race: {r.distance} on {r.date}")
            print(f"    Pace: {pace_min}:{pace_sec:02d}/mi{cond}")
            print(f"    RPI: {r.rpi:.1f}")
        
        print("\n  All Races:")
        for r in bank.race_performances[:5]:
            pace_min = int(r.pace_per_mile)
            pace_sec = int((r.pace_per_mile - pace_min) * 60)
            cond = f" ({r.conditions})" if r.conditions else ""
            print(f"    {r.date}: {r.distance:10s} - {pace_min}:{pace_sec:02d}/mi, RPI {r.rpi:.1f}{cond}")
        
        print("\n🧬 INDIVIDUAL RESPONSE")
        print(f"  τ1 (fitness):  {bank.tau1:.0f} days")
        print(f"  τ2 (fatigue):  {bank.tau2:.0f} days")
        print(f"  Experience:    {bank.experience_level.value}")
        
        print("\n⚠️  CONSTRAINT ANALYSIS")
        print(f"  Type:          {bank.constraint_type.value}")
        print(f"  Details:       {bank.constraint_details or 'None'}")
        print(f"  Returning:     {bank.is_returning_from_break}")
        
        print("\n📅 TRAINING PATTERNS")
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        if bank.typical_long_run_day is not None:
            print(f"  Long Run Day:  {days[bank.typical_long_run_day]}")
        if bank.typical_quality_day is not None:
            print(f"  Quality Day:   {days[bank.typical_quality_day]}")
        if bank.typical_rest_days:
            print(f"  Rest Days:     {', '.join(days[d] for d in bank.typical_rest_days)}")
        
        print("\n🔮 PROJECTIONS")
        print(f"  Weeks to 80% CTL:   {bank.weeks_to_80pct_ctl}")
        print(f"  Weeks to Race Ready: {bank.weeks_to_race_ready}")
        print(f"  Sustainable Peak:    {bank.sustainable_peak_weekly:.0f} mpw")
        
        # Validate against expectations
        print("\n" + "=" * 80)
        print("VALIDATION AGAINST KNOWN HISTORY")
        print("=" * 80)
        
        checks = [
            ("Peak Weekly >= 70", bank.peak_weekly_miles >= 70),
            ("Peak Monthly >= 270", bank.peak_monthly_miles >= 270),
            ("Peak Long Run >= 22", bank.peak_long_run_miles >= 22),
            ("Peak MP Long >= 16", bank.peak_mp_long_run_miles >= 16),
            ("Best RPI >= 52", bank.best_rpi >= 52),
            ("Experience = Elite or Experienced", 
             bank.experience_level.value in ("elite", "experienced")),
            ("Constraint = Injury", bank.constraint_type.value == "injury"),
            ("τ1 < 35 (fast adapter)", bank.tau1 < 35),
        ]
        
        passed = 0
        for name, result in checks:
            status = "✅" if result else "❌"
            print(f"  {status} {name}")
            if result:
                passed += 1
        
        print(f"\n  Result: {passed}/{len(checks)} checks passed")
        
        # What this means for March races
        print("\n" + "=" * 80)
        print("IMPLICATIONS FOR MARCH RACES")
        print("=" * 80)
        
        print(f"""
  Based on Fitness Bank:
  
  Your Proven Capability:
    - RPI {bank.best_rpi:.0f} = 10-mile @ ~{6 + bank.best_rpi/100:.0f}:{int((bank.best_rpi%100)/10*6):02d}/mi
    - Marathon equivalent: ~{2 + (55-bank.best_rpi)/10:.0f}:{int(((55-bank.best_rpi)%10)*6):02d}
    
  Current Constraint:
    - {bank.constraint_type.value}: {bank.constraint_details}
    - Weeks to race ready: {bank.weeks_to_race_ready}
    
  March 7 (10-Mile):
    - Your 6:18 10K while limping = you can run 6:20 10-mile healthy
    - {bank.weeks_to_race_ready} weeks to regain race fitness
    - Target 63:20 is achievable with {bank.weeks_to_race_ready} quality weeks
    
  March 15 (Marathon):
    - Conservative: 7:15/mi (3:10) given constraints
    - Optimistic: 7:00/mi (3:03) if fully recovered
    - Based on τ1={bank.tau1:.0f}d, you adapt fast
""")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
