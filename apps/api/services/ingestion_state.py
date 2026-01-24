"""
Durable ingestion state service (operational visibility).

Goals:
- Store last task/run metadata per (athlete, provider)
- Record last error deterministically (no log scraping)
- Keep this write path lightweight and safe to call from Celery tasks
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session

from models import AthleteIngestionState


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_or_create_state(db: Session, athlete_id: UUID, provider: str) -> AthleteIngestionState:
    state = (
        db.query(AthleteIngestionState)
        .filter(AthleteIngestionState.athlete_id == athlete_id, AthleteIngestionState.provider == provider)
        .first()
    )
    if state:
        return state
    state = AthleteIngestionState(athlete_id=athlete_id, provider=provider)
    db.add(state)
    db.flush()
    return state


def mark_best_efforts_started(db: Session, athlete_id: UUID, provider: str, task_id: str) -> None:
    state = _get_or_create_state(db, athlete_id, provider)
    state.last_best_efforts_task_id = task_id
    state.last_best_efforts_started_at = _utcnow()
    state.last_best_efforts_finished_at = None
    state.last_best_efforts_status = "running"
    state.last_best_efforts_error = None
    state.last_best_efforts_retry_after_s = None
    # Clear any prior deferral when work resumes.
    state.deferred_until = None
    state.deferred_reason = None
    db.add(state)


def mark_best_efforts_finished(db: Session, athlete_id: UUID, provider: str, result: Dict[str, Any]) -> None:
    state = _get_or_create_state(db, athlete_id, provider)
    state.last_best_efforts_finished_at = _utcnow()

    rate_limited = bool(result.get("rate_limited", False))
    state.last_best_efforts_status = "rate_limited" if rate_limited else "success"
    state.last_best_efforts_error = None
    state.last_best_efforts_retry_after_s = result.get("retry_after_s")
    state.last_best_efforts_activities_checked = result.get("activities_checked")
    state.last_best_efforts_efforts_stored = result.get("efforts_stored")
    state.last_best_efforts_pbs_created = result.get("pbs_created")
    # Completion clears deferral.
    state.deferred_until = None
    state.deferred_reason = None
    db.add(state)


def mark_best_efforts_error(db: Session, athlete_id: UUID, provider: str, error: str, task_id: Optional[str] = None) -> None:
    state = _get_or_create_state(db, athlete_id, provider)
    if task_id:
        state.last_best_efforts_task_id = task_id
    state.last_best_efforts_finished_at = _utcnow()
    state.last_best_efforts_status = "error"
    state.last_best_efforts_error = error
    db.add(state)


def mark_index_started(db: Session, athlete_id: UUID, provider: str, task_id: str) -> None:
    state = _get_or_create_state(db, athlete_id, provider)
    state.last_index_task_id = task_id
    state.last_index_started_at = _utcnow()
    state.last_index_finished_at = None
    state.last_index_status = "running"
    state.last_index_error = None
    # Clear any prior deferral when work resumes.
    state.deferred_until = None
    state.deferred_reason = None
    db.add(state)


def mark_index_finished(db: Session, athlete_id: UUID, provider: str, result: Dict[str, Any]) -> None:
    state = _get_or_create_state(db, athlete_id, provider)
    state.last_index_finished_at = _utcnow()
    state.last_index_status = "success" if result.get("status") == "success" else (result.get("status") or "success")
    state.last_index_error = None
    state.last_index_pages_fetched = result.get("pages_fetched")
    state.last_index_created = result.get("created")
    state.last_index_already_present = result.get("already_present")
    state.last_index_skipped_non_runs = result.get("skipped_non_runs")
    # Completion clears deferral.
    state.deferred_until = None
    state.deferred_reason = None
    db.add(state)


def mark_index_error(db: Session, athlete_id: UUID, provider: str, error: str, task_id: Optional[str] = None) -> None:
    state = _get_or_create_state(db, athlete_id, provider)
    if task_id:
        state.last_index_task_id = task_id
    state.last_index_finished_at = _utcnow()
    state.last_index_status = "error"
    state.last_index_error = error
    db.add(state)


def mark_ingestion_deferred(
    db: Session,
    athlete_id: UUID,
    provider: str,
    *,
    scope: str,
    deferred_until: datetime,
    reason: str,
    task_id: Optional[str] = None,
) -> None:
    """
    Phase 5: mark ingestion as intentionally deferred (e.g. rate limit, global pause).

    This must NOT be treated as an error.
    """
    state = _get_or_create_state(db, athlete_id, provider)
    state.deferred_until = deferred_until
    state.deferred_reason = reason

    if scope == "index":
        if task_id:
            state.last_index_task_id = task_id
        state.last_index_status = "deferred"
        state.last_index_error = None
    elif scope == "best_efforts":
        if task_id:
            state.last_best_efforts_task_id = task_id
        state.last_best_efforts_status = "deferred"
        state.last_best_efforts_error = None

    db.add(state)


@dataclass
class IngestionStateSnapshot:
    provider: str
    last_best_efforts_task_id: Optional[str]
    last_best_efforts_started_at: Optional[str]
    last_best_efforts_finished_at: Optional[str]
    last_best_efforts_status: Optional[str]
    last_best_efforts_error: Optional[str]
    last_best_efforts_retry_after_s: Optional[int]
    last_index_task_id: Optional[str]
    last_index_started_at: Optional[str]
    last_index_finished_at: Optional[str]
    last_index_status: Optional[str]
    last_index_error: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "last_best_efforts_task_id": self.last_best_efforts_task_id,
            "last_best_efforts_started_at": self.last_best_efforts_started_at,
            "last_best_efforts_finished_at": self.last_best_efforts_finished_at,
            "last_best_efforts_status": self.last_best_efforts_status,
            "last_best_efforts_error": self.last_best_efforts_error,
            "last_best_efforts_retry_after_s": self.last_best_efforts_retry_after_s,
            "last_index_task_id": self.last_index_task_id,
            "last_index_started_at": self.last_index_started_at,
            "last_index_finished_at": self.last_index_finished_at,
            "last_index_status": self.last_index_status,
            "last_index_error": self.last_index_error,
        }


def get_ingestion_state_snapshot(db: Session, athlete_id: UUID, provider: str = "strava") -> Optional[IngestionStateSnapshot]:
    state = (
        db.query(AthleteIngestionState)
        .filter(AthleteIngestionState.athlete_id == athlete_id, AthleteIngestionState.provider == provider)
        .first()
    )
    if not state:
        return None

    def iso(dt: Optional[datetime]) -> Optional[str]:
        return dt.isoformat() if dt else None

    return IngestionStateSnapshot(
        provider=state.provider,
        last_best_efforts_task_id=state.last_best_efforts_task_id,
        last_best_efforts_started_at=iso(state.last_best_efforts_started_at),
        last_best_efforts_finished_at=iso(state.last_best_efforts_finished_at),
        last_best_efforts_status=state.last_best_efforts_status,
        last_best_efforts_error=state.last_best_efforts_error,
        last_best_efforts_retry_after_s=state.last_best_efforts_retry_after_s,
        last_index_task_id=state.last_index_task_id,
        last_index_started_at=iso(state.last_index_started_at),
        last_index_finished_at=iso(state.last_index_finished_at),
        last_index_status=state.last_index_status,
        last_index_error=state.last_index_error,
    )

