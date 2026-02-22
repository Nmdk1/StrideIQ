"""
Activity Deduplication Service

Handles deduplication between Garmin and Strava activities.
Garmin is primary source; Strava is secondary.

ARCHITECTURE CONTRACT (enforced by tests):
- This service operates EXCLUSIVELY on internal field names.
- Callers MUST pass already-adapted dicts using internal field names:
    start_time  (datetime or ISO string)
    distance_m  (float, meters)
    avg_hr      (int, bpm — optional)
- Provider-specific field names must NEVER appear in this file. If you find
  yourself passing a raw Garmin or Strava API payload directly to this service,
  run it through the appropriate adapter first.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Deduplication thresholds for live sync (webhook / API push).
# The takeout/file-import path (garmin_di_connect.py) uses tighter
# thresholds (120s / 1.5%) — that is intentional. See AC §D5.2.
TIME_WINDOW_S = 3600   # 1 hour
DISTANCE_TOLERANCE = 0.05   # 5%
HR_TOLERANCE_BPM = 5


def match_activities(
    activity_a: Dict,
    activity_b: Dict,
) -> bool:
    """
    Check whether two activities represent the same workout.

    Both arguments must use internal field names only:
        start_time  — datetime or ISO-8601 string
        distance_m  — float (meters)
        avg_hr      — int (bpm), optional

    Returns True if activities match within all applicable thresholds.
    """
    try:
        date_a = _parse_start_time(activity_a)
        date_b = _parse_start_time(activity_b)

        if not date_a or not date_b:
            return False

        if abs((date_a - date_b).total_seconds()) > TIME_WINDOW_S:
            return False

        dist_a = _extract_distance_m(activity_a)
        dist_b = _extract_distance_m(activity_b)

        if not dist_a or not dist_b:
            return False

        distance_diff_pct = abs(dist_a - dist_b) / max(dist_a, dist_b)
        if distance_diff_pct > DISTANCE_TOLERANCE:
            return False

        hr_a = _extract_avg_hr(activity_a)
        hr_b = _extract_avg_hr(activity_b)

        if hr_a and hr_b:
            if abs(hr_a - hr_b) > HR_TOLERANCE_BPM:
                return False

        return True

    except Exception as e:
        logger.error(f"Error matching activities: {e}")
        return False


def deduplicate_activities(
    primary_activities: List[Dict],
    secondary_activities: List[Dict],
) -> Tuple[List[Dict], List[Dict]]:
    """
    Deduplicate activities from two providers.

    primary_activities are kept as-is. secondary_activities that match
    a primary activity are dropped. Returns (primary, unique_secondary).

    Both lists must use internal field names (see module docstring).
    """
    unique_secondary = []

    for secondary in secondary_activities:
        is_duplicate = any(
            match_activities(primary, secondary)
            for primary in primary_activities
        )
        if not is_duplicate:
            unique_secondary.append(secondary)
        else:
            logger.debug(
                f"Dedup: secondary activity at {secondary.get('start_time')} "
                f"({secondary.get('distance_m')}m) matches primary — dropping secondary"
            )

    return primary_activities, unique_secondary


def _parse_start_time(activity: Dict) -> Optional[datetime]:
    """
    Parse start_time from an internal-field-name activity dict.

    Accepts a datetime directly or an ISO-8601 string. Never reads
    provider-specific field names.
    """
    try:
        value = activity.get("start_time")
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                    try:
                        return datetime.strptime(value, fmt)
                    except ValueError:
                        continue
        return None
    except Exception:
        return None


def _extract_distance_m(activity: Dict) -> Optional[float]:
    """
    Extract distance in meters from an internal-field-name activity dict.

    Only reads distance_m. Never reads provider-specific field names.
    """
    try:
        value = activity.get("distance_m")
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _extract_avg_hr(activity: Dict) -> Optional[int]:
    """
    Extract average heart rate from an internal-field-name activity dict.

    Only reads avg_hr. Never reads provider-specific field names.
    """
    try:
        value = activity.get("avg_hr")
        if value is None:
            return None
        return int(value)
    except Exception:
        return None
