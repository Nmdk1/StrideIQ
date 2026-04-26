"""
Pace Ladder — percentage-based pace system extending Daniels zones.

One function, one ladder, anchor is a parameter:
  - Marathon mode → anchor = marathon pace
  - 5K mode → anchor = 5K pace
  - Ultra mode → anchor = marathon pace
  - Build modes → anchor = marathon pace

Daniels zones are SACRED — named zone values come from
calculate_paces_from_rpi() and are never overridden.  The percentage
ladder fills only the gaps between named zones.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

from services.fitness_bank import rpi_equivalent_time
from services.workout_prescription import calculate_paces_from_rpi

from .models import PaceLadder

logger = logging.getLogger(__name__)

MI_TO_KM = 1.60934

# Percentage rungs to compute on the ladder
LADDER_RUNGS = [75, 80, 85, 90, 92, 94, 95, 96, 100, 103, 105, 108, 110, 115, 120]


def _min_per_mi_to_sec_per_km(pace_min_per_mi: float) -> float:
    """Convert pace from minutes/mile to seconds/km."""
    return (pace_min_per_mi * 60.0) / MI_TO_KM


def _compute_anchor_pace(
    best_rpi: float,
    anchor_type: str,
    daniels_paces: Dict[str, float],
) -> float:
    """Compute the anchor pace in sec/km for the percentage ladder.

    For marathon anchor: use the Daniels marathon pace (most trustworthy).
    For 5K anchor: derive from rpi_equivalent_time for precision.
    """
    if anchor_type == "5k":
        fiveK_time_sec = rpi_equivalent_time(best_rpi, 5000)
        return fiveK_time_sec / 5.0  # sec/km
    else:
        return _min_per_mi_to_sec_per_km(daniels_paces["marathon"])


def compute_pace_ladder(
    best_rpi: float,
    anchor_type: str = "marathon",
) -> PaceLadder:
    """Build a full pace ladder from an athlete's RPI.

    Args:
        best_rpi: The athlete's best Running Performance Index.
        anchor_type: "marathon" or "5k" — determines the 100% reference.

    Returns:
        PaceLadder with both named Daniels zones and percentage rungs.
    """
    if best_rpi <= 0:
        raise ValueError("Cannot compute pace ladder with RPI <= 0")

    daniels = calculate_paces_from_rpi(best_rpi)
    anchor = _compute_anchor_pace(best_rpi, anchor_type, daniels)

    # Convert all Daniels zones to sec/km
    daniels_sec_km = {
        zone: _min_per_mi_to_sec_per_km(pace)
        for zone, pace in daniels.items()
    }

    # Build percentage ladder from anchor.
    # % anchor refers to SPEED, not pace.  Faster = higher %.
    # 90% of anchor speed = anchor_pace / 0.90 = anchor_pace * (1 / 0.90)
    # In general: pace_at_pct = anchor_pace * (100 / pct)
    paces: Dict[int, float] = {}
    for pct in LADDER_RUNGS:
        paces[pct] = anchor * (100.0 / pct)

    # The `paces` dict stays purely arithmetic.  Named Daniels zones
    # are stored as separate fields on PaceLadder.  When a workout is
    # labeled by zone name (e.g. "threshold"), use the named field.
    # When it's labeled by percentage (e.g. "90% MP"), use the dict.
    # This avoids inversions from pinning Daniels values at rungs
    # where the arithmetic disagrees.

    return PaceLadder(
        paces=paces,
        anchor_pace_sec_per_km=anchor,
        anchor_type=anchor_type,
        easy=daniels_sec_km["easy"],
        long=daniels_sec_km["long"],
        marathon=daniels_sec_km["marathon"],
        threshold=daniels_sec_km["threshold"],
        interval=daniels_sec_km["interval"],
        repetition=daniels_sec_km["repetition"],
        recovery=daniels_sec_km["recovery"],
    )



def format_pace_sec_km(sec_per_km: float, unit: str = "mi") -> str:
    """Format pace for athlete display.

    Args:
        sec_per_km: Pace in seconds per km (internal representation).
        unit: "mi" for min/mi, "km" for min/km.

    Returns:
        Formatted string like "6:32".
    """
    if unit == "mi":
        total_sec = sec_per_km * MI_TO_KM
    else:
        total_sec = sec_per_km
    minutes = int(total_sec) // 60
    seconds = int(total_sec) % 60
    return f"{minutes}:{seconds:02d}"


def format_pace_range_sec_km(
    sec_per_km: float,
    range_sec: int = 10,
    unit: str = "mi",
) -> str:
    """Format pace as a range for athlete display.

    Args:
        sec_per_km: Center pace in seconds per km.
        range_sec: Half-width of the range in seconds (per display unit).
        unit: "mi" or "km".
    """
    if unit == "mi":
        center_sec = sec_per_km * MI_TO_KM
    else:
        center_sec = sec_per_km
    lo = (center_sec - range_sec) / (MI_TO_KM if unit == "mi" else 1.0)
    hi = (center_sec + range_sec) / (MI_TO_KM if unit == "mi" else 1.0)
    return f"{format_pace_sec_km(lo, unit)}-{format_pace_sec_km(hi, unit)}"
