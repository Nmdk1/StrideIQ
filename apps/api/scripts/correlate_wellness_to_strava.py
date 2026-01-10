"""
Correlate Garmin Wellness Metrics to Strava Running Performance

Uses:
- Garmin export: HRV, Resting HR, Sleep Duration
- Database: Running activities from Strava

Question: How do wellness metrics affect running efficiency?
"""

import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

# Add parent for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/postgres")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def load_wellness_data(filepath: str) -> dict:
    """Load Garmin wellness JSON, indexed by date."""
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    by_date = {}
    for record in data.get('daily_data', []):
        date = record.get('date')
        if date:
            by_date[date] = record
    return by_date


def load_strava_activities(session, athlete_identifier: str) -> list:
    """Load running activities from Strava via database."""
    
    # Get athlete ID (try email, then display_name)
    result = session.execute(text("""
        SELECT id FROM athlete 
        WHERE email = :identifier 
           OR display_name = :identifier
           OR CAST(strava_athlete_id AS TEXT) = :identifier
        LIMIT 1
    """), {"identifier": athlete_identifier}).fetchone()
    
    if not result:
        print(f"Athlete not found: {athlete_email}")
        return []
    
    athlete_id = result[0]
    
    # Get running activities with HR
    activities = session.execute(text("""
        SELECT 
            id,
            start_time,
            distance_m,
            duration_s,
            avg_hr,
            max_hr,
            total_elevation_gain,
            sport
        FROM activity 
        WHERE athlete_id = :athlete_id
        AND avg_hr IS NOT NULL 
        AND distance_m > 1000
        AND duration_s > 300
        AND avg_hr > 80 AND avg_hr < 200
        ORDER BY start_time
    """), {"athlete_id": str(athlete_id)}).fetchall()
    
    parsed = []
    for row in activities:
        distance_m = float(row[2])
        duration_s = float(row[3])
        avg_hr = float(row[4])
        
        pace_min_km = (duration_s / 60) / (distance_m / 1000)
        speed_kph = distance_m / duration_s * 3.6
        efficiency = speed_kph / avg_hr
        
        parsed.append({
            'id': row[0],
            'date': row[1].strftime('%Y-%m-%d'),
            'datetime': row[1],
            'distance_km': distance_m / 1000,
            'duration_min': duration_s / 60,
            'avg_hr': avg_hr,
            'max_hr': float(row[5]) if row[5] else None,
            'elevation': float(row[6]) if row[6] else 0,
            'sport': row[7] or 'run',
            'pace_min_km': pace_min_km,
            'speed_kph': speed_kph,
            'efficiency': efficiency,
        })
    
    return parsed


def classify_run(activity: dict) -> str:
    """Classify run type based on pace, HR, and distance (no activity name available)."""
    distance = activity.get('distance_km', 0)
    duration = activity.get('duration_min', 0)
    avg_hr = activity.get('avg_hr', 0)
    pace = activity.get('pace_min_km', 10)
    
    # Distance-based
    if distance > 18:
        return 'long_run'
    if distance > 13:
        return 'medium_long'
    
    # Intensity-based (using HR as proxy)
    if avg_hr > 170:
        return 'high_intensity'
    if avg_hr > 155 and pace < 4.8:
        return 'tempo'
    if avg_hr < 140:
        return 'recovery'
    
    return 'easy'


