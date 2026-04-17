"""Activity comparison services (Phase 5+)."""

from .comparable_runs import (  # noqa: F401
    ComparableTier,
    ComparableEntry,
    ComparablesResult,
    HEAT_TEMP_TOLERANCE_F,
    HEAT_DEW_TOLERANCE_F,
    ELEVATION_TOLERANCE,
    DISTANCE_TOLERANCE,
    DEFAULT_TRAILING_DAYS,
    find_comparables_for_activity,
)
