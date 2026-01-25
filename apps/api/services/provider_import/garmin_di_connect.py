"""
Garmin DI_CONNECT (Garmin Connect export) importer.

This supports the "Garmin takeout" / account export format that includes:
  DI_CONNECT/DI-Connect-Fitness/*_summarizedActivities.json

Empirically (from user-provided export):
  - distance is in *centimeters*
  - duration / elapsedDuration are in *milliseconds*
  - startTimeLocal is epoch milliseconds (startTimeGMT may be missing)

We ingest summary-only activities into the canonical Activity table, using:
  provider="garmin", external_activity_id=str(activityId)

We also do a best-effort cross-provider dedup (e.g. Strava already imported)
by matching start_time within a small window and distance within a tolerance.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
import uuid

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from models import Activity


GARMIN_PROVIDER_KEY = "garmin"


def _utc_from_epoch_ms(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    try:
        ms = float(value)
    except Exception:
        return None
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)


def _meters_from_centimeters(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        cm = float(value)
    except Exception:
        return None
    if math.isnan(cm) or cm < 0:
        return None
    return int(round(cm / 100.0))


def _seconds_from_millis(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        ms = float(value)
    except Exception:
        return None
    if math.isnan(ms) or ms < 0:
        return None
    return int(round(ms / 1000.0))


def _safe_basename(name: str) -> str:
    base = os.path.basename(name or "")
    if not base:
        return "garmin_export.zip"
    keep: List[str] = []
    for ch in base:
        if ch.isalnum() or ch in (".", "_", "-", "@"):
            keep.append(ch)
        else:
            keep.append("_")
    return "".join(keep)[:180]


def find_summarized_activities_files(root_dir: Path) -> List[Path]:
    """
    Locate summarized activities export files within an extracted Garmin takeout folder.
    """
    root_dir = Path(root_dir)
    if not root_dir.exists():
        return []
    candidates = list(root_dir.rglob("*_summarizedActivities.json"))
    return sorted(candidates, key=lambda p: str(p).lower())


def load_summarized_activities(path: Path) -> List[Dict[str, Any]]:
    """
    Returns the list of summarized activity dicts from a single file.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        return []
    root = raw[0]
    if not isinstance(root, dict):
        return []
    arr = root.get("summarizedActivitiesExport")
    if not isinstance(arr, list):
        return []
    return [x for x in arr if isinstance(x, dict)]


def _sport_from_activity_type(activity_type: Optional[str]) -> str:
    t = (activity_type or "").lower()
    if "run" in t:
        return "run"
    if "cycle" in t or "bike" in t:
        return "ride"
    if "swim" in t:
        return "swim"
    return "workout"


def _is_run_like(activity_type: Optional[str]) -> bool:
    t = (activity_type or "").lower()
    return "run" in t


@dataclass(frozen=True)
class ExistingActivityIndex:
    garmin_external_ids: set[str]
    by_minute: Dict[int, List[Tuple[int, Optional[int]]]]


def build_existing_activity_index(db: Session, athlete_id: UUID) -> ExistingActivityIndex:
    rows = (
        db.query(Activity.provider, Activity.external_activity_id, Activity.start_time, Activity.distance_m)
        .filter(Activity.athlete_id == athlete_id)
        .all()
    )

    garmin_external_ids: set[str] = set()
    by_minute: Dict[int, List[Tuple[int, Optional[int]]]] = {}

    for provider, external_id, start_time, distance_m in rows:
        if provider == GARMIN_PROVIDER_KEY and external_id:
            garmin_external_ids.add(str(external_id))
        if not start_time:
            continue
        try:
            ts = int(start_time.timestamp())
        except Exception:
            continue
        bucket = ts // 60
        by_minute.setdefault(bucket, []).append((ts, int(distance_m) if distance_m is not None else None))

    return ExistingActivityIndex(garmin_external_ids=garmin_external_ids, by_minute=by_minute)


def _matches_existing_time_distance(
    idx: ExistingActivityIndex,
    *,
    start_time: datetime,
    distance_m: Optional[int],
    window_s: int = 120,
    rel_tol: float = 0.015,
) -> bool:
    try:
        ts = int(start_time.timestamp())
    except Exception:
        return False
    bucket = ts // 60
    for b in (bucket - 2, bucket - 1, bucket, bucket + 1, bucket + 2):
        for existing_ts, existing_dist in idx.by_minute.get(b, []):
            if abs(existing_ts - ts) > window_s:
                continue
            if distance_m is None or existing_dist is None or existing_dist <= 0:
                return True
            if abs(existing_dist - distance_m) / float(existing_dist) <= rel_tol:
                return True
    return False