def merge_data(wellness: dict, activities: list) -> list:
    """Merge wellness with activities by date."""
    merged = []
    
    for activity in activities:
        date = activity['date']
        well = wellness.get(date, {})
        
        # Previous day
        prev_date = (datetime.strptime(date, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
        prev_well = wellness.get(prev_date, {})
        
        merged.append({
            **activity,
            'run_type': classify_run(activity),
            # Same day
            'hrv': well.get('hrv'),
            'resting_hr': well.get('resting_hr'),
            'hours_slept': well.get('hours_slept'),
            # Previous day
            'prev_hrv': prev_well.get('hrv'),
            'prev_rhr': prev_well.get('resting_hr'),
            'prev_sleep': prev_well.get('hours_slept'),
        })
    
    return merged


def pearson(pairs: list) -> float:
    """Pearson correlation from (x,y) pairs."""
    valid = [(x, y) for x, y in pairs if x is not None and y is not None]
    if len(valid) < 5:
        return None
    
    n = len(valid)
    x = [p[0] for p in valid]
    y = [p[1] for p in valid]
    
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    
    num = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    den_x = sum((xi - mean_x) ** 2 for xi in x) ** 0.5
    den_y = sum((yi - mean_y) ** 2 for yi in y) ** 0.5
    
    if den_x == 0 or den_y == 0:
        return None
    return num / (den_x * den_y), len(valid)


def main():
    if len(sys.argv) < 3:
        print("Usage: python correlate_wellness_to_strava.py <wellness_json> <athlete_email>")
        sys.exit(1)
    
    wellness_path = sys.argv[1]
    athlete_email = sys.argv[2]
    
    print("="*70)
    print("WELLNESS -> RUNNING PERFORMANCE ANALYSIS")
    print("="*70)
    
    # Load data
    print("\nLoading wellness data...")
    wellness = load_wellness_data(wellness_path)
    print(f"  {len(wellness)} days of wellness data")
    
    print("\nLoading Strava activities from database...")
    session = SessionLocal()
    try:
        activities = load_strava_activities(session, athlete_email)
        print(f"  {len(activities)} running activities with HR")
    finally:
        session.close()
    
    if not activities:
        print("\nNo activities found!")
        return
    
    # Merge
    merged = merge_data(wellness, activities)
    
    with_wellness = [r for r in merged if r.get('hrv') or r.get('hours_slept')]
    print(f"\n  {len(with_wellness)} runs have associated wellness data")
    
    # === SAME-DAY CORRELATIONS ===
    print("\n" + "="*70)
    print("SAME-DAY EFFECTS")
    print("(Morning wellness -> Today's run efficiency)")
    print("="*70)
    
    pairs_hrv = [(r['hrv'], r['efficiency']) for r in merged if r.get('hrv')]
    pairs_rhr = [(r['resting_hr'], r['efficiency']) for r in merged if r.get('resting_hr')]
    pairs_sleep = [(r['hours_slept'], r['efficiency']) for r in merged if r.get('hours_slept')]
    
    result = pearson(pairs_hrv)
    if result:
        r, n = result
        print(f"\nHRV -> Efficiency: r = {r:.3f} (n={n})")
        if r > 0.1:
            print("  -> Higher HRV = better efficiency")
        elif r < -0.1:
            print("  -> Higher HRV = WORSE efficiency (unexpected)")
        else:
            print("  -> No meaningful relationship")
    
    result = pearson(pairs_rhr)
    if result:
        r, n = result
        print(f"\nResting HR -> Efficiency: r = {r:.3f} (n={n})")
        if r < -0.1:
            print("  -> Lower RHR = better efficiency (expected)")
        elif r > 0.1:
            print("  -> Higher RHR = better efficiency (unexpected)")
        else:
            print("  -> No meaningful relationship")
    
    result = pearson(pairs_sleep)
    if result:
        r, n = result
        print(f"\nSleep Duration -> Efficiency: r = {r:.3f} (n={n})")
        if r > 0.1:
            print("  -> More sleep = better efficiency")
        elif r < -0.1:
            print("  -> More sleep = WORSE efficiency (unexpected)")
        else:
            print("  -> No meaningful relationship")
    
    # === DELAYED EFFECTS ===
    print("\n" + "="*70)
    print("DELAYED EFFECTS")
    print("(Yesterday's wellness -> Today's run)")
    print("="*70)
    
    pairs_prev_hrv = [(r['prev_hrv'], r['efficiency']) for r in merged if r.get('prev_hrv')]
    pairs_prev_sleep = [(r['prev_sleep'], r['efficiency']) for r in merged if r.get('prev_sleep')]
    
    result = pearson(pairs_prev_hrv)
    if result:
        r, n = result
        print(f"\nYesterday's HRV -> Today's Efficiency: r = {r:.3f} (n={n})")
    
    result = pearson(pairs_prev_sleep)
    if result:
        r, n = result
        print(f"\nYesterday's Sleep -> Today's Efficiency: r = {r:.3f} (n={n})")
    
    # === BY RUN TYPE ===
    print("\n" + "="*70)
    print("BY RUN TYPE")
    print("(Which workouts are most affected by wellness?)")
    print("="*70)
    
    by_type = defaultdict(list)
    for r in merged:
        if r.get('hrv'):
            by_type[r['run_type']].append(r)
    
    print("\nHRV -> Efficiency by run type:")
    for run_type in ['easy', 'recovery', 'tempo', 'high_intensity', 'medium_long', 'long_run']:
        runs = by_type.get(run_type, [])
        if len(runs) >= 5:
            pairs = [(r['hrv'], r['efficiency']) for r in runs]
            result = pearson(pairs)
            if result:
                r, n = result
                impact = "HIGH" if abs(r) > 0.3 else "MODERATE" if abs(r) > 0.15 else "LOW"
                print(f"  {run_type.upper():15} r={r:+.3f} n={n:3} Impact: {impact}")
    
    # === HIGH vs LOW HRV ===
    print("\n" + "="*70)
    print("HIGH HRV vs LOW HRV DAYS")
    print("="*70)
    
    runs_with_hrv = [r for r in merged if r.get('hrv')]
    if len(runs_with_hrv) >= 10:
        hrv_values = sorted([r['hrv'] for r in runs_with_hrv])
        median_hrv = hrv_values[len(hrv_values) // 2]
        
        high_hrv = [r for r in runs_with_hrv if r['hrv'] >= median_hrv]
        low_hrv = [r for r in runs_with_hrv if r['hrv'] < median_hrv]
        
        high_eff = sum(r['efficiency'] for r in high_hrv) / len(high_hrv)
        low_eff = sum(r['efficiency'] for r in low_hrv) / len(low_hrv)
        
        print(f"\nMedian HRV: {median_hrv}")
        print(f"High HRV days (>= {median_hrv}): n={len(high_hrv)}, avg efficiency = {high_eff:.4f}")
        print(f"Low HRV days (< {median_hrv}):  n={len(low_hrv)}, avg efficiency = {low_eff:.4f}")
        diff_pct = (high_eff - low_eff) / low_eff * 100
        print(f"Difference: {diff_pct:+.1f}%")
        
        if abs(diff_pct) > 3:
            print(f"\n** SIGNAL DETECTED: HRV appears to affect efficiency by ~{abs(diff_pct):.0f}%")
        else:
            print(f"\n** NO MEANINGFUL SIGNAL: Difference is negligible")
    
    # === GOOD vs POOR SLEEP ===
    print("\n" + "="*70)
    print("GOOD SLEEP vs POOR SLEEP")
    print("="*70)
    
    runs_with_sleep = [r for r in merged if r.get('hours_slept')]
    if len(runs_with_sleep) >= 10:
        sleep_values = sorted([r['hours_slept'] for r in runs_with_sleep])
        median_sleep = sleep_values[len(sleep_values) // 2]
        
        good_sleep = [r for r in runs_with_sleep if r['hours_slept'] >= median_sleep]
        poor_sleep = [r for r in runs_with_sleep if r['hours_slept'] < median_sleep]
        
        good_eff = sum(r['efficiency'] for r in good_sleep) / len(good_sleep)
        poor_eff = sum(r['efficiency'] for r in poor_sleep) / len(poor_sleep)
        
        print(f"\nMedian sleep: {median_sleep:.1f}h")
        print(f"Good sleep (>= {median_sleep:.1f}h): n={len(good_sleep)}, avg efficiency = {good_eff:.4f}")
        print(f"Poor sleep (< {median_sleep:.1f}h):  n={len(poor_sleep)}, avg efficiency = {poor_eff:.4f}")
        diff_pct = (good_eff - poor_eff) / poor_eff * 100
        print(f"Difference: {diff_pct:+.1f}%")
    
    # === BEST/WORST CONDITIONS ===
    print("\n" + "="*70)
    print("TOP 10 vs BOTTOM 10 EFFICIENCY")
    print("="*70)
    
    full_data = [r for r in merged if r.get('hrv') and r.get('hours_slept')]
    if len(full_data) >= 20:
        sorted_runs = sorted(full_data, key=lambda x: x['efficiency'], reverse=True)
        
        top_10 = sorted_runs[:10]
        bot_10 = sorted_runs[-10:]
        
        print("\nTOP 10 EFFICIENCY:")
        for r in top_10:
            print(f"  {r['date']}: eff={r['efficiency']:.4f} | HRV={r['hrv']:.0f} Sleep={r['hours_slept']:.1f}h | {r['distance_km']:.1f}km {r['run_type']}")
        
        avg_hrv_top = sum(r['hrv'] for r in top_10) / 10
        avg_sleep_top = sum(r['hours_slept'] for r in top_10) / 10
        
        print(f"\n  TOP 10 AVERAGES: HRV={avg_hrv_top:.1f}, Sleep={avg_sleep_top:.1f}h")
        
        print("\nBOTTOM 10 EFFICIENCY:")
        for r in bot_10:
            print(f"  {r['date']}: eff={r['efficiency']:.4f} | HRV={r['hrv']:.0f} Sleep={r['hours_slept']:.1f}h | {r['distance_km']:.1f}km {r['run_type']}")
        
        avg_hrv_bot = sum(r['hrv'] for r in bot_10) / 10
        avg_sleep_bot = sum(r['hours_slept'] for r in bot_10) / 10
        
        print(f"\n  BOTTOM 10 AVERAGES: HRV={avg_hrv_bot:.1f}, Sleep={avg_sleep_bot:.1f}h")
        
        print("\n  COMPARISON:")
        print(f"    HRV:   Top={avg_hrv_top:.1f} vs Bottom={avg_hrv_bot:.1f} (diff: {avg_hrv_top - avg_hrv_bot:+.1f})")
        print(f"    Sleep: Top={avg_sleep_top:.1f}h vs Bottom={avg_sleep_bot:.1f}h (diff: {avg_sleep_top - avg_sleep_bot:+.1f}h)")
    
    # === TRENDS ===
    print("\n" + "="*70)
    print("MONTHLY TRENDS")
    print("="*70)
    
    by_month = defaultdict(list)
    for r in merged:
        month = r['date'][:7]
        by_month[month].append(r)
    
    print("\nMonth      Runs  Volume   Avg Eff   Avg HR   Avg HRV")
    print("-" * 60)
    for month in sorted(by_month.keys()):
        runs = by_month[month]
        num = len(runs)
        vol = sum(r['distance_km'] for r in runs)
        eff = sum(r['efficiency'] for r in runs) / num
        hr = sum(r['avg_hr'] for r in runs) / num
        
        hrv_runs = [r for r in runs if r.get('hrv')]
        avg_hrv = sum(r['hrv'] for r in hrv_runs) / len(hrv_runs) if hrv_runs else None
        hrv_str = f"{avg_hrv:.0f}" if avg_hrv else "-"
        
        print(f"{month}    {num:3}   {vol:5.0f}km   {eff:.4f}   {hr:.0f}      {hrv_str}")
    
    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70)


if __name__ == "__main__":
    main()

