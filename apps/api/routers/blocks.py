"""Training blocks endpoints (Phase 4 of comparison family).

Surfaces detected training blocks for athlete-facing block-over-block
views. Suppression: returns ``{"blocks": []}`` when nothing detected
(do NOT invent placeholder blocks).
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from models import Activity, Athlete, TrainingBlock

router = APIRouter(prefix="/v1/blocks", tags=["blocks"])


class BlockSummary(BaseModel):
    id: str
    start_date: date
    end_date: date
    weeks: int
    phase: str
    total_distance_m: int
    total_duration_s: int
    run_count: int
    peak_week_distance_m: int
    longest_run_m: Optional[int] = None
    quality_pct: int
    workout_type_counts: dict
    dominant_workout_types: List[str]
    goal_event_name: Optional[str] = None


class BlockListResponse(BaseModel):
    blocks: List[BlockSummary]


class BlockActivityEntry(BaseModel):
    id: str
    start_time: Optional[str] = None
    distance_m: Optional[int] = None
    duration_s: Optional[int] = None
    avg_hr: Optional[int] = None
    workout_type: Optional[str] = None
    name: Optional[str] = None


class BlockDetailResponse(BaseModel):
    block: BlockSummary
    activities: List[BlockActivityEntry]


def _to_summary(b: TrainingBlock) -> BlockSummary:
    return BlockSummary(
        id=str(b.id),
        start_date=b.start_date,
        end_date=b.end_date,
        weeks=int(b.weeks or 0),
        phase=b.phase,
        total_distance_m=int(b.total_distance_m or 0),
        total_duration_s=int(b.total_duration_s or 0),
        run_count=int(b.run_count or 0),
        peak_week_distance_m=int(b.peak_week_distance_m or 0),
        longest_run_m=b.longest_run_m,
        quality_pct=int(b.quality_pct or 0),
        workout_type_counts=dict(b.workout_type_counts or {}),
        dominant_workout_types=list(b.dominant_workout_types or []),
        goal_event_name=b.goal_event_name,
    )


@router.get("", response_model=BlockListResponse)
def list_blocks(
    phase: Optional[str] = Query(default=None, description="Filter to a single phase label."),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BlockListResponse:
    q = db.query(TrainingBlock).filter(TrainingBlock.athlete_id == current_user.id)
    if phase:
        q = q.filter(TrainingBlock.phase == phase)
    rows = q.order_by(desc(TrainingBlock.start_date)).limit(limit).all()
    return BlockListResponse(blocks=[_to_summary(b) for b in rows])


@router.get("/{block_id}/compare")
def compare_block(
    block_id: UUID,
    against: Optional[UUID] = Query(
        default=None,
        description=(
            "Block id to compare against. If omitted, the most recent prior "
            "block of the same phase is selected; falls back to any prior block."
        ),
    ),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Block-over-block periodization comparison.

    See ``services/comparison/block_comparison.py`` for selection
    rules and aggregation. Returns:

    ```
    {
      "a": { ...older block summary + week_series... },
      "b": { ...focus block summary + week_series... },
      "same_phase": bool,
      "workout_type_compare": [ ... ],
      "deltas": { "total_distance_m": ..., "run_count": ..., ... },
      "suppressions": [ ... ]
    }
    ```

    When no prior block exists, returns ``b`` populated and ``a`` empty
    with a `previous_block` suppression — the UI shows the focus
    standalone with an explicit "no previous block to compare yet"
    message rather than fabricating a comparison.
    """
    from dataclasses import asdict
    from services.comparison import compare_blocks

    focus = (
        db.query(TrainingBlock)
        .filter(
            TrainingBlock.id == block_id,
            TrainingBlock.athlete_id == current_user.id,
        )
        .first()
    )
    if focus is None:
        raise HTTPException(status_code=404, detail="block not found")

    if against is not None:
        peer = (
            db.query(TrainingBlock)
            .filter(
                TrainingBlock.id == against,
                TrainingBlock.athlete_id == current_user.id,
            )
            .first()
        )
        if peer is None:
            raise HTTPException(status_code=404, detail="against block not found")

    result = compare_blocks(db, block_id, against)
    if result is None:
        raise HTTPException(status_code=404, detail="block not found")

    return {
        "a": asdict(result.a),
        "b": asdict(result.b),
        "same_phase": result.same_phase,
        "workout_type_compare": [asdict(w) for w in result.workout_type_compare],
        "deltas": result.deltas,
        "suppressions": result.suppressions,
    }


@router.get("/{block_id}", response_model=BlockDetailResponse)
def get_block(
    block_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BlockDetailResponse:
    block = (
        db.query(TrainingBlock)
        .filter(
            TrainingBlock.id == block_id,
            TrainingBlock.athlete_id == current_user.id,
        )
        .first()
    )
    if block is None:
        raise HTTPException(status_code=404, detail="block not found")

    acts = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == current_user.id,
            Activity.sport == "run",
            Activity.start_time >= block.start_date,
            Activity.start_time
            <= block.end_date.isoformat() + " 23:59:59+00:00",
        )
        .order_by(Activity.start_time.asc())
        .all()
    )
    entries = [
        BlockActivityEntry(
            id=str(a.id),
            start_time=a.start_time.isoformat() if a.start_time else None,
            distance_m=a.distance_m,
            duration_s=a.duration_s,
            avg_hr=a.avg_hr,
            workout_type=a.workout_type,
            name=a.name,
        )
        for a in acts
    ]
    return BlockDetailResponse(block=_to_summary(block), activities=entries)