def import_garmin_di_connect_summaries(
    db: Session,
    *,
    athlete_id: UUID,
    extracted_root_dir: Path,
) -> Dict[str, Any]:
    files = find_summarized_activities_files(Path(extracted_root_dir))
    idx = build_existing_activity_index(db, athlete_id)

    created = 0
    already_present = 0
    skipped_non_runs = 0
    skipped_possible_duplicate = 0
    parsed_total = 0

    for f in files:
        activities = load_summarized_activities(f)
        rows_to_insert: List[Dict[str, Any]] = []
        for a in activities:
            parsed_total += 1

            external_id = a.get("activityId")
            if external_id is None:
                continue
            external_id_str = str(int(external_id)) if isinstance(external_id, (int, float)) else str(external_id)

            activity_type = a.get("activityType")
            if not _is_run_like(activity_type):
                skipped_non_runs += 1
                continue

            if external_id_str in idx.garmin_external_ids:
                already_present += 1
                continue

            # Garmin DI_CONNECT uses startTimeGmt/startTimeLocal (note casing).
            # Prefer GMT for canonical UTC alignment (matches Strava start_time semantics).
            start_time = (
                _utc_from_epoch_ms(a.get("startTimeGmt"))
                or _utc_from_epoch_ms(a.get("startTimeGMT"))
                or _utc_from_epoch_ms(a.get("beginTimestamp"))
                or _utc_from_epoch_ms(a.get("startTimeLocal"))
            )
            if not start_time:
                continue

            distance_m = _meters_from_centimeters(a.get("distance"))
            duration_s = _seconds_from_millis(a.get("duration")) or _seconds_from_millis(a.get("elapsedDuration"))

            if _matches_existing_time_distance(idx, start_time=start_time, distance_m=distance_m):
                skipped_possible_duplicate += 1
                continue

            name = a.get("activityName") or f"Garmin {str(activity_type).title() if activity_type else 'Run'}"
            sport = _sport_from_activity_type(activity_type)

            avg_hr = a.get("averageHeartRate")
            max_hr = a.get("maxHeartRate")
            elevation_gain = a.get("elevationGain")
            average_speed = a.get("averageSpeed")

            rows_to_insert.append(
                {
                    "id": uuid.uuid4(),
                    "athlete_id": athlete_id,
                    "name": str(name) if name is not None else None,
                    "start_time": start_time,
                    "sport": sport,
                    "source": "garmin_import",
                    "duration_s": duration_s,
                    "distance_m": distance_m,
                    "avg_hr": int(avg_hr) if isinstance(avg_hr, (int, float)) else None,
                    "max_hr": int(max_hr) if isinstance(max_hr, (int, float)) else None,
                    "total_elevation_gain": float(elevation_gain) if isinstance(elevation_gain, (int, float)) else None,
                    "average_speed": float(average_speed) if isinstance(average_speed, (int, float)) else None,
                    "provider": GARMIN_PROVIDER_KEY,
                    "external_activity_id": external_id_str,
                }
            )
            idx.garmin_external_ids.add(external_id_str)
            try:
                ts = int(start_time.timestamp())
                idx.by_minute.setdefault(ts // 60, []).append((ts, distance_m))
            except Exception:
                pass

        if rows_to_insert:
            # Critical: daily/weekly/monthly re-imports will always include the full history.
            # We MUST be idempotent. Use DB-level upsert semantics to avoid crashing jobs
            # when activities already exist (including potential cross-athlete collisions).
            stmt = (
                pg_insert(Activity.__table__)
                .values(rows_to_insert)
                .on_conflict_do_nothing(constraint="uq_activity_provider_external_id")
                .returning(Activity.__table__.c.external_activity_id)
            )
            inserted = {row[0] for row in db.execute(stmt).all()}
            db.commit()

            created += len(inserted)
            already_present += max(0, len(rows_to_insert) - len(inserted))

    return {
        "status": "success",
        "pages_fetched": len(files),
        "files_parsed": len(files),
        "activities_total": parsed_total,
        "created": created,
        "already_present": already_present,
        "skipped_non_runs": skipped_non_runs,
        "skipped_possible_duplicate": skipped_possible_duplicate,
        # ADR-057 audit field aliases (minimum set)
        "parser_types_used": ["garmin_di_connect_summarized_activities_json"],
        "activities_parsed": parsed_total,
        "activities_inserted": created,
        "activities_updated": 0,
        "activities_skipped_duplicate": int(already_present) + int(skipped_possible_duplicate),
        "splits_inserted": 0,
        "errors_count": 0,
        "error_codes": [],
    }

