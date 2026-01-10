"""
Population Comparison Service

"People Like You" analysis - comparing an individual athlete
to population baselines from research data.

This is NOT about comparing to elites.
This is about understanding where you stand among REGULAR runners.

Key Questions We Answer:
- How does my volume compare to runners at my level?
- Is my pace improvement typical or exceptional?
- Am I building volume at a safe rate?
- What does a typical progression look like for someone like me?
"""

from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID
import statistics
import json
import os
import logging

from sqlalchemy.orm import Session

from models import Athlete, Activity
from .age_grading import (
    age_grade_performance,
    classify_performance_level,
    get_population_percentile_by_age_grade
)

logger = logging.getLogger(__name__)


@dataclass
class PeerComparison:
    """Comparison to peer cohort"""
    metric_name: str
    your_value: float
    peer_average: float
    peer_median: float
    peer_p25: float
    peer_p75: float
    percentile: float  # Your percentile within peer group
    interpretation: str
    cohort_size: int
    cohort_name: str


@dataclass 
class ProgressionComparison:
    """Comparison of progression to typical patterns"""
    timeframe_weeks: int
    your_volume_change_pct: float
    typical_volume_change_pct: float
    your_pace_change_sec: float
    typical_pace_change_sec: float
    assessment: str  # "on_track", "faster_than_typical", "slower_than_typical", "caution"
    notes: str


@dataclass
class PopulationInsight:
    """High-level insight from population comparison"""
    category: str  # "volume", "pace", "consistency", "progression"
    insight: str
    data_point: str  # The specific data backing this insight
    relevance: float  # 0-1, how relevant this insight is


# Pre-computed baseline statistics (would be populated from research data)
# These are approximate values based on running research literature
# Will be replaced with actual computed values from Figshare dataset

POPULATION_BASELINES = {
    "beginner": {
        "weekly_km": {"avg": 15, "median": 14, "p25": 10, "p75": 20},
        "weekly_runs": {"avg": 3.0, "median": 3, "p25": 2, "p75": 4},
        "easy_pace_per_km": {"avg": 420, "median": 410, "p25": 380, "p75": 460},  # 7:00/km
        "consistency_pct": {"avg": 55, "median": 50},
        "sample_size": 8500,
    },
    "recreational": {
        "weekly_km": {"avg": 32, "median": 30, "p25": 22, "p75": 42},
        "weekly_runs": {"avg": 4.0, "median": 4, "p25": 3, "p75": 5},
        "easy_pace_per_km": {"avg": 360, "median": 350, "p25": 320, "p75": 390},  # 6:00/km
        "consistency_pct": {"avg": 68, "median": 70},
        "sample_size": 12000,
    },
    "local_competitive": {
        "weekly_km": {"avg": 52, "median": 50, "p25": 40, "p75": 65},
        "weekly_runs": {"avg": 5.2, "median": 5, "p25": 4, "p75": 6},
        "easy_pace_per_km": {"avg": 310, "median": 305, "p25": 280, "p75": 340},  # 5:10/km
        "consistency_pct": {"avg": 78, "median": 80},
        "sample_size": 6500,
    },
    "competitive": {
        "weekly_km": {"avg": 75, "median": 72, "p25": 60, "p75": 90},
        "weekly_runs": {"avg": 6.0, "median": 6, "p25": 5, "p75": 7},
        "easy_pace_per_km": {"avg": 280, "median": 275, "p25": 255, "p75": 300},  # 4:40/km
        "consistency_pct": {"avg": 85, "median": 88},
        "sample_size": 3200,
    },
}

# Typical progression rates from research
PROGRESSION_BENCHMARKS = {
    "beginner": {
        "monthly_volume_increase_pct": 8,  # Can progress faster early
        "monthly_pace_improvement_sec": 6,  # per km
        "safe_weekly_increase_pct": 10,
    },
    "recreational": {
        "monthly_volume_increase_pct": 5,
        "monthly_pace_improvement_sec": 3,
        "safe_weekly_increase_pct": 8,
    },
    "local_competitive": {
        "monthly_volume_increase_pct": 3,
        "monthly_pace_improvement_sec": 2,
        "safe_weekly_increase_pct": 6,
    },
    "competitive": {
        "monthly_volume_increase_pct": 2,
        "monthly_pace_improvement_sec": 1,
        "safe_weekly_increase_pct": 5,
    },
}


