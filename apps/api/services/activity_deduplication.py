"""
Activity Deduplication Service

Handles deduplication between Garmin and Strava activities.
Garmin is primary source; Strava is fallback.

ARCHITECTURE:
- Match activities by date + time + distance + avg HR
- Keep Garmin version as golden record
- Mark or discard Strava duplicates
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def match_activities(
    garmin_activity: Dict,
    strava_activity: Dict
) -> bool:
    """
    Check if Garmin and Strava activities match (same workout).
    
    Matching criteria:
    - Date: Same day (within 24 hours)
    - Time: Start time within 1 hour
    - Distance: Within 5% difference
    - Avg HR: Within 5 bpm (if both have HR)
    
    Args:
        garmin_activity: Garmin activity dictionary
        strava_activity: Strava activity dictionary
        
    Returns:
        True if activities match, False otherwise
    """
    try:
        # Extract dates
        garmin_date = _parse_activity_date(garmin_activity)
        strava_date = _parse_activity_date(strava_activity)
        
        if not garmin_date or not strava_date:
            return False
        
        # Check date match (within 24 hours)
        date_diff = abs((garmin_date - strava_date).total_seconds())
        if date_diff > 86400:  # More than 24 hours
            return False
        
        # Extract distances
        garmin_distance = _extract_distance(garmin_activity)
        strava_distance = _extract_distance(strava_activity)
        
        if not garmin_distance or not strava_distance:
            return False
        
        # Check distance match (within 5%)
        distance_diff_pct = abs(garmin_distance - strava_distance) / max(garmin_distance, strava_distance)
        if distance_diff_pct > 0.05:
            return False
        
        # Extract avg HR if available
        garmin_hr = _extract_avg_hr(garmin_activity)
        strava_hr = _extract_avg_hr(strava_activity)
        
        # If both have HR, check match (within 5 bpm)
        if garmin_hr and strava_hr:
            hr_diff = abs(garmin_hr - strava_hr)
            if hr_diff > 5:
                return False
        
        # Extract start times
        garmin_time = _extract_start_time(garmin_activity)
        strava_time = _extract_start_time(strava_activity)
        
        # Check time match (within 1 hour)
        if garmin_time and strava_time:
            time_diff = abs((garmin_time - strava_time).total_seconds())
            if time_diff > 3600:  # More than 1 hour
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error matching activities: {e}")
        return False


def _parse_activity_date(activity: Dict) -> Optional[datetime]:
    """Parse activity date from various formats."""
    try:
        # Try different date fields
        date_str = activity.get("startTimeLocal") or activity.get("startTime") or activity.get("start_date_local")
        if date_str:
            # Parse ISO format or other formats
            if isinstance(date_str, str):
                # Try ISO format first
                try:
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except:
                    # Try other formats
                    for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
                        try:
                            return datetime.strptime(date_str, fmt)
                        except:
                            continue
        return None
    except:
        return None


def _extract_distance(activity: Dict) -> Optional[float]:
    """Extract distance in meters."""
    try:
        # Try different distance fields
        distance = activity.get("distance") or activity.get("distanceInMeters") or activity.get("distance_m")
        if distance:
            return float(distance)
        return None
    except:
        return None


def _extract_avg_hr(activity: Dict) -> Optional[int]:
    """Extract average heart rate."""
    try:
        hr = activity.get("averageHeartRate") or activity.get("avgHeartRate") or activity.get("avg_hr")
        if hr:
            return int(hr)
        return None
    except:
        return None


def _extract_start_time(activity: Dict) -> Optional[datetime]:
    """Extract start time."""
    return _parse_activity_date(activity)


def deduplicate_activities(
    garmin_activities: List[Dict],
    strava_activities: List[Dict]
) -> Tuple[List[Dict], List[Dict]]:
    """
    Deduplicate activities between Garmin and Strava.
    
    Args:
        garmin_activities: List of Garmin activities
        strava_activities: List of Strava activities
        
    Returns:
        Tuple of (unique_garmin_activities, unique_strava_activities)
        Garmin activities are kept as-is (primary source)
        Strava activities are filtered to remove duplicates
    """
    unique_garmin = garmin_activities.copy()
    unique_strava = []
    
    for strava_activity in strava_activities:
        is_duplicate = False
        
        for garmin_activity in garmin_activities:
            if match_activities(garmin_activity, strava_activity):
                is_duplicate = True
                logger.debug(f"Found duplicate: Strava activity {strava_activity.get('id')} matches Garmin {garmin_activity.get('activityId')}")
                break
        
        if not is_duplicate:
            unique_strava.append(strava_activity)
    
    return unique_garmin, unique_strava

