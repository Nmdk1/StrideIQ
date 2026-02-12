"""
Constants for plan generation.

These are DEFAULTS that can be overridden by config or database.
They exist here for type safety and documentation.
"""

from enum import Enum
from typing import Dict, List


class PlanTier(str, Enum):
    """Plan pricing/access tiers."""
    STANDARD = "standard"      # Free, fixed templates
    SEMI_CUSTOM = "semi"       # $5, questionnaire-based
    CUSTOM = "custom"          # Subscription, full personalization


class VolumeTier(str, Enum):
    """Athlete volume classification."""
    BUILDER = "builder"        # Building up to handle training
    LOW = "low"                # < 35 mpw
    MID = "mid"                # 35-55 mpw
    HIGH = "high"              # 55-80 mpw
    ELITE = "elite"            # 80+ mpw


class Distance(str, Enum):
    """Goal race distances."""
    FIVE_K = "5k"
    TEN_K = "10k"
    HALF_MARATHON = "half_marathon"
    MARATHON = "marathon"


class Phase(str, Enum):
    """Training phases."""
    BASE = "base"
    BASE_SPEED = "base_speed"
    VOLUME_BUILD = "volume_build"
    THRESHOLD = "threshold"
    MARATHON_SPECIFIC = "marathon_specific"
    RACE_SPECIFIC = "race_specific"
    HOLD = "hold"
    TAPER = "taper"
    RACE = "race"
    RECOVERY = "recovery"


class WorkoutCategory(str, Enum):
    """High-level workout categories."""
    REST = "rest"
    EASY = "easy"
    LONG = "long"
    THRESHOLD = "threshold"
    INTERVAL = "interval"
    SPEED = "speed"
    RACE_PACE = "race_pace"
    RACE = "race"


# Distance in meters
DISTANCE_METERS = {
    Distance.FIVE_K: 5000,
    Distance.TEN_K: 10000,
    Distance.HALF_MARATHON: 21097,
    Distance.MARATHON: 42195,
}

# Standard plan durations
STANDARD_DURATIONS = {
    Distance.MARATHON: [18, 12],
    Distance.HALF_MARATHON: [16, 12],
    Distance.TEN_K: [12, 8],
    Distance.FIVE_K: [12, 8],
}

# Volume tier thresholds (miles per week)
# Tier classification AND peak targets are UNIVERSAL across distances.
#
# Mileage is mileage.  The aerobic base is the aerobic base.  The best 5K
# racers in the world run 120-130 mpw.  A 70mpw runner doing a 10K peak
# block is training correctly.  The race determines the workout mix (more
# VO2max for 5K, more MP for marathon), not the volume ceiling.
#
# These are DEFAULTS for standard (non-personalized) plans.  The N=1 profile
# overrides peak, cutback frequency, and long run targets based on the
# athlete's actual history.  The defaults just need to not get in the way.
VOLUME_TIER_THRESHOLDS = {
    Distance.MARATHON: {
        VolumeTier.BUILDER: {"min": 20, "max": 35, "peak": 50},
        VolumeTier.LOW: {"min": 35, "max": 45, "peak": 55},
        VolumeTier.MID: {"min": 45, "max": 60, "peak": 70},
        VolumeTier.HIGH: {"min": 60, "max": 80, "peak": 85},
        VolumeTier.ELITE: {"min": 80, "max": 120, "peak": 110},
    },
    Distance.HALF_MARATHON: {
        VolumeTier.BUILDER: {"min": 20, "max": 35, "peak": 50},
        VolumeTier.LOW: {"min": 35, "max": 45, "peak": 55},
        VolumeTier.MID: {"min": 45, "max": 60, "peak": 70},
        VolumeTier.HIGH: {"min": 60, "max": 80, "peak": 85},
        VolumeTier.ELITE: {"min": 80, "max": 120, "peak": 110},
    },
    Distance.TEN_K: {
        VolumeTier.BUILDER: {"min": 20, "max": 35, "peak": 50},
        VolumeTier.LOW: {"min": 35, "max": 45, "peak": 55},
        VolumeTier.MID: {"min": 45, "max": 60, "peak": 70},
        VolumeTier.HIGH: {"min": 60, "max": 80, "peak": 85},
        VolumeTier.ELITE: {"min": 80, "max": 120, "peak": 110},
    },
    Distance.FIVE_K: {
        VolumeTier.BUILDER: {"min": 20, "max": 35, "peak": 50},
        VolumeTier.LOW: {"min": 35, "max": 45, "peak": 55},
        VolumeTier.MID: {"min": 45, "max": 60, "peak": 70},
        VolumeTier.HIGH: {"min": 60, "max": 80, "peak": 85},
        VolumeTier.ELITE: {"min": 80, "max": 120, "peak": 110},
    },
}

