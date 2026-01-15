"""
Anchor Finder (ADR-033)

Finds dynamic, history-specific anchors for narrative generation.

The key insight: Templates can repeat, but anchors make each sentence unique.
"You bounced back fast" is stale. 
"You bounced back from Dec 15 faster than April" is specific to this athlete, this moment.

Anchors come from:
- Specific dates (workouts, races, injuries)
- Comparable events (similar TSB, same workout structure, same route)
- Historical patterns (prior rebuilds, seasonal trends)
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple
from uuid import UUID
import logging

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from models import Activity, Athlete

logger = logging.getLogger(__name__)


# =============================================================================
# ANCHOR DATA CLASSES
# =============================================================================

@dataclass
class InjuryReboundAnchor:
    """A prior injury → rebound pattern."""
    injury_date: date
    rebound_date: date
    weeks_to_recover: int
    peak_volume_before: float
    volume_at_rebound: float
    recovery_pct: float


@dataclass
class WorkoutAnchor:
    """A prior workout with similar structure."""
    activity_id: UUID
    date: date
    name: str
    workout_type: str
    pace_per_mile: Optional[float]
    following_race: Optional[str]  # Race within 3 weeks of this workout
    days_to_race: Optional[int]


@dataclass
class EfficiencyAnchor:
    """An efficiency outlier (best or worst)."""
    activity_id: UUID
    date: date
    name: str
    efficiency_score: float  # pace:HR ratio
    delta_from_baseline: float  # % difference from 28-day average
    direction: str  # "high" or "low"


@dataclass
class LoadStateAnchor:
    """A prior day with similar TSB/CTL state."""
    date: date
    tsb: float
    ctl: float
    following_workout_type: Optional[str]
    following_workout_quality: Optional[str]  # "good", "bad", "normal"


@dataclass
class RaceAnchor:
    """A prior race performance."""
    date: date
    name: str
    distance: str
    finish_time_seconds: int
    pace_per_mile: float
    conditions: Optional[str]
    tsb_at_race: Optional[float]
    ctl_at_race: Optional[float]


@dataclass
class MilestoneAnchor:
    """A comparable milestone in training history."""
    date: date
    week_number: int  # Week N of that build cycle
    weekly_miles: float
    following_race: Optional[str]
    days_to_race: Optional[int]


# =============================================================================
# ANCHOR FINDER
# =============================================================================

class AnchorFinder:
    """
    Finds dynamic anchors from athlete history.
    
    These anchors make narratives specific and fresh:
    - "Last Tuesday" instead of "recently"
    - "The Dec 15 strain" instead of "your injury"
    - "Before Philly" instead of "before a race"
    """
    
    def __init__(self, db: Session, athlete_id: UUID):
        self.db = db
        self.athlete_id = athlete_id
    
    # =========================================================================
    # INJURY REBOUND
    # =========================================================================
    
    def find_previous_injury_rebound(
        self,
        current_injury_start: Optional[date] = None,
        lookback_days: int = 365
    ) -> Optional[InjuryReboundAnchor]:
        """
        Find a prior injury → rebound pattern to compare against current state.
        
        Injury detection: Sharp volume drop (>50%) sustained for 2+ weeks.
        Rebound: Return to 70%+ of prior peak.
        """
        today = date.today()
        start_date = today - timedelta(days=lookback_days)
        
        # Get weekly volumes
        activities = self.db.query(Activity).filter(
            Activity.athlete_id == self.athlete_id,
            Activity.start_time >= datetime.combine(start_date, datetime.min.time()),
            Activity.sport.ilike("run")
        ).order_by(Activity.start_time).all()
        
        if len(activities) < 20:
            return None
        
        # Calculate weekly volumes
        weekly_volumes = {}
        for a in activities:
            week_start = a.start_time.date() - timedelta(days=a.start_time.weekday())
            if week_start not in weekly_volumes:
                weekly_volumes[week_start] = 0
            weekly_volumes[week_start] += (a.distance_m or 0) / 1609.344
        
        sorted_weeks = sorted(weekly_volumes.keys())
        if len(sorted_weeks) < 8:
            return None
        
        # Find injury patterns (sharp drop followed by rebound)
        rebounds = []
        
        for i in range(4, len(sorted_weeks) - 4):
            # Pre-injury average (4 weeks before)
            pre_injury_avg = sum(weekly_volumes.get(sorted_weeks[j], 0) for j in range(i-4, i)) / 4
            
            if pre_injury_avg < 20:  # Not enough baseline
                continue
            
            # Check for sharp drop
            drop_week = sorted_weeks[i]
            drop_volume = weekly_volumes.get(drop_week, 0)
            
            if drop_volume > pre_injury_avg * 0.5:  # Not a sharp drop
                continue
            
            # Check if drop sustained (next week also low)
            if i + 1 < len(sorted_weeks):
                next_volume = weekly_volumes.get(sorted_weeks[i + 1], 0)
                if next_volume > pre_injury_avg * 0.5:
                    continue
            
            # Find rebound (return to 70%+)
            for j in range(i + 2, min(i + 12, len(sorted_weeks))):
                rebound_volume = weekly_volumes.get(sorted_weeks[j], 0)
                if rebound_volume >= pre_injury_avg * 0.7:
                    rebounds.append(InjuryReboundAnchor(
                        injury_date=drop_week,
                        rebound_date=sorted_weeks[j],
                        weeks_to_recover=j - i,
                        peak_volume_before=pre_injury_avg,
                        volume_at_rebound=rebound_volume,
                        recovery_pct=rebound_volume / pre_injury_avg
                    ))
                    break
        
        # Skip the current injury if specified
        if current_injury_start and rebounds:
            rebounds = [r for r in rebounds if r.injury_date < current_injury_start - timedelta(days=30)]
        
        # Return most recent prior rebound
        if rebounds:
            return sorted(rebounds, key=lambda r: r.injury_date, reverse=True)[0]
        
        return None
    
    # =========================================================================
    # SIMILAR WORKOUT
    # =========================================================================
    
    def find_similar_workout(
        self,
        workout_type: str,
        target_pace: Optional[float] = None,
        lookback_days: int = 180
    ) -> Optional[WorkoutAnchor]:
        """
        Find a prior workout with similar structure.
        
        Matches on workout_type and optionally pace range.
        Prioritizes workouts followed by good races.
        """
        today = date.today()
        start_date = today - timedelta(days=lookback_days)
        
        # Query similar workouts
        query = self.db.query(Activity).filter(
            Activity.athlete_id == self.athlete_id,
            Activity.start_time >= datetime.combine(start_date, datetime.min.time()),
            Activity.start_time < datetime.combine(today - timedelta(days=7), datetime.min.time()),  # Not too recent
            Activity.workout_type == workout_type
        ).order_by(Activity.start_time.desc())
        
        activities = query.limit(20).all()
        
        if not activities:
            return None
        
        # Find races that followed these workouts
        anchors = []
        for a in activities:
            # Look for race within 3 weeks after this workout
            race_window_start = a.start_time.date()
            race_window_end = race_window_start + timedelta(days=21)
            
            following_race = self.db.query(Activity).filter(
                Activity.athlete_id == self.athlete_id,
                Activity.start_time >= datetime.combine(race_window_start, datetime.min.time()),
                Activity.start_time <= datetime.combine(race_window_end, datetime.min.time()),
                or_(
                    Activity.workout_type == "race",
                    Activity.is_race_candidate == True
                )
            ).first()
            
            race_name = None
            days_to_race = None
            if following_race:
                race_name = following_race.name or f"{(following_race.distance_m or 0) / 1000:.0f}K race"
                days_to_race = (following_race.start_time.date() - a.start_time.date()).days
            
            anchors.append(WorkoutAnchor(
                activity_id=a.id,
                date=a.start_time.date(),
                name=a.name or workout_type,
                workout_type=workout_type,
                pace_per_mile=a.pace_per_mile,
                following_race=race_name,
                days_to_race=days_to_race
            ))
        
        # Prioritize workouts followed by races
        anchors_with_race = [a for a in anchors if a.following_race]
        if anchors_with_race:
            return anchors_with_race[0]
        
        # Otherwise return most recent
        return anchors[0] if anchors else None
    
    # =========================================================================
    # EFFICIENCY OUTLIER
    # =========================================================================
    
    def find_efficiency_outlier(
        self,
        direction: str = "high",
        lookback_days: int = 60
    ) -> Optional[EfficiencyAnchor]:
        """
        Find best (or worst) efficiency day in lookback period.
        
        Efficiency = pace / HR (lower pace at same HR = better)
        """
        today = date.today()
        start_date = today - timedelta(days=lookback_days)
        
        # Get activities with HR data
        activities = self.db.query(Activity).filter(
            Activity.athlete_id == self.athlete_id,
            Activity.start_time >= datetime.combine(start_date, datetime.min.time()),
            Activity.sport.ilike("run"),
            Activity.avg_hr.isnot(None),
            Activity.avg_hr > 100,
            Activity.average_speed.isnot(None),
            Activity.distance_m > 3000  # At least 3K
        ).all()
        
        if len(activities) < 5:
            return None
        
        # Calculate efficiency for each
        efficiencies = []
        for a in activities:
            if a.avg_hr and a.average_speed and float(a.average_speed) > 0:
                # Efficiency = speed / HR (higher = better, faster at lower HR)
                eff = float(a.average_speed) / a.avg_hr * 1000
                efficiencies.append((a, eff))
        
        if len(efficiencies) < 5:
            return None
        
        # Calculate baseline (mean)
        baseline = sum(e[1] for e in efficiencies) / len(efficiencies)
        
        # Sort by efficiency
        sorted_eff = sorted(efficiencies, key=lambda x: x[1], reverse=(direction == "high"))
        
        best = sorted_eff[0]
        activity, eff = best
        delta = (eff - baseline) / baseline * 100
        
        return EfficiencyAnchor(
            activity_id=activity.id,
            date=activity.start_time.date(),
            name=activity.name or "run",
            efficiency_score=eff,
            delta_from_baseline=delta,
            direction=direction
        )
    
    # =========================================================================
    # COMPARABLE LOAD STATE
    # =========================================================================
    
    def find_comparable_load_state(
        self,
        target_tsb: float,
        tolerance: float = 5.0,
        lookback_days: int = 180
    ) -> Optional[LoadStateAnchor]:
        """
        Find a prior day with similar TSB.
        
        Useful for: "You're coiled like {date}. That day you felt light."
        """
        from services.training_load import TrainingLoadCalculator
        
        today = date.today()
        
        # Calculate TSB for past days
        load_calc = TrainingLoadCalculator(self.db)
        
        matches = []
        for days_ago in range(14, lookback_days):  # Skip recent 2 weeks
            check_date = today - timedelta(days=days_ago)
            try:
                load = load_calc.calculate_training_load(self.athlete_id, check_date)
                if abs(load.current_tsb - target_tsb) <= tolerance:
                    # Find what workout followed this day
                    following = self.db.query(Activity).filter(
                        Activity.athlete_id == self.athlete_id,
                        Activity.start_time >= datetime.combine(check_date, datetime.min.time()),
                        Activity.start_time < datetime.combine(check_date + timedelta(days=2), datetime.min.time()),
                        Activity.sport.ilike("run")
                    ).first()
                    
                    matches.append(LoadStateAnchor(
                        date=check_date,
                        tsb=load.current_tsb,
                        ctl=load.current_ctl,
                        following_workout_type=following.workout_type if following else None,
                        following_workout_quality=None  # Could enhance later
                    ))
            except Exception:
                continue
            
            if len(matches) >= 3:
                break
        
        return matches[0] if matches else None
    
    # =========================================================================
    # PRIOR RACE AT SIMILAR LOAD
    # =========================================================================
    
    def find_prior_race_at_load(
        self,
        target_ctl: float,
        target_tsb: float,
        ctl_tolerance: float = 10.0,
        tsb_tolerance: float = 10.0
    ) -> Optional[RaceAnchor]:
        """
        Find a prior race performed at similar CTL/TSB.
        
        Useful for: "TSB is as high as before {race}."
        """
        from services.training_load import TrainingLoadCalculator
        
        # Get race candidates
        races = self.db.query(Activity).filter(
            Activity.athlete_id == self.athlete_id,
            or_(
                Activity.workout_type == "race",
                Activity.is_race_candidate == True
            )
        ).order_by(Activity.start_time.desc()).limit(20).all()
        
        if not races:
            return None
        
        load_calc = TrainingLoadCalculator(self.db)
        
        for race in races:
            race_date = race.start_time.date()
            try:
                load = load_calc.calculate_training_load(self.athlete_id, race_date)
                
                if (abs(load.current_ctl - target_ctl) <= ctl_tolerance and 
                    abs(load.current_tsb - target_tsb) <= tsb_tolerance):
                    
                    # Calculate pace
                    pace = None
                    if race.duration_s and race.distance_m and race.distance_m > 0:
                        pace = (race.duration_s / 60) / (race.distance_m / 1609.344)
                    
                    # Infer distance
                    dist_m = race.distance_m or 0
                    if 4800 <= dist_m <= 5200:
                        distance = "5K"
                    elif 9800 <= dist_m <= 10200:
                        distance = "10K"
                    elif 20900 <= dist_m <= 21300:
                        distance = "half"
                    elif 42000 <= dist_m <= 42500:
                        distance = "marathon"
                    else:
                        distance = f"{dist_m / 1000:.1f}K"
                    
                    return RaceAnchor(
                        date=race_date,
                        name=race.name or f"{distance} race",
                        distance=distance,
                        finish_time_seconds=race.duration_s or 0,
                        pace_per_mile=pace or 0,
                        conditions=None,
                        tsb_at_race=load.current_tsb,
                        ctl_at_race=load.current_ctl
                    )
            except Exception:
                continue
        
        return None
    
    # =========================================================================
    # MILESTONE COMPARISON
    # =========================================================================
    
    def find_similar_milestone(
        self,
        current_weekly_miles: float,
        tolerance_pct: float = 0.15
    ) -> Optional[MilestoneAnchor]:
        """
        Find a prior point where weekly mileage was similar.
        
        Useful for: "You're at the same mileage as Week 4 before Boston."
        """
        today = date.today()
        
        # Get weekly volumes for past year
        activities = self.db.query(Activity).filter(
            Activity.athlete_id == self.athlete_id,
            Activity.start_time >= datetime.combine(today - timedelta(days=365), datetime.min.time()),
            Activity.start_time < datetime.combine(today - timedelta(days=30), datetime.min.time()),
            Activity.sport.ilike("run")
        ).all()
        
        if not activities:
            return None
        
        # Calculate weekly volumes
        weekly_volumes = {}
        for a in activities:
            week_start = a.start_time.date() - timedelta(days=a.start_time.weekday())
            if week_start not in weekly_volumes:
                weekly_volumes[week_start] = 0
            weekly_volumes[week_start] += (a.distance_m or 0) / 1609.344
        
        # Find weeks with similar volume
        matches = []
        lower = current_weekly_miles * (1 - tolerance_pct)
        upper = current_weekly_miles * (1 + tolerance_pct)
        
        for week, volume in weekly_volumes.items():
            if lower <= volume <= upper:
                # Look for race within 8 weeks after
                race_window_end = week + timedelta(days=56)
                following_race = self.db.query(Activity).filter(
                    Activity.athlete_id == self.athlete_id,
                    Activity.start_time >= datetime.combine(week, datetime.min.time()),
                    Activity.start_time <= datetime.combine(race_window_end, datetime.min.time()),
                    or_(
                        Activity.workout_type == "race",
                        Activity.is_race_candidate == True
                    )
                ).first()
                
                race_name = None
                days_to_race = None
                if following_race:
                    race_name = following_race.name
                    days_to_race = (following_race.start_time.date() - week).days
                
                matches.append(MilestoneAnchor(
                    date=week,
                    week_number=0,  # Would need cycle detection to set properly
                    weekly_miles=volume,
                    following_race=race_name,
                    days_to_race=days_to_race
                ))
        
        # Prefer matches followed by races
        matches_with_race = [m for m in matches if m.following_race]
        if matches_with_race:
            return sorted(matches_with_race, key=lambda m: m.date, reverse=True)[0]
        
        return sorted(matches, key=lambda m: m.date, reverse=True)[0] if matches else None


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def format_date_relative(d: date) -> str:
    """Format date in human-friendly relative terms."""
    today = date.today()
    delta = (today - d).days
    
    if delta == 0:
        return "today"
    elif delta == 1:
        return "yesterday"
    elif delta < 7:
        return d.strftime("%A")  # "Tuesday"
    elif delta < 14:
        return "last " + d.strftime("%A")  # "last Tuesday"
    elif delta < 60:
        return d.strftime("%b %d")  # "Dec 15"
    else:
        return d.strftime("%b %Y")  # "Dec 2025"


def format_pace(pace_minutes: float) -> str:
    """Format pace as M:SS."""
    minutes = int(pace_minutes)
    seconds = int((pace_minutes - minutes) * 60)
    return f"{minutes}:{seconds:02d}"
