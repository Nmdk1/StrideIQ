"""Strength v1 manual logging API.

Routes:

- ``GET    /v1/strength/sessions``                   list recent sessions
- ``POST   /v1/strength/sessions``                   create a new manual session
- ``GET    /v1/strength/sessions/{activity_id}``     read one session w/ active sets
- ``PATCH  /v1/strength/sessions/{activity_id}/sets/{set_id}``  edit a set (supersede)
- ``DELETE /v1/strength/sessions/{activity_id}``     archive (sport=strength_archived)
- ``GET    /v1/strength/sessions/{activity_id}/edit-history``    full edit graph
- ``GET    /v1/strength/exercises``                  search the taxonomy + recent

Every route is gated behind the ``strength.v1`` feature flag. When the
flag is off for an athlete, every route returns 404 (not 403) so the
feature is invisible — there is no "you don't have access to this"
banner that would tip the surface's existence.

Edits are non-destructive (see ``docs/specs/STRENGTH_V1_SCOPE.md`` §5.1):
patching a set inserts a new row whose ``superseded_by_id`` points at
the predecessor, and the old row gets ``superseded_at`` stamped. The
default read path filters ``superseded_at IS NULL``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from core.feature_flags import is_feature_enabled
from models import Activity, Athlete, StrengthExerciseSet, StrengthRoutine
from schemas_strength_v1 import (
    ExercisePickerEntry,
    ExercisePickerResponse,
    StrengthSessionCreate,
    StrengthSessionListItem,
    StrengthSessionResponse,
    StrengthSetCreate,
    StrengthSetResponse,
    StrengthSetUpdate,
)
from services.strength_taxonomy import (
    MOVEMENT_PATTERN_MAP,
    estimate_1rm,
    is_unilateral,
    lookup_movement_pattern,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/strength", tags=["strength_v1"])

STRENGTH_V1_FLAG = "strength.v1"


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _require_strength_v1(athlete_id: UUID, db: Session) -> None:
    """Block every route when the flag is off for this athlete.

    404 (not 403) is intentional: the surface should not exist for an
    athlete who isn't in the rollout — no "upgrade to access" prompt,
    no leaky existence signal.
    """
    if not is_feature_enabled(STRENGTH_V1_FLAG, str(athlete_id), db):
        raise HTTPException(status_code=404, detail="Not found")


def _set_payload_to_kwargs(
    payload: StrengthSetCreate,
    set_order: int,
    activity_id: UUID,
    athlete_id: UUID,
    source: str,
) -> dict:
    """Translate a manual-log payload into ``StrengthExerciseSet`` columns.

    Movement-pattern + unilateral are looked up via the taxonomy at write
    time (matches Garmin ingest semantics). e1RM is computed via Epley
    when reps + weight are present.
    """
    name = payload.exercise_name
    pattern, muscle = lookup_movement_pattern(name)
    return {
        "id": uuid4(),
        "activity_id": activity_id,
        "athlete_id": athlete_id,
        "set_order": set_order,
        "exercise_name_raw": name,
        "exercise_category": name,
        "movement_pattern": pattern,
        "muscle_group": muscle,
        "is_unilateral": is_unilateral(name),
        "set_type": payload.set_type,
        "reps": payload.reps,
        "weight_kg": payload.weight_kg,
        "duration_s": payload.duration_s,
        "estimated_1rm_kg": estimate_1rm(payload.weight_kg, payload.reps),
        "rpe": payload.rpe,
        "implement_type": payload.implement_type,
        "set_modifier": payload.set_modifier,
        "tempo": payload.tempo,
        "notes": payload.notes,
        "source": source,
        "manually_augmented": True,
    }


def _active_sets(db: Session, activity_id: UUID) -> List[StrengthExerciseSet]:
    """Sets for an activity, current rows only (superseded_at IS NULL)."""
    return (
        db.query(StrengthExerciseSet)
        .filter(
            StrengthExerciseSet.activity_id == activity_id,
            StrengthExerciseSet.superseded_at.is_(None),
        )
        .order_by(StrengthExerciseSet.set_order)
        .all()
    )


def _session_summary(
    activity: Activity, sets: List[StrengthExerciseSet]
) -> tuple[int, Optional[float], List[str]]:
    """Compute (set_count, total_volume_kg, movement_patterns)."""
    active = [s for s in sets if s.set_type == "active"]
    set_count = len(active)
    total_volume = None
    if active:
        vol = 0.0
        any_volume = False
        for s in active:
            if s.weight_kg is not None and s.reps is not None:
                vol += float(s.weight_kg) * int(s.reps)
                any_volume = True
        total_volume = vol if any_volume else None
    patterns_seen: List[str] = []
    for s in active:
        if s.movement_pattern and s.movement_pattern not in patterns_seen:
            patterns_seen.append(s.movement_pattern)
    return set_count, total_volume, patterns_seen


def _to_session_response(
    activity: Activity, sets: List[StrengthExerciseSet]
) -> StrengthSessionResponse:
    set_count, total_volume, patterns = _session_summary(activity, sets)
    return StrengthSessionResponse(
        id=activity.id,
        athlete_id=activity.athlete_id,
        start_time=activity.start_time,
        duration_s=activity.duration_s,
        name=activity.name,
        sport=activity.sport,
        source=activity.source,
        sets=[StrengthSetResponse.model_validate(s) for s in sets],
        set_count=set_count,
        total_volume_kg=total_volume,
        movement_patterns=patterns,
    )


def _bump_routine_usage(
    db: Session, routine_id: Optional[UUID], athlete_id: UUID
) -> None:
    if routine_id is None:
        return
    routine = (
        db.query(StrengthRoutine)
        .filter(
            StrengthRoutine.id == routine_id,
            StrengthRoutine.athlete_id == athlete_id,
        )
        .first()
    )
    if not routine:
        return
    routine.times_used = (routine.times_used or 0) + 1
    routine.last_used_at = datetime.now(timezone.utc)


# ---------------------------------------------------------------------
# Sessions: create / read / list / archive
# ---------------------------------------------------------------------


@router.post(
    "/sessions",
    response_model=StrengthSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_strength_session(
    payload: StrengthSessionCreate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StrengthSessionResponse:
    """Log a strength session manually.

    Creates one ``Activity`` row (sport=strength, source=manual) plus one
    ``StrengthExerciseSet`` row per set in payload.sets. Returns the
    full session as it reads back.
    """
    _require_strength_v1(current_user.id, db)

    start_time = payload.start_time or datetime.now(timezone.utc)
    activity = Activity(
        id=uuid4(),
        athlete_id=current_user.id,
        name=payload.name,
        start_time=start_time,
        sport="strength",
        source="manual",
        duration_s=payload.duration_s,
    )
    db.add(activity)
    db.flush()

    rows = []
    for idx, set_payload in enumerate(payload.sets, start=1):
        kwargs = _set_payload_to_kwargs(
            set_payload,
            set_order=idx,
            activity_id=activity.id,
            athlete_id=current_user.id,
            source="manual",
        )
        rows.append(StrengthExerciseSet(**kwargs))
    db.add_all(rows)

    _bump_routine_usage(db, payload.routine_id, current_user.id)

    db.commit()
    db.refresh(activity)

    sets = _active_sets(db, activity.id)
    return _to_session_response(activity, sets)


@router.get(
    "/sessions",
    response_model=List[StrengthSessionListItem],
)
def list_strength_sessions(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[StrengthSessionListItem]:
    """Recent strength sessions for the current athlete, newest first."""
    _require_strength_v1(current_user.id, db)

    activities = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == current_user.id,
            Activity.sport == "strength",
        )
        .order_by(Activity.start_time.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    out: List[StrengthSessionListItem] = []
    for act in activities:
        sets = _active_sets(db, act.id)
        set_count, total_volume, patterns = _session_summary(act, sets)
        out.append(
            StrengthSessionListItem(
                id=act.id,
                start_time=act.start_time,
                duration_s=act.duration_s,
                name=act.name,
                set_count=set_count,
                total_volume_kg=total_volume,
                movement_patterns=patterns,
            )
        )
    return out


@router.get(
    "/sessions/{activity_id}",
    response_model=StrengthSessionResponse,
)
def get_strength_session(
    activity_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StrengthSessionResponse:
    _require_strength_v1(current_user.id, db)

    activity = (
        db.query(Activity)
        .filter(
            Activity.id == activity_id,
            Activity.athlete_id == current_user.id,
        )
        .first()
    )
    if not activity or activity.sport != "strength":
        raise HTTPException(status_code=404, detail="Strength session not found")

    sets = _active_sets(db, activity.id)
    return _to_session_response(activity, sets)


@router.delete(
    "/sessions/{activity_id}",
    status_code=status.HTTP_200_OK,
)
def archive_strength_session(
    activity_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Soft-archive a manual strength session.

    The Activity row stays in the DB; sport flips to ``strength_archived``
    so it stops showing in the recent-sessions list and stops feeding the
    correlation engine. We never hard-delete athlete-logged data.
    """
    _require_strength_v1(current_user.id, db)

    activity = (
        db.query(Activity)
        .filter(
            Activity.id == activity_id,
            Activity.athlete_id == current_user.id,
        )
        .first()
    )
    if not activity or activity.sport != "strength":
        raise HTTPException(status_code=404, detail="Strength session not found")
    if activity.source != "manual":
        # Archiving a Garmin-ingested session would silently desync future
        # syncs. Athletes can edit details on Garmin sessions but can't
        # archive them through this surface.
        raise HTTPException(
            status_code=400,
            detail="Garmin-ingested sessions cannot be archived from here.",
        )

    activity.sport = "strength_archived"
    db.commit()
    return {"status": "archived", "activity_id": str(activity.id)}


