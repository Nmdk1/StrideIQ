"""
Garmin DI_CONNECT (Garmin Connect export) importer.

This supports the "Garmin takeout" / account export format that includes:
  DI_CONNECT/DI-Connect-Fitness/*_summarizedActivities.json
  DI_CONNECT/DI-Connect-Wellness/*_sleepData.json
  DI_CONNECT/DI-Connect-Wellness/*_healthStatusData.json

Activity import (Phase 7):
  - distance is in *centimeters*
  - duration / elapsedDuration are in *milliseconds*
  - startTimeLocal is epoch milliseconds (startTimeGMT may be missing)
  - elevationGain is in *centimeters* for some exports (needs normalization)
  - Ingests summary-only activities into the canonical Activity table
  - Best-effort cross-provider dedup (e.g. Strava already imported)

Wellness import:
  - Parses sleep, HRV, resting HR, stress, and daily summary data
  - Upserts into GarminDay table (one row per athlete + calendar_date)
  - Field names differ from the webhook API format — this module handles
    the DI_CONNECT export-specific JSON structure
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

import logging

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from models import Activity, GarminDay

logger = logging.getLogger(__name__)

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


def _meters_from_garmin_elevation_gain(value: Any) -> Optional[float]:
    """
    Normalize Garmin elevation gain to meters.

    Garmin export formats are not fully consistent across accounts/devices.
    We see elevationGain reported in centimeters for some exports (e.g. 26200 => 262m).

    Heuristic (production-beta safe):
    - Reject negative/NaN
    - Treat very large values as centimeters and divide by 100
    - Otherwise treat as meters
    """
    if value is None:
        return None
    try:
        v = float(value)
    except Exception:
        return None
    if math.isnan(v) or v < 0:
        return None
    # If it's > 5000, it's almost certainly centimeters (50m–500m typical; 5000m gain is extreme).
    if v > 5000:
        return float(v / 100.0)
    return float(v)


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


def _garmin_activity_id_exists(db: Session, athlete_id: UUID, garmin_native_id: int) -> bool:
    """
    Check if an Activity with this garmin_activity_id already exists.
    Catches the case where the webhook stored the activity with summaryId
    as external_activity_id but garmin_activity_id holds the native ID.
    """
    return db.query(Activity.id).filter(
        Activity.athlete_id == athlete_id,
        Activity.garmin_activity_id == garmin_native_id,
    ).first() is not None


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

            garmin_native_id = int(external_id) if isinstance(external_id, (int, float)) else None
            if garmin_native_id and _garmin_activity_id_exists(db, athlete_id, garmin_native_id):
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
                    "total_elevation_gain": _meters_from_garmin_elevation_gain(elevation_gain),
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


# ---------------------------------------------------------------------------
# Wellness / Health data import (DI-Connect-Wellness)
# ---------------------------------------------------------------------------

def _load_json_array_files(root_dir: Path, glob_pattern: str) -> List[Dict[str, Any]]:
    """Load and flatten all JSON files matching a glob pattern under root_dir."""
    results: List[Dict[str, Any]] = []
    for path in sorted(root_dir.rglob(glob_pattern)):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                results.extend(r for r in raw if isinstance(r, dict))
            elif isinstance(raw, dict):
                results.append(raw)
        except Exception as exc:
            logger.warning("Failed to parse wellness file %s: %s", path, exc)
    return results


def _parse_sleep_records(root_dir: Path) -> Dict[str, Dict[str, Any]]:
    """
    Parse *_sleepData.json files into {calendar_date: GarminDay fields}.

    Garmin export sleep format:
      calendarDate, deepSleepSeconds, lightSleepSeconds, remSleepSeconds,
      awakeSleepSeconds, sleepScores.overallScore, sleepScores.qualifierKey,
      validation, sleepStartTimestampGMT, sleepEndTimestampGMT
    """
    records = _load_json_array_files(root_dir, "*_sleepData.json")
    by_date: Dict[str, Dict[str, Any]] = {}

    for rec in records:
        cal_date = rec.get("calendarDate")
        if not cal_date:
            continue

        deep_s = rec.get("deepSleepSeconds")
        light_s = rec.get("lightSleepSeconds")
        rem_s = rec.get("remSleepSeconds")
        awake_s = rec.get("awakeSleepSeconds")

        total_s = None
        stage_parts = [deep_s, light_s, rem_s]
        if any(p is not None and p > 0 for p in stage_parts):
            total_s = sum(p for p in stage_parts if p is not None and p > 0)

        sleep_scores = rec.get("sleepScores") or {}
        score_val = sleep_scores.get("overallScore")
        score_qual = sleep_scores.get("qualifierKey")

        entry: Dict[str, Any] = {"calendar_date": cal_date}
        if total_s is not None:
            entry["sleep_total_s"] = int(total_s)
        if deep_s is not None and deep_s >= 0:
            entry["sleep_deep_s"] = int(deep_s)
        if light_s is not None and light_s >= 0:
            entry["sleep_light_s"] = int(light_s)
        if rem_s is not None and rem_s >= 0:
            entry["sleep_rem_s"] = int(rem_s)
        if awake_s is not None and awake_s >= 0:
            entry["sleep_awake_s"] = int(awake_s)
        if score_val is not None:
            entry["sleep_score"] = int(score_val)
        if score_qual:
            entry["sleep_score_qualifier"] = str(score_qual)

        validation = rec.get("validation")
        if validation:
            entry["sleep_validation"] = str(validation)

        if cal_date not in by_date or len(entry) > len(by_date[cal_date]):
            by_date[cal_date] = entry

    return by_date


def _parse_health_status_records(root_dir: Path) -> Dict[str, Dict[str, Any]]:
    """
    Parse *_healthStatusData.json files into {calendar_date: GarminDay fields}.

    Garmin export health status format:
      calendarDate, metrics: [{type: "HRV", value: ...}, {type: "HR", value: ...}, ...]
    """
    records = _load_json_array_files(root_dir, "*_healthStatusData.json")
    by_date: Dict[str, Dict[str, Any]] = {}

    for rec in records:
        cal_date = rec.get("calendarDate")
        if not cal_date:
            continue

        entry: Dict[str, Any] = {"calendar_date": cal_date}
        metrics = rec.get("metrics") or []

        for metric in metrics:
            if not isinstance(metric, dict):
                continue
            mtype = metric.get("type")
            mvalue = metric.get("value")
            if mvalue is None:
                continue

            try:
                val = float(mvalue)
            except (TypeError, ValueError):
                continue

            if mtype == "HRV":
                entry["hrv_overnight_avg"] = int(round(val))
            elif mtype == "HR":
                entry["resting_hr"] = int(round(val))
                entry["min_hr"] = int(round(val))

        if len(entry) > 1:
            by_date[cal_date] = entry

    return by_date


def _parse_daily_summary_records(root_dir: Path) -> Dict[str, Dict[str, Any]]:
    """
    Parse daily summary JSON files. Garmin exports may use several naming
    conventions: *_dailySummary.json, *_dailies.json, *_allDayStress.json.
    """
    by_date: Dict[str, Dict[str, Any]] = {}

    for pattern in ["*_dailySummary.json", "*_dailies.json"]:
        records = _load_json_array_files(root_dir, pattern)
        for rec in records:
            cal_date = rec.get("calendarDate")
            if not cal_date:
                continue

            entry: Dict[str, Any] = {"calendar_date": cal_date}

            steps = rec.get("totalSteps") or rec.get("steps")
            if steps is not None:
                try:
                    entry["steps"] = int(steps)
                except (TypeError, ValueError):
                    pass

            for src, dst in [
                ("restingHeartRate", "resting_hr"),
                ("minHeartRate", "min_hr"),
                ("maxHeartRate", "max_hr"),
                ("averageStressLevel", "avg_stress"),
                ("maxStressLevel", "max_stress"),
                ("activeTimeInSeconds", "active_time_s"),
                ("activeKilocalories", "active_kcal"),
                ("moderateIntensityDurationInSeconds", "moderate_intensity_s"),
                ("vigorousIntensityDurationInSeconds", "vigorous_intensity_s"),
            ]:
                v = rec.get(src)
                if v is not None:
                    try:
                        entry[dst] = int(v)
                    except (TypeError, ValueError):
                        pass

            stress_qual = rec.get("stressQualifier")
            if stress_qual:
                entry["stress_qualifier"] = str(stress_qual)

            if len(entry) > 1:
                existing = by_date.get(cal_date, {})
                existing.update(entry)
                by_date[cal_date] = existing

    return by_date


def _parse_stress_detail_records(root_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Parse *_stressDetails.json for body battery end-of-day values."""
    by_date: Dict[str, Dict[str, Any]] = {}

    for pattern in ["*_stressDetails.json", "*_stressDetailData.json"]:
        records = _load_json_array_files(root_dir, pattern)
        for rec in records:
            cal_date = rec.get("calendarDate")
            if not cal_date:
                continue

            entry: Dict[str, Any] = {"calendar_date": cal_date}

            bb_samples = rec.get("timeOffsetBodyBatteryValues")
            if isinstance(bb_samples, dict) and bb_samples:
                try:
                    last_key = max(bb_samples.keys(), key=lambda k: int(k))
                    entry["body_battery_end"] = int(bb_samples[last_key])
                except (TypeError, ValueError):
                    pass

            avg_stress = rec.get("averageStressLevel")
            if avg_stress is not None:
                try:
                    entry["avg_stress"] = int(avg_stress)
                except (TypeError, ValueError):
                    pass

            max_stress = rec.get("maxStressLevel")
            if max_stress is not None:
                try:
                    entry["max_stress"] = int(max_stress)
                except (TypeError, ValueError):
                    pass

            if len(entry) > 1:
                by_date[cal_date] = entry

    return by_date


