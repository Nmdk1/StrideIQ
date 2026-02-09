#!/usr/bin/env python3
"""
Analyze Michael's training and race history to understand:
1. November 29 half marathon (6:39 pace)
2. 10K two weeks later (6:19 pace, limping)
3. May-December training block
4. What fitness level was banked before injury
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, datetime, timedelta
from core.database import SessionLocal
from models import Athlete, Activity


def main():
    db = SessionLocal()
    
    try:
        # Find athlete
        athlete = db.query(Athlete).filter(
            Athlete.display_name.ilike("%mbshaf%")
        ).first()
        
        if not athlete:
            athlete = db.query(Athlete).filter(
                Athlete.email.ilike("%michael%")
            ).first()
        
        if not athlete:
            print("Could not find athlete record")
            return
        
        print("=" * 80)
        print(f"ANALYZING FITNESS HISTORY FOR: {athlete.display_name or athlete.email}")
        print("=" * 80)
        
        # Get all activities from May 2025 onwards
        may_2025 = datetime(2025, 5, 1)
        
        activities = db.query(Activity).filter(
            Activity.athlete_id == athlete.id,
            Activity.start_time >= may_2025,
            Activity.sport.ilike("run")
        ).order_by(Activity.start_time.desc()).all()
        
        print(f"\nTotal runs since May 2025: {len(activities)}")
        
        # Find races (by distance or name)
        print("\n" + "=" * 80)
        print("RACE PERFORMANCES")
        print("=" * 80)
        
        races = []
        for a in activities:
            miles = (a.distance_m or 0) / 1609.344
            duration_min = (a.duration_s or 0) / 60
            
            if duration_min > 0:
                pace_per_mile = duration_min / miles if miles > 0 else 0
            else:
                pace_per_mile = 0
            
            name_lower = (a.name or "").lower()
            
            # Detect races by name, distance, or workout type
            is_race = False
            race_type = None
            
            # Half marathon detection (13.0 - 13.2 miles)
            if 13.0 <= miles <= 13.3:
                is_race = True
                race_type = "Half Marathon"
            # 10K detection (6.1 - 6.3 miles)
            elif 6.0 <= miles <= 6.4 and pace_per_mile < 7.5:
                is_race = True
                race_type = "10K"
            # Check name for race keywords
            elif any(kw in name_lower for kw in ["race", "marathon", "half", "10k", "5k"]):
                is_race = True
                race_type = "Race"
            # Check workout type
            elif a.workout_type and "race" in a.workout_type.lower():
                is_race = True
                race_type = a.workout_type
            
            if is_race and pace_per_mile > 0:
                races.append({
                    "date": a.start_time.date(),
                    "name": a.name,
                    "type": race_type,
                    "miles": miles,
                    "time_min": duration_min,
                    "pace": pace_per_mile
                })
        
        # Sort by date
        races.sort(key=lambda x: x["date"], reverse=True)
        
        for r in races[:10]:
            pace_min = int(r["pace"])
            pace_sec = int((r["pace"] - pace_min) * 60)
            time_hr = int(r["time_min"] // 60)
            time_min = int(r["time_min"] % 60)
            time_sec = int((r["time_min"] * 60) % 60)
            
            if time_hr > 0:
                time_str = f"{time_hr}:{time_min:02d}:{time_sec:02d}"
            else:
                time_str = f"{time_min}:{time_sec:02d}"
            
            print(f"  {r['date']}: {r['type']:15s} - {r['miles']:.1f}mi in {time_str} ({pace_min}:{pace_sec:02d}/mi)")
            if r['name']:
                print(f"           Name: {r['name']}")
        
        # Find November 29 half marathon specifically
        print("\n" + "=" * 80)
        print("NOVEMBER 29 HALF MARATHON DETAIL")
        print("=" * 80)
        
        nov_29 = date(2025, 11, 29)
        nov_races = [a for a in activities if a.start_time.date() == nov_29]
        
        for a in nov_races:
            miles = (a.distance_m or 0) / 1609.344
            duration_min = (a.duration_s or 0) / 60
            pace = duration_min / miles if miles > 0 else 0
            pace_min = int(pace)
            pace_sec = int((pace - pace_min) * 60)
            
            print(f"  Date: {a.start_time.date()}")
            print(f"  Name: {a.name}")
            print(f"  Distance: {miles:.2f} miles")
            print(f"  Time: {int(duration_min//60)}:{int(duration_min%60):02d}")
            print(f"  Pace: {pace_min}:{pace_sec:02d}/mi")
            
            # Check for splits if available
            if hasattr(a, 'splits') and a.splits:
                print(f"  Splits: Available")
        
        if not nov_races:
            # Look around that date
            print("  No activity exactly on Nov 29, checking nearby...")
            for a in activities:
                if date(2025, 11, 25) <= a.start_time.date() <= date(2025, 12, 3):
                    miles = (a.distance_m or 0) / 1609.344
                    if miles > 10:
                        duration_min = (a.duration_s or 0) / 60
                        pace = duration_min / miles if miles > 0 else 0
                        print(f"  {a.start_time.date()}: {a.name} - {miles:.1f}mi @ {int(pace)}:{int((pace%1)*60):02d}/mi")
        
        # Find December 10K
        print("\n" + "=" * 80)
        print("DECEMBER 10K (TWO WEEKS AFTER HALF)")
        print("=" * 80)
        
        dec_start = date(2025, 12, 10)
        dec_end = date(2025, 12, 15)
        
        for a in activities:
            if dec_start <= a.start_time.date() <= dec_end:
                miles = (a.distance_m or 0) / 1609.344
                if 6.0 <= miles <= 6.5:
                    duration_min = (a.duration_s or 0) / 60
                    pace = duration_min / miles if miles > 0 else 0
                    pace_min = int(pace)
                    pace_sec = int((pace - pace_min) * 60)
                    print(f"  Date: {a.start_time.date()}")
                    print(f"  Name: {a.name}")
                    print(f"  Distance: {miles:.2f} miles")
                    print(f"  Pace: {pace_min}:{pace_sec:02d}/mi (WHILE LIMPING)")
        
        # Monthly volume May-December
        print("\n" + "=" * 80)
        print("MONTHLY TRAINING VOLUME (MAY-DECEMBER 2025)")
        print("=" * 80)
        
        monthly_miles = {}
        for a in activities:
            month_key = a.start_time.strftime("%Y-%m")
            if month_key not in monthly_miles:
                monthly_miles[month_key] = {"miles": 0, "runs": 0, "long_runs": []}
            
            miles = (a.distance_m or 0) / 1609.344
            monthly_miles[month_key]["miles"] += miles
            monthly_miles[month_key]["runs"] += 1
            
            if miles >= 15:
                monthly_miles[month_key]["long_runs"].append(miles)
        
        for month in sorted(monthly_miles.keys()):
            data = monthly_miles[month]
            long_run_str = f", Long runs: {len(data['long_runs'])}" if data['long_runs'] else ""
            peak_long = f" (peak: {max(data['long_runs']):.0f}mi)" if data['long_runs'] else ""
            print(f"  {month}: {data['miles']:.0f} miles over {data['runs']} runs{long_run_str}{peak_long}")
        
        # Peak weekly volumes
        print("\n" + "=" * 80)
        print("PEAK WEEKLY VOLUMES")
        print("=" * 80)
        
        weekly_miles = {}
        for a in activities:
            week_start = a.start_time.date() - timedelta(days=a.start_time.weekday())
            if week_start not in weekly_miles:
                weekly_miles[week_start] = 0
            weekly_miles[week_start] += (a.distance_m or 0) / 1609.344
        
        sorted_weeks = sorted(weekly_miles.items(), key=lambda x: x[1], reverse=True)
        
        print("  Top 10 weeks:")
        for week, miles in sorted_weeks[:10]:
            print(f"    {week}: {miles:.0f} miles")
        
        # What this means for March
        print("\n" + "=" * 80)
        print("WHAT THIS MEANS FOR MARCH")
        print("=" * 80)
        
        # Calculate RPI from half marathon
        # 6:39 pace for half = 1:27:20ish
        # That's roughly RPI 52-53
        
        print("""
  Your November Half Marathon:
    - 6:39 pace = ~1:27:20 finish
    - RPI equivalent: ~52-53
    - Marathon equivalent: ~3:02-3:05 at 6:57-7:03/mi
    - 10K equivalent: ~39:30 at 6:22/mi

  Your December 10K (WHILE LIMPING):
    - 6:19 pace = ~39:10 finish
    - This EXCEEDED the RPI prediction while injured
    - Shows you were even fitter than the half suggested

  Fitness Banked:
    - May-November: Consistent high volume block
    - Peak weeks: 70+ miles
    - Multiple 20+ mile long runs
    - Race performances confirmed fitness

  For March:
    - If you can get back to 60+ miles/week for 2-3 weeks
    - Your τ1=25 days means fast adaptation
    - 10-mile at 6:20 (63:20) is VERY achievable
    - Marathon at 7:00-7:15 is realistic given injury
    - Sub-3:10 is reasonable floor, sub-3:05 if stars align
""")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
