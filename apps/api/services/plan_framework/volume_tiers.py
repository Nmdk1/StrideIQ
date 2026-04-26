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
from services.mileage_aggregation import get_canonical_run_activities

from .constants import VolumeTier, Distance, VOLUME_TIER_THRESHOLDS

import math


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
        
        # Find appropriate tier (highest first — a 90mpw runner is ELITE, not HIGH)
        # Tier boundaries are universal across distances; only peak volume varies.
        for tier in [VolumeTier.ELITE, VolumeTier.HIGH, VolumeTier.MID, VolumeTier.LOW, VolumeTier.BUILDER]:
            tier_config = thresholds.get(tier)
            if not isinstance(tier_config, dict) or not tier_config:
                continue
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
        if not tier_config:
            # Fallback to the highest defined tier at or below the requested tier.
            fallback_order = [VolumeTier.HIGH, VolumeTier.MID, VolumeTier.LOW, VolumeTier.BUILDER]
            for t in fallback_order:
                if t in thresholds and isinstance(thresholds.get(t), dict) and thresholds.get(t):
                    tier_config = thresholds[t]
                    tier = t
                    break
        
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
        taper_weeks: int = 2,
        cutback_frequency_override: int = None,
        peak_volume_override: Optional[float] = None,
    ) -> list:
        """
        Calculate week-by-week volume targets.

        Returns list of target weekly volumes. Volume progresses toward the
        target peak over the build phase using linear steps — no per-week
        percentage cap. The athlete's history IS the safety guarantee.

        peak_volume_override: When provided (N=1: athlete's actual history/
            request), replaces the tier-table peak.  The plan reaches this
            target over the build phase.  Session-level spike limits are
            enforced separately by WorkoutScaler.

        Returning athletes (starting_volume < 65% of peak) have early cutbacks
        suppressed: they are ramping back to a load their body already knows,
        not training at ceiling.  Normal periodization resumes once they reach
        90% of peak.

        cutback_frequency_override: If provided (from athlete_plan_profile),
            overrides the tier default cutback frequency.
        """
        params = self.get_tier_params(tier, distance)
        peak_volume = peak_volume_override if peak_volume_override is not None else params["peak_weekly_miles"]
        cutback_freq = cutback_frequency_override or params["cutback_frequency"]
        cutback_reduction = params["cutback_reduction"]

        build_weeks = plan_weeks - taper_weeks

        # Returning athlete: starting well below their target peak.
        # Their ramp IS the re-adaptation stimulus — cutbacks serve athletes
        # training at ceiling, not athletes rebuilding to a known prior load.
        # Only applies when an explicit N=1 peak override is provided — standard
        # tier-table plans always use full cutback structure.
        is_returning = (
            peak_volume_override is not None
            and starting_volume < peak_volume * 0.65
        )

        volumes = []
        current = starting_volume

        for week in range(1, plan_weeks + 1):
            # Taper phase — taper from ACTUAL achieved peak, not config ceiling.
            if week > build_weeks:
                actual_peak = max(volumes) if volumes else peak_volume
                taper_week = week - build_weeks
                volumes.append(round(actual_peak * (0.6 if taper_week == 1 else 0.4), 1))
                continue

            # Should this week be a cutback?
            would_be_cutback = (week % cutback_freq == 0)
            # Suppress cutback while returning athlete is still below 90% of target.
            cutback_suppressed = is_returning and (current < peak_volume * 0.90)

            if would_be_cutback and not cutback_suppressed:
                if tier == VolumeTier.BUILDER:
                    cv = math.floor(current * 0.90 * 10) / 10.0
                else:
                    effective_reduction = min(cutback_reduction, 0.15) if tier == VolumeTier.LOW else cutback_reduction
                    cv = math.floor(current * (1 - effective_reduction) * 10) / 10.0
                volumes.append(cv)
                current = cv
            else:
                # Build week: linear step toward peak distributed across the
                # remaining non-taper, non-cutback weeks (including this one).
                # Suppressed-cutback weeks are treated as build weeks.
                remaining_build = sum(
                    1 for w in range(week, build_weeks + 1)
                    if not (w % cutback_freq == 0 and not (is_returning and current < peak_volume * 0.90))
                )
                remaining_build = max(1, remaining_build)
                step = (peak_volume - current) / remaining_build

                # Tier-specific absolute step ceiling for plans without an N=1
                # history override.  An athlete with documented high-volume
                # history (peak_volume_override provided) needs no cap — their
                # body already adapted to that load.  A BUILDER with no prior
                # high-volume history genuinely cannot safely spike large weekly
                # jumps even if their tier table peak is 50+.
                if peak_volume_override is None:
                    tier_step_ceil = {
                        VolumeTier.BUILDER: 4.0,
                        VolumeTier.LOW: 6.0,
                        VolumeTier.MID: 10.0,
                    }.get(tier)
                    if tier_step_ceil is not None:
                        step = min(step, tier_step_ceil)

                target = math.floor(min(current + max(step, 0.0), peak_volume) * 10) / 10.0
                volumes.append(target)
                current = target

        return volumes
    
    def _get_actual_volume(self, athlete_id: UUID) -> Optional[float]:
        """
        Get athlete's actual recent weekly volume from activity data.
        """
        if not self.db:
            return None

        # Look at last 4 weeks (trusted duplicate flags path).
        four_weeks_ago = datetime.utcnow() - timedelta(days=28)
        activities, _ = get_canonical_run_activities(
            athlete_id,
            self.db,
            start_time=four_weeks_ago,
            require_trusted_duplicate_flags=True,
        )
        
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
