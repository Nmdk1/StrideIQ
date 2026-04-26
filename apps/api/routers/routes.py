"""Athlete routes endpoints (Phase 2 of comparison family).

Surfaces the canonical routes built by the route fingerprint service so
the frontend can list / browse them, attach an athlete-supplied name
(Phase 3 UX), and pull the run history for a given route.

Suppression discipline: never returns a route the athlete didn't run.
Cross-athlete reads are blocked. If the athlete has no routes, returns
``{"routes": []}`` — no fake data, no placeholders.
"""

from __future__ import annotations

from collections import Counter
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from models import Activity, Athlete, AthleteRoute

router = APIRouter(prefix="/v1/routes", tags=["routes"])


class RouteSummary(BaseModel):
    id: str
    name: Optional[str] = None
    display_name: str  # athlete-set name, or auto-generated default
    run_count: int
    distance_p50_m: Optional[int] = None
    distance_min_m: Optional[int] = None
    distance_max_m: Optional[int] = None
    centroid_lat: Optional[float] = None
    centroid_lng: Optional[float] = None
    first_seen_at: Optional[str] = None
    last_seen_at: Optional[str] = None
    dominant_workout_type: Optional[str] = None


class RouteListResponse(BaseModel):
    routes: List[RouteSummary]


class RouteRenameRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)


class RouteActivityEntry(BaseModel):
    id: str
    start_time: Optional[str] = None
    distance_m: Optional[int] = None
    duration_s: Optional[int] = None
    avg_hr: Optional[int] = None
    workout_type: Optional[str] = None
    temperature_f: Optional[float] = None
    dew_point_f: Optional[float] = None
    heat_adjustment_pct: Optional[float] = None
    name: Optional[str] = None


class RouteDetailResponse(BaseModel):
    route: RouteSummary
    activities: List[RouteActivityEntry]


# Default-name dictionary tuned to the founder's data shape — short
# distance buckets get "loop", longer get "long-run route", marathon-ish
# get "race-distance route". Athlete can always override.
def _auto_display_name(r: AthleteRoute, dominant_type: Optional[str] = None) -> str:
    d_m = r.distance_p50_m or 0
    d_km = d_m / 1000.0
    if d_km <= 0:
        return "Untitled route"
    # Distance bucket
    if d_km < 8:
        descriptor = "loop"
    elif d_km < 16:
        descriptor = "route"
    elif d_km < 26:
        descriptor = "long-run route"
    elif d_km < 36:
        descriptor = "marathon-distance route"
    else:
        descriptor = "ultra-distance route"
    # Workout-type hint when dominant
    type_prefix = ""
    if dominant_type in {"interval_workout", "track_workout", "vo2max_intervals"}:
        type_prefix = "track "
    elif dominant_type in {"threshold_run", "tempo_run"}:
        type_prefix = "tempo "
    elif dominant_type in {"long_run", "medium_long_run"}:
        type_prefix = "long-run "
    if type_prefix and descriptor.startswith("long-run"):
        # avoid "long-run long-run"
        type_prefix = ""
    return f"{d_km:.1f} km {type_prefix}{descriptor}".strip()


def _dominant_workout_type(db: Session, route_id) -> Optional[str]:
    """Return the most common non-null workout_type for the route, or None."""
    rows = (
        db.query(Activity.workout_type, func.count(Activity.id))
        .filter(
            Activity.route_id == route_id,
            Activity.workout_type.is_not(None),
        )
        .group_by(Activity.workout_type)
        .all()
    )
    if not rows:
        return None
    counts = Counter({wt: int(c) for wt, c in rows if wt})
    if not counts:
        return None
    top, top_count = counts.most_common(1)[0]
    total = sum(counts.values())
    # Only call it dominant if it's at least 40% of typed runs
    if top_count / total >= 0.40:
        return top
    return None


def _route_to_summary(r: AthleteRoute, db: Optional[Session] = None) -> RouteSummary:
    dominant = _dominant_workout_type(db, r.id) if db is not None else None
    name = (r.name or "").strip() or None
    display = name or _auto_display_name(r, dominant)
    return RouteSummary(
        id=str(r.id),
        name=name,
        display_name=display,
        run_count=int(r.run_count or 0),
        distance_p50_m=r.distance_p50_m,
        distance_min_m=r.distance_min_m,
        distance_max_m=r.distance_max_m,
        centroid_lat=r.centroid_lat,
        centroid_lng=r.centroid_lng,
        first_seen_at=r.first_seen_at.isoformat() if r.first_seen_at else None,
        last_seen_at=r.last_seen_at.isoformat() if r.last_seen_at else None,
        dominant_workout_type=dominant,
    )


@router.get("", response_model=RouteListResponse)
def list_routes(
    min_runs: int = Query(default=2, ge=1, le=100),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RouteListResponse:
    """List the athlete's routes ordered by most-recently-run.

    Default ``min_runs=2`` filters out singletons — a route that has only
    been run once isn't useful for comparisons. Pass ``min_runs=1`` to
    see every fingerprint.
    """
    rows = (
        db.query(AthleteRoute)
        .filter(
            AthleteRoute.athlete_id == current_user.id,
            AthleteRoute.run_count >= min_runs,
        )
        .order_by(desc(AthleteRoute.last_seen_at))
        .limit(limit)
        .all()
    )
    return RouteListResponse(routes=[_route_to_summary(r, db) for r in rows])


@router.get("/{route_id}", response_model=RouteDetailResponse)
def get_route(
    route_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RouteDetailResponse:
    route = (
        db.query(AthleteRoute)
        .filter(
            AthleteRoute.id == route_id,
            AthleteRoute.athlete_id == current_user.id,
        )
        .first()
    )
    if route is None:
        raise HTTPException(status_code=404, detail="route not found")

    acts = (
        db.query(Activity)
        .filter(
            Activity.route_id == route_id,
            Activity.athlete_id == current_user.id,
        )
        .order_by(desc(Activity.start_time))
        .all()
    )

    entries = [
        RouteActivityEntry(
            id=str(a.id),
            start_time=a.start_time.isoformat() if a.start_time else None,
            distance_m=a.distance_m,
            duration_s=a.duration_s,
            avg_hr=a.avg_hr,
            workout_type=a.workout_type,
            temperature_f=a.temperature_f,
            dew_point_f=a.dew_point_f,
            heat_adjustment_pct=a.heat_adjustment_pct,
            name=a.name,
        )
        for a in acts
    ]
    return RouteDetailResponse(route=_route_to_summary(route, db), activities=entries)


@router.put("/{route_id}/name", response_model=RouteSummary)
def rename_route(
    route_id: UUID,
    body: RouteRenameRequest,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RouteSummary:
    route = (
        db.query(AthleteRoute)
        .filter(
            AthleteRoute.id == route_id,
            AthleteRoute.athlete_id == current_user.id,
        )
        .first()
    )
    if route is None:
        raise HTTPException(status_code=404, detail="route not found")
    name = (body.name or "").strip() or None
    route.name = name
    db.commit()
    db.refresh(route)
    return _route_to_summary(route, db)
