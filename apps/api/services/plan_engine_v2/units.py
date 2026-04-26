"""
Unit formatting for athlete-facing output.

Internal calculations are ALWAYS in km and sec/km.
This module converts to the athlete's preferred display units
at the output boundary — the last step before the athlete sees anything.

Default: imperial (miles, min/mi). Toggle: metric (km, min/km).
"""

from __future__ import annotations

KM_TO_MI = 0.621371
MI_TO_KM = 1.60934


def dist(km: float, units: str = "imperial", precision: int = 1) -> str:
    """Format a distance for display."""
    if units == "metric":
        return f"{km:.{precision}f}km"
    mi = km * KM_TO_MI
    return f"{mi:.{precision}f}mi"


def dist_value(km: float, units: str = "imperial") -> float:
    """Convert km to display value (mi or km) without label."""
    if units == "metric":
        return round(km, 1)
    return round(km * KM_TO_MI, 1)


def dist_range(lo_km: float, hi_km: float, units: str = "imperial") -> str:
    """Format a distance range for display."""
    if units == "metric":
        return f"{lo_km:.0f}-{hi_km:.0f}km"
    lo_mi = lo_km * KM_TO_MI
    hi_mi = hi_km * KM_TO_MI
    return f"{lo_mi:.0f}-{hi_mi:.0f}mi"


def dist_range_tuple(lo_km: float, hi_km: float, units: str = "imperial") -> tuple:
    """Convert distance range to display values."""
    if units == "metric":
        return (round(lo_km, 1), round(hi_km, 1))
    return (round(lo_km * KM_TO_MI, 1), round(hi_km * KM_TO_MI, 1))


def pace(sec_per_km: float, units: str = "imperial") -> str:
    """Format pace for display (min:sec per unit)."""
    if units == "metric":
        total_sec = sec_per_km
        label = "/km"
    else:
        total_sec = sec_per_km / KM_TO_MI  # sec/mi
        label = "/mi"
    minutes = int(total_sec // 60)
    seconds = int(total_sec % 60)
    return f"{minutes}:{seconds:02d}{label}"


def unit_label(units: str = "imperial") -> str:
    """Return the short distance unit label."""
    return "mi" if units == "imperial" else "km"


# ── Text localization ─────────────────────────────────────────────

import re

_KM_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*km\b")


def _replace_km_match(m: re.Match) -> str:
    km_val = float(m.group(1))
    mi_val = km_val * KM_TO_MI
    if mi_val == int(mi_val):
        return f"{int(mi_val)}mi"
    return f"{mi_val:.1f}mi"


_PACE_MI_PATTERN = re.compile(r"(\d+:\d{2})-(\d+:\d{2})/mi")


def _pace_str_mi_to_km(pace_mi_str: str) -> str:
    """Convert a 'M:SS' pace in min/mi to min/km."""
    parts = pace_mi_str.split(":")
    total_sec_mi = int(parts[0]) * 60 + int(parts[1])
    total_sec_km = total_sec_mi * KM_TO_MI  # min/mi × (mi/km) = min/km
    m = int(total_sec_km) // 60
    s = int(total_sec_km) % 60
    return f"{m}:{s:02d}"


def _replace_pace_range_to_km(m: re.Match) -> str:
    lo = _pace_str_mi_to_km(m.group(1))
    hi = _pace_str_mi_to_km(m.group(2))
    return f"{lo}-{hi}/km"


_SINGLE_PACE_MI = re.compile(r"(\d+:\d{2})/mi")


def _replace_single_pace_to_km(m: re.Match) -> str:
    return f"{_pace_str_mi_to_km(m.group(1))}/km"


def localize_text(text: str, units: str = "imperial") -> str:
    """Convert distance and pace references in athlete-facing text.

    Imperial (default): converts km → mi in distances. Paces stay /mi.
    Metric: keeps km distances. Converts /mi paces → /km.
    """
    if units == "metric":
        result = _PACE_MI_PATTERN.sub(_replace_pace_range_to_km, text)
        result = _SINGLE_PACE_MI.sub(_replace_single_pace_to_km, result)
        return result

    result = _KM_PATTERN.sub(_replace_km_match, text)
    result = result.replace("Alt-KM", "Alt-MI")
    result = result.replace("alt-km", "alt-mi")
    result = result.replace("the early km", "the early miles")
    return result
