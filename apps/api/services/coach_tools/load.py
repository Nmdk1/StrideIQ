from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)

from models import Activity, Athlete
from core.date_utils import calculate_age
from services.training_load import TrainingLoadCalculator
from services.recovery_metrics import (
    calculate_recovery_half_life,
    calculate_durability_index,
    detect_false_fitness,
    detect_masked_fatigue,
)
from services.coach_tools._utils import (
    _iso, _mi_from_m, _pace_str_mi, _pace_str, _relative_date,
    _preferred_units, _fmt_mmss, _M_PER_MI,
)


def get_training_load(db: Session, athlete_id: UUID) -> Dict[str, Any]:
    """
    CTL/ATL/TSB summary using TrainingLoadCalculator.
    """
    from services.timezone_utils import get_athlete_timezone_from_db, athlete_local_today
    _tz = get_athlete_timezone_from_db(db, athlete_id)
    _today = athlete_local_today(_tz)
    now = datetime.utcnow()
    calc = TrainingLoadCalculator(db)
    summary = calc.calculate_training_load(athlete_id)
    zone_info = calc.get_tsb_zone(summary.current_tsb, athlete_id=athlete_id)

    # --- Narrative ---
    ctl_v = round(summary.current_ctl, 1) if summary.current_ctl is not None else "?"
    atl_v = round(summary.current_atl, 1) if summary.current_atl is not None else "?"
    tsb_v = round(summary.current_tsb, 1) if summary.current_tsb is not None else "?"
    ratio_note = ""
    if summary.current_ctl and summary.current_atl:
        ratio = summary.current_atl / summary.current_ctl if summary.current_ctl > 0 else 0
        if ratio > 1.3:
            ratio_note = " Acute:Chronic ratio is high — coach should recommend recovery."
        elif ratio > 1.1:
            ratio_note = " Acute:Chronic ratio is moderately elevated."

    narrative = (
        f"(INTERNAL — translate for athlete, never quote raw numbers.) "
        f"CTL: {ctl_v}, ATL: {atl_v}, TSB: {tsb_v}. "
        f"Zone: {zone_info.label} — {zone_info.description} "
        f"Phase: {summary.training_phase or 'N/A'}.{ratio_note}"
    )

    return {
        "ok": True,
        "tool": "get_training_load",
        "generated_at": _iso(now),
        "narrative": narrative,
        "data": {
            "atl": summary.current_atl,
            "ctl": summary.current_ctl,
            "tsb": summary.current_tsb,
            "atl_trend": summary.atl_trend,
            "ctl_trend": summary.ctl_trend,
            "tsb_trend": summary.tsb_trend,
            "training_phase": summary.training_phase,
            "recommendation": summary.recommendation,
            "tsb_zone": {
                "zone": zone_info.zone.value,
                "label": zone_info.label,
                "description": zone_info.description,
                "color": zone_info.color,
                "is_race_window": zone_info.is_race_window,
            },
        },
        "evidence": [
            {
                "type": "derived",
                "id": f"training_load:{str(athlete_id)}",
                "date": _today.isoformat(),
                "value": f"ATL {summary.current_atl}, CTL {summary.current_ctl}, TSB {summary.current_tsb} ({zone_info.zone.value})",
                # Back-compat keys
                "metric_set": "training_load",
                "as_of_date": _today.isoformat(),
                "source": "TrainingLoadCalculator.calculate_training_load",
            }
        ],
    }