# ---------------------------------------------------------------------
# Set edit (supersede semantics)
# ---------------------------------------------------------------------


@router.patch(
    "/sessions/{activity_id}/sets/{set_id}",
    response_model=StrengthSessionResponse,
)
def edit_strength_set(
    activity_id: UUID,
    set_id: UUID,
    payload: StrengthSetUpdate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StrengthSessionResponse:
    """Edit a single set non-destructively.

    Implementation:
      1. Look up the active set row (must belong to the athlete + activity).
      2. Build a new row from the existing fields, overlaid with payload
         deltas. The taxonomy lookup is re-run on the (unchanged) name in
         case the taxonomy itself has been updated since the original
         write — keeps movement_pattern accurate.
      3. Insert the new row, point its ``superseded_by_id`` at NULL (it
         is the new head of the chain).
      4. Stamp the OLD row: ``superseded_at = now()`` and
         ``superseded_by_id = new_row.id``.
      5. Flip ``manually_augmented = true`` on the new row regardless of
         the original source. If the predecessor was ``garmin``, the new
         row's source becomes ``garmin_then_manual_edit``.
    """
    _require_strength_v1(current_user.id, db)

    activity = (
        db.query(Activity)
        .filter(
            Activity.id == activity_id,
            Activity.athlete_id == current_user.id,
        )
        .first()
    )
    if not activity or activity.sport != "strength":
        raise HTTPException(status_code=404, detail="Strength session not found")

    old_set = (
        db.query(StrengthExerciseSet)
        .filter(
            StrengthExerciseSet.id == set_id,
            StrengthExerciseSet.activity_id == activity_id,
            StrengthExerciseSet.athlete_id == current_user.id,
            StrengthExerciseSet.superseded_at.is_(None),
        )
        .first()
    )
    if not old_set:
        raise HTTPException(status_code=404, detail="Set not found or already edited")

    delta = payload.model_dump(exclude_unset=True)

    new_reps = delta.get("reps", old_set.reps)
    new_weight_kg = delta.get("weight_kg", old_set.weight_kg)
    new_source = (
        "garmin_then_manual_edit"
        if old_set.source in ("garmin", "garmin_then_manual_edit")
        else "manual"
    )

    pattern, muscle = lookup_movement_pattern(old_set.exercise_name_raw)

    new_set = StrengthExerciseSet(
        id=uuid4(),
        activity_id=activity_id,
        athlete_id=current_user.id,
        set_order=old_set.set_order,
        exercise_name_raw=old_set.exercise_name_raw,
        exercise_category=old_set.exercise_category,
        movement_pattern=pattern,
        muscle_group=muscle,
        is_unilateral=is_unilateral(old_set.exercise_name_raw),
        set_type=old_set.set_type,
        reps=new_reps,
        weight_kg=new_weight_kg,
        duration_s=delta.get("duration_s", old_set.duration_s),
        estimated_1rm_kg=estimate_1rm(new_weight_kg, new_reps),
        rpe=delta.get("rpe", old_set.rpe),
        implement_type=delta.get("implement_type", old_set.implement_type),
        set_modifier=delta.get("set_modifier", old_set.set_modifier),
        tempo=delta.get("tempo", old_set.tempo),
        notes=delta.get("notes", old_set.notes),
        source=new_source,
        manually_augmented=True,
    )
    db.add(new_set)
    db.flush()

    old_set.superseded_by_id = new_set.id
    old_set.superseded_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(activity)

    sets = _active_sets(db, activity_id)
    return _to_session_response(activity, sets)


@router.get("/sessions/{activity_id}/edit-history")
def get_strength_session_edit_history(
    activity_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Return the full set-edit graph for an activity (audit surface).

    Returns every row, active or superseded, ordered by ``set_order`` then
    ``created_at``. The frontend can render an "edit history" timeline.
    """
    _require_strength_v1(current_user.id, db)

    activity = (
        db.query(Activity)
        .filter(
            Activity.id == activity_id,
            Activity.athlete_id == current_user.id,
        )
        .first()
    )
    if not activity or activity.sport != "strength":
        raise HTTPException(status_code=404, detail="Strength session not found")

    rows = (
        db.query(StrengthExerciseSet)
        .filter(StrengthExerciseSet.activity_id == activity_id)
        .order_by(
            StrengthExerciseSet.set_order,
            StrengthExerciseSet.created_at,
        )
        .all()
    )
    return {
        "activity_id": str(activity_id),
        "rows": [
            {
                "id": str(r.id),
                "set_order": r.set_order,
                "exercise_name": r.exercise_name_raw,
                "reps": r.reps,
                "weight_kg": float(r.weight_kg) if r.weight_kg is not None else None,
                "rpe": r.rpe,
                "implement_type": r.implement_type,
                "source": r.source,
                "manually_augmented": r.manually_augmented,
                "superseded_by_id": str(r.superseded_by_id) if r.superseded_by_id else None,
                "superseded_at": r.superseded_at.isoformat() if r.superseded_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------
# Exercise picker
# ---------------------------------------------------------------------


@router.get(
    "/exercises",
    response_model=ExercisePickerResponse,
)
def search_strength_exercises(
    q: Optional[str] = Query(default=None, min_length=0, max_length=120),
    limit: int = Query(default=30, ge=1, le=100),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExercisePickerResponse:
    """Search the canonical taxonomy and return recent exercises.

    Search is case-insensitive substring match against the canonical
    exercise name (UPPER_SNAKE). The "recent" list is the unique
    exercise names from the athlete's last 50 active sets, newest first
    — drives the two-tap-repeat UX in §6.1.
    """
    _require_strength_v1(current_user.id, db)

    query = (q or "").strip().upper().replace(" ", "_")
    matched: List[ExercisePickerEntry] = []
    for name, (pattern, muscle) in MOVEMENT_PATTERN_MAP.items():
        if not query or query in name:
            matched.append(
                ExercisePickerEntry(
                    name=name,
                    movement_pattern=pattern,
                    muscle_group=muscle,
                    is_unilateral=is_unilateral(name),
                )
            )
        if len(matched) >= limit:
            break

    recent_names = (
        db.query(StrengthExerciseSet.exercise_name_raw)
        .filter(
            StrengthExerciseSet.athlete_id == current_user.id,
            StrengthExerciseSet.superseded_at.is_(None),
            StrengthExerciseSet.set_type == "active",
        )
        .order_by(StrengthExerciseSet.created_at.desc())
        .limit(50)
        .all()
    )
    seen: List[str] = []
    recent: List[ExercisePickerEntry] = []
    for (n,) in recent_names:
        if not n or n in seen:
            continue
        seen.append(n)
        pattern, muscle = lookup_movement_pattern(n)
        recent.append(
            ExercisePickerEntry(
                name=n,
                movement_pattern=pattern,
                muscle_group=muscle,
                is_unilateral=is_unilateral(n),
            )
        )

    return ExercisePickerResponse(query=q, results=matched, recent=recent)


# ---------------------------------------------------------------------
# Garmin-reconciliation nudges (read-only)
# ---------------------------------------------------------------------


@router.get("/nudges")
def get_strength_nudges(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Return Garmin strength activities in the last 7 days that look
    incomplete, so the home card can offer to fill in details.

    A session is "incomplete" when ALL of:
      - sport == 'strength'
      - source != 'manual'   (came from Garmin)
      - manually_augmented == False on every active set
      - active set count < 3 (sparse — see SPARSE_SET_THRESHOLD)

    The card is dismissible client-side (localStorage). We do not
    persist dismissals server-side in v1; the next sweep will resurface
    a session only if it is still sparse.
    """
    _require_strength_v1(current_user.id, db)

    from datetime import datetime, timedelta, timezone as tz
    from sqlalchemy import func

    cutoff = datetime.now(tz.utc) - timedelta(days=7)

    set_count_sq = (
        db.query(
            StrengthExerciseSet.activity_id.label("aid"),
            func.count(StrengthExerciseSet.id).label("n"),
            func.bool_or(StrengthExerciseSet.manually_augmented).label("touched"),
        )
        .filter(
            StrengthExerciseSet.athlete_id == current_user.id,
            StrengthExerciseSet.superseded_at.is_(None),
            StrengthExerciseSet.set_type == "active",
        )
        .group_by(StrengthExerciseSet.activity_id)
        .subquery()
    )

    rows = (
        db.query(Activity, set_count_sq.c.n, set_count_sq.c.touched)
        .outerjoin(set_count_sq, set_count_sq.c.aid == Activity.id)
        .filter(
            Activity.athlete_id == current_user.id,
            Activity.sport == "strength",
            Activity.source != "manual",
            Activity.start_time >= cutoff,
        )
        .order_by(Activity.start_time.desc())
        .all()
    )

    nudges: List[dict] = []
    for activity, n, touched in rows:
        if touched:
            continue
        n_int = int(n or 0)
        if n_int >= 3:
            continue
        nudges.append(
            {
                "activity_id": str(activity.id),
                "start_time": activity.start_time.isoformat()
                if activity.start_time
                else None,
                "name": activity.name,
                "duration_s": activity.duration_s,
                "current_set_count": n_int,
                "source": activity.source,
            }
        )

    return {"count": len(nudges), "nudges": nudges}
