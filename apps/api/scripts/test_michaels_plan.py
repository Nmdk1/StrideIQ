#!/usr/bin/env python3
"""
Test plan generation specifically for Michael (mbshaf) - the 55-70 mpw runner.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta
from core.database import SessionLocal
from models import Athlete, Activity
from services.model_driven_plan_generator import generate_model_driven_plan


def main():
    db = SessionLocal()
    
    try:
        # Find Michael's athlete record
        athlete = db.query(Athlete).filter(
            Athlete.display_name.ilike("%mbshaf%")
        ).first()
        
        if not athlete:
            # Try email
            athlete = db.query(Athlete).filter(
                Athlete.email.ilike("%michael%")
            ).first()
        
        if not athlete:
            print("Could not find Michael's athlete record")
            return
        
        print("=" * 70)
        print(f"TESTING PLAN FOR: {athlete.display_name or athlete.email}")
        print("=" * 70)
        
        # Get training history stats
        from datetime import datetime
        end_date = date.today()
        year_ago = end_date - timedelta(days=365)
        
        activities = db.query(Activity).filter(
            Activity.athlete_id == athlete.id,
            Activity.start_time >= datetime.combine(year_ago, datetime.min.time()),
            Activity.sport.ilike("run")
        ).all()
        
        print(f"\n📊 TRAINING HISTORY")
        print(f"  Total runs in past year: {len(activities)}")
        
        # Calculate weekly volumes
        weekly_miles = {}
        long_runs = []
        
        for activity in activities:
            week_start = activity.start_time.date() - timedelta(days=activity.start_time.weekday())
            miles = (activity.distance_m or 0) / 1609.344
            
            if week_start not in weekly_miles:
                weekly_miles[week_start] = 0
            weekly_miles[week_start] += miles
            
            if miles >= 10:
                long_runs.append(miles)
        
        # Split baseline vs recent
        recent_cutoff = end_date - timedelta(days=42)
        baseline_end = end_date - timedelta(days=90)
        
        baseline_weeks = [m for ws, m in weekly_miles.items() if ws <= baseline_end]
        recent_weeks = [m for ws, m in weekly_miles.items() if ws >= recent_cutoff]
        
        if baseline_weeks:
            baseline_avg = sum(baseline_weeks) / len(baseline_weeks)
            baseline_p75 = sorted(baseline_weeks)[int(len(baseline_weeks) * 0.75)]
            print(f"  Baseline (3-12mo ago):")
            print(f"    - Average: {baseline_avg:.1f} mpw")
            print(f"    - P75: {baseline_p75:.1f} mpw")
            print(f"    - Peak: {max(baseline_weeks):.1f} mpw")
        
        if recent_weeks:
            recent_avg = sum(recent_weeks) / len(recent_weeks)
            print(f"  Recent (last 6 weeks):")
            print(f"    - Average: {recent_avg:.1f} mpw")
        
        if long_runs:
            long_runs.sort()
            p75_idx = int(len(long_runs) * 0.75)
            print(f"\n🏃 LONG RUNS")
            print(f"  Longest: {max(long_runs):.1f} miles")
            print(f"  Typical (P75): {long_runs[p75_idx]:.1f} miles")
            print(f"  Count: {len(long_runs)}")
        
        # Detect MP long runs
        mp_long_runs = []
        for activity in activities:
            miles = (activity.distance_m or 0) / 1609.344
            if miles >= 13:
                name_lower = (activity.name or "").lower()
                workout_type = (activity.workout_type or "").lower()
                if any(mp in name_lower for mp in ["mp", "marathon pace", "race pace", "goal pace"]):
                    mp_long_runs.append(miles)
                elif workout_type in ("tempo", "race_pace", "threshold"):
                    mp_long_runs.append(miles)
        
        if mp_long_runs:
            print(f"\n🏃 MARATHON-SPECIFIC WORK (MP Long Runs)")
            print(f"  Longest MP long run: {max(mp_long_runs):.1f} miles")
            print(f"  Count: {len(mp_long_runs)}")
        
        # Generate marathon plan
        print(f"\n" + "=" * 70)
        print("GENERATING 16-WEEK MARATHON PLAN")
        print("=" * 70)
        
        race_date = date.today() + timedelta(days=16 * 7)
        
        plan = generate_model_driven_plan(
            athlete_id=athlete.id,
            race_date=race_date,
            race_distance="marathon",
            db=db
        )
        
        print(f"\n📋 PLAN SUMMARY")
        print(f"  Total weeks: {plan.total_weeks}")
        print(f"  Total miles: {plan.total_miles:.1f}")
        print(f"  Model: τ1={plan.tau1:.1f}d, τ2={plan.tau2:.1f}d ({plan.model_confidence})")
        
        # Find all long runs in plan
        print(f"\n🏃 LONG RUN PROGRESSION IN PLAN")
        for week in plan.weeks:
            for day in week.days:
                if day.workout_type == "long_run":
                    print(f"  Week {week.week_number:2d} ({week.phase:6s}): {day.target_miles:.1f}mi - {day.name}")
        
        # Key metrics
        all_long_runs = []
        for week in plan.weeks:
            for day in week.days:
                if day.workout_type == "long_run":
                    all_long_runs.append(day.target_miles or 0)
        
        print(f"\n📏 LONG RUN ANALYSIS")
        print(f"  Peak long run in plan: {max(all_long_runs):.1f} miles")
        print(f"  Athlete's longest historical: {max(long_runs):.1f} miles")
        
        if max(all_long_runs) >= 20:
            print(f"  ✅ Plan includes proper 20+ mile long run for marathon prep")
        else:
            print(f"  ⚠️ ISSUE: Peak long run of {max(all_long_runs):.1f}mi may be too short")
            print(f"      Expected: 20+ miles for a {baseline_avg:.0f} mpw runner")
        
        # Show personalization
        print(f"\n💡 PERSONALIZED INSIGHTS")
        for note in (plan.counter_conventional_notes or []):
            print(f"  • {note}")
        
        # Show sample peak week
        peak_weeks = [w for w in plan.weeks if w.phase == "peak"]
        if peak_weeks:
            pw = peak_weeks[-1]  # Last peak week
            print(f"\n📅 PEAK WEEK SAMPLE (Week {pw.week_number})")
            print(f"  Target: {pw.target_miles:.1f} miles, TSS: {pw.target_tss:.0f}")
            for day in pw.days:
                if day.workout_type != "rest":
                    print(f"  {day.day_of_week}: {day.name} ({day.target_miles:.1f}mi)")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
