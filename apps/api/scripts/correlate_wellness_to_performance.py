"""
Correlate Wellness Metrics to Running Performance

The real question: How do HRV, Resting HR, and Sleep affect:
1. Running efficiency (pace at given HR)
2. Performance by workout type
3. Same-day vs delayed effects
4. Trends over training cycles
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import math


def load_garmin_data(filepath: str) -> dict:
    """Load the Garmin import JSON."""
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    # Index by date
    by_date = {}
    for record in data.get('daily_data', []):
        date = record.get('date')
        if date:
            by_date[date] = record
    
    return by_date


def load_strava_activities(export_path: Path) -> list:
    """
    Load activities from Garmin export (DI-Connect-Fitness).
    These are the same activities synced to Strava.
    """
    import glob
    
    fitness_path = export_path / "DI_CONNECT" / "DI-Connect-Fitness"
    
    # Try the summarized activities file
    pattern = str(fitness_path / "*_summarizedActivities.json")
    
    activities = []
    for filepath in glob.glob(pattern):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    activities.extend(data)
        except Exception as e:
            print(f"  Warning: Could not load {filepath}: {e}")
    
    return activities


def parse_activities(raw_activities: list) -> list:
    """Parse and filter for running activities with HR data."""
    running_activities = []
    
    for activity in raw_activities:
        try:
            # Filter for running
            activity_type = activity.get('activityType', '')
            if 'running' not in activity_type.lower() and 'run' not in activity_type.lower():
                continue
            
            # Get key metrics
            distance_m = activity.get('distance', 0)
            duration_s = activity.get('duration', 0)
            avg_hr = activity.get('averageHR')
            max_hr = activity.get('maxHR')
            
            # Skip if missing key data
            if not distance_m or not duration_s or not avg_hr:
                continue
            if distance_m < 1000 or duration_s < 300:  # Min 1km, 5min
                continue
            if avg_hr < 80 or avg_hr > 200:  # Realistic HR
                continue
            
            # Calculate derived metrics
            pace_min_km = (duration_s / 60) / (distance_m / 1000)
            speed_kph = distance_m / duration_s * 3.6
            efficiency = speed_kph / avg_hr  # Higher = better
            
            # Get date
            start_time = activity.get('beginTimestamp')
            if start_time:
                # Handle milliseconds timestamp
                if isinstance(start_time, (int, float)):
                    dt = datetime.fromtimestamp(start_time / 1000)
                else:
                    dt = datetime.fromisoformat(str(start_time).replace('Z', ''))
                date_str = dt.strftime('%Y-%m-%d')
            else:
                continue
            
            running_activities.append({
                'date': date_str,
                'distance_km': distance_m / 1000,
                'duration_min': duration_s / 60,
                'avg_hr': avg_hr,
                'max_hr': max_hr,
                'pace_min_km': pace_min_km,
                'speed_kph': speed_kph,
                'efficiency': efficiency,
                'elevation_gain': activity.get('elevationGain', 0),
                'name': activity.get('activityName', ''),
            })
            
        except Exception as e:
            continue
    
    # Sort by date
    running_activities.sort(key=lambda x: x['date'])
    return running_activities


def classify_run(activity: dict) -> str:
    """Simple run classification based on pace and duration."""
    pace = activity.get('pace_min_km', 0)
    duration = activity.get('duration_min', 0)
    distance = activity.get('distance_km', 0)
    avg_hr = activity.get('avg_hr', 0)
    name = activity.get('name', '').lower()
    
    # Use name hints first
    if 'tempo' in name or 'threshold' in name:
        return 'tempo'
    if 'interval' in name or 'speed' in name or 'track' in name:
        return 'intervals'
    if 'long' in name or distance > 16:
        return 'long_run'
    if 'easy' in name or 'recovery' in name:
        return 'easy'
    if 'race' in name or 'marathon' in name or '10k' in name or '5k' in name:
        return 'race'
    
    # Fallback to pace/duration heuristics
    if duration > 90:
        return 'long_run'
    if pace < 4.5 and avg_hr > 160:
        return 'tempo'
    if avg_hr > 170:
        return 'intervals'
    
    return 'easy'


def merge_wellness_and_activities(wellness: dict, activities: list) -> list:
    """Merge wellness data with activities by date."""
    merged = []
    
    for activity in activities:
        date = activity['date']
        wellness_data = wellness.get(date, {})
        
        # Also get previous day's wellness (for delayed effects)
        prev_date = (datetime.strptime(date, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
        prev_wellness = wellness.get(prev_date, {})
        
        merged.append({
            **activity,
            'run_type': classify_run(activity),
            # Same-day wellness
            'hrv': wellness_data.get('hrv'),
            'resting_hr': wellness_data.get('resting_hr'),
            'hours_slept': wellness_data.get('hours_slept'),
            # Previous-day wellness (for delayed effects)
            'prev_hrv': prev_wellness.get('hrv'),
            'prev_resting_hr': prev_wellness.get('resting_hr'),
            'prev_sleep': prev_wellness.get('hours_slept'),
        })
    
    return merged


def pearson(x: list, y: list) -> float:
    """Calculate Pearson correlation coefficient."""
    pairs = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
    if len(pairs) < 5:
        return None
    
    n = len(pairs)
    x_vals = [p[0] for p in pairs]
    y_vals = [p[1] for p in pairs]
    
    mean_x = sum(x_vals) / n
    mean_y = sum(y_vals) / n
    
    num = sum((x_vals[i] - mean_x) * (y_vals[i] - mean_y) for i in range(n))
    den_x = sum((xi - mean_x) ** 2 for xi in x_vals) ** 0.5
    den_y = sum((yi - mean_y) ** 2 for yi in y_vals) ** 0.5
    
    if den_x == 0 or den_y == 0:
        return None
    
    return num / (den_x * den_y)


def analyze_correlations(merged_data: list):
    """Main correlation analysis."""
    
    print("\n" + "="*70)
    print("WELLNESS -> PERFORMANCE CORRELATIONS")
    print("="*70)
    
    # Filter for runs with wellness data
    with_wellness = [r for r in merged_data if r.get('hrv') or r.get('resting_hr') or r.get('hours_slept')]
    
    print(f"\nRuns with wellness data: {len(with_wellness)} / {len(merged_data)}")
    
    # === SAME-DAY EFFECTS ===
    print("\n--- SAME-DAY EFFECTS ---")
    print("(How does morning wellness affect today's run?)\n")
    
    # Efficiency correlations
    correlations = []
    
    # HRV -> Efficiency
    hrv_vals = [r['hrv'] for r in with_wellness if r.get('hrv')]
    eff_vals = [r['efficiency'] for r in with_wellness if r.get('hrv')]
    r = pearson(hrv_vals, eff_vals)
    if r:
        correlations.append(('HRV -> Efficiency', r, len(hrv_vals)))
        print(f"HRV -> Efficiency: r = {r:.3f} (n={len(hrv_vals)})")
    
    # RHR -> Efficiency (expect negative - higher RHR = worse)
    rhr_vals = [r['resting_hr'] for r in with_wellness if r.get('resting_hr')]
    eff_vals2 = [r['efficiency'] for r in with_wellness if r.get('resting_hr')]
    r = pearson(rhr_vals, eff_vals2)
    if r:
        correlations.append(('Resting HR -> Efficiency', r, len(rhr_vals)))
        print(f"Resting HR -> Efficiency: r = {r:.3f} (n={len(rhr_vals)})")
    
    # Sleep -> Efficiency
    sleep_vals = [r['hours_slept'] for r in with_wellness if r.get('hours_slept')]
    eff_vals3 = [r['efficiency'] for r in with_wellness if r.get('hours_slept')]
    r = pearson(sleep_vals, eff_vals3)
    if r:
        correlations.append(('Sleep -> Efficiency', r, len(sleep_vals)))
        print(f"Sleep (hours) -> Efficiency: r = {r:.3f} (n={len(sleep_vals)})")
    
    # === DELAYED EFFECTS (Previous Day) ===
    print("\n--- DELAYED EFFECTS (Previous Day) ---")
    print("(How does yesterday's wellness affect today's run?)\n")
    
    # Previous HRV -> Today's Efficiency
    prev_hrv = [r['prev_hrv'] for r in with_wellness if r.get('prev_hrv')]
    eff_prev = [r['efficiency'] for r in with_wellness if r.get('prev_hrv')]
    r = pearson(prev_hrv, eff_prev)
    if r:
        correlations.append(('Yesterday HRV -> Today Efficiency', r, len(prev_hrv)))
        print(f"Yesterday's HRV -> Today's Efficiency: r = {r:.3f} (n={len(prev_hrv)})")
    
    # Previous Sleep -> Today's Efficiency
    prev_sleep = [r['prev_sleep'] for r in with_wellness if r.get('prev_sleep')]
    eff_prev2 = [r['efficiency'] for r in with_wellness if r.get('prev_sleep')]
    r = pearson(prev_sleep, eff_prev2)
    if r:
        correlations.append(('Yesterday Sleep -> Today Efficiency', r, len(prev_sleep)))
        print(f"Yesterday's Sleep -> Today's Efficiency: r = {r:.3f} (n={len(prev_sleep)})")
    
    # === BY RUN TYPE ===
    print("\n--- BY RUN TYPE ---")
    print("(Which workouts are most affected by wellness?)\n")
    
    run_types = defaultdict(list)
    for r in with_wellness:
        if r.get('hrv'):
            run_types[r['run_type']].append(r)
    
    for run_type, runs in sorted(run_types.items(), key=lambda x: -len(x[1])):
        if len(runs) < 5:
            continue
        
        hrv_vals = [r['hrv'] for r in runs]
        eff_vals = [r['efficiency'] for r in runs]
        r = pearson(hrv_vals, eff_vals)
        
        if r is not None:
            print(f"{run_type.upper()} (n={len(runs)}): HRV -> Efficiency r = {r:.3f}")
    
    return correlations


def analyze_trends(merged_data: list):
    """Analyze trends over time."""
    
    print("\n" + "="*70)
    print("TRENDS OVER TIME")
    print("="*70)
    
    # Group by month
    by_month = defaultdict(list)
    for r in merged_data:
        month = r['date'][:7]  # YYYY-MM
        by_month[month].append(r)
    
    print("\n--- MONTHLY EFFICIENCY TREND ---\n")
    
    for month in sorted(by_month.keys()):
        runs = by_month[month]
        efficiencies = [r['efficiency'] for r in runs]
        avg_eff = sum(efficiencies) / len(efficiencies)
        avg_hr = sum(r['avg_hr'] for r in runs) / len(runs)
        total_km = sum(r['distance_km'] for r in runs)
        
        bar = '█' * int(avg_eff * 200)
        print(f"{month}: eff={avg_eff:.4f} {bar} ({len(runs)} runs, {total_km:.0f}km, HR={avg_hr:.0f})")
    
    # === EFFICIENCY IN HIGH VS LOW HRV DAYS ===
    print("\n--- EFFICIENCY: HIGH HRV DAYS vs LOW HRV DAYS ---\n")
    
    with_hrv = [r for r in merged_data if r.get('hrv')]
    if len(with_hrv) >= 10:
        hrv_values = [r['hrv'] for r in with_hrv]
        median_hrv = sorted(hrv_values)[len(hrv_values) // 2]
        
        high_hrv_runs = [r for r in with_hrv if r['hrv'] >= median_hrv]
        low_hrv_runs = [r for r in with_hrv if r['hrv'] < median_hrv]
        
        high_eff = sum(r['efficiency'] for r in high_hrv_runs) / len(high_hrv_runs)
        low_eff = sum(r['efficiency'] for r in low_hrv_runs) / len(low_hrv_runs)
        
        print(f"Median HRV: {median_hrv}")
        print(f"High HRV days (>= {median_hrv}): avg efficiency = {high_eff:.4f} (n={len(high_hrv_runs)})")
        print(f"Low HRV days (< {median_hrv}): avg efficiency = {low_eff:.4f} (n={len(low_hrv_runs)})")
        print(f"Difference: {((high_eff - low_eff) / low_eff * 100):.1f}%")
    
    # === EFFICIENCY IN HIGH VS LOW SLEEP DAYS ===
    print("\n--- EFFICIENCY: GOOD SLEEP vs POOR SLEEP ---\n")
    
    with_sleep = [r for r in merged_data if r.get('hours_slept')]
    if len(with_sleep) >= 10:
        sleep_values = [r['hours_slept'] for r in with_sleep]
        median_sleep = sorted(sleep_values)[len(sleep_values) // 2]
        
        good_sleep = [r for r in with_sleep if r['hours_slept'] >= median_sleep]
        poor_sleep = [r for r in with_sleep if r['hours_slept'] < median_sleep]
        
        good_eff = sum(r['efficiency'] for r in good_sleep) / len(good_sleep)
        poor_eff = sum(r['efficiency'] for r in poor_sleep) / len(poor_sleep)
        
        print(f"Median sleep: {median_sleep:.1f}h")
        print(f"Good sleep (>= {median_sleep:.1f}h): avg efficiency = {good_eff:.4f} (n={len(good_sleep)})")
        print(f"Poor sleep (< {median_sleep:.1f}h): avg efficiency = {poor_eff:.4f} (n={len(poor_sleep)})")
        print(f"Difference: {((good_eff - poor_eff) / poor_eff * 100):.1f}%")


def identify_best_worst_conditions(merged_data: list):
    """Find the conditions that produce best/worst efficiency."""
    
    print("\n" + "="*70)
    print("BEST AND WORST CONDITIONS")
    print("="*70)
    
    # Filter for runs with full wellness data
    full_data = [r for r in merged_data if r.get('hrv') and r.get('resting_hr') and r.get('hours_slept')]
    
    if len(full_data) < 10:
        print("\nInsufficient runs with complete wellness data for this analysis.")
        return
    
    # Sort by efficiency
    sorted_by_eff = sorted(full_data, key=lambda x: x['efficiency'], reverse=True)
    
    print("\n--- TOP 10 EFFICIENCY RUNS (What was wellness like?) ---\n")
    for r in sorted_by_eff[:10]:
        print(f"  {r['date']}: eff={r['efficiency']:.4f} | HRV={r['hrv']:.0f} RHR={r['resting_hr']:.0f} Sleep={r['hours_slept']:.1f}h | {r['distance_km']:.1f}km @ {r['pace_min_km']:.2f}/km HR={r['avg_hr']:.0f}")
    
    top_10 = sorted_by_eff[:10]
    avg_hrv_top = sum(r['hrv'] for r in top_10) / 10
    avg_rhr_top = sum(r['resting_hr'] for r in top_10) / 10
    avg_sleep_top = sum(r['hours_slept'] for r in top_10) / 10
    
    print(f"\n  TOP 10 AVERAGES: HRV={avg_hrv_top:.1f}, RHR={avg_rhr_top:.1f}, Sleep={avg_sleep_top:.1f}h")
    
    print("\n--- BOTTOM 10 EFFICIENCY RUNS (What was wellness like?) ---\n")
    for r in sorted_by_eff[-10:]:
        print(f"  {r['date']}: eff={r['efficiency']:.4f} | HRV={r['hrv']:.0f} RHR={r['resting_hr']:.0f} Sleep={r['hours_slept']:.1f}h | {r['distance_km']:.1f}km @ {r['pace_min_km']:.2f}/km HR={r['avg_hr']:.0f}")
    
    bottom_10 = sorted_by_eff[-10:]
    avg_hrv_bot = sum(r['hrv'] for r in bottom_10) / 10
    avg_rhr_bot = sum(r['resting_hr'] for r in bottom_10) / 10
    avg_sleep_bot = sum(r['hours_slept'] for r in bottom_10) / 10
    
    print(f"\n  BOTTOM 10 AVERAGES: HRV={avg_hrv_bot:.1f}, RHR={avg_rhr_bot:.1f}, Sleep={avg_sleep_bot:.1f}h")
    
    print("\n--- COMPARISON ---")
    print(f"  HRV: Top={avg_hrv_top:.1f} vs Bottom={avg_hrv_bot:.1f} (diff: {avg_hrv_top - avg_hrv_bot:.1f})")
    print(f"  RHR: Top={avg_rhr_top:.1f} vs Bottom={avg_rhr_bot:.1f} (diff: {avg_rhr_top - avg_rhr_bot:.1f})")
    print(f"  Sleep: Top={avg_sleep_top:.1f}h vs Bottom={avg_sleep_bot:.1f}h (diff: {avg_sleep_top - avg_sleep_bot:.1f}h)")


def main():
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python correlate_wellness_to_performance.py <garmin_export_path> <wellness_json_path>")
        sys.exit(1)
    
    garmin_path = Path(sys.argv[1])
    wellness_path = sys.argv[2]
    
    print("="*70)
    print("WELLNESS -> PERFORMANCE ANALYSIS")
    print("="*70)
    
    # Load data
    print("\nLoading wellness data...")
    wellness = load_garmin_data(wellness_path)
    print(f"  Loaded {len(wellness)} days of wellness data")
    
    print("\nLoading activities from Garmin export...")
    raw_activities = load_strava_activities(garmin_path)
    print(f"  Loaded {len(raw_activities)} raw activities")
    
    activities = parse_activities(raw_activities)
    print(f"  Parsed {len(activities)} running activities with HR data")
    
    # Merge
    print("\nMerging wellness with activities...")
    merged = merge_wellness_and_activities(wellness, activities)
    
    runs_with_any = len([r for r in merged if r.get('hrv') or r.get('hours_slept')])
    print(f"  {runs_with_any} runs have associated wellness data")
    
    # Analyze
    analyze_correlations(merged)
    analyze_trends(merged)
    identify_best_worst_conditions(merged)
    
    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70)


if __name__ == "__main__":
    main()

