"""
Analyze May-September 2025: The Base Building Phase

Looking for:
- Saturday intervals + Sunday long runs pattern
- Long runs with elevation (in MS summer heat)
- The 5K PR that popped "out of nowhere"
"""
from sqlalchemy import create_engine, text
import os
from datetime import datetime, timedelta
from collections import defaultdict

def main():
    user = os.environ.get('POSTGRES_USER', 'postgres')
    password = os.environ.get('POSTGRES_PASSWORD', 'postgres')
    host = os.environ.get('POSTGRES_HOST', 'postgres')
    db = os.environ.get('POSTGRES_DB', 'running_app')
    db_url = f'postgresql://{user}:{password}@{host}:5432/{db}'
    
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id FROM athlete WHERE display_name LIKE '%Michael%' LIMIT 1"))
        michael_id = result.scalar()
        
        print("=" * 80)
        print("BASE BUILDING PHASE: May - September 2025")
        print("(The Foundation for the Fall PRs)")
        print("=" * 80)
        
        # May 1 to September 30, 2025
        start_date = datetime(2025, 5, 1)
        end_date = datetime(2025, 10, 1)
        
        result = conn.execute(text("""
            SELECT 
                start_time,
                distance_m,
                duration_s,
                avg_hr,
                max_hr,
                total_elevation_gain,
                (distance_m / duration_s * 3.6) as speed_kph,
                (duration_s / 60.0) / (distance_m / 1000.0) as pace_min_km,
                EXTRACT(DOW FROM start_time) as day_of_week
            FROM activity 
            WHERE athlete_id = :id 
            AND start_time >= :start_date
            AND start_time < :end_date
            AND distance_m > 1000
            ORDER BY start_time
        """), {"id": michael_id, "start_date": start_date, "end_date": end_date})
        
        runs = []
        for row in result:
            runs.append({
                'date': row[0],
                'distance_km': float(row[1]) / 1000,
                'duration_min': float(row[2]) / 60,
                'avg_hr': float(row[3]) if row[3] else None,
                'max_hr': float(row[4]) if row[4] else None,
                'elevation': float(row[5]) if row[5] else 0,
                'speed_kph': float(row[6]),
                'pace_min_km': float(row[7]),
                'day_of_week': int(row[8]),  # 0=Sunday, 6=Saturday
                'day_name': ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][int(row[8])]
            })
        
        print(f"\nTotal runs: {len(runs)}")
        print(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        # Find Saturday/Sunday patterns
        print("\n" + "=" * 80)
        print("SATURDAY + SUNDAY PATTERN")
        print("=" * 80)
        
        # Group by week
        weekly = defaultdict(list)
        for r in runs:
            week_start = r['date'] - timedelta(days=r['date'].weekday())
            week_key = week_start.strftime('%Y-W%W')
            weekly[week_key].append(r)
        
        sat_sun_pattern = []
        for week in sorted(weekly.keys()):
            week_runs = weekly[week]
            saturday = [r for r in week_runs if r['day_of_week'] == 6]  # Saturday
            sunday = [r for r in week_runs if r['day_of_week'] == 0]   # Sunday
            
            if saturday and sunday:
                sat_run = saturday[0]
                sun_run = sunday[0]
                
                # Classify Saturday run
                sat_type = "EASY"
                if sat_run['avg_hr'] and sat_run['avg_hr'] > 150:
                    sat_type = "INTERVAL/SPEED"
                elif sat_run['avg_hr'] and sat_run['avg_hr'] > 140 and sat_run['pace_min_km'] < 5.0:
                    sat_type = "TEMPO"
                
                # Sunday is usually long run
                sun_type = "LONG" if sun_run['distance_km'] > 15 else "MEDIUM-LONG" if sun_run['distance_km'] > 10 else "EASY"
                
                sat_sun_pattern.append({
                    'week': week,
                    'sat': sat_run,
                    'sat_type': sat_type,
                    'sun': sun_run,
                    'sun_type': sun_type
                })
        
        print(f"\nWeeks with Saturday + Sunday runs: {len(sat_sun_pattern)}")
        print("\nPattern (Sat → Sun):")
        for p in sat_sun_pattern:
            sat = p['sat']
            sun = p['sun']
            elev_str = f" ↑{sun['elevation']:.0f}m" if sun['elevation'] > 50 else ""
            sat_hr = f"{sat['avg_hr']:.0f}" if sat['avg_hr'] else "N/A"
            print(f"  {p['week']}: {p['sat_type']:12} ({sat['distance_km']:.0f}km, {sat['pace_min_km']:.1f}/km, HR:{sat_hr}) → {p['sun_type']:10} ({sun['distance_km']:.0f}km, {sun['pace_min_km']:.1f}/km{elev_str})")
        
        # Count pattern types
        interval_then_long = [p for p in sat_sun_pattern if 'INTERVAL' in p['sat_type'] and 'LONG' in p['sun_type']]
        print(f"\n'Interval Saturday → Long Sunday' pattern: {len(interval_then_long)} weeks")
        
        # Elevation analysis
        print("\n" + "=" * 80)
        print("ELEVATION IN LONG RUNS")
        print("=" * 80)
        
        long_runs = [r for r in runs if r['distance_km'] > 15]
        long_runs.sort(key=lambda x: x['elevation'], reverse=True)
        
        print(f"\nLong runs (>15km) with most elevation:")
        for r in long_runs[:15]:
            hr_str = f"HR:{r['avg_hr']:.0f}" if r['avg_hr'] else "HR:N/A"
            print(f"  {r['date'].strftime('%m/%d %a')} | {r['distance_km']:.0f}km | {r['pace_min_km']:.1f}/km | {hr_str} | ↑{r['elevation']:.0f}m")
        
        avg_elev = sum(r['elevation'] for r in long_runs) / len(long_runs) if long_runs else 0
        print(f"\nAverage elevation in long runs: {avg_elev:.0f}m")
        
        # Look for the 5K PR
        print("\n" + "=" * 80)
        print("LOOKING FOR THE 5K PR")
        print("=" * 80)
        
        # Find short, fast runs (likely races or time trials)
        fast_short = [r for r in runs if 4.5 <= r['distance_km'] <= 5.5 and r['pace_min_km'] < 4.5]
        fast_short.sort(key=lambda x: x['pace_min_km'])
        
        print("\nPossible 5K races/TTs (4.5-5.5km at <4.5/km):")
        for r in fast_short:
            hr_str = f"HR:{r['avg_hr']:.0f}" if r['avg_hr'] else "HR:N/A"
            time_str = f"{int(r['duration_min'])}:{int((r['duration_min'] % 1) * 60):02d}"
            print(f"  {r['date'].strftime('%m/%d %a')} | {r['distance_km']:.2f}km | {time_str} | {r['pace_min_km']:.2f}/km | {hr_str}")
        
        # Also check for any 5K-ish distances with max effort
        all_5k_ish = [r for r in runs if 4.8 <= r['distance_km'] <= 5.3]
        all_5k_ish.sort(key=lambda x: x['pace_min_km'])
        
        print(f"\nAll ~5K runs (4.8-5.3km) sorted by pace:")
        for r in all_5k_ish[:10]:
            hr_str = f"HR:{r['avg_hr']:.0f}" if r['avg_hr'] else "HR:N/A"
            time_str = f"{int(r['duration_min'])}:{int((r['duration_min'] % 1) * 60):02d}"
            print(f"  {r['date'].strftime('%m/%d %a')} | {r['distance_km']:.2f}km | {time_str} | {r['pace_min_km']:.2f}/km | {hr_str}")
        
        # Volume and intensity by month
        print("\n" + "=" * 80)
        print("MONTHLY SUMMARY")
        print("=" * 80)
        
        monthly = defaultdict(lambda: {'km': 0, 'runs': 0, 'long': 0, 'quality': 0, 'elevation': 0})
        for r in runs:
            month_key = r['date'].strftime('%Y-%m')
            monthly[month_key]['km'] += r['distance_km']
            monthly[month_key]['runs'] += 1
            monthly[month_key]['elevation'] += r['elevation']
            if r['distance_km'] > 15:
                monthly[month_key]['long'] += 1
            if r['avg_hr'] and r['avg_hr'] > 150:
                monthly[month_key]['quality'] += 1
        
        for month in sorted(monthly.keys()):
            m = monthly[month]
            bar = '█' * int(m['km'] / 20)
            print(f"  {month}: {m['km']:6.0f}km | {m['runs']:2} runs | {m['long']:2} long | {m['quality']:2} quality | ↑{m['elevation']:5.0f}m | {bar}")
        
        # Weekly volume trend
        print("\n" + "=" * 80)
        print("WEEKLY VOLUME TREND")
        print("=" * 80)
        
        for week in sorted(weekly.keys()):
            week_runs = weekly[week]
            total_km = sum(r['distance_km'] for r in week_runs)
            total_elev = sum(r['elevation'] for r in week_runs)
            quality = len([r for r in week_runs if r['avg_hr'] and r['avg_hr'] > 150])
            bar = '█' * int(total_km / 5)
            print(f"  {week}: {total_km:5.0f}km | {len(week_runs)} runs | {quality} quality | ↑{total_elev:4.0f}m | {bar}")
        
        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY: BASE BUILDING PHASE")
        print("=" * 80)
        
        total_km = sum(r['distance_km'] for r in runs)
        total_elev = sum(r['elevation'] for r in runs)
        weeks_count = len(weekly)
        quality_sessions = len([r for r in runs if r['avg_hr'] and r['avg_hr'] > 150])
        
        print(f"""
Total Volume: {total_km:.0f} km over {weeks_count} weeks ({total_km/weeks_count:.0f} km/week avg)
Total Runs: {len(runs)}
Total Elevation: {total_elev:.0f} m ({total_elev/weeks_count:.0f} m/week avg)
Quality Sessions (HR>150): {quality_sessions}
Long Runs (>15km): {len(long_runs)}
Saturday→Sunday patterns: {len(sat_sun_pattern)}
Interval→Long weekends: {len(interval_then_long)}

KEY INSIGHT:
Building aerobic base through:
- High volume in Mississippi summer heat
- Weekend structure: Intervals Saturday → Long run Sunday
- Long runs with significant elevation
- This laid the foundation for the fall build
""")
        
        print("=" * 80)

if __name__ == "__main__":
    main()

