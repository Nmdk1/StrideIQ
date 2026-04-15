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
from services.coach_tools._utils import (
    _iso, _mi_from_m, _pace_str_mi, _pace_str, _relative_date,
    _preferred_units, _fmt_mmss, _interpret_nutrition_correlation, _M_PER_MI,
)


def get_nutrition_correlations(
    db: Session,
    athlete_id: UUID,
    days: int = 90,
) -> Dict[str, Any]:
    """
    Get activity-linked nutrition correlations.
    """
    from services.timezone_utils import get_athlete_timezone_from_db, athlete_local_today
    _tz = get_athlete_timezone_from_db(db, athlete_id)
    _today = athlete_local_today(_tz)
    now = datetime.utcnow()
    try:
        days = max(30, min(int(days), 365))
        start = now - timedelta(days=days)

        # Local import to avoid circulars.
        from services.correlation_engine import aggregate_activity_nutrition

        data = aggregate_activity_nutrition(str(athlete_id), start, now, db)
        results: Dict[str, Any] = {}

        for key, pairs in (data or {}).items():
            if not pairs:
                results[key] = {
                    "sample_size": 0,
                    "correlation": None,
                    "note": "insufficient data",
                }
                continue

            if len(pairs) < 5:
                results[key] = {
                    "sample_size": len(pairs),
                    "correlation": None,
                    "note": "insufficient data",
                }
                continue

            x_vals = [p[1] for p in pairs]
            y_vals = [p[2] for p in pairs]

            n = len(x_vals)
            mean_x = sum(x_vals) / n
            mean_y = sum(y_vals) / n

            numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_vals, y_vals))
            denom_x = sum((x - mean_x) ** 2 for x in x_vals) ** 0.5
            denom_y = sum((y - mean_y) ** 2 for y in y_vals) ** 0.5

            if denom_x == 0 or denom_y == 0:
                r = 0.0
            else:
                r = numerator / (denom_x * denom_y)

            results[key] = {
                "sample_size": n,
                "correlation": round(float(r), 3),
                "interpretation": _interpret_nutrition_correlation(key, float(r)),
            }

        # --- Narrative ---
        nc_items: List[str] = []
        for key, val in results.items():
            if isinstance(val, dict) and val.get("correlation") is not None:
                interp = val.get("interpretation", "")
                nc_items.append(f"{key}: r={val['correlation']:.2f} ({interp})")
        if nc_items:
            nc_narrative = f"Nutrition correlations over {days} days: " + "; ".join(nc_items[:3]) + "."
        else:
            nc_narrative = f"No significant nutrition correlations found over {days} days."

        return {
            "ok": True,
            "tool": "get_nutrition_correlations",
            "generated_at": _iso(now),
            "narrative": nc_narrative,
            "data": results,
            "evidence": [
                {
                    "type": "derived",
                    "id": f"nutrition_correlations:{str(athlete_id)}",
                    "date": _today.isoformat(),
                    "value": f"Activity-linked nutrition analysis over {days} days",
                }
            ],
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "get_nutrition_correlations", "error": str(e)}



