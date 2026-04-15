"""
Weather enrichment service using Open-Meteo APIs.

Populates temperature_f, humidity_pct, dew_point_f, weather_condition,
and heat_adjustment_pct on Activity records using GPS coordinates.

Two modes:
  - Live enrichment: ``enrich_activity_weather()`` called during activity
    ingestion (Garmin webhook, Strava post-sync). Fire-and-forget.
  - Batch backfill: ``backfill_weather_for_athlete()`` for correcting
    historical activities that have wrong device-sensor temps.

API strategy:
  1. Historical Forecast API (``historical-forecast-api.open-meteo.com``)
     — updated continuously, covers 2022-present including today.
  2. Archive API (``archive-api.open-meteo.com``) — ERA5 reanalysis,
     covers 1940-present with a 2-5 day delay on recent dates.

Both APIs return the same response format; callers never need to know
which served the data.

Location resolution:
  1. Activity's own lat/lng (exact GPS)
  2. Athlete's home location (mode of all GPS coordinates)
  3. Explicit fallback coordinates (caller-provided)

Open-Meteo is free, requires no API key.
"""

import logging
import time
from collections import Counter, defaultdict
from datetime import date
from typing import Dict, List, Optional, Tuple
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from models import Activity

logger = logging.getLogger(__name__)

HISTORICAL_FORECAST_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
REQUEST_DELAY_S = 0.3  # be polite to free API

_INDOOR_SPORTS = frozenset({"strength", "flexibility"})

_HOURLY_PARAMS = ",".join([
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "wind_speed_10m",
    "wind_direction_10m",
    "weather_code",
])


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


def _try_api(url: str, lat: float, lng: float, target_date: date) -> Optional[Dict]:
    """Call a single Open-Meteo endpoint. Returns parsed JSON or None."""
    params = {
        "latitude": round(lat, 4),
        "longitude": round(lng, 4),
        "start_date": target_date.isoformat(),
        "end_date": target_date.isoformat(),
        "hourly": _HOURLY_PARAMS,
        "timezone": "auto",
    }
    try:
        resp = httpx.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("hourly", {}).get("temperature_2m"):
            return data
        return None
    except Exception:
        return None


def fetch_weather_for_date(
    lat: float,
    lng: float,
    target_date: date,
) -> Optional[Dict]:
    """
    Fetch hourly weather for a single date from Open-Meteo.

    Tries the Historical Forecast API first (covers 2022-today, updated
    continuously). Falls back to the Archive API (ERA5, 1940-present,
    2-5 day delay on recent dates). Both return the same response format.
    """
    data = _try_api(HISTORICAL_FORECAST_URL, lat, lng, target_date)
    if data is not None:
        return data
    data = _try_api(ARCHIVE_URL, lat, lng, target_date)
    if data is not None:
        return data
    logger.warning(
        "Open-Meteo: both APIs failed for %s at (%.4f, %.4f)",
        target_date, lat, lng,
    )
    return None


def extract_weather_at_hour(data: Dict, hour: int) -> Optional[Dict]:
    """Extract weather values for a specific hour from the API response."""
    hourly = data.get('hourly', {})
    hourly.get('time', [])
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


def enrich_activity_weather(activity: Activity, db: Session) -> bool:
    """
    Enrich a single activity with API weather data.

    Sets temperature_f, humidity_pct, dew_point_f, weather_condition,
    and heat_adjustment_pct from Open-Meteo based on the activity's GPS
    coordinates and start time.

    Designed for the live ingestion pipeline — fire-and-forget.
    Never raises; returns False on skip or failure, True on success.
    """
    try:
        sport = getattr(activity, "sport", None)
        if sport in _INDOOR_SPORTS:
            return False

        lat = activity.start_lat
        lng = activity.start_lng
        if lat is None or lng is None:
            return False

        start = activity.start_time
        if start is None:
            return False

        data = fetch_weather_for_date(lat, lng, start.date())
        if data is None:
            return False

        weather = extract_weather_at_hour(data, start.hour)
        if weather is None:
            return False

        activity.temperature_f = weather["temperature_f"]
        activity.humidity_pct = weather["humidity_pct"]
        activity.weather_condition = weather["weather_condition"]

        if weather.get("dew_point_f") is not None:
            activity.dew_point_f = weather["dew_point_f"]
        elif weather["temperature_f"] is not None and weather["humidity_pct"] is not None:
            from services.heat_adjustment import calculate_dew_point_f
            activity.dew_point_f = round(
                calculate_dew_point_f(weather["temperature_f"], weather["humidity_pct"]), 1
            )

        if activity.dew_point_f is not None and activity.temperature_f is not None:
            from services.heat_adjustment import calculate_heat_adjustment_pct
            activity.heat_adjustment_pct = round(
                calculate_heat_adjustment_pct(activity.temperature_f, activity.dew_point_f), 4
            )

        logger.info(
            "Weather enriched: activity %s → %.1f°F, %s",
            activity.id, activity.temperature_f, activity.weather_condition,
        )
        return True
    except Exception as exc:
        logger.warning("Weather enrichment failed for activity %s: %s", getattr(activity, "id", "?"), exc)
        return False


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
        if getattr(act, "sport", None) in _INDOOR_SPORTS:
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

            if weather.get('dew_point_f') is not None:
                act.dew_point_f = weather['dew_point_f']
            elif weather['temperature_f'] is not None and weather['humidity_pct'] is not None:
                from services.heat_adjustment import calculate_dew_point_f
                act.dew_point_f = round(calculate_dew_point_f(
                    weather['temperature_f'], weather['humidity_pct']), 1)

            if act.dew_point_f is not None and act.temperature_f is not None:
                from services.heat_adjustment import calculate_heat_adjustment_pct
                act.heat_adjustment_pct = round(calculate_heat_adjustment_pct(
                    act.temperature_f, act.dew_point_f), 4)

            stats['updated'] += 1

        time.sleep(REQUEST_DELAY_S)

        if stats['api_calls'] % 50 == 0:
            db.flush()
            logger.info("Weather backfill progress: %d API calls, %d updated",
                        stats['api_calls'], stats['updated'])

    db.flush()
    return stats
