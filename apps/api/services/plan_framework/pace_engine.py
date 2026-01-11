"""
Pace Engine

Integrates with Training Pace Calculator (VDOT) to populate
training plans with personalized paces.

Usage:
    pace_engine = PaceEngine()
    
    # From race time
    paces = pace_engine.calculate_from_race(distance="5k", time_seconds=1200)
    
    # Get specific pace
    easy_pace = paces.easy_pace_per_mile_seconds
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class TrainingPaces:
    """All training paces for an athlete."""
    
    # VDOT source
    vdot: float
    race_distance: str
    race_time_seconds: int
    
    # Paces in seconds per mile
    easy_pace_low: int   # Lower end of easy range
    easy_pace_high: int  # Upper end of easy range
    marathon_pace: int
    threshold_pace: int
    interval_pace: int    # VO2max intervals
    repetition_pace: int  # Fast reps (200s, 400s)
    
    # Also in seconds per km
    easy_pace_per_km_low: int
    easy_pace_per_km_high: int
    marathon_pace_per_km: int
    threshold_pace_per_km: int
    interval_pace_per_km: int
    repetition_pace_per_km: int
    
    def get_pace_description(self, workout_type: str) -> str:
        """
        Get pace description for a workout type.
        
        Returns pace + effort context (e.g., "9:30-10:00/mi (conversational, relaxed)")
        """
        if workout_type in ["easy", "recovery", "easy_run"]:
            pace = f"{self._format_pace(self.easy_pace_low)}-{self._format_pace(self.easy_pace_high)}/mi"
            return f"{pace} (conversational, relaxed)"
        elif workout_type in ["long", "long_run"]:
            pace = f"{self._format_pace(self.easy_pace_low)}-{self._format_pace(self.easy_pace_high)}/mi"
            return f"{pace} (easy, sustainable)"
        elif workout_type in ["medium_long"]:
            # Medium-long slightly quicker than easy
            pace = f"{self._format_pace(self.easy_pace_low)}-{self._format_pace(self.easy_pace_high)}/mi"
            return f"{pace} (easy to steady)"
        elif workout_type in ["marathon", "mp", "marathon_pace", "long_mp"]:
            pace = f"{self._format_pace(self.marathon_pace)}/mi"
            return f"{pace} (goal race pace)"
        elif workout_type in ["threshold", "tempo", "t_run", "threshold_intervals"]:
            pace = f"{self._format_pace(self.threshold_pace)}/mi"
            return f"{pace} (comfortably hard)"
        elif workout_type in ["interval", "vo2max", "i_run", "intervals"]:
            pace = f"{self._format_pace(self.interval_pace)}/mi"
            return f"{pace} (hard effort)"
        elif workout_type in ["repetition", "reps", "strides"]:
            pace = f"{self._format_pace(self.repetition_pace)}/mi"
            return f"{pace} (quick, controlled)"
        elif workout_type in ["hills"]:
            # Hills don't have a specific pace, effort-based
            return "strong effort uphill, controlled descent"
        else:
            return "conversational pace"
    
    def _format_pace(self, seconds_per_mile: int) -> str:
        """Format pace as mm:ss."""
        minutes = seconds_per_mile // 60
        seconds = seconds_per_mile % 60
        return f"{minutes}:{seconds:02d}"


class PaceEngine:
    """
    Calculate training paces from race performances.
    Uses VDOT methodology from the existing calculator.
    """
    
    def calculate_from_race(
        self,
        distance: str,
        time_seconds: int
    ) -> Optional[TrainingPaces]:
        """
        Calculate training paces from a race time.
        
        Args:
            distance: Race distance ("5k", "10k", "half", "marathon")
            time_seconds: Race time in seconds
            
        Returns:
            TrainingPaces object with all pace zones
        """
        # Import the VDOT calculator
        from services.vdot_calculator import calculate_vdot_from_race_time, calculate_training_paces
        
        try:
            # Convert distance to meters
            distance_meters = {
                "5k": 5000,
                "10k": 10000,
                "half_marathon": 21097.5,
                "half": 21097.5,
                "marathon": 42195,
            }.get(distance.lower(), 0)
            
            if not distance_meters:
                return None
            
            # Calculate VDOT
            vdot = calculate_vdot_from_race_time(distance_meters, time_seconds)
            
            if vdot is None:
                return None
            
            # Get training paces
            paces = calculate_training_paces(vdot)
            
            if not paces:
                return None
            
            # Convert to our format
            return TrainingPaces(
                vdot=vdot,
                race_distance=distance,
                race_time_seconds=time_seconds,
                
                # Paces per mile
                easy_pace_low=paces.get("easy_pace_low", 540),
                easy_pace_high=paces.get("easy_pace_high", 570),
                marathon_pace=paces.get("marathon_pace", 450),
                threshold_pace=paces.get("threshold_pace", 420),
                interval_pace=paces.get("interval_pace", 390),
                repetition_pace=paces.get("repetition_pace", 360),
                
                # Convert to per km (divide by 1.609)
                easy_pace_per_km_low=int(paces.get("easy_pace_low", 540) / 1.609),
                easy_pace_per_km_high=int(paces.get("easy_pace_high", 570) / 1.609),
                marathon_pace_per_km=int(paces.get("marathon_pace", 450) / 1.609),
                threshold_pace_per_km=int(paces.get("threshold_pace", 420) / 1.609),
                interval_pace_per_km=int(paces.get("interval_pace", 390) / 1.609),
                repetition_pace_per_km=int(paces.get("repetition_pace", 360) / 1.609),
            )
        except Exception as e:
            import logging
            logging.warning(f"Pace calculation failed: {e}")
            return None
    
    def calculate_from_vdot(self, vdot: float) -> Optional[TrainingPaces]:
        """
        Calculate training paces from VDOT directly.
        """
        from services.vdot_calculator import get_training_paces
        
        try:
            paces = get_training_paces(vdot)
            
            if not paces:
                return None
            
            return TrainingPaces(
                vdot=vdot,
                race_distance="estimated",
                race_time_seconds=0,
                
                easy_pace_low=paces.get("easy_pace_low", 540),
                easy_pace_high=paces.get("easy_pace_high", 570),
                marathon_pace=paces.get("marathon_pace", 450),
                threshold_pace=paces.get("threshold_pace", 420),
                interval_pace=paces.get("interval_pace", 390),
                repetition_pace=paces.get("repetition_pace", 360),
                
                easy_pace_per_km_low=int(paces.get("easy_pace_low", 540) / 1.609),
                easy_pace_per_km_high=int(paces.get("easy_pace_high", 570) / 1.609),
                marathon_pace_per_km=int(paces.get("marathon_pace", 450) / 1.609),
                threshold_pace_per_km=int(paces.get("threshold_pace", 420) / 1.609),
                interval_pace_per_km=int(paces.get("interval_pace", 390) / 1.609),
                repetition_pace_per_km=int(paces.get("repetition_pace", 360) / 1.609),
            )
        except Exception as e:
            import logging
            logging.warning(f"Pace calculation from VDOT failed: {e}")
            return None
    
    def get_effort_description(self, workout_type: str) -> str:
        """
        Get effort description when no pace data available.
        Used for standard/free plans.
        """
        descriptions = {
            "easy": "Conversational pace - you should be able to hold a conversation",
            "recovery": "Very easy, slower than normal easy pace",
            "long": "Easy effort, building endurance through time on feet",
            "marathon_pace": "Goal marathon race pace - comfortably hard",
            "threshold": "Comfortably hard - can speak in short sentences",
            "tempo": "Comfortably hard, sustainable for 20-30 minutes",
            "interval": "Hard effort, short recovery between reps",
            "vo2max": "Near-maximum effort, very hard breathing",
            "repetition": "Fast and controlled, with full recovery",
            "strides": "Quick turnover, not all-out, focus on form",
            "hills": "Strong effort uphill, controlled descent",
        }
        
        return descriptions.get(workout_type, "Run by feel")
    
    def format_pace_range(
        self,
        pace_low: int,
        pace_high: int,
        unit: str = "mile"
    ) -> str:
        """Format a pace range as string."""
        low = self._format_pace(pace_low)
        high = self._format_pace(pace_high)
        return f"{low}-{high} per {unit}"
    
    def _format_pace(self, seconds: int) -> str:
        """Format pace as mm:ss."""
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}:{secs:02d}"
