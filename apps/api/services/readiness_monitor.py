"""Overreaching Risk Watchdog (Discovery Engine V2 — Layer 6).

Multi-signal convergence detector that flags specific risk patterns.
This is operational monitoring, NOT a statistical test — it does not
produce CorrelationFinding rows.

Architecturally separate from readiness_score.py (which produces a
single scalar readiness score for display). The watchdog detects
simultaneous adverse trends across multiple sensitive signals.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class OverreachingAssessment:
    athlete_id: UUID
    target_date: date
    risk_level: str              # "low", "elevated", "high"
    red_count: int
    contributing_signals: List[str]
    sustained_days: int          # consecutive days at elevated+
    details: Dict[str, float] = field(default_factory=dict)


def _compute_trend(values: List[float]) -> Optional[float]:
    """Simple linear regression slope over a list of values."""
    n = len(values)
    if n < 3:
        return None
    xs = list(range(n))
    x_mean = sum(xs) / n
    y_mean = sum(values) / n
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, values))
    den = sum((x - x_mean) ** 2 for x in xs)
    if den == 0:
        return None
    return num / den


def _signal_sd(values: List[float]) -> float:
    """Standard deviation of a value list."""
    if len(values) < 2:
        return 1.0
    m = sum(values) / len(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / (len(values) - 1)) or 1.0


def evaluate_overreaching_risk(
    athlete_id: UUID,
    target_date: date,
    db: Session,
    lookback_days: int = 30,
) -> OverreachingAssessment:
    """Evaluate overreaching risk for an athlete on a given date.

    Monitors:
    1. HRV trend (5d) — declining = bad
    2. Resting HR trend (5d) — rising = bad
    3. TSB — deep negative = bad
    4. Sleep score trend (5d) — declining = bad

    Flags:
    - 3+ red signals = "high" risk
    - 2+ red for 3+ days = "elevated" (sustained)
    - else "low"

    Thresholds start at 1 SD from baseline, calibrated per-athlete later.
    """
    from models import GarminDay

    window_start = target_date - timedelta(days=lookback_days)

    gd_rows = (
        db.query(GarminDay)
        .filter(
            GarminDay.athlete_id == athlete_id,
            GarminDay.calendar_date >= window_start,
            GarminDay.calendar_date <= target_date,
        )
        .order_by(GarminDay.calendar_date)
        .all()
    )

    hrv_series = []
    rhr_series = []
    sleep_series = []

    for row in gd_rows:
        hrv = getattr(row, "hrv_overnight_avg", None) or getattr(row, "hrv_5min_high", None)
        rhr = getattr(row, "resting_hr", None)
        sleep = getattr(row, "sleep_score", None)

        if hrv is not None:
            hrv_series.append((row.calendar_date, float(hrv)))
        if rhr is not None:
            rhr_series.append((row.calendar_date, float(rhr)))
        if sleep is not None:
            sleep_series.append((row.calendar_date, float(sleep)))

    tsb_value = None
    try:
        from services.training_load import TrainingLoadCalculator
        calc = TrainingLoadCalculator(db)
        result = calc.calculate_training_load(athlete_id, target_date)
        tsb_value = result.current_tsb
    except Exception:
        pass

    red_count = 0
    contributing: List[str] = []
    details: Dict[str, float] = {}

    recent_5d = [v for d, v in hrv_series if (target_date - d).days <= 5]
    if len(recent_5d) >= 3:
        trend = _compute_trend(recent_5d)
        if trend is not None:
            all_vals = [v for _, v in hrv_series]
            sd = _signal_sd(all_vals)
            threshold = -sd / 5
            details["hrv_trend_5d"] = round(trend, 4)
            details["hrv_threshold"] = round(threshold, 4)
            if trend < threshold:
                red_count += 1
                contributing.append("hrv_declining")

    recent_rhr_5d = [v for d, v in rhr_series if (target_date - d).days <= 5]
    if len(recent_rhr_5d) >= 3:
        trend = _compute_trend(recent_rhr_5d)
        if trend is not None:
            all_vals = [v for _, v in rhr_series]
            sd = _signal_sd(all_vals)
            threshold = sd / 5
            details["rhr_trend_5d"] = round(trend, 4)
            details["rhr_threshold"] = round(threshold, 4)
            if trend > threshold:
                red_count += 1
                contributing.append("rhr_rising")

    if tsb_value is not None:
        details["tsb"] = round(tsb_value, 1)
        if tsb_value < -20:
            red_count += 1
            contributing.append("tsb_deep_negative")

    recent_sleep_5d = [v for d, v in sleep_series if (target_date - d).days <= 5]
    if len(recent_sleep_5d) >= 3:
        trend = _compute_trend(recent_sleep_5d)
        if trend is not None:
            all_vals = [v for _, v in sleep_series]
            sd = _signal_sd(all_vals)
            threshold = -sd / 5
            details["sleep_trend_5d"] = round(trend, 4)
            details["sleep_threshold"] = round(threshold, 4)
            if trend < threshold:
                red_count += 1
                contributing.append("sleep_declining")

    sustained_days = 0
    if red_count >= 2:
        for lookback in range(1, 8):
            prev_date = target_date - timedelta(days=lookback)
            prev_red = 0

            prev_hrv = [v for d, v in hrv_series if (prev_date - d).days <= 5 and d <= prev_date]
            if len(prev_hrv) >= 3:
                t = _compute_trend(prev_hrv)
                if t is not None:
                    all_vals = [v for _, v in hrv_series]
                    if t < -_signal_sd(all_vals) / 5:
                        prev_red += 1

            prev_rhr = [v for d, v in rhr_series if (prev_date - d).days <= 5 and d <= prev_date]
            if len(prev_rhr) >= 3:
                t = _compute_trend(prev_rhr)
                if t is not None:
                    all_vals = [v for _, v in rhr_series]
                    if t > _signal_sd(all_vals) / 5:
                        prev_red += 1

            if prev_red >= 2:
                sustained_days += 1
            else:
                break

    if red_count >= 3:
        risk_level = "high"
    elif red_count >= 2 and sustained_days >= 3:
        risk_level = "elevated"
    elif red_count >= 2:
        risk_level = "elevated"
    else:
        risk_level = "low"

    return OverreachingAssessment(
        athlete_id=athlete_id,
        target_date=target_date,
        risk_level=risk_level,
        red_count=red_count,
        contributing_signals=contributing,
        sustained_days=sustained_days,
        details=details,
    )
