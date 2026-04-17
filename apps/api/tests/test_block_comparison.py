"""Phase 7 — block-over-block comparison (pure function tests).

The full DB integration coverage piggybacks on the block_detector
fixture; these tests cover the pure helpers + dataclass shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional

from services.comparison.block_comparison import (
    WeekStat,
    WorkoutTypeCompare,
    _aggregate_workout_type_compare,
    _avg_pace_s_per_km,
    _compute_week_series,
)


@dataclass
class _A:
    workout_type: Optional[str] = None
    distance_m: Optional[int] = None
    duration_s: Optional[int] = None
    start_time: Optional[datetime] = None


@dataclass
class _Block:
    start_date: date
    end_date: date
    weeks: int
    athlete_id: object = None
    id: object = None


# ---------------------------------------------------------------------------
# pace helper
# ---------------------------------------------------------------------------


class TestAvgPace:
    def test_normal(self):
        assert _avg_pace_s_per_km(10000, 3000) == 300.0

    def test_zero_distance(self):
        assert _avg_pace_s_per_km(0, 3000) is None

    def test_missing(self):
        assert _avg_pace_s_per_km(None, 3000) is None
        assert _avg_pace_s_per_km(10000, None) is None


# ---------------------------------------------------------------------------
# week series
# ---------------------------------------------------------------------------


class TestWeekSeries:
    def test_empty_block_returns_zero_filled_series(self):
        block = _Block(
            start_date=date(2026, 4, 6),  # Monday
            end_date=date(2026, 4, 26),  # Sunday, 3 weeks later
            weeks=3,
        )
        series = _compute_week_series(block, [])
        assert len(series) == 3
        assert all(w.total_distance_m == 0 for w in series)
        assert all(w.run_count == 0 for w in series)
        assert series[0].iso_week_start == "2026-04-06"
        assert series[1].iso_week_start == "2026-04-13"
        assert series[2].iso_week_start == "2026-04-20"

    def test_one_run_one_week(self):
        block = _Block(
            start_date=date(2026, 4, 6),
            end_date=date(2026, 4, 19),
            weeks=2,
        )
        runs = [
            _A(
                workout_type="threshold_run",
                distance_m=10000,
                duration_s=2400,
                start_time=datetime(2026, 4, 8, tzinfo=timezone.utc),
            )
        ]
        series = _compute_week_series(block, runs)
        assert len(series) == 2
        assert series[0].total_distance_m == 10000
        assert series[0].run_count == 1
        assert series[0].quality_count == 1
        assert series[0].easy_count == 0
        assert series[0].longest_run_m == 10000
        assert series[1].total_distance_m == 0

    def test_easy_quality_categorization(self):
        block = _Block(
            start_date=date(2026, 4, 6),
            end_date=date(2026, 4, 12),
            weeks=1,
        )
        runs = [
            _A(
                workout_type="easy_run",
                distance_m=8000,
                duration_s=2880,
                start_time=datetime(2026, 4, 7, tzinfo=timezone.utc),
            ),
            _A(
                workout_type="threshold_run",
                distance_m=10000,
                duration_s=2400,
                start_time=datetime(2026, 4, 9, tzinfo=timezone.utc),
            ),
            _A(
                workout_type="long_run",
                distance_m=20000,
                duration_s=7200,
                start_time=datetime(2026, 4, 11, tzinfo=timezone.utc),
            ),
        ]
        series = _compute_week_series(block, runs)
        assert len(series) == 1
        assert series[0].run_count == 3
        assert series[0].easy_count == 1
        assert series[0].quality_count == 1  # threshold; long is its own bucket
        assert series[0].longest_run_m == 20000


# ---------------------------------------------------------------------------
# workout type compare
# ---------------------------------------------------------------------------


class TestWorkoutTypeCompare:
    def test_one_type_only(self):
        a = [_A(workout_type="easy_run", distance_m=10000, duration_s=3000)]
        b = [
            _A(workout_type="easy_run", distance_m=10000, duration_s=2700),  # faster
            _A(workout_type="easy_run", distance_m=10000, duration_s=2700),
        ]
        rows = _aggregate_workout_type_compare(a, b)
        assert len(rows) == 1
        r = rows[0]
        assert r.workout_type == "easy_run"
        assert r.a_count == 1
        assert r.b_count == 2
        assert r.delta_count == 1
        # 10km/3000s = 5:00/km in A; 20km/5400s = 4:30/km in B
        assert r.a_avg_pace_s_per_km == 300.0
        assert r.b_avg_pace_s_per_km == 270.0
        assert r.delta_pace_s_per_km == -30.0  # B is 30s/km faster

    def test_disjoint_types(self):
        a = [_A(workout_type="easy_run", distance_m=10000, duration_s=3000)]
        b = [_A(workout_type="threshold_run", distance_m=8000, duration_s=2000)]
        rows = _aggregate_workout_type_compare(a, b)
        # Both types should appear; each has 0 in the other
        types = {r.workout_type for r in rows}
        assert types == {"easy_run", "threshold_run"}
        easy = next(r for r in rows if r.workout_type == "easy_run")
        thresh = next(r for r in rows if r.workout_type == "threshold_run")
        assert easy.a_count == 1
        assert easy.b_count == 0
        assert easy.b_avg_pace_s_per_km is None
        assert easy.delta_pace_s_per_km is None
        assert thresh.a_count == 0
        assert thresh.b_count == 1

    def test_sorted_by_combined_volume(self):
        a = [
            _A(workout_type="threshold_run", distance_m=8000, duration_s=2000),
            _A(workout_type="easy_run", distance_m=2000, duration_s=600),
        ]
        b = [
            _A(workout_type="threshold_run", distance_m=8000, duration_s=2000),
            _A(workout_type="easy_run", distance_m=2000, duration_s=600),
        ]
        rows = _aggregate_workout_type_compare(a, b)
        # threshold (16km combined) > easy (4km combined)
        assert rows[0].workout_type == "threshold_run"
        assert rows[1].workout_type == "easy_run"

    def test_skips_untyped_runs(self):
        a = [_A(workout_type=None, distance_m=10000, duration_s=3000)]
        b = [_A(workout_type=None, distance_m=10000, duration_s=3000)]
        rows = _aggregate_workout_type_compare(a, b)
        assert rows == []
