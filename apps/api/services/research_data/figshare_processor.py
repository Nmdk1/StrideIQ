"""
Figshare Long-Distance Running Dataset Processor

Dataset: "A public dataset on long-distance running training in 2019 and 2020"
Source: https://figshare.com/articles/dataset/A_public_dataset_on_long-distance_running_training_in_2019_and_2020/16620238

Contains:
- 10+ million training records
- 36,000+ athletes worldwide
- Training activities with duration, distance, pace, elevation
- Activity types and timestamps

Our Processing Goals:
1. Filter to recreational athletes (not elites)
2. Age-grade where possible
3. Extract patterns: volume progressions, efficiency trends, injury indicators
4. Build population baselines for "people like you" comparisons
5. Identify what ACTUALLY helps recreational runners improve
"""

import csv
import json
import os
from dataclasses import dataclass
from typing import List, Dict, Optional, Iterator, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import statistics
import logging

from .age_grading import (
    age_grade_performance, 
    classify_performance_level,
    get_population_percentile_by_age_grade
)

logger = logging.getLogger(__name__)


@dataclass
class RawTrainingRecord:
    """Single training record from Figshare dataset"""
    athlete_id: str
    activity_date: datetime
    activity_type: str  # run, bike, swim, etc.
    duration_seconds: float
    distance_meters: float
    elevation_gain_meters: Optional[float]
    avg_pace_sec_per_km: Optional[float]
    avg_hr: Optional[int]


@dataclass
class AthleteProfile:
    """Aggregated profile for an athlete from research data"""
    athlete_id: str
    total_activities: int
    
    # Volume metrics
    avg_weekly_distance_km: float
    avg_weekly_duration_hours: float
    avg_weekly_runs: float
    
    # Pace metrics (if available)
    avg_easy_pace_per_km: Optional[float]  # seconds
    best_estimated_5k: Optional[float]  # seconds
    best_estimated_10k: Optional[float]
    best_estimated_half: Optional[float]
    best_estimated_marathon: Optional[float]
    
    # Consistency metrics
    weeks_with_data: int
    training_consistency_pct: float  # % of weeks with 3+ runs
    
    # Progression indicators
    volume_trend: str  # "building", "stable", "declining"
    pace_trend: str  # "improving", "stable", "declining"
    
    # Classification
    runner_level: str  # "beginner", "recreational", "competitive", etc.
    estimated_age_grade_pct: Optional[float]


@dataclass
class PopulationBaseline:
    """Population-level baseline statistics"""
    cohort_name: str  # e.g., "recreational_40-50mpw"
    sample_size: int
    
    # Volume stats
    avg_weekly_km: float
    median_weekly_km: float
    p25_weekly_km: float
    p75_weekly_km: float
    
    # Pace stats (easy pace)
    avg_easy_pace_per_km: float
    median_easy_pace_per_km: float
    
    # Progression stats
    typical_weekly_volume_increase_pct: float
    typical_pace_improvement_per_month: float  # seconds per km
    
    # Risk indicators
    avg_runs_before_injury_spike: int
    risky_volume_increase_threshold_pct: float


