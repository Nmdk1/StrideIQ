"""
Analyze What Actually Drives Improvement

Focus: Find the variables that correlate with efficiency gains over time.
Not: HRV/Sleep (already proven to be noise)
Yes: Training patterns, volume progression, intensity distribution, consistency
"""

import os
import sys
import json
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/running_app")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def pearson(pairs):
    """Pearson correlation from (x,y) pairs."""
    valid = [(float(x), float(y)) for x, y in pairs if x is not None and y is not None]
    if len(valid) < 5:
        return None, 0
    
    n = len(valid)
    x = [p[0] for p in valid]
    y = [p[1] for p in valid]
    
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    
    num = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    den_x = sum((xi - mean_x) ** 2 for xi in x) ** 0.5
    den_y = sum((yi - mean_y) ** 2 for yi in y) ** 0.5
    
    if den_x == 0 or den_y == 0:
        return None, 0
    return num / (den_x * den_y), n


def load_activities(session, athlete_name: str) -> list:
    """Load all running activities."""
    
    result = session.execute(text("""
        SELECT id FROM athlete 
        WHERE display_name = :name
        LIMIT 1
    """), {"name": athlete_name}).fetchone()
    
    if not result:
        print(f"Athlete not found: {athlete_name}")
        return []
    
    athlete_id = result[0]
    
    activities = session.execute(text("""
        SELECT 
            id, start_time, distance_m, duration_s, avg_hr, max_hr, 
            total_elevation_gain, sport
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
            'week': row[1].strftime('%Y-W%W'),
            'distance_km': distance_m / 1000,
            'duration_min': duration_s / 60,
            'avg_hr': avg_hr,
            'max_hr': float(row[5]) if row[5] else None,
            'elevation': float(row[6]) if row[6] else 0,
            'pace_min_km': pace_min_km,
            'speed_kph': speed_kph,
            'efficiency': efficiency,
        })
    
    return parsed


def calculate_weekly_metrics(activities: list) -> list:
    """Calculate weekly aggregates."""
    by_week = defaultdict(list)
    for a in activities:
        by_week[a['week']].append(a)
    
    weekly = []
    for week, runs in sorted(by_week.items()):
        volume_km = sum(r['distance_km'] for r in runs)
        num_runs = len(runs)
        avg_run_distance = volume_km / num_runs
        avg_efficiency = sum(r['efficiency'] for r in runs) / num_runs
        avg_hr = sum(r['avg_hr'] for r in runs) / num_runs
        avg_pace = sum(r['pace_min_km'] for r in runs) / num_runs
        
        # Long run (max distance)
        long_run = max(r['distance_km'] for r in runs)
        
        # High intensity runs (HR > 155)
        high_intensity = sum(1 for r in runs if r['avg_hr'] > 155)
        
        # Longest duration
        longest_duration = max(r['duration_min'] for r in runs)
        
        weekly.append({
            'week': week,
            'volume_km': volume_km,
            'num_runs': num_runs,
            'avg_run_distance': avg_run_distance,
            'avg_efficiency': avg_efficiency,
            'avg_hr': avg_hr,
            'avg_pace': avg_pace,
            'long_run_km': long_run,
            'high_intensity_count': high_intensity,
            'longest_duration_min': longest_duration,
        })
    
    return weekly


def analyze_volume_efficiency(weekly: list):
    """Does volume correlate with efficiency?"""
    print("\n" + "="*70)
    print("VOLUME -> EFFICIENCY ANALYSIS")
    print("="*70)
    
    # Current week volume vs current week efficiency
    pairs = [(w['volume_km'], w['avg_efficiency']) for w in weekly]
    r, n = pearson(pairs)
    print(f"\nCurrent Week Volume -> Current Week Efficiency: r={r:.3f} (n={n})")
    
    # Previous week volume vs current week efficiency
    pairs_lag = []
    for i in range(1, len(weekly)):
        pairs_lag.append((weekly[i-1]['volume_km'], weekly[i]['avg_efficiency']))
    r, n = pearson(pairs_lag)
    print(f"Previous Week Volume -> Current Week Efficiency: r={r:.3f} (n={n})")
    
    # Rolling 4-week volume vs efficiency
    pairs_rolling = []
    for i in range(4, len(weekly)):
        rolling_vol = sum(weekly[j]['volume_km'] for j in range(i-4, i))
        pairs_rolling.append((rolling_vol, weekly[i]['avg_efficiency']))
    r, n = pearson(pairs_rolling)
    print(f"Rolling 4-Week Volume -> Current Week Efficiency: r={r:.3f} (n={n})")
    
    # Cumulative volume vs efficiency
    cumulative = 0
    pairs_cumulative = []
    for w in weekly:
        cumulative += w['volume_km']
        pairs_cumulative.append((cumulative, w['avg_efficiency']))
    r, n = pearson(pairs_cumulative)
    print(f"Cumulative Volume -> Efficiency: r={r:.3f} (n={n})")
    if r and r > 0.3:
        print("  ** SIGNAL: More total running = better efficiency")


def analyze_consistency(weekly: list):
    """Does consistency correlate with efficiency?"""
    print("\n" + "="*70)
    print("CONSISTENCY -> EFFICIENCY ANALYSIS")
    print("="*70)
    
    # Runs per week vs efficiency
    pairs = [(w['num_runs'], w['avg_efficiency']) for w in weekly]
    r, n = pearson(pairs)
    print(f"\nRuns Per Week -> Efficiency: r={r:.3f} (n={n})")
    
    # Streak (consecutive weeks with 4+ runs)
    streak = 0
    pairs_streak = []
    for w in weekly:
        if w['num_runs'] >= 4:
            streak += 1
        else:
            streak = 0
        pairs_streak.append((streak, w['avg_efficiency']))
    r, n = pearson(pairs_streak)
    print(f"Consecutive 4+ Run Weeks -> Efficiency: r={r:.3f} (n={n})")
    if r and r > 0.3:
        print("  ** SIGNAL: Consistency streaks improve efficiency")


def analyze_long_runs(weekly: list):
    """Do long runs correlate with efficiency gains?"""
    print("\n" + "="*70)
    print("LONG RUNS -> EFFICIENCY ANALYSIS")
    print("="*70)
    
    # Long run distance vs next week efficiency
    pairs_lag = []
    for i in range(1, len(weekly)):
        pairs_lag.append((weekly[i-1]['long_run_km'], weekly[i]['avg_efficiency']))
    r, n = pearson(pairs_lag)
    print(f"\nLong Run Distance -> Next Week Efficiency: r={r:.3f} (n={n})")
    
    # Longest duration vs efficiency
    pairs = [(w['longest_duration_min'], w['avg_efficiency']) for w in weekly]
    r, n = pearson(pairs)
    print(f"Longest Duration -> Efficiency: r={r:.3f} (n={n})")
    
    # Long runs > 20km in last 4 weeks
    pairs_count = []
    for i in range(4, len(weekly)):
        count_20k = sum(1 for j in range(i-4, i) if weekly[j]['long_run_km'] >= 20)
        pairs_count.append((count_20k, weekly[i]['avg_efficiency']))
    r, n = pearson(pairs_count)
    print(f"20km+ Long Runs (Last 4 Weeks) -> Efficiency: r={r:.3f} (n={n})")
    if r and r > 0.3:
        print("  ** SIGNAL: Long runs build efficiency")


def analyze_intensity_distribution(weekly: list):
    """Does intensity mix correlate with efficiency?"""
    print("\n" + "="*70)
    print("INTENSITY DISTRIBUTION -> EFFICIENCY ANALYSIS")
    print("="*70)
    
    # High intensity runs vs efficiency
    pairs = [(w['high_intensity_count'], w['avg_efficiency']) for w in weekly]
    r, n = pearson(pairs)
    print(f"\nHigh Intensity Runs/Week -> Efficiency: r={r:.3f} (n={n})")
    
    # Ratio of high intensity to total
    pairs_ratio = []
    for w in weekly:
        if w['num_runs'] > 0:
            ratio = w['high_intensity_count'] / w['num_runs']
            pairs_ratio.append((ratio, w['avg_efficiency']))
    r, n = pearson(pairs_ratio)
    print(f"High Intensity Ratio -> Efficiency: r={r:.3f} (n={n})")
    
    # High intensity in previous week
    pairs_lag = []
    for i in range(1, len(weekly)):
        pairs_lag.append((weekly[i-1]['high_intensity_count'], weekly[i]['avg_efficiency']))
    r, n = pearson(pairs_lag)
    print(f"Previous Week High Intensity -> This Week Efficiency: r={r:.3f} (n={n})")


def analyze_hr_trends(weekly: list):
    """HR at given effort over time."""
    print("\n" + "="*70)
    print("HEART RATE TRENDS (Fitness Indicator)")
    print("="*70)
    
    # Average HR trend
    pairs_time = [(i, w['avg_hr']) for i, w in enumerate(weekly)]
    r, n = pearson(pairs_time)
    print(f"\nTime -> Average HR: r={r:.3f} (n={n})")
    if r and r < -0.3:
        print("  ** SIGNAL: HR dropping over time = improving fitness")
    
    # HR vs pace (efficiency by another name)
    pairs = [(w['avg_hr'], w['avg_pace']) for w in weekly]
    r, n = pearson(pairs)
    print(f"Average HR -> Average Pace: r={r:.3f} (n={n})")
    
    # First 10 weeks vs last 10 weeks
    if len(weekly) >= 20:
        first_10_hr = sum(w['avg_hr'] for w in weekly[:10]) / 10
        last_10_hr = sum(w['avg_hr'] for w in weekly[-10:]) / 10
        first_10_eff = sum(w['avg_efficiency'] for w in weekly[:10]) / 10
        last_10_eff = sum(w['avg_efficiency'] for w in weekly[-10:]) / 10
        
        print(f"\nFirst 10 Weeks: Avg HR={first_10_hr:.0f}, Avg Eff={first_10_eff:.4f}")
        print(f"Last 10 Weeks:  Avg HR={last_10_hr:.0f}, Avg Eff={last_10_eff:.4f}")
        print(f"HR Change: {last_10_hr - first_10_hr:.0f} bpm")
        print(f"Efficiency Change: {(last_10_eff - first_10_eff) / first_10_eff * 100:.1f}%")


def analyze_periodization(activities: list):
    """Look at training patterns over longer periods."""
    print("\n" + "="*70)
    print("PERIODIZATION ANALYSIS")
    print("="*70)
    
    # Group by month
    by_month = defaultdict(list)
    for a in activities:
        month = a['date'][:7]
        by_month[month].append(a)
    
    months = []
    for month, runs in sorted(by_month.items()):
        volume = sum(r['distance_km'] for r in runs)
        avg_eff = sum(r['efficiency'] for r in runs) / len(runs)
        avg_hr = sum(r['avg_hr'] for r in runs) / len(runs)
        months.append({
            'month': month,
            'volume': volume,
            'efficiency': avg_eff,
            'avg_hr': avg_hr,
            'num_runs': len(runs),
        })
    
    # Volume progression
    pairs_time = [(i, m['volume']) for i, m in enumerate(months)]
    r, n = pearson(pairs_time)
    print(f"\nTime -> Monthly Volume: r={r:.3f} (n={n})")
    if r and r > 0.3:
        print("  ** SIGNAL: Progressive volume overload")
    
    # Volume vs next month efficiency
    pairs_lag = []
    for i in range(1, len(months)):
        pairs_lag.append((months[i-1]['volume'], months[i]['efficiency']))
    r, n = pearson(pairs_lag)
    print(f"Previous Month Volume -> Next Month Efficiency: r={r:.3f} (n={n})")
    if r and r > 0.3:
        print("  ** SIGNAL: Volume investment pays off next month")
    
    # Show progression
    print("\nMonthly Progression:")
    for m in months:
        print(f"  {m['month']}: {m['volume']:5.0f}km, {m['num_runs']:2} runs, eff={m['efficiency']:.4f}, HR={m['avg_hr']:.0f}")


def find_breakthrough_periods(activities: list):
    """Identify periods of significant improvement."""
    print("\n" + "="*70)
    print("BREAKTHROUGH PERIODS")
    print("="*70)
    
    # Calculate rolling efficiency
    window = 14  # 2-week rolling average
    rolling = []
    for i in range(window, len(activities)):
        window_runs = activities[i-window:i]
        avg_eff = sum(r['efficiency'] for r in window_runs) / len(window_runs)
        rolling.append({
            'end_date': activities[i]['date'],
            'avg_efficiency': avg_eff,
        })
    
    # Find biggest jumps
    if len(rolling) < 10:
        print("Not enough data for breakthrough analysis")
        return
    
    jumps = []
    for i in range(7, len(rolling)):
        prev = rolling[i-7]['avg_efficiency']
        curr = rolling[i]['avg_efficiency']
        change = (curr - prev) / prev * 100
        jumps.append({
            'date': rolling[i]['end_date'],
            'change_pct': change,
            'from_eff': prev,
            'to_eff': curr,
        })
    
    # Top 5 improvements
    jumps.sort(key=lambda x: x['change_pct'], reverse=True)
    
    print("\nTop 5 Efficiency Jumps (2-week rolling):")
    for j in jumps[:5]:
        print(f"  {j['date']}: +{j['change_pct']:.1f}% ({j['from_eff']:.4f} -> {j['to_eff']:.4f})")
    
    print("\nTop 5 Efficiency Drops (2-week rolling):")
    for j in jumps[-5:]:
        print(f"  {j['date']}: {j['change_pct']:.1f}% ({j['from_eff']:.4f} -> {j['to_eff']:.4f})")


def summarize_findings(weekly: list, activities: list):
    """Summarize the key findings."""
    print("\n" + "="*70)
    print("SUMMARY: WHAT DRIVES IMPROVEMENT")
    print("="*70)
    
    # Calculate all correlations
    findings = []
    
    # Volume correlations
    cumulative = 0
    pairs_cumulative = []
    for w in weekly:
        cumulative += w['volume_km']
        pairs_cumulative.append((cumulative, w['avg_efficiency']))
    r, n = pearson(pairs_cumulative)
    if r:
        findings.append(('Cumulative Volume -> Efficiency', r, n))
    
    # Rolling volume
    pairs_rolling = []
    for i in range(4, len(weekly)):
        rolling_vol = sum(weekly[j]['volume_km'] for j in range(i-4, i))
        pairs_rolling.append((rolling_vol, weekly[i]['avg_efficiency']))
    r, n = pearson(pairs_rolling)
    if r:
        findings.append(('Rolling 4-Week Volume -> Efficiency', r, n))
    
    # Consistency
    streak = 0
    pairs_streak = []
    for w in weekly:
        if w['num_runs'] >= 4:
            streak += 1
        else:
            streak = 0
        pairs_streak.append((streak, w['avg_efficiency']))
    r, n = pearson(pairs_streak)
    if r:
        findings.append(('Consistency Streak -> Efficiency', r, n))
    
    # Long runs
    pairs_count = []
    for i in range(4, len(weekly)):
        count_20k = sum(1 for j in range(i-4, i) if weekly[j]['long_run_km'] >= 20)
        pairs_count.append((count_20k, weekly[i]['avg_efficiency']))
    r, n = pearson(pairs_count)
    if r:
        findings.append(('20km+ Long Runs (4 weeks) -> Efficiency', r, n))
    
    # HR over time
    pairs_time = [(i, w['avg_hr']) for i, w in enumerate(weekly)]
    r, n = pearson(pairs_time)
    if r:
        findings.append(('Time -> Average HR (negative = improving)', r, n))
    
    # Sort by absolute correlation
    findings.sort(key=lambda x: abs(x[1]), reverse=True)
    
    print("\nRANKED CORRELATIONS (strongest first):\n")
    for name, r, n in findings:
        direction = "+" if r > 0 else "-"
        strength = "STRONG" if abs(r) > 0.5 else "MODERATE" if abs(r) > 0.3 else "WEAK"
        print(f"  {name}")
        print(f"    r = {r:+.3f} (n={n}) [{strength}]")
        print()
    
    print("\n" + "="*70)
    print("ACTIONABLE INSIGHTS")
    print("="*70)
    
    insights = []
    
    # Check cumulative volume
    r, n = pearson(pairs_cumulative)
    if r and r > 0.3:
        insights.append("Keep running. Total lifetime volume correlates with efficiency.")
    
    # Check consistency
    r, n = pearson(pairs_streak)
    if r and r > 0.2:
        insights.append("Stay consistent. Consecutive training weeks compound.")
    
    # Check long runs
    r, n = pearson(pairs_count)
    if r and r > 0.2:
        insights.append("Do your long runs. 20km+ runs in last 4 weeks predict efficiency.")
    
    # Check HR trend
    if len(weekly) >= 20:
        first_10_hr = sum(w['avg_hr'] for w in weekly[:10]) / 10
        last_10_hr = sum(w['avg_hr'] for w in weekly[-10:]) / 10
        if last_10_hr < first_10_hr - 5:
            insights.append(f"HR dropped {first_10_hr - last_10_hr:.0f}bpm over time. Aerobic base is building.")
    
    for i, insight in enumerate(insights, 1):
        print(f"\n{i}. {insight}")
    
    print("\n" + "="*70)


def main():
    athlete_name = sys.argv[1] if len(sys.argv) > 1 else "Michael Shaffer"
    
    print("="*70)
    print("WHAT DRIVES IMPROVEMENT?")
    print("="*70)
    print(f"\nAthlete: {athlete_name}")
    
    session = SessionLocal()
    try:
        activities = load_activities(session, athlete_name)
        print(f"Loaded {len(activities)} activities")
        
        if not activities:
            return
        
        weekly = calculate_weekly_metrics(activities)
        print(f"Calculated {len(weekly)} weekly aggregates")
        
        analyze_volume_efficiency(weekly)
        analyze_consistency(weekly)
        analyze_long_runs(weekly)
        analyze_intensity_distribution(weekly)
        analyze_hr_trends(weekly)
        analyze_periodization(activities)
        find_breakthrough_periods(activities)
        summarize_findings(weekly, activities)
        
    finally:
        session.close()


if __name__ == "__main__":
    main()


