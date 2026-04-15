"""Racing Fingerprint — Race curation API (Phase 1A)."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from core.auth import get_current_user, require_admin
from core.database import get_db
from models import Activity, Athlete, PerformanceEvent, AthleteFinding
from services.timezone_utils import get_athlete_timezone, get_athlete_timezone_from_db, to_athlete_local_date
from schemas_fingerprint import (
    BrowseResponse,
    RaceCard,
    RaceCandidateResponse,
    RacePin,
    RacingLifeStripData,
    RacingLifeStripResponse,
    WeekData,
    FingerprintFindingsResponse,
)
from services.fingerprint_analysis import (
    extract_fingerprint_findings,
    store_findings,
)
from services.performance_event_pipeline import (
    populate_performance_events,
    compute_block_signature,
)
from services.personal_best import DISTANCE_CATEGORIES
from services.training_load import TrainingLoadCalculator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/fingerprint", tags=["Fingerprint"])


def _format_pace(distance_m: float, duration_s: int, units: str = "imperial") -> str:
    """Format pace as min:ss/mi (imperial) or min:ss/km (metric)."""
    if not distance_m or not duration_s or distance_m <= 0:
        return "—"
    if units == "metric":
        divisor = distance_m / 1000
        label = "/km"
    else:
        divisor = distance_m / 1609.34
        label = "/mi"
    sec_per_unit = duration_s / divisor
    mins = int(sec_per_unit // 60)
    secs = int(sec_per_unit % 60)
    return f"{mins}:{secs:02d}{label}"


def _format_duration(seconds: int) -> str:
    """Format duration as H:MM:SS or MM:SS."""
    if not seconds:
        return "—"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _activity_to_card(
    act: Activity,
    event: Optional[PerformanceEvent] = None,
    units: str = "imperial",
    tz=None,
) -> RaceCard:
    dist_m = float(act.distance_m) if act.distance_m else 0
    from services.personal_best import get_distance_category
    dist_cat = get_distance_category(dist_m) or "unknown"

    time_of_day = None
    day_of_week = None
    if act.start_time:
        time_of_day = act.start_time.strftime("%-I:%M %p") if hasattr(act.start_time, 'strftime') else None
        try:
            time_of_day = act.start_time.strftime("%I:%M %p").lstrip("0")
        except Exception:
            pass
        day_of_week = act.start_time.strftime("%A") if hasattr(act.start_time, 'strftime') else None

    return RaceCard(
        event_id=event.id if event else None,
        activity_id=act.id,
        name=act.name,
        date=to_athlete_local_date(act.start_time, tz) if (act.start_time and tz) else (act.start_time.date() if act.start_time else None),
        time_of_day=time_of_day,
        day_of_week=day_of_week,
        distance_category=dist_cat,
        distance_meters=int(dist_m),
        pace_display=_format_pace(dist_m, act.duration_s, units),
        duration_display=_format_duration(act.duration_s),
        avg_hr=act.avg_hr,
        detection_confidence=event.detection_confidence if event else None,
        detection_source=event.detection_source if event else None,
        user_confirmed=event.user_confirmed if event else None,
        is_personal_best=event.is_personal_best if event else False,
    )


def _build_strip_data(athlete_id: UUID, db: Session) -> RacingLifeStripData:
    """Build the Racing Life Strip data for the athlete."""
    confirmed_events = db.query(PerformanceEvent).filter(
        PerformanceEvent.athlete_id == athlete_id,
        PerformanceEvent.user_confirmed == True,  # noqa: E712
    ).order_by(PerformanceEvent.event_date).all()

    pins = [
        RacePin(
            event_id=ev.id,
            date=ev.event_date,
            distance_category=ev.distance_category,
            time_seconds=ev.time_seconds,
            is_personal_best=ev.is_personal_best,
            performance_percentage=ev.performance_percentage,
        )
        for ev in confirmed_events
    ]

    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_duplicate == False,  # noqa: E712
        Activity.distance_m.isnot(None),
        Activity.distance_m > 0,
    ).order_by(Activity.start_time).all()

    _tz = get_athlete_timezone_from_db(db, athlete_id)
    weekly: dict = {}
    for act in activities:
        d = to_athlete_local_date(act.start_time, _tz)
        week_start = d - timedelta(days=d.weekday())
        if week_start not in weekly:
            weekly[week_start] = {"volume_m": 0, "count": 0}
        weekly[week_start]["volume_m"] += float(act.distance_m)
        weekly[week_start]["count"] += 1

    weeks = [
        WeekData(
            week_start=ws,
            total_volume_km=round(data["volume_m"] / 1000, 1),
            intensity="moderate",
            activity_count=data["count"],
        )
        for ws, data in sorted(weekly.items())
    ]

    return RacingLifeStripData(weeks=weeks, pins=pins)


@router.get("/race-candidates", response_model=RaceCandidateResponse)
async def get_race_candidates(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns three tiers for the discovery experience.
    Triggers pipeline if no PerformanceEvents exist yet.
    """
    event_count = db.query(PerformanceEvent).filter(
        PerformanceEvent.athlete_id == current_user.id,
    ).count()

    if event_count == 0:
        populate_performance_events(current_user.id, db)
        db.commit()

    rows = db.query(PerformanceEvent, Activity).join(
        Activity, PerformanceEvent.activity_id == Activity.id
    ).filter(
        PerformanceEvent.athlete_id == current_user.id,
    ).all()

    event_activity_ids = {ev.activity_id for ev, _ in rows}

    confirmed = []
    candidates = []

    for ev, act in rows:
        card = _activity_to_card(act, ev, units=current_user.preferred_units or "imperial", tz=get_athlete_timezone(current_user))

        if ev.user_confirmed is True or (ev.detection_confidence and ev.detection_confidence >= 0.7) or ev.detection_source in ('strava_tag', 'user_verified'):
            confirmed.append(card)
        elif ev.user_confirmed is None:
            candidates.append(card)

    from sqlalchemy import or_
    dist_filters = []
    for lo, hi in DISTANCE_CATEGORIES.values():
        dist_filters.append(
            (Activity.distance_m >= lo) & (Activity.distance_m <= hi)
        )
    browse_count = db.query(Activity).filter(
        Activity.athlete_id == current_user.id,
        Activity.is_duplicate == False,  # noqa: E712
        or_(*dist_filters) if dist_filters else True,
        ~Activity.id.in_(event_activity_ids) if event_activity_ids else True,
    ).count() if dist_filters else 0

    strip_data = _build_strip_data(current_user.id, db)

    return RaceCandidateResponse(
        confirmed=confirmed,
        candidates=candidates,
        browse_count=browse_count,
        strip_data=strip_data,
    )