class FigshareDataProcessor:
    """
    Processes the Figshare running dataset to extract patterns
    that help recreational runners.
    """
    
    # Filter criteria for "recreational" athletes
    MIN_TOTAL_ACTIVITIES = 50  # Need enough data to be meaningful
    MAX_WEEKLY_VOLUME_KM = 150  # Filter out likely elites
    MIN_WEEKLY_VOLUME_KM = 10  # Filter out very casual joggers
    
    def __init__(self, data_path: str):
        """
        Initialize processor with path to downloaded dataset.
        
        Expected format: CSV with columns for activity data
        """
        self.data_path = data_path
        self.athletes: Dict[str, List[RawTrainingRecord]] = defaultdict(list)
        self.baselines: Dict[str, PopulationBaseline] = {}
    
    def load_data(self, limit: Optional[int] = None) -> int:
        """
        Load data from CSV file.
        Returns count of records loaded.
        """
        if not os.path.exists(self.data_path):
            logger.warning(f"Dataset not found at {self.data_path}")
            return 0
        
        count = 0
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    record = self._parse_row(row)
                    if record and record.activity_type.lower() in ('run', 'running'):
                        self.athletes[record.athlete_id].append(record)
                        count += 1
                        
                    if limit and count >= limit:
                        break
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            
        logger.info(f"Loaded {count} records from {len(self.athletes)} athletes")
        return count
    
    def _parse_row(self, row: Dict) -> Optional[RawTrainingRecord]:
        """Parse a CSV row into a RawTrainingRecord"""
        try:
            # Adapt column names based on actual dataset format
            # This may need adjustment when we get the actual data
            return RawTrainingRecord(
                athlete_id=row.get('athlete_id', row.get('user_id', '')),
                activity_date=datetime.fromisoformat(
                    row.get('date', row.get('activity_date', ''))
                ),
                activity_type=row.get('type', row.get('activity_type', 'run')),
                duration_seconds=float(row.get('duration', row.get('moving_time', 0))),
                distance_meters=float(row.get('distance', row.get('distance_m', 0))),
                elevation_gain_meters=float(row.get('elevation', 0)) if row.get('elevation') else None,
                avg_pace_sec_per_km=self._calculate_pace(row),
                avg_hr=int(row.get('avg_hr', 0)) if row.get('avg_hr') else None
            )
        except (ValueError, KeyError) as e:
            logger.debug(f"Failed to parse row: {e}")
            return None
    
    def _calculate_pace(self, row: Dict) -> Optional[float]:
        """Calculate pace in seconds per km from row data"""
        duration = float(row.get('duration', row.get('moving_time', 0)) or 0)
        distance = float(row.get('distance', row.get('distance_m', 0)) or 0)
        
        if duration > 0 and distance > 0:
            return duration / (distance / 1000)
        return None
    
    def filter_recreational_athletes(self) -> Dict[str, List[RawTrainingRecord]]:
        """
        Filter to only include recreational athletes.
        
        Criteria:
        - Not running elite volumes (>150km/week consistently)
        - Have enough data to analyze (50+ activities)
        - Training patterns suggest non-professional
        """
        recreational = {}
        
        for athlete_id, activities in self.athletes.items():
            if len(activities) < self.MIN_TOTAL_ACTIVITIES:
                continue
            
            # Calculate average weekly volume
            weekly_volumes = self._get_weekly_volumes(activities)
            if not weekly_volumes:
                continue
                
            avg_weekly_km = statistics.mean(weekly_volumes)
            
            # Filter out likely elites and very casual
            if self.MIN_WEEKLY_VOLUME_KM <= avg_weekly_km <= self.MAX_WEEKLY_VOLUME_KM:
                recreational[athlete_id] = activities
        
        logger.info(f"Filtered to {len(recreational)} recreational athletes")
        return recreational
    
    def _get_weekly_volumes(self, activities: List[RawTrainingRecord]) -> List[float]:
        """Group activities by week and return weekly volumes in km"""
        if not activities:
            return []
        
        # Sort by date
        sorted_acts = sorted(activities, key=lambda a: a.activity_date)
        
        # Group by week
        weekly = defaultdict(float)
        for act in sorted_acts:
            week_key = act.activity_date.isocalendar()[:2]  # (year, week)
            weekly[week_key] += act.distance_meters / 1000
        
        return list(weekly.values())
    
    def build_athlete_profile(
        self, 
        athlete_id: str, 
        activities: List[RawTrainingRecord]
    ) -> AthleteProfile:
        """
        Build comprehensive profile for a single athlete.
        """
        weekly_volumes = self._get_weekly_volumes(activities)
        weekly_durations = self._get_weekly_durations(activities)
        weekly_run_counts = self._get_weekly_run_counts(activities)
        
        # Calculate pace metrics
        paces = [a.avg_pace_sec_per_km for a in activities if a.avg_pace_sec_per_km]
        
        # Estimate race times from training paces (rough heuristic)
        # Easy pace is typically 60-90 seconds slower than threshold
        easy_pace = statistics.median(paces) if paces else None
        
        # Rough estimates based on easy pace
        estimated_times = self._estimate_race_times_from_easy_pace(easy_pace)
        
        # Calculate consistency
        weeks_with_data = len(weekly_run_counts)
        weeks_with_3plus = sum(1 for c in weekly_run_counts if c >= 3)
        consistency = (weeks_with_3plus / weeks_with_data * 100) if weeks_with_data > 0 else 0
        
        # Calculate trends
        volume_trend = self._calculate_trend(weekly_volumes)
        pace_trend = self._calculate_pace_trend(activities)
        
        # Estimate level
        level = self._estimate_runner_level(weekly_volumes, easy_pace)
        
        return AthleteProfile(
            athlete_id=athlete_id,
            total_activities=len(activities),
            avg_weekly_distance_km=statistics.mean(weekly_volumes) if weekly_volumes else 0,
            avg_weekly_duration_hours=statistics.mean(weekly_durations) if weekly_durations else 0,
            avg_weekly_runs=statistics.mean(weekly_run_counts) if weekly_run_counts else 0,
            avg_easy_pace_per_km=easy_pace,
            best_estimated_5k=estimated_times.get('5k'),
            best_estimated_10k=estimated_times.get('10k'),
            best_estimated_half=estimated_times.get('half'),
            best_estimated_marathon=estimated_times.get('marathon'),
            weeks_with_data=weeks_with_data,
            training_consistency_pct=consistency,
            volume_trend=volume_trend,
            pace_trend=pace_trend,
            runner_level=level,
            estimated_age_grade_pct=None  # Would need age/sex data
        )
    
    def _get_weekly_durations(self, activities: List[RawTrainingRecord]) -> List[float]:
        """Get weekly duration totals in hours"""
        sorted_acts = sorted(activities, key=lambda a: a.activity_date)
        weekly = defaultdict(float)
        for act in sorted_acts:
            week_key = act.activity_date.isocalendar()[:2]
            weekly[week_key] += act.duration_seconds / 3600
        return list(weekly.values())
    
    def _get_weekly_run_counts(self, activities: List[RawTrainingRecord]) -> List[int]:
        """Get count of runs per week"""
        sorted_acts = sorted(activities, key=lambda a: a.activity_date)
        weekly = defaultdict(int)
        for act in sorted_acts:
            week_key = act.activity_date.isocalendar()[:2]
            weekly[week_key] += 1
        return list(weekly.values())
    
    def _estimate_race_times_from_easy_pace(
        self, 
        easy_pace_per_km: Optional[float]
    ) -> Dict[str, float]:
        """
        Estimate race times from easy pace.
        
        Very rough heuristic:
        - Easy pace is typically 60-90 sec/km slower than threshold
        - Threshold is roughly 10K race pace
        """
        if not easy_pace_per_km:
            return {}
        
        # Estimate threshold pace (subtract ~75 sec/km from easy)
        threshold_pace = easy_pace_per_km - 75
        
        # 10K is roughly at threshold
        est_10k = threshold_pace * 10  # 10 km
        
        # Use Riegel formula for other distances
        # T2 = T1 * (D2/D1)^1.06
        return {
            '5k': est_10k * (5/10) ** 1.06,
            '10k': est_10k,
            'half': est_10k * (21.1/10) ** 1.06,
            'marathon': est_10k * (42.2/10) ** 1.06,
        }
    
    def _calculate_trend(self, values: List[float], window: int = 8) -> str:
        """Calculate trend from time series"""
        if len(values) < window * 2:
            return "insufficient_data"
        
        first_half = statistics.mean(values[:window])
        second_half = statistics.mean(values[-window:])
        
        change_pct = (second_half - first_half) / first_half if first_half > 0 else 0
        
        if change_pct > 0.15:
            return "building"
        elif change_pct < -0.15:
            return "declining"
        else:
            return "stable"
    
    def _calculate_pace_trend(self, activities: List[RawTrainingRecord]) -> str:
        """Calculate pace trend over time (lower = faster = improving)"""
        paces = [(a.activity_date, a.avg_pace_sec_per_km) 
                 for a in sorted(activities, key=lambda x: x.activity_date)
                 if a.avg_pace_sec_per_km]
        
        if len(paces) < 20:
            return "insufficient_data"
        
        first_paces = [p[1] for p in paces[:10]]
        last_paces = [p[1] for p in paces[-10:]]
        
        first_avg = statistics.mean(first_paces)
        last_avg = statistics.mean(last_paces)
        
        change_pct = (last_avg - first_avg) / first_avg if first_avg > 0 else 0
        
        # Negative change = faster = improving
        if change_pct < -0.05:
            return "improving"
        elif change_pct > 0.05:
            return "declining"
        else:
            return "stable"
    
    def _estimate_runner_level(
        self, 
        weekly_volumes: List[float],
        easy_pace: Optional[float]
    ) -> str:
        """Estimate runner level from volume and pace"""
        if not weekly_volumes:
            return "unknown"
        
        avg_weekly = statistics.mean(weekly_volumes)
        
        # Volume-based classification (rough)
        if avg_weekly < 20:
            return "beginner"
        elif avg_weekly < 40:
            return "recreational"
        elif avg_weekly < 70:
            return "local_competitive"
        elif avg_weekly < 100:
            return "competitive"
        else:
            return "serious_competitive"
    
    # =========================================================================
    # POPULATION BASELINE GENERATION
    # =========================================================================
    
    def build_population_baselines(self) -> Dict[str, PopulationBaseline]:
        """
        Build baseline statistics for different cohorts of recreational runners.
        
        Cohorts based on:
        - Weekly volume bands (10-20, 20-40, 40-60, 60-80, 80+ km/week)
        """
        recreational = self.filter_recreational_athletes()
        
        # Build profiles for all recreational athletes
        profiles: List[AthleteProfile] = []
        for athlete_id, activities in recreational.items():
            profile = self.build_athlete_profile(athlete_id, activities)
            profiles.append(profile)
        
        # Group into cohorts by weekly volume
        volume_bands = [
            (10, 20, "10-20km_week"),
            (20, 40, "20-40km_week"),
            (40, 60, "40-60km_week"),
            (60, 80, "60-80km_week"),
            (80, 150, "80+km_week"),
        ]
        
        baselines = {}
        
        for min_km, max_km, cohort_name in volume_bands:
            cohort_profiles = [
                p for p in profiles 
                if min_km <= p.avg_weekly_distance_km < max_km
            ]
            
            if len(cohort_profiles) < 10:
                continue
            
            weekly_kms = [p.avg_weekly_distance_km for p in cohort_profiles]
            easy_paces = [p.avg_easy_pace_per_km for p in cohort_profiles if p.avg_easy_pace_per_km]
            
            baselines[cohort_name] = PopulationBaseline(
                cohort_name=cohort_name,
                sample_size=len(cohort_profiles),
                avg_weekly_km=statistics.mean(weekly_kms),
                median_weekly_km=statistics.median(weekly_kms),
                p25_weekly_km=self._percentile(weekly_kms, 25),
                p75_weekly_km=self._percentile(weekly_kms, 75),
                avg_easy_pace_per_km=statistics.mean(easy_paces) if easy_paces else 0,
                median_easy_pace_per_km=statistics.median(easy_paces) if easy_paces else 0,
                typical_weekly_volume_increase_pct=3.0,  # Placeholder - calculate from data
                typical_pace_improvement_per_month=2.0,   # Placeholder
                avg_runs_before_injury_spike=0,           # Would need injury data
                risky_volume_increase_threshold_pct=10.0  # Research suggests >10%/week is risky
            )
        
        self.baselines = baselines
        return baselines
    
    def _percentile(self, values: List[float], pct: int) -> float:
        """Calculate percentile of a list"""
        if not values:
            return 0
        sorted_vals = sorted(values)
        idx = int(len(sorted_vals) * pct / 100)
        return sorted_vals[min(idx, len(sorted_vals) - 1)]
    
    def get_comparison_cohort(self, weekly_km: float) -> Optional[PopulationBaseline]:
        """Get the appropriate baseline cohort for comparison"""
        for cohort_name, baseline in self.baselines.items():
            if (baseline.p25_weekly_km <= weekly_km <= baseline.p75_weekly_km * 1.5):
                return baseline
        return None
    
    def export_baselines_json(self, output_path: str):
        """Export baselines to JSON for frontend use"""
        data = {
            name: {
                'cohort_name': b.cohort_name,
                'sample_size': b.sample_size,
                'avg_weekly_km': round(b.avg_weekly_km, 1),
                'median_weekly_km': round(b.median_weekly_km, 1),
                'p25_weekly_km': round(b.p25_weekly_km, 1),
                'p75_weekly_km': round(b.p75_weekly_km, 1),
                'avg_easy_pace_per_km': round(b.avg_easy_pace_per_km, 1),
                'median_easy_pace_per_km': round(b.median_easy_pace_per_km, 1),
            }
            for name, b in self.baselines.items()
        }
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Exported baselines to {output_path}")


