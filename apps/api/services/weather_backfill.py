"""
Weather backfill service using Open-Meteo Historical Weather API.

Populates temperature_f, humidity_pct, and weather_condition on Activity
records using GPS coordinates from the activity or the athlete's home location.

Works for any athlete:
  1. Uses activity's own lat/lng when available (exact location)
  2. Falls back to athlete's most common training location (mode of lat/lng)
  3. Falls back to explicit fallback coordinates if provided

Open-Meteo is free, requires no API key, and has historical data from 1940+.
We batch requests by date to minimize API calls (one call per unique date
per location covers all activities on that date).
"""

import logging
import time
from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from models import Activity

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
REQUEST_DELAY_S = 0.3  # be polite to free API


def _celsius_to_fahrenheit(c: float) -> float:
    return c * 9 / 5 + 32


def _wmo_to_condition(code: int) -> str:
    """Map WMO weather interpretation code to human-readable condition."""
    mapping = {
        0: 'clear', 1: 'mostly_clear', 2: 'partly_cloudy', 3: 'overcast',
        45: 'fog', 48: 'fog',
        51: 'drizzle', 53: 'drizzle', 55: 'drizzle',
        61: 'rain', 63: 'rain', 65: 'heavy_rain',
        71: 'snow', 73: 'snow', 75: 'heavy_snow',
        80: 'rain_showers', 81: 'rain_showers', 82: 'heavy_rain_showers',
        95: 'thunderstorm', 96: 'thunderstorm', 99: 'thunderstorm',
    }
    return mapping.get(code, 'unknown')


