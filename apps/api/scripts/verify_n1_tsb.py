#!/usr/bin/env python3
"""
Verification script for N=1 Individualized TSB Zones (ADR-035)

This script verifies that the personal TSB zone calculation works correctly
with real athlete data.

Run: docker-compose exec api python scripts/verify_n1_tsb.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, datetime, timedelta
from uuid import UUID
from sqlalchemy import func

# Use the app's database session
from database import SessionLocal
from models import Athlete, Activity
from services.training_load import (
    TrainingLoadCalculator,
    PersonalTSBProfile,
    TSBZone
)


def main():
    print("=" * 70)
    print("N=1 Individualized TSB Zones - Verification Script")
    print("ADR-035 Verification")
    print("=" * 70)
    print()
    
    # Use the app's database session
    db = SessionLocal()
    
    try:
        # Find athletes with activity history
        print("1. FINDING ATHLETES WITH ACTIVITY DATA")
        print("-" * 50)
        
        athletes = db.query(
            Athlete.id,
            Athlete.email,
            func.count(Activity.id).label('activity_count'),
            func.min(Activity.start_time).label('first_activity'),
            func.max(Activity.start_time).label('last_activity')
        ).outerjoin(Activity).group_by(Athlete.id).all()
        
        if not athletes:
            print("ERROR: No athletes found in database")
            return 1
        
        # Find athlete with most data
        athlete_with_data = None
        max_activities = 0
        
        for a in athletes:
            print(f"  - {a.email}: {a.activity_count} activities")
            if a.first_activity:
                days = (a.last_activity - a.first_activity).days
                print(f"    Date range: {a.first_activity.date()} to {a.last_activity.date()} ({days} days)")
            if a.activity_count > max_activities:
                max_activities = a.activity_count
                athlete_with_data = a
        
        if not athlete_with_data or athlete_with_data.activity_count < 10:
            print("\nWARNING: No athlete with sufficient activity data (need 10+)")
            print("This may be a test database. Using first athlete for structure verification.")
            athlete_with_data = athletes[0]
        
        athlete_id = athlete_with_data.id
        print(f"\nUsing athlete: {athlete_with_data.email} ({athlete_with_data.activity_count} activities)")
        print()
        
        # Initialize calculator
        calculator = TrainingLoadCalculator(db)
        
        # Test get_load_history
        print("2. VERIFYING get_load_history()")
        print("-" * 50)
        
        history = calculator.get_load_history(athlete_id, days=180)
        
        print(f"  History returned: {len(history)} days")
        
        if not history:
            print("  ERROR: get_load_history returned empty list")
            print("  This means the athlete has no activity data in the last 180 days")
            return 1
        
        # Count days with non-zero TSS
        days_with_tss = sum(1 for d in history if d.total_tss > 0)
        print(f"  Days with TSS > 0: {days_with_tss}")
        
        # Show TSB range
        tsb_values = [d.tsb for d in history]
        print(f"  TSB range: {min(tsb_values):.1f} to {max(tsb_values):.1f}")
        print(f"  Latest TSB: {history[-1].tsb:.1f}")
        print()
        
        # Test personal profile calculation
        print("3. VERIFYING PersonalTSBProfile CALCULATION")
        print("-" * 50)
        
        profile = calculator.get_personal_tsb_profile(athlete_id)
        
        print(f"  Sample days: {profile.sample_days}")
        print(f"  Sufficient data (>=56 days): {profile.is_sufficient_data}")
        print()
        print(f"  Personal Statistics:")
        print(f"    Mean TSB: {profile.mean_tsb:.1f}")
        print(f"    Std Dev:  {profile.std_tsb:.1f}")
        print(f"    Min TSB:  {profile.min_tsb:.1f}")
        print(f"    Max TSB:  {profile.max_tsb:.1f}")
        print()
        print(f"  Personal Zone Thresholds:")
        print(f"    Race Ready (fresh):   > {profile.threshold_fresh:.1f}")
        print(f"    Recovering:           > {profile.threshold_recovering:.1f}")
        print(f"    Normal training:      > {profile.threshold_normal_low:.1f}")
        print(f"    Overreaching:         > {profile.threshold_danger:.1f}")
        print(f"    Overtraining risk:    < {profile.threshold_danger:.1f}")
        print()
        
        # Compare to population thresholds
        print("4. COMPARISON: PERSONAL vs POPULATION THRESHOLDS")
        print("-" * 50)
        print()
        print(f"  Zone           | Population | Personal (This Athlete)")
        print(f"  ---------------|------------|------------------------")
        print(f"  Race Ready     | > +15      | > {profile.threshold_fresh:+.1f}")
        print(f"  Recovering     | > +5       | > {profile.threshold_recovering:+.1f}")
        print(f"  Normal Low     | > -10      | > {profile.threshold_normal_low:+.1f}")
        print(f"  Overreaching   | > -30      | > {profile.threshold_danger:+.1f}")
        print()
        
        # Test zone classification
        print("5. VERIFYING ZONE CLASSIFICATION")
        print("-" * 50)
        
        current_tsb = history[-1].tsb if history else 0
        
        # Population-based zone
        population_zone = calculator._get_population_tsb_zone(current_tsb)
        
        # Personal zone
        personal_zone_info = calculator.get_tsb_zone(current_tsb, athlete_id=athlete_id)
        personal_zone = profile.get_zone(current_tsb)
        
        print(f"  Current TSB: {current_tsb:.1f}")
        print()
        print(f"  Population-based zone: {population_zone.zone.value}")
        print(f"    Label: {population_zone.label}")
        print()
        print(f"  Personal zone: {personal_zone.value}")
        print(f"    Label: {personal_zone_info.label}")
        print(f"    Description: {personal_zone_info.description}")
        print()
        
        # Check if zones differ
        if population_zone.zone != personal_zone:
            print(f"  ✓ ZONES DIFFER: Personal zones are working!")
            print(f"    Population says '{population_zone.zone.value}' but personal says '{personal_zone.value}'")
        else:
            print(f"  Zones match (this is OK if athlete's profile is close to population norm)")
        print()
        
        # Sanity checks
        print("6. SANITY CHECKS")
        print("-" * 50)
        
        errors = []
        warnings = []
        
        # Check threshold ordering
        if not (profile.threshold_fresh > profile.threshold_recovering > 
                profile.threshold_normal_low > profile.threshold_danger):
            errors.append("Threshold ordering is wrong!")
        else:
            print("  ✓ Thresholds are correctly ordered")
        
        # Check minimum SD
        if profile.std_tsb < 8:
            errors.append(f"SD {profile.std_tsb} is below minimum of 8")
        else:
            print(f"  ✓ SD ({profile.std_tsb:.1f}) meets minimum requirement (8)")
        
        # Check mean is within reasonable range
        if profile.mean_tsb < -50 or profile.mean_tsb > 30:
            warnings.append(f"Mean TSB {profile.mean_tsb} seems extreme")
        else:
            print(f"  ✓ Mean TSB ({profile.mean_tsb:.1f}) is within reasonable range")
        
        # Check sample days matches history
        if profile.sample_days != len(history):
            warnings.append(f"Sample days ({profile.sample_days}) doesn't match history length ({len(history)})")
        else:
            print(f"  ✓ Sample days matches history length")
        
        if errors:
            print()
            print("  ERRORS:")
            for e in errors:
                print(f"    ✗ {e}")
        
        if warnings:
            print()
            print("  WARNINGS:")
            for w in warnings:
                print(f"    ⚠ {w}")
        
        print()
        print("=" * 70)
        if errors:
            print("VERIFICATION FAILED - Errors found")
            return 1
        else:
            print("VERIFICATION PASSED - N=1 TSB zones working correctly")
            return 0
        
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
