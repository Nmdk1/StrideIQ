#!/usr/bin/env python3
"""
Test script for Performance Physics Engine features.
Tests age category classification and derived signals calculation.
"""
import sys
from database import SessionLocal
from models import Athlete
from services.performance_engine import get_age_category, calculate_age_at_date
from services.athlete_metrics import calculate_athlete_derived_signals
from datetime import datetime

def test_age_categories():
    """Test age category classification"""
    print("=" * 60)
    print("Testing Age Category Classification")
    print("=" * 60)
    
    test_ages = [30, 35, 40, 50, 60, 70, 80, 90, 100]
    for age in test_ages:
        category = get_age_category(age)
        print(f"  Age {age:3d}: {category}")
    
    print("\n✅ Age category classification test complete\n")

def test_derived_signals():
    """Test derived signals calculation"""
    print("=" * 60)
    print("Testing Derived Signals Calculation")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        athlete = db.query(Athlete).first()
        if not athlete:
            print("❌ No athlete found in database")
            return False
        
        print(f"\n✓ Found athlete: {athlete.id}")
        if athlete.birthdate:
            age = calculate_age_at_date(athlete.birthdate, datetime.now())
            category = get_age_category(age) if age else None
            print(f"  Age: {age}, Category: {category}")
        
        print("\n🔄 Calculating derived signals...")
        metrics = calculate_athlete_derived_signals(athlete, db, force_recalculate=True)
        
        print("\n📊 Derived Signals Results:")
        print(f"  Durability Index: {metrics.get('durability_index')}")
        print(f"  Recovery Half-Life: {metrics.get('recovery_half_life_hours')} hours")
        print(f"  Consistency Index: {metrics.get('consistency_index')}")
        
        print("\n✅ Derived signals calculation test complete")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("PERFORMANCE PHYSICS ENGINE TEST SUITE")
    print("=" * 60 + "\n")
    
    test_age_categories()
    success = test_derived_signals()
    
    sys.exit(0 if success else 1)


