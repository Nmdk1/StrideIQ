"""
Volume Tier Classification

Classifies athletes into appropriate volume tiers based on:
- Current weekly mileage
- Training history (if available)
- Goal distance

Usage:
    classifier = VolumeTierClassifier(db)
    tier = classifier.classify(athlete, distance="marathon")
    
    # Get tier parameters
    params = classifier.get_tier_params(tier, distance)
"""

from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .constants import VolumeTier, Distance, VOLUME_TIER_THRESHOLDS


class VolumeTierClassifier:
    """
    Classify athletes into volume tiers.
    """
    
    def __init__(self, db: Session = None):
        self.db = db
    
    def classify(
        self,
        current_weekly_miles: float,
        goal_distance: str,
        athlete_id: UUID = None,
        consider_history: bool = True
    ) -> VolumeTier:
        """
        Classify athlete into volume tier.
        
        Args:
            current_weekly_miles: Reported or calculated weekly mileage
            goal_distance: Target race distance
            athlete_id: Optional athlete ID for history lookup
            consider_history: Whether to consider training history
            
        Returns:
            VolumeTier enum value
        """
        # If athlete_id provided and we should consider history,
        # get their actual training data
        if athlete_id and consider_history and self.db:
            actual_volume = self._get_actual_volume(athlete_id)
            if actual_volume:
                # Use the higher of reported and actual
                current_weekly_miles = max(current_weekly_miles, actual_volume)
        
        # Get distance enum
        try:
            distance = Distance(goal_distance)
        except ValueError:
            distance = Distance.MARATHON  # Default
        
        # Get thresholds for this distance
        thresholds = VOLUME_TIER_THRESHOLDS.get(distance, {})
        
        # Find appropriate tier
        for tier in [VolumeTier.ELITE, VolumeTier.HIGH, VolumeTier.MID, VolumeTier.LOW, VolumeTier.BUILDER]:
            tier_config = thresholds.get(tier, {})
            min_mpw = tier_config.get("min", 0)
            max_mpw = tier_config.get("max", 999)
            
            if min_mpw <= current_weekly_miles <= max_mpw:
                return tier
        
        # If below lowest tier, they're a builder
        return VolumeTier.BUILDER
    
    def get_tier_params(
        self, 
        tier: VolumeTier, 
        distance: str
    ) -> Dict[str, Any]:
        """
        Get training parameters for a tier.
        
        Returns:
            Dict with min, max, peak, long_run_peak, etc.
        """
        try:
            dist = Distance(distance)
        except ValueError:
            dist = Distance.MARATHON
        
        thresholds = VOLUME_TIER_THRESHOLDS.get(dist, {})
        tier_config = thresholds.get(tier, {})
        
        from .constants import LONG_RUN_PEAKS, CUTBACK_RULES
        
        return {
            "min_weekly_miles": tier_config.get("min", 25),
            "max_weekly_miles": tier_config.get("max", 45),
            "peak_weekly_miles": tier_config.get("peak", 55),
            "long_run_peak_miles": LONG_RUN_PEAKS.get(dist, {}).get(tier, 20),
            "cutback_frequency": CUTBACK_RULES.get(tier, {}).get("frequency", 4),
            "cutback_reduction": CUTBACK_RULES.get(tier, {}).get("reduction", 0.25),
        }
    
    def calculate_starting_volume(
        self,
        tier: VolumeTier,
        distance: str,
        current_volume: float
    ) -> float:
        """
        Calculate appropriate starting volume for plan.
        
        Starts at current (not higher) and builds up.
        """
        params = self.get_tier_params(tier, distance)
        
        # Never start higher than current
        start = min(current_volume, params["min_weekly_miles"])
        
        # But don't start absurdly low either
        floor = params["min_weekly_miles"] * 0.7
        
        return max(start, floor)
    
    def calculate_volume_progression(
        self,
        tier: VolumeTier,
        distance: str,
        starting_volume: float,
        plan_weeks: int,
        taper_weeks: int = 2
    ) -> list:
        """
        Calculate week-by-week volume targets.
        
        Returns list of target weekly volumes.
        Uses safe progression: max 10% increase week-over-week.
        """
        params = self.get_tier_params(tier, distance)
        peak_volume = params["peak_weekly_miles"]
        cutback_freq = params["cutback_frequency"]
        cutback_reduction = params["cutback_reduction"]
        
        # Build weeks (excluding taper)
        build_weeks = plan_weeks - taper_weeks
        
        # Calculate weekly increase (max 10% of current volume, or less to reach peak)
        volumes = []
        current = starting_volume
        
        for week in range(1, plan_weeks + 1):
            # Taper phase
            if week > build_weeks:
                taper_week = week - build_weeks
                if taper_week == 1:
                    # First taper week: 60% of peak
                    volumes.append(peak_volume * 0.6)
                else:
                    # Race week: 40% of peak
                    volumes.append(peak_volume * 0.4)
            # Cutback week
            elif week % cutback_freq == 0:
                # Cutback to 75% of what would have been this week's volume
                cutback_volume = current * (1 - cutback_reduction)
                volumes.append(cutback_volume)
            # Build week
            else:
                # Increase by up to 10%, but don't exceed peak
                max_increase = current * 0.10
                target = min(current + max_increase, peak_volume)
                volumes.append(target)
                current = target  # Update current for next week
        
        return volumes
    
    def _get_actual_volume(self, athlete_id: UUID) -> Optional[float]:
        """
        Get athlete's actual recent weekly volume from activity data.
        """
        if not self.db:
            return None
        
        from models import Activity
        
        # Look at last 4 weeks
        four_weeks_ago = datetime.utcnow() - timedelta(days=28)
        
        activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.sport == "run",
            Activity.start_time >= four_weeks_ago
        ).all()
        
        if not activities:
            return None
        
        # Calculate average weekly volume
        total_distance_m = sum(a.distance_m or 0 for a in activities)
        total_distance_miles = total_distance_m / 1609.34
        
        # 4-week average
        return total_distance_miles / 4
    
    def get_tier_description(self, tier: VolumeTier) -> str:
        """Get human-readable tier description."""
        descriptions = {
            VolumeTier.BUILDER: "Building base fitness and adapting to higher volume",
            VolumeTier.LOW: "Established runner with solid aerobic base",
            VolumeTier.MID: "Experienced runner comfortable with consistent training",
            VolumeTier.HIGH: "Advanced runner handling significant volume",
            VolumeTier.ELITE: "Elite-level volume and training intensity",
        }
        return descriptions.get(tier, "Unknown tier")
