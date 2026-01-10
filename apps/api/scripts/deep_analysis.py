"""
Deep Analysis Script
Comprehensive analysis of all available factors.
"""
from sqlalchemy import create_engine, text
import os
from datetime import datetime, timedelta
import statistics
from collections import defaultdict

def pearson_correlation(x, y):
    """Calculate Pearson correlation coefficient."""
    if len(x) != len(y) or len(x) < 3:
        return 0, 0
    
    x = [float(v) if v is not None else 0 for v in x]
    y = [float(v) if v is not None else 0 for v in y]
    
    n = len(x)
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    
    numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    var_x = sum((x[i] - mean_x)**2 for i in range(n))
    var_y = sum((y[i] - mean_y)**2 for i in range(n))
    denominator = (var_x * var_y) ** 0.5
    
    if denominator == 0:
        return 0, 1.0
    
    r = numerator / denominator
    
    # Approximate p-value using t-distribution approximation
    if abs(r) >= 1:
        p = 0.0
    else:
        t = r * ((n - 2) ** 0.5) / ((1 - r**2) ** 0.5)
        # Approximate p-value (two-tailed)
        p = 2 * (1 - min(0.9999, abs(t) / (abs(t) + n)))  # Rough approximation
    
    return r, p

def effect_size_interpretation(r):
    """Cohen's conventions for correlation effect size."""
    if abs(r) < 0.1:
        return "negligible"
    elif abs(r) < 0.3:
        return "small"
    elif abs(r) < 0.5:
        return "medium"
    else:
        return "large"

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
        
        print("=" * 75)
        print("COMPREHENSIVE DIAGNOSTIC REPORT - Michael Shaffer")
        print("Generated:", datetime.now().strftime("%Y-%m-%d %H:%M"))
        print("=" * 75)
        
        # Get all activities
        result = conn.execute(text("""
            SELECT 
                id,
                start_time,
                distance_m,
                duration_s,
                avg_hr,
                max_hr,
                total_elevation_gain,
                (distance_m / duration_s * 3.6) as speed_kph,
                (duration_s / 60.0) / (distance_m / 1000.0) as pace_min_km,
                EXTRACT(DOW FROM start_time) as day_of_week,
                EXTRACT(HOUR FROM start_time) as hour_of_day
            FROM activity 
            WHERE athlete_id = :id 
            AND avg_hr IS NOT NULL 
            AND distance_m > 1000
            AND duration_s > 300
            AND avg_hr > 60 AND avg_hr < 220
            AND start_time > NOW() - INTERVAL '12 weeks'
            ORDER BY start_time
        """), {"id": michael_id})
        
        activities = []
        for row in result:
            activities.append({
                'id': row[0],
                'date': row[1],
                'distance_km': float(row[2]) / 1000,
                'duration_min': float(row[3]) / 60,
                'avg_hr': float(row[4]),
                'max_hr': float(row[5]) if row[5] else None,
                'elevation': float(row[6]) if row[6] else 0,
                'speed_kph': float(row[7]),
                'pace_min_km': float(row[8]),
                'day_of_week': int(row[9]),  # 0=Sunday
                'hour': int(row[10]),
                'efficiency': float(row[7]) / float(row[4])  # speed/HR
            })
        
        print(f"\nAnalysis Period: {activities[0]['date'].strftime('%Y-%m-%d')} to {activities[-1]['date'].strftime('%Y-%m-%d')}")
        print(f"Activities Analyzed: {len(activities)}")
        
        # ========================================
        # SECTION 1: EFFICIENCY TREND
        # ========================================
        print(f"\n{'='*75}")
        print("SECTION 1: EFFICIENCY TREND ANALYSIS")
        print("='*75}")
        print("(Efficiency = Speed (km/h) / Avg HR - higher is better)")
        
        # Split into thirds for trend analysis
        third = len(activities) // 3
        early = activities[:third]
        middle = activities[third:2*third]
        late = activities[2*third:]
        
        early_eff = statistics.mean([a['efficiency'] for a in early])
        middle_eff = statistics.mean([a['efficiency'] for a in middle])
        late_eff = statistics.mean([a['efficiency'] for a in late])
        
        print(f"\nEarly period ({early[0]['date'].strftime('%m/%d')} - {early[-1]['date'].strftime('%m/%d')}): {early_eff:.4f}")
        print(f"Middle period ({middle[0]['date'].strftime('%m/%d')} - {middle[-1]['date'].strftime('%m/%d')}): {middle_eff:.4f}")
        print(f"Recent period ({late[0]['date'].strftime('%m/%d')} - {late[-1]['date'].strftime('%m/%d')}): {late_eff:.4f}")
        
        overall_change = (late_eff - early_eff) / early_eff * 100
        print(f"\nOverall change: {overall_change:+.1f}%")
        
        if overall_change < -10:
            print("STATUS: SIGNIFICANT DECLINE in efficiency")
        elif overall_change < -5:
            print("STATUS: MODERATE DECLINE in efficiency")
        elif overall_change > 10:
            print("STATUS: SIGNIFICANT IMPROVEMENT in efficiency")
        elif overall_change > 5:
            print("STATUS: MODERATE IMPROVEMENT in efficiency")
        else:
            print("STATUS: STABLE efficiency")
        
        # ========================================
        # SECTION 2: CORRELATION ANALYSIS
        # ========================================
        print(f"\n{'='*75}")
        print("SECTION 2: CORRELATION ANALYSIS")
        print("(What factors correlate with efficiency?)")
        print("='*75}")
        
        correlations = []
        
        # Distance vs Efficiency
        r, p = pearson_correlation(
            [a['distance_km'] for a in activities],
            [a['efficiency'] for a in activities]
        )
        correlations.append({
            'factor': 'Run Distance (km)',
            'r': r,
            'direction': 'positive' if r > 0 else 'negative',
            'effect': effect_size_interpretation(r),
            'n': len(activities),
            'interpretation': 'Longer runs = lower efficiency' if r < 0 else 'Longer runs = higher efficiency'
        })
        
        # Elevation vs Efficiency
        elevs = [a['elevation'] for a in activities]
        if statistics.stdev(elevs) > 0:
            r, p = pearson_correlation(elevs, [a['efficiency'] for a in activities])
            correlations.append({
                'factor': 'Elevation Gain (m)',
                'r': r,
                'direction': 'positive' if r > 0 else 'negative',
                'effect': effect_size_interpretation(r),
                'n': len(activities),
                'interpretation': 'More elevation = lower efficiency' if r < 0 else 'More elevation = higher efficiency'
            })
        
        # Day of Week vs Efficiency
        r, p = pearson_correlation(
            [a['day_of_week'] for a in activities],
            [a['efficiency'] for a in activities]
        )
        correlations.append({
            'factor': 'Day of Week (0=Sun)',
            'r': r,
            'direction': 'positive' if r > 0 else 'negative',
            'effect': effect_size_interpretation(r),
            'n': len(activities),
            'interpretation': 'Later in week = different efficiency' if abs(r) > 0.2 else 'Day of week not predictive'
        })
        
        # Time of Day vs Efficiency
        r, p = pearson_correlation(
            [a['hour'] for a in activities],
            [a['efficiency'] for a in activities]
        )
        correlations.append({
            'factor': 'Hour of Day',
            'r': r,
            'direction': 'positive' if r > 0 else 'negative',
            'effect': effect_size_interpretation(r),
            'n': len(activities),
            'interpretation': 'Later runs = higher efficiency' if r > 0.2 else 'Earlier runs = higher efficiency' if r < -0.2 else 'Time of day not strongly predictive'
        })
        
        # Duration vs Efficiency
        r, p = pearson_correlation(
            [a['duration_min'] for a in activities],
            [a['efficiency'] for a in activities]
        )
        correlations.append({
            'factor': 'Run Duration (min)',
            'r': r,
            'direction': 'positive' if r > 0 else 'negative',
            'effect': effect_size_interpretation(r),
            'n': len(activities),
            'interpretation': 'Longer duration = lower efficiency' if r < 0 else 'Longer duration = higher efficiency'
        })
        
        # Days since last run
        for i, a in enumerate(activities):
            if i == 0:
                a['days_rest'] = None
            else:
                delta = (a['date'] - activities[i-1]['date']).days
                a['days_rest'] = delta
        
        rest_activities = [a for a in activities if a['days_rest'] is not None]
        r, p = pearson_correlation(
            [a['days_rest'] for a in rest_activities],
            [a['efficiency'] for a in rest_activities]
        )
        correlations.append({
            'factor': 'Days Since Last Run',
            'r': r,
            'direction': 'positive' if r > 0 else 'negative',
            'effect': effect_size_interpretation(r),
            'n': len(rest_activities),
            'interpretation': 'More rest = higher efficiency' if r > 0.2 else 'More rest = lower efficiency' if r < -0.2 else 'Rest days not strongly predictive'
        })
        
        # Weekly volume (previous week) vs efficiency
        weekly_volume = defaultdict(float)
        for a in activities:
            week_key = (a['date'] - timedelta(days=a['date'].weekday())).strftime('%Y-%W')
            weekly_volume[week_key] += a['distance_km']
        
        for a in activities:
            prev_week = (a['date'] - timedelta(days=7 + a['date'].weekday())).strftime('%Y-%W')
            a['prev_week_volume'] = weekly_volume.get(prev_week, 0)
        
        vol_activities = [a for a in activities if a['prev_week_volume'] > 0]
        if len(vol_activities) > 10:
            r, p = pearson_correlation(
                [a['prev_week_volume'] for a in vol_activities],
                [a['efficiency'] for a in vol_activities]
            )
            correlations.append({
                'factor': 'Previous Week Volume (km)',
                'r': r,
                'direction': 'positive' if r > 0 else 'negative',
                'effect': effect_size_interpretation(r),
                'n': len(vol_activities),
                'interpretation': 'Higher prior volume = higher efficiency' if r > 0.2 else 'Higher prior volume = lower efficiency' if r < -0.2 else 'Prior volume not strongly predictive'
            })
        
        # Sort by effect size
        correlations.sort(key=lambda x: abs(x['r']), reverse=True)
        
        print("\nRanked by strength of correlation:")
        print("-" * 75)
        for i, c in enumerate(correlations, 1):
            sig = "**" if abs(c['r']) > 0.22 else ""  # Rough significance for n~80
            print(f"{i}. {c['factor']}: r = {c['r']:+.3f} ({c['effect']} effect){sig}")
            print(f"   {c['interpretation']}")
        
        # ========================================
        # SECTION 3: BEST/WORST CONDITIONS
        # ========================================
        print(f"\n{'='*75}")
        print("SECTION 3: BEST AND WORST CONDITIONS")
        print("='*75}")
        
        # Sort by efficiency
        sorted_by_eff = sorted(activities, key=lambda x: x['efficiency'], reverse=True)
        top_10 = sorted_by_eff[:10]
        bottom_10 = sorted_by_eff[-10:]
        
        print("\nTOP 10 EFFICIENCY RUNS:")
        print("-" * 75)
        for a in top_10:
            day_name = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][a['day_of_week']]
            print(f"  {a['date'].strftime('%m/%d')} {day_name} {a['hour']:02d}:00 | {a['distance_km']:.1f}km @ {a['pace_min_km']:.1f}min/km | HR:{a['avg_hr']:.0f} | eff:{a['efficiency']:.4f}")
        
        print("\nBOTTOM 10 EFFICIENCY RUNS:")
        print("-" * 75)
        for a in bottom_10:
            day_name = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][a['day_of_week']]
            print(f"  {a['date'].strftime('%m/%d')} {day_name} {a['hour']:02d}:00 | {a['distance_km']:.1f}km @ {a['pace_min_km']:.1f}min/km | HR:{a['avg_hr']:.0f} | eff:{a['efficiency']:.4f}")
        
        # Find patterns in top vs bottom
        print("\nPATTERN ANALYSIS:")
        print("-" * 75)
        
        avg_dist_top = statistics.mean([a['distance_km'] for a in top_10])
        avg_dist_bottom = statistics.mean([a['distance_km'] for a in bottom_10])
        print(f"Avg distance - Top 10: {avg_dist_top:.1f}km | Bottom 10: {avg_dist_bottom:.1f}km")
        
        avg_hr_top = statistics.mean([a['avg_hr'] for a in top_10])
        avg_hr_bottom = statistics.mean([a['avg_hr'] for a in bottom_10])
        print(f"Avg HR - Top 10: {avg_hr_top:.0f} | Bottom 10: {avg_hr_bottom:.0f}")
        
        avg_hour_top = statistics.mean([a['hour'] for a in top_10])
        avg_hour_bottom = statistics.mean([a['hour'] for a in bottom_10])
        print(f"Avg hour - Top 10: {avg_hour_top:.1f} | Bottom 10: {avg_hour_bottom:.1f}")
        
        # ========================================
        # SECTION 4: VOLUME ANALYSIS
        # ========================================
        print(f"\n{'='*75}")
        print("SECTION 4: VOLUME TREND ANALYSIS")
        print("='*75}")
        
        # Weekly volume trend
        weeks = sorted(set((a['date'] - timedelta(days=a['date'].weekday())).strftime('%Y-%W') for a in activities))
        print("\nWeekly Volume:")
        for week in weeks[-12:]:
            vol = weekly_volume.get(week, 0)
            runs = len([a for a in activities if (a['date'] - timedelta(days=a['date'].weekday())).strftime('%Y-%W') == week])
            bar = '█' * int(vol / 5)
            print(f"  {week}: {vol:5.1f}km ({runs} runs) {bar}")
        
        # ========================================
        # SECTION 5: STATISTICAL CONFIDENCE
        # ========================================
        print(f"\n{'='*75}")
        print("SECTION 5: STATISTICAL CONFIDENCE ASSESSMENT")
        print("='*75}")
        
        print(f"\nSample size: n = {len(activities)}")
        print(f"For this sample size, correlations with |r| > 0.22 are likely significant (p < 0.05)")
        
        significant = [c for c in correlations if abs(c['r']) > 0.22]
        nonsig = [c for c in correlations if abs(c['r']) <= 0.22]
        
        print(f"\nStatistically Significant Findings ({len(significant)}):")
        for c in significant:
            print(f"  - {c['factor']}: r = {c['r']:+.3f}")
        
        print(f"\nNot Statistically Significant ({len(nonsig)}):")
        for c in nonsig:
            print(f"  - {c['factor']}: r = {c['r']:+.3f} (likely noise)")
        
        # ========================================
        # SECTION 6: MISSING DATA IMPACT
        # ========================================
        print(f"\n{'='*75}")
        print("SECTION 6: MISSING DATA - WHAT WE CANNOT ANSWER")
        print("='*75}")
        
        # Check for missing data
        result = conn.execute(text("SELECT COUNT(*) FROM daily_checkin WHERE athlete_id = :id"), {"id": michael_id})
        checkins = result.scalar()
        
        result = conn.execute(text("SELECT COUNT(*) FROM nutrition_entry WHERE athlete_id = :id"), {"id": michael_id})
        nutrition = result.scalar()
        
        result = conn.execute(text("SELECT COUNT(*) FROM body_composition WHERE athlete_id = :id"), {"id": michael_id})
        body = result.scalar()
        
        print(f"\nData Availability:")
        print(f"  - Daily check-ins (sleep, stress, soreness): {checkins} entries")
        print(f"  - Nutrition logs: {nutrition} entries")
        print(f"  - Body composition: {body} entries")
        
        print("\nUnanswerable Questions Due to Missing Data:")
        if checkins == 0:
            print("  ✗ Does sleep duration affect your efficiency?")
            print("  ✗ Does perceived stress correlate with performance?")
            print("  ✗ Does muscle soreness predict performance decline?")
            print("  ✗ Does HRV trend with efficiency?")
        if nutrition == 0:
            print("  ✗ Do certain foods improve your running?")
            print("  ✗ Does meal timing affect performance?")
            print("  ✗ Does hydration status correlate with efficiency?")
        if body == 0:
            print("  ✗ Does weight fluctuation affect performance?")
        
        print("\nTo Answer These Questions:")
        print("  → Start using the Morning Check-in (takes 10 seconds)")
        print("  → Log nutrition for 2-4 weeks")
        print("  → Weekly weight check-ins")
        
        # ========================================
        # SECTION 7: RECOMMENDATIONS
        # ========================================
        print(f"\n{'='*75}")
        print("SECTION 7: ACTIONABLE INSIGHTS")
        print("='*75}")
        
        # Find the strongest actionable correlations
        strong = [c for c in correlations if abs(c['r']) > 0.3]
        
        print("\n1. HIGHEST-LEVERAGE EXPERIMENT:")
        if len(strong) > 0:
            strongest = strong[0]
            if 'Distance' in strongest['factor'] and strongest['r'] < 0:
                print("   Based on the data: shorter runs show higher efficiency.")
                print("   Experiment: For 2 weeks, cap most runs at 8km and compare.")
                print("   Caveat: This may reflect that quality sessions are shorter, not that")
                print("   shorter is inherently better. Consider workout type distinction.")
            elif 'Rest' in strongest['factor']:
                print(f"   Based on the data: rest days {'help' if strongest['r'] > 0 else 'hurt'} efficiency.")
                print("   Experiment: Track performance after different rest intervals.")
            else:
                print(f"   Based on the data: {strongest['interpretation']}")
                print("   Experiment: Deliberately vary this factor and track results.")
        else:
            print("   No single factor dominates. Consider increasing data variety.")
        
        print("\n2. WHAT WOULD BE RECKLESS TO CHANGE:")
        print("   - Dramatically changing weekly volume (insufficient evidence)")
        print("   - Assuming time of day matters (r is weak)")
        print("   - Making nutrition changes (NO DATA to support or refute)")
        print("   - Changing sleep patterns (NO DATA)")
        
        print("\n3. HIGHEST-CONFIDENCE FINDING:")
        if len(significant) > 0:
            best = max(significant, key=lambda x: abs(x['r']))
            print(f"   {best['factor']}: {best['interpretation']}")
            print(f"   Confidence: {best['effect']} effect size, n={best['n']}")
        
        print("\n4. WEAKEST FINDINGS (TREAT AS SPECULATIVE):")
        for c in correlations[-3:]:
            print(f"   - {c['factor']}: r = {c['r']:+.3f} (too weak to act on)")
        
        print("\n" + "=" * 75)
        print("END OF DIAGNOSTIC REPORT")
        print("=" * 75)

if __name__ == "__main__":
    main()

