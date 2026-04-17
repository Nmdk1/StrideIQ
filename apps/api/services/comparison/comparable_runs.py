"""Find comparable runs for an activity (Phase 5).

Tier-based comparison. For a given activity, walk a priority hierarchy
of comparison "tiers" and surface the strongest tier with data:

    1. ``same_route_anniversary``   — same route, 1 year ago ± 30 days,
                                       within heat/dew tolerance
    2. ``same_route_recent``        — last 5 runs on the same route
    3. ``same_type_current_block``  — same workout type, in the current
                                       training block
    4. ``same_type_similar_cond``   — same workout type, last 90 days,
                                       within heat/dew/elevation tolerance

Suppression is the default: never invent a tier. If no comparables exist
in a tier, that tier is omitted (and listed in ``suppressions`` for
transparency). Heat-adjusted pace requires both compared activities to
have temp + dew populated; otherwise raw pace is shown without a "heat
context" label.

Designed for fast (one-DB-roundtrip-per-tier) execution. The output is
deliberately structured so the frontend can render any tier as a
horizontal strip + per-comparable visual delta panel without further
joins.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from models import Activity, AthleteRoute, TrainingBlock
from services.blocks.block_detector import QUALITY_TYPES

logger = logging.getLogger(__name__)


# Tolerances — explicit constants so they're testable.
HEAT_TEMP_TOLERANCE_F = 5.0
HEAT_DEW_TOLERANCE_F = 5.0
ELEVATION_TOLERANCE = 0.20  # ±20% of elevation_gain_m
DISTANCE_TOLERANCE = 0.15  # ±15% for "same workout shape"
DEFAULT_TRAILING_DAYS = 90
ANNIVERSARY_WINDOW_DAYS = 30
SAME_ROUTE_RECENT_LIMIT = 5
SAME_TYPE_LIMIT = 5
SIMILAR_DISTANCE_LIMIT = 5
SIMILAR_DISTANCE_TRAILING_DAYS = 60


# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------


@dataclass
class ComparableEntry:
    activity_id: str
    start_time: Optional[str]
    distance_m: Optional[int]
    duration_s: Optional[int]
    avg_pace_s_per_km: Optional[float]
    avg_hr: Optional[int]
    workout_type: Optional[str]
    name: Optional[str]
    route_id: Optional[str]
    route_display_name: Optional[str]
    temperature_f: Optional[float]
    dew_point_f: Optional[float]
    elevation_gain_m: Optional[float]
    days_ago: Optional[int]
    in_tolerance_heat: bool
    in_tolerance_elevation: bool
    delta_pace_s_per_km: Optional[float]  # vs the focus activity
    delta_hr_bpm: Optional[int]
    delta_distance_m: Optional[int]


@dataclass
class ComparableTier:
    kind: str
    label: str
    entries: List[ComparableEntry] = field(default_factory=list)


@dataclass
class ComparablesResult:
    activity_id: str
    activity_summary: Dict
    block_summary: Optional[Dict]
    tiers: List[ComparableTier] = field(default_factory=list)
    suppressions: List[Dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Utility: build a ComparableEntry from an Activity row + the focus activity
# ---------------------------------------------------------------------------


def _route_display_name(r: Optional[AthleteRoute]) -> Optional[str]:
    """Return the route's display name (athlete-set or auto)."""
    if r is None:
        return None
    name = (r.name or "").strip() or None
    if name:
        return name
    # Lazy import to avoid circulars
    from routers.routes import _auto_display_name
    return _auto_display_name(r, None)


def _avg_pace_s_per_km(distance_m: Optional[float], duration_s: Optional[float]) -> Optional[float]:
    if not distance_m or not duration_s or distance_m <= 0:
        return None
    km = float(distance_m) / 1000.0
    return float(duration_s) / km


def _days_ago(when: Optional[datetime], focus_time: Optional[datetime]) -> Optional[int]:
    if when is None or focus_time is None:
        return None
    a = when if isinstance(when, datetime) else datetime.combine(when, datetime.min.time(), tzinfo=timezone.utc)
    b = focus_time if isinstance(focus_time, datetime) else datetime.combine(focus_time, datetime.min.time(), tzinfo=timezone.utc)
    if a.tzinfo is None:
        a = a.replace(tzinfo=timezone.utc)
    if b.tzinfo is None:
        b = b.replace(tzinfo=timezone.utc)
    return (b.date() - a.date()).days


