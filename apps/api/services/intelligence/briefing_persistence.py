"""
Home briefing persistence (ADR-065 / Lane 2A corpus).

One-way write path: after the Celery task successfully generates a briefing
and writes it to Redis, this module also inserts a permanent row into
`coach_briefing` + `coach_briefing_input` so the system retains a corpus of
every materially-distinct briefing it has produced.

Rules (all enforced here, not at the call site):

  * Deterministic fallback briefs are skipped by default. Set
    PERSIST_DETERMINISTIC_BRIEFS=1 in the environment to opt them in.
  * Cache-refresh writes (fingerprint unchanged, no new LLM call) MUST NOT
    reach this module — the caller is responsible for that gate. Re-saving
    an unchanged fingerprint would pollute the corpus.
  * Idempotent against the UNIQUE index
    (athlete_id, data_fingerprint, date_trunc('minute', generated_at)).
    Duplicate inserts inside the same minute are collapsed into one row.
  * NEVER raises. Any failure is logged at WARNING and returns False so
    /v1/home stays healthy if the DB hiccups.

No reader in this module. The corpus earns its keep by being queryable
directly from psql until a first consumer is built.
"""

from __future__ import annotations

import logging
import os
from datetime import date as _date
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_DETERMINISTIC_SOURCES = {"deterministic_fallback"}


def _should_persist_source(briefing_source: str, source_model: str) -> bool:
    """Deterministic fallback briefs are skipped unless explicitly opted in."""
    if os.getenv("PERSIST_DETERMINISTIC_BRIEFS", "").strip() == "1":
        return True
    source = (briefing_source or "").strip().lower()
    model = (source_model or "").strip().lower()
    if source in _DETERMINISTIC_SOURCES:
        return False
    if "deterministic" in model:
        return False
    return True


def _coerce_uuid(value: Any) -> Optional[UUID]:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _coerce_sleep_h(checkin_data: Optional[Dict[str, Any]]) -> Optional[float]:
    if not isinstance(checkin_data, dict):
        return None
    for key in ("garmin_sleep_h", "sleep_h"):
        v = checkin_data.get(key)
        if v is None:
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return None


def persist_briefing(
    *,
    db: Session,
    athlete_id: str,
    athlete_local_date: _date,
    payload: Dict[str, Any],
    source_model: str,
    briefing_source: str,
    briefing_is_interim: bool,
    data_fingerprint: str,
    schema_version: int,
    prompt_text: str,
    today_completed: Optional[Dict[str, Any]],
    planned_workout: Optional[Dict[str, Any]],
    checkin_data: Optional[Dict[str, Any]],
    race_data: Optional[Dict[str, Any]],
    upcoming_plan: Optional[List[Dict[str, Any]]],
    findings_injected: Optional[List[Dict[str, Any]]],
    validation_flags: Optional[Dict[str, Any]] = None,
    generated_at: Optional[datetime] = None,
) -> bool:
    """
    Insert one CoachBriefing + CoachBriefingInput row pair.

    Returns True on a successful insert (or on a silently-collapsed duplicate
    under the unique index). Returns False on any failure. Never raises.
    """
    try:
        if not _should_persist_source(briefing_source, source_model):
            return False

        athlete_uuid = _coerce_uuid(athlete_id)
        if athlete_uuid is None:
            logger.warning(
                "persist_briefing: refusing to persist, invalid athlete_id=%r",
                athlete_id,
            )
            return False

        if not isinstance(payload, dict):
            logger.warning(
                "persist_briefing: refusing to persist, payload is not a dict (athlete=%s)",
                athlete_id,
            )
            return False

        if not isinstance(prompt_text, str) or not prompt_text:
            logger.warning(
                "persist_briefing: refusing to persist, empty prompt_text (athlete=%s)",
                athlete_id,
            )
            return False

        from models import CoachBriefing, CoachBriefingInput

        # Minute-truncated UTC copy feeds the unique index that deduplicates
        # same-minute retries. Kept naive (no tz) so the index comparison is
        # exact (the column is declared without timezone).
        from datetime import timezone as _tz
        if generated_at is not None:
            _utc = (
                generated_at.astimezone(_tz.utc)
                if generated_at.tzinfo
                else generated_at
            )
        else:
            _utc = datetime.now(tz=_tz.utc)
        generated_at_minute = _utc.replace(tzinfo=None, second=0, microsecond=0)

        briefing = CoachBriefing(
            athlete_id=athlete_uuid,
            athlete_local_date=athlete_local_date,
            generated_at_minute=generated_at_minute,
            data_fingerprint=str(data_fingerprint)[:32],
            source_model=str(source_model),
            briefing_source=str(briefing_source),
            briefing_is_interim=bool(briefing_is_interim),
            schema_version=int(schema_version),
            coach_noticed=payload.get("coach_noticed"),
            today_context=payload.get("today_context"),
            week_assessment=payload.get("week_assessment"),
            checkin_reaction=payload.get("checkin_reaction"),
            race_assessment=payload.get("race_assessment"),
            morning_voice=payload.get("morning_voice"),
            workout_why=payload.get("workout_why"),
            payload_json=payload,
            validation_flags=dict(validation_flags or {}),
        )
        if generated_at is not None:
            briefing.generated_at = generated_at

        input_snapshot = CoachBriefingInput(
            athlete_id=athlete_uuid,
            today_completed=today_completed,
            planned_workout=planned_workout,
            checkin_data=checkin_data,
            race_data=race_data,
            upcoming_plan=upcoming_plan,
            findings_injected=findings_injected,
            prompt_text=prompt_text,
            garmin_sleep_h=_coerce_sleep_h(checkin_data),
        )
        briefing.input_snapshot = input_snapshot

        db.add(briefing)
        try:
            db.commit()
        except IntegrityError:
            # Same-minute duplicate insert (unique index on
            # athlete_id + data_fingerprint + minute). This is the
            # expected idempotent no-op — treat as success.
            db.rollback()
            logger.info(
                "persist_briefing: duplicate briefing collapsed (athlete=%s, fp=%s)",
                athlete_id,
                data_fingerprint,
            )
            return True
        return True
    except Exception as e:  # noqa: BLE001 — hot path must not break
        logger.warning(
            "persist_briefing failed for athlete=%s: %s",
            athlete_id,
            e,
        )
        try:
            db.rollback()
        except Exception:
            pass
        return False
