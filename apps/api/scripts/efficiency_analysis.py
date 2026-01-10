"""
Efficiency Analysis Script
Calculates actual efficiency metrics and correlations from Michael's data.
"""
from sqlalchemy import create_engine, text
import os
from datetime import datetime, timedelta
import statistics

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
        
        print("=" * 70)
        print("EFFICIENCY ANALYSIS - Raw Data Exploration")
        print("=" * 70)
        
        # Get all activities with pace and HR in last 12 weeks
        result = conn.execute(text("""
            SELECT 
                id,
                start_time,
                distance_m,
                duration_s,
                avg_hr,
                max_hr,
                total_elevation_gain,
                (distance_m / duration_s * 3.6) as avg_speed_kph,
                (duration_s / 60.0) / (distance_m / 1000.0) as pace_min_per_km
            FROM activity 
            WHERE athlete_id = :id 
            AND avg_hr IS NOT NULL 
            AND distance_m > 0 
            AND duration_s > 0
            AND avg_hr > 60 AND avg_hr < 220
            ORDER BY start_time
        """), {"id": michael_id})
        
        activities = result.fetchall()
        print(f"\nTotal activities with valid pace+HR: {len(activities)}")
        
        # Calculate efficiency metric: pace per HR beat
        # Lower is better (faster pace per heart beat)
        efficiencies = []
        weekly_data = {}
        
        for row in activities:
            activity_id, start_time, distance_m, duration_s, avg_hr, max_hr, elevation, speed_kph, pace_min_km = row
            
            # Efficiency = pace / HR (lower = more efficient)
            # Alternative: speed / HR (higher = more efficient)
            efficiency = speed_kph / avg_hr if avg_hr > 0 else None
            
            if efficiency:
                week_key = start_time.strftime("%Y-W%W")
                efficiencies.append({
                    'date': start_time,
                    'week': week_key,
                    'distance_km': distance_m / 1000,
                    'pace_min_km': pace_min_km,
                    'avg_hr': avg_hr,
                    'max_hr': max_hr,
                    'elevation': elevation or 0,
                    'efficiency': efficiency,  # km/h per bpm
                    'speed_kph': speed_kph
                })
                
                if week_key not in weekly_data:
                    weekly_data[week_key] = []
                weekly_data[week_key].append(efficiencies[-1])
        
        print(f"Activities with calculable efficiency: {len(efficiencies)}")
        
        # Weekly aggregates
        print(f"\n--- WEEKLY EFFICIENCY TREND (last 12 weeks) ---")
        weeks_sorted = sorted(weekly_data.keys())[-12:]
        
        weekly_stats = []
        for week in weeks_sorted:
            runs = weekly_data[week]
            avg_eff = statistics.mean([r['efficiency'] for r in runs])
            total_km = sum([r['distance_km'] for r in runs])
            avg_hr = statistics.mean([r['avg_hr'] for r in runs])
            avg_pace = statistics.mean([r['pace_min_km'] for r in runs])
            run_count = len(runs)
            
            weekly_stats.append({
                'week': week,
                'efficiency': avg_eff,
                'volume_km': total_km,
                'avg_hr': avg_hr,
                'avg_pace': avg_pace,
                'run_count': run_count
            })
            print(f"  {week}: eff={avg_eff:.4f} vol={total_km:.1f}km runs={run_count} HR={avg_hr:.0f} pace={avg_pace:.1f}min/km")
        
        # Correlation: Volume vs Next Week's Efficiency
        print(f"\n--- CORRELATION ANALYSIS ---")
        
        if len(weekly_stats) >= 6:
            # Volume this week vs efficiency next week
            vol_eff_pairs = []
            for i in range(len(weekly_stats) - 1):
                vol_eff_pairs.append((weekly_stats[i]['volume_km'], weekly_stats[i+1]['efficiency']))
            
            if len(vol_eff_pairs) >= 5:
                volumes = [p[0] for p in vol_eff_pairs]
                next_effs = [p[1] for p in vol_eff_pairs]
                r = pearson_correlation(volumes, next_effs)
                print(f"\nVolume (km) vs Next Week Efficiency: r = {r:.3f}")
                print(f"  n = {len(vol_eff_pairs)} pairs")
                interpret_r(r, len(vol_eff_pairs), "volume on future efficiency")
            
            # Run frequency vs efficiency
            freq_eff_pairs = [(w['run_count'], w['efficiency']) for w in weekly_stats]
            freqs = [p[0] for p in freq_eff_pairs]
            effs = [p[1] for p in freq_eff_pairs]
            r = pearson_correlation(freqs, effs)
            print(f"\nRun Frequency vs Same-Week Efficiency: r = {r:.3f}")
            print(f"  n = {len(freq_eff_pairs)} pairs")
            interpret_r(r, len(freq_eff_pairs), "frequency on efficiency")
            
            # Average HR vs efficiency
            hr_eff_pairs = [(w['avg_hr'], w['efficiency']) for w in weekly_stats]
            hrs = [p[0] for p in hr_eff_pairs]
            effs = [p[1] for p in hr_eff_pairs]
            r = pearson_correlation(hrs, effs)
            print(f"\nAvg HR vs Efficiency: r = {r:.3f}")
            print(f"  n = {len(hr_eff_pairs)} pairs")
            interpret_r(r, len(hr_eff_pairs), "HR on efficiency")
        
        # Run-level analysis: distance, elevation, etc.
        print(f"\n--- RUN-LEVEL CORRELATIONS (Last 12 weeks only) ---")
        recent = [e for e in efficiencies if e['date'] > datetime.now(e['date'].tzinfo) - timedelta(weeks=12)]
        print(f"Recent runs analyzed: {len(recent)}")
        
        if len(recent) >= 20:
            # Distance vs efficiency
            dists = [r['distance_km'] for r in recent]
            effs = [r['efficiency'] for r in recent]
            r = pearson_correlation(dists, effs)
            print(f"\nDistance vs Efficiency: r = {r:.3f}")
            interpret_r(r, len(recent), "distance on efficiency")
            
            # Elevation vs efficiency
            elevs = [r['elevation'] for r in recent]
            if statistics.stdev(elevs) > 0:
                r = pearson_correlation(elevs, effs)
                print(f"\nElevation vs Efficiency: r = {r:.3f}")
                interpret_r(r, len(recent), "elevation on efficiency")
            else:
                print(f"\nElevation: Insufficient variation in data")
            
            # Speed vs HR (should be positive if HR tracking is valid)
            speeds = [r['speed_kph'] for r in recent]
            hrs = [r['avg_hr'] for r in recent]
            r = pearson_correlation(speeds, hrs)
            print(f"\nSpeed vs Avg HR: r = {r:.3f}")
            print(f"  (Expected: positive, as faster = harder)")
            interpret_r(r, len(recent), "speed on HR")
        
        # Efficiency trend over time
        print(f"\n--- EFFICIENCY TREND OVER TIME ---")
        if len(weekly_stats) >= 4:
            first_half = weekly_stats[:len(weekly_stats)//2]
            second_half = weekly_stats[len(weekly_stats)//2:]
            
            early_avg = statistics.mean([w['efficiency'] for w in first_half])
            late_avg = statistics.mean([w['efficiency'] for w in second_half])
            
            change_pct = (late_avg - early_avg) / early_avg * 100
            print(f"Early period avg efficiency: {early_avg:.4f}")
            print(f"Recent period avg efficiency: {late_avg:.4f}")
            print(f"Change: {change_pct:+.1f}%")
            
            if abs(change_pct) > 5:
                if change_pct > 0:
                    print("FINDING: Efficiency has IMPROVED over the analysis period")
                else:
                    print("FINDING: Efficiency has DECLINED over the analysis period")
            else:
                print("FINDING: Efficiency is relatively STABLE")
        
        print("\n" + "=" * 70)

def pearson_correlation(x, y):
    """Calculate Pearson correlation coefficient."""
    if len(x) != len(y) or len(x) < 3:
        return 0
    
    # Convert to float to handle Decimal types
    x = [float(v) for v in x]
    y = [float(v) for v in y]
    
    n = len(x)
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    
    numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    denominator = (sum((x[i] - mean_x)**2 for i in range(n)) * 
                   sum((y[i] - mean_y)**2 for i in range(n))) ** 0.5
    
    if denominator == 0:
        return 0
    
    return numerator / denominator

def interpret_r(r, n, context):
    """Interpret correlation coefficient."""
    # Calculate approximate p-value significance threshold
    # For n=20, |r| > 0.44 is significant at p<0.05
    # For n=30, |r| > 0.36 is significant at p<0.05
    # For n=50, |r| > 0.28 is significant at p<0.05
    
    threshold = 2.0 / (n ** 0.5) if n > 4 else 0.95
    
    strength = ""
    if abs(r) < 0.2:
        strength = "negligible"
    elif abs(r) < 0.4:
        strength = "weak"
    elif abs(r) < 0.6:
        strength = "moderate"
    elif abs(r) < 0.8:
        strength = "strong"
    else:
        strength = "very strong"
    
    direction = "positive" if r > 0 else "negative"
    sig = "likely significant" if abs(r) > threshold else "NOT significant (likely noise)"
    
    print(f"  Interpretation: {strength} {direction} relationship, {sig}")
    print(f"  (Significance threshold for n={n}: |r| > {threshold:.2f})")

if __name__ == "__main__":
    main()

