"""
Garmin Data Export Importer

Imports data from Garmin's manual data export.
Focuses on raw metrics (HRV, Resting HR, Sleep Duration) but captures
all available data for exploration and correlation analysis.

Usage:
    python import_garmin_export.py <path_to_garmin_export>

Note: This is a manual process until we have Garmin API access.
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
import glob


def parse_garmin_timestamp(ts_str: str) -> Optional[datetime]:
    """Parse various Garmin timestamp formats."""
    if not ts_str:
        return None
    
    # Try ISO format first (without timezone)
    try:
        # Handle "2025-10-01T22:45:00.0"
        clean = ts_str.split('.')[0] if '.' in ts_str else ts_str
        return datetime.fromisoformat(clean.replace('Z', ''))
    except:
        pass
    
    # Try Garmin's weird format: "Wed Aug 07 16:58:23 GMT 2024"
    try:
        return datetime.strptime(ts_str, "%a %b %d %H:%M:%S GMT %Y")
    except:
        pass
    
    return None


def calculate_sleep_hours(start_ts: str, end_ts: str) -> Optional[float]:
    """Calculate sleep duration in hours from timestamps."""
    start = parse_garmin_timestamp(start_ts)
    end = parse_garmin_timestamp(end_ts)
    
    if start and end:
        delta = end - start
        return delta.total_seconds() / 3600.0
    return None


def load_json_files(pattern: str) -> list:
    """Load all JSON files matching a glob pattern."""
    all_data = []
    for filepath in glob.glob(pattern):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    all_data.extend(data)
                else:
                    all_data.append(data)
        except Exception as e:
            print(f"  Warning: Could not load {filepath}: {e}")
    return all_data


def import_sleep_data(export_path: Path) -> list:
    """Import sleep data - raw metrics only."""
    print("\n--- Importing Sleep Data ---")
    
    wellness_path = export_path / "DI_CONNECT" / "DI-Connect-Wellness"
    pattern = str(wellness_path / "*_sleepData.json")
    
    sleep_records = load_json_files(pattern)
    print(f"Found {len(sleep_records)} sleep records")
    
    processed = []
    for record in sleep_records:
        try:
            date_str = record.get('calendarDate')
            if not date_str:
                continue
            
            # RAW METRICS (trusted)
            hours_slept = calculate_sleep_hours(
                record.get('sleepStartTimestampGMT'),
                record.get('sleepEndTimestampGMT')
            )
            
            # SpO2 during sleep (raw data)
            spo2_summary = record.get('spo2SleepSummary', {})
            avg_spo2 = spo2_summary.get('averageSPO2')
            sleep_avg_hr = spo2_summary.get('averageHR')
            
            # DERIVED (skeptical - capture for exploration)
            deep_seconds = record.get('deepSleepSeconds', 0)
            light_seconds = record.get('lightSleepSeconds', 0)
            rem_seconds = record.get('remSleepSeconds', 0)
            total_sleep_seconds = deep_seconds + light_seconds + rem_seconds
            
            sleep_scores = record.get('sleepScores', {})
            
            processed.append({
                'date': date_str,
                # RAW (trusted)
                'hours_slept': round(hours_slept, 2) if hours_slept else None,
                'sleep_avg_hr': sleep_avg_hr,
                'avg_spo2': avg_spo2,
                # DERIVED (skeptical)
                'deep_pct': round(deep_seconds / total_sleep_seconds * 100, 1) if total_sleep_seconds > 0 else None,
                'rem_pct': round(rem_seconds / total_sleep_seconds * 100, 1) if total_sleep_seconds > 0 else None,
                'garmin_sleep_score': sleep_scores.get('overallScore'),
                'avg_sleep_stress': record.get('avgSleepStress'),
                'awake_count': record.get('awakeCount'),
            })
        except Exception as e:
            print(f"  Warning: Could not process sleep record: {e}")
    
    print(f"Processed {len(processed)} sleep records")
    return processed


def import_health_status_data(export_path: Path) -> list:
    """Import HRV and Resting HR."""
    print("\n--- Importing Health Status (HRV, RHR) ---")
    
    wellness_path = export_path / "DI_CONNECT" / "DI-Connect-Wellness"
    pattern = str(wellness_path / "*_healthStatusData.json")
    
    health_records = load_json_files(pattern)
    print(f"Found {len(health_records)} health status records")
    
    processed = []
    for record in health_records:
        try:
            date_str = record.get('calendarDate')
            if not date_str:
                continue
            
            metrics = record.get('metrics', [])
            entry = {'date': date_str}
            
            for metric in metrics:
                metric_type = metric.get('type')
                value = metric.get('value')
                
                if metric_type == 'HRV' and value is not None:
                    entry['hrv'] = value
                    entry['hrv_baseline_low'] = metric.get('baselineLowerLimit')
                    entry['hrv_baseline_high'] = metric.get('baselineUpperLimit')
                
                elif metric_type == 'HR' and value is not None:
                    entry['resting_hr'] = value
                    entry['rhr_baseline_low'] = metric.get('baselineLowerLimit')
                    entry['rhr_baseline_high'] = metric.get('baselineUpperLimit')
                
                elif metric_type == 'SPO2' and value is not None:
                    entry['daily_spo2'] = value
                
                elif metric_type == 'RESPIRATION' and value is not None:
                    entry['respiration'] = value
            
            if 'hrv' in entry or 'resting_hr' in entry:
                processed.append(entry)
                
        except Exception as e:
            print(f"  Warning: Could not process health record: {e}")
    
    print(f"Processed {len(processed)} health status records")
    return processed


def import_personal_records(export_path: Path) -> list:
    """Import running PRs."""
    print("\n--- Importing Personal Records ---")
    
    fitness_path = export_path / "DI_CONNECT" / "DI-Connect-Fitness"
    pattern = str(fitness_path / "*_personalRecord.json")
    
    all_records = []
    for filepath in glob.glob(pattern):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                records = data.get('personalRecords', [])
                all_records.extend(records)
        except Exception as e:
            print(f"  Warning: Could not load {filepath}: {e}")
    
    running_types = [
        'Best 1km Run', 'Best 1 Mile Run', 'Best 5km Run', 
        'Best 10km Run', 'Best Half Marathon', 'Best Marathon',
        'Farthest Run'
    ]
    
    processed = []
    for record in all_records:
        try:
            record_type = record.get('personalRecordType')
            if record_type not in running_types:
                continue
            if not record.get('current', False):
                continue
            
            value = record.get('value')
            date_str = record.get('prStartTimeGMT')
            
            if value and date_str:
                pr_date = parse_garmin_timestamp(date_str)
                
                # Format time
                if 'Best' in record_type:
                    minutes = value / 60
                    hours = int(minutes // 60)
                    mins = int(minutes % 60)
                    secs = int(value % 60)
                    time_str = f"{hours}:{mins:02d}:{secs:02d}" if hours > 0 else f"{mins}:{secs:02d}"
                else:
                    time_str = f"{value/1000:.2f} km"
                
                processed.append({
                    'type': record_type,
                    'value_seconds': value,
                    'display': time_str,
                    'date': pr_date.strftime('%Y-%m-%d') if pr_date else None,
                })
        except Exception as e:
            print(f"  Warning: Could not process PR: {e}")
    
    print(f"Processed {len(processed)} running PRs")
    return processed


def merge_daily_data(sleep_data: list, health_data: list) -> list:
    """Merge by date."""
    by_date = {}
    
    for record in health_data:
        date = record.get('date')
        if date:
            by_date[date] = record.copy()
    
    for record in sleep_data:
        date = record.get('date')
        if date:
            if date in by_date:
                by_date[date].update(record)
            else:
                by_date[date] = record.copy()
    
    merged = list(by_date.values())
    merged.sort(key=lambda x: x.get('date', ''))
    return merged


def analyze_correlations(daily_data: list):
    """Quick correlation analysis on the data."""
    print("\n" + "="*70)
    print("QUICK CORRELATION ANALYSIS")
    print("="*70)
    
    # Get paired data
    pairs_hrv_sleep = [(d['hrv'], d['hours_slept']) for d in daily_data 
                       if d.get('hrv') and d.get('hours_slept')]
    pairs_rhr_sleep = [(d['resting_hr'], d['hours_slept']) for d in daily_data 
                       if d.get('resting_hr') and d.get('hours_slept')]
    pairs_hrv_rhr = [(d['hrv'], d['resting_hr']) for d in daily_data 
                     if d.get('hrv') and d.get('resting_hr')]
    
    def pearson(pairs):
        if len(pairs) < 3:
            return None
        n = len(pairs)
        x = [p[0] for p in pairs]
        y = [p[1] for p in pairs]
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        num = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        den_x = sum((xi - mean_x) ** 2 for xi in x) ** 0.5
        den_y = sum((yi - mean_y) ** 2 for yi in y) ** 0.5
        if den_x == 0 or den_y == 0:
            return None
        return num / (den_x * den_y)
    
    print(f"\nHRV vs Sleep Duration: r = {pearson(pairs_hrv_sleep):.3f} (n={len(pairs_hrv_sleep)})" if pearson(pairs_hrv_sleep) else "HRV vs Sleep: insufficient data")
    print(f"Resting HR vs Sleep Duration: r = {pearson(pairs_rhr_sleep):.3f} (n={len(pairs_rhr_sleep)})" if pearson(pairs_rhr_sleep) else "RHR vs Sleep: insufficient data")
    print(f"HRV vs Resting HR: r = {pearson(pairs_hrv_rhr):.3f} (n={len(pairs_hrv_rhr)})" if pearson(pairs_hrv_rhr) else "HRV vs RHR: insufficient data")


def main():
    if len(sys.argv) < 2:
        print("Usage: python import_garmin_export.py <path_to_garmin_export>")
        sys.exit(1)
    
    export_path = Path(sys.argv[1])
    
    if not export_path.exists():
        print(f"Error: Path does not exist: {export_path}")
        sys.exit(1)
    
    print("="*70)
    print("GARMIN DATA EXPORT IMPORTER")
    print("="*70)
    print(f"\nExport path: {export_path}")
    
    # Import
    sleep_data = import_sleep_data(export_path)
    health_data = import_health_status_data(export_path)
    prs = import_personal_records(export_path)
    
    # Merge
    daily_data = merge_daily_data(sleep_data, health_data)
    
    # Stats
    print("\n" + "="*70)
    print("DATA SUMMARY")
    print("="*70)
    
    hrv_values = [d['hrv'] for d in daily_data if d.get('hrv')]
    rhr_values = [d['resting_hr'] for d in daily_data if d.get('resting_hr')]
    sleep_values = [d['hours_slept'] for d in daily_data if d.get('hours_slept')]
    
    print(f"\nTotal days: {len(daily_data)}")
    print(f"Date range: {daily_data[0]['date'] if daily_data else 'N/A'} to {daily_data[-1]['date'] if daily_data else 'N/A'}")
    
    print(f"\nDays with HRV: {len(hrv_values)}")
    if hrv_values:
        print(f"  Range: {min(hrv_values):.0f} - {max(hrv_values):.0f}, Avg: {sum(hrv_values)/len(hrv_values):.1f}")
    
    print(f"\nDays with Resting HR: {len(rhr_values)}")
    if rhr_values:
        print(f"  Range: {min(rhr_values):.0f} - {max(rhr_values):.0f}, Avg: {sum(rhr_values)/len(rhr_values):.1f}")
    
    print(f"\nDays with Sleep: {len(sleep_values)}")
    if sleep_values:
        print(f"  Range: {min(sleep_values):.1f}h - {max(sleep_values):.1f}h, Avg: {sum(sleep_values)/len(sleep_values):.1f}h")
    
    print("\n--- Personal Records ---")
    for pr in prs:
        print(f"  {pr['type']}: {pr['display']} ({pr['date']})")
    
    # Correlations
    analyze_correlations(daily_data)
    
    # Sample recent data
    print("\n" + "="*70)
    print("RECENT DATA (Last 14 days)")
    print("="*70)
    recent = daily_data[-14:]
    for day in recent:
        hrv = f"HRV={day.get('hrv', '-'):>3}" if day.get('hrv') else "HRV=  -"
        rhr = f"RHR={day.get('resting_hr', '-'):>3}" if day.get('resting_hr') else "RHR=  -"
        sleep = f"Sleep={day.get('hours_slept', 0):.1f}h" if day.get('hours_slept') else "Sleep=   -"
        print(f"  {day['date']}: {hrv} {rhr} {sleep}")
    
    # Save to JSON
    output = {
        'import_date': datetime.now().isoformat(),
        'daily_data': daily_data,
        'personal_records': prs,
    }
    
    output_path = Path('garmin_import_review.json')
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n\nFull data saved to: {output_path}")
    print("="*70)


if __name__ == "__main__":
    main()