def get_recovery_status(db: Session, athlete_id: UUID) -> Dict[str, Any]:
    """
    Recovery metrics: half-life, durability, overtraining risk signals.
    """
    from services.timezone_utils import get_athlete_timezone_from_db, athlete_local_today
    _tz = get_athlete_timezone_from_db(db, athlete_id)
    _today = athlete_local_today(_tz)
    now = datetime.utcnow()
    try:
        athlete_id_str = str(athlete_id)

        # NOTE: recovery_metrics.calculate_recovery_half_life returns hours; convert to days for coach-facing output.
        half_life_hours = calculate_recovery_half_life(db, athlete_id_str)
        half_life_days = round(half_life_hours / 24.0, 2) if half_life_hours is not None else None

        durability = calculate_durability_index(db, athlete_id_str)
        false_fitness = detect_false_fitness(db, athlete_id_str)
        masked_fatigue = detect_masked_fatigue(db, athlete_id_str)

        # --- Narrative ---
        n_parts: List[str] = []
        if half_life_days is not None:
            n_parts.append(f"Recovery half-life: {half_life_days} days.")
        else:
            n_parts.append("Recovery half-life: insufficient data.")
        if durability is not None:
            dur_val = round(durability, 1) if isinstance(durability, (int, float)) else durability
            n_parts.append(f"Durability index: {dur_val}.")
        if false_fitness:
            n_parts.append("WARNING: False fitness signals detected.")
        if masked_fatigue:
            n_parts.append("WARNING: Masked fatigue signals detected.")
        if not false_fitness and not masked_fatigue:
            n_parts.append("No red flags in recovery signals.")
        narrative = " ".join(n_parts)

        return {
            "ok": True,
            "tool": "get_recovery_status",
            "generated_at": _iso(now),
            "narrative": narrative,
            "data": {
                "recovery_half_life_days": half_life_days,
                "durability_index": durability,
                "false_fitness_signals": false_fitness,
                "masked_fatigue_signals": masked_fatigue,
            },
            "evidence": [
                {
                    "type": "derived",
                    "id": f"recovery_status:{str(athlete_id)}",
                    "date": _today.isoformat(),
                    "value": (
                        f"Recovery half-life: {half_life_days} days"
                        if half_life_days is not None
                        else "Recovery half-life: insufficient data"
                    ),
                }
            ],
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "get_recovery_status", "error": str(e)}



