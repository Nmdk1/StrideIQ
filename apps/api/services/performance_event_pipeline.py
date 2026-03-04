"""
Performance Event Pipeline — Racing Fingerprint Phase 1A

Scans an athlete's activities, identifies race events through multiple
signals, creates PerformanceEvents with training state and block signatures.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models import Activity, Athlete, PerformanceEvent
from services.effort_classification import classify_effort_bulk
from services.performance_engine import (
    RACE_DISTANCES,
    detect_race_candidate,
    calculate_age_graded_performance,
    calculate_age_at_date,
)
from services.personal_best import get_distance_category
from services.rpi_calculator import calculate_rpi_from_race_time
from services.training_load import TrainingLoadCalculator

logger = logging.getLogger(__name__)

LOOKBACK_WEEKS = {
    'mile': 8, '5k': 8,
    '10k': 12, '15k': 12,
    'half_marathon': 14,
    'marathon': 18,
    '50k': 20,
}


def populate_performance_events(
    athlete_id: UUID,
    db: Session,
) -> dict:
    """
    Scan all non-duplicate activities at standard distances.
    Create PerformanceEvents for qualifying races.

    Sources (in priority order):
    1. Activities where user_verified_race == True
    2. Activities where strava_workout_type_raw == 3
    3. Activities where detect_race_candidate() returns confidence >= 0.3
    """
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        raise ValueError(f"Athlete {athlete_id} not found")

    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_duplicate == False,  # noqa: E712
        Activity.distance_m.isnot(None),
        Activity.distance_m > 0,
        Activity.duration_s.isnot(None),
        Activity.duration_s > 0,
    ).order_by(Activity.start_time).all()

    existing_event_activity_ids = set(
        row[0] for row in db.query(PerformanceEvent.activity_id).filter(
            PerformanceEvent.athlete_id == athlete_id
        ).all()
    )

    load_svc = TrainingLoadCalculator(db)

    events_created = 0
    events_updated = 0

    for act in activities:
        if act.id in existing_event_activity_ids:
            continue

        dist_m = float(act.distance_m)
        dist_cat = get_distance_category(dist_m)
        if not dist_cat:
            continue

        # Determine detection source and confidence
        detection_source = None
        detection_confidence = None
        user_confirmed = None

        if act.user_verified_race is True:
            detection_source = 'user_verified'
            detection_confidence = 1.0
            user_confirmed = True
        elif getattr(act, 'strava_workout_type_raw', None) == 3:
            detection_source = 'strava_tag'
            detection_confidence = 0.9
            user_confirmed = None
        else:
            _is_race, conf = detect_race_candidate(
                activity_pace=act.pace_per_mile,
                max_hr=act.max_hr,
                avg_hr=act.avg_hr,
                splits=[],
                distance_meters=dist_m,
                duration_seconds=act.duration_s,
                activity_name=act.name,
            )
            if conf < 0.3:
                continue
            detection_source = 'algorithm'
            detection_confidence = conf
            user_confirmed = True if conf >= 0.7 else None

        event_date = act.start_time.date()
        time_seconds = act.duration_s

        pace_per_mile = act.pace_per_mile

        rpi = calculate_rpi_from_race_time(dist_m, time_seconds)

        perf_pct = None
        if pace_per_mile and athlete.birthdate:
            age = calculate_age_at_date(athlete.birthdate, act.start_time)
            perf_pct = calculate_age_graded_performance(
                actual_pace_per_mile=pace_per_mile,
                age=age,
                sex=athlete.sex,
                distance_meters=dist_m,
            )

        # Training state
        ctl = atl = tsb = None
        try:
            state = load_svc.compute_training_state_history(
                athlete_id, target_dates=[event_date]
            )
            if event_date in state:
                ls = state[event_date]
                ctl = ls.current_ctl
                atl = ls.current_atl
                tsb = ls.current_tsb
        except Exception as e:
            logger.warning("Failed to compute training state for %s: %s", act.id, e)

        # Block signature
        block_sig = None
        try:
            block_sig = compute_block_signature(
                activity_id=act.id,
                event_date=event_date,
                distance_category=dist_cat,
                athlete_id=athlete_id,
                db=db,
            )
        except Exception as e:
            logger.warning("Failed to compute block signature for %s: %s", act.id, e)

        # fitness_relative_performance is intentionally None until a CTL→RPI
        # linear model can be fitted (requires 8+ confirmed races with both values).
        # The column stores actual_rpi / predicted_rpi, not rpi / ctl.

        event = PerformanceEvent(
            athlete_id=athlete_id,
            activity_id=act.id,
            distance_category=dist_cat,
            event_date=event_date,
            event_type='race',
            time_seconds=time_seconds,
            pace_per_mile=pace_per_mile,
            rpi_at_event=rpi,
            performance_percentage=perf_pct,
            is_personal_best=False,
            ctl_at_event=ctl,
            atl_at_event=atl,
            tsb_at_event=tsb,
            block_signature=block_sig,
            detection_source=detection_source,
            detection_confidence=detection_confidence,
            user_confirmed=user_confirmed,
        )
        db.add(event)
        events_created += 1

    db.flush()

    _mark_personal_bests(athlete_id, db)
    _classify_race_roles(athlete_id, db)

    return {"events_created": events_created, "events_updated": events_updated}


def _mark_personal_bests(athlete_id: UUID, db: Session) -> None:
    """Mark the fastest PerformanceEvent per distance category as PB."""
    events = db.query(PerformanceEvent).filter(
        PerformanceEvent.athlete_id == athlete_id,
        PerformanceEvent.user_confirmed == True,  # noqa: E712
    ).all()

    best_by_cat: Dict[str, PerformanceEvent] = {}
    for ev in events:
        cat = ev.distance_category
        if cat not in best_by_cat or ev.time_seconds < best_by_cat[cat].time_seconds:
            best_by_cat[cat] = ev

    for ev in events:
        should_be_pb = (ev.id == best_by_cat.get(ev.distance_category, object()).id)
        if ev.is_personal_best != should_be_pb:
            ev.is_personal_best = should_be_pb


def _classify_race_roles(athlete_id: UUID, db: Session) -> None:
    """Infer race roles (a_race, tune_up, training_race) from proximity."""
    events = db.query(PerformanceEvent).filter(
        PerformanceEvent.athlete_id == athlete_id,
        PerformanceEvent.user_confirmed == True,  # noqa: E712
    ).order_by(PerformanceEvent.event_date).all()

    for ev in events:
        if ev.user_classified_role:
            continue
        ev.race_role = classify_race_role(ev, events)


def classify_race_role(
    event: PerformanceEvent,
    all_events: List[PerformanceEvent],
) -> str:
    """
    Infer race_role from proximity and distance hierarchy.

    - Two races within 8 weeks, second is equal/longer distance →
      first is 'tune_up'
    - Only race in its distance category within 12 weeks → 'a_race'
    - Default: 'unknown'
    """
    DIST_ORDER = {
        'mile': 1, '5k': 2, '10k': 3, '15k': 4,
        '25k': 5, 'half_marathon': 6, 'marathon': 7, '50k': 8,
    }

    my_rank = DIST_ORDER.get(event.distance_category, 0)
    my_date = event.event_date

    for other in all_events:
        if other.id == event.id:
            continue
        delta = (other.event_date - my_date).days
        if 7 <= delta <= 56:
            other_rank = DIST_ORDER.get(other.distance_category, 0)
            if other_rank >= my_rank:
                return 'tune_up'

    nearby = [
        e for e in all_events
        if e.id != event.id
        and abs((e.event_date - my_date).days) <= 84
        and e.distance_category == event.distance_category
    ]
    if not nearby:
        return 'a_race'

    return 'unknown'


def compute_block_signature(
    activity_id: UUID,
    event_date: date,
    distance_category: str,
    athlete_id: UUID,
    db: Session,
) -> dict:
    """
    Compute the training block signature leading up to an event.

    Lookback window scales with distance. Classifies effort for all
    activities in the window, then aggregates weekly volume, intensity,
    long runs, and quality sessions.
    """
    weeks = LOOKBACK_WEEKS.get(distance_category, 12)
    start = event_date - timedelta(weeks=weeks)

    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_duplicate == False,  # noqa: E712
        Activity.start_time >= start,
        Activity.start_time < event_date,
        Activity.distance_m.isnot(None),
        Activity.distance_m > 0,
    ).order_by(Activity.start_time).all()

    if not activities:
        return {
            "lookback_weeks": weeks,
            "total_activities": 0,
            "weekly_volumes_km": [],
            "intensity_distribution": {"easy": 0, "moderate": 0, "hard": 0},
            "peak_volume_week": None,
            "taper_start_week": None,
            "long_run_max_km": None,
            "quality_sessions": 0,
        }

    effort_map = classify_effort_bulk(activities, athlete_id, db)

    weekly_data: Dict[int, dict] = {}
    for act in activities:
        act_date = act.start_time.date()
        week_num = (event_date - act_date).days // 7
        if week_num not in weekly_data:
            weekly_data[week_num] = {
                "volume_m": 0, "activities": 0,
                "easy": 0, "moderate": 0, "hard": 0,
                "long_run_m": 0,
            }
        w = weekly_data[week_num]
        dist = float(act.distance_m) if act.distance_m else 0
        w["volume_m"] += dist
        w["activities"] += 1
        effort = effort_map.get(act.id, "easy")
        w[effort] = w.get(effort, 0) + 1
        if dist > w["long_run_m"]:
            w["long_run_m"] = dist

    weekly_volumes_km = []
    total_easy = total_mod = total_hard = 0
    peak_vol = 0
    peak_vol_week = None
    quality_sessions = 0

    for wk in range(weeks, 0, -1):
        wd = weekly_data.get(wk, {
            "volume_m": 0, "activities": 0,
            "easy": 0, "moderate": 0, "hard": 0, "long_run_m": 0,
        })
        vol_km = round(wd["volume_m"] / 1000, 1)
        weekly_volumes_km.append(vol_km)
        total_easy += wd["easy"]
        total_mod += wd["moderate"]
        total_hard += wd["hard"]
        quality_sessions += wd["moderate"] + wd["hard"]
        if vol_km > peak_vol:
            peak_vol = vol_km
            peak_vol_week = weeks - wk

    # Detect taper: first week where volume drops > 20% from peak, sustained
    taper_start = None
    if peak_vol > 0:
        for i, v in enumerate(weekly_volumes_km):
            if i > (peak_vol_week or 0) and v < peak_vol * 0.8:
                taper_start = i
                break

    total_sessions = total_easy + total_mod + total_hard
    long_run_max_km = max(
        (float(wd.get("long_run_m", 0)) for wd in weekly_data.values()),
        default=0,
    ) / 1000

    return {
        "lookback_weeks": weeks,
        "total_activities": len(activities),
        "weekly_volumes_km": weekly_volumes_km,
        "intensity_distribution": {
            "easy": round(total_easy / total_sessions, 2) if total_sessions else 0,
            "moderate": round(total_mod / total_sessions, 2) if total_sessions else 0,
            "hard": round(total_hard / total_sessions, 2) if total_sessions else 0,
        },
        "peak_volume_week": peak_vol_week,
        "peak_volume_km": peak_vol,
        "taper_start_week": taper_start,
        "long_run_max_km": round(long_run_max_km, 1),
        "quality_sessions": quality_sessions,
    }
