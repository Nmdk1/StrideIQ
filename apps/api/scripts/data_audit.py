"""
Data Audit Script
Analyzes data availability for diagnostic report generation.
"""
from sqlalchemy import create_engine, text
import os

def main():
    user = os.environ.get('POSTGRES_USER', 'postgres')
    password = os.environ.get('POSTGRES_PASSWORD', 'postgres')
    host = os.environ.get('POSTGRES_HOST', 'postgres')
    db = os.environ.get('POSTGRES_DB', 'running_app')
    db_url = f'postgresql://{user}:{password}@{host}:5432/{db}'
    
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        print("=" * 60)
        print("DATA AUDIT REPORT")
        print("=" * 60)
        
        # Find Michael's ID
        result = conn.execute(text("SELECT id, display_name, created_at FROM athlete WHERE display_name LIKE '%Michael%' OR display_name LIKE '%Shaffer%'"))
        rows = result.fetchall()
        if not rows:
            result = conn.execute(text("SELECT id, display_name, created_at FROM athlete LIMIT 1"))
            rows = result.fetchall()
        
        if rows:
            michael_id = rows[0][0]
            print(f"\nAthlete: {rows[0][1]}")
            print(f"Athlete ID: {michael_id}")
            print(f"Created: {rows[0][2]}")
        else:
            print("No athletes found!")
            return
        
        # Total activities
        result = conn.execute(text(f"SELECT COUNT(*) FROM activity WHERE athlete_id = :id"), {"id": michael_id})
        total = result.scalar()
        print(f"\n--- ACTIVITIES ---")
        print(f"Total activities: {total}")
        
        # Activities with HR
        result = conn.execute(text(f"SELECT COUNT(*) FROM activity WHERE athlete_id = :id AND avg_hr IS NOT NULL"), {"id": michael_id})
        hr_count = result.scalar()
        print(f"With heart rate data: {hr_count} ({100*hr_count/total:.1f}%)" if total > 0 else "With HR: 0")
        
        # Activities with pace (distance and time)
        result = conn.execute(text(f"SELECT COUNT(*) FROM activity WHERE athlete_id = :id AND distance_m > 0 AND duration_s > 0"), {"id": michael_id})
        pace_count = result.scalar()
        print(f"With pace data: {pace_count}")
        
        # Date range
        result = conn.execute(text(f"SELECT MIN(start_time), MAX(start_time) FROM activity WHERE athlete_id = :id"), {"id": michael_id})
        row = result.fetchone()
        print(f"Date range: {row[0].strftime('%Y-%m-%d') if row[0] else 'N/A'} to {row[1].strftime('%Y-%m-%d') if row[1] else 'N/A'}")
        
        # Last 12 weeks
        result = conn.execute(text(f"""
            SELECT COUNT(*) FROM activity 
            WHERE athlete_id = :id 
            AND start_time > NOW() - INTERVAL '12 weeks'
        """), {"id": michael_id})
        recent = result.scalar()
        print(f"Activities (last 12 weeks): {recent}")
        
        # Recent with HR
        result = conn.execute(text(f"""
            SELECT COUNT(*) FROM activity 
            WHERE athlete_id = :id 
            AND avg_hr IS NOT NULL
            AND start_time > NOW() - INTERVAL '12 weeks'
        """), {"id": michael_id})
        recent_hr = result.scalar()
        print(f"With HR (last 12 weeks): {recent_hr}")
        
        # Check-ins
        print(f"\n--- CHECK-INS ---")
        result = conn.execute(text(f"SELECT COUNT(*) FROM daily_checkin WHERE athlete_id = :id"), {"id": michael_id})
        checkins = result.scalar()
        print(f"Total check-ins: {checkins}")
        
        if checkins > 0:
            result = conn.execute(text(f"""
                SELECT 
                    COUNT(*) FILTER (WHERE sleep_h IS NOT NULL) as sleep,
                    COUNT(*) FILTER (WHERE stress_1_5 IS NOT NULL) as stress,
                    COUNT(*) FILTER (WHERE soreness_1_5 IS NOT NULL) as soreness,
                    COUNT(*) FILTER (WHERE hrv_rmssd IS NOT NULL) as hrv,
                    COUNT(*) FILTER (WHERE resting_hr IS NOT NULL) as rhr
                FROM daily_checkin WHERE athlete_id = :id
            """), {"id": michael_id})
            row = result.fetchone()
            print(f"  Sleep logged: {row[0]}")
            print(f"  Stress logged: {row[1]}")
            print(f"  Soreness logged: {row[2]}")
            print(f"  HRV logged: {row[3]}")
            print(f"  Resting HR logged: {row[4]}")
        
        # Nutrition
        print(f"\n--- NUTRITION ---")
        result = conn.execute(text(f"SELECT COUNT(*) FROM nutrition_entry WHERE athlete_id = :id"), {"id": michael_id})
        nutrition = result.scalar()
        print(f"Total nutrition entries: {nutrition}")
        
        # Body composition
        print(f"\n--- BODY COMPOSITION ---")
        result = conn.execute(text(f"SELECT COUNT(*) FROM body_composition WHERE athlete_id = :id"), {"id": michael_id})
        body = result.scalar()
        print(f"Total body comp entries: {body}")
        
        # Activity types breakdown
        print(f"\n--- ACTIVITY ANALYSIS (Last 12 weeks) ---")
        result = conn.execute(text(f"""
            SELECT 
                sport,
                COUNT(*) as count,
                AVG(distance_m) as avg_dist,
                AVG(avg_hr) as avg_hr
            FROM activity 
            WHERE athlete_id = :id 
            AND start_time > NOW() - INTERVAL '12 weeks'
            GROUP BY sport
            ORDER BY count DESC
        """), {"id": michael_id})
        for row in result:
            print(f"  {row[0]}: {row[1]} activities, avg {row[2]/1000:.1f}km, avg HR {row[3]:.0f}" if row[3] else f"  {row[0]}: {row[1]} activities")
        
        # Efficiency calculation feasibility
        print(f"\n--- EFFICIENCY ANALYSIS FEASIBILITY ---")
        result = conn.execute(text(f"""
            SELECT COUNT(*) FROM activity 
            WHERE athlete_id = :id 
            AND avg_hr IS NOT NULL 
            AND distance_m > 0 
            AND duration_s > 0
            AND start_time > NOW() - INTERVAL '12 weeks'
        """), {"id": michael_id})
        efficiency_capable = result.scalar()
        print(f"Activities with pace+HR (efficiency calculable): {efficiency_capable}")
        
        if efficiency_capable >= 20:
            print("STATUS: SUFFICIENT DATA for basic efficiency analysis")
        elif efficiency_capable >= 10:
            print("STATUS: MARGINAL DATA - correlations possible but low confidence")
        else:
            print("STATUS: INSUFFICIENT DATA for reliable correlations")
        
        # What's missing
        print(f"\n--- MISSING DATA IMPACT ---")
        if checkins == 0:
            print("! NO check-in data - cannot correlate sleep/stress/soreness to performance")
        if nutrition == 0:
            print("! NO nutrition data - cannot analyze food/timing effects")
        if hr_count < total * 0.8:
            print(f"! Only {100*hr_count/total:.0f}% of runs have HR - efficiency metrics may be incomplete")
        
        print("\n" + "=" * 60)

if __name__ == "__main__":
    main()


