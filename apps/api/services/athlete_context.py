"""
Athlete Context Builder

Builds and maintains a structured "intelligence dossier" for each athlete.
This context is injected into GPT prompts to make AI responses smarter.

The context block includes:
- Current training state (ACWR, phase, load)
- Historical patterns from their data
- Data quality indicators
- Performance trends
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, text
import statistics
import json

from models import Activity, DailyCheckin, BodyComposition, Athlete


@dataclass
class TrainingState:
    """Current training state snapshot."""
    acwr: float
    phase: str  # "taper", "recovery", "steady", "build", "overreaching"
    
    trailing_7d_km: float
    trailing_28d_km: float
    avg_weekly_km: float
    
    runs_last_7d: int
    runs_last_28d: int
    avg_runs_per_week: float
    
    intensity_distribution: Dict[str, float]  # easy/tempo/long/interval %
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "acwr": round(self.acwr, 2),
            "phase": self.phase,
            "trailing_7d_km": round(self.trailing_7d_km, 1),
            "trailing_28d_km": round(self.trailing_28d_km, 1),
            "avg_weekly_km": round(self.avg_weekly_km, 1),
            "runs_last_7d": self.runs_last_7d,
            "runs_last_28d": self.runs_last_28d,
            "avg_runs_per_week": round(self.avg_runs_per_week, 1),
            "intensity_distribution": {k: round(v, 1) for k, v in self.intensity_distribution.items()},
        }


@dataclass
class RecentPerformance:
    """Recent performance trends."""
    last_5_runs_avg_pace: Optional[float]  # seconds/km
    pace_trend: str  # "improving", "stable", "declining"
    
    last_5_runs_avg_hr: Optional[int]
    hr_trend: str
    
    efficiency_trend: str  # pace/HR ratio trend
    
    recent_workout_types: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "last_5_runs_avg_pace_sec": self.last_5_runs_avg_pace,
            "pace_trend": self.pace_trend,
            "last_5_runs_avg_hr": self.last_5_runs_avg_hr,
            "hr_trend": self.hr_trend,
            "efficiency_trend": self.efficiency_trend,
            "recent_workout_types": self.recent_workout_types,
        }


@dataclass
class DataAvailability:
    """What data we have for this athlete."""
    total_activities: int
    activities_with_hr: int
    activities_with_splits: int
    
    checkin_density_30d: float  # 0-1, what % of days have check-ins
    has_sleep_data: bool
    has_hrv_data: bool
    has_body_comp_data: bool
    
    earliest_activity: Optional[datetime]
    latest_activity: Optional[datetime]
    days_of_data: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_activities": self.total_activities,
            "activities_with_hr": self.activities_with_hr,
            "activities_with_splits": self.activities_with_splits,
            "checkin_density_30d": round(self.checkin_density_30d, 2),
            "has_sleep_data": self.has_sleep_data,
            "has_hrv_data": self.has_hrv_data,
            "has_body_comp_data": self.has_body_comp_data,
            "earliest_activity": self.earliest_activity.isoformat() if self.earliest_activity else None,
            "latest_activity": self.latest_activity.isoformat() if self.latest_activity else None,
            "days_of_data": self.days_of_data,
        }


@dataclass
class PersonalPatterns:
    """
    Patterns discovered from this athlete's historical data.
    These are athlete-specific, NOT population averages.
    """
    # What inputs correlate with this athlete's best performances?
    best_performance_patterns: List[str]  # e.g., "Lower HRV before PRs"
    
    # Typical values for this athlete
    typical_weekly_volume: float
    typical_easy_pace: Optional[float]
    typical_tempo_pace: Optional[float]
    
    # Consistency patterns
    avg_runs_per_week: float
    longest_streak: int  # consecutive weeks with 3+ runs
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "best_performance_patterns": self.best_performance_patterns,
            "typical_weekly_volume_km": round(self.typical_weekly_volume, 1),
            "typical_easy_pace_sec": self.typical_easy_pace,
            "typical_tempo_pace_sec": self.typical_tempo_pace,
            "avg_runs_per_week": round(self.avg_runs_per_week, 1),
            "longest_streak_weeks": self.longest_streak,
        }


@dataclass
class AthleteContextProfile:
    """
    The complete 'intelligence dossier' for an athlete.
    This is what gets injected into GPT prompts.
    """
    athlete_id: str
    generated_at: datetime
    
    # Current state
    training_state: TrainingState
    recent_performance: RecentPerformance
    
    # Data quality
    data_availability: DataAvailability
    
    # Personal patterns (learned from their data)
    patterns: PersonalPatterns
    
    # Pre-built context block for prompt injection
    context_block: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "athlete_id": self.athlete_id,
            "generated_at": self.generated_at.isoformat(),
            "training_state": self.training_state.to_dict(),
            "recent_performance": self.recent_performance.to_dict(),
            "data_availability": self.data_availability.to_dict(),
            "patterns": self.patterns.to_dict(),
            "context_block": self.context_block,
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class AthleteContextBuilder:
    """
    Builds the athlete context profile.
    
    Can be called:
    - On-demand (for fresh context)
    - Via background job (for caching)
    """
    
    # ACWR thresholds
    ACWR_TAPER = 0.8
    ACWR_RECOVERY = 0.9
    ACWR_STEADY = 1.1
    ACWR_BUILD = 1.3
    
    def __init__(self, db: Session):
        self.db = db
    
    def build(self, athlete_id: UUID) -> AthleteContextProfile:
        """Build complete context profile for an athlete."""
        from datetime import timezone
        now = datetime.now(timezone.utc)
        
        # Build each component
        training_state = self._build_training_state(athlete_id, now)
        recent_performance = self._build_recent_performance(athlete_id)
        data_availability = self._build_data_availability(athlete_id)
        patterns = self._build_personal_patterns(athlete_id)
        
        # Build context block
        context_block = self._build_context_block(
            training_state, recent_performance, data_availability, patterns
        )
        
        return AthleteContextProfile(
            athlete_id=str(athlete_id),
            generated_at=now,
            training_state=training_state,
            recent_performance=recent_performance,
            data_availability=data_availability,
            patterns=patterns,
            context_block=context_block,
        )
    
    def _build_training_state(self, athlete_id: UUID, now: datetime) -> TrainingState:
        """Build current training state."""
        # Make timezone-aware if needed
        from datetime import timezone
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        seven_days_ago = now - timedelta(days=7)
        twenty_eight_days_ago = now - timedelta(days=28)
        
        # Get activities
        activities_28d = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= twenty_eight_days_ago,
            Activity.sport.ilike("run"),
        ).all()
        
        activities_7d = [a for a in activities_28d if a.start_time >= seven_days_ago]
        
        # Calculate volumes
        volume_7d = sum(a.distance_m or 0 for a in activities_7d) / 1000
        volume_28d = sum(a.distance_m or 0 for a in activities_28d) / 1000
        avg_weekly = volume_28d / 4
        
        # ACWR
        chronic_weekly = avg_weekly if avg_weekly > 0 else 1
        acwr = volume_7d / chronic_weekly if chronic_weekly > 0 else 1.0
        
        # Phase
        if acwr < self.ACWR_TAPER:
            phase = "taper"
        elif acwr < self.ACWR_RECOVERY:
            phase = "recovery"
        elif acwr <= self.ACWR_STEADY:
            phase = "steady"
        elif acwr <= self.ACWR_BUILD:
            phase = "build"
        else:
            phase = "overreaching"
        
        # Intensity distribution
        intensity_dist = self._calculate_intensity_distribution(activities_28d)
        
        return TrainingState(
            acwr=acwr,
            phase=phase,
            trailing_7d_km=volume_7d,
            trailing_28d_km=volume_28d,
            avg_weekly_km=avg_weekly,
            runs_last_7d=len(activities_7d),
            runs_last_28d=len(activities_28d),
            avg_runs_per_week=len(activities_28d) / 4,
            intensity_distribution=intensity_dist,
        )
    
    def _calculate_intensity_distribution(self, activities: List[Activity]) -> Dict[str, float]:
        """Calculate intensity distribution."""
        if not activities:
            return {"easy": 0, "tempo": 0, "long": 0, "interval": 0}
        
        type_map = {
            "easy_run": "easy", "recovery_run": "easy", "aerobic_run": "easy",
            "tempo_run": "tempo", "threshold_run": "tempo", "tempo_intervals": "tempo",
            "long_run": "long", "medium_long_run": "long",
            "vo2max_intervals": "interval", "track_workout": "interval", "fartlek": "interval",
        }
        
        counts = {"easy": 0, "tempo": 0, "long": 0, "interval": 0}
        for a in activities:
            category = type_map.get(a.workout_type, "easy")
            counts[category] += 1
        
        total = len(activities)
        return {k: (v / total) * 100 for k, v in counts.items()}
    
    def _build_recent_performance(self, athlete_id: UUID) -> RecentPerformance:
        """Build recent performance metrics."""
        # Get last 5 runs
        recent_runs = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.sport.ilike("run"),
        ).order_by(desc(Activity.start_time)).limit(10).all()
        
        if not recent_runs:
            return RecentPerformance(
                last_5_runs_avg_pace=None,
                pace_trend="unknown",
                last_5_runs_avg_hr=None,
                hr_trend="unknown",
                efficiency_trend="unknown",
                recent_workout_types=[],
            )
        
        last_5 = recent_runs[:5]
        prev_5 = recent_runs[5:10] if len(recent_runs) > 5 else []
        
        # Calculate paces
        paces = [
            a.duration_s / (a.distance_m / 1000) 
            for a in last_5 
            if a.duration_s and a.distance_m
        ]
        avg_pace = statistics.mean(paces) if paces else None
        
        prev_paces = [
            a.duration_s / (a.distance_m / 1000) 
            for a in prev_5 
            if a.duration_s and a.distance_m
        ]
        prev_avg_pace = statistics.mean(prev_paces) if prev_paces else None
        
        # Pace trend (lower is faster)
        if avg_pace and prev_avg_pace:
            if avg_pace < prev_avg_pace * 0.98:
                pace_trend = "improving"
            elif avg_pace > prev_avg_pace * 1.02:
                pace_trend = "declining"
            else:
                pace_trend = "stable"
        else:
            pace_trend = "unknown"
        
        # HR
        hrs = [a.avg_hr for a in last_5 if a.avg_hr]
        avg_hr = int(statistics.mean(hrs)) if hrs else None
        
        prev_hrs = [a.avg_hr for a in prev_5 if a.avg_hr]
        prev_avg_hr = statistics.mean(prev_hrs) if prev_hrs else None
        
        if avg_hr and prev_avg_hr:
            if avg_hr < prev_avg_hr * 0.98:
                hr_trend = "decreasing"
            elif avg_hr > prev_avg_hr * 1.02:
                hr_trend = "increasing"
            else:
                hr_trend = "stable"
        else:
            hr_trend = "unknown"
        
        # Efficiency trend
        if pace_trend == "improving" and hr_trend in ["stable", "decreasing"]:
            efficiency_trend = "improving"
        elif pace_trend == "declining" and hr_trend == "increasing":
            efficiency_trend = "declining"
        else:
            efficiency_trend = "stable"
        
        workout_types = [a.workout_type for a in last_5 if a.workout_type]
        
        return RecentPerformance(
            last_5_runs_avg_pace=avg_pace,
            pace_trend=pace_trend,
            last_5_runs_avg_hr=avg_hr,
            hr_trend=hr_trend,
            efficiency_trend=efficiency_trend,
            recent_workout_types=workout_types[:5],
        )
    
    def _build_data_availability(self, athlete_id: UUID) -> DataAvailability:
        """Analyze what data is available for this athlete."""
        # Activities
        activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.sport.ilike("run"),
        ).all()
        
        total = len(activities)
        with_hr = sum(1 for a in activities if a.avg_hr)
        
        # Get split counts
        with_splits_result = self.db.execute(
            text("""
                SELECT COUNT(DISTINCT a.id) 
                FROM activity a 
                JOIN activity_split s ON a.id = s.activity_id 
                WHERE a.athlete_id = :athlete_id
            """),
            {"athlete_id": str(athlete_id)}
        ).scalar() or 0
        with_splits = int(with_splits_result)
        
        # Check-ins
        from datetime import timezone
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        checkins = self.db.query(DailyCheckin).filter(
            DailyCheckin.athlete_id == athlete_id,
            DailyCheckin.date >= thirty_days_ago.date(),
        ).all()
        
        checkin_density = len(checkins) / 30
        has_sleep = any(c.sleep_h is not None for c in checkins)
        has_hrv = any(c.hrv_rmssd is not None for c in checkins)
        
        # Body comp
        body_comp_count = self.db.query(BodyComposition).filter(
            BodyComposition.athlete_id == athlete_id,
        ).count()
        
        # Date range
        if activities:
            earliest = min(a.start_time for a in activities)
            latest = max(a.start_time for a in activities)
            days = (latest - earliest).days
        else:
            earliest = None
            latest = None
            days = 0
        
        return DataAvailability(
            total_activities=total,
            activities_with_hr=with_hr,
            activities_with_splits=with_splits,
            checkin_density_30d=checkin_density,
            has_sleep_data=has_sleep,
            has_hrv_data=has_hrv,
            has_body_comp_data=body_comp_count > 0,
            earliest_activity=earliest,
            latest_activity=latest,
            days_of_data=days,
        )
    
    def _build_personal_patterns(self, athlete_id: UUID) -> PersonalPatterns:
        """
        Discover patterns from this athlete's data.
        This is where we learn from THEIR history, not population averages.
        """
        # Get all activities
        activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.sport.ilike("run"),
        ).order_by(Activity.start_time).all()
        
        if not activities:
            return PersonalPatterns(
                best_performance_patterns=[],
                typical_weekly_volume=0,
                typical_easy_pace=None,
                typical_tempo_pace=None,
                avg_runs_per_week=0,
                longest_streak=0,
            )
        
        # Calculate typical weekly volume (median over last 12 weeks)
        from datetime import timezone
        now = datetime.now(timezone.utc)
        weekly_volumes = []
        for week_offset in range(12):
            week_start = now - timedelta(days=7 * (week_offset + 1))
            week_end = now - timedelta(days=7 * week_offset)
            week_activities = [
                a for a in activities 
                if week_start <= a.start_time < week_end
            ]
            volume = sum(a.distance_m or 0 for a in week_activities) / 1000
            if volume > 0:  # Only count weeks with activity
                weekly_volumes.append(volume)
        
        typical_volume = statistics.median(weekly_volumes) if weekly_volumes else 0
        
        # Calculate typical paces by workout type
        easy_paces = [
            a.duration_s / (a.distance_m / 1000)
            for a in activities
            if a.workout_type in ["easy_run", "recovery_run", "aerobic_run"]
            and a.duration_s and a.distance_m
        ]
        typical_easy = statistics.median(easy_paces) if easy_paces else None
        
        tempo_paces = [
            a.duration_s / (a.distance_m / 1000)
            for a in activities
            if a.workout_type in ["tempo_run", "threshold_run", "tempo_intervals"]
            and a.duration_s and a.distance_m
        ]
        typical_tempo = statistics.median(tempo_paces) if tempo_paces else None
        
        # Consistency streak
        longest_streak = self._calculate_longest_streak(activities)
        
        # Average runs per week
        if activities:
            date_range = (activities[-1].start_time - activities[0].start_time).days
            weeks = max(1, date_range / 7)
            avg_per_week = len(activities) / weeks
        else:
            avg_per_week = 0
        
        # TODO: In future, add more pattern discovery here
        # e.g., correlation between sleep/HRV and performance
        patterns = []
        
        return PersonalPatterns(
            best_performance_patterns=patterns,
            typical_weekly_volume=typical_volume,
            typical_easy_pace=typical_easy,
            typical_tempo_pace=typical_tempo,
            avg_runs_per_week=avg_per_week,
            longest_streak=longest_streak,
        )
    
    def _calculate_longest_streak(self, activities: List[Activity]) -> int:
        """Calculate longest streak of consecutive weeks with 3+ runs."""
        if not activities:
            return 0
        
        # Group by week
        from collections import defaultdict
        weeks = defaultdict(int)
        for a in activities:
            week_key = a.start_time.isocalendar()[:2]  # (year, week)
            weeks[week_key] += 1
        
        # Find longest streak
        sorted_weeks = sorted(weeks.keys())
        longest = 0
        current = 0
        
        for i, week in enumerate(sorted_weeks):
            if weeks[week] >= 3:
                current += 1
                longest = max(longest, current)
            else:
                current = 0
        
        return longest
    
    def _build_context_block(
        self,
        training_state: TrainingState,
        recent_performance: RecentPerformance,
        data_availability: DataAvailability,
        patterns: PersonalPatterns,
    ) -> str:
        """Build the context block for GPT prompt injection."""
        lines = [
            "=== ATHLETE PROFILE ===",
            "",
            "CURRENT TRAINING STATE:",
            f"- Phase: {training_state.phase.upper()} (ACWR: {training_state.acwr:.2f})",
            f"- Last 7 days: {training_state.trailing_7d_km:.1f}km across {training_state.runs_last_7d} runs",
            f"- Typical weekly: {training_state.avg_weekly_km:.1f}km",
            f"- Intensity mix: {training_state.intensity_distribution.get('easy', 0):.0f}% easy, "
            f"{training_state.intensity_distribution.get('tempo', 0):.0f}% tempo, "
            f"{training_state.intensity_distribution.get('interval', 0):.0f}% intervals",
            "",
            "RECENT TRENDS:",
            f"- Pace trend: {recent_performance.pace_trend}",
            f"- HR trend: {recent_performance.hr_trend}",
            f"- Efficiency: {recent_performance.efficiency_trend}",
            "",
            "ATHLETE PATTERNS:",
            f"- Typical weekly volume: {patterns.typical_weekly_volume:.1f}km",
            f"- Average runs/week: {patterns.avg_runs_per_week:.1f}",
            f"- Longest consistent streak: {patterns.longest_streak} weeks",
            "",
            "DATA QUALITY:",
            f"- Total runs: {data_availability.total_activities}",
            f"- Days of history: {data_availability.days_of_data}",
            f"- Check-in coverage: {data_availability.checkin_density_30d * 100:.0f}% of last 30 days",
            "",
            "=== END PROFILE ===",
        ]
        
        return "\n".join(lines)
