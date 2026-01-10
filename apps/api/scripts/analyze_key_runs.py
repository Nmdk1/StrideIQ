"""
Deep analysis of key workouts that led to Michael's half marathon PR.

The initial analysis shows:
- 99 km/week average
- 19 long runs in 8 weeks
- Only 4 tempo sessions
- NO interval work!
- Long run pace improved from 5.75/km to 4.73/km (1+ min/km faster!)

Let's find the specific breakthrough moments.
"""
from sqlalchemy import create_engine, text
import os
from datetime import datetime, timedelta

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
        print("DEEP ANALYSIS: WHAT LED TO THE PR")
        print("=" * 80)
        
        half_pr_date = datetime(2025, 11, 29)
        
        # Get all runs with splits info
        result = conn.execute(text("""
            SELECT 
                start_time,
                distance_m,
                duration_s,
                avg_hr,
                max_hr,
                (distance_m / duration_s * 3.6) as speed_kph,
                (duration_s / 60.0) / (distance_m / 1000.0) as pace_min_km
            FROM activity 
            WHERE athlete_id = :id 
            AND start_time >= :start_date
            AND start_time < :end_date
            AND distance_m > 5000
            AND avg_hr IS NOT NULL
            ORDER BY start_time
        """), {
            "id": michael_id, 
            "start_date": half_pr_date - timedelta(weeks=8),
            "end_date": half_pr_date
        })
        
        runs = []
        for row in result:
            runs.append({
                'date': row[0],
                'distance_km': float(row[1]) / 1000,
                'duration_min': float(row[2]) / 60,
                'avg_hr': float(row[3]),
                'max_hr': float(row[4]) if row[4] else None,
                'speed_kph': float(row[5]),
                'pace_min_km': float(row[6]),
                'efficiency': float(row[5]) / float(row[3])  # speed/HR
            })
        
        print(f"\nTotal qualifying runs (>5km with HR): {len(runs)}")
        
        # KEY FINDING 1: Long run progression
        print("\n" + "=" * 80)
        print("KEY FINDING 1: LONG RUN PROGRESSION")
        print("=" * 80)
        long_runs = [r for r in runs if r['distance_km'] > 18]
        long_runs.sort(key=lambda x: x['date'])
        
        print(f"\nRuns over 18km:")
        for r in long_runs:
            print(f"  {r['date'].strftime('%m/%d')} | {r['distance_km']:.1f}km | {r['pace_min_km']:.2f}/km | HR:{r['avg_hr']:.0f} | eff:{r['efficiency']:.4f}")
        
        if len(long_runs) >= 2:
            first_5 = long_runs[:5]
            last_5 = long_runs[-5:]
            early_pace = sum(r['pace_min_km'] for r in first_5) / len(first_5)
            late_pace = sum(r['pace_min_km'] for r in last_5) / len(last_5)
            print(f"\nFirst 5 long runs avg pace: {early_pace:.2f}/km")
            print(f"Last 5 long runs avg pace: {late_pace:.2f}/km")
            print(f"Improvement: {early_pace - late_pace:.2f} min/km FASTER")
        
        # KEY FINDING 2: Tempo consistency
        print("\n" + "=" * 80)
        print("KEY FINDING 2: TEMPO/THRESHOLD SESSIONS")
        print("=" * 80)
        
        # Tempo runs: 5-12km, pace < 4.5/km, HR > 150
        tempo_runs = [r for r in runs if 5 < r['distance_km'] < 12 and r['pace_min_km'] < 4.5 and r['avg_hr'] > 140]
        tempo_runs.sort(key=lambda x: x['date'])
        
        print(f"\nLikely tempo sessions (5-12km, <4.5/km, HR>140):")
        for r in tempo_runs:
            print(f"  {r['date'].strftime('%m/%d')} | {r['distance_km']:.1f}km | {r['pace_min_km']:.2f}/km | HR:{r['avg_hr']:.0f}")
        
        if len(tempo_runs) >= 2:
            first_tempo = tempo_runs[0]
            last_tempo = tempo_runs[-1]
            print(f"\nFirst tempo: {first_tempo['pace_min_km']:.2f}/km @ HR {first_tempo['avg_hr']:.0f}")
            print(f"Last tempo: {last_tempo['pace_min_km']:.2f}/km @ HR {last_tempo['avg_hr']:.0f}")
        
        # KEY FINDING 3: Fast finish long runs / workout long runs
        print("\n" + "=" * 80)
        print("KEY FINDING 3: FAST LONG RUNS (WORKOUT LONG RUNS)")
        print("=" * 80)
        
        # Fast long runs: > 15km at < 4.8/km pace
        fast_long = [r for r in runs if r['distance_km'] > 15 and r['pace_min_km'] < 4.8]
        fast_long.sort(key=lambda x: x['date'])
        
        print(f"\nFast long runs (>15km at <4.8/km):")
        for r in fast_long:
            print(f"  {r['date'].strftime('%m/%d')} | {r['distance_km']:.1f}km | {r['pace_min_km']:.2f}/km | HR:{r['avg_hr']:.0f}")
        
        # KEY FINDING 4: Weekly structure
        print("\n" + "=" * 80)
        print("KEY FINDING 4: WEEKLY PATTERN")
        print("=" * 80)
        
        from collections import defaultdict
        weekly = defaultdict(list)
        for r in runs:
            week = r['date'].strftime('%Y-W%W')
            weekly[week].append(r)
        
        for week in sorted(weekly.keys()):
            week_runs = weekly[week]
            total_km = sum(r['distance_km'] for r in week_runs)
            long = [r for r in week_runs if r['distance_km'] > 18]
            fast = [r for r in week_runs if r['pace_min_km'] < 4.5]
            
            print(f"\n{week}: {total_km:.0f}km | {len(week_runs)} runs")
            if long:
                long_strs = [f"{r['distance_km']:.0f}km@{r['pace_min_km']:.1f}" for r in long]
                print(f"  LONG: {', '.join(long_strs)}")
            if fast:
                fast_strs = [f"{r['distance_km']:.0f}km@{r['pace_min_km']:.1f}" for r in fast]
                print(f"  FAST: {', '.join(fast_strs)}")
        
        # KEY FINDING 5: The "breakthrough" workouts
        print("\n" + "=" * 80)
        print("KEY FINDING 5: BREAKTHROUGH WORKOUTS")
        print("=" * 80)
        
        # Define breakthrough as: fastest pace for distance bucket
        dist_buckets = {
            '5-10km': [r for r in runs if 5 <= r['distance_km'] < 10],
            '10-16km': [r for r in runs if 10 <= r['distance_km'] < 16],
            '16-25km': [r for r in runs if 16 <= r['distance_km'] < 25],
            '25km+': [r for r in runs if r['distance_km'] >= 25]
        }
        
        for bucket, bucket_runs in dist_buckets.items():
            if bucket_runs:
                fastest = min(bucket_runs, key=lambda x: x['pace_min_km'])
                print(f"\n{bucket} - Fastest:")
                print(f"  {fastest['date'].strftime('%m/%d')} | {fastest['distance_km']:.1f}km @ {fastest['pace_min_km']:.2f}/km | HR:{fastest['avg_hr']:.0f}")
        
        # THE RACE
        print("\n" + "=" * 80)
        print("THE RACE: November 29, 2025 Half Marathon PR")
        print("=" * 80)
        
        result = conn.execute(text("""
            SELECT 
                distance_m,
                duration_s,
                avg_hr,
                max_hr,
                (duration_s / 60.0) / (distance_m / 1000.0) as pace_min_km
            FROM activity 
            WHERE athlete_id = :id 
            AND start_time::date = :race_date
            ORDER BY distance_m DESC
            LIMIT 1
        """), {"id": michael_id, "race_date": half_pr_date.date()})
        
        race = result.fetchone()
        if race:
            hours = int(race[1] // 3600)
            mins = int((race[1] % 3600) // 60)
            secs = int(race[1] % 60)
            print(f"\n  Distance: {race[0]/1000:.2f} km")
            print(f"  Time: {hours}:{mins:02d}:{secs:02d}")
            print(f"  Pace: {race[4]:.2f} min/km")
            print(f"  Avg HR: {race[2]:.0f}")
            print(f"  Max HR: {race[3]:.0f}" if race[3] else "  Max HR: N/A")
        
        # SUMMARY
        print("\n" + "=" * 80)
        print("SUMMARY: WHAT MADE THIS BUILD WORK")
        print("=" * 80)
        
        print("""
Based on the data, the key factors appear to be:

1. HIGH VOLUME
   - Average 99 km/week (8.1 runs/week)
   - Consistent high mileage throughout

2. LONG RUN DOMINANCE
   - 19 long runs in 8 weeks (>2 per week!)
   - Long run pace improved 1+ min/km over the build
   - Several "workout" long runs at sub-5:00/km pace

3. LIMITED HIGH INTENSITY
   - Only 4 tempo sessions
   - NO interval work detected
   - Quality came from pace in long runs, not separate speed work

4. KEY WORKOUTS (candidates):
   - 10/12: 29.0km @ 4.66/km (fast long run early)
   - 10/18: 16.1km @ 4.41/km (breakthrough pace)
   - 11/09: 29.0km @ 4.44/km (fastest long run)
   - 11/18: 24.1km @ 4.73/km (confidence builder 11 days before race)

5. RACE EXECUTION
   - Race pace: 4.13/km
   - Tempo sessions were at 4.03-4.10/km (just faster than race pace)
   - Long runs progressed from 5.75 to 4.73/km
   - Race pace was well-practiced territory
""")
        
        print("=" * 80)

if __name__ == "__main__":
    main()

