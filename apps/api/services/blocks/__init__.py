"""Block detection services."""

from .block_detector import (  # noqa: F401
    QUALITY_TYPES,
    LONG_TYPES,
    EASY_TYPES,
    WeekStat,
    DetectedBlock,
    aggregate_weeks,
    detect_block_boundaries,
    label_blocks,
    detect_blocks_for_athlete,
    persist_detected_blocks,
)
