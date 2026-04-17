"""Route fingerprinting service.

Goal: identify when an athlete is running the same physical course as a
prior activity, so the product can show year-over-year and trailing-N
comparisons on the same route.

Approach (intentionally boring):
    1. Walk the GPS track at uniform ~50m intervals.
    2. Encode each sampled point as a precision-7 geohash (~150m grid).
    3. The route fingerprint of an activity is the *set* of unique
       geohash cells. Direction-independent and tolerant to small GPS
       drift, but rejects non-overlapping courses.
    4. Two activities are "same route" when Jaccard(set_a, set_b) ≥ 0.6
       AND distance differs by ≤ 25%.

We deliberately avoid `python-geohash` as a dependency — the encoder is
~25 lines and the algorithm is a 1972 spec, no need for an external lib.

Suppression rules (per founder's "we never surface what we don't have"):
    - Track with <10 GPS points → no fingerprint (return None).
    - Track shorter than ~500m total → no fingerprint.
    - Distance prefilter excludes routes with >25% length difference.
    - Match requires Jaccard ≥ JACCARD_MATCH_THRESHOLD; otherwise we
      create a new route, never force a match.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Iterable, List, Optional, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from models import Activity, ActivityStream, AthleteRoute

GEOHASH_PRECISION = 7  # ~153m × 153m at the equator
SAMPLE_DISTANCE_M = 50.0  # cell side / 3 — guarantees coverage
JACCARD_MATCH_THRESHOLD = 0.6  # >=0.6 means same route
DISTANCE_TOLERANCE = 0.25  # routes must be within ±25% of each other's median
MIN_TRACK_POINTS = 10
MIN_TRACK_DISTANCE_M = 500.0

_GEOHASH_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"


# ---------------------------------------------------------------------------
# Geohash + geometry primitives
# ---------------------------------------------------------------------------


def encode_geohash(lat: float, lng: float, precision: int = GEOHASH_PRECISION) -> str:
    """Encode (lat, lng) as a base-32 geohash of the given precision.

    Pure-Python implementation of the standard geohash spec. Lat must be
    in [-90, 90] and lng in [-180, 180]; outside-range inputs are
    clamped because real GPS noise occasionally produces invalid points.
    """
    lat = max(-90.0, min(90.0, float(lat)))
    lng = max(-180.0, min(180.0, float(lng)))

    lat_lo, lat_hi = -90.0, 90.0
    lng_lo, lng_hi = -180.0, 180.0
    bits = []
    even = True
    while len(bits) < precision * 5:
        if even:
            mid = (lng_lo + lng_hi) / 2.0
            if lng >= mid:
                bits.append(1)
                lng_lo = mid
            else:
                bits.append(0)
                lng_hi = mid
        else:
            mid = (lat_lo + lat_hi) / 2.0
            if lat >= mid:
                bits.append(1)
                lat_lo = mid
            else:
                bits.append(0)
                lat_hi = mid
        even = not even

    out = []
    for i in range(0, len(bits), 5):
        chunk = bits[i : i + 5]
        idx = 0
        for b in chunk:
            idx = (idx << 1) | b
        out.append(_GEOHASH_BASE32[idx])
    return "".join(out)


def haversine_m(a: Sequence[float], b: Sequence[float]) -> float:
    """Distance in meters between two (lat, lng) pairs."""
    lat1, lng1 = float(a[0]), float(a[1])
    lat2, lng2 = float(b[0]), float(b[1])
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _iter_valid_points(points: Iterable) -> Iterable[List[float]]:
    for p in points:
        if p is None:
            continue
        try:
            lat, lng = float(p[0]), float(p[1])
        except (TypeError, ValueError, IndexError):
            continue
        if lat == 0.0 and lng == 0.0:
            # Common Garmin sentinel for "no fix yet" — exclude.
            continue
        yield [lat, lng]


# ---------------------------------------------------------------------------
# Fingerprint
# ---------------------------------------------------------------------------


def compute_geohash_set(
    latlng_track: Iterable,
    sample_distance_m: float = SAMPLE_DISTANCE_M,
    precision: int = GEOHASH_PRECISION,
) -> Optional[List[str]]:
    """Compute the route fingerprint as a sorted list of unique geohashes.

    Returns ``None`` if the track is too short or sparse for matching.
    """
    pts = list(_iter_valid_points(latlng_track))
    if len(pts) < MIN_TRACK_POINTS:
        return None

    cells = set()
    cells.add(encode_geohash(pts[0][0], pts[0][1], precision))
    accumulated = 0.0
    total = 0.0
    last = pts[0]
    for p in pts[1:]:
        step = haversine_m(last, p)
        total += step
        accumulated += step
        if accumulated >= sample_distance_m:
            cells.add(encode_geohash(p[0], p[1], precision))
            accumulated = 0.0
        last = p

    if total < MIN_TRACK_DISTANCE_M:
        return None
    if not cells:
        return None
    return sorted(cells)


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa = set(a)
    sb = set(b)
    if not sa or not sb:
        return 0.0
    inter = sa & sb
    union = sa | sb
    return len(inter) / len(union)


# ---------------------------------------------------------------------------
# Match + persist
# ---------------------------------------------------------------------------


def _candidate_routes(
    db: Session,
    athlete_id,
    distance_m: Optional[int],
) -> List[AthleteRoute]:
    q = db.query(AthleteRoute).filter(AthleteRoute.athlete_id == athlete_id)
    if distance_m and distance_m > 0:
        lo = int(distance_m * (1 - DISTANCE_TOLERANCE))
        hi = int(distance_m * (1 + DISTANCE_TOLERANCE))
        q = q.filter(
            AthleteRoute.distance_p50_m.is_not(None),
            AthleteRoute.distance_p50_m >= lo,
            AthleteRoute.distance_p50_m <= hi,
        )
    return q.all()


def find_matching_route(
    db: Session,
    athlete_id,
    geohash_set: Sequence[str],
    distance_m: Optional[int],
    *,
    threshold: float = JACCARD_MATCH_THRESHOLD,
) -> Optional[AthleteRoute]:
    """Return the best-matching existing route, or ``None`` if none qualify."""
    if not geohash_set:
        return None
    best: Optional[AthleteRoute] = None
    best_score = 0.0
    for route in _candidate_routes(db, athlete_id, distance_m):
        score = jaccard(geohash_set, route.geohash_set or [])
        if score >= threshold and score > best_score:
            best = route
            best_score = score
    return best


def _centroid(pts: Sequence) -> Optional[List[float]]:
    coords = list(_iter_valid_points(pts))
    if not coords:
        return None
    n = len(coords)
    return [sum(p[0] for p in coords) / n, sum(p[1] for p in coords) / n]


def _update_route_aggregates(route: AthleteRoute, activity: Activity, fingerprint: Sequence[str]) -> None:
    route.run_count = (route.run_count or 0) + 1
    if activity.start_time is not None:
        if route.first_seen_at is None or activity.start_time < route.first_seen_at:
            route.first_seen_at = activity.start_time
        if route.last_seen_at is None or activity.start_time > route.last_seen_at:
            route.last_seen_at = activity.start_time

    if activity.distance_m is not None:
        d = int(activity.distance_m)
        route.distance_min_m = d if route.distance_min_m is None else min(route.distance_min_m, d)
        route.distance_max_m = d if route.distance_max_m is None else max(route.distance_max_m, d)
        # Cheap rolling estimate of the median: snap toward the new value.
        if route.distance_p50_m is None:
            route.distance_p50_m = d
        else:
            route.distance_p50_m = int((route.distance_p50_m * 4 + d) / 5)

    # Keep the route's geohash set as the union — guarantees future Jaccard
    # comparisons widen rather than narrow as more runs are added.
    merged = sorted(set(route.geohash_set or []) | set(fingerprint))
    route.geohash_set = merged
    route.updated_at = datetime.now(timezone.utc)


def attach_or_create_route(
    db: Session,
    activity: Activity,
    fingerprint: Sequence[str],
    track: Optional[Sequence] = None,
) -> Optional[AthleteRoute]:
    """Attach the activity to an existing matching route or create a new one.

    Idempotent: if the activity is already attached to a route that still
    matches by Jaccard, the function refreshes the fingerprint on the
    activity but does not double-count run aggregates.

    Caller is responsible for committing the session.
    """
    if not fingerprint:
        return None

    # Idempotency: if already attached, update the activity-side fingerprint
    # only and return the existing route. This keeps repeated calls safe.
    if activity.route_id is not None:
        existing = db.query(AthleteRoute).filter(AthleteRoute.id == activity.route_id).first()
        if existing is not None and jaccard(fingerprint, existing.geohash_set or []) >= JACCARD_MATCH_THRESHOLD:
            activity.route_geohash_set = list(fingerprint)
            return existing

    match = find_matching_route(db, activity.athlete_id, fingerprint, activity.distance_m)
    if match is None:
        centroid = _centroid(track) if track is not None else None
        match = AthleteRoute(
            athlete_id=activity.athlete_id,
            geohash_set=list(fingerprint),
            run_count=0,
            distance_p50_m=int(activity.distance_m) if activity.distance_m else None,
            distance_min_m=int(activity.distance_m) if activity.distance_m else None,
            distance_max_m=int(activity.distance_m) if activity.distance_m else None,
            centroid_lat=centroid[0] if centroid else None,
            centroid_lng=centroid[1] if centroid else None,
            first_seen_at=activity.start_time,
            last_seen_at=activity.start_time,
        )
        db.add(match)
        db.flush()  # assign id

    _update_route_aggregates(match, activity, fingerprint)
    activity.route_id = match.id
    activity.route_geohash_set = list(fingerprint)
    return match


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def compute_for_activity(
    db: Session,
    activity_id: UUID,
    *,
    commit: bool = True,
) -> Optional[AthleteRoute]:
    """Compute fingerprint + attach route for the given activity, idempotent.

    Safe to call repeatedly: if a fingerprint already exists, the activity
    is re-routed against the latest set of athlete routes (cheap, deterministic).
    """
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if activity is None:
        return None
    if activity.athlete_id is None:
        return None

    stream = (
        db.query(ActivityStream)
        .filter(ActivityStream.activity_id == activity_id)
        .first()
    )
    if stream is None:
        return None
    raw = (stream.stream_data or {}).get("latlng") or []
    fingerprint = compute_geohash_set(raw)
    if not fingerprint:
        return None

    route = attach_or_create_route(db, activity, fingerprint, track=raw)
    if commit:
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
    return route
