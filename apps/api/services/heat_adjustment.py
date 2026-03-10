"""
Heat adjustment service — research-validated Temp + Dew Point model.

Port of the frontend HeatAdjustedPace.tsx calculator to Python for
backend use across the investigation engine, training story, and coach.

Research sources: RunFitMKE, Berlin Marathon Study (668K runners),
Six Major Marathons Study. Validated against McMillan Running Calculator
and Training Pace App.

Model: Combined Value = Temperature(°F) + Dew Point(°F)
       determines the percentage pace slowdown.

Living Fingerprint Spec — Capability 1.
"""
from __future__ import annotations

import math
from typing import Optional


def calculate_dew_point_f(temp_f: float, humidity_pct: float) -> float:
    """Compute dew point in °F from temperature and relative humidity.

    Uses the Magnus formula:
        α(T, RH) = (a·T)/(b+T) + ln(RH/100)
        Td = (b·α)/(a-α)

    Constants: a = 17.27, b = 237.7 (Celsius).
    Identical to HeatAdjustedPace.tsx calculateDewPoint.
    """
    temp_c = (temp_f - 32) * 5 / 9

    a = 17.27
    b = 237.7

    if humidity_pct <= 0:
        humidity_pct = 1.0
    if humidity_pct > 100:
        humidity_pct = 100.0

    alpha = (a * temp_c) / (b + temp_c) + math.log(humidity_pct / 100)
    dew_point_c = (b * alpha) / (a - alpha)

    return dew_point_c * 9 / 5 + 32


def calculate_heat_adjustment_pct(temp_f: float, dew_point_f: float) -> float:
    """Return the percentage pace slowdown for given conditions.

    Combined Value = temp_f + dew_point_f.
    Returns a float in [0.0, ~0.12+] representing the fraction of pace
    slowdown (e.g. 0.045 = 4.5% slower).

    Identical to HeatAdjustedPace.tsx calculateHeatAdjustment.
    """
    combined = temp_f + dew_point_f

    if combined >= 170:
        return 0.09 + ((combined - 170) / 10) * 0.01
    elif combined >= 160:
        return 0.065 + ((combined - 160) / 10) * 0.0025
    elif combined >= 150:
        return 0.045 + ((combined - 150) / 10) * 0.002
    elif combined >= 140:
        return 0.03 + ((combined - 140) / 10) * 0.0015
    elif combined >= 130:
        return 0.015 + ((combined - 130) / 10) * 0.0015
    elif combined >= 120:
        return 0.005 + ((combined - 120) / 10) * 0.001
    else:
        return 0.0


def heat_adjusted_pace(
    pace_sec_per_mile: float,
    temp_f: float,
    humidity_pct: float,
    dew_point_f: Optional[float] = None,
) -> float:
    """Return what this pace would be in ideal conditions (combined < 120).

    If dew_point_f is not provided, it's computed from temp + humidity.
    adjusted = raw_pace / (1 + adjustment_pct)
    """
    if dew_point_f is None:
        dew_point_f = calculate_dew_point_f(temp_f, humidity_pct)

    adj_pct = calculate_heat_adjustment_pct(temp_f, dew_point_f)
    if adj_pct <= 0:
        return pace_sec_per_mile

    return pace_sec_per_mile / (1 + adj_pct)


def compute_activity_heat_fields(
    temp_f: Optional[float],
    humidity_pct: Optional[float],
) -> dict:
    """Compute dew_point_f and heat_adjustment_pct for an activity.

    Returns dict with keys 'dew_point_f' and 'heat_adjustment_pct',
    either of which may be None if inputs are insufficient.
    """
    if temp_f is None or humidity_pct is None:
        return {'dew_point_f': None, 'heat_adjustment_pct': None}

    dp = calculate_dew_point_f(temp_f, humidity_pct)
    adj = calculate_heat_adjustment_pct(temp_f, dp)

    return {
        'dew_point_f': round(dp, 1),
        'heat_adjustment_pct': round(adj, 4),
    }
