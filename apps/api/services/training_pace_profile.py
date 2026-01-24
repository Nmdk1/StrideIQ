"""
Training Pace Profile

Goal:
- Compute prescriptive training paces ONLY from a race/time-trial performance anchor.
- Use the existing Training Pace Calculator formulas (vdot_calculator.py).
- Avoid "appeasement" from noisy training-run data.

UI note:
- We avoid surfacing "VDOT" branding in product UI. This module uses the existing
  internal naming because the calculator file does.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Optional, Tuple


@dataclass(frozen=True)
class RaceAnchor:
    distance_key: str
    time_seconds: int
    distance_meters: Optional[int] = None
    race_date: Optional[date] = None


def parse_time_to_seconds(s: str) -> Optional[int]:
    """
    Parse "MM:SS" or "HH:MM:SS" to seconds.

    Returns None for invalid inputs.
    """
    if not s:
        return None
    raw = str(s).strip()
    if not raw:
        return None

    parts = raw.split(":")
    if len(parts) not in (2, 3):
        return None

    try:
        nums = [int(p) for p in parts]
    except Exception:
        return None

    if any(n < 0 for n in nums):
        return None

    if len(nums) == 2:
        mm, ss = nums
        if ss >= 60:
            return None
        return mm * 60 + ss

    hh, mm, ss = nums
    if mm >= 60 or ss >= 60:
        return None
    return hh * 3600 + mm * 60 + ss


def _format_time_s(total_seconds: int) -> str:
    if total_seconds < 0:
        total_seconds = 0
    hh = total_seconds // 3600
    mm = (total_seconds % 3600) // 60
    ss = total_seconds % 60
    if hh > 0:
        return f"{hh}:{mm:02d}:{ss:02d}"
    return f"{mm}:{ss:02d}"


def _resolve_distance_meters(distance_key: str, distance_meters: Optional[int]) -> Optional[int]:
    key = (distance_key or "").strip().lower()
    if key in ("other", "custom"):
        try:
            m = int(distance_meters or 0)
        except Exception:
            return None
        return m if m > 0 else None

    from services.vdot_calculator import STANDARD_DISTANCES

    m = STANDARD_DISTANCES.get(key)
    if m is None:
        return None
    # STANDARD_DISTANCES includes floats for some entries (e.g. half_marathon)
    return int(round(float(m)))


def compute_training_pace_profile(anchor: RaceAnchor) -> Tuple[Optional[dict], Optional[str]]:
    """
    Compute a stable pace profile payload from a race anchor.

    Returns: (payload, error_code)
    - payload: dict suitable for API responses and DB persistence
    - error_code: None if ok, else a short machine-readable string
    """
    if not anchor or not anchor.distance_key or not anchor.time_seconds:
        return None, "missing_anchor"

    dm = _resolve_distance_meters(anchor.distance_key, anchor.distance_meters)
    if not dm:
        return None, "unsupported_distance"

    from services.vdot_calculator import calculate_vdot_from_race_time, calculate_training_paces

    vdot = calculate_vdot_from_race_time(float(dm), int(anchor.time_seconds))
    if vdot is None:
        return None, "calc_failed"

    paces = calculate_training_paces(float(vdot)) or {}

    # Keep payload small + UI-friendly; include raw seconds for future use.
    out: dict[str, Any] = {
        "anchor": {
            "distance_key": anchor.distance_key,
            "distance_meters": int(dm),
            "time_seconds": int(anchor.time_seconds),
            "time_display": _format_time_s(int(anchor.time_seconds)),
            "race_date": anchor.race_date.isoformat() if anchor.race_date else None,
        },
        # Avoid trademark exposure in UI surfaces; this is the same scalar used by the calculator.
        "fitness_score": float(vdot),
        "paces": {
            "easy": paces.get("easy"),
            "marathon": paces.get("marathon"),
            "threshold": paces.get("threshold"),
            "interval": paces.get("interval"),
            "repetition": paces.get("repetition"),
        },
        "_raw_seconds_per_mile": {
            "easy_pace_low": paces.get("easy_pace_low"),
            "easy_pace_high": paces.get("easy_pace_high"),
            "marathon_pace": paces.get("marathon_pace"),
            "threshold_pace": paces.get("threshold_pace"),
            "interval_pace": paces.get("interval_pace"),
            "repetition_pace": paces.get("repetition_pace"),
        },
    }

    return out, None