# Long run peaks by distance and tier (miles)
LONG_RUN_PEAKS = {
    Distance.MARATHON: {
        VolumeTier.BUILDER: 18,
        VolumeTier.LOW: 20,
        VolumeTier.MID: 22,
        # High-volume marathoners often benefit from longer durability work;
        # this is a DEFAULT peak cap (N=1 history can justify higher/other strategies).
        VolumeTier.HIGH: 24,
        VolumeTier.ELITE: 26,
    },
    Distance.HALF_MARATHON: {
        VolumeTier.BUILDER: 13,
        VolumeTier.LOW: 14,
        VolumeTier.MID: 16,
        # Durable HM runners frequently tolerate 18-20mi long runs.
        VolumeTier.HIGH: 20,
    },
    Distance.TEN_K: {
        VolumeTier.BUILDER: 10,
        VolumeTier.LOW: 12,
        VolumeTier.MID: 14,
        VolumeTier.HIGH: 15,
    },
    Distance.FIVE_K: {
        VolumeTier.BUILDER: 8,
        VolumeTier.LOW: 10,
        VolumeTier.MID: 12,
        VolumeTier.HIGH: 13,
    },
}

# Workout limits as percentage of weekly volume (Source B)
WORKOUT_LIMITS = {
    "threshold_pct": 0.10,      # Max 10% of weekly in one T session
    "interval_pct": 0.08,       # Max 8% of weekly in one I session
    "repetition_pct": 0.05,     # Max 5% of weekly in R work
    "long_run_pct": 0.30,       # Target 30% (can exceed for marathon)
    "mp_max_miles": 18,         # Max continuous MP (Source B)
}

# Cutback week frequency by tier
CUTBACK_RULES = {
    VolumeTier.BUILDER: {"frequency": 3, "reduction": 0.25},
    VolumeTier.LOW: {"frequency": 3, "reduction": 0.25},
    VolumeTier.MID: {"frequency": 4, "reduction": 0.25},
    VolumeTier.HIGH: {"frequency": 4, "reduction": 0.20},
    VolumeTier.ELITE: {"frequency": 4, "reduction": 0.20},
}

# Taper durations by distance (weeks) — legacy, used by generate_standard()
TAPER_WEEKS = {
    Distance.MARATHON: 2,      # 10-14 days
    Distance.HALF_MARATHON: 2,
    Distance.TEN_K: 1,
    Distance.FIVE_K: 1,
}

# Taper durations by distance (days) — personalized plans use this
# These are POPULATION DEFAULTS (Priority 4 in ADR-062).  The TaperCalculator
# will override with N=1 signals when available.
TAPER_DAYS_DEFAULT = {
    Distance.MARATHON: 14,
    Distance.HALF_MARATHON: 10,
    Distance.TEN_K: 7,
    Distance.FIVE_K: 5,
}


class ReboundSpeed(str, Enum):
    """Recovery rebound speed classification."""
    FAST = "fast"       # recovery_half_life_hours <= 36
    NORMAL = "normal"   # 36 < recovery_half_life_hours <= 60
    SLOW = "slow"       # recovery_half_life_hours > 60


# Direct mapping: (rebound_speed, distance) → taper_days
# Anchored to coaching literature (Daniels, Pfitzinger, Vigil).
# No τ1 conversion — this is an observable-to-prescription mapping.
#
# Fast recoverers adapt quickly but also LOSE fitness quickly → shorter taper.
# Slow recoverers retain fitness longer → can handle longer taper.
# Longer races need more taper because the training block generates more
# accumulated fatigue (MP long runs, glycogen depletion, musculoskeletal load).
TAPER_DAYS_BY_REBOUND = {
    (ReboundSpeed.FAST, Distance.MARATHON): 10,
    (ReboundSpeed.FAST, Distance.HALF_MARATHON): 7,
    (ReboundSpeed.FAST, Distance.TEN_K): 5,
    (ReboundSpeed.FAST, Distance.FIVE_K): 4,
    (ReboundSpeed.NORMAL, Distance.MARATHON): 13,
    (ReboundSpeed.NORMAL, Distance.HALF_MARATHON): 9,
    (ReboundSpeed.NORMAL, Distance.TEN_K): 7,
    (ReboundSpeed.NORMAL, Distance.FIVE_K): 5,
    (ReboundSpeed.SLOW, Distance.MARATHON): 17,
    (ReboundSpeed.SLOW, Distance.HALF_MARATHON): 12,
    (ReboundSpeed.SLOW, Distance.TEN_K): 9,
    (ReboundSpeed.SLOW, Distance.FIVE_K): 7,
}