@router.get("/browse", response_model=BrowseResponse)
async def browse_activities(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
    distance_category: Optional[str] = Query(None),
    day_of_week: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Tier 3 browse: activities at standard distances that don't have
    a PerformanceEvent yet. Sorted by pace (fastest first).
    Supports day_of_week filter: "saturday", "sunday", or "weekend".
    """
    from sqlalchemy import extract, or_

    event_activity_ids = set(
        row[0] for row in db.query(PerformanceEvent.activity_id).filter(
            PerformanceEvent.athlete_id == current_user.id,
        ).all()
    )

    q = db.query(Activity).filter(
        Activity.athlete_id == current_user.id,
        Activity.is_duplicate == False,  # noqa: E712
        Activity.distance_m.isnot(None),
        Activity.distance_m > 0,
        Activity.duration_s.isnot(None),
        Activity.duration_s > 0,
        ~Activity.id.in_(event_activity_ids) if event_activity_ids else True,
    )

    if distance_category and distance_category in DISTANCE_CATEGORIES:
        lo, hi = DISTANCE_CATEGORIES[distance_category]
        q = q.filter(Activity.distance_m >= lo, Activity.distance_m <= hi)
    else:
        dist_filters = []
        for lo, hi in DISTANCE_CATEGORIES.values():
            dist_filters.append(
                (Activity.distance_m >= lo) & (Activity.distance_m <= hi)
            )
        if dist_filters:
            q = q.filter(or_(*dist_filters))

    if day_of_week:
        dow = extract('dow', Activity.start_time)  # PostgreSQL: 0=Sun, 6=Sat
        dow_lower = day_of_week.lower()
        if dow_lower == 'weekend':
            q = q.filter(or_(dow == 0, dow == 6))
        elif dow_lower == 'saturday':
            q = q.filter(dow == 6)
        elif dow_lower == 'sunday':
            q = q.filter(dow == 0)

    total = q.count()

    # Sort by pace (fastest first = lowest duration/distance ratio)
    activities = q.order_by(
        (Activity.duration_s / Activity.distance_m).asc()
    ).offset(offset).limit(limit).all()

    units = current_user.preferred_units or "imperial"
    _tz = get_athlete_timezone(current_user)
    items = [_activity_to_card(act, units=units, tz=_tz) for act in activities]

    return BrowseResponse(items=items, total=total, offset=offset, limit=limit)


@router.post("/confirm-race/{event_id}")
async def confirm_race(
    event_id: UUID,
    confirmed: bool = Query(...),
    chip_time_seconds: Optional[int] = Query(None),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Athlete confirms (True) or rejects (False) a candidate race."""
    event = db.query(PerformanceEvent).filter(
        PerformanceEvent.id == event_id,
        PerformanceEvent.athlete_id == current_user.id,
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if confirmed:
        dupe = db.query(PerformanceEvent).filter(
            PerformanceEvent.athlete_id == current_user.id,
            PerformanceEvent.id != event_id,
            PerformanceEvent.event_date == event.event_date,
            PerformanceEvent.distance_category == event.distance_category,
            PerformanceEvent.user_confirmed == True,  # noqa: E712
        ).first()
        if dupe:
            event.user_confirmed = False
            event.detection_source = 'duplicate_rejected'
            db.commit()
            strip_data = _build_strip_data(current_user.id, db)
            return {"status": "duplicate_rejected", "kept_event_id": str(dupe.id), "strip_data": strip_data.model_dump()}

    event.user_confirmed = confirmed
    if confirmed:
        event.detection_source = 'user_verified'
        if chip_time_seconds:
            event.chip_time_seconds = chip_time_seconds
        if not event.block_signature:
            try:
                event.block_signature = compute_block_signature(
                    activity_id=event.activity_id,
                    event_date=event.event_date,
                    distance_category=event.distance_category,
                    athlete_id=current_user.id,
                    db=db,
                )
            except Exception as e:
                logger.warning("Block signature computation failed: %s", e)

    db.commit()

    strip_data = _build_strip_data(current_user.id, db)
    return {"status": "confirmed" if confirmed else "rejected", "strip_data": strip_data.model_dump()}


@router.post("/add-race/{activity_id}")
async def add_race(
    activity_id: UUID,
    chip_time_seconds: Optional[int] = Query(None),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Athlete identifies an activity as a race the system missed."""
    act = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.athlete_id == current_user.id,
    ).first()

    if not act:
        raise HTTPException(status_code=404, detail="Activity not found")

    existing = db.query(PerformanceEvent).filter(
        PerformanceEvent.athlete_id == current_user.id,
        PerformanceEvent.activity_id == activity_id,
    ).first()

    if existing:
        existing.user_confirmed = True
        existing.detection_source = 'user_added'
        if chip_time_seconds:
            existing.chip_time_seconds = chip_time_seconds
        db.commit()
        strip_data = _build_strip_data(current_user.id, db)
        return {"status": "updated", "event_id": str(existing.id), "strip_data": strip_data.model_dump()}

    from services.personal_best import get_distance_category
    from services.rpi_calculator import calculate_rpi_from_race_time

    dist_m = float(act.distance_m) if act.distance_m else 0
    dist_cat = get_distance_category(dist_m) or "unknown"
    event_date = to_athlete_local_date(act.start_time, get_athlete_timezone(current_user))

    dupe = db.query(PerformanceEvent).filter(
        PerformanceEvent.athlete_id == current_user.id,
        PerformanceEvent.event_date == event_date,
        PerformanceEvent.distance_category == dist_cat,
        PerformanceEvent.user_confirmed == True,  # noqa: E712
    ).first()
    if dupe:
        strip_data = _build_strip_data(current_user.id, db)
        return {"status": "duplicate_exists", "event_id": str(dupe.id), "strip_data": strip_data.model_dump()}

    rpi = calculate_rpi_from_race_time(dist_m, act.duration_s) if act.duration_s else None

    # Training state
    ctl = atl = tsb = None
    try:
        load_svc = TrainingLoadCalculator(db)
        state = load_svc.compute_training_state_history(
            current_user.id, target_dates=[event_date]
        )
        if event_date in state:
            ls = state[event_date]
            ctl, atl, tsb = ls.current_ctl, ls.current_atl, ls.current_tsb
    except Exception as e:
        logger.warning("Training state failed for add-race: %s", e)

    block_sig = None
    try:
        block_sig = compute_block_signature(
            activity_id=act.id,
            event_date=event_date,
            distance_category=dist_cat,
            athlete_id=current_user.id,
            db=db,
        )
    except Exception as e:
        logger.warning("Block signature failed for add-race: %s", e)

    event = PerformanceEvent(
        athlete_id=current_user.id,
        activity_id=activity_id,
        distance_category=dist_cat,
        event_date=event_date,
        event_type='race',
        time_seconds=act.duration_s,
        chip_time_seconds=chip_time_seconds,
        pace_per_mile=act.pace_per_mile,
        rpi_at_event=rpi,
        performance_percentage=act.performance_percentage,
        is_personal_best=False,
        ctl_at_event=ctl,
        atl_at_event=atl,
        tsb_at_event=tsb,
        block_signature=block_sig,
        detection_source='user_added',
        detection_confidence=1.0,
        user_confirmed=True,
    )
    db.add(event)
    db.commit()

    strip_data = _build_strip_data(current_user.id, db)
    return {"status": "created", "event_id": str(event.id), "strip_data": strip_data.model_dump()}


@router.get("/strip", response_model=RacingLifeStripResponse)
async def get_racing_life_strip(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns data for the Racing Life Strip visual."""
    strip_data = _build_strip_data(current_user.id, db)
    return RacingLifeStripResponse(strip_data=strip_data)


@router.get("/findings", response_model=FingerprintFindingsResponse)
async def get_fingerprint_findings(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns stored pattern extraction findings for the current athlete."""
    stored = db.query(AthleteFinding).filter(
        AthleteFinding.athlete_id == current_user.id,
        AthleteFinding.is_active == True,  # noqa: E712
    ).order_by(AthleteFinding.first_detected_at).all()
    return FingerprintFindingsResponse(findings=stored)


@router.post("/admin/extract/{athlete_id}")
async def admin_extract_findings(
    athlete_id: UUID,
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin trigger for pattern extraction and finding storage."""
    findings = extract_fingerprint_findings(athlete_id, db)
    stored_count = store_findings(athlete_id, findings, db)
    db.commit()

    return {
        "total_findings": len(findings),
        "stored": stored_count,
        "suppressed": len(findings) - stored_count,
        "findings": [
            {
                "type": f.finding_type,
                "confidence": f.confidence,
                "sentence": f.sentence,
            }
            for f in findings
        ],
    }


@router.post("/admin/populate/{athlete_id}")
async def admin_populate_events(
    athlete_id: UUID,
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin trigger for the population pipeline."""
    result = populate_performance_events(athlete_id, db)
    db.commit()
    return result
