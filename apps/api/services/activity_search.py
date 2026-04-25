from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
import re
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, asc, desc, or_
from sqlalchemy.orm import Query, Session

from models import Activity


def _name_search_needles(value: str) -> list[str]:
    raw = (value or "").strip()
    if not raw:
        return []
    needles = {raw}
    compact = re.sub(r"\s+", "", raw).lower().replace("×", "x")
    spaced = re.sub(r"(?i)\b(\d{1,2})\s*x\s*(\d{3,4})m?\b", r"\1 x \2", raw).strip()
    if spaced:
        needles.add(spaced)
    compact_match = re.search(r"(?i)\b(\d{1,2})x(\d{3,4})m?\b", compact)
    if compact_match:
        count, distance = compact_match.groups()
        needles.update(
            {
                f"{count}x{distance}",
                f"{count} x {distance}",
                f"{count} x {distance}m",
                f"{distance}s",
                f"{distance} repeats",
            }
        )
    distance_only = re.search(r"(?i)\b(200|300|400|600|800|1000|1200|1600)s?\b", raw)
    if distance_only:
        distance = distance_only.group(1)
        needles.update({distance, f"{distance}s", f"{distance} repeats"})
    return sorted(needles)


@dataclass(frozen=True)
class ActivitySearchParams:
    athlete_id: UUID
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    min_distance_m: Optional[int] = None
    max_distance_m: Optional[int] = None
    sport: Optional[str] = None
    is_race: Optional[bool] = None
    workout_type: Optional[str] = None
    name_contains: Optional[str] = None
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None
    dew_min: Optional[float] = None
    dew_max: Optional[float] = None
    elev_gain_min: Optional[float] = None
    elev_gain_max: Optional[float] = None
    sort_by: str = "start_time"
    sort_order: str = "desc"


def _parse_boundary(value: Optional[str], *, is_end: bool) -> Optional[datetime]:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    if len(raw) == 10:
        parsed_date = datetime.fromisoformat(raw).date()
        return datetime.combine(parsed_date, time.max if is_end else time.min)
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _apply_range(query: Query, column, lo, hi, label: str) -> Query:
    if lo is not None and hi is not None and lo > hi:
        raise ValueError(f"{label}: min cannot exceed max ({lo} > {hi})")
    if lo is not None:
        query = query.filter(column >= lo, column.isnot(None))
    if hi is not None:
        query = query.filter(column <= hi, column.isnot(None))
    return query


def build_activity_search_query(db: Session, params: ActivitySearchParams) -> Query:
    """Build the canonical activity search query used by activities API + coach tools."""
    query = db.query(Activity).filter(Activity.athlete_id == params.athlete_id)

    start_dt = _parse_boundary(params.start_date, is_end=False)
    if start_dt is not None:
        query = query.filter(Activity.start_time >= start_dt)

    end_dt = _parse_boundary(params.end_date, is_end=True)
    if end_dt is not None:
        query = query.filter(Activity.start_time <= end_dt)

    query = _apply_range(
        query,
        Activity.distance_m,
        params.min_distance_m,
        params.max_distance_m,
        "distance",
    )

    if params.sport:
        query = query.filter(Activity.sport == params.sport)

    if params.workout_type:
        types = [t.strip() for t in params.workout_type.split(",") if t.strip()]
        if types:
            query = query.filter(Activity.workout_type.in_(types))

    if params.name_contains:
        needles = [f"%{needle}%" for needle in _name_search_needles(params.name_contains)]
        query = query.filter(
            or_(
                *[
                    condition
                    for needle in needles
                    for condition in (
                        Activity.name.ilike(needle),
                        Activity.athlete_title.ilike(needle),
                        Activity.shape_sentence.ilike(needle),
                        Activity.workout_type.ilike(needle),
                    )
                ]
            )
        )

    query = _apply_range(query, Activity.temperature_f, params.temp_min, params.temp_max, "temp")
    query = _apply_range(query, Activity.dew_point_f, params.dew_min, params.dew_max, "dew")
    query = _apply_range(
        query,
        Activity.total_elevation_gain,
        params.elev_gain_min,
        params.elev_gain_max,
        "elev_gain",
    )

    if params.is_race is not None:
        if params.is_race:
            query = query.filter(
                or_(
                    Activity.user_verified_race.is_(True),
                    Activity.is_race_candidate.is_(True),
                )
            )
        else:
            query = query.filter(
                and_(
                    or_(Activity.user_verified_race.is_(False), Activity.user_verified_race.is_(None)),
                    or_(Activity.is_race_candidate.is_(False), Activity.is_race_candidate.is_(None)),
                )
            )

    sort_field_map = {
        "start_time": Activity.start_time,
        "distance_m": Activity.distance_m,
        "duration_s": Activity.duration_s,
    }
    sort_field = sort_field_map.get(params.sort_by, Activity.start_time)
    if (params.sort_order or "desc").lower() == "asc":
        return query.order_by(asc(sort_field))
    return query.order_by(desc(sort_field))
