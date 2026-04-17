"""Phase 4 — Training block detection algorithm tests.

Pure-algorithm tests using lightweight stand-in objects. Persistence
tests live separately (require a real session fixture / Postgres).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from services.blocks.block_detector import (
    EASY_TYPES,
    LONG_TYPES,
    QUALITY_TYPES,
    aggregate_weeks,
    detect_block_boundaries,
    label_blocks,
)


# ---------------------------------------------------------------------------
# Lightweight Activity stand-in (avoids needing the SQLAlchemy ORM in tests)
# ---------------------------------------------------------------------------


@dataclass
class _A:
    start_time: datetime
    distance_m: int = 8000
    duration_s: int = 2400
    workout_type: Optional[str] = "easy_run"
    sport: str = "run"
    name: Optional[str] = None
    id: uuid.UUID = uuid.uuid4()


def _runs(
    start_date: date,
    n: int,
    *,
    spacing_days: int = 1,
    distance_m: int = 8000,
    workout_type: Optional[str] = "easy_run",
    name: Optional[str] = None,
) -> List[_A]:
    """Build n run activities starting from start_date."""
    out = []
    cur = start_date
    for _ in range(n):
        out.append(
            _A(
                start_time=datetime.combine(cur, datetime.min.time(), tzinfo=timezone.utc),
                distance_m=distance_m,
                workout_type=workout_type,
                name=name,
            )
        )
        cur = cur + timedelta(days=spacing_days)
    return out


# ---------------------------------------------------------------------------
# Workout-type registry sanity
# ---------------------------------------------------------------------------


class TestWorkoutTypeRegistry:
    def test_known_quality_types(self):
        assert "interval_workout" in QUALITY_TYPES
        assert "threshold_run" in QUALITY_TYPES
        assert "tempo_run" in QUALITY_TYPES
        assert "race" in QUALITY_TYPES
        assert "cruise_intervals" in QUALITY_TYPES

    def test_known_easy_types(self):
        assert "recovery_run" in EASY_TYPES
        assert "easy_run" in EASY_TYPES

    def test_long_types(self):
        assert "long_run" in LONG_TYPES
        assert "medium_long_run" in LONG_TYPES

    def test_categories_are_disjoint(self):
        assert not (QUALITY_TYPES & EASY_TYPES)
        assert not (QUALITY_TYPES & LONG_TYPES)
        assert not (EASY_TYPES & LONG_TYPES)


# ---------------------------------------------------------------------------
# aggregate_weeks
# ---------------------------------------------------------------------------


class TestAggregateWeeks:
    def test_empty_returns_empty(self):
        assert aggregate_weeks([]) == []

    def test_single_run_yields_single_week(self):
        weeks = aggregate_weeks(_runs(date(2025, 6, 2), 1))
        assert len(weeks) == 1
        assert weeks[0].run_count == 1
        assert weeks[0].distance_m == 8000

    def test_dense_weekly_series_includes_zero_weeks(self):
        # Run on week 1, skip week 2, run again on week 3
        a1 = _runs(date(2025, 6, 2), 1)  # Mon, week 23
        a2 = _runs(date(2025, 6, 16), 1)  # Mon, week 25
        weeks = aggregate_weeks(a1 + a2)
        # Should be three rows: weeks 23, 24 (zero), 25
        assert len(weeks) == 3
        assert weeks[0].run_count == 1
        assert weeks[1].run_count == 0
        assert weeks[2].run_count == 1

    def test_workout_type_categorization(self):
        acts = (
            _runs(date(2025, 6, 2), 3, workout_type="easy_run")
            + _runs(date(2025, 6, 3), 1, workout_type="threshold_run")
            + _runs(date(2025, 6, 4), 1, workout_type="long_run", distance_m=18000)
        )
        weeks = aggregate_weeks(acts)
        assert len(weeks) == 1
        w = weeks[0]
        assert w.run_count == 5
        assert w.quality_count == 1  # threshold_run
        assert w.long_count == 1
        assert w.workout_type_counts["easy_run"] == 3
        assert w.longest_run_m == 18000

    def test_race_week_flagged(self):
        acts = _runs(date(2025, 6, 2), 1, workout_type="race", name="Bonita 5K")
        weeks = aggregate_weeks(acts)
        assert weeks[0].has_race is True
        assert weeks[0].race_name == "Bonita 5K"


# ---------------------------------------------------------------------------
# detect_block_boundaries
# ---------------------------------------------------------------------------


class TestDetectBoundaries:
    def test_single_week_one_block(self):
        weeks = aggregate_weeks(_runs(date(2025, 6, 2), 3))
        ranges = detect_block_boundaries(weeks, _runs(date(2025, 6, 2), 3))
        assert ranges == [(0, 0)]

    def test_off_week_isolated_as_own_block(self):
        acts = _runs(date(2025, 6, 2), 3) + _runs(date(2025, 6, 16), 3)
        weeks = aggregate_weeks(acts)
        ranges = detect_block_boundaries(weeks, acts)
        # Block 0 = week with first runs; block 1 = off week; block 2 = resumption
        assert (1, 1) in ranges
        # The off week is its own block (single index)
        off_blocks = [(lo, hi) for lo, hi in ranges if weeks[lo].run_count == 0]
        assert len(off_blocks) == 1
        assert off_blocks[0] == (1, 1)

    def test_race_week_terminates_block(self):
        acts = (
            _runs(date(2025, 6, 2), 5, workout_type="easy_run")
            + _runs(date(2025, 6, 9), 5, workout_type="easy_run")
            + [
                _A(
                    start_time=datetime(2025, 6, 14, 8, 0, tzinfo=timezone.utc),
                    distance_m=21097,
                    workout_type="race",
                    name="Bonita Half",
                )
            ]
        )
        weeks = aggregate_weeks(acts)
        ranges = detect_block_boundaries(weeks, acts)
        # Last range must include the race week
        last = ranges[-1]
        assert weeks[last[1]].has_race is True

    def test_recovery_week_after_build_isolated(self):
        # 4 building weeks, then a recovery week at ~30% of trailing avg
        building = []
        for w in range(4):
            building += _runs(
                date(2025, 6, 2) + timedelta(days=7 * w), 5, distance_m=10000
            )
        # Recovery week: only 2 short runs at 4km each
        recovery = _runs(date(2025, 6, 30), 2, distance_m=4000)
        acts = building + recovery
        weeks = aggregate_weeks(acts)
        ranges = detect_block_boundaries(weeks, acts)
        # Should have at least 2 ranges, with the last single-week being recovery
        assert len(ranges) >= 2
        last_lo, last_hi = ranges[-1]
        assert last_lo == last_hi  # single-week block
        assert weeks[last_lo].distance_m < 12000  # the recovery week

    def test_ten_day_gap_creates_boundary(self):
        # Mon-Wed runs in week 1, then 12-day gap, then runs week 3
        a1 = _runs(date(2025, 6, 2), 3, spacing_days=1, distance_m=8000)
        a2 = _runs(date(2025, 6, 16), 3, spacing_days=1, distance_m=8000)
        # Note: a1 ends 6/4, a2 starts 6/16 → 12-day gap
        acts = a1 + a2
        weeks = aggregate_weeks(acts)
        ranges = detect_block_boundaries(weeks, acts)
        # We expect AT LEAST 2 ranges (gap split)
        assert len(ranges) >= 2


# ---------------------------------------------------------------------------
# label_blocks
# ---------------------------------------------------------------------------


class TestLabelBlocks:
    def test_easy_only_block_labeled_base(self):
        acts = []
        for w in range(4):
            acts += _runs(
                date(2025, 6, 2) + timedelta(days=7 * w),
                4,
                workout_type="easy_run",
                distance_m=8000,
            )
        weeks = aggregate_weeks(acts)
        ranges = detect_block_boundaries(weeks, acts)
        blocks = label_blocks(ranges, weeks)
        assert all(b.phase in {"base", "off"} for b in blocks)

    def test_quality_present_labeled_build_or_peak(self):
        acts = []
        for w in range(4):
            acts += _runs(
                date(2025, 6, 2) + timedelta(days=7 * w),
                3,
                workout_type="easy_run",
                distance_m=8000,
            )
            acts += _runs(
                date(2025, 6, 4) + timedelta(days=7 * w),
                1,
                workout_type="threshold_run",
                distance_m=12000,
            )
        weeks = aggregate_weeks(acts)
        ranges = detect_block_boundaries(weeks, acts)
        blocks = label_blocks(ranges, weeks)
        # The big block should be `build` or `peak`
        big = max(blocks, key=lambda b: len(b.weeks))
        assert big.phase in {"build", "peak"}

    def test_race_week_labeled_race(self):
        acts = (
            _runs(date(2025, 6, 2), 4)
            + _runs(date(2025, 6, 9), 4)
            + [
                _A(
                    start_time=datetime(2025, 6, 14, 8, 0, tzinfo=timezone.utc),
                    distance_m=42195,
                    workout_type="race",
                    name="Boston",
                )
            ]
        )
        weeks = aggregate_weeks(acts)
        ranges = detect_block_boundaries(weeks, acts)
        blocks = label_blocks(ranges, weeks)
        # Final block must be a race or taper
        assert blocks[-1].phase in {"race", "taper"}
        assert blocks[-1].goal_event_name == "Boston"

    def test_off_block_labeled_off(self):
        # Only one week with runs, then a fully off week
        acts = _runs(date(2025, 6, 2), 3)
        # Weeks list: week 1 has runs, week 2 is empty (we get density via aggregate)
        # Simulate off week by including a run later that pushes a gap.
        acts += _runs(date(2025, 6, 23), 3)
        weeks = aggregate_weeks(acts)
        ranges = detect_block_boundaries(weeks, acts)
        blocks = label_blocks(ranges, weeks)
        off_blocks = [b for b in blocks if b.phase == "off"]
        assert len(off_blocks) >= 1


# ---------------------------------------------------------------------------
# DetectedBlock derived properties
# ---------------------------------------------------------------------------


class TestDetectedBlockProps:
    def test_total_distance_summed_correctly(self):
        acts = []
        for w in range(3):
            acts += _runs(
                date(2025, 6, 2) + timedelta(days=7 * w), 4, distance_m=8000
            )
        weeks = aggregate_weeks(acts)
        ranges = detect_block_boundaries(weeks, acts)
        blocks = label_blocks(ranges, weeks)
        assert blocks[0].total_distance_m == 3 * 4 * 8000  # 96km
        assert blocks[0].run_count == 12

    def test_dominant_workout_types_top3(self):
        acts = (
            _runs(date(2025, 6, 2), 3, workout_type="easy_run")
            + _runs(date(2025, 6, 3), 2, workout_type="threshold_run")
            + _runs(date(2025, 6, 4), 1, workout_type="long_run")
            + _runs(date(2025, 6, 5), 1, workout_type="hill_workout")
        )
        weeks = aggregate_weeks(acts)
        ranges = detect_block_boundaries(weeks, acts)
        blocks = label_blocks(ranges, weeks)
        assert blocks[0].dominant_workout_types[0] == "easy_run"
        assert "threshold_run" in blocks[0].dominant_workout_types
        assert len(blocks[0].dominant_workout_types) <= 3

    def test_quality_pct_computed(self):
        acts = (
            _runs(date(2025, 6, 2), 8, workout_type="easy_run")
            + _runs(date(2025, 6, 3), 2, workout_type="threshold_run")
        )
        weeks = aggregate_weeks(acts)
        ranges = detect_block_boundaries(weeks, acts)
        blocks = label_blocks(ranges, weeks)
        # 2 quality / 10 runs = 20%
        assert blocks[0].quality_pct == 20
