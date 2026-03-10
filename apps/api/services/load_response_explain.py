"""
Load Response Explain Service

Explains why a week was labeled adaptation_signal/load_signal/stable/neutral in load-response.

This is NOT a correlational attribution (needs many samples). Instead:
- Shows the exact rule used for classification (delta thresholds)
- Shows week metrics vs previous week
- Surfaces the biggest "signal deviations" vs a recent baseline (sleep/stress/soreness/HRV/resting HR, etc.)

Note: Labels are intentionally neutral because the pace/HR efficiency ratio is
directionally ambiguous.  See Athlete Trust Safety Contract in n1_insight_generator.py.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from models import Activity, DailyCheckin
from services.efficiency_calculation import calculate_activity_efficiency_with_decoupling
from services.efficiency_analytics import bulk_load_splits_for_activities, is_quality_activity


DELTA_POSITIVE_SHIFT = -0.5  # Negative Δ = pace/HR ratio decreased
DELTA_NEGATIVE_SHIFT = 0.5  # Positive Δ = pace/HR ratio increased
# CAUTION: Pace/HR ratio is directionally ambiguous.  These thresholds
# detect meaningful week-over-week change, but the labels below
# ("adaptation signal" / "load signal" / "stable") intentionally avoid
# claiming "productive" or "harmful" because both improvement modes
# (faster pace at same HR, or same pace at lower HR) move the ratio
# in opposite directions.  See Athlete Trust Safety Contract in
# n1_insight_generator.py.
DELTA_FLAT_ABS = 0.1   # Flat zone


FACTOR_DEFS: Dict[str, Dict[str, Any]] = {
    "sleep_duration": {"label": "Sleep Duration (h)", "direction": "higher_better"},
    "hrv": {"label": "HRV", "direction": "higher_better"},
    "resting_hr": {"label": "Resting HR", "direction": "lower_better"},
    "stress": {"label": "Stress", "direction": "lower_better"},
    "soreness": {"label": "Soreness", "direction": "lower_better"},
    "fatigue": {"label": "Fatigue", "direction": "lower_better"},
}

ACTIVITY_FACTOR_DEFS: Dict[str, Dict[str, Any]] = {
    "intensity_score": {"label": "Intensity score", "direction": "higher_more_strain"},
    "decoupling_percent": {"label": "Decoupling (%)", "direction": "lower_better"},
    "avg_hr": {"label": "Avg HR", "direction": "lower_better"},
    "pace_per_mile": {"label": "Pace (min/mi)", "direction": "lower_better"},
    "temperature_f": {"label": "Temperature (°F)", "direction": "lower_better"},
    "humidity_pct": {"label": "Humidity (%)", "direction": "lower_better"},
}


def _normalize_to_monday(d: date) -> date:
    # Monday is 0
    return d - timedelta(days=d.weekday())


def _safe_avg(xs: List[float]) -> Optional[float]:
    if not xs:
        return None
    return sum(xs) / len(xs)


def _safe_std(xs: List[float], mean: float) -> Optional[float]:
    if len(xs) < 5:
        return None
    var = sum((x - mean) ** 2 for x in xs) / (len(xs) - 1)
    if var <= 0:
        return None
    return var ** 0.5


def _extract_checkin_factor(checkin: DailyCheckin, key: str) -> Optional[float]:
    """Extract a wellness factor from a DailyCheckin by logical key name."""
    if key == "sleep_duration":
        return float(checkin.sleep_h) if checkin.sleep_h is not None else None
    if key == "hrv":
        v = checkin.hrv_rmssd if checkin.hrv_rmssd is not None else checkin.hrv_sdnn
        return float(v) if v is not None else None
    if key == "resting_hr":
        return float(checkin.resting_hr) if checkin.resting_hr is not None else None
    if key == "stress":
        return float(checkin.stress_1_5) if checkin.stress_1_5 is not None else None
    if key == "soreness":
        return float(checkin.soreness_1_5) if checkin.soreness_1_5 is not None else None
    if key == "fatigue":
        return float(checkin.rpe_1_10) if checkin.rpe_1_10 is not None else None
    return None


def _classify_load_type(efficiency_delta: Optional[float], avg_efficiency: Optional[float]) -> str:
    """Classify week-over-week efficiency shift.

    Uses neutral labels because the pace/HR ratio is directionally ambiguous.
    "adaptation_signal" and "load_signal" replace the old "productive" /
    "harmful" labels to avoid false directional claims.
    See Athlete Trust Safety Contract in n1_insight_generator.py.
    """
    load_type = "neutral"
    if efficiency_delta is not None and avg_efficiency:
        if efficiency_delta < DELTA_POSITIVE_SHIFT:
            load_type = "adaptation_signal"
        elif efficiency_delta > DELTA_NEGATIVE_SHIFT:
            load_type = "load_signal"
        elif abs(efficiency_delta) < DELTA_FLAT_ABS:
            load_type = "stable"
    return load_type


def explain_load_response_week(athlete_id: str, week_start: date, db: Session) -> Dict[str, Any]:
    wk0 = _normalize_to_monday(week_start)
    wk1 = wk0 + timedelta(days=7)
    prev0 = wk0 - timedelta(days=7)
    prev1 = wk0

    # Pull activities for current + previous week (so we can compute delta)
    acts = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= datetime.combine(prev0, datetime.min.time()),
            Activity.start_time < datetime.combine(wk1, datetime.min.time()),
        )
        .order_by(Activity.start_time.asc())
        .all()
    )
    quality = [a for a in acts if is_quality_activity(a)]

    curr_acts = [a for a in quality if wk0 <= a.start_time.date() < wk1]
    prev_acts = [a for a in quality if prev0 <= a.start_time.date() < prev1]

    def _week_totals(xs: List[Activity]) -> Tuple[float, float, int]:
        total_m = sum(float(a.distance_m or 0) for a in xs)
        total_s = sum(float(a.duration_s or 0) for a in xs)
        return total_m, total_s, len(xs)

    curr_dist_m, curr_dur_s, curr_n = _week_totals(curr_acts)
    prev_dist_m, prev_dur_s, prev_n = _week_totals(prev_acts)

    # Compute efficiency averages using same pipeline as load-response (GAP + decoupling)
    all_ids = [str(a.id) for a in (curr_acts + prev_acts)]
    splits_by_activity = bulk_load_splits_for_activities(all_ids, db) if all_ids else {}

    def _avg_eff(xs: List[Activity]) -> Optional[float]:
        vals: List[float] = []
        for a in xs:
            splits = splits_by_activity.get(str(a.id), [])
            eff = calculate_activity_efficiency_with_decoupling(activity=a, splits=splits, max_hr=None)
            ef = eff.get("efficiency_factor")
            if ef:
                vals.append(float(ef))
        return _safe_avg(vals)

    curr_avg_eff = _avg_eff(curr_acts)
    prev_avg_eff = _avg_eff(prev_acts)
    efficiency_delta = (curr_avg_eff - prev_avg_eff) if (curr_avg_eff is not None and prev_avg_eff is not None) else None

    load_type = _classify_load_type(efficiency_delta, curr_avg_eff)

    # Data quality / confidence (this is a week-over-week signal; small-N can swing).
    # Keep it simple and honest: confidence is about sample size of quality activities.
    confidence = "low"
    if curr_n >= 3 and prev_n >= 3:
        confidence = "high"
    elif curr_n >= 2 and prev_n >= 2:
        confidence = "moderate"

    volume_change_pct = None
    if prev_dist_m > 0:
        volume_change_pct = round((curr_dist_m - prev_dist_m) / prev_dist_m * 100.0, 1)

    # Collect checkins for week and baseline (28d prior to week)
    baseline_start = wk0 - timedelta(days=28)
    baseline_end = wk0 - timedelta(days=1)

    checkins_week = (
        db.query(DailyCheckin)
        .filter(DailyCheckin.athlete_id == athlete_id, DailyCheckin.date >= wk0, DailyCheckin.date < wk1)
        .all()
    )
    checkins_base = (
        db.query(DailyCheckin)
        .filter(DailyCheckin.athlete_id == athlete_id, DailyCheckin.date >= baseline_start, DailyCheckin.date <= baseline_end)
        .all()
    )

    signals: List[Dict[str, Any]] = []
    for factor, meta in FACTOR_DEFS.items():
        w_vals = [v for c in checkins_week if (v := _extract_checkin_factor(c, factor)) is not None]
        b_vals = [v for c in checkins_base if (v := _extract_checkin_factor(c, factor)) is not None]

        w_avg = _safe_avg(w_vals)
        b_avg = _safe_avg(b_vals)
        if w_avg is None or b_avg is None:
            continue

        b_std = _safe_std(b_vals, b_avg) if b_vals else None
        z = None
        if b_std and b_std > 0:
            z = (w_avg - b_avg) / b_std

        delta = w_avg - b_avg

        # Interpret deviation (direction-aware)
        direction = meta["direction"]
        worse = None
        if direction == "higher_better":
            worse = delta < 0
        elif direction == "lower_better":
            worse = delta > 0

        signals.append(
            {
                "factor": factor,
                "label": meta["label"],
                "week_avg": round(w_avg, 2),
                "baseline_avg": round(b_avg, 2),
                "delta": round(delta, 2),
                "z": round(z, 2) if z is not None else None,
                "direction": direction,
                "is_worse": worse,
                "sample_size_week": len(w_vals),
                "sample_size_baseline": len(b_vals),
            }
        )

    # Rank "most notable" signals: prefer statistically meaningful z, fall back to abs(delta)
    def _signal_rank(s: Dict[str, Any]) -> float:
        if s.get("z") is not None:
            return abs(float(s["z"]))
        return abs(float(s.get("delta") or 0))

    signals.sort(key=_signal_rank, reverse=True)
    signals = signals[:6]

    # Activity-derived drivers (activity-first, check-ins are optional).
    baseline_start = wk0 - timedelta(days=28)
    baseline_end = wk0 - timedelta(days=1)

    base_acts = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= datetime.combine(baseline_start, datetime.min.time()),
            Activity.start_time <= datetime.combine(baseline_end, datetime.max.time()),
        )
        .order_by(Activity.start_time.asc())
        .all()
    )
    base_quality = [a for a in base_acts if is_quality_activity(a)]

    base_ids = [str(a.id) for a in base_quality]
    splits_by_base = bulk_load_splits_for_activities(base_ids, db) if base_ids else {}

    def _activity_metric_rows(xs: List[Activity], splits_by: Dict[str, Any]) -> Dict[str, List[float]]:
        out: Dict[str, List[float]] = {k: [] for k in ACTIVITY_FACTOR_DEFS.keys()}
        for a in xs:
            # direct fields
            if a.intensity_score is not None:
                out["intensity_score"].append(float(a.intensity_score))
            if a.avg_hr is not None:
                out["avg_hr"].append(float(a.avg_hr))
            if a.pace_per_mile is not None:
                out["pace_per_mile"].append(float(a.pace_per_mile))
            if a.temperature_f is not None:
                out["temperature_f"].append(float(a.temperature_f))
            if a.humidity_pct is not None:
                out["humidity_pct"].append(float(a.humidity_pct))

            # derived from splits/efficiency calc
            splits = splits_by.get(str(a.id), [])
            eff = calculate_activity_efficiency_with_decoupling(activity=a, splits=splits, max_hr=None)
            dp = eff.get("decoupling_percent")
            if dp is not None:
                out["decoupling_percent"].append(float(dp))
        return out

    curr_ids = [str(a.id) for a in curr_acts]
    splits_by_curr = bulk_load_splits_for_activities(curr_ids, db) if curr_ids else {}

    curr_metrics = _activity_metric_rows(curr_acts, splits_by_curr)
    base_metrics = _activity_metric_rows(base_quality, splits_by_base)

    prev_ids = [str(a.id) for a in prev_acts]
    splits_by_prev = bulk_load_splits_for_activities(prev_ids, db) if prev_ids else {}
    prev_metrics = _activity_metric_rows(prev_acts, splits_by_prev)

    activity_signals: List[Dict[str, Any]] = []
    for key, meta in ACTIVITY_FACTOR_DEFS.items():
        w_avg = _safe_avg(curr_metrics.get(key, []))
        b_avg = _safe_avg(base_metrics.get(key, []))
        if w_avg is None or b_avg is None:
            continue
        delta = w_avg - b_avg

        direction = meta["direction"]
        is_worse = None
        if direction == "lower_better":
            is_worse = delta > 0
        elif direction == "higher_more_strain":
            # Not "bad" per se, but higher strain can explain short-term regression.
            is_worse = delta > 0
        elif direction == "higher_better":
            is_worse = delta < 0

        activity_signals.append(
            {
                "factor": key,
                "label": meta["label"],
                "week_avg": round(w_avg, 2),
                "baseline_avg": round(b_avg, 2),
                "delta": round(delta, 2),
                "direction": direction,
                "is_worse": is_worse,
                "sample_size_week": len(curr_metrics.get(key, [])),
                "sample_size_baseline": len(base_metrics.get(key, [])),
            }
        )

    activity_signals.sort(key=lambda s: abs(float(s.get("delta") or 0)), reverse=True)
    activity_signals = activity_signals[:6]

    # Week-vs-previous drivers (more intuitive than baseline-only and almost always computable).
    week_vs_prev_signals: List[Dict[str, Any]] = []
    for key, meta in ACTIVITY_FACTOR_DEFS.items():
        w_avg = _safe_avg(curr_metrics.get(key, []))
        p_avg = _safe_avg(prev_metrics.get(key, []))
        if w_avg is None or p_avg is None:
            continue
        delta = w_avg - p_avg

        direction = meta["direction"]
        is_worse = None
        if direction == "lower_better":
            is_worse = delta > 0
        elif direction == "higher_more_strain":
            is_worse = delta > 0
        elif direction == "higher_better":
            is_worse = delta < 0

        week_vs_prev_signals.append(
            {
                "factor": key,
                "label": meta["label"],
                "week_avg": round(w_avg, 2),
                "previous_week_avg": round(p_avg, 2),
                "delta": round(delta, 2),
                "direction": direction,
                "is_worse": is_worse,
                "sample_size_week": len(curr_metrics.get(key, [])),
                "sample_size_previous_week": len(prev_metrics.get(key, [])),
            }
        )

    week_vs_prev_signals.sort(key=lambda s: abs(float(s.get("delta") or 0)), reverse=True)
    week_vs_prev_signals = week_vs_prev_signals[:6]

    # Human explanation of classification rule
    rule = {
        "adaptation_signal_if_delta_lt": DELTA_POSITIVE_SHIFT,
        "load_signal_if_delta_gt": DELTA_NEGATIVE_SHIFT,
        "stable_if_abs_delta_lt": DELTA_FLAT_ABS,
        "note": "Efficiency Δ is current_week_avg(pace/HR) - prior_week_avg(pace/HR). Pace/HR ratio is directionally ambiguous — labels indicate magnitude of change, not good/bad. See Athlete Trust Safety Contract.",
    }

    return {
        "week": {
            "week_start": wk0.isoformat(),
            "week_end": (wk1 - timedelta(days=1)).isoformat(),
        },
        "load_type": load_type,
        "confidence": confidence,
        "interpretation": {
            "meaning": "This chart is computed from your runs. The label reflects a week-over-week shift in your efficiency ratio (pace/HR). Because this ratio can move in different directions for different types of improvement, the label indicates change magnitude — not whether the change is good or bad.",
            "taper_cutback_note": "A cutback week or taper can show a shift in efficiency ratio (fewer quality samples, different conditions). Treat this as a flag to inspect context, not as a judgment.",
            "volume_change_pct": volume_change_pct,
        },
        "data_sources": {
            "activities_week": curr_n,
            "activities_previous_week": prev_n,
            "checkins_week": len(checkins_week),
            "checkins_baseline": len(checkins_base),
            "activities_baseline": len(base_quality),
        },
        "rule": rule,
        "metrics": {
            "current": {
                "total_distance_miles": round(curr_dist_m / 1609.34, 2),
                "total_distance_km": round(curr_dist_m / 1000.0, 2),
                "total_duration_hours": round(curr_dur_s / 3600.0, 2),
                "activity_count": curr_n,
                "avg_efficiency": round(curr_avg_eff, 2) if curr_avg_eff is not None else None,
            },
            "previous": {
                "total_distance_miles": round(prev_dist_m / 1609.34, 2),
                "total_distance_km": round(prev_dist_m / 1000.0, 2),
                "total_duration_hours": round(prev_dur_s / 3600.0, 2),
                "activity_count": prev_n,
                "avg_efficiency": round(prev_avg_eff, 2) if prev_avg_eff is not None else None,
            },
            "efficiency_delta": round(efficiency_delta, 2) if efficiency_delta is not None else None,
            "volume_change_pct": volume_change_pct,
        },
        "signals": signals,
        "activity_signals": activity_signals,
        "week_vs_prev_activity_signals": week_vs_prev_signals,
        "generated_at": datetime.utcnow().isoformat(),
    }