def _heat_in_tolerance(focus: Activity, candidate: Activity) -> bool:
    """Both temps + dews must be present and within tolerance."""
    if focus.temperature_f is None or candidate.temperature_f is None:
        return False
    if focus.dew_point_f is None or candidate.dew_point_f is None:
        return False
    if abs(focus.temperature_f - candidate.temperature_f) > HEAT_TEMP_TOLERANCE_F:
        return False
    if abs(focus.dew_point_f - candidate.dew_point_f) > HEAT_DEW_TOLERANCE_F:
        return False
    return True


def _elevation_in_tolerance(focus: Activity, candidate: Activity) -> bool:
    """Elevation gain within ±20% if both populated; ``False`` if either missing
    (suppression discipline — never claim "same elevation" without evidence)."""
    f_raw = focus.total_elevation_gain
    c_raw = candidate.total_elevation_gain
    if f_raw is None or c_raw is None:
        return False
    f = float(f_raw or 0)
    c = float(c_raw or 0)
    if f == 0 and c == 0:
        return True
    if f == 0:
        return False
    return abs(c - f) / f <= ELEVATION_TOLERANCE


def _to_entry(
    candidate: Activity,
    focus: Activity,
    route_lookup: Dict[UUID, AthleteRoute],
) -> ComparableEntry:
    cand_pace = _avg_pace_s_per_km(candidate.distance_m, candidate.duration_s)
    focus_pace = _avg_pace_s_per_km(focus.distance_m, focus.duration_s)
    delta_pace = (
        cand_pace - focus_pace if cand_pace is not None and focus_pace is not None else None
    )
    delta_hr = (
        int(candidate.avg_hr) - int(focus.avg_hr)
        if candidate.avg_hr is not None and focus.avg_hr is not None
        else None
    )
    delta_distance = (
        int(candidate.distance_m) - int(focus.distance_m)
        if candidate.distance_m is not None and focus.distance_m is not None
        else None
    )
    route = route_lookup.get(candidate.route_id) if candidate.route_id else None
    return ComparableEntry(
        activity_id=str(candidate.id),
        start_time=candidate.start_time.isoformat() if candidate.start_time else None,
        distance_m=int(candidate.distance_m) if candidate.distance_m else None,
        duration_s=int(candidate.duration_s) if candidate.duration_s else None,
        avg_pace_s_per_km=cand_pace,
        avg_hr=int(candidate.avg_hr) if candidate.avg_hr else None,
        workout_type=candidate.workout_type,
        name=candidate.name,
        route_id=str(candidate.route_id) if candidate.route_id else None,
        route_display_name=_route_display_name(route),
        temperature_f=float(candidate.temperature_f) if candidate.temperature_f is not None else None,
        dew_point_f=float(candidate.dew_point_f) if candidate.dew_point_f is not None else None,
        elevation_gain_m=float(candidate.total_elevation_gain) if candidate.total_elevation_gain is not None else None,
        days_ago=_days_ago(candidate.start_time, focus.start_time),
        in_tolerance_heat=_heat_in_tolerance(focus, candidate),
        in_tolerance_elevation=_elevation_in_tolerance(focus, candidate),
        delta_pace_s_per_km=delta_pace,
        delta_hr_bpm=delta_hr,
        delta_distance_m=delta_distance,
    )


# ---------------------------------------------------------------------------
# Tier finders
# ---------------------------------------------------------------------------