def get_nutrition_log(
    db: Session,
    athlete_id: UUID,
    days: int = 7,
    entry_type: str = "",
    activity_id: str = "",
) -> Dict[str, Any]:
    """
    Return recent nutrition entries for coaching conversation.
    Supports filtering by entry_type (daily, pre_activity, during_activity, post_activity)
    or by activity_id to see what was eaten around a specific run.
    """
    from models import NutritionEntry
    now = datetime.utcnow()
    try:
        days = max(1, min(int(days), 90))
        start = now - timedelta(days=days)
        units = _preferred_units(db, athlete_id)

        q = (
            db.query(NutritionEntry)
            .filter(
                NutritionEntry.athlete_id == athlete_id,
                NutritionEntry.date >= start.date(),
            )
            .order_by(NutritionEntry.date.desc(), NutritionEntry.created_at.desc())
        )

        if entry_type:
            q = q.filter(NutritionEntry.entry_type == entry_type)
        if activity_id:
            q = q.filter(NutritionEntry.activity_id == activity_id)

        entries = q.limit(50).all()

        if not entries:
            return {
                "ok": True,
                "tool": "get_nutrition_log",
                "generated_at": _iso(now),
                "narrative": f"No nutrition entries found in the last {days} days.",
                "data": {"entries": [], "summary": {}},
            }

        entry_list = []
        daily_totals: Dict[str, Dict[str, float]] = {}

        for e in entries:
            d = e.date.isoformat() if e.date else ""
            row = {
                "date": d,
                "entry_type": e.entry_type or "daily",
                "notes": (e.notes or "")[:120],
                "calories": float(e.calories) if e.calories else None,
                "protein_g": float(e.protein_g) if e.protein_g else None,
                "carbs_g": float(e.carbs_g) if e.carbs_g else None,
                "fat_g": float(e.fat_g) if e.fat_g else None,
                "caffeine_mg": e.caffeine_mg,
                "fluid_ml": e.fluid_ml,
                "macro_source": e.macro_source,
            }
            if e.activity_id:
                act = db.query(Activity).filter(Activity.id == e.activity_id).first()
                if act:
                    dist = act.distance_meters or 0
                    if units == "imperial":
                        row["linked_activity"] = f"{act.name or 'Run'} ({dist / _M_PER_MI:.1f}mi)"
                    else:
                        row["linked_activity"] = f"{act.name or 'Run'} ({dist / 1000:.1f}km)"
            entry_list.append(row)

            if d:
                if d not in daily_totals:
                    daily_totals[d] = {"cal": 0, "p": 0, "c": 0, "f": 0, "caf": 0, "entries": 0}
                dt = daily_totals[d]
                dt["cal"] += float(e.calories or 0)
                dt["p"] += float(e.protein_g or 0)
                dt["c"] += float(e.carbs_g or 0)
                dt["f"] += float(e.fat_g or 0)
                dt["caf"] += float(e.caffeine_mg or 0)
                dt["entries"] += 1

        days_with_data = len(daily_totals)
        if days_with_data > 0:
            avg_cal = sum(d["cal"] for d in daily_totals.values()) / days_with_data
            avg_p = sum(d["p"] for d in daily_totals.values()) / days_with_data
            avg_c = sum(d["c"] for d in daily_totals.values()) / days_with_data
            avg_f = sum(d["f"] for d in daily_totals.values()) / days_with_data
        else:
            avg_cal = avg_p = avg_c = avg_f = 0

        summary = {
            "days_with_entries": days_with_data,
            "total_entries": len(entries),
            "daily_avg_calories": round(avg_cal),
            "daily_avg_protein_g": round(avg_p),
            "daily_avg_carbs_g": round(avg_c),
            "daily_avg_fat_g": round(avg_f),
        }

        pre_run = [e for e in entries if e.entry_type == "pre_activity"]
        during_run = [e for e in entries if e.entry_type == "during_activity"]
        if pre_run:
            summary["pre_run_entries"] = len(pre_run)
            summary["pre_run_avg_carbs_g"] = round(sum(float(e.carbs_g or 0) for e in pre_run) / len(pre_run))
            summary["pre_run_avg_caffeine_mg"] = round(sum(float(e.caffeine_mg or 0) for e in pre_run) / len(pre_run))
        if during_run:
            summary["during_run_entries"] = len(during_run)
            summary["during_run_avg_carbs_g"] = round(sum(float(e.carbs_g or 0) for e in during_run) / len(during_run))

        narrative_parts = [f"Found {len(entries)} nutrition entries over the last {days} days ({days_with_data} days with data)."]
        if avg_cal > 0:
            narrative_parts.append(f"Daily average: {round(avg_cal)} cal, {round(avg_p)}g protein, {round(avg_c)}g carbs, {round(avg_f)}g fat.")
        if pre_run:
            narrative_parts.append(f"Pre-run fueling logged {len(pre_run)} times (avg {summary.get('pre_run_avg_carbs_g', 0)}g carbs, {summary.get('pre_run_avg_caffeine_mg', 0)}mg caffeine).")

        return {
            "ok": True,
            "tool": "get_nutrition_log",
            "generated_at": _iso(now),
            "narrative": " ".join(narrative_parts),
            "data": {"entries": entry_list, "summary": summary},
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "get_nutrition_log", "error": str(e)}



