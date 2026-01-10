"""
Build Population Baselines from Research Data

Processes the Figshare running dataset to create population baselines
for "people like you" comparisons.

Outputs:
- Weekly volume percentiles by age/gender
- Race time distributions by age/gender/distance
- Training consistency metrics
"""

import pandas as pd
import json
import os
from pathlib import Path

# Paths
DATA_DIR = Path(__file__).parent.parent / "data" / "research"
OUTPUT_DIR = Path(__file__).parent.parent / "apps" / "api" / "services" / "research_data" / "baselines"

def load_data():
    """Load all available parquet files"""
    print("Loading research data...")
    
    files = list(DATA_DIR.glob("run_ww_*_d.parquet"))
    if not files:
        print(f"No data files found in {DATA_DIR}")
        return None
    
    dfs = []
    for f in files:
        print(f"  Loading {f.name}...")
        df = pd.read_parquet(f, engine='fastparquet')
        dfs.append(df)
    
    df = pd.concat(dfs, ignore_index=True)
    print(f"Total records: {len(df):,}")
    print(f"Unique athletes: {df['athlete'].nunique():,}")
    return df


def build_weekly_volume_baselines(df):
    """Build weekly volume percentiles by age/gender"""
    print("\n" + "="*70)
    print("WEEKLY VOLUME BASELINES BY AGE/GENDER")
    print("="*70)
    
    baselines = {}
    
    for gender in ['M', 'F']:
        for age_group in ['18 - 34', '35 - 54', '55 +']:
            cohort = df[(df['gender'] == gender) & (df['age_group'] == age_group)].copy()
            
            # Group by athlete and week
            cohort['week'] = cohort['datetime'].dt.isocalendar().week
            cohort['year'] = cohort['datetime'].dt.year
            
            weekly = cohort.groupby(['athlete', 'year', 'week'])['distance'].sum().reset_index()
            active_weeks = weekly[weekly['distance'] > 0]
            
            if len(active_weeks) > 100:
                key = f"{gender}_{age_group.replace(' ', '').replace('-', '_')}"
                baselines[key] = {
                    'gender': gender,
                    'age_group': age_group,
                    'sample_size': int(len(active_weeks)),
                    'athletes': int(cohort['athlete'].nunique()),
                    'weekly_km': {
                        'mean': round(active_weeks['distance'].mean(), 1),
                        'median': round(active_weeks['distance'].median(), 1),
                        'p10': round(active_weeks['distance'].quantile(0.10), 1),
                        'p25': round(active_weeks['distance'].quantile(0.25), 1),
                        'p75': round(active_weeks['distance'].quantile(0.75), 1),
                        'p90': round(active_weeks['distance'].quantile(0.90), 1),
                    }
                }
                print(f"\n{gender} {age_group}:")
                print(f"  Athletes: {baselines[key]['athletes']:,}")
                print(f"  Active weeks: {baselines[key]['sample_size']:,}")
                print(f"  Mean: {baselines[key]['weekly_km']['mean']} km/week")
                print(f"  Median: {baselines[key]['weekly_km']['median']} km/week")
                print(f"  10th-90th: {baselines[key]['weekly_km']['p10']} - {baselines[key]['weekly_km']['p90']} km")
    
    return baselines