class PopulationComparisonService:
    """
    Service for comparing individual athletes to population baselines.
    
    Uses research data to provide context for:
    - Where you stand among peers
    - Whether your progression is typical
    - Risk indicators based on population patterns
    
    Now powered by 26.6M training records from 36,412 athletes!
    """
    
    # Path to research baselines JSON
    BASELINES_PATH = os.path.join(
        os.path.dirname(__file__), 
        "baselines", 
        "population_baselines.json"
    )
    
    def __init__(self, db: Session):
        self.db = db
        self.baselines = POPULATION_BASELINES
        self.progression_benchmarks = PROGRESSION_BENCHMARKS
        self.research_data = None
        
        # Auto-load research baselines if available
        self._load_research_baselines()
    
    def _load_research_baselines(self):
        """Load baselines from processed research data JSON"""
        if os.path.exists(self.BASELINES_PATH):
            try:
                with open(self.BASELINES_PATH, 'r') as f:
                    self.research_data = json.load(f)
                logger.info(
                    f"Loaded research baselines: {self.research_data['metadata']['total_records']:,} records "
                    f"from {self.research_data['metadata']['unique_athletes']:,} athletes"
                )
            except Exception as e:
                logger.warning(f"Failed to load research baselines: {e}")
    
    def load_research_baselines(self, json_path: str):
        """Load baselines from a custom path (for testing)"""
        if os.path.exists(json_path):
            with open(json_path, 'r') as f:
                self.research_data = json.load(f)
            logger.info(f"Loaded research baselines from {json_path}")
    
    def get_athlete_cohort(self, athlete_id: UUID) -> str:
        """
        Determine which cohort an athlete belongs to based on their training.
        """
        # Get recent activities
        cutoff = datetime.now() - timedelta(days=60)
        activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= cutoff,
            Activity.distance_m > 0
        ).all()
        
        if not activities:
            return "beginner"
        
        # Calculate average weekly volume
        total_distance_km = sum(a.distance_m or 0 for a in activities) / 1000
        weeks = max(1, (datetime.now() - cutoff).days / 7)
        avg_weekly_km = total_distance_km / weeks
        
        # Classify
        if avg_weekly_km < 20:
            return "beginner"
        elif avg_weekly_km < 45:
            return "recreational"
        elif avg_weekly_km < 65:
            return "local_competitive"
        else:
            return "competitive"
    
    def compare_to_peers(self, athlete_id: UUID) -> List[PeerComparison]:
        """
        Compare athlete's metrics to their peer cohort.
        Returns list of comparisons for different metrics.
        """
        cohort = self.get_athlete_cohort(athlete_id)
        baseline = self.baselines.get(cohort)
        
        if not baseline:
            return []
        
        comparisons = []
        
        # Get athlete's current metrics
        athlete_metrics = self._calculate_athlete_metrics(athlete_id)
        
        # Volume comparison
        if 'weekly_km' in athlete_metrics and 'weekly_km' in baseline:
            vol_comp = self._create_comparison(
                metric_name="Weekly Volume",
                your_value=athlete_metrics['weekly_km'],
                baseline_stats=baseline['weekly_km'],
                cohort_name=cohort,
                sample_size=baseline.get('sample_size', 0),
                higher_is_better=None  # Context-dependent
            )
            comparisons.append(vol_comp)
        
        # Run frequency comparison
        if 'weekly_runs' in athlete_metrics and 'weekly_runs' in baseline:
            runs_comp = self._create_comparison(
                metric_name="Weekly Runs",
                your_value=athlete_metrics['weekly_runs'],
                baseline_stats=baseline['weekly_runs'],
                cohort_name=cohort,
                sample_size=baseline.get('sample_size', 0),
                higher_is_better=None
            )
            comparisons.append(runs_comp)
        
        # Consistency comparison
        if 'consistency_pct' in athlete_metrics and 'consistency_pct' in baseline:
            cons_comp = self._create_comparison(
                metric_name="Training Consistency",
                your_value=athlete_metrics['consistency_pct'],
                baseline_stats=baseline['consistency_pct'],
                cohort_name=cohort,
                sample_size=baseline.get('sample_size', 0),
                higher_is_better=True
            )
            comparisons.append(cons_comp)
        
        return comparisons
    
    def _calculate_athlete_metrics(self, athlete_id: UUID) -> Dict[str, float]:
        """Calculate current metrics for an athlete"""
        cutoff = datetime.now() - timedelta(days=60)
        activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= cutoff,
            Activity.distance_m > 0
        ).order_by(Activity.start_time).all()
        
        if not activities:
            return {}
        
        # Group by week
        weekly_distances = {}
        weekly_counts = {}
        
        for act in activities:
            week_key = act.start_time.isocalendar()[:2]
            weekly_distances[week_key] = weekly_distances.get(week_key, 0) + (act.distance_m / 1000)
            weekly_counts[week_key] = weekly_counts.get(week_key, 0) + 1
        
        weeks_with_data = len(weekly_distances)
        total_weeks = max(1, (datetime.now() - cutoff).days / 7)
        
        # Calculate metrics
        metrics = {
            'weekly_km': statistics.mean(weekly_distances.values()) if weekly_distances else 0,
            'weekly_runs': statistics.mean(weekly_counts.values()) if weekly_counts else 0,
            'consistency_pct': (weeks_with_data / total_weeks) * 100,
        }
        
        return metrics
    
    def _create_comparison(
        self,
        metric_name: str,
        your_value: float,
        baseline_stats: Dict[str, float],
        cohort_name: str,
        sample_size: int,
        higher_is_better: Optional[bool] = None
    ) -> PeerComparison:
        """Create a peer comparison object"""
        avg = baseline_stats.get('avg', 0)
        median = baseline_stats.get('median', avg)
        p25 = baseline_stats.get('p25', avg * 0.8)
        p75 = baseline_stats.get('p75', avg * 1.2)
        
        # Estimate percentile
        if your_value <= p25:
            percentile = 25 * (your_value / p25) if p25 > 0 else 0
        elif your_value <= median:
            percentile = 25 + 25 * ((your_value - p25) / (median - p25)) if median > p25 else 50
        elif your_value <= p75:
            percentile = 50 + 25 * ((your_value - median) / (p75 - median)) if p75 > median else 75
        else:
            # Extrapolate above p75
            excess_ratio = (your_value - p75) / (p75 - median) if p75 > median else 1
            percentile = min(99, 75 + 25 * excess_ratio * 0.5)
        
        # Generate interpretation
        interpretation = self._interpret_comparison(
            metric_name, your_value, avg, median, p25, p75, percentile, higher_is_better
        )
        
        return PeerComparison(
            metric_name=metric_name,
            your_value=round(your_value, 1),
            peer_average=round(avg, 1),
            peer_median=round(median, 1),
            peer_p25=round(p25, 1),
            peer_p75=round(p75, 1),
            percentile=round(percentile, 0),
            interpretation=interpretation,
            cohort_size=sample_size,
            cohort_name=cohort_name
        )
    
    def _interpret_comparison(
        self,
        metric_name: str,
        your_value: float,
        avg: float,
        median: float,
        p25: float,
        p75: float,
        percentile: float,
        higher_is_better: Optional[bool]
    ) -> str:
        """Generate human-readable interpretation"""
        cohort_desc = f"runners at your level"
        
        if percentile < 25:
            position = f"below most {cohort_desc}"
        elif percentile < 45:
            position = f"slightly below average for {cohort_desc}"
        elif percentile <= 55:
            position = f"right around average for {cohort_desc}"
        elif percentile <= 75:
            position = f"above average for {cohort_desc}"
        else:
            position = f"well above most {cohort_desc}"
        
        return f"Your {metric_name.lower()} is {position}"
    
    def assess_progression(
        self, 
        athlete_id: UUID, 
        weeks: int = 8
    ) -> ProgressionComparison:
        """
        Assess whether athlete's progression is typical, fast, or concerning.
        """
        cohort = self.get_athlete_cohort(athlete_id)
        benchmarks = self.progression_benchmarks.get(cohort, self.progression_benchmarks['recreational'])
        
        # Get volume progression
        cutoff = datetime.now() - timedelta(weeks=weeks * 7)
        midpoint = datetime.now() - timedelta(weeks=weeks // 2 * 7)
        
        first_half = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= cutoff,
            Activity.start_time < midpoint
        ).all()
        
        second_half = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= midpoint
        ).all()
        
        # Calculate changes
        first_vol = sum(a.distance_m or 0 for a in first_half) / 1000
        second_vol = sum(a.distance_m or 0 for a in second_half) / 1000
        
        vol_change_pct = ((second_vol - first_vol) / first_vol * 100) if first_vol > 0 else 0
        
        # Expected change for the period
        months = weeks / 4
        expected_vol_change = benchmarks['monthly_volume_increase_pct'] * months
        
        # Assess
        if vol_change_pct > expected_vol_change * 2:
            assessment = "caution"
            notes = f"Volume increasing faster than typical ({vol_change_pct:.0f}% vs {expected_vol_change:.0f}% typical). Monitor for overtraining signs."
        elif vol_change_pct > expected_vol_change * 1.3:
            assessment = "faster_than_typical"
            notes = f"Building faster than most {cohort} runners. Good if recovering well."
        elif vol_change_pct < 0:
            assessment = "declining"
            notes = f"Volume decreasing. Could be intentional (taper, recovery) or concerning."
        else:
            assessment = "on_track"
            notes = f"Progression rate is typical for {cohort} runners."
        
        return ProgressionComparison(
            timeframe_weeks=weeks,
            your_volume_change_pct=round(vol_change_pct, 1),
            typical_volume_change_pct=round(expected_vol_change, 1),
            your_pace_change_sec=0,  # Would need pace data
            typical_pace_change_sec=benchmarks['monthly_pace_improvement_sec'] * months,
            assessment=assessment,
            notes=notes
        )
    
    def get_insights(self, athlete_id: UUID) -> List[PopulationInsight]:
        """
        Generate population-based insights for an athlete.
        """
        insights = []
        
        comparisons = self.compare_to_peers(athlete_id)
        progression = self.assess_progression(athlete_id)
        
        for comp in comparisons:
            if comp.percentile > 75:
                insights.append(PopulationInsight(
                    category=comp.metric_name.lower().replace(' ', '_'),
                    insight=f"Your {comp.metric_name.lower()} is higher than 75% of {comp.cohort_name} runners",
                    data_point=f"{comp.your_value} vs {comp.peer_median} median",
                    relevance=0.7
                ))
            elif comp.percentile < 25:
                insights.append(PopulationInsight(
                    category=comp.metric_name.lower().replace(' ', '_'),
                    insight=f"Your {comp.metric_name.lower()} is lower than most {comp.cohort_name} runners",
                    data_point=f"{comp.your_value} vs {comp.peer_median} median",
                    relevance=0.6
                ))
        
        if progression.assessment == "caution":
            insights.append(PopulationInsight(
                category="progression",
                insight="Volume building faster than typical - research suggests monitoring closely",
                data_point=f"{progression.your_volume_change_pct}% vs {progression.typical_volume_change_pct}% typical",
                relevance=0.9
            ))
        
        # Sort by relevance
        insights.sort(key=lambda x: x.relevance, reverse=True)
        
        return insights
    
    # =========================================================================
    # RESEARCH DATA COMPARISONS (powered by 26.6M records)
    # =========================================================================
    
    def _get_athlete_cohort_key(self, athlete_id: UUID) -> Optional[str]:
        """
        Get the cohort key (e.g., 'M_35_54') for an athlete based on age and gender.
        """
        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            return None
        
        # Determine gender
        gender = athlete.sex.upper() if athlete.sex else None
        if gender not in ['M', 'F']:
            return None
        
        # Determine age group
        if not athlete.birthdate:
            return None
        
        from datetime import date
        today = date.today()
        age = today.year - athlete.birthdate.year
        if today.month < athlete.birthdate.month or (today.month == athlete.birthdate.month and today.day < athlete.birthdate.day):
            age -= 1
        
        if age < 18:
            return None
        elif age <= 34:
            age_group = "18_34"
        elif age <= 54:
            age_group = "35_54"
        else:
            age_group = "55+"
        
        return f"{gender}_{age_group}"
    
    def compare_weekly_volume_to_research(
        self, 
        athlete_id: UUID,
        current_weekly_km: float
    ) -> Optional[Dict]:
        """
        Compare athlete's weekly volume to research population data.
        
        Returns detailed comparison with percentile and context.
        """
        if not self.research_data:
            return None
        
        cohort_key = self._get_athlete_cohort_key(athlete_id)
        if not cohort_key or cohort_key not in self.research_data.get('weekly_volume', {}):
            return None
        
        baseline = self.research_data['weekly_volume'][cohort_key]
        stats = baseline['weekly_km']
        
        # Calculate percentile
        percentile = self._calculate_percentile(
            current_weekly_km,
            stats['p10'], stats['p25'], stats['median'], stats['p75'], stats['p90']
        )
        
        return {
            'your_weekly_km': round(current_weekly_km, 1),
            'cohort': {
                'gender': baseline['gender'],
                'age_group': baseline['age_group'],
                'sample_size': baseline['sample_size'],
                'athletes': baseline['athletes']
            },
            'comparison': {
                'mean': stats['mean'],
                'median': stats['median'],
                'p10': stats['p10'],
                'p25': stats['p25'],
                'p75': stats['p75'],
                'p90': stats['p90']
            },
            'percentile': round(percentile, 0),
            'interpretation': self._interpret_volume_percentile(percentile, baseline['age_group'], baseline['gender'])
        }
    
    def compare_race_time_to_research(
        self,
        athlete_id: UUID,
        distance: str,  # '5K', '10K', 'half_marathon', 'marathon'
        finish_time_minutes: float
    ) -> Optional[Dict]:
        """
        Compare athlete's race time to research population data.
        
        Returns detailed comparison showing where they stand.
        """
        if not self.research_data:
            return None
        
        cohort_key = self._get_athlete_cohort_key(athlete_id)
        if not cohort_key:
            return None
        
        # Build the full key for race times
        race_key = f"{distance}_{cohort_key}"
        race_data = self.research_data.get('race_times', {}).get(race_key)
        
        if not race_data:
            return None
        
        stats = race_data['finish_time_minutes']
        
        # For race times, LOWER is better, so invert the percentile logic
        percentile = self._calculate_percentile_inverted(
            finish_time_minutes,
            stats['p10'], stats['p25'], stats['p50'], stats['p75'], stats['p90']
        )
        
        # Format times for display
        def format_time(mins):
            h = int(mins // 60)
            m = int(mins % 60)
            return f"{h}:{m:02d}" if h > 0 else f"{m} min"
        
        return {
            'your_time': format_time(finish_time_minutes),
            'your_time_minutes': round(finish_time_minutes, 1),
            'distance': distance,
            'cohort': {
                'gender': race_data['gender'],
                'age_group': race_data['age_group'],
                'sample_size': race_data['sample_size']
            },
            'comparison': {
                'fastest_10pct': format_time(stats['p10']),
                'p25': format_time(stats['p25']),
                'median': format_time(stats['p50']),
                'p75': format_time(stats['p75']),
                'slowest_10pct': format_time(stats['p90'])
            },
            'percentile': round(percentile, 0),
            'interpretation': self._interpret_race_percentile(percentile, distance, race_data['gender'], race_data['age_group'])
        }
    
    def _calculate_percentile(
        self, 
        value: float,
        p10: float, p25: float, p50: float, p75: float, p90: float
    ) -> float:
        """Calculate percentile using linear interpolation between known quantiles."""
        if value <= p10:
            return 10 * (value / p10) if p10 > 0 else 0
        elif value <= p25:
            return 10 + 15 * ((value - p10) / (p25 - p10)) if p25 > p10 else 25
        elif value <= p50:
            return 25 + 25 * ((value - p25) / (p50 - p25)) if p50 > p25 else 50
        elif value <= p75:
            return 50 + 25 * ((value - p50) / (p75 - p50)) if p75 > p50 else 75
        elif value <= p90:
            return 75 + 15 * ((value - p75) / (p90 - p75)) if p90 > p75 else 90
        else:
            # Extrapolate above 90th
            excess = (value - p90) / (p90 - p75) if p90 > p75 else 1
            return min(99, 90 + 10 * excess * 0.3)
    
    def _calculate_percentile_inverted(
        self,
        value: float,
        p10: float, p25: float, p50: float, p75: float, p90: float
    ) -> float:
        """
        Calculate percentile where LOWER is better (e.g., race times).
        A time faster than p10 means you're in the top 10%.
        """
        if value <= p10:
            # Faster than 90% of people
            return min(99, 90 + 10 * (1 - value / p10) if p10 > 0 else 99)
        elif value <= p25:
            return 75 + 15 * ((p25 - value) / (p25 - p10)) if p25 > p10 else 75
        elif value <= p50:
            return 50 + 25 * ((p50 - value) / (p50 - p25)) if p50 > p25 else 50
        elif value <= p75:
            return 25 + 25 * ((p75 - value) / (p75 - p50)) if p75 > p50 else 25
        elif value <= p90:
            return 10 + 15 * ((p90 - value) / (p90 - p75)) if p90 > p75 else 10
        else:
            # Slower than 90% of people
            return max(1, 10 * (p90 / value) if value > 0 else 1)
    
    def _interpret_volume_percentile(self, percentile: float, age_group: str, gender: str) -> str:
        """Generate human-readable interpretation for weekly volume."""
        gender_word = "male" if gender == "M" else "female"
        cohort_desc = f"{age_group.replace('_', '-')} {gender_word} runners"
        
        if percentile >= 90:
            return f"Your weekly volume is higher than 90% of {cohort_desc}. You're putting in serious work."
        elif percentile >= 75:
            return f"Above average volume - higher than ~{int(percentile)}% of {cohort_desc}."
        elif percentile >= 50:
            return f"Right around typical for {cohort_desc}."
        elif percentile >= 25:
            return f"Below average for {cohort_desc}, but that's not necessarily bad. Quality over quantity."
        else:
            return f"Lower volume than most {cohort_desc}. Consider if this aligns with your goals."
    
    def _interpret_race_percentile(self, percentile: float, distance: str, gender: str, age_group: str) -> str:
        """Generate human-readable interpretation for race times."""
        gender_word = "male" if gender == "M" else "female"
        cohort_desc = f"{age_group.replace('_', '-')} {gender_word} runners"
        
        if percentile >= 90:
            return f"Elite territory. Faster than ~90% of {cohort_desc} at this distance."
        elif percentile >= 75:
            return f"Strong performance - faster than ~{int(percentile)}% of {cohort_desc}."
        elif percentile >= 50:
            return f"Solid time - around the middle of the pack for {cohort_desc}."
        elif percentile >= 25:
            return f"Plenty of room to improve. You're still ahead of ~{int(percentile)}% of {cohort_desc}."
        else:
            return f"Early in your journey. Every race is a data point. Keep building."

