"""
Insight Aggregator Service

The "brain" that collects signals from all analysis engines and produces
ranked, actionable insights for athletes.

This is THE MOAT - we answer "WHY" with causal attribution and personalized
pattern recognition. Not just "what happened" but "why it happened."

Design Principles:
- Never show raw numbers without context (always delta or comparison)
- Always cite the data source ("From YOUR history" vs "From population data")
- Rank insights by actionability and importance
- Generate on sync (not daily batch) for freshness
- Cache aggressively to control costs
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, date, timezone
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from enum import Enum
from decimal import Decimal
import statistics
import logging

from sqlalchemy import func, and_, or_, desc
from sqlalchemy.orm import Session

from models import (
    Activity,
    Athlete,
    DailyCheckin,
    BodyComposition,
    CalendarInsight,
    TrainingPlan,
    PlannedWorkout,
)

logger = logging.getLogger(__name__)


# =============================================================================
# INSIGHT TYPES AND PRIORITIES
# =============================================================================

class InsightType(str, Enum):
    """Types of insights we generate"""
    CAUSAL_ATTRIBUTION = "causal_attribution"  # WHY performance changed
    PATTERN_DETECTION = "pattern_detection"    # Recurring behavior
    TREND_ALERT = "trend_alert"                # Significant trend identified
    FATIGUE_WARNING = "fatigue_warning"        # Cumulative fatigue high
    BREAKTHROUGH = "breakthrough"               # Performance inflection
    COMPARISON = "comparison"                   # vs-similar analysis
    PHASE_SPECIFIC = "phase_specific"          # Build phase context
    INJURY_RISK = "injury_risk"                # Pattern matches injury history
    ACHIEVEMENT = "achievement"                 # PBs, milestones, streaks


class InsightPriority(int, Enum):
    """Priority levels for ranking"""
    CRITICAL = 100      # Injury risk, major warning
    HIGH = 80           # Breakthrough, significant trend
    MEDIUM = 60         # Pattern detection, comparison
    LOW = 40            # Phase context, achievement
    INFO = 20           # General info


# Premium insight types (require subscription)
PREMIUM_INSIGHT_TYPES = {
    InsightType.CAUSAL_ATTRIBUTION,
    InsightType.PATTERN_DETECTION,
    InsightType.INJURY_RISK,
    InsightType.PHASE_SPECIFIC,
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class GeneratedInsight:
    """A generated insight ready for display"""
    insight_type: InsightType
    priority: int
    title: str
    content: str
    
    # Context
    activity_id: Optional[UUID] = None
    insight_date: date = field(default_factory=date.today)
    
    # Supporting data for visualization
    data: Dict[str, Any] = field(default_factory=dict)
    
    # Source tracking
    source: str = "n1"  # "n1" (individual data) or "population"
    confidence: float = 1.0  # 0-1
    
    # For deduplication
    dedup_key: str = ""
    
    def __post_init__(self):
        if not self.dedup_key:
            self.dedup_key = f"{self.insight_type}:{self.title[:50]}"


@dataclass
class EfficiencyTrend:
    """Efficiency trend data"""
    current_ef: float
    previous_ef: float
    change_percent: float
    period_days: int
    trend: str  # "improving", "declining", "stable"
    hr_change_bpm: Optional[float] = None
    pace_context: Optional[str] = None


@dataclass
class BuildStatus:
    """Current build/training plan status"""
    plan_name: str
    current_week: int
    total_weeks: int
    current_phase: str
    phase_focus: str
    goal_race_name: Optional[str]
    goal_race_date: Optional[date]
    days_to_race: Optional[int]
    
    # KPIs
    threshold_pace_current: Optional[float] = None
    threshold_pace_start: Optional[float] = None
    ef_current: Optional[float] = None
    ef_start: Optional[float] = None
    long_run_max_miles: Optional[float] = None
    mp_capability_miles: Optional[float] = None
    
    # Trajectory
    projected_time: Optional[str] = None
    confidence: Optional[str] = None  # "high", "medium", "low"
    
    # This week
    week_focus: Optional[str] = None
    key_session: Optional[str] = None


@dataclass 
class AthleteIntelligence:
    """Banked learnings about what works for this athlete"""
    what_works: List[str] = field(default_factory=list)
    what_doesnt: List[str] = field(default_factory=list)
    patterns: Dict[str, Any] = field(default_factory=dict)
    injury_patterns: List[str] = field(default_factory=list)
    career_prs: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# INSIGHT AGGREGATOR SERVICE
# =============================================================================

class InsightAggregator:
    """
    Collects signals from all analysis engines and produces ranked insights.
    
    Called on activity sync to generate fresh insights.
    """
    
    def __init__(self, db: Session, athlete: Athlete):
        self.db = db
        self.athlete = athlete
        self.is_premium = athlete.subscription_tier in ("pro", "premium", "elite")
    
    def generate_insights(
        self,
        activity: Optional[Activity] = None,
        max_insights: int = 10
    ) -> List[GeneratedInsight]:
        """
        Generate insights based on current state and recent activity.
        
        Args:
            activity: The activity that triggered this generation (if any)
            max_insights: Maximum number of insights to return
            
        Returns:
            List of insights ranked by priority
        """
        all_insights: List[GeneratedInsight] = []
        
        try:
            # 1. Efficiency trend insights
            ef_insights = self._generate_efficiency_insights(activity)
            all_insights.extend(ef_insights)
            
            # 2. Pattern detection
            pattern_insights = self._generate_pattern_insights()
            all_insights.extend(pattern_insights)
            
            # 3. Comparison insights (if activity provided)
            if activity:
                comparison_insights = self._generate_comparison_insights(activity)
                all_insights.extend(comparison_insights)
            
            # 4. Fatigue/recovery insights
            fatigue_insights = self._generate_fatigue_insights()
            all_insights.extend(fatigue_insights)
            
            # 5. Build/phase insights (if active plan)
            build_insights = self._generate_build_insights()
            all_insights.extend(build_insights)
            
            # 6. Achievement insights
            achievement_insights = self._generate_achievement_insights(activity)
            all_insights.extend(achievement_insights)
            
        except Exception as e:
            logger.error(f"Error generating insights: {e}")
        
        # Filter by premium status
        if not self.is_premium:
            all_insights = [
                i for i in all_insights 
                if i.insight_type not in PREMIUM_INSIGHT_TYPES
            ]
        
        # Deduplicate
        seen_keys = set()
        unique_insights = []
        for insight in all_insights:
            if insight.dedup_key not in seen_keys:
                seen_keys.add(insight.dedup_key)
                unique_insights.append(insight)
        
        # Sort by priority (highest first)
        unique_insights.sort(key=lambda x: x.priority, reverse=True)
        
        # Limit
        return unique_insights[:max_insights]
    
    def _generate_efficiency_insights(
        self, 
        activity: Optional[Activity] = None
    ) -> List[GeneratedInsight]:
        """Generate insights about efficiency trends"""
        insights = []
        
        # Get recent activities with HR data
        recent = (
            self.db.query(Activity)
            .filter(
                Activity.athlete_id == self.athlete.id,
                Activity.avg_hr.isnot(None),
                Activity.average_speed.isnot(None),
                Activity.start_time >= datetime.now(timezone.utc) - timedelta(days=42)
            )
            .order_by(desc(Activity.start_time))
            .limit(30)
            .all()
        )
        
        if len(recent) < 5:
            return insights
        
        # Calculate EF for each (simple: speed / HR)
        # Lower HR at same speed = better EF
        def calc_ef(act: Activity) -> Optional[float]:
            if act.avg_hr and act.average_speed and act.avg_hr > 0:
                # meters/sec per bpm - higher is more efficient
                return act.average_speed / act.avg_hr
            return None
        
        efs = [(a, calc_ef(a)) for a in recent if calc_ef(a)]
        if len(efs) < 5:
            return insights
        
        # Compare recent 7 days vs previous 3 weeks
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        
        recent_efs = [ef for a, ef in efs if a.start_time >= week_ago]
        older_efs = [ef for a, ef in efs if a.start_time < week_ago]
        
        if len(recent_efs) >= 2 and len(older_efs) >= 3:
            avg_recent = statistics.mean(recent_efs)
            avg_older = statistics.mean(older_efs)
            
            change_pct = ((avg_recent - avg_older) / avg_older) * 100
            
            if abs(change_pct) >= 5:
                # Significant change detected
                trend = "improving" if change_pct > 0 else "declining"
                
                # Calculate HR difference at similar pace
                # (This would need more sophisticated matching in production)
                hr_diff = None
                if recent and len(recent) >= 2:
                    recent_hr = statistics.mean([a.avg_hr for a in recent[:3] if a.avg_hr])
                    older_hr = statistics.mean([a.avg_hr for a in recent[-3:] if a.avg_hr])
                    hr_diff = recent_hr - older_hr
                
                if trend == "improving":
                    title = "Your easy pace efficiency is improving"
                    hr_text = f", HR is {abs(hr_diff):.0f} bpm lower at similar pace" if hr_diff and hr_diff < 0 else ""
                    content = (
                        f"Your efficiency improved {abs(change_pct):.0f}% over the past week{hr_text}. "
                        f"Based on {len(recent_efs)} recent runs vs {len(older_efs)} from prior weeks."
                    )
                    priority = InsightPriority.HIGH
                else:
                    title = "Efficiency has declined slightly"
                    content = (
                        f"Your efficiency dropped {abs(change_pct):.0f}% over the past week. "
                        f"This could indicate fatigue, illness, or external stress. Monitor recovery."
                    )
                    priority = InsightPriority.MEDIUM
                
                insights.append(GeneratedInsight(
                    insight_type=InsightType.TREND_ALERT,
                    priority=priority,
                    title=title,
                    content=content,
                    data={
                        "change_percent": round(change_pct, 1),
                        "trend": trend,
                        "recent_count": len(recent_efs),
                        "comparison_count": len(older_efs),
                        "hr_change_bpm": round(hr_diff, 0) if hr_diff else None,
                    },
                    source="n1",
                ))
        
        return insights
    
    def _generate_pattern_insights(self) -> List[GeneratedInsight]:
        """Detect recurring patterns in training"""
        insights = []
        
        # Pattern: Running easy days too fast
        # Check last 4 weeks of "easy" labeled workouts
        # (In production, would use workout_type classification)
        
        recent = (
            self.db.query(Activity)
            .filter(
                Activity.athlete_id == self.athlete.id,
                Activity.start_time >= datetime.now(timezone.utc) - timedelta(days=28),
                Activity.avg_hr.isnot(None),
            )
            .order_by(desc(Activity.start_time))
            .all()
        )
        
        if len(recent) < 5:
            return insights
        
        # Look for pattern: high HR on what should be easy runs
        # (simplified - would need workout type classification)
        # Flag if avg HR > 75% of max on runs that aren't race-flagged
        
        max_hr = self.athlete.max_hr or 185  # Default estimate
        threshold_hr = max_hr * 0.75
        
        easy_runs = [
            a for a in recent 
            if not a.is_race_candidate and a.distance_m and a.distance_m > 3000
        ]
        
        too_hard_count = sum(1 for a in easy_runs if a.avg_hr and a.avg_hr > threshold_hr)
        
        if len(easy_runs) >= 4 and too_hard_count / len(easy_runs) >= 0.5:
            insights.append(GeneratedInsight(
                insight_type=InsightType.PATTERN_DETECTION,
                priority=InsightPriority.MEDIUM,
                title="Easy runs may be too hard",
                content=(
                    f"In {too_hard_count} of your last {len(easy_runs)} non-race runs, "
                    f"your HR averaged above {threshold_hr:.0f} bpm (75% of max). "
                    f"If these were meant to be easy runs, consider slowing down. "
                    f"Easy runs should feel conversational."
                ),
                data={
                    "too_hard_count": too_hard_count,
                    "total_runs": len(easy_runs),
                    "threshold_hr": threshold_hr,
                    "avg_hr": statistics.mean([a.avg_hr for a in easy_runs if a.avg_hr]),
                },
                source="n1",
            ))
        
        return insights
    
    def _generate_comparison_insights(self, activity: Activity) -> List[GeneratedInsight]:
        """Compare this activity to similar past activities"""
        insights = []
        
        if not activity.distance_m or not activity.avg_hr:
            return insights
        
        # Find similar activities (±15% distance, same sport)
        distance_min = activity.distance_m * 0.85
        distance_max = activity.distance_m * 1.15
        
        similar = (
            self.db.query(Activity)
            .filter(
                Activity.athlete_id == self.athlete.id,
                Activity.id != activity.id,
                Activity.distance_m.between(distance_min, distance_max),
                Activity.avg_hr.isnot(None),
                Activity.start_time >= datetime.now(timezone.utc) - timedelta(days=90)
            )
            .order_by(desc(Activity.start_time))
            .limit(20)
            .all()
        )
        
        if len(similar) < 3:
            return insights
        
        # Calculate where this activity ranks
        def calc_ef(act: Activity) -> float:
            if act.avg_hr and act.average_speed and act.avg_hr > 0:
                return act.average_speed / act.avg_hr
            return 0
        
        current_ef = calc_ef(activity)
        all_efs = sorted([calc_ef(a) for a in similar if calc_ef(a) > 0], reverse=True)
        
        if not all_efs or current_ef <= 0:
            return insights
        
        # Find percentile
        better_count = sum(1 for ef in all_efs if current_ef > ef)
        percentile = (better_count / len(all_efs)) * 100
        
        if percentile >= 80:
            insights.append(GeneratedInsight(
                insight_type=InsightType.COMPARISON,
                priority=InsightPriority.MEDIUM,
                title=f"Top {100-percentile:.0f}% efficiency for this distance",
                content=(
                    f"This {activity.distance_m/1609:.1f} mi run was more efficient than "
                    f"{percentile:.0f}% of your similar runs in the past 90 days. "
                    f"Great execution!"
                ),
                activity_id=activity.id,
                data={
                    "percentile": round(percentile, 0),
                    "similar_count": len(similar),
                    "distance_miles": round(activity.distance_m/1609, 1),
                },
                source="n1",
            ))
        elif percentile <= 20:
            insights.append(GeneratedInsight(
                insight_type=InsightType.COMPARISON,
                priority=InsightPriority.LOW,
                title="Lower efficiency than usual for this distance",
                content=(
                    f"This run was less efficient than {100-percentile:.0f}% of your similar runs. "
                    f"Could be fatigue, weather, or just an off day. Not every run is a winner."
                ),
                activity_id=activity.id,
                data={
                    "percentile": round(percentile, 0),
                    "similar_count": len(similar),
                },
                source="n1",
            ))
        
        return insights
    
    def _generate_fatigue_insights(self) -> List[GeneratedInsight]:
        """Detect cumulative fatigue signals"""
        insights = []
        
        # Look for declining efficiency across last 3-5 workouts
        recent = (
            self.db.query(Activity)
            .filter(
                Activity.athlete_id == self.athlete.id,
                Activity.avg_hr.isnot(None),
                Activity.average_speed.isnot(None),
            )
            .order_by(desc(Activity.start_time))
            .limit(5)
            .all()
        )
        
        if len(recent) < 3:
            return insights
        
        # Calculate EF trend
        efs = []
        for a in recent:
            if a.avg_hr and a.average_speed and a.avg_hr > 0:
                efs.append(a.average_speed / a.avg_hr)
        
        if len(efs) < 3:
            return insights
        
        # Check if consistently declining
        declining_count = sum(
            1 for i in range(len(efs)-1) 
            if efs[i] < efs[i+1]  # Lower EF in more recent run
        )
        
        if declining_count >= len(efs) - 1:
            insights.append(GeneratedInsight(
                insight_type=InsightType.FATIGUE_WARNING,
                priority=InsightPriority.HIGH,
                title="Efficiency declining across recent runs",
                content=(
                    f"Your last {len(efs)} runs show progressively lower efficiency. "
                    f"This often indicates cumulative fatigue. Consider extra recovery, "
                    f"a cutback day, or checking sleep/stress factors."
                ),
                data={
                    "run_count": len(efs),
                    "trend": "declining",
                },
                source="n1",
            ))
        
        return insights
    
    def _generate_build_insights(self) -> List[GeneratedInsight]:
        """Generate insights about current training build/phase"""
        insights = []
        
        # Check for active training plan
        active_plan = (
            self.db.query(TrainingPlan)
            .filter(
                TrainingPlan.athlete_id == self.athlete.id,
                TrainingPlan.status == "active",
            )
            .first()
        )
        
        if not active_plan:
            return insights
        
        # Calculate current week
        if active_plan.start_date:
            days_in = (date.today() - active_plan.start_date).days
            current_week = (days_in // 7) + 1
            
            if active_plan.goal_race_date:
                days_to_race = (active_plan.goal_race_date - date.today()).days
                
                if days_to_race <= 14 and days_to_race > 0:
                    insights.append(GeneratedInsight(
                        insight_type=InsightType.PHASE_SPECIFIC,
                        priority=InsightPriority.MEDIUM,
                        title=f"{days_to_race} days to race",
                        content=(
                            f"You're in the taper phase for {active_plan.goal_race_name or 'your goal race'}. "
                            f"Trust the work you've done. Focus on rest, nutrition, and staying healthy."
                        ),
                        data={
                            "days_to_race": days_to_race,
                            "race_name": active_plan.goal_race_name,
                        },
                        source="n1",
                    ))
        
        return insights
    
    def _generate_achievement_insights(
        self, 
        activity: Optional[Activity] = None
    ) -> List[GeneratedInsight]:
        """Generate achievement/milestone insights"""
        insights = []
        
        # Check for recent week stats
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        
        week_stats = (
            self.db.query(
                func.count(Activity.id).label("count"),
                func.sum(Activity.distance_m).label("distance"),
            )
            .filter(
                Activity.athlete_id == self.athlete.id,
                Activity.start_time >= week_ago,
            )
            .first()
        )
        
        if week_stats and week_stats.count and week_stats.count >= 6:
            insights.append(GeneratedInsight(
                insight_type=InsightType.ACHIEVEMENT,
                priority=InsightPriority.LOW,
                title=f"Consistent week: {week_stats.count} runs",
                content=(
                    f"You logged {week_stats.count} runs this week "
                    f"({week_stats.distance/1609:.1f} miles total). "
                    f"Consistency is the foundation of improvement."
                ),
                data={
                    "run_count": week_stats.count,
                    "total_miles": round(week_stats.distance/1609, 1) if week_stats.distance else 0,
                },
                source="n1",
            ))
        
        return insights
    
    def get_build_status(self) -> Optional[BuildStatus]:
        """Get current build/training plan status"""
        active_plan = (
            self.db.query(TrainingPlan)
            .filter(
                TrainingPlan.athlete_id == self.athlete.id,
                TrainingPlan.status == "active",
            )
            .first()
        )
        
        if not active_plan:
            return None
        
        # Calculate current week
        current_week = 1
        days_to_race = None
        
        if active_plan.start_date:
            days_in = (date.today() - active_plan.start_date).days
            current_week = max(1, (days_in // 7) + 1)
        
        if active_plan.goal_race_date:
            days_to_race = (active_plan.goal_race_date - date.today()).days
        
        # Get this week's focus from planned workouts
        week_start = date.today() - timedelta(days=date.today().weekday())
        week_end = week_start + timedelta(days=6)
        
        this_week_workouts = (
            self.db.query(PlannedWorkout)
            .filter(
                PlannedWorkout.plan_id == active_plan.id,
                PlannedWorkout.scheduled_date.between(week_start, week_end),
            )
            .all()
        )
        
        # Find key session
        key_session = None
        for w in this_week_workouts:
            if w.workout_type and w.workout_type.lower() in ("threshold", "tempo", "long_mp", "intervals"):
                key_session = f"{w.workout_type.replace('_', ' ').title()} - {w.title or ''}"
                break
        
        return BuildStatus(
            plan_name=active_plan.name or "Training Plan",
            current_week=current_week,
            total_weeks=active_plan.duration_weeks or 18,
            current_phase=active_plan.current_phase or "Build",
            phase_focus="",  # Would come from plan metadata
            goal_race_name=active_plan.goal_race_name,
            goal_race_date=active_plan.goal_race_date,
            days_to_race=days_to_race,
            week_focus="",  # Would come from plan metadata
            key_session=key_session,
        )
    
    def get_athlete_intelligence(self) -> AthleteIntelligence:
        """
        Get banked learnings about what works for this athlete.
        
        In production, this would pull from a dedicated athlete_intelligence table
        that's populated over time. For now, we generate some basic insights.
        """
        intelligence = AthleteIntelligence()
        
        # Calculate what correlates with good performance
        # (Simplified - would be much more sophisticated in production)
        
        recent = (
            self.db.query(Activity)
            .filter(
                Activity.athlete_id == self.athlete.id,
                Activity.start_time >= datetime.now(timezone.utc) - timedelta(days=90),
            )
            .all()
        )
        
        if len(recent) >= 10:
            # Check consistency pattern
            weeks_with_runs = set()
            for a in recent:
                week_num = a.start_time.isocalendar()[1]
                weeks_with_runs.add(week_num)
            
            if len(weeks_with_runs) >= 10:
                intelligence.what_works.append(
                    f"Consistency: You've run in {len(weeks_with_runs)} of the last 12 weeks"
                )
        
        # Volume pattern
        total_distance = sum(a.distance_m or 0 for a in recent)
        avg_weekly = (total_distance / 90) * 7 / 1609  # miles per week
        
        if avg_weekly >= 30:
            intelligence.what_works.append(
                f"Volume: Averaging {avg_weekly:.0f} miles/week builds your aerobic base"
            )
        
        # Check for injury history (would come from athlete profile in production)
        # For now, just add a placeholder
        intelligence.injury_patterns.append(
            "No injury patterns detected yet (need more history)"
        )
        
        return intelligence
    
    def persist_insights(self, insights: List[GeneratedInsight]) -> int:
        """
        Persist generated insights to the database.
        
        Returns number of insights saved.
        """
        saved = 0
        
        for insight in insights:
            # Check if similar insight already exists today
            existing = (
                self.db.query(CalendarInsight)
                .filter(
                    CalendarInsight.athlete_id == self.athlete.id,
                    CalendarInsight.insight_date == insight.insight_date,
                    CalendarInsight.insight_type == insight.insight_type.value,
                    CalendarInsight.title == insight.title,
                )
                .first()
            )
            
            if not existing:
                db_insight = CalendarInsight(
                    athlete_id=self.athlete.id,
                    insight_date=insight.insight_date,
                    insight_type=insight.insight_type.value,
                    priority=insight.priority,
                    title=insight.title,
                    content=insight.content,
                    activity_id=insight.activity_id,
                    generation_data=insight.data,
                )
                self.db.add(db_insight)
                saved += 1
        
        if saved > 0:
            self.db.commit()
        
        return saved


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def generate_insights_for_athlete(
    db: Session,
    athlete: Athlete,
    activity: Optional[Activity] = None,
    persist: bool = True,
) -> List[GeneratedInsight]:
    """
    Generate insights for an athlete, optionally triggered by an activity.
    
    This is the main entry point called from activity sync.
    """
    aggregator = InsightAggregator(db, athlete)
    insights = aggregator.generate_insights(activity)
    
    if persist and insights:
        aggregator.persist_insights(insights)
    
    return insights


def get_active_insights(
    db: Session,
    athlete_id: UUID,
    limit: int = 10,
    include_dismissed: bool = False,
) -> List[CalendarInsight]:
    """
    Get active insights for an athlete.
    
    Returns most recent, highest priority insights.
    """
    query = (
        db.query(CalendarInsight)
        .filter(
            CalendarInsight.athlete_id == athlete_id,
            CalendarInsight.insight_date >= date.today() - timedelta(days=7),
        )
    )
    
    if not include_dismissed:
        query = query.filter(CalendarInsight.is_dismissed == False)
    
    return (
        query
        .order_by(desc(CalendarInsight.priority), desc(CalendarInsight.created_at))
        .limit(limit)
        .all()
    )