def fetch_weather_for_date(
    lat: float,
    lng: float,
    target_date: date,
) -> Optional[Dict]:
    """
    Fetch hourly weather for a single date from Open-Meteo.
    Returns dict with hourly arrays or None on failure.
    """
    params = {
        'latitude': round(lat, 4),
        'longitude': round(lng, 4),
        'start_date': target_date.isoformat(),
        'end_date': target_date.isoformat(),
        'hourly': ','.join([
            'temperature_2m',
            'relative_humidity_2m',
            'dew_point_2m',
            'wind_speed_10m',
            'wind_direction_10m',
            'weather_code',
        ]),
        'timezone': 'auto',
    }

    try:
        resp = httpx.get(OPEN_METEO_URL, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning("Open-Meteo request failed for %s at (%.4f, %.4f): %s",
                       target_date, lat, lng, e)
        return None


def extract_weather_at_hour(data: Dict, hour: int) -> Optional[Dict]:
    """Extract weather values for a specific hour from the API response."""
    hourly = data.get('hourly', {})
    times = hourly.get('time', [])
    temps = hourly.get('temperature_2m', [])
    humidity = hourly.get('relative_humidity_2m', [])
    dew_points = hourly.get('dew_point_2m', [])
    wind_speed = hourly.get('wind_speed_10m', [])
    wind_dir = hourly.get('wind_direction_10m', [])
    weather_codes = hourly.get('weather_code', [])

    if hour >= len(temps):
        return None

    temp_c = temps[hour]
    if temp_c is None:
        return None

    return {
        'temperature_f': round(_celsius_to_fahrenheit(temp_c), 1),
        'humidity_pct': humidity[hour] if hour < len(humidity) else None,
        'dew_point_f': round(_celsius_to_fahrenheit(dew_points[hour]), 1) if hour < len(dew_points) and dew_points[hour] is not None else None,
        'wind_speed_mph': round(wind_speed[hour] * 0.621371, 1) if hour < len(wind_speed) and wind_speed[hour] is not None else None,
        'wind_direction': wind_dir[hour] if hour < len(wind_dir) else None,
        'weather_condition': _wmo_to_condition(weather_codes[hour]) if hour < len(weather_codes) and weather_codes[hour] is not None else None,
    }


def detect_home_location(
    athlete_id: UUID,
    db: Session,
) -> Optional[Tuple[float, float]]:
    """
    Detect an athlete's most common training location from their activities.

    Uses the mode of rounded lat/lng (0.01° ≈ 1.1km) across all activities
    with GPS data. Most runners do most training near home.

    Returns (lat, lng) or None if no GPS data exists.
    """
    acts_with_loc = db.query(Activity.start_lat, Activity.start_lng).filter(
        Activity.athlete_id == athlete_id,
        Activity.start_lat.isnot(None),
        Activity.start_lng.isnot(None),
        Activity.is_duplicate == False,  # noqa: E712
    ).all()

    if not acts_with_loc:
        return None

    location_counts = Counter()
    for lat, lng in acts_with_loc:
        key = (round(lat, 2), round(lng, 2))
        location_counts[key] += 1

    most_common = location_counts.most_common(1)[0][0]
    logger.info("Detected home location for athlete %s: (%.2f, %.2f) from %d activities",
                athlete_id, most_common[0], most_common[1], len(acts_with_loc))
    return most_common


def backfill_weather_for_athlete(
    athlete_id: UUID,
    db: Session,
    force: bool = False,
    fallback_lat: Optional[float] = None,
    fallback_lng: Optional[float] = None,
) -> Dict:
    """
    Backfill weather data for all outdoor activities missing temperature.

    Location resolution order:
      1. Activity's own lat/lng (exact GPS from Strava/Garmin)
      2. Athlete's home location (mode of all their GPS coordinates)
      3. Explicit fallback_lat/lng (caller-provided, e.g. for testing)

    Groups activities by (date, rounded lat/lng) to batch API calls.
    One API call per unique location-date covers all activities that day.
    """
    # Auto-detect home location as first fallback
    home = detect_home_location(athlete_id, db)
    home_lat = home[0] if home else fallback_lat
    home_lng = home[1] if home else fallback_lng

    query = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.is_duplicate == False,  # noqa: E712
    )

    if not force:
        query = query.filter(Activity.temperature_f.is_(None))

    activities = query.order_by(Activity.start_time).all()

    if not activities:
        return {'total': 0, 'updated': 0, 'failed': 0, 'skipped_indoor': 0,
                'no_location': 0, 'home_location': home}

    LocationDate = Tuple[float, float, date]
    groups: Dict[LocationDate, List[Activity]] = defaultdict(list)
    skipped_indoor = 0
    no_location = 0

    for act in activities:
        elev = float(act.total_elevation_gain) if act.total_elevation_gain else 0
        dist_km = (act.distance_m or 0) / 1000
        if elev < 20 and dist_km > 5:
            skipped_indoor += 1
            continue

        lat = act.start_lat or home_lat
        lng = act.start_lng or home_lng
        if lat is None or lng is None:
            no_location += 1
            continue

        d = act.start_time.date()
        lat_rounded = round(lat, 2)
        lng_rounded = round(lng, 2)
        groups[(lat_rounded, lng_rounded, d)].append(act)

    stats = {'total': len(activities), 'updated': 0, 'failed': 0,
             'skipped_indoor': skipped_indoor, 'no_location': no_location,
             'api_calls': 0, 'home_location': home}

    for (lat, lng, d), group_acts in groups.items():
        data = fetch_weather_for_date(lat, lng, d)
        stats['api_calls'] += 1

        if data is None:
            stats['failed'] += len(group_acts)
            time.sleep(REQUEST_DELAY_S)
            continue

        for act in group_acts:
            hour = act.start_time.hour
            weather = extract_weather_at_hour(data, hour)
            if weather is None:
                stats['failed'] += 1
                continue

            act.temperature_f = weather['temperature_f']
            act.humidity_pct = weather['humidity_pct']
            act.weather_condition = weather['weather_condition']
            stats['updated'] += 1

        time.sleep(REQUEST_DELAY_S)

        if stats['api_calls'] % 50 == 0:
            db.flush()
            logger.info("Weather backfill progress: %d API calls, %d updated",
                        stats['api_calls'], stats['updated'])

    db.flush()
    return stats
