"""
Country-aware unit-system default derivation.

Product rule (set by the founder 2026-04-22):
  US athletes default to imperial (miles, feet, /mi pace).
  Non-US athletes default to metric (km, meters, /km pace).
  Both can switch in Settings; the explicit choice is preserved
  via `Athlete.preferred_units_set_explicitly`.

The signal we use is the IANA timezone written from Strava OAuth (the most
reliable country signal we have without asking the athlete directly). The
US TZ subset below is the complete set of IANA zones that map to the
50 states + DC + territories (Hawaii, Alaska, Puerto Rico via America/
Puerto_Rico if ever encountered). Other America/* zones (Canada, Mexico,
Brazil, Argentina, the Caribbean, etc.) all default to metric, which is
correct for those countries.
"""
from typing import Literal, Optional

UnitSystem = Literal["metric", "imperial"]

# IANA timezones that resolve to the United States (50 states, DC, US territories).
# Sourced from the IANA tzdata zone1970.tab / zone.tab CC=US entries.
# Liberia (LR) and Myanmar (MM) also use imperial-adjacent units but are
# negligible for our market and excluded for v1; they will fall through to
# the metric default and can switch in Settings.
US_TIMEZONES = frozenset({
    # Continental US
    "America/New_York",
    "America/Detroit",
    "America/Kentucky/Louisville",
    "America/Kentucky/Monticello",
    "America/Indiana/Indianapolis",
    "America/Indiana/Vincennes",
    "America/Indiana/Winamac",
    "America/Indiana/Marengo",
    "America/Indiana/Petersburg",
    "America/Indiana/Vevay",
    "America/Indiana/Tell_City",
    "America/Indiana/Knox",
    "America/Chicago",
    "America/Menominee",
    "America/North_Dakota/Center",
    "America/North_Dakota/New_Salem",
    "America/North_Dakota/Beulah",
    "America/Denver",
    "America/Boise",
    "America/Phoenix",
    "America/Los_Angeles",
    # Alaska
    "America/Anchorage",
    "America/Juneau",
    "America/Sitka",
    "America/Metlakatla",
    "America/Yakutat",
    "America/Nome",
    "America/Adak",
    # Hawaii
    "Pacific/Honolulu",
    # Territories (non-conus)
    "America/Puerto_Rico",
    "Pacific/Guam",
    "Pacific/Saipan",
    "Pacific/Pago_Pago",
    "America/St_Thomas",  # US Virgin Islands
})


def derive_default_units(timezone: Optional[str]) -> UnitSystem:
    """Return the default unit system for an athlete given their timezone.

    Returns 'imperial' when the timezone is US (or unknown — US-first product),
    'metric' for everything else.

    The athlete can override this in Settings; the override is tracked
    separately via `Athlete.preferred_units_set_explicitly` so subsequent
    calls to this helper do not overwrite a deliberate choice.
    """
    if not timezone:
        return "imperial"
    if timezone in US_TIMEZONES:
        return "imperial"
    return "metric"