def _tier_anniversary(
    db: Session,
    focus: Activity,
    route_lookup: Dict[UUID, AthleteRoute],
) -> List[ComparableEntry]:
    """Same route, ~1 year ago (±30 days), in heat tolerance."""
    if focus.route_id is None or focus.start_time is None:
        return []
    target = focus.start_time.date() - timedelta(days=365)
    lo = target - timedelta(days=ANNIVERSARY_WINDOW_DAYS)
    hi = target + timedelta(days=ANNIVERSARY_WINDOW_DAYS)
    rows = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == focus.athlete_id,
            Activity.route_id == focus.route_id,
            Activity.id != focus.id,
            Activity.sport == "run",
            Activity.start_time >= datetime.combine(lo, datetime.min.time(), tzinfo=timezone.utc),
            Activity.start_time <= datetime.combine(hi, datetime.max.time(), tzinfo=timezone.utc),
        )
        .order_by(Activity.start_time.asc())
        .all()
    )
    # Heat tolerance is a soft filter — surface even if not in tolerance
    # so the UI can show "different conditions" honestly.
    return [_to_entry(a, focus, route_lookup) for a in rows]


def _tier_same_route_recent(
    db: Session,
    focus: Activity,
    route_lookup: Dict[UUID, AthleteRoute],
) -> List[ComparableEntry]:
    """Last N runs on the same route (excluding focus, excluding anniversary
    window so we don't double-show)."""
    if focus.route_id is None:
        return []
    rows = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == focus.athlete_id,
            Activity.route_id == focus.route_id,
            Activity.id != focus.id,
            Activity.sport == "run",
        )
        .order_by(Activity.start_time.desc())
        .limit(SAME_ROUTE_RECENT_LIMIT)
        .all()
    )
    return [_to_entry(a, focus, route_lookup) for a in rows]


def _current_block_for_activity(db: Session, focus: Activity) -> Optional[TrainingBlock]:
    if focus.start_time is None:
        return None
    d = focus.start_time.date() if isinstance(focus.start_time, datetime) else focus.start_time
    return (
        db.query(TrainingBlock)
        .filter(
            TrainingBlock.athlete_id == focus.athlete_id,
            TrainingBlock.start_date <= d,
            TrainingBlock.end_date >= d,
        )
        .first()
    )


def _tier_same_type_current_block(
    db: Session,
    focus: Activity,
    block: Optional[TrainingBlock],
    route_lookup: Dict[UUID, AthleteRoute],
) -> List[ComparableEntry]:
    if block is None or not focus.workout_type:
        return []
    rows = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == focus.athlete_id,
            Activity.workout_type == focus.workout_type,
            Activity.id != focus.id,
            Activity.sport == "run",
            Activity.start_time
            >= datetime.combine(block.start_date, datetime.min.time(), tzinfo=timezone.utc),
            Activity.start_time
            <= datetime.combine(block.end_date, datetime.max.time(), tzinfo=timezone.utc),
        )
        .order_by(Activity.start_time.desc())
        .limit(SAME_TYPE_LIMIT)
        .all()
    )
    return [_to_entry(a, focus, route_lookup) for a in rows]


def _tier_similar_distance(
    db: Session,
    focus: Activity,
    route_lookup: Dict[UUID, AthleteRoute],
    *,
    trailing_days: int = SIMILAR_DISTANCE_TRAILING_DAYS,
) -> List[ComparableEntry]:
    """Trailing N runs within DISTANCE_TOLERANCE of the focus run.

    This is the always-available fallback. It deliberately does NOT require
    workout_type, route_id, training block, or weather match -- those are
    the gates that silently emptied tiers 1-4 for every Garmin-primary
    athlete and made the Compare tab look broken to the entire population.

    For any athlete who has done at least one other run within ±15% of this
    distance in the last N days, this tier returns something. It is the
    contractual floor for the Compare panel: if it returns empty, the
    athlete genuinely does not have a comparable run, and the empty-state
    in the UI is honest rather than a hidden tier-gate failure.
    """
    if focus.distance_m is None or focus.start_time is None:
        return []
    focus_distance = float(focus.distance_m)
    if focus_distance <= 0:
        return []
    distance_floor = focus_distance * (1 - DISTANCE_TOLERANCE)
    distance_ceiling = focus_distance * (1 + DISTANCE_TOLERANCE)
    since = focus.start_time - timedelta(days=trailing_days)
    rows = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == focus.athlete_id,
            Activity.id != focus.id,
            Activity.sport == "run",
            Activity.start_time >= since,
            Activity.start_time < focus.start_time,
            Activity.distance_m >= distance_floor,
            Activity.distance_m <= distance_ceiling,
        )
        .order_by(Activity.start_time.desc())
        .limit(SIMILAR_DISTANCE_LIMIT * 3)
        .all()
    )
    return [_to_entry(a, focus, route_lookup) for a in rows[:SIMILAR_DISTANCE_LIMIT]]


