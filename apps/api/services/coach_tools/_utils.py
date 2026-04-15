from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)

from models import Athlete
from core.date_utils import calculate_age

_M_PER_MI = 1609.344


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()



def _mi_from_m(meters: Optional[int | float]) -> Optional[float]:
    if meters is None:
        return None
    try:
        return float(meters) / _M_PER_MI
    except Exception:
        return None



def _pace_str_mi(seconds: Optional[int], meters: Optional[int]) -> Optional[str]:
    if not seconds or not meters or meters <= 0:
        return None
    pace_s_per_mi = seconds / (meters / _M_PER_MI)
    m = int(pace_s_per_mi // 60)
    s = int(round(pace_s_per_mi % 60))
    return f"{m}:{s:02d}/mi"



def _pace_seconds_from_text(pace_text: Optional[str]) -> Optional[int]:
    if not pace_text:
        return None
    cleaned = str(pace_text).strip()
    if "/" in cleaned:
        cleaned = cleaned.split("/", 1)[0]
    parts = cleaned.split(":")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        return None



def _fmt_mmss(total_seconds: int) -> str:
    total_seconds = abs(int(total_seconds))
    m = total_seconds // 60
    s = total_seconds % 60
    return f"{m}:{s:02d}"



def _relative_date(target: date, reference: Optional[date] = None) -> str:
    """Pre-compute a human-readable relative time string.

    Past dates  → "(today)", "(yesterday)", "(3 days ago)", "(2 weeks ago)"
    Future dates → "(tomorrow)", "(in 3 days)", "(in 2 weeks)"

    Every date entering an LLM prompt MUST use this — the LLM must never
    compute relative time itself (it gets it wrong).
    """
    ref = reference or date.today()
    delta = (ref - target).days

    if delta == 0:
        return "(today)"
    elif delta == 1:
        return "(yesterday)"
    elif delta == -1:
        return "(tomorrow)"
    elif delta < 0:
        future = abs(delta)
        if future >= 7 and future % 7 == 0:
            return f"(in {future // 7} weeks)"
        return f"(in {future} days)"
    elif delta <= 30:
        if delta >= 14 and delta % 7 == 0:
            return f"({delta // 7} weeks ago)"
        return f"({delta} days ago)"
    elif delta <= 90:
        weeks = delta // 7
        days_rem = delta % 7
        if days_rem == 0:
            return f"({weeks} weeks ago)"
        return f"({weeks}w {days_rem}d ago)"
    else:
        return f"({delta} days ago)"



def _preferred_units(db: Session, athlete_id: UUID) -> str:
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    units = (athlete.preferred_units if athlete else None) or "metric"
    return units if units in ("metric", "imperial") else "metric"



def _pace_str(seconds: Optional[int], meters: Optional[int]) -> Optional[str]:
    if not seconds or not meters or meters <= 0:
        return None
    pace_s_per_km = seconds / (meters / 1000.0)
    m = int(pace_s_per_km // 60)
    s = int(round(pace_s_per_km % 60))
    return f"{m}:{s:02d}/km"



def _interpret_nutrition_correlation(key: str, r: float) -> str:
    """Interpret correlation coefficient for nutrition."""
    if abs(r) < 0.1:
        return "No meaningful relationship found"

    # Efficiency (pace/HR) is directionally ambiguous — correlation sign
    # cannot determine better/worse.  See Athlete Trust Safety Contract
    # in n1_insight_generator.py.  Use neutral association language.
    if "efficiency" in key and "delta" not in key:
        if abs(r) > 0.3:
            return f"Notable association with efficiency (r={r:.2f}) — review with context"
        elif abs(r) > 0.1:
            return f"Mild association with efficiency (r={r:.2f})"

    if "delta" in key:
        if r < -0.3:
            return "Strong recovery benefit: higher protein -> faster recovery"
        elif r < -0.1:
            return "Moderate recovery benefit"
        elif r > 0.1:
            return "No recovery benefit detected"

    return f"Correlation: {r:.2f}"




def _format_run_context(run: dict) -> str:
    """Compact elevation + weather suffix for a recent-run line."""
    parts = []
    elev = run.get("elevation_gain_ft")
    if elev is not None and elev > 0:
        parts.append(f"+{int(elev)}ft")
    temp = run.get("temperature_f")
    if temp is not None:
        parts.append(f"{temp:.0f}°F")
    hum = run.get("humidity_pct")
    if hum is not None and temp is not None:
        parts.append(f"{int(hum)}%rh")
    return f" [{', '.join(parts)}]" if parts else ""



def _guardrails_from_pain(pain_flag: str) -> List[str]:
    if pain_flag == "pain":
        return [
            "Stop condition: pain while running => do not run; consult a clinician if it persists.",
            "No intensity. No 'push through'.",
        ]
    if pain_flag == "niggle":
        return [
            "Stop condition: pain increases or alters gait => stop.",
            "Keep intensity easy; skip quality if it feels off.",
            "No ramp jumps this week.",
        ]
    return [
        "Stop condition: sharp pain or gait change => stop.",
        "Keep easy days easy; quality stays inside prescription.",
    ]



