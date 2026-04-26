"""Block-over-block comparison (Phase 7).

Compares two training blocks side by side. Surfaces:

- Aggregate deltas: total distance, run count, peak week, quality %,
  longest run, average pace by workout type.
- Week-by-week series: distance, quality runs, easy runs aligned by
  *position within the block* (week 1 vs week 1, week 2 vs week 2, …)
  so two blocks of different lengths can still be compared at the
  shape level. Truncated to the shorter block's length when computing
  deltas; full series returned for both.
- Per-workout-type comparison: for each shared workout type, total
  count, total distance, and average pace delta — answers "did my
  cruise intervals get faster from build A to build B?"

Suppression discipline: if the focus block has fewer than 2 weeks of
data, comparison is suppressed (not enough signal). If a candidate
"previous" block is not the same phase as focus, surface it with a
flag so the UI can label the comparison honestly ("comparing to
previous BUILD" vs "comparing to last BLOCK regardless of phase").
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models import Activity, TrainingBlock
from services.blocks.block_detector import EASY_TYPES, QUALITY_TYPES

logger = logging.getLogger(__name__)


@dataclass
class WeekStat:
    week_index: int  # 0-indexed week within the block
    iso_week_start: str  # YYYY-MM-DD of Monday
    total_distance_m: int
    run_count: int
    quality_count: int
    easy_count: int
    longest_run_m: int


@dataclass
class WorkoutTypeCompare:
    workout_type: str
    a_count: int
    b_count: int
    a_total_distance_m: int
    b_total_distance_m: int
    a_avg_pace_s_per_km: Optional[float]
    b_avg_pace_s_per_km: Optional[float]
    delta_pace_s_per_km: Optional[float]  # positive = block B is slower
    delta_count: int


@dataclass
class BlockCompareSide:
    id: str
    phase: str
    start_date: str
    end_date: str
    weeks: int
    total_distance_m: int
    total_duration_s: int
    run_count: int
    quality_pct: int
    peak_week_distance_m: int
    longest_run_m: Optional[int]
    dominant_workout_types: List[str]
    goal_event_name: Optional[str]
    week_series: List[WeekStat]


@dataclass
class BlockComparison:
    a: BlockCompareSide  # the "previous" / older block
    b: BlockCompareSide  # the "focus" / newer block
    same_phase: bool
    workout_type_compare: List[WorkoutTypeCompare]
    deltas: Dict[str, float]  # named deltas, b minus a
    suppressions: List[Dict[str, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _avg_pace_s_per_km(distance_m: int, duration_s: int) -> Optional[float]:
    if not distance_m or not duration_s or distance_m <= 0:
        return None
    return float(duration_s) / (float(distance_m) / 1000.0)


def _activities_in_block(db: Session, block: TrainingBlock) -> List[Activity]:
    return (
        db.query(Activity)
        .filter(
            Activity.athlete_id == block.athlete_id,
            Activity.sport == "run",
            Activity.start_time
            >= datetime.combine(block.start_date, datetime.min.time(), tzinfo=timezone.utc),
            Activity.start_time
            <= datetime.combine(block.end_date, datetime.max.time(), tzinfo=timezone.utc),
        )
        .order_by(Activity.start_time.asc())
        .all()
    )


def _compute_week_series(block: TrainingBlock, activities: List[Activity]) -> List[WeekStat]:
    """Bucket the block's activities into weekly aggregates indexed from
    block start. ISO weeks (Mon–Sun)."""
    if not activities:
        return [
            WeekStat(
                week_index=i,
                iso_week_start=(block.start_date + timedelta(weeks=i)).isoformat(),
                total_distance_m=0,
                run_count=0,
                quality_count=0,
                easy_count=0,
                longest_run_m=0,
            )
            for i in range(int(block.weeks or 0))
        ]

    # Map week_index -> aggregator
    series: Dict[int, Dict[str, int]] = defaultdict(
        lambda: {
            "distance": 0,
            "runs": 0,
            "quality": 0,
            "easy": 0,
            "longest": 0,
        }
    )
    block_start_monday = block.start_date - timedelta(days=block.start_date.weekday())
    for a in activities:
        if a.start_time is None:
            continue
        a_date = a.start_time.date() if isinstance(a.start_time, datetime) else a.start_time
        a_monday = a_date - timedelta(days=a_date.weekday())
        idx = (a_monday - block_start_monday).days // 7
        if idx < 0:
            continue
        d = int(a.distance_m or 0)
        bucket = series[idx]
        bucket["distance"] += d
        bucket["runs"] += 1
        if a.workout_type in QUALITY_TYPES:
            bucket["quality"] += 1
        elif a.workout_type in EASY_TYPES:
            bucket["easy"] += 1
        if d > bucket["longest"]:
            bucket["longest"] = d

    weeks_n = max(int(block.weeks or 0), max(series.keys(), default=-1) + 1)
    return [
        WeekStat(
            week_index=i,
            iso_week_start=(block_start_monday + timedelta(weeks=i)).isoformat(),
            total_distance_m=series[i]["distance"],
            run_count=series[i]["runs"],
            quality_count=series[i]["quality"],
            easy_count=series[i]["easy"],
            longest_run_m=series[i]["longest"],
        )
        for i in range(weeks_n)
    ]


def _aggregate_workout_type_compare(
    activities_a: List[Activity],
    activities_b: List[Activity],
) -> List[WorkoutTypeCompare]:
    def _bucket(acts: List[Activity]) -> Dict[str, Dict[str, float]]:
        out: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"count": 0, "distance": 0.0, "duration": 0.0}
        )
        for a in acts:
            if not a.workout_type:
                continue
            out[a.workout_type]["count"] += 1
            out[a.workout_type]["distance"] += float(a.distance_m or 0)
            out[a.workout_type]["duration"] += float(a.duration_s or 0)
        return out

    bucket_a = _bucket(activities_a)
    bucket_b = _bucket(activities_b)
    types = sorted(set(bucket_a) | set(bucket_b))

    rows: List[WorkoutTypeCompare] = []
    for wt in types:
        a = bucket_a.get(wt, {"count": 0, "distance": 0.0, "duration": 0.0})
        b = bucket_b.get(wt, {"count": 0, "distance": 0.0, "duration": 0.0})
        pace_a = _avg_pace_s_per_km(int(a["distance"]), int(a["duration"]))
        pace_b = _avg_pace_s_per_km(int(b["distance"]), int(b["duration"]))
        delta_pace = pace_b - pace_a if pace_a is not None and pace_b is not None else None
        rows.append(
            WorkoutTypeCompare(
                workout_type=wt,
                a_count=int(a["count"]),
                b_count=int(b["count"]),
                a_total_distance_m=int(a["distance"]),
                b_total_distance_m=int(b["distance"]),
                a_avg_pace_s_per_km=pace_a,
                b_avg_pace_s_per_km=pace_b,
                delta_pace_s_per_km=delta_pace,
                delta_count=int(b["count"]) - int(a["count"]),
            )
        )
    # Sort by combined volume so the dominant types in the comparison rise.
    rows.sort(key=lambda r: r.a_total_distance_m + r.b_total_distance_m, reverse=True)
    return rows


def _to_side(block: TrainingBlock, week_series: List[WeekStat]) -> BlockCompareSide:
    return BlockCompareSide(
        id=str(block.id),
        phase=block.phase,
        start_date=block.start_date.isoformat(),
        end_date=block.end_date.isoformat(),
        weeks=int(block.weeks or 0),
        total_distance_m=int(block.total_distance_m or 0),
        total_duration_s=int(block.total_duration_s or 0),
        run_count=int(block.run_count or 0),
        quality_pct=int(block.quality_pct or 0),
        peak_week_distance_m=int(block.peak_week_distance_m or 0),
        longest_run_m=block.longest_run_m,
        dominant_workout_types=list(block.dominant_workout_types or []),
        goal_event_name=block.goal_event_name,
        week_series=week_series,
    )


# ---------------------------------------------------------------------------
# top-level
# ---------------------------------------------------------------------------


def _find_previous_comparable(
    db: Session,
    focus: TrainingBlock,
    *,
    same_phase_only: bool = False,
) -> Optional[TrainingBlock]:
    """Return the most recent block strictly *before* focus.start_date, optionally
    restricted to the same phase."""
    q = (
        db.query(TrainingBlock)
        .filter(
            TrainingBlock.athlete_id == focus.athlete_id,
            TrainingBlock.start_date < focus.start_date,
            TrainingBlock.id != focus.id,
        )
    )
    if same_phase_only:
        q = q.filter(TrainingBlock.phase == focus.phase)
    return q.order_by(TrainingBlock.start_date.desc()).first()


def compare_blocks(
    db: Session,
    focus_block_id: UUID,
    against_block_id: Optional[UUID] = None,
    *,
    prefer_same_phase: bool = True,
) -> Optional[BlockComparison]:
    """Compare ``focus_block_id`` to either ``against_block_id`` or the most
    recent same-phase block before it (falling back to *any* previous block).

    Returns ``None`` if the focus block doesn't exist; returns a
    `BlockComparison` with empty `b.week_series` and a populated
    `suppressions` list when no comparable previous block can be found.
    """
    focus = db.query(TrainingBlock).filter(TrainingBlock.id == focus_block_id).first()
    if focus is None:
        return None

    if against_block_id is not None:
        prev = (
            db.query(TrainingBlock)
            .filter(
                TrainingBlock.id == against_block_id,
                TrainingBlock.athlete_id == focus.athlete_id,
            )
            .first()
        )
    else:
        prev = None
        if prefer_same_phase:
            prev = _find_previous_comparable(db, focus, same_phase_only=True)
        if prev is None:
            prev = _find_previous_comparable(db, focus, same_phase_only=False)

    activities_b = _activities_in_block(db, focus)
    week_series_b = _compute_week_series(focus, activities_b)

    if prev is None:
        return BlockComparison(
            a=BlockCompareSide(
                id="",
                phase="",
                start_date="",
                end_date="",
                weeks=0,
                total_distance_m=0,
                total_duration_s=0,
                run_count=0,
                quality_pct=0,
                peak_week_distance_m=0,
                longest_run_m=None,
                dominant_workout_types=[],
                goal_event_name=None,
                week_series=[],
            ),
            b=_to_side(focus, week_series_b),
            same_phase=False,
            workout_type_compare=[],
            deltas={},
            suppressions=[
                {
                    "kind": "previous_block",
                    "reason": "no earlier training block detected for this athlete",
                }
            ],
        )

    activities_a = _activities_in_block(db, prev)
    week_series_a = _compute_week_series(prev, activities_a)

    workout_compare = _aggregate_workout_type_compare(activities_a, activities_b)

    deltas: Dict[str, float] = {
        "total_distance_m": float(focus.total_distance_m or 0)
        - float(prev.total_distance_m or 0),
        "run_count": float(focus.run_count or 0) - float(prev.run_count or 0),
        "quality_pct": float(focus.quality_pct or 0) - float(prev.quality_pct or 0),
        "peak_week_distance_m": float(focus.peak_week_distance_m or 0)
        - float(prev.peak_week_distance_m or 0),
        "weeks": float(focus.weeks or 0) - float(prev.weeks or 0),
    }
    if focus.longest_run_m is not None and prev.longest_run_m is not None:
        deltas["longest_run_m"] = float(focus.longest_run_m) - float(prev.longest_run_m)

    suppressions: List[Dict[str, str]] = []
    if (focus.weeks or 0) < 2:
        suppressions.append(
            {
                "kind": "focus_too_short",
                "reason": "focus block has fewer than 2 weeks of data — comparison may not be meaningful",
            }
        )

    return BlockComparison(
        a=_to_side(prev, week_series_a),
        b=_to_side(focus, week_series_b),
        same_phase=(prev.phase == focus.phase),
        workout_type_compare=workout_compare,
        deltas=deltas,
        suppressions=suppressions,
    )
