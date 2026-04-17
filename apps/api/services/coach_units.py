"""
Unit-aware formatters for coach-facing text (LLM prompts, deterministic
fallbacks, narrative responses).

The home briefing pipeline historically baked imperial units into the prompt
template ("distances in miles", "Pace as min/mi") and into the data dicts
fed to the LLM (`distance_mi`, `elevation_gain_ft`, `temperature_f`). For
metric athletes this guaranteed a unit mismatch in `morning_voice`: the
athlete sees "11.2 km" everywhere else and "7-mile run at 7:39 pace" in
the LLM-written paragraph.

This module centralises the conversion so the briefing builder, the
deterministic fallback, and any future coach-facing text generator share
one source of truth.

Returned strings always include the unit suffix so they can be dropped
verbatim into prompts without further string surgery.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


_KM_TO_MI = 0.621371
_M_TO_FT = 3.28084


def _is_metric(preferred_units: Optional[str]) -> bool:
    return (preferred_units or "imperial").strip().lower() == "metric"


@dataclass(frozen=True)
class CoachUnits:
    """Bundle of pre-resolved unit labels for one athlete.

    Use the formatter methods rather than hand-rolling f-strings so the
    output stays consistent across briefings, deterministic fallbacks,
    and any other coach-facing surface that adopts this helper.
    """

    preferred_units: str  # "metric" or "imperial"

    # ---- label accessors (for prompt instruction text) ----

    @property
    def is_metric(self) -> bool:
        return _is_metric(self.preferred_units)

    @property
    def pace_unit(self) -> str:
        """Pace unit suffix, e.g. 'min/mi' or 'min/km'."""
        return "min/km" if self.is_metric else "min/mi"

    @property
    def pace_unit_short(self) -> str:
        """Pace unit suffix on a numeric value, e.g. '/mi' or '/km'."""
        return "/km" if self.is_metric else "/mi"

    @property
    def distance_unit_short(self) -> str:
        return "km" if self.is_metric else "mi"

    @property
    def distance_unit_long(self) -> str:
        return "kilometers" if self.is_metric else "miles"

    @property
    def elevation_unit(self) -> str:
        return "m" if self.is_metric else "ft"

    @property
    def temperature_unit(self) -> str:
        return "°C" if self.is_metric else "°F"

    # ---- value formatters ----

    def format_distance(self, distance_m: Optional[float], decimals: int = 1) -> Optional[str]:
        """Format a distance in meters into '11.2 km' or '7.0 mi'."""
        if distance_m is None:
            return None
        try:
            meters = float(distance_m)
        except (TypeError, ValueError):
            return None
        if self.is_metric:
            value = meters / 1000.0
        else:
            value = meters / 1609.344
        return f"{value:.{decimals}f} {self.distance_unit_short}"

    def format_pace_from_distance_duration(
        self,
        distance_m: Optional[float],
        duration_s: Optional[float],
    ) -> Optional[str]:
        """Compute and format pace from raw meters + seconds."""
        if not distance_m or not duration_s:
            return None
        try:
            meters = float(distance_m)
            seconds = float(duration_s)
        except (TypeError, ValueError):
            return None
        if meters <= 0 or seconds <= 0:
            return None
        if self.is_metric:
            secs_per_unit = seconds / (meters / 1000.0)
        else:
            secs_per_unit = seconds / (meters / 1609.344)
        mins = int(secs_per_unit // 60)
        secs = int(round(secs_per_unit - mins * 60))
        if secs == 60:
            secs = 0
            mins += 1
        return f"{mins}:{secs:02d}{self.pace_unit_short}"

    def format_elevation(self, gain_m: Optional[float]) -> Optional[str]:
        """Format an elevation gain in meters into '+330 m' or '+1083 ft'."""
        if gain_m is None:
            return None
        try:
            meters = float(gain_m)
        except (TypeError, ValueError):
            return None
        if self.is_metric:
            return f"+{int(round(meters))} m"
        return f"+{int(round(meters * _M_TO_FT))} ft"

    def format_temperature_from_f(self, temp_f: Optional[float]) -> Optional[str]:
        """Format a temperature stored in Fahrenheit into the athlete's unit."""
        if temp_f is None:
            return None
        try:
            t = float(temp_f)
        except (TypeError, ValueError):
            return None
        if self.is_metric:
            celsius = (t - 32.0) * 5.0 / 9.0
            return f"{celsius:.1f}°C"
        return f"{t:.1f}°F"


def coach_units(preferred_units: Optional[str]) -> CoachUnits:
    """Build a CoachUnits bundle from the athlete's stored preference.

    Defaults to imperial when the value is missing or unrecognised so the
    pipeline behaviour for legacy rows (and tests that don't set the field)
    matches what was on the wire before unit-awareness was introduced.
    """
    return CoachUnits(preferred_units="metric" if _is_metric(preferred_units) else "imperial")
