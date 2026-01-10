"""
Activity Comparison Service

Enables powerful comparisons of activities by:
- Workout type (compare all tempo runs)
- Time period (this month vs last month)
- Conditions (hot vs cool, flat vs hilly)
- Combinations (tempo runs in heat vs cool)

This is a key differentiator - neither Garmin nor Strava offer this.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy import func, and_, or_, case
from sqlalchemy.orm import Session

from models import Activity, ActivitySplit, Athlete


@dataclass
class SplitData:
    """Data for a single split (mile/km)"""
    split_number: int
    distance_m: float
    elapsed_time_s: int
    pace_per_km: Optional[float]
    avg_hr: Optional[int]
    cumulative_distance_m: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "split_number": self.split_number,
            "distance_m": self.distance_m,
            "elapsed_time_s": self.elapsed_time_s,
            "pace_per_km": self.pace_per_km,
            "avg_hr": self.avg_hr,
            "cumulative_distance_m": self.cumulative_distance_m,
        }


@dataclass
class ActivitySummary:
    """Summary of an activity for comparison"""
    id: str
    date: datetime
    name: str
    workout_type: Optional[str]
    distance_m: int
    duration_s: int
    avg_hr: Optional[int]
    pace_per_km: Optional[float]
    efficiency: Optional[float]  # Speed / HR
    intensity_score: Optional[float]
    elevation_gain: Optional[float]
    temperature_f: Optional[float]
    splits: Optional[List[SplitData]] = None  # For charting
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "date": self.date.isoformat(),
            "name": self.name,
            "workout_type": self.workout_type,
            "distance_m": self.distance_m,
            "distance_km": self.distance_m / 1000 if self.distance_m else 0,
            "duration_s": self.duration_s,
            "avg_hr": self.avg_hr,
            "pace_per_km": self.pace_per_km,
            "pace_formatted": self._format_pace(self.pace_per_km) if self.pace_per_km else None,
            "splits": [s.to_dict() for s in self.splits] if self.splits else [],
            "efficiency": self.efficiency,
            "intensity_score": self.intensity_score,
            "elevation_gain": self.elevation_gain,
            "temperature_f": self.temperature_f,
        }
    
    def _format_pace(self, seconds_per_km: float) -> str:
        minutes = int(seconds_per_km // 60)
        secs = int(seconds_per_km % 60)
        return f"{minutes}:{secs:02d}/km"


@dataclass
class ComparisonResult:
    """Result of comparing a set of activities"""
    workout_type: str
    total_activities: int
    date_range_start: Optional[datetime]
    date_range_end: Optional[datetime]
    
    # Trends
    avg_pace_per_km: Optional[float]
    avg_efficiency: Optional[float]
    avg_hr: Optional[float]
    total_distance_km: float
    
    # Progression
    efficiency_trend: Optional[str]  # 'improving', 'declining', 'stable'
    efficiency_change_pct: Optional[float]
    pace_trend: Optional[str]
    pace_change_pct: Optional[float]
    
    # Best/Worst
    best_activity: Optional[ActivitySummary]
    worst_activity: Optional[ActivitySummary]
    most_recent: Optional[ActivitySummary]
    
    # All activities
    activities: List[ActivitySummary]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "workout_type": self.workout_type,
            "total_activities": self.total_activities,
            "date_range_start": self.date_range_start.isoformat() if self.date_range_start else None,
            "date_range_end": self.date_range_end.isoformat() if self.date_range_end else None,
            "avg_pace_per_km": self.avg_pace_per_km,
            "avg_pace_formatted": self._format_pace(self.avg_pace_per_km) if self.avg_pace_per_km else None,
            "avg_efficiency": self.avg_efficiency,
            "avg_hr": self.avg_hr,
            "total_distance_km": self.total_distance_km,
            "efficiency_trend": self.efficiency_trend,
            "efficiency_change_pct": self.efficiency_change_pct,
            "pace_trend": self.pace_trend,
            "pace_change_pct": self.pace_change_pct,
            "best_activity": self.best_activity.to_dict() if self.best_activity else None,
            "worst_activity": self.worst_activity.to_dict() if self.worst_activity else None,
            "most_recent": self.most_recent.to_dict() if self.most_recent else None,
            "activities": [a.to_dict() for a in self.activities],
        }
    
    def _format_pace(self, seconds_per_km: float) -> str:
        minutes = int(seconds_per_km // 60)
        secs = int(seconds_per_km % 60)
        return f"{minutes}:{secs:02d}/km"


@dataclass
class IndividualComparisonResult:
    """Result of comparing 2-10 specific activities"""
    activities: List[ActivitySummary]
    comparison_table: Dict[str, List[Any]]  # metric -> [value_per_activity]
    best_by_metric: Dict[str, str]  # metric -> activity_id that was best
    insights: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "activities": [a.to_dict() for a in self.activities],
            "comparison_table": self.comparison_table,
            "best_by_metric": self.best_by_metric,
            "insights": self.insights,
            "count": len(self.activities),
        }


class ActivityComparisonService:
    """Compare activities by various criteria"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def compare_individual(
        self,
        athlete_id: UUID,
        activity_ids: List[UUID],
    ) -> IndividualComparisonResult:
        """
        Compare 2-10 specific activities side-by-side.
        This is the marquee feature.
        """
        if len(activity_ids) < 2:
            raise ValueError("Need at least 2 activities to compare")
        if len(activity_ids) > 10:
            raise ValueError("Maximum 10 activities for individual comparison")
        
        # Fetch all activities
        activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.id.in_(activity_ids),
        ).all()
        
        if len(activities) != len(activity_ids):
            raise ValueError("One or more activities not found")
        
        # Sort by date (newest first)
        activities.sort(key=lambda a: a.start_time, reverse=True)
        
        # Convert to summaries with splits for charting
        summaries = []
        for a in activities:
            pace = a.duration_s / (a.distance_m / 1000) if a.distance_m and a.duration_s else None
            speed = (a.distance_m / 1000) / (a.duration_s / 3600) if a.distance_m and a.duration_s else None
            efficiency = speed / a.avg_hr if speed and a.avg_hr else None
            
            # Fetch splits for overlay charts
            splits_data = []
            db_splits = self.db.query(ActivitySplit).filter(
                ActivitySplit.activity_id == a.id
            ).order_by(ActivitySplit.split_number).all()
            
            cumulative_distance = 0.0
            for split in db_splits:
                split_distance = float(split.distance) if split.distance else 1609.34  # Default 1 mile
                cumulative_distance += split_distance
                elapsed = split.moving_time or split.elapsed_time or 0
                split_pace = elapsed / (split_distance / 1000) if split_distance > 0 and elapsed > 0 else None
                
                splits_data.append(SplitData(
                    split_number=split.split_number,
                    distance_m=split_distance,
                    elapsed_time_s=elapsed,
                    pace_per_km=split_pace,
                    avg_hr=split.average_heartrate,
                    cumulative_distance_m=cumulative_distance,
                ))
            
            summaries.append(ActivitySummary(
                id=str(a.id),
                date=a.start_time,
                name=a.name or f"Run on {a.start_time.strftime('%b %d')}",
                workout_type=a.workout_type,
                distance_m=a.distance_m or 0,
                duration_s=a.duration_s or 0,
                avg_hr=a.avg_hr,
                pace_per_km=pace,
                efficiency=efficiency,
                intensity_score=a.intensity_score,
                elevation_gain=float(a.total_elevation_gain) if a.total_elevation_gain else None,
                temperature_f=float(a.temperature_f) if a.temperature_f else None,
                splits=splits_data if splits_data else None,
            ))
        
        # Build comparison table
        comparison_table = {
            "date": [s.date.strftime("%b %d, %Y") for s in summaries],
            "name": [s.name for s in summaries],
            "workout_type": [s.workout_type for s in summaries],
            "distance_m": [s.distance_m for s in summaries],
            "duration_s": [s.duration_s for s in summaries],
            "pace_per_km": [s.pace_per_km for s in summaries],
            "avg_hr": [s.avg_hr for s in summaries],
            "efficiency": [s.efficiency for s in summaries],
            "elevation_gain": [s.elevation_gain for s in summaries],
            "temperature_f": [s.temperature_f for s in summaries],
            "intensity_score": [s.intensity_score for s in summaries],
        }
        
        # Find best for each metric (lower is better for pace, higher is better for others)
        best_by_metric = {}
        
        # Pace: lower is better
        paces = [(s.id, s.pace_per_km) for s in summaries if s.pace_per_km]
        if paces:
            best_by_metric["pace_per_km"] = min(paces, key=lambda x: x[1])[0]
        
        # Efficiency: higher is better
        effs = [(s.id, s.efficiency) for s in summaries if s.efficiency]
        if effs:
            best_by_metric["efficiency"] = max(effs, key=lambda x: x[1])[0]
        
        # Distance: higher (for same type comparison)
        dists = [(s.id, s.distance_m) for s in summaries if s.distance_m]
        if dists:
            best_by_metric["distance_m"] = max(dists, key=lambda x: x[1])[0]
        
        # Lowest HR (for similar efforts): lower is better
        hrs = [(s.id, s.avg_hr) for s in summaries if s.avg_hr]
        if hrs:
            best_by_metric["avg_hr"] = min(hrs, key=lambda x: x[1])[0]
        
        # Generate insights
        insights = self._generate_individual_insights(summaries, best_by_metric)
        
        return IndividualComparisonResult(
            activities=summaries,
            comparison_table=comparison_table,
            best_by_metric=best_by_metric,
            insights=insights,
        )
    
    def _generate_individual_insights(
        self,
        summaries: List[ActivitySummary],
        best_by_metric: Dict[str, str],
    ) -> List[str]:
        """Generate plain-language insights from the comparison"""
        insights = []
        
        # Find the most efficient run
        if "efficiency" in best_by_metric:
            best_id = best_by_metric["efficiency"]
            best = next(s for s in summaries if s.id == best_id)
            insights.append(
                f"🏆 Most efficient: {best.name} ({best.date.strftime('%b %d')}) "
                f"with efficiency of {best.efficiency:.3f}"
            )
        
        # Find the fastest
        if "pace_per_km" in best_by_metric:
            best_id = best_by_metric["pace_per_km"]
            best = next(s for s in summaries if s.id == best_id)
            pace_min = int(best.pace_per_km // 60)
            pace_sec = int(best.pace_per_km % 60)
            insights.append(
                f"⚡ Fastest pace: {best.name} at {pace_min}:{pace_sec:02d}/km"
            )
        
        # Temperature insight if we have it
        temps = [s for s in summaries if s.temperature_f]
        if len(temps) >= 2:
            coldest = min(temps, key=lambda x: x.temperature_f)
            hottest = max(temps, key=lambda x: x.temperature_f)
            temp_diff = hottest.temperature_f - coldest.temperature_f
            if temp_diff >= 15:  # Meaningful difference
                # Check if efficiency differs
                if coldest.efficiency and hottest.efficiency:
                    eff_diff_pct = ((coldest.efficiency - hottest.efficiency) / hottest.efficiency) * 100
                    if eff_diff_pct > 3:
                        insights.append(
                            f"🌡️ Temperature effect: {coldest.temperature_f:.0f}°F was "
                            f"{eff_diff_pct:.1f}% more efficient than {hottest.temperature_f:.0f}°F"
                        )
        
        # Trend if all same workout type
        types = set(s.workout_type for s in summaries if s.workout_type)
        if len(types) == 1:
            wtype = types.pop()
            # Check if efficiency improving over time (summaries are newest-first)
            effs_with_date = [(s.date, s.efficiency) for s in summaries if s.efficiency]
            if len(effs_with_date) >= 3:
                effs_with_date.sort(key=lambda x: x[0])  # oldest first
                first_half = effs_with_date[:len(effs_with_date)//2]
                second_half = effs_with_date[len(effs_with_date)//2:]
                if first_half and second_half:
                    first_avg = sum(e[1] for e in first_half) / len(first_half)
                    second_avg = sum(e[1] for e in second_half) / len(second_half)
                    change_pct = ((second_avg - first_avg) / first_avg) * 100
                    if change_pct > 3:
                        insights.append(f"📈 Your {wtype} efficiency improved {change_pct:.1f}% over this period")
                    elif change_pct < -3:
                        insights.append(f"📉 Your {wtype} efficiency declined {abs(change_pct):.1f}% - check recovery")
        
        if not insights:
            insights.append("Select runs of the same type for more meaningful comparisons")
        
        return insights
    
    def get_workout_type_summary(self, athlete_id: UUID) -> Dict[str, int]:
        """Get count of activities by workout type"""
        results = self.db.query(
            Activity.workout_type,
            func.count(Activity.id)
        ).filter(
            Activity.athlete_id == athlete_id,
            Activity.workout_type.isnot(None)
        ).group_by(Activity.workout_type).all()
        
        return {wt: count for wt, count in results if wt}
    
    def compare_by_workout_type(
        self,
        athlete_id: UUID,
        workout_type: str,
        days: int = 180,
        min_distance_m: int = 1000,
        max_activities: int = 50,
    ) -> ComparisonResult:
        """Compare all activities of a specific workout type"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Query activities
        activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.workout_type == workout_type,
            Activity.start_time >= cutoff,
            Activity.distance_m >= min_distance_m,
        ).order_by(Activity.start_time.desc()).limit(max_activities).all()
        
        return self._build_comparison_result(workout_type, activities)
    
    def compare_by_conditions(
        self,
        athlete_id: UUID,
        workout_type: Optional[str] = None,
        temp_min: Optional[float] = None,
        temp_max: Optional[float] = None,
        days: int = 365,
    ) -> ComparisonResult:
        """Compare activities filtered by conditions (temperature, etc.)"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        query = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= cutoff,
            Activity.distance_m >= 1000,
        )
        
        if workout_type:
            query = query.filter(Activity.workout_type == workout_type)
        
        if temp_min is not None:
            query = query.filter(Activity.temperature_f >= temp_min)
        
        if temp_max is not None:
            query = query.filter(Activity.temperature_f <= temp_max)
        
        activities = query.order_by(Activity.start_time.desc()).limit(50).all()
        
        label = workout_type or "all"
        if temp_min and temp_max:
            label = f"{label} ({temp_min}°F-{temp_max}°F)"
        elif temp_min:
            label = f"{label} (>{temp_min}°F)"
        elif temp_max:
            label = f"{label} (<{temp_max}°F)"
        
        return self._build_comparison_result(label, activities)
    
    def compare_time_periods(
        self,
        athlete_id: UUID,
        workout_type: Optional[str] = None,
        period1_start: datetime = None,
        period1_end: datetime = None,
        period2_start: datetime = None,
        period2_end: datetime = None,
    ) -> Dict[str, ComparisonResult]:
        """Compare two time periods"""
        
        def get_period_activities(start: datetime, end: datetime) -> List[Activity]:
            query = self.db.query(Activity).filter(
                Activity.athlete_id == athlete_id,
                Activity.start_time >= start,
                Activity.start_time <= end,
                Activity.distance_m >= 1000,
            )
            if workout_type:
                query = query.filter(Activity.workout_type == workout_type)
            return query.order_by(Activity.start_time.desc()).all()
        
        period1_activities = get_period_activities(period1_start, period1_end)
        period2_activities = get_period_activities(period2_start, period2_end)
        
        return {
            "period1": self._build_comparison_result(f"Period 1", period1_activities),
            "period2": self._build_comparison_result(f"Period 2", period2_activities),
        }
    
    def _build_comparison_result(
        self, 
        workout_type: str, 
        activities: List[Activity]
    ) -> ComparisonResult:
        """Build comparison result from list of activities"""
        if not activities:
            return ComparisonResult(
                workout_type=workout_type,
                total_activities=0,
                date_range_start=None,
                date_range_end=None,
                avg_pace_per_km=None,
                avg_efficiency=None,
                avg_hr=None,
                total_distance_km=0,
                efficiency_trend=None,
                efficiency_change_pct=None,
                pace_trend=None,
                pace_change_pct=None,
                best_activity=None,
                worst_activity=None,
                most_recent=None,
                activities=[],
            )
        
        # Convert to summaries
        summaries = []
        for a in activities:
            pace = a.duration_s / (a.distance_m / 1000) if a.distance_m and a.duration_s else None
            speed = (a.distance_m / 1000) / (a.duration_s / 3600) if a.distance_m and a.duration_s else None
            efficiency = speed / a.avg_hr if speed and a.avg_hr else None
            
            summaries.append(ActivitySummary(
                id=str(a.id),
                date=a.start_time,
                name=a.external_activity_id or f"Activity {a.id}",  # TODO: store name
                workout_type=a.workout_type,
                distance_m=a.distance_m or 0,
                duration_s=a.duration_s or 0,
                avg_hr=a.avg_hr,
                pace_per_km=pace,
                efficiency=efficiency,
                intensity_score=a.intensity_score,
                elevation_gain=float(a.total_elevation_gain) if a.total_elevation_gain else None,
                temperature_f=a.temperature_f,
            ))
        
        # Calculate aggregates
        paces = [s.pace_per_km for s in summaries if s.pace_per_km]
        efficiencies = [s.efficiency for s in summaries if s.efficiency]
        hrs = [s.avg_hr for s in summaries if s.avg_hr]
        
        avg_pace = sum(paces) / len(paces) if paces else None
        avg_efficiency = sum(efficiencies) / len(efficiencies) if efficiencies else None
        avg_hr = sum(hrs) / len(hrs) if hrs else None
        total_distance = sum(s.distance_m for s in summaries) / 1000
        
        # Find best/worst (by efficiency)
        sorted_by_eff = sorted([s for s in summaries if s.efficiency], key=lambda x: x.efficiency, reverse=True)
        best = sorted_by_eff[0] if sorted_by_eff else None
        worst = sorted_by_eff[-1] if sorted_by_eff else None
        
        # Calculate trends (first half vs second half)
        efficiency_trend = None
        efficiency_change = None
        pace_trend = None
        pace_change = None
        
        if len(efficiencies) >= 4:
            mid = len(summaries) // 2
            recent_effs = [s.efficiency for s in summaries[:mid] if s.efficiency]
            older_effs = [s.efficiency for s in summaries[mid:] if s.efficiency]
            
            if recent_effs and older_effs:
                recent_avg = sum(recent_effs) / len(recent_effs)
                older_avg = sum(older_effs) / len(older_effs)
                change = ((recent_avg - older_avg) / older_avg) * 100 if older_avg else 0
                
                efficiency_change = change
                if change > 2:
                    efficiency_trend = "improving"
                elif change < -2:
                    efficiency_trend = "declining"
                else:
                    efficiency_trend = "stable"
        
        if len(paces) >= 4:
            mid = len(summaries) // 2
            recent_paces = [s.pace_per_km for s in summaries[:mid] if s.pace_per_km]
            older_paces = [s.pace_per_km for s in summaries[mid:] if s.pace_per_km]
            
            if recent_paces and older_paces:
                recent_avg = sum(recent_paces) / len(recent_paces)
                older_avg = sum(older_paces) / len(older_paces)
                change = ((older_avg - recent_avg) / older_avg) * 100 if older_avg else 0  # Faster = positive
                
                pace_change = change
                if change > 2:
                    pace_trend = "improving"
                elif change < -2:
                    pace_trend = "declining"
                else:
                    pace_trend = "stable"
        
        return ComparisonResult(
            workout_type=workout_type,
            total_activities=len(summaries),
            date_range_start=min(s.date for s in summaries),
            date_range_end=max(s.date for s in summaries),
            avg_pace_per_km=avg_pace,
            avg_efficiency=avg_efficiency,
            avg_hr=avg_hr,
            total_distance_km=total_distance,
            efficiency_trend=efficiency_trend,
            efficiency_change_pct=efficiency_change,
            pace_trend=pace_trend,
            pace_change_pct=pace_change,
            best_activity=best,
            worst_activity=worst,
            most_recent=summaries[0] if summaries else None,
            activities=summaries,
        )
    
    def get_activity_with_comparison(
        self,
        activity_id: UUID,
        athlete_id: UUID,
    ) -> Dict[str, Any]:
        """Get an activity with comparison to similar workouts"""
        activity = self.db.query(Activity).filter(
            Activity.id == activity_id,
            Activity.athlete_id == athlete_id,
        ).first()
        
        if not activity:
            return None
        
        # Get similar workouts (same type, last 90 days)
        similar = []
        if activity.workout_type:
            cutoff = datetime.utcnow() - timedelta(days=90)
            similar_activities = self.db.query(Activity).filter(
                Activity.athlete_id == athlete_id,
                Activity.workout_type == activity.workout_type,
                Activity.id != activity_id,
                Activity.start_time >= cutoff,
                Activity.distance_m >= 1000,
            ).order_by(Activity.start_time.desc()).limit(20).all()
            
            for sa in similar_activities:
                pace = sa.duration_s / (sa.distance_m / 1000) if sa.distance_m and sa.duration_s else None
                speed = (sa.distance_m / 1000) / (sa.duration_s / 3600) if sa.distance_m and sa.duration_s else None
                efficiency = speed / sa.avg_hr if speed and sa.avg_hr else None
                similar.append({
                    "id": str(sa.id),
                    "date": sa.start_time.isoformat(),
                    "distance_m": sa.distance_m,
                    "pace_per_km": pace,
                    "avg_hr": sa.avg_hr,
                    "efficiency": efficiency,
                })
        
        # Calculate this activity's metrics
        pace = activity.duration_s / (activity.distance_m / 1000) if activity.distance_m and activity.duration_s else None
        speed = (activity.distance_m / 1000) / (activity.duration_s / 3600) if activity.distance_m and activity.duration_s else None
        efficiency = speed / activity.avg_hr if speed and activity.avg_hr else None
        
        # Calculate percentile
        if similar and efficiency:
            similar_effs = [s["efficiency"] for s in similar if s.get("efficiency")]
            if similar_effs:
                better_count = sum(1 for e in similar_effs if efficiency > e)
                percentile = (better_count / len(similar_effs)) * 100
            else:
                percentile = None
        else:
            percentile = None
        
        # Get splits
        splits = self.db.query(ActivitySplit).filter(
            ActivitySplit.activity_id == activity_id
        ).order_by(ActivitySplit.split_number).all()
        
        splits_data = []
        for split in splits:
            splits_data.append({
                "split_number": split.split_number,
                "distance": float(split.distance) if split.distance else None,
                "elapsed_time": split.elapsed_time,
                "moving_time": split.moving_time,
                "average_heartrate": split.average_heartrate,
                "max_heartrate": split.max_heartrate,
                "average_cadence": float(split.average_cadence) if split.average_cadence else None,
                "gap_seconds_per_mile": float(split.gap_seconds_per_mile) if split.gap_seconds_per_mile else None,
            })
        
        return {
            "id": str(activity.id),
            "date": activity.start_time.isoformat(),
            "workout_type": activity.workout_type,
            "workout_zone": activity.workout_zone,
            "distance_m": activity.distance_m,
            "duration_s": activity.duration_s,
            "avg_hr": activity.avg_hr,
            "max_hr": activity.max_hr,
            "elevation_gain": float(activity.total_elevation_gain) if activity.total_elevation_gain else None,
            "pace_per_km": pace,
            "efficiency": efficiency,
            "intensity_score": activity.intensity_score,
            "temperature_f": activity.temperature_f,
            "splits": splits_data,
            "comparison": {
                "similar_count": len(similar),
                "percentile_vs_similar": percentile,
                "avg_similar_efficiency": sum(s["efficiency"] for s in similar if s.get("efficiency")) / len([s for s in similar if s.get("efficiency")]) if [s for s in similar if s.get("efficiency")] else None,
                "similar_activities": similar[:5],  # Return top 5 for reference
            } if similar else None,
        }