def import_garmin_di_connect_wellness(
    db: Session,
    *,
    athlete_id: UUID,
    extracted_root_dir: Path,
) -> Dict[str, Any]:
    """
    Import wellness/health data from a Garmin DI_CONNECT export into GarminDay.

    Merges data from sleep, health status (HRV/RHR), daily summaries, and stress
    detail files. Uses upsert semantics: existing GarminDay rows are updated with
    non-null values from the export (webhook-delivered data is preserved when the
    export doesn't have a field).

    Args:
        db: SQLAlchemy session.
        athlete_id: Target athlete UUID.
        extracted_root_dir: Root of the extracted zip (contains DI_CONNECT/).

    Returns:
        Stats dict with counts of parsed/created/updated records.
    """
    root = Path(extracted_root_dir)

    sleep_data = _parse_sleep_records(root)
    health_data = _parse_health_status_records(root)
    daily_data = _parse_daily_summary_records(root)
    stress_data = _parse_stress_detail_records(root)

    all_dates: set[str] = set()
    all_dates.update(sleep_data.keys())
    all_dates.update(health_data.keys())
    all_dates.update(daily_data.keys())
    all_dates.update(stress_data.keys())

    if not all_dates:
        logger.info("No wellness data found in export for athlete %s", athlete_id)
        return {
            "status": "success",
            "wellness_dates_found": 0,
            "wellness_created": 0,
            "wellness_updated": 0,
        }

    created = 0
    updated = 0
    errors = 0

    GARMIN_DAY_FIELDS = {
        "resting_hr", "avg_stress", "max_stress", "stress_qualifier",
        "steps", "active_time_s", "active_kcal",
        "moderate_intensity_s", "vigorous_intensity_s",
        "min_hr", "max_hr",
        "sleep_total_s", "sleep_deep_s", "sleep_light_s", "sleep_rem_s",
        "sleep_awake_s", "sleep_score", "sleep_score_qualifier", "sleep_validation",
        "hrv_overnight_avg", "hrv_5min_high",
        "vo2max", "body_battery_end",
    }

    for cal_date_str in sorted(all_dates):
        merged: Dict[str, Any] = {}
        for source in [daily_data, stress_data, health_data, sleep_data]:
            if cal_date_str in source:
                for k, v in source[cal_date_str].items():
                    if k != "calendar_date" and v is not None:
                        merged[k] = v

        fields_to_write = {k: v for k, v in merged.items() if k in GARMIN_DAY_FIELDS}
        if not fields_to_write:
            continue

        try:
            from datetime import date as date_type
            cal_date = date_type.fromisoformat(cal_date_str)
        except (ValueError, TypeError):
            errors += 1
            continue

        try:
            already_exists = db.query(GarminDay).filter_by(
                athlete_id=athlete_id,
                calendar_date=cal_date,
            ).first() is not None

            insert_vals = {
                "id": uuid.uuid4(),
                "athlete_id": athlete_id,
                "calendar_date": cal_date,
                **fields_to_write,
            }

            stmt = (
                pg_insert(GarminDay.__table__)
                .values(insert_vals)
                .on_conflict_do_update(
                    constraint="uq_garmin_day_athlete_date",
                    set_=fields_to_write,
                )
            )
            db.execute(stmt)
            db.commit()

            if already_exists:
                updated += 1
            else:
                created += 1
        except Exception as exc:
            db.rollback()
            errors += 1
            logger.warning("Failed to upsert GarminDay for %s/%s: %s", athlete_id, cal_date_str, exc)

    logger.info(
        "Wellness import complete for athlete %s: %d dates, %d created, %d updated, %d errors",
        athlete_id, len(all_dates), created, updated, errors,
    )

    return {
        "status": "success",
        "wellness_dates_found": len(all_dates),
        "wellness_created": created,
        "wellness_updated": updated,
        "wellness_errors": errors,
        "wellness_sources": {
            "sleep_records": len(sleep_data),
            "health_status_records": len(health_data),
            "daily_summary_records": len(daily_data),
            "stress_detail_records": len(stress_data),
        },
    }