def _tier_same_type_similar_cond(
    db: Session,
    focus: Activity,
    route_lookup: Dict[UUID, AthleteRoute],
    *,
    trailing_days: int = DEFAULT_TRAILING_DAYS,
) -> List[ComparableEntry]:
    """Same workout type, in last N days, within heat tolerance (when temps
    available). Excludes runs already in earlier tiers."""
    if not focus.workout_type or focus.start_time is None:
        return []
    since = focus.start_time - timedelta(days=trailing_days)
    rows = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == focus.athlete_id,
            Activity.workout_type == focus.workout_type,
            Activity.id != focus.id,
            Activity.sport == "run",
            Activity.start_time >= since,
            Activity.start_time < focus.start_time,
        )
        .order_by(Activity.start_time.desc())
        .limit(SAME_TYPE_LIMIT * 3)  # filter then trim
        .all()
    )
    # Soft-filter to heat tolerance when both have weather; otherwise keep.
    candidates = []
    for a in rows:
        if (
            focus.temperature_f is not None
            and a.temperature_f is not None
            and not _heat_in_tolerance(focus, a)
        ):
            continue
        candidates.append(a)
        if len(candidates) >= SAME_TYPE_LIMIT:
            break
    return [_to_entry(a, focus, route_lookup) for a in candidates]


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------


def _activity_summary(a: Activity, route: Optional[AthleteRoute]) -> Dict:
    return {
        "id": str(a.id),
        "start_time": a.start_time.isoformat() if a.start_time else None,
        "distance_m": int(a.distance_m) if a.distance_m else None,
        "duration_s": int(a.duration_s) if a.duration_s else None,
        "avg_pace_s_per_km": _avg_pace_s_per_km(a.distance_m, a.duration_s),
        "avg_hr": int(a.avg_hr) if a.avg_hr else None,
        "workout_type": a.workout_type,
        "name": a.name,
        "route_id": str(a.route_id) if a.route_id else None,
        "route_display_name": _route_display_name(route),
        "temperature_f": float(a.temperature_f) if a.temperature_f is not None else None,
        "dew_point_f": float(a.dew_point_f) if a.dew_point_f is not None else None,
        "elevation_gain_m": float(a.total_elevation_gain) if a.total_elevation_gain is not None else None,
    }


def _block_summary(b: Optional[TrainingBlock]) -> Optional[Dict]:
    if b is None:
        return None
    return {
        "id": str(b.id),
        "phase": b.phase,
        "start_date": b.start_date.isoformat(),
        "end_date": b.end_date.isoformat(),
        "weeks": int(b.weeks or 0),
        "total_distance_m": int(b.total_distance_m or 0),
        "run_count": int(b.run_count or 0),
        "quality_pct": int(b.quality_pct or 0),
        "peak_week_distance_m": int(b.peak_week_distance_m or 0),
        "goal_event_name": b.goal_event_name,
    }