def get_weekly_volume(db: Session, athlete_id: UUID, weeks: int = 12) -> Dict[str, Any]:
    """
    Weekly rollups of run volume (distance/time/count).

    This is designed for questions like:
    - "What were my highest-volume weeks recently?"
    - "How consistent have I been since returning from injury?"
    """
    from services.timezone_utils import get_athlete_timezone_from_db, to_activity_local_date, athlete_local_today
    _tz = get_athlete_timezone_from_db(db, athlete_id)
    now = datetime.utcnow()
    try:
        weeks = max(1, min(int(weeks), 104))  # cap at ~2 years
        units = _preferred_units(db, athlete_id)

        # Build week buckets aligned to Monday starts (ISO week).
        today = athlete_local_today(_tz)
        end_week_start = today - timedelta(days=today.weekday())  # Monday
        start_week_start = end_week_start - timedelta(days=7 * (weeks - 1))
        start_dt = datetime.combine(start_week_start, datetime.min.time())
        end_dt = datetime.combine(end_week_start + timedelta(days=7), datetime.min.time())

        runs = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete_id,
                Activity.sport == "run",
                Activity.start_time >= start_dt,
                Activity.start_time < end_dt,
            )
            .order_by(Activity.start_time.asc())
            .all()
        )

        buckets: Dict[str, Dict[str, Any]] = {}
        for w in range(weeks):
            ws = start_week_start + timedelta(days=7 * w)
            key = ws.isoformat()
            buckets[key] = {
                "week_start": key,
                "week_end": (ws + timedelta(days=6)).isoformat(),
                "run_count": 0,
                "total_distance_m": 0.0,
                "total_duration_s": 0.0,
            }

        for a in runs:
            d = to_activity_local_date(a, _tz)
            ws = d - timedelta(days=d.weekday())
            key = ws.isoformat()
            if key not in buckets:
                continue
            b = buckets[key]
            b["run_count"] += 1
            b["total_distance_m"] += float(a.distance_m or 0)
            b["total_duration_s"] += float(a.duration_s or 0)

        current_week_key = end_week_start.isoformat()
        week_rows: List[Dict[str, Any]] = []
        for key in sorted(buckets.keys()):
            b = buckets[key]
            dist_m = float(b["total_distance_m"])
            dur_s = float(b["total_duration_s"])
            row: Dict[str, Any] = {
                "week_start": b["week_start"],
                "week_end": b["week_end"],
                "run_count": int(b["run_count"]),
                "total_distance_km": round(dist_m / 1000.0, 2),
                "total_distance_mi": round(dist_m / _M_PER_MI, 2),
                "total_duration_hr": round(dur_s / 3600.0, 2),
            }
            # Mark the current (in-progress) week so the coach doesn't
            # confuse partial data with a completed week.
            if key == current_week_key:
                days_elapsed = (today - end_week_start).days + 1  # 1-7
                row["is_current_week"] = True
                row["days_elapsed"] = days_elapsed
                row["days_remaining"] = 7 - days_elapsed
                row["note"] = f"IN PROGRESS — only {days_elapsed} of 7 days completed"
            week_rows.append(row)

        # Evidence: cite the top 3 weeks by distance in preferred units
        def _week_magnitude(wr: Dict[str, Any]) -> float:
            return float(wr.get("total_distance_mi" if units == "imperial" else "total_distance_km") or 0)

        top_weeks = sorted(week_rows, key=_week_magnitude, reverse=True)[:3]
        evidence: List[Dict[str, Any]] = []
        for w in top_weeks:
            dist = w["total_distance_mi"] if units == "imperial" else w["total_distance_km"]
            unit = "mi" if units == "imperial" else "km"
            partial_note = " (IN PROGRESS — week not complete)" if w.get("is_current_week") else ""
            evidence.append(
                {
                    "type": "derived",
                    "id": f"weekly_volume:{str(athlete_id)}:{w['week_start']}",
                    "date": w["week_start"],
                    "value": f"Week of {w['week_start']}: {dist:.1f} {unit} across {w['run_count']} runs{partial_note}",
                }
            )

        # --- Narrative ---
        unit_label = "mi" if units == "imperial" else "km"
        dist_key = "total_distance_mi" if units == "imperial" else "total_distance_km"

        # Identify the current (partial) week and the last full week
        current_row = next((w for w in week_rows if w.get("is_current_week")), None)
        completed_rows = [w for w in week_rows if not w.get("is_current_week")]
        last_full = completed_rows[-1] if completed_rows else None

        lines: List[str] = []
        if current_row:
            lines.append(
                f"This week (in progress, {current_row['days_elapsed']} of 7 days): "
                f"{current_row[dist_key]:.1f} {unit_label} across {current_row['run_count']} runs. "
                f"DO NOT treat this as a full week."
            )
        if last_full:
            try:
                _lf_rel = _relative_date(date.fromisoformat(last_full['week_start']), today)
            except (ValueError, TypeError):
                _lf_rel = ""
            lines.append(
                f"Last full week ({last_full['week_start']} {_lf_rel}): "
                f"{last_full[dist_key]:.1f} {unit_label} across {last_full['run_count']} runs."
            )

        # 4-week trend
        recent_4 = completed_rows[-4:] if len(completed_rows) >= 4 else completed_rows
        if len(recent_4) >= 2:
            vols = [w[dist_key] for w in recent_4]
            trajectory = "rising" if vols[-1] > vols[0] else ("falling" if vols[-1] < vols[0] else "flat")
            lines.append(
                f"Last {len(recent_4)} full weeks trajectory: {trajectory} "
                f"({' → '.join(f'{v:.0f}' for v in vols)} {unit_label})."
            )

        # Peak week
        if completed_rows:
            peak = max(completed_rows, key=lambda w: w[dist_key])
            lines.append(
                f"Peak week in window: {peak['week_start']} at {peak[dist_key]:.1f} {unit_label}."
            )

        narrative = " ".join(lines) if lines else "No weekly volume data available."

        return {
            "ok": True,
            "tool": "get_weekly_volume",
            "generated_at": _iso(now),
            "narrative": narrative,
            "data": {
                "preferred_units": units,
                "weeks": weeks,
                "week_start_first": start_week_start.isoformat(),
                "week_start_last": end_week_start.isoformat(),
                "weeks_data": week_rows,
            },
            "evidence": evidence,
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "get_weekly_volume", "error": str(e)}



