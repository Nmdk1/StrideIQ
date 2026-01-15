#!/usr/bin/env python3
"""
TEST PLAN GENERATION WITH REAL ATHLETE DATA
=============================================

This test uses actual athlete data from the database to verify
that plans are properly scaled to the athlete's established baseline.

A 55-70 mpw runner should NOT get 10-15 mile long runs!
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta
from uuid import UUID
import logging

# Setup database connection
from core.database import SessionLocal
from models import Athlete, Activity
from services.model_driven_plan_generator import generate_model_driven_plan

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_athlete_stats(db, athlete_id):
    """Get detailed stats about an athlete's training history."""
    from datetime import datetime
    
    end_date = date.today()
    year_ago = end_date - timedelta(days=365)
    
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.start_time >= datetime.combine(year_ago, datetime.min.time()),
        Activity.sport.ilike("run")
    ).all()
    
    if not activities:
        return None
    
    # Calculate weekly mileage
    weekly_miles = {}
    long_runs = []
    
    for activity in activities:
        week_start = activity.start_time.date() - timedelta(days=activity.start_time.weekday())
        miles = (activity.distance_m or 0) / 1609.344
        
        if week_start not in weekly_miles:
            weekly_miles[week_start] = 0
        weekly_miles[week_start] += miles
        
        # Track long runs
        duration_min = (activity.duration_s or 0) / 60
        if miles >= 10 or duration_min >= 90:
            long_runs.append(miles)
    
    if not weekly_miles:
        return None
    
    # Split by time period
    recent_cutoff = end_date - timedelta(days=42)
    baseline_end = end_date - timedelta(days=90)
    
    baseline_weeks = [m for ws, m in weekly_miles.items() if ws <= baseline_end]
    recent_weeks = [m for ws, m in weekly_miles.items() if ws >= recent_cutoff]
    
    return {
        "total_activities": len(activities),
        "total_weeks_with_data": len(weekly_miles),
        "all_weeks": sorted(weekly_miles.values()),
        "baseline_weeks": baseline_weeks,
        "recent_weeks": recent_weeks,
        "baseline_avg": sum(baseline_weeks) / len(baseline_weeks) if baseline_weeks else 0,
        "recent_avg": sum(recent_weeks) / len(recent_weeks) if recent_weeks else 0,
        "long_runs": sorted(long_runs) if long_runs else [],
        "longest_run": max(long_runs) if long_runs else 0,
        "typical_long_run": sorted(long_runs)[int(len(long_runs) * 0.75)] if long_runs else 0,
    }


def test_real_athlete():
    """Test plan generation with real athlete data."""
    db = SessionLocal()
    
    try:
        # Find athletes with significant training history
        athletes = db.query(Athlete).all()
        
        print("=" * 70)
        print("TESTING WITH REAL ATHLETE DATA")
        print("=" * 70)
        
        if not athletes:
            print("No athletes found in database!")
            return
        
        print(f"\nFound {len(athletes)} athletes")
        
        for athlete in athletes:
            print(f"\n{'='*60}")
            print(f"ATHLETE: {athlete.display_name or athlete.email or str(athlete.id)[:8]}")
            print(f"{'='*60}")
            
            stats = get_athlete_stats(db, athlete.id)
            
            if not stats:
                print("  No training data found")
                continue
            
            print(f"\n📊 TRAINING HISTORY ANALYSIS (Last 12 Months)")
            print(f"  Total activities: {stats['total_activities']}")
            print(f"  Weeks with data: {stats['total_weeks_with_data']}")
            print(f"  Baseline avg (3-12mo ago): {stats['baseline_avg']:.1f} mpw")
            print(f"  Recent avg (last 6 weeks): {stats['recent_avg']:.1f} mpw")
            
            if stats['baseline_avg'] > 0 and stats['recent_avg'] > 0:
                drop_pct = (stats['baseline_avg'] - stats['recent_avg']) / stats['baseline_avg'] * 100
                if drop_pct > 30:
                    print(f"  ⚠️  DETECTED: {drop_pct:.0f}% volume drop - returning from break")
                else:
                    print(f"  Volume change: {-drop_pct:+.0f}%")
            
            if stats['long_runs']:
                print(f"\n🏃 LONG RUN HISTORY")
                print(f"  Longest run: {stats['longest_run']:.1f} miles")
                print(f"  Typical long run (P75): {stats['typical_long_run']:.1f} miles")
                print(f"  Long run count: {len(stats['long_runs'])}")
            
            # Generate plan
            print(f"\n📋 GENERATING MARATHON PLAN...")
            race_date = date.today() + timedelta(days=16 * 7)  # 16 weeks out
            
            try:
                plan = generate_model_driven_plan(
                    athlete_id=athlete.id,
                    race_date=race_date,
                    race_distance="marathon",
                    db=db
                )
                
                print(f"\n✅ PLAN GENERATED")
                print(f"  Total weeks: {plan.total_weeks}")
                print(f"  Total miles: {plan.total_miles:.1f}")
                print(f"  τ1: {plan.tau1:.1f}d, τ2: {plan.tau2:.1f}d")
                print(f"  Model confidence: {plan.model_confidence}")
                
                # Find peak long run in plan
                peak_long = 0
                for week in plan.weeks:
                    for day in week.days:
                        if day.workout_type == "long_run":
                            peak_long = max(peak_long, day.target_miles or 0)
                
                print(f"\n📏 LONG RUN ANALYSIS")
                print(f"  Peak long run in plan: {peak_long:.1f} miles")
                print(f"  Athlete's typical long: {stats['typical_long_run']:.1f} miles")
                
                if stats['typical_long_run'] > 0:
                    if peak_long < stats['typical_long_run'] * 0.8:
                        print(f"  ⚠️  PROBLEM: Plan long run ({peak_long:.1f}) is too short!")
                        print(f"      Should be at least {stats['typical_long_run'] * 0.9:.1f}mi")
                    else:
                        print(f"  ✅ Plan appropriately scaled to athlete baseline")
                
                # Show counter-conventional notes
                print(f"\n💡 PERSONALIZED INSIGHTS")
                for note in (plan.counter_conventional_notes or []):
                    print(f"  • {note}")
                
                # Show sample peak week
                peak_weeks = [w for w in plan.weeks if w.phase == "peak"]
                if peak_weeks:
                    print(f"\n📅 SAMPLE PEAK WEEK (Week {peak_weeks[0].week_number})")
                    for day in peak_weeks[0].days:
                        if day.workout_type != "rest":
                            print(f"  {day.day_of_week}: {day.name} ({day.target_miles:.1f}mi)")
                
            except Exception as e:
                print(f"  ERROR: {e}")
                import traceback
                traceback.print_exc()
        
    finally:
        db.close()


if __name__ == "__main__":
    test_real_athlete()