def compare_training_periods(db: Session, athlete_id: UUID, days: int = 28) -> Dict[str, Any]:
    """
    Compare the last N days to the previous N days.

    Designed for:
    - "Am I ramping too fast?"
    - "What changed in the last 4 weeks vs the prior 4 weeks?"
    """
    from services.timezone_utils import get_athlete_timezone_from_db, to_activity_local_date
    _tz = get_athlete_timezone_from_db(db, athlete_id)
    now = datetime.utcnow()
    try:
        days = max(7, min(int(days), 180))
        units = _preferred_units(db, athlete_id)

        end_a = now
        start_a = now - timedelta(days=days)
        end_b = start_a
        start_b = start_a - timedelta(days=days)

        def _fetch(start: datetime, end: datetime) -> List[Activity]:
            return (
                db.query(Activity)
                .filter(
                    Activity.athlete_id == athlete_id,
                    Activity.sport == "run",
                    Activity.start_time >= start,
                    Activity.start_time < end,
                )
                .order_by(Activity.start_time.desc())
                .all()
            )

        a = _fetch(start_a, end_a)
        b = _fetch(start_b, end_b)

        def _summ(acts: List[Activity]) -> Dict[str, Any]:
            total_m = sum(float(x.distance_m or 0) for x in acts)
            total_s = sum(float(x.duration_s or 0) for x in acts)
            run_count = sum(1 for x in acts if x.distance_m)
            avg_hr_vals = [int(x.avg_hr) for x in acts if x.avg_hr is not None]
            return {
                "run_count": run_count,
                "total_distance_km": round(total_m / 1000.0, 2),
                "total_distance_mi": round(total_m / _M_PER_MI, 2),
                "total_duration_hr": round(total_s / 3600.0, 2),
                "avg_hr": round(sum(avg_hr_vals) / len(avg_hr_vals), 1) if avg_hr_vals else None,
            }

        sa = _summ(a)
        sb = _summ(b)

        def _pct(new: float, old: float) -> Optional[float]:
            try:
                if old == 0:
                    return None
                return round(((new - old) / old) * 100.0, 1)
            except Exception:
                return None

        dist_a = sa["total_distance_mi"] if units == "imperial" else sa["total_distance_km"]
        dist_b = sb["total_distance_mi"] if units == "imperial" else sb["total_distance_km"]
        dist_delta_pct = _pct(float(dist_a), float(dist_b))

        # Evidence: cite a couple runs from each period, in preferred units
        def _fmt_run(act: Activity) -> str:
            distance_km = (float(act.distance_m) / 1000.0) if act.distance_m else None
            distance_mi = _mi_from_m(act.distance_m) if act.distance_m else None
            if units == "imperial":
                dist = f"{distance_mi:.1f} mi" if distance_mi is not None else "n/a"
                pace = _pace_str_mi(act.duration_s, act.distance_m) or "n/a"
            else:
                dist = f"{distance_km:.1f} km" if distance_km is not None else "n/a"
                pace = _pace_str(act.duration_s, act.distance_m) or "n/a"
            hr = f"(avg HR {int(act.avg_hr)} bpm)" if act.avg_hr is not None else ""
            name = (act.name or "").strip() or "Run"
            return f"{name} {dist} @ {pace} {hr}".strip()

        evidence: List[Dict[str, Any]] = []
        for act in (a[:2] if a else []):
            evidence.append(
                {
                    "type": "activity",
                    "id": str(act.id),
                    "ref": str(act.id)[:8],
                    "date": to_activity_local_date(act, _tz).isoformat(),
                    "value": _fmt_run(act),
                }
            )
        for act in (b[:2] if b else []):
            evidence.append(
                {
                    "type": "activity",
                    "id": str(act.id),
                    "ref": str(act.id)[:8],
                    "date": to_activity_local_date(act, _tz).isoformat(),
                    "value": _fmt_run(act),
                }
            )

        # --- Narrative ---
        unit_lbl = "mi" if units == "imperial" else "km"
        dist_a_val = sa["total_distance_mi"] if units == "imperial" else sa["total_distance_km"]
        dist_b_val = sb["total_distance_mi"] if units == "imperial" else sb["total_distance_km"]
        cp_parts: List[str] = [
            f"Last {days} days vs prior {days} days: "
            f"{dist_a_val:.0f} {unit_lbl} ({sa['run_count']} runs) vs "
            f"{dist_b_val:.0f} {unit_lbl} ({sb['run_count']} runs)."
        ]
        if dist_delta_pct is not None:
            direction = "increase" if dist_delta_pct > 0 else ("decrease" if dist_delta_pct < 0 else "no change")
            cp_parts.append(f"Volume change: {dist_delta_pct:+.0f}% ({direction}).")
            if abs(dist_delta_pct) > 30:
                cp_parts.append("This is a significant ramp — monitor for injury risk.")
        cp_narrative = " ".join(cp_parts)

        return {
            "ok": True,
            "tool": "compare_training_periods",
            "generated_at": _iso(now),
            "narrative": cp_narrative,
            "data": {
                "preferred_units": units,
                "days": days,
                "period_a": {
                    "start": start_a.date().isoformat(),
                    "end": (end_a.date()).isoformat(),
                    "summary": sa,
                },
                "period_b": {
                    "start": start_b.date().isoformat(),
                    "end": (end_b.date()).isoformat(),
                    "summary": sb,
                },
                "deltas": {
                    "distance_delta_pct": dist_delta_pct,
                    "run_count_delta": sa["run_count"] - sb["run_count"],
                },
            },
            "evidence": evidence,
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "compare_training_periods", "error": str(e)}