def build_race_time_baselines(df):
    """Build race time distributions by age/gender/distance"""
    print("\n" + "="*70)
    print("RACE TIME BASELINES BY AGE/GENDER/DISTANCE")
    print("="*70)
    
    # Race distance definitions
    race_distances = {
        '5K': (4.5, 5.5),
        '10K': (9.5, 10.5),
        'half_marathon': (20, 22),
        'marathon': (40, 45),
    }
    
    baselines = {}
    
    for distance_name, (min_d, max_d) in race_distances.items():
        print(f"\n{distance_name}:")
        
        # Filter to this distance and race-pace efforts
        race_runs = df[(df['distance'] >= min_d) & (df['distance'] <= max_d)].copy()
        race_runs['pace'] = race_runs['duration'] / race_runs['distance']
        race_runs = race_runs[(race_runs['pace'] >= 3) & (race_runs['pace'] <= 10)]
        
        for gender in ['M', 'F']:
            for age_group in ['18 - 34', '35 - 54', '55 +']:
                cohort = race_runs[(race_runs['gender'] == gender) & (race_runs['age_group'] == age_group)]
                
                if len(cohort) > 50:
                    key = f"{distance_name}_{gender}_{age_group.replace(' ', '').replace('-', '_')}"
                    
                    # Calculate finish times
                    times = cohort['duration']  # in minutes
                    
                    baselines[key] = {
                        'distance': distance_name,
                        'gender': gender,
                        'age_group': age_group,
                        'sample_size': int(len(cohort)),
                        'finish_time_minutes': {
                            'mean': round(times.mean(), 1),
                            'median': round(times.median(), 1),
                            'p10': round(times.quantile(0.10), 1),  # Fast
                            'p25': round(times.quantile(0.25), 1),
                            'p50': round(times.quantile(0.50), 1),
                            'p75': round(times.quantile(0.75), 1),
                            'p90': round(times.quantile(0.90), 1),  # Slow
                        }
                    }
                    
                    median_mins = baselines[key]['finish_time_minutes']['median']
                    h = int(median_mins // 60)
                    m = int(median_mins % 60)
                    print(f"  {gender} {age_group}: {len(cohort):,} races, median {h}:{m:02d}")
    
    return baselines


def build_training_consistency_baselines(df):
    """Build training consistency metrics"""
    print("\n" + "="*70)
    print("TRAINING CONSISTENCY BASELINES")
    print("="*70)
    
    baselines = {}
    
    for gender in ['M', 'F']:
        for age_group in ['18 - 34', '35 - 54', '55 +']:
            cohort = df[(df['gender'] == gender) & (df['age_group'] == age_group)].copy()
            
            # Calculate runs per week per athlete
            cohort['week'] = cohort['datetime'].dt.isocalendar().week
            cohort['year'] = cohort['datetime'].dt.year
            cohort['has_run'] = (cohort['distance'] > 0).astype(int)
            
            weekly_runs = cohort.groupby(['athlete', 'year', 'week'])['has_run'].sum().reset_index()
            active_weeks = weekly_runs[weekly_runs['has_run'] > 0]
            
            if len(active_weeks) > 100:
                key = f"{gender}_{age_group.replace(' ', '').replace('-', '_')}"
                baselines[key] = {
                    'gender': gender,
                    'age_group': age_group,
                    'runs_per_week': {
                        'mean': round(active_weeks['has_run'].mean(), 1),
                        'median': round(active_weeks['has_run'].median(), 1),
                        'p25': round(active_weeks['has_run'].quantile(0.25), 1),
                        'p75': round(active_weeks['has_run'].quantile(0.75), 1),
                    }
                }
                print(f"{gender} {age_group}: {baselines[key]['runs_per_week']['mean']} runs/week avg")
    
    return baselines


def main():
    # Load data
    df = load_data()
    if df is None:
        return
    
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Build baselines
    weekly_baselines = build_weekly_volume_baselines(df)
    race_baselines = build_race_time_baselines(df)
    consistency_baselines = build_training_consistency_baselines(df)
    
    # Combine all baselines
    all_baselines = {
        'metadata': {
            'source': 'Figshare Long-Distance Running Dataset 2019-2020',
            'total_records': int(len(df)),
            'unique_athletes': int(df['athlete'].nunique()),
            'generated_by': 'build_research_baselines.py'
        },
        'weekly_volume': weekly_baselines,
        'race_times': race_baselines,
        'training_consistency': consistency_baselines,
    }
    
    # Save
    output_file = OUTPUT_DIR / "population_baselines.json"
    with open(output_file, 'w') as f:
        json.dump(all_baselines, f, indent=2)
    
    print("\n" + "="*70)
    print(f"SAVED TO: {output_file}")
    print("="*70)


if __name__ == "__main__":
    main()


