"""
Calendar Signals Service

Provides day-level badges and week-level trajectory summaries
for calendar visualization.

ADR-016: Calendar Signals - Day Badges + Week Trajectory

Design Principles:
- Scannable: Quick visual badges, not clutter
- Confidence-filtered: Only high/moderate signals
- Mobile-first: Compact but tappable
- Sparse tone: Non-prescriptive
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Any
from enum import Enum
from uuid import UUID
import logging

from sqlalchemy.orm import Session
from sqlalchemy import and_

from models import Activity, DailyCheckin, PersonalBest

logger = logging.getLogger(__name__)


class SignalType(str, Enum):
    """Types of calendar signals."""
    EFFICIENCY_SPIKE = "efficiency_spike"
    EFFICIENCY_DROP = "efficiency_drop"
    DECAY_RISK = "decay_risk"
    EVEN_PACING = "even_pacing"
    PR_MATCH = "pr_match"
    FRESH_FORM = "fresh_form"
    FATIGUED = "fatigued"
    AT_CS = "at_cs"
    PERSONAL_BEST = "personal_best"


class SignalConfidence(str, Enum):
    """Confidence levels."""
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


class TrajectoryTrend(str, Enum):
    """Week trajectory trends."""
    POSITIVE = "positive"
    CAUTION = "caution"
    NEUTRAL = "neutral"


@dataclass
class DayBadge:
    """A badge for a calendar day."""
    type: str
    badge: str
    color: str
    icon: str
    confidence: str
    tooltip: str
    priority: int = 5


@dataclass
class WeekTrajectory:
    """Trajectory summary for a week."""
    summary: str
    trend: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CalendarSignalsResponse:
    """Complete calendar signals response."""
    day_signals: Dict[str, List[DayBadge]]
    week_trajectories: Dict[str, WeekTrajectory]


# Maximum badges per day
MAX_BADGES_PER_DAY = 2


def get_efficiency_badge(
    athlete_id: str,
    activity_date: date,
    db: Session
) -> Optional[DayBadge]:
    """
    Check if efficiency for this day is notably different from average.
    """
    try:
        # Get activities for this day
        activities = db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= datetime.combine(activity_date, datetime.min.time()),
            Activity.start_time < datetime.combine(activity_date + timedelta(days=1), datetime.min.time()),
            Activity.avg_hr.isnot(None),
            Activity.avg_hr > 100,
            Activity.distance_m > 1000,
            Activity.duration_s > 0
        ).all()
        
        if not activities:
            return None
        
        # Calculate average efficiency for the day
        day_efficiencies = []
        for act in activities:
            pace = act.duration_s / (act.distance_m / 1000)
            eff = pace / act.avg_hr
            day_efficiencies.append(eff)
        
        if not day_efficiencies:
            return None
        
        day_avg_eff = sum(day_efficiencies) / len(day_efficiencies)
        
        # Get 28-day average for comparison
        start_28 = activity_date - timedelta(days=28)
        recent = db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= datetime.combine(start_28, datetime.min.time()),
            Activity.start_time < datetime.combine(activity_date, datetime.min.time()),
            Activity.avg_hr.isnot(None),
            Activity.avg_hr > 100,
            Activity.distance_m > 1000,
            Activity.duration_s > 0
        ).all()
        
        if len(recent) < 5:
            return None
        
        recent_efficiencies = []
        for act in recent:
            pace = act.duration_s / (act.distance_m / 1000)
            eff = pace / act.avg_hr
            recent_efficiencies.append(eff)
        
        avg_28 = sum(recent_efficiencies) / len(recent_efficiencies)
        
        # Calculate difference (pace/HR ratio — directionally ambiguous, see OutputMetricMeta)
        diff_pct = ((day_avg_eff - avg_28) / avg_28) * 100
        
        # Efficiency (pace/HR) is directionally ambiguous — show neutral
        # "notable change" badge without claiming better/worse.
        # See Athlete Trust Safety Contract in n1_insight_generator.py.
        if abs(diff_pct) > 5:
            return DayBadge(
                type=SignalType.EFFICIENCY_SPIKE.value,
                badge="Eff Δ",
                color="blue",
                icon="activity",
                confidence=SignalConfidence.HIGH.value if abs(diff_pct) > 8 else SignalConfidence.MODERATE.value,
                tooltip=f"Efficiency {abs(diff_pct):.0f}% different from 28-day average",
                priority=3
            )
        
        return None
        
    except Exception as e:
        logger.warning(f"Error getting efficiency badge: {e}")
        return None


def get_pace_decay_badge(
    athlete_id: str,
    activity_date: date,
    db: Session
) -> Optional[DayBadge]:
    """
    Check for pace decay patterns in long runs or races.
    """
    try:
        from services.pace_decay import get_athlete_decay_profile
        from models import ActivitySplit
        
        # Get activities for this day
        activities = db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= datetime.combine(activity_date, datetime.min.time()),
            Activity.start_time < datetime.combine(activity_date + timedelta(days=1), datetime.min.time()),
            Activity.distance_m >= 8000  # 8km+ for meaningful decay
        ).all()
        
        if not activities:
            return None
        
        for activity in activities:
            # Get splits
            splits = db.query(ActivitySplit).filter(
                ActivitySplit.activity_id == activity.id
            ).order_by(ActivitySplit.split_number).all()
            
            if len(splits) < 3:
                continue
            
            # Calculate decay
            split_paces = []
            for s in splits:
                if s.distance_m and s.elapsed_time_s and s.elapsed_time_s > 0:
                    pace = s.elapsed_time_s / (s.distance_m / 1000)
                    split_paces.append(pace)
            
            if len(split_paces) < 3:
                continue
            
            first_half = split_paces[:len(split_paces)//2]
            second_half = split_paces[len(split_paces)//2:]
            
            avg_first = sum(first_half) / len(first_half)
            avg_second = sum(second_half) / len(second_half)
            
            decay_pct = ((avg_second - avg_first) / avg_first) * 100 if avg_first > 0 else 0
            
            if decay_pct > 8:
                return DayBadge(
                    type=SignalType.DECAY_RISK.value,
                    badge="Fade",
                    color="orange",
                    icon="trending_down",
                    confidence=SignalConfidence.HIGH.value if decay_pct > 12 else SignalConfidence.MODERATE.value,
                    tooltip=f"Pace faded {decay_pct:.0f}% — more than typical",
                    priority=2
                )
            elif decay_pct < -2:
                return DayBadge(
                    type=SignalType.EVEN_PACING.value,
                    badge="Even",
                    color="green",
                    icon="check",
                    confidence=SignalConfidence.HIGH.value,
                    tooltip=f"Negative split — strong finish",
                    priority=3
                )
            elif decay_pct <= 3:
                return DayBadge(
                    type=SignalType.EVEN_PACING.value,
                    badge="Even",
                    color="green",
                    icon="check",
                    confidence=SignalConfidence.MODERATE.value,
                    tooltip=f"Even pacing — controlled execution",
                    priority=4
                )
        
        return None
        
    except Exception as e:
        logger.warning(f"Error getting pace decay badge: {e}")
        return None


def get_tsb_badge(
    athlete_id: str,
    activity_date: date,
    db: Session
) -> Optional[DayBadge]:
    """
    Check TSB status for the day.
    """
    try:
        from services.training_load import TrainingLoadCalculator, TSBZone
        
        calculator = TrainingLoadCalculator(db)
        athlete_uuid = UUID(athlete_id)
        load = calculator.calculate_training_load(athlete_uuid)
        
        if not load or load.current_ctl < 20:
            return None
        
        tsb = load.current_tsb
        zone_info = calculator.get_tsb_zone(tsb, athlete_id=athlete_uuid)
        
        if zone_info.zone == TSBZone.RACE_READY:
            return DayBadge(
                type=SignalType.FRESH_FORM.value,
                badge="Fresh",
                color="blue",
                icon="zap",
                confidence=SignalConfidence.HIGH.value,
                tooltip=f"TSB +{int(tsb)} — race-ready zone",
                priority=3
            )
        elif zone_info.zone == TSBZone.OVERREACHING:
            return DayBadge(
                type=SignalType.FATIGUED.value,
                badge="Load",
                color="yellow",
                icon="alert_triangle",
                confidence=SignalConfidence.MODERATE.value,
                tooltip=f"TSB {int(tsb)} — building fatigue",
                priority=4
            )
        elif zone_info.zone == TSBZone.OVERTRAINING_RISK:
            return DayBadge(
                type=SignalType.FATIGUED.value,
                badge="Tired",
                color="orange",
                icon="alert_circle",
                confidence=SignalConfidence.HIGH.value,
                tooltip=f"TSB {int(tsb)} — high fatigue",
                priority=2
            )
        
        return None
        
    except Exception as e:
        logger.warning(f"Error getting TSB badge: {e}")
        return None


def get_pr_match_badge(
    athlete_id: str,
    activity_date: date,
    db: Session
) -> Optional[DayBadge]:
    """
    Check if pre-run state matches PR fingerprint.
    """
    try:
        from services.pre_race_fingerprinting import generate_readiness_profile
        
        # Check for check-in on this day
        checkin = db.query(DailyCheckin).filter(
            DailyCheckin.athlete_id == athlete_id,
            DailyCheckin.date == activity_date
        ).first()
        
        if not checkin:
            return None
        
        profile = generate_readiness_profile(athlete_id, db)
        
        if not profile or profile.confidence_level == "insufficient":
            return None
        
        # Count how many optimal-range features this day matches
        match_count = 0
        total_features = len(profile.optimal_ranges)
        if total_features == 0:
            return None
        
        # Check sleep against optimal range
        if "Sleep Hours" in profile.optimal_ranges and checkin.sleep_h is not None:
            lo, hi = profile.optimal_ranges["Sleep Hours"]
            if lo <= float(checkin.sleep_h) <= hi:
                match_count += 1
        
        match_pct = (match_count / max(total_features, 1)) * 100
        
        if match_pct >= 80:
            return DayBadge(
                type=SignalType.PR_MATCH.value,
                badge="PR ✓",
                color="purple",
                icon="target",
                confidence=SignalConfidence.HIGH.value,
                tooltip=f"State matches PR fingerprint ({int(match_pct)}%)",
                priority=1
            )
        elif match_pct >= 50:
            return DayBadge(
                type=SignalType.PR_MATCH.value,
                badge="Ready",
                color="blue",
                icon="target",
                confidence=SignalConfidence.MODERATE.value,
                tooltip=f"Good readiness match ({int(match_pct)}%)",
                priority=3
            )
        
        return None
        
    except Exception as e:
        logger.warning(f"Error getting PR match badge: {e}")
        return None


def get_personal_best_badge(
    athlete_id: str,
    activity_date: date,
    db: Session
) -> Optional[DayBadge]:
    """
    Check if any activity on this day is a personal best.
    
    Looks up the PersonalBest table to see if any PB has an activity
    from this date.
    """
    try:
        # Get activities for this day
        activities = db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= datetime.combine(activity_date, datetime.min.time()),
            Activity.start_time < datetime.combine(activity_date + timedelta(days=1), datetime.min.time())
        ).all()
        
        if not activities:
            return None
        
        # Check if any activity is linked to a PersonalBest
        activity_ids = [a.id for a in activities]
        
        pbs = db.query(PersonalBest).filter(
            PersonalBest.activity_id.in_(activity_ids)
        ).all()
        
        if not pbs:
            return None
        
        # Get the most significant PB (shortest distance = more valuable in running culture)
        # Order: 5K > 10K > Half > Marathon > others
        distance_priority = {
            '5k': 1, '10k': 2, 'half_marathon': 3, 'marathon': 4,
            'mile': 0, '1k': 0, '2mile': 1  # Mile is also a prestigious distance
        }
        
        best_pb = min(pbs, key=lambda p: (
            distance_priority.get(p.distance_category.lower(), 10),
            p.distance_meters
        ))
        
        # Format distance for display
        category = best_pb.distance_category.replace('_', ' ').upper()
        if category == 'HALF MARATHON':
            category = 'HALF'
        elif category == '5K':
            category = '5K'
        elif category == '10K':
            category = '10K'
        
        return DayBadge(
            type=SignalType.PERSONAL_BEST.value,
            badge=f"PB {category}",
            color="purple",
            icon="zap",
            confidence=SignalConfidence.HIGH.value,
            tooltip=f"Personal Best: {best_pb.distance_category.replace('_', ' ').title()}",
            priority=0  # Highest priority - PBs should always show
        )
        
    except Exception as e:
        logger.warning(f"Error getting personal best badge: {e}")
        return None


def get_day_badges(
    athlete_id: str,
    activity_date: date,
    db: Session
) -> List[DayBadge]:
    """
    Get all badges for a single day.
    
    Filters by confidence and limits to MAX_BADGES_PER_DAY.
    
    Note: TSB/Load badges are intentionally NOT included here.
    Training load is normal daily state, not an exception worth badging.
    Load info is available in the day detail panel and week trajectory.
    Badges should highlight exceptions, not the norm.
    """
    badges: List[DayBadge] = []
    
    # Collect from all sources
    # PB badge first (highest priority)
    pb_badge = get_personal_best_badge(athlete_id, activity_date, db)
    if pb_badge:
        badges.append(pb_badge)
    
    eff_badge = get_efficiency_badge(athlete_id, activity_date, db)
    if eff_badge:
        badges.append(eff_badge)
    
    decay_badge = get_pace_decay_badge(athlete_id, activity_date, db)
    if decay_badge:
        badges.append(decay_badge)
    
    # NOTE: TSB badge intentionally removed from calendar view.
    # Load status is normal training state, not an exception.
    # Available in: day detail panel, week trajectory, analytics.
    
    pr_badge = get_pr_match_badge(athlete_id, activity_date, db)
    if pr_badge:
        badges.append(pr_badge)
    
    # Filter by confidence
    filtered = [b for b in badges if b.confidence in [SignalConfidence.HIGH.value, SignalConfidence.MODERATE.value]]
    
    # Sort by priority (lower = more important)
    filtered.sort(key=lambda b: (b.priority, b.confidence != SignalConfidence.HIGH.value))
    
    # Limit
    return filtered[:MAX_BADGES_PER_DAY]


def get_week_trajectory(
    athlete_id: str,
    week_start: date,
    db: Session
) -> Optional[WeekTrajectory]:
    """
    Generate trajectory summary for a week.
    """
    try:
        week_end = week_start + timedelta(days=6)
        
        # Get activities for the week
        activities = db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= datetime.combine(week_start, datetime.min.time()),
            Activity.start_time < datetime.combine(week_end + timedelta(days=1), datetime.min.time())
        ).all()
        
        if not activities:
            return None
        
        # Collect metrics
        details: Dict[str, Any] = {}
        signals: List[str] = []
        trend = TrajectoryTrend.NEUTRAL
        
        # Check efficiency trend
        try:
            from services.efficiency_analytics import get_efficiency_trends
            
            eff_result = get_efficiency_trends(athlete_id, db, days=14)
            # Efficiency (pace/HR) is directionally ambiguous — report
            # change magnitude without claiming positive/negative direction.
            # See Athlete Trust Safety Contract in n1_insight_generator.py.
            if eff_result and hasattr(eff_result, 'trend_direction'):
                if eff_result.trend_direction in ('improving', 'declining'):
                    change = getattr(eff_result, 'percentage_change', 0)
                    details['efficiency_trend'] = f"{change:+.1f}%"
                    signals.append(f"efficiency shifted {abs(change):.1f}%")
                    # Do NOT set trend to POSITIVE or CAUTION based on
                    # ambiguous efficiency direction
        except Exception:
            pass
        
        # Check TSB (personalized zones for this athlete)
        try:
            from services.training_load import TrainingLoadCalculator, TSBZone
            
            calculator = TrainingLoadCalculator(db)
            athlete_uuid = UUID(athlete_id)
            load = calculator.calculate_training_load(athlete_uuid)
            
            if load and load.current_ctl >= 20:
                zone_info = calculator.get_tsb_zone(load.current_tsb, athlete_id=athlete_uuid)
                details['tsb_zone'] = zone_info.zone.value
                
                if zone_info.zone == TSBZone.RACE_READY:
                    signals.append("fresh and fit")
                    trend = TrajectoryTrend.POSITIVE
                elif zone_info.zone == TSBZone.OVERREACHING:
                    signals.append("building load")
                    if trend != TrajectoryTrend.POSITIVE:
                        trend = TrajectoryTrend.CAUTION
                elif zone_info.zone == TSBZone.OVERTRAINING_RISK:
                    signals.append("high fatigue")
                    trend = TrajectoryTrend.CAUTION
        except Exception:
            pass
        
        # Count quality sessions
        quality_types = {'threshold', 'tempo', 'intervals', 'vo2max', 'speed', 'race'}
        quality_count = sum(1 for a in activities if a.workout_type and a.workout_type.lower() in quality_types)
        if quality_count > 0:
            details['quality_sessions'] = quality_count
        
        # Check consistency
        days_with_runs = len(set(a.start_time.date() for a in activities))
        if days_with_runs >= 5:
            signals.append("consistency strong")
            if trend == TrajectoryTrend.NEUTRAL:
                trend = TrajectoryTrend.POSITIVE
        
        # Generate summary sentence
        if not signals:
            summary = "No significant signals this week."
        elif trend == TrajectoryTrend.POSITIVE:
            summary = f"On track — {signals[0]}."
        elif trend == TrajectoryTrend.CAUTION:
            summary = f"Watch fatigue — {signals[0]}."
        else:
            summary = f"Building week — {signals[0]}."
        
        return WeekTrajectory(
            summary=summary,
            trend=trend.value,
            details=details
        )
        
    except Exception as e:
        logger.warning(f"Error getting week trajectory: {e}")
        return None


def get_calendar_signals(
    athlete_id: str,
    start_date: date,
    end_date: date,
    db: Session
) -> CalendarSignalsResponse:
    """
    Main function: Get all signals for a date range.
    
    Args:
        athlete_id: Athlete UUID string
        start_date: Start of range
        end_date: End of range
        db: Database session
    
    Returns:
        CalendarSignalsResponse with day_signals and week_trajectories
    """
    day_signals: Dict[str, List[DayBadge]] = {}
    week_trajectories: Dict[str, WeekTrajectory] = {}
    
    # Get day badges for each day with activities
    current = start_date
    while current <= end_date:
        badges = get_day_badges(athlete_id, current, db)
        if badges:
            day_signals[current.isoformat()] = badges
        current += timedelta(days=1)
    
    # Get week trajectories
    # Find all week starts in range
    week_start = start_date - timedelta(days=start_date.weekday())  # Monday
    while week_start <= end_date:
        week_end = week_start + timedelta(days=6)
        if week_end >= start_date:  # Week overlaps our range
            trajectory = get_week_trajectory(athlete_id, week_start, db)
            if trajectory:
                week_key = f"{week_start.isocalendar()[0]}-W{week_start.isocalendar()[1]:02d}"
                week_trajectories[week_key] = trajectory
        week_start += timedelta(days=7)
    
    return CalendarSignalsResponse(
        day_signals=day_signals,
        week_trajectories=week_trajectories
    )


def calendar_signals_to_dict(response: CalendarSignalsResponse) -> Dict[str, Any]:
    """Convert CalendarSignalsResponse to dictionary for API response."""
    return {
        "day_signals": {
            date_str: [
                {
                    "type": b.type,
                    "badge": b.badge,
                    "color": b.color,
                    "icon": b.icon,
                    "confidence": b.confidence,
                    "tooltip": b.tooltip
                }
                for b in badges
            ]
            for date_str, badges in response.day_signals.items()
        },
        "week_trajectories": {
            week_key: {
                "summary": t.summary,
                "trend": t.trend,
                "details": t.details
            }
            for week_key, t in response.week_trajectories.items()
        }
    }