# =============================================================================
# PHASE 3: NEW TOOLS - Wellness, Athlete Profile, Training Load History
# =============================================================================



def get_wellness_trends(db: Session, athlete_id: UUID, days: int = 28) -> Dict[str, Any]:
    """
    Phase 3: Wellness trends from DailyCheckin (self-report) + GarminDay (watch-measured).

    Returns sleep, stress, soreness, HRV, and mindset trends.
    Critical for understanding recovery context and readiness.
    Garmin Health API data (hrv_overnight_avg, resting_hr, sleep_total_s, avg_stress)
    is included alongside athlete self-report when available.
    """
    from models import DailyCheckin, GarminDay
    from services.timezone_utils import get_athlete_timezone_from_db, athlete_local_today
    _tz = get_athlete_timezone_from_db(db, athlete_id)

    now = datetime.utcnow()
    days = max(7, min(int(days), 90))
    cutoff = now - timedelta(days=days)

    try:
        checkins = (
            db.query(DailyCheckin)
            .filter(
                DailyCheckin.athlete_id == athlete_id,
                DailyCheckin.date >= cutoff.date(),
            )
            .order_by(DailyCheckin.date.desc())
            .all()
        )

        # Garmin Health API data — watch-measured biometrics for the same window
        garmin_days = (
            db.query(GarminDay)
            .filter(
                GarminDay.athlete_id == athlete_id,
                GarminDay.calendar_date >= cutoff.date(),
            )
            .order_by(GarminDay.calendar_date.desc())
            .all()
        )

        if not checkins and not garmin_days:
            return {
                "ok": True,
                "tool": "get_wellness_trends",
                "generated_at": _iso(now),
                "data": {
                    "window_days": days,
                    "checkin_count": 0,
                    "garmin_days_count": 0,
                    "message": "No wellness check-ins or Garmin Health API data recorded in this period.",
                },
                "evidence": [],
            }

        # Aggregate metrics from self-report check-ins
        sleep_values = [float(c.sleep_h) for c in checkins if c.sleep_h is not None]
        stress_values = [int(c.stress_1_5) for c in checkins if c.stress_1_5 is not None]
        soreness_values = [int(c.soreness_1_5) for c in checkins if c.soreness_1_5 is not None]
        hrv_values = [float(c.hrv_rmssd) for c in checkins if c.hrv_rmssd is not None]
        resting_hr_values = [int(c.resting_hr) for c in checkins if c.resting_hr is not None]
        enjoyment_values = [int(c.enjoyment_1_5) for c in checkins if c.enjoyment_1_5 is not None]
        confidence_values = [int(c.confidence_1_5) for c in checkins if c.confidence_1_5 is not None]
        readiness_values = [int(c.readiness_1_5) for c in checkins if c.readiness_1_5 is not None]

        # Aggregate Garmin Health API biometrics (device-measured, higher fidelity than self-report).
        # Be defensive: unit tests and mixed/malformed rows can contain mock/non-numeric values.
        # avg_stress = -1 means insufficient data from Garmin — exclude from aggregation.
        def _to_num(value: Any) -> Optional[float]:
            if value is None:
                return None
            # Avoid unittest MagicMock placeholders being treated as numeric.
            if value.__class__.__module__.startswith("unittest.mock"):
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        garmin_sleep_h_vals: List[float] = []
        garmin_hrv_vals: List[float] = []
        garmin_rhr_vals: List[float] = []
        garmin_stress_vals: List[float] = []
        garmin_sleep_score_vals: List[float] = []

        for g in garmin_days:
            sleep_total_s = _to_num(getattr(g, "sleep_total_s", None))
            if sleep_total_s is not None:
                garmin_sleep_h_vals.append(sleep_total_s / 3600.0)

            hrv_overnight_avg = _to_num(getattr(g, "hrv_overnight_avg", None))
            if hrv_overnight_avg is not None:
                garmin_hrv_vals.append(hrv_overnight_avg)

            resting_hr = _to_num(getattr(g, "resting_hr", None))
            if resting_hr is not None:
                garmin_rhr_vals.append(resting_hr)

            avg_stress = _to_num(getattr(g, "avg_stress", None))
            if avg_stress is not None and avg_stress >= 0:
                garmin_stress_vals.append(avg_stress)

            sleep_score = _to_num(getattr(g, "sleep_score", None))
            if sleep_score is not None:
                garmin_sleep_score_vals.append(sleep_score)

        def avg(vals: List) -> Optional[float]:
            return round(sum(vals) / len(vals), 2) if vals else None

        def trend(vals: List) -> Optional[str]:
            """Determine if values are trending up, down, or stable."""
            if len(vals) < 3:
                return None
            recent = vals[:len(vals)//2]
            older = vals[len(vals)//2:]
            if not recent or not older:
                return None
            recent_avg = sum(recent) / len(recent)
            older_avg = sum(older) / len(older)
            delta_pct = ((recent_avg - older_avg) / older_avg * 100) if older_avg else 0
            if delta_pct > 10:
                return "improving"
            elif delta_pct < -10:
                return "declining"
            return "stable"

        # Build recent entries for evidence
        evidence: List[Dict[str, Any]] = []
        for c in checkins[:7]:  # Last 7 entries
            parts = []
            if c.sleep_h:
                parts.append(f"sleep:{float(c.sleep_h):.1f}h")
            if c.stress_1_5:
                parts.append(f"stress:{c.stress_1_5}/5")
            if c.soreness_1_5:
                parts.append(f"soreness:{c.soreness_1_5}/5")
            if c.hrv_rmssd:
                parts.append(f"HRV:{float(c.hrv_rmssd):.0f}")
            if c.resting_hr:
                parts.append(f"RHR:{c.resting_hr}")

            _today = athlete_local_today(_tz)
            evidence.append({
                "type": "wellness",
                "date": f"{c.date.isoformat()} {_relative_date(c.date, _today)}",
                "value": " | ".join(parts) if parts else "check-in recorded",
            })

        # --- Narrative ---
        # Lead with most recent self-report entry for temporal anchoring.
        # Guard: if no checkins (only Garmin data), skip this block.
        most_recent_line = ""
        _today = athlete_local_today(_tz)
        if checkins:
            most_recent = checkins[0]
            _mr_rel = _relative_date(most_recent.date, _today)
            recent_parts: List[str] = [f"Most recent self-report ({most_recent.date.isoformat()} {_mr_rel}):"]
            if most_recent.sleep_h is not None:
                recent_parts.append(f"sleep={float(most_recent.sleep_h):.1f}h")
            if most_recent.stress_1_5 is not None:
                recent_parts.append(f"stress={most_recent.stress_1_5}/5")
            if most_recent.soreness_1_5 is not None:
                recent_parts.append(f"soreness={most_recent.soreness_1_5}/5")
            if most_recent.hrv_rmssd is not None:
                recent_parts.append(f"HRV={float(most_recent.hrv_rmssd):.0f}ms")
            if most_recent.resting_hr is not None:
                recent_parts.append(f"RHR={most_recent.resting_hr}bpm")
            most_recent_line = (
                " | ".join(recent_parts)
                if len(recent_parts) > 1
                else f"Most recent self-report ({most_recent.date.isoformat()}): no numeric data."
            )

        wt_parts: List[str] = [
            most_recent_line or f"No self-report check-ins in last {days} days.",
            f"Wellness over {days} days ({len(checkins)} check-ins, {len(garmin_days)} Garmin Health API days):",
        ]
        if sleep_values:
            wt_parts.append(f"Self-report sleep avg {avg(sleep_values):.1f}h (trend: {trend(sleep_values) or 'N/A'}).")
        if garmin_sleep_h_vals:
            wt_parts.append(
                f"Garmin device sleep avg {avg(garmin_sleep_h_vals):.1f}h "
                f"(trend: {trend(garmin_sleep_h_vals) or 'N/A'}, source: Garmin Health API)."
            )
        if garmin_sleep_score_vals:
            wt_parts.append(f"Garmin sleep score avg {avg(garmin_sleep_score_vals):.0f}/100 (source: Garmin Health API).")
        if stress_values:
            wt_parts.append(f"Self-report stress avg {avg(stress_values):.1f}/5 (trend: {trend(stress_values) or 'N/A'}).")
        if garmin_stress_vals:
            wt_parts.append(
                f"Garmin device stress avg {avg(garmin_stress_vals):.0f} "
                f"(trend: {trend(garmin_stress_vals) or 'N/A'}, source: Garmin Health API)."
            )
        if soreness_values:
            wt_parts.append(f"Soreness avg {avg(soreness_values):.1f}/5 (trend: {trend(soreness_values) or 'N/A'}).")
        if hrv_values:
            wt_parts.append(f"HRV (self-report) avg {avg(hrv_values):.0f} ms (trend: {trend(hrv_values) or 'N/A'}).")
        if garmin_hrv_vals:
            wt_parts.append(
                f"Garmin overnight HRV avg {avg(garmin_hrv_vals):.0f} ms "
                f"(trend: {trend(garmin_hrv_vals) or 'N/A'}, source: Garmin Health API). Higher = better recovery."
            )
        if resting_hr_values:
            wt_parts.append(f"Resting HR (self-report) avg {avg(resting_hr_values):.0f} bpm (trend: {trend(resting_hr_values) or 'N/A'}).")
        if garmin_rhr_vals:
            wt_parts.append(
                f"Garmin resting HR avg {avg(garmin_rhr_vals):.0f} bpm "
                f"(trend: {trend(garmin_rhr_vals) or 'N/A'}, source: Garmin Health API)."
            )
        wt_narrative = " ".join(wt_parts) if len(wt_parts) > 1 else "No wellness data available."

        return {
            "ok": True,
            "tool": "get_wellness_trends",
            "generated_at": _iso(now),
            "narrative": wt_narrative,
            "data": {
                "window_days": days,
                "checkin_count": len(checkins),
                "garmin_days_count": len(garmin_days),
                "garmin_health_api": {
                    "sleep_avg_h": avg(garmin_sleep_h_vals),
                    "sleep_score_avg": avg(garmin_sleep_score_vals),
                    "hrv_overnight_avg_ms": avg(garmin_hrv_vals),
                    "resting_hr_avg_bpm": avg(garmin_rhr_vals),
                    "stress_avg": avg(garmin_stress_vals),
                    "data_points": len(garmin_days),
                    "note": "Device-measured data from Garmin Health API",
                },
                "sleep": {
                    "avg_hours": avg(sleep_values),
                    "min_hours": round(min(sleep_values), 1) if sleep_values else None,
                    "max_hours": round(max(sleep_values), 1) if sleep_values else None,
                    "trend": trend(sleep_values),
                    "data_points": len(sleep_values),
                },
                "stress": {
                    "avg": avg(stress_values),
                    "trend": trend(stress_values),
                    "data_points": len(stress_values),
                    "note": "1=low stress, 5=high stress",
                },
                "soreness": {
                    "avg": avg(soreness_values),
                    "trend": trend(soreness_values),
                    "data_points": len(soreness_values),
                    "note": "1=no soreness, 5=very sore",
                },
                "hrv": {
                    "avg_rmssd": avg(hrv_values),
                    "trend": trend(hrv_values),
                    "data_points": len(hrv_values),
                    "note": "Higher HRV generally indicates better recovery",
                },
                "resting_hr": {
                    "avg_bpm": avg(resting_hr_values),
                    "trend": trend(resting_hr_values),
                    "data_points": len(resting_hr_values),
                    "note": "Lower resting HR often indicates better fitness/recovery",
                },
                "mindset": {
                    "avg_enjoyment": avg(enjoyment_values),
                    "avg_confidence": avg(confidence_values),
                    "avg_readiness": avg(readiness_values),
                    "note": "All scales 1-5, higher is better",
                },
            },
            "evidence": evidence,
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "get_wellness_trends", "error": str(e)}