def get_training_load_history(db: Session, athlete_id: UUID, days: int = 42) -> Dict[str, Any]:
    """
    Phase 3: Training load history showing ATL/CTL/TSB trends over time.

    Returns daily snapshots of training load metrics to understand load progression.
    Critical for periodization analysis and injury risk assessment.
    """
    from services.timezone_utils import get_athlete_timezone_from_db, to_activity_local_date
    _tz = get_athlete_timezone_from_db(db, athlete_id)
    now = datetime.utcnow()
    days = max(7, min(int(days), 90))

    try:
        # Get activities for the window + buffer for CTL calculation (42 days for CTL)
        buffer_days = 42
        cutoff = now - timedelta(days=days + buffer_days)

        runs = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete_id,
                Activity.sport == "run",
                Activity.start_time >= cutoff,
            )
            .order_by(Activity.start_time.asc())
            .all()
        )

        if not runs:
            return {
                "ok": True,
                "tool": "get_training_load_history",
                "generated_at": _iso(now),
                "data": {
                    "window_days": days,
                    "message": "No training data available for load calculation.",
                },
                "evidence": [],
            }

        # Calculate daily TSS values
        daily_tss: Dict[date, float] = {}
        for a in runs:
            run_date = to_activity_local_date(a, _tz)
            # Simple TSS approximation: (duration_min * intensity_score / 100) or duration-based fallback
            duration_min = (a.duration_s or 0) / 60
            intensity = (a.intensity_score or 50) / 100  # Default to moderate if unknown
            tss = duration_min * intensity
            daily_tss[run_date] = daily_tss.get(run_date, 0) + tss

        # Calculate ATL (7-day) and CTL (42-day) for each day in window
        atl_decay = 1 - (2 / 8)  # 7-day time constant
        ctl_decay = 1 - (2 / 43)  # 42-day time constant

        history: List[Dict[str, Any]] = []
        evidence: List[Dict[str, Any]] = []

        atl = 0.0
        ctl = 0.0

        start_date = (now - timedelta(days=days + buffer_days)).date()
        end_date = now.date()
        current_date = start_date

        while current_date <= end_date:
            day_tss = daily_tss.get(current_date, 0)

            # Exponential weighted moving average
            atl = atl * atl_decay + day_tss * (1 - atl_decay)
            ctl = ctl * ctl_decay + day_tss * (1 - ctl_decay)
            tsb = ctl - atl

            # Only include days within the requested window
            if current_date >= (now - timedelta(days=days)).date():
                # Determine form state
                form_state = "fresh" if tsb > 10 else ("fatigued" if tsb < -10 else "balanced")

                # Risk assessment
                if atl > ctl * 1.3:
                    risk = "high"
                elif atl > ctl * 1.1:
                    risk = "moderate"
                else:
                    risk = "low"

                history.append({
                    "date": current_date.isoformat(),
                    "atl": round(atl, 1),
                    "ctl": round(ctl, 1),
                    "tsb": round(tsb, 1),
                    "form_state": form_state,
                    "injury_risk": risk,
                    "day_tss": round(day_tss, 1),
                })

            current_date += timedelta(days=1)

        # Get current state (latest entry)
        current = history[-1] if history else None

        # Calculate trends
        if len(history) >= 7:
            recent_ctl = [h["ctl"] for h in history[-7:]]
            older_ctl = [h["ctl"] for h in history[-14:-7]] if len(history) >= 14 else []
            ctl_trend = None
            if older_ctl:
                recent_avg = sum(recent_ctl) / len(recent_ctl)
                older_avg = sum(older_ctl) / len(older_ctl)
                delta_pct = ((recent_avg - older_avg) / older_avg * 100) if older_avg else 0
                if delta_pct > 5:
                    ctl_trend = "building"
                elif delta_pct < -5:
                    ctl_trend = "tapering"
                else:
                    ctl_trend = "maintaining"
        else:
            ctl_trend = None

        # Build evidence from key dates
        for h in history[-7:]:
            evidence.append({
                "type": "load_snapshot",
                "date": h["date"],
                "value": f"ATL={h['atl']:.0f} CTL={h['ctl']:.0f} TSB={h['tsb']:+.0f} ({h['form_state']})",
            })

        # --- Narrative ---
        tlh_parts: List[str] = [f"Training load history over {days} days."]
        if current:
            tlh_parts.append(
                f"Current: ATL={current['atl']:.0f}, CTL={current['ctl']:.0f}, "
                f"TSB={current['tsb']:+.0f} ({current['form_state']}). "
                f"Injury risk: {current['injury_risk']}."
            )
        if ctl_trend:
            tlh_parts.append(f"CTL trend: {ctl_trend}.")
        tlh_narrative = " ".join(tlh_parts)

        return {
            "ok": True,
            "tool": "get_training_load_history",
            "generated_at": _iso(now),
            "narrative": tlh_narrative,
            "data": {
                "window_days": days,
                "current_state": current,
                "ctl_trend": ctl_trend,
                "ctl_trend_note": {
                    "building": "Fitness is increasing - good for base building",
                    "tapering": "Fitness is decreasing - expected before races or during recovery",
                    "maintaining": "Fitness is stable - good for maintenance phases",
                }.get(ctl_trend, None),
                "history": history,
                "guidance": {
                    "tsb_interpretation": "TSB > 10: Fresh/ready to race. TSB 0-10: Balanced. TSB < 0: Fatigued (training hard).",
                    "injury_risk_note": "High risk when ATL > 1.3x CTL (acute:chronic ratio too high).",
                },
            },
            "evidence": evidence,
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "get_training_load_history", "error": str(e)}



