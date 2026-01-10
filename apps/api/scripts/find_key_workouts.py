"""
Find the key workouts that led to Michael's PRs.

PR1: November 29, 2025 - Half Marathon (7-min PR)
PR2: December 13, 2025 - 10K (3-min PR)

Looking for patterns in the 6-8 weeks before each race.
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
        # Get Michael's ID
        result = conn.execute(text("SELECT id FROM athlete WHERE display_name LIKE '%Michael%' LIMIT 1"))
        michael_id = result.scalar()
        
        print("=" * 80)
        print("FINDING KEY WORKOUTS LEADING TO PRs")
        print("=" * 80)
        
        # Define race dates
        half_pr_date = datetime(2025, 11, 29)
        tenk_pr_date = datetime(2025, 12, 13)
        
        # Get all activities in the 8 weeks before half PR (Oct 4 - Nov 29)
        result = conn.execute(text("""
            SELECT 
                id,
                sport,
                start_time,
                distance_m,
                duration_s,
                avg_hr,
                max_hr,
                total_elevation_gain,
                (distance_m / duration_s * 3.6) as speed_kph,
                (duration_s / 60.0) / (distance_m / 1000.0) as pace_min_km
            FROM activity 
            WHERE athlete_id = :id 
            AND start_time >= :start_date
            AND start_time < :end_date
            AND distance_m > 1000
            ORDER BY start_time
        """), {
            "id": michael_id, 
            "start_date": half_pr_date - timedelta(weeks=8),
            "end_date": half_pr_date
        })
        
        activities = []
        for row in result:
            activities.append({
                'id': row[0],
                'sport': row[1],
                'date': row[2],
                'distance_km': float(row[3]) / 1000,
                'duration_min': float(row[4]) / 60,
                'avg_hr': float(row[5]) if row[5] else None,
                'max_hr': float(row[6]) if row[6] else None,
                'elevation': float(row[7]) if row[7] else 0,
                'speed_kph': float(row[8]),
                'pace_min_km': float(row[9])
            })
        
        print(f"\n8 WEEKS BEFORE HALF MARATHON PR (Nov 29)")
        print(f"Period: {(half_pr_date - timedelta(weeks=8)).strftime('%Y-%m-%d')} to {half_pr_date.strftime('%Y-%m-%d')}")
        print(f"Total activities: {len(activities)}")
        print("-" * 80)
        
        # Classify workouts by likely type
        long_runs = []
        tempo_workouts = []
        interval_workouts = []
        easy_runs = []
        
        for a in activities:
            if a['avg_hr'] is None:
                continue
                
            # Estimate workout type
            # Long runs: > 90 min OR > 16km
            # Tempo: pace < 5:00/km and HR > 150 and duration > 20 min
            # Intervals: high HR variance (would need splits), high pace
            # Easy: everything else
            
            if a['duration_min'] > 90 or a['distance_km'] > 16:
                long_runs.append(a)
            elif a['pace_min_km'] < 5.0 and a['avg_hr'] and a['avg_hr'] > 140 and a['duration_min'] > 20:
                tempo_workouts.append(a)
            elif a['avg_hr'] and a['avg_hr'] > 155 and a['pace_min_km'] < 4.5:
                interval_workouts.append(a)
            else:
                easy_runs.append(a)
        
        print(f"\nWORKOUT BREAKDOWN:")
        print(f"  Long runs (>90min or >16km): {len(long_runs)}")
        print(f"  Likely tempo/threshold: {len(tempo_workouts)}")
        print(f"  Likely intervals/speed: {len(interval_workouts)}")
        print(f"  Easy/other: {len(easy_runs)}")
        
        # Show long runs
        print(f"\n--- LONG RUNS ---")
        for a in sorted(long_runs, key=lambda x: x['date']):
            hr_str = f"HR:{a['avg_hr']:.0f}" if a['avg_hr'] else "HR:N/A"
            print(f"  {a['date'].strftime('%m/%d')} | {a['distance_km']:.1f}km | {a['duration_min']:.0f}min | {a['pace_min_km']:.2f}/km | {hr_str}")
        
        # Show tempo workouts
        print(f"\n--- TEMPO / THRESHOLD WORKOUTS ---")
        for a in sorted(tempo_workouts, key=lambda x: x['date']):
            hr_str = f"HR:{a['avg_hr']:.0f}" if a['avg_hr'] else "HR:N/A"
            print(f"  {a['date'].strftime('%m/%d')} | {a['distance_km']:.1f}km | {a['duration_min']:.0f}min | {a['pace_min_km']:.2f}/km | {hr_str}")
        
        # Show interval workouts
        print(f"\n--- INTERVAL / SPEED WORKOUTS ---")
        for a in sorted(interval_workouts, key=lambda x: x['date']):
            hr_str = f"HR:{a['avg_hr']:.0f}" if a['avg_hr'] else "HR:N/A"
            print(f"  {a['date'].strftime('%m/%d')} | {a['distance_km']:.1f}km | {a['duration_min']:.0f}min | {a['pace_min_km']:.2f}/km | {hr_str}")
        
        # Weekly summary
        print(f"\n--- WEEKLY VOLUME & QUALITY ---")
        weekly = defaultdict(lambda: {'km': 0, 'runs': 0, 'long': 0, 'quality': 0})
        for a in activities:
            week_key = a['date'].strftime('%Y-W%W')
            weekly[week_key]['km'] += a['distance_km']
            weekly[week_key]['runs'] += 1
            if a in long_runs:
                weekly[week_key]['long'] += 1
            if a in tempo_workouts or a in interval_workouts:
                weekly[week_key]['quality'] += 1
        
        for week in sorted(weekly.keys()):
            w = weekly[week]
            bar = '█' * int(w['km'] / 5)
            print(f"  {week}: {w['km']:5.1f}km | {w['runs']} runs | {w['long']} long | {w['quality']} quality | {bar}")
        
        # Find standout workouts
        print(f"\n--- STANDOUT WORKOUTS (by pace + HR combo) ---")
        # Best efficiency (fastest pace at reasonable HR)
        quality_runs = [a for a in activities if a['avg_hr'] and a['avg_hr'] > 130 and a['distance_km'] > 5]
        if quality_runs:
            quality_runs.sort(key=lambda x: x['pace_min_km'])
            print("\nFastest quality runs:")
            for a in quality_runs[:10]:
                print(f"  {a['date'].strftime('%m/%d')} | {a['distance_km']:.1f}km @ {a['pace_min_km']:.2f}/km | HR:{a['avg_hr']:.0f}")
        
        # Find the race itself
        print(f"\n--- THE RACE (Nov 29) ---")
        result = conn.execute(text("""
            SELECT sport, distance_m, duration_s, avg_hr, max_hr,
                   (duration_s / 60.0) / (distance_m / 1000.0) as pace_min_km
            FROM activity 
            WHERE athlete_id = :id 
            AND start_time::date = :race_date
            ORDER BY distance_m DESC
            LIMIT 1
        """), {"id": michael_id, "race_date": half_pr_date.date()})
        
        race = result.fetchone()
        if race:
            print(f"  Sport: {race[0]}")
            print(f"  Distance: {race[1]/1000:.2f} km")
            print(f"  Time: {race[2]/60:.1f} min ({int(race[2]//3600)}:{int((race[2]%3600)//60):02d}:{int(race[2]%60):02d})")
            print(f"  Pace: {race[5]:.2f} min/km")
            print(f"  Avg HR: {race[3]:.0f}" if race[3] else "  Avg HR: N/A")
        
        # Look at progression of similar workouts
        print(f"\n--- WORKOUT PROGRESSION PATTERNS ---")
        print("(Looking for improvements in same-type workouts over time)")
        
        # Group by approximate distance buckets
        dist_buckets = defaultdict(list)
        for a in activities:
            if a['avg_hr'] and a['avg_hr'] > 130:  # Quality runs only
                if 8 <= a['distance_km'] <= 12:
                    dist_buckets['8-12km quality'].append(a)
                elif 12 < a['distance_km'] <= 18:
                    dist_buckets['12-18km quality'].append(a)
                elif a['distance_km'] > 18:
                    dist_buckets['18km+ long'].append(a)
        
        for bucket, runs in dist_buckets.items():
            if len(runs) >= 2:
                runs.sort(key=lambda x: x['date'])
                first = runs[0]
                last = runs[-1]
                pace_change = last['pace_min_km'] - first['pace_min_km']
                print(f"\n  {bucket}:")
                print(f"    First: {first['date'].strftime('%m/%d')} @ {first['pace_min_km']:.2f}/km HR:{first['avg_hr']:.0f}")
                print(f"    Last:  {last['date'].strftime('%m/%d')} @ {last['pace_min_km']:.2f}/km HR:{last['avg_hr']:.0f}")
                print(f"    Pace change: {pace_change:+.2f} min/km ({'FASTER' if pace_change < 0 else 'SLOWER'})")
        
        # Summary
        print("\n" + "=" * 80)
        print("ANALYSIS SUMMARY")
        print("=" * 80)
        
        total_km = sum(a['distance_km'] for a in activities)
        total_runs = len(activities)
        weeks = 8
        
        print(f"\n8-WEEK BUILD STATS:")
        print(f"  Total volume: {total_km:.0f} km")
        print(f"  Weekly average: {total_km/weeks:.0f} km/week")
        print(f"  Total runs: {total_runs}")
        print(f"  Runs per week: {total_runs/weeks:.1f}")
        print(f"  Long runs: {len(long_runs)}")
        print(f"  Quality sessions: {len(tempo_workouts) + len(interval_workouts)}")
        
        print("\n" + "=" * 80)

if __name__ == "__main__":
    main()