def find_comparables_for_activity(
    db: Session,
    activity_id: UUID,
) -> Optional[ComparablesResult]:
    """Compute the comparable-runs result for one activity.

    Returns ``None`` if the activity does not exist. Returns a result
    with ``tiers=[]`` and a populated ``suppressions`` list when there
    is nothing to compare (transparency over silence).
    """
    focus = db.query(Activity).filter(Activity.id == activity_id).first()
    if focus is None:
        return None

    # Pre-load the routes referenced by all candidate activities — saves
    # N+1 in _route_display_name.
    route_ids = set()
    if focus.route_id:
        route_ids.add(focus.route_id)
    # We can't know all candidate route_ids without running the queries
    # first; the route lookup will be filled lazily by per-tier finders
    # via a single bulk query at the end.
    route_lookup: Dict[UUID, AthleteRoute] = {}
    if route_ids:
        for r in db.query(AthleteRoute).filter(AthleteRoute.id.in_(route_ids)).all():
            route_lookup[r.id] = r

    block = _current_block_for_activity(db, focus)

    tiers: List[ComparableTier] = []
    suppressions: List[Dict] = []

    # Tier 1 — anniversary
    anniv = _tier_anniversary(db, focus, route_lookup)
    if anniv:
        tiers.append(
            ComparableTier(
                kind="same_route_anniversary",
                label="Same route, one year ago",
                entries=anniv,
            )
        )
    else:
        suppressions.append(
            {
                "kind": "same_route_anniversary",
                "reason": (
                    "no run on this route in the ±30-day window one year ago"
                    if focus.route_id
                    else "this run has no route fingerprint"
                ),
            }
        )

    # Tier 2 — same route recent
    seen_ids = {e.activity_id for tier in tiers for e in tier.entries}
    recent = [e for e in _tier_same_route_recent(db, focus, route_lookup) if e.activity_id not in seen_ids]
    if recent:
        tiers.append(
            ComparableTier(
                kind="same_route_recent",
                label="Recent runs on this route",
                entries=recent,
            )
        )
    elif focus.route_id is None:
        suppressions.append(
            {
                "kind": "same_route_recent",
                "reason": "this run has no route fingerprint (treadmill / no GPS)",
            }
        )

    # Tier 3 — same workout type in current block
    seen_ids.update(e.activity_id for tier in tiers for e in tier.entries)
    same_block = [
        e
        for e in _tier_same_type_current_block(db, focus, block, route_lookup)
        if e.activity_id not in seen_ids
    ]
    if same_block:
        wt = focus.workout_type or "this type"
        tiers.append(
            ComparableTier(
                kind="same_type_current_block",
                label=f"Other {wt.replace('_', ' ')} sessions in this block",
                entries=same_block,
            )
        )
    elif block is None:
        suppressions.append(
            {
                "kind": "same_type_current_block",
                "reason": "no detected training block at this date",
            }
        )

    # Tier 4 — same type, similar conditions, last 90 days
    seen_ids.update(e.activity_id for tier in tiers for e in tier.entries)
    sim_cond = [
        e
        for e in _tier_same_type_similar_cond(db, focus, route_lookup)
        if e.activity_id not in seen_ids
    ]
    if sim_cond:
        wt = focus.workout_type or "this type"
        # Be honest about whether heat tolerance was applied.
        applied_heat = focus.temperature_f is not None and focus.dew_point_f is not None
        suffix = " in similar conditions" if applied_heat else ""
        tiers.append(
            ComparableTier(
                kind="same_type_similar_cond",
                label=f"Recent {wt.replace('_', ' ')}{suffix}",
                entries=sim_cond,
            )
        )
    elif not focus.workout_type:
        suppressions.append(
            {
                "kind": "same_type_similar_cond",
                "reason": "this run has no workout type",
            }
        )

    # Tier 5 — always-available fallback: trailing same-distance runs.
    # The other four tiers gate on workout_type, route_id, anniversary, or
    # current block.  When all four are absent (a non-classified easy run on
    # a never-repeated route for a new athlete with no detected block) the
    # panel used to render empty for the entire population.  This tier has
    # only one gate -- the focus run has a positive distance -- so the panel
    # is empty if and only if the athlete has zero other runs of similar
    # distance in the last 60 days.
    seen_ids.update(e.activity_id for tier in tiers for e in tier.entries)
    similar_distance = [
        e
        for e in _tier_similar_distance(db, focus, route_lookup)
        if e.activity_id not in seen_ids
    ]
    if similar_distance and focus.distance_m:
        focus_km = float(focus.distance_m) / 1000.0
        tiers.append(
            ComparableTier(
                kind="similar_distance",
                label=f"Recent runs around {focus_km:.1f} km",
                entries=similar_distance,
            )
        )

    return ComparablesResult(
        activity_id=str(focus.id),
        activity_summary=_activity_summary(
            focus, route_lookup.get(focus.route_id) if focus.route_id else None
        ),
        block_summary=_block_summary(block),
        tiers=tiers,
        suppressions=suppressions,
    )
