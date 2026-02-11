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
# PHASE DISPLAY NAMES
# =============================================================================

PHASE_DISPLAY_NAMES = {
    "base": "Base",
    "base_speed": "Base + Speed",
    "volume_build": "Volume Build",
    "threshold": "Threshold",
    "marathon_specific": "Marathon Specific",
    "race_specific": "Race Specific",
    "hold": "Maintenance",
    "taper": "Taper",
    "race": "Race Week",
    "recovery": "Recovery",
    "build": "Build",
    "build1": "Build",
    "build2": "Build",
    "peak": "Peak",
    "cutback": "Cutback",
}


def format_phase(phase: Optional[str]) -> str:
    """Convert raw phase name to human-readable display name."""
    if not phase:
        return "Build"
    key = phase.lower().replace(" ", "_")
    return PHASE_DISPLAY_NAMES.get(key, phase.replace("_", " ").title())


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


# Elite-only insight types (require paid access)
ELITE_ONLY_INSIGHT_TYPES = {
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
    insight_date: Optional[date] = None  # Set from activity.start_time; falls back to today
    
    # Supporting data for visualization
    data: Dict[str, Any] = field(default_factory=dict)
    
    # Source tracking
    source: str = "n1"  # "n1" (individual data) or "population"
    confidence: float = 1.0  # 0-1
    
    # For deduplication — must be stable across regenerations.
    # Do NOT include changing data (numbers, counts) in this key.
    dedup_key: str = ""
    
    def __post_init__(self):
        if not self.dedup_key:
            # Use activity_id for activity-linked insights (unique per activity),
            # otherwise use type + a stable title prefix (strip digits).
            if self.activity_id:
                self.dedup_key = f"{self.insight_type}:{self.activity_id}"
            else:
                # Strip digits so "30-day volume: 201.5 miles" and "30-day volume: 209.5 miles"
                # both become the same key.
                import re
                stable_title = re.sub(r'[\d.]+', '', self.title).strip()[:40]
                self.dedup_key = f"{self.insight_type}:{stable_title}"


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
    what_works: List[Dict[str, str]] = field(default_factory=list)  # [{text, source}]
    what_doesnt: List[Dict[str, str]] = field(default_factory=list)  # [{text, source}]
    patterns: Dict[str, Any] = field(default_factory=dict)
    injury_patterns: List[Dict[str, str]] = field(default_factory=list)  # [{text, source}]
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
        # Elite is the single paid tier; legacy paid tiers still grant Elite access for now.
        self.is_elite = bool(getattr(athlete, "has_active_subscription", False)) or athlete.subscription_tier == "elite"
    
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
        
        # Stamp insight_date from the triggering activity's actual date,
        # not the date insight generation happens to run.
        activity_date = (
            activity.start_time.date()
            if activity and getattr(activity, "start_time", None)
            else None
        )
        for insight in all_insights:
            if insight.insight_date is None:
                if insight.activity_id and activity_date:
                    insight.insight_date = activity_date
                else:
                    insight.insight_date = date.today()
        
        # Filter by Elite status
        if not self.is_elite:
            all_insights = [
                i for i in all_insights 
                if i.insight_type not in ELITE_ONLY_INSIGHT_TYPES
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
            # "Top X%" means you're in the top X% — lower is better.
            # Beating 100% of peers = top 1% (clamp to avoid "top 0%").
            top_pct = max(1, round(100 - percentile))
            insights.append(GeneratedInsight(
                insight_type=InsightType.COMPARISON,
                priority=InsightPriority.MEDIUM,
                title=f"Top {top_pct}% efficiency for this distance",
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
        if active_plan.plan_start_date:
            days_in = (date.today() - active_plan.plan_start_date).days
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
        
        # Lower threshold to 3 runs (was 6)
        if week_stats and week_stats.count and week_stats.count >= 3:
            miles = round(week_stats.distance/1609, 1) if week_stats.distance else 0
            insights.append(GeneratedInsight(
                insight_type=InsightType.ACHIEVEMENT,
                priority=InsightPriority.LOW,
                title=f"This week: {week_stats.count} runs, {miles} mi",
                content=f"Logged {week_stats.count} runs totaling {miles} miles.",
                data={
                    "run_count": week_stats.count,
                    "total_miles": miles,
                },
                source="n1",
            ))
        
        # Monthly volume insight
        month_ago = datetime.now(timezone.utc) - timedelta(days=30)
        month_stats = (
            self.db.query(
                func.count(Activity.id).label("count"),
                func.sum(Activity.distance_m).label("distance"),
            )
            .filter(
                Activity.athlete_id == self.athlete.id,
                Activity.start_time >= month_ago,
            )
            .first()
        )
        
        if month_stats and month_stats.count and month_stats.count >= 5:
            miles = round(month_stats.distance/1609, 1) if month_stats.distance else 0
            insights.append(GeneratedInsight(
                insight_type=InsightType.TREND_ALERT,
                priority=InsightPriority.MEDIUM,
                title=f"30-day volume: {miles} miles",
                content=f"{month_stats.count} runs over the past 30 days. Avg {miles/4.3:.0f} mi/week.",
                data={
                    "run_count": month_stats.count,
                    "total_miles": miles,
                    "avg_weekly": round(miles/4.3, 1),
                },
                source="n1",
            ))
        
        # Check for hard workouts in past 14 days
        HARD_TYPES = {'race', 'threshold_run', 'tempo_run', 'vo2max_intervals', 
                      'fartlek', 'intervals', 'threshold', 'tempo'}
        two_weeks = datetime.now(timezone.utc) - timedelta(days=14)
        
        hard_count = (
            self.db.query(func.count(Activity.id))
            .filter(
                Activity.athlete_id == self.athlete.id,
                Activity.start_time >= two_weeks,
                Activity.workout_type.in_(HARD_TYPES),
            )
            .scalar() or 0
        )
        
        if hard_count >= 1:
            insights.append(GeneratedInsight(
                insight_type=InsightType.PATTERN_DETECTION,
                priority=InsightPriority.MEDIUM,
                title=f"{hard_count} quality session{'s' if hard_count > 1 else ''} in 14 days",
                content=f"Tracked {hard_count} hard workout{'s' if hard_count > 1 else ''} recently. Data collection in progress.",
                data={"hard_count": hard_count},
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
        
        if active_plan.plan_start_date:
            days_in = (date.today() - active_plan.plan_start_date).days
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
        
        # Find key session and current phase from this week's workouts
        key_session = None
        current_phase = None
        
        for w in this_week_workouts:
            # Get phase from first workout with a phase
            if not current_phase and w.phase:
                current_phase = w.phase
            
            # Find key session (threshold, tempo, intervals, long_mp)
            if w.workout_type and w.workout_type.lower() in ("threshold", "tempo", "long_mp", "intervals"):
                key_session = f"{w.workout_type.replace('_', ' ').title()} - {w.title or ''}"
        
        # If no phase found from this week, try to get from any planned workout
        if not current_phase:
            any_workout = (
                self.db.query(PlannedWorkout)
                .filter(
                    PlannedWorkout.plan_id == active_plan.id,
                    PlannedWorkout.week_number == current_week,
                )
                .first()
            )
            if any_workout:
                current_phase = any_workout.phase
        
        return BuildStatus(
            plan_name=active_plan.name or "Training Plan",
            current_week=current_week,
            total_weeks=active_plan.total_weeks or 18,
            current_phase=format_phase(current_phase),
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

        # IMPORTANT: These are allowed to be "micro insights", but they must be stated
        # accurately. No universalized claims. Always include the analysis window and
        # sample sizes implicitly in the wording when possible.

        HARD_TYPES = {
            "race",
            "threshold_run",
            "tempo_run",
            "vo2max_intervals",
            "fartlek",
            "intervals",
            "threshold",
            "tempo",
        }

        now = datetime.now(timezone.utc)
        lookback_days = 730  # ~2 years (you have enough history; use it)

        runs: List[Activity] = (
            self.db.query(Activity)
            .filter(
                Activity.athlete_id == self.athlete.id,
                Activity.sport == "run",
                Activity.start_time >= now - timedelta(days=lookback_days),
            )
            .order_by(Activity.start_time.asc())
            .all()
        )

        if not runs:
            return intelligence

        def _miles(a: Activity) -> float:
            return float(a.distance_m or 0) / 1609.344

        def _ef(a: Activity) -> Optional[float]:
            # Efficiency proxy consistent with other parts of this service:
            # higher = more speed per bpm.
            if a.avg_hr and a.average_speed and a.avg_hr > 0:
                try:
                    return float(a.average_speed) / float(a.avg_hr)
                except Exception:
                    return None
            return None

        def _week_key(dt: datetime) -> Tuple[int, int]:
            iso = dt.isocalendar()
            return (int(iso[0]), int(iso[1]))  # (iso_year, iso_week)

        def _monday_of_iso_week(d: date) -> date:
            # Monday-based week start (matches ISO week semantics)
            return d - timedelta(days=d.weekday())

        def _last_n_weeks(end_date: date, n: int) -> List[Tuple[int, int]]:
            keys: List[Tuple[int, int]] = []
            cursor = _monday_of_iso_week(end_date)
            for _ in range(n):
                iso = cursor.isocalendar()
                keys.append((int(iso[0]), int(iso[1])))
                cursor = cursor - timedelta(days=7)
            return keys

        # --- Weekly aggregates (counts, mileage, EF distribution) ---
        weekly_run_counts: Dict[Tuple[int, int], int] = {}
        weekly_miles: Dict[Tuple[int, int], float] = {}
        weekly_hard_counts: Dict[Tuple[int, int], int] = {}
        weekly_efs: Dict[Tuple[int, int], List[float]] = {}

        for a in runs:
            wk = _week_key(a.start_time)
            weekly_run_counts[wk] = weekly_run_counts.get(wk, 0) + 1
            weekly_miles[wk] = weekly_miles.get(wk, 0.0) + _miles(a)
            if a.workout_type in HARD_TYPES or bool(a.is_race_candidate):
                weekly_hard_counts[wk] = weekly_hard_counts.get(wk, 0) + 1
            ef = _ef(a)
            if ef is not None:
                weekly_efs.setdefault(wk, []).append(ef)

        # --- What works (scoped, non-universal) ---
        # Run-frequency association: compare weeks with >=4 runs vs <=3 runs, excluding very low-volume weeks.
        # This avoids claiming "4 runs/week = +4%" as a universal law; it's a within-history comparison.
        high_weeks: List[float] = []
        low_weeks: List[float] = []
        n_weeks_total = 0
        for wk, ef_list in weekly_efs.items():
            miles = weekly_miles.get(wk, 0.0)
            # Exclude near-zero weeks (often injury/off/travel) from "what works" claims.
            if miles < 5:
                continue
            if len(ef_list) < 2:
                continue
            n_weeks_total += 1
            weekly_median_ef = statistics.median(ef_list)
            rc = weekly_run_counts.get(wk, 0)
            if rc >= 4:
                high_weeks.append(weekly_median_ef)
            elif rc <= 3:
                low_weeks.append(weekly_median_ef)

        if len(high_weeks) >= 6 and len(low_weeks) >= 6:
            med_high = statistics.median(high_weeks)
            med_low = statistics.median(low_weeks)
            if med_low > 0:
                pct = ((med_high - med_low) / med_low) * 100.0
                direction = "higher" if pct >= 0 else "lower"
                intelligence.what_works.append(
                    {
                        "text": (
                            f"Run frequency (last ~{lookback_days//30} months): weeks with ≥4 runs had "
                            f"{abs(pct):.0f}% {direction} median efficiency vs weeks with ≤3 runs."
                        ),
                        "source": "n1",
                    }
                )

        # Volume baseline (descriptive, not prescriptive)
        # Use last 12 full weeks for a *current* profile without pretending it's a universal lever.
        last12 = _last_n_weeks(date.today(), 12)
        miles_12 = [weekly_miles.get(wk, 0.0) for wk in last12]
        runs_12 = [weekly_run_counts.get(wk, 0) for wk in last12]
        if any((m > 0) for m in miles_12):
            avg_miles_12 = statistics.mean(miles_12)
            med_runs_12 = statistics.median(runs_12) if runs_12 else 0
            weeks_4plus = sum(1 for r in runs_12 if r >= 4)
            min_miles_12 = min(miles_12) if miles_12 else 0.0
            max_miles_12 = max(miles_12) if miles_12 else 0.0

            # Put this in "what works" as a *measurable operating range*, not a claim of causality.
            intelligence.what_works.append(
                {
                    "text": (
                        f"Consistency (last 12w): ≥4 runs in {weeks_4plus}/12 weeks "
                        f"(median {med_runs_12:.1f} runs/week)."
                    ),
                    "source": "n1",
                }
            )
            intelligence.what_works.append(
                {
                    "text": f"Volume (last 12w): ~{avg_miles_12:.0f} mi/week average (range {min_miles_12:.0f}–{max_miles_12:.0f}).",
                    "source": "n1",
                }
            )

        # --- What doesn't work (detectable, data-backed flags) ---
        # 1) “Easy runs too hard” heuristic: non-race runs above 75% max HR.
        max_hr = float(self.athlete.max_hr or 185)
        easy_hr_threshold = max_hr * 0.75
        last_28_cutoff = now - timedelta(days=28)
        recent_28 = [a for a in runs if a.start_time >= last_28_cutoff]
        non_race_recent = [
            a for a in recent_28 if not a.is_race_candidate and (a.distance_m or 0) >= 3000 and a.avg_hr
        ]
        too_hard = [a for a in non_race_recent if a.avg_hr and float(a.avg_hr) > easy_hr_threshold]
        if len(non_race_recent) >= 6:
            frac = len(too_hard) / len(non_race_recent) if non_race_recent else 0.0
            if frac >= 0.5:
                intelligence.what_doesnt.append(
                    {
                        "text": (
                            f"Last 28 days: {len(too_hard)}/{len(non_race_recent)} non-race runs averaged "
                            f">{easy_hr_threshold:.0f} bpm (75% max HR). If those were meant to be easy, that’s a fatigue amplifier."
                        ),
                        "source": "n1",
                    }
                )

        # 2) Hard-session clustering: 2+ “hard” runs within 48 hours.
        hard_runs = [
            a
            for a in recent_28
            if (a.workout_type in HARD_TYPES or bool(a.is_race_candidate)) and (a.distance_m or 0) >= 3000
        ]
        hard_runs.sort(key=lambda a: a.start_time)
        clusters = 0
        for i in range(1, len(hard_runs)):
            if (hard_runs[i].start_time - hard_runs[i - 1].start_time).total_seconds() <= 48 * 3600:
                clusters += 1
        if clusters >= 1:
            intelligence.what_doesnt.append(
                {
                    "text": f"Last 28 days: {clusters} instance(s) of hard efforts within 48 hours. If you’re rebuilding, this is a common place to get hurt again.",
                    "source": "n1",
                }
            )

        # 3) Volatility: big week-to-week swings are a repeatable injury amplifier during returns.
        if len(miles_12) >= 8:
            miles_min = min(miles_12)
            miles_max = max(miles_12)
            if miles_max - miles_min >= 30:
                intelligence.what_doesnt.append(
                    {
                        "text": f"Last 12 weeks: weekly mileage swung {miles_min:.0f}→{miles_max:.0f} mi. Volatility like this is where injuries hide.",
                        "source": "n1",
                    }
                )
            low_weeks = sum(1 for r in runs_12 if r <= 2)
            if low_weeks >= 2:
                intelligence.what_doesnt.append(
                    {
                        "text": f"Last 12 weeks: {low_weeks} weeks with ≤2 runs. That’s a real disruption vs a steady base.",
                        "source": "n1",
                    }
                )

        # --- Injury risk patterns (detect “return to run” + ramp risk) ---
        # We don’t need “more data”; we need better signals. Use objective return-to-run markers.
        # 1) Detect a recent gap (proxy for injury/off)
        run_dates = [a.start_time.date() for a in runs]
        run_dates.sort()
        biggest_recent_gap = 0
        gap_end: Optional[date] = None
        for i in range(1, len(run_dates)):
            gap = (run_dates[i] - run_dates[i - 1]).days
            if run_dates[i] >= date.today() - timedelta(days=180) and gap > biggest_recent_gap:
                biggest_recent_gap = gap
                gap_end = run_dates[i]

        if biggest_recent_gap >= 10 and gap_end is not None:
            intelligence.injury_patterns.append(
                {
                    "text": f"Return-to-run flag: a {biggest_recent_gap}-day gap ended on {gap_end.isoformat()}. That usually marks injury/travel/off-cycle risk.",
                    "source": "n1",
                }
            )

        # 0) If your active plan is explicitly in rebuild, treat that as an injury-return context signal.
        active_plan = (
            self.db.query(TrainingPlan)
            .filter(
                TrainingPlan.athlete_id == self.athlete.id,
                TrainingPlan.status == "active",
            )
            .first()
        )
        if active_plan:
            # Look at nearby planned workouts for phase labels
            today = date.today()
            phases = (
                self.db.query(PlannedWorkout.phase)
                .filter(
                    PlannedWorkout.plan_id == active_plan.id,
                    PlannedWorkout.scheduled_date.between(today - timedelta(days=7), today + timedelta(days=14)),
                    PlannedWorkout.phase.isnot(None),
                )
                .all()
            )
            phase_set = {p[0] for p in phases if p and p[0]}
            if any(str(p).lower().startswith("rebuild") for p in phase_set):
                intelligence.injury_patterns.append(
                    {
                        "text": "Plan context: current phase is REBUILD. Treat everything as return-to-run until proven otherwise.",
                        "source": "n1",
                    }
                )

        # 2) Acute ramp: this week vs prior 4-week average
        # Use ISO weeks so it matches how athletes think about training weeks.
        last1 = _last_n_weeks(date.today(), 1)[0]
        prev4 = _last_n_weeks(date.today() - timedelta(days=7), 4)
        cur_miles = weekly_miles.get(last1, 0.0)
        prev4_miles = [weekly_miles.get(wk, 0.0) for wk in prev4]
        prev4_avg = statistics.mean(prev4_miles) if prev4_miles else 0.0
        if prev4_avg >= 5 and cur_miles >= prev4_avg * 1.35:
            intelligence.injury_patterns.append(
                {
                    "text": f"Ramp flag: this week is {cur_miles:.0f} mi vs prior-4wk avg {prev4_avg:.0f} mi/week (+{((cur_miles/prev4_avg)-1)*100:.0f}%).",
                    "source": "n1",
                }
            )

        # If we detected no injury flags at all, be explicit (true negative) instead of “need more history”.
        if not intelligence.injury_patterns:
            intelligence.injury_patterns.append(
                {
                    "text": "In the last 6 months, no obvious gap/ramp/stacking flags triggered from your run history.",
                    "source": "n1",
                }
            )

        return intelligence
    
    def persist_insights(self, insights: List[GeneratedInsight]) -> int:
        """
        Persist generated insights to the database.
        
        For activity-linked insights: dedup by (athlete, date, type, activity_id).
        For rolling-stat insights (no activity): dedup by (athlete, date, type)
        and UPDATE existing rows so stale numbers don't accumulate.
        
        Returns number of insights saved or updated.
        """
        saved = 0
        
        for insight in insights:
            # Safety: ensure insight_date is never None before DB write
            if insight.insight_date is None:
                insight.insight_date = date.today()
            
            # Build the dedup query — activity-linked insights match on activity_id too,
            # rolling-stat insights match only on (athlete, date, type) so updated
            # numbers replace old rows instead of piling up.
            filters = [
                CalendarInsight.athlete_id == self.athlete.id,
                CalendarInsight.insight_date == insight.insight_date,
                CalendarInsight.insight_type == insight.insight_type.value,
            ]
            if insight.activity_id:
                filters.append(CalendarInsight.activity_id == insight.activity_id)
            else:
                filters.append(CalendarInsight.activity_id.is_(None))
            
            existing = self.db.query(CalendarInsight).filter(*filters).first()
            
            if existing:
                # Update in place — title/content/data may have changed
                existing.title = insight.title
                existing.content = insight.content
                existing.priority = insight.priority
                existing.generation_data = insight.data
                saved += 1
            else:
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
