from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)

from models import Activity, Athlete, TrainingPlan
from core.date_utils import calculate_age
from services.efficiency_analytics import (
    get_efficiency_trends,
    is_quality_activity,
    calculate_efficiency_factor,
)
from services.correlation_engine import (
    aggregate_efficiency_by_effort_zone,
    aggregate_efficiency_trend,
)
from services.rpi_calculator import calculate_race_time_from_rpi, calculate_training_paces as _rpi_training_paces
from services.coach_tools._utils import (
    _iso, _mi_from_m, _pace_str_mi, _pace_str, _relative_date,
    _preferred_units, _fmt_mmss, _M_PER_MI,
)


def get_efficiency_trend(db: Session, athlete_id: UUID, days: int = 30) -> Dict[str, Any]:
    """
    Efficiency over time.
    """
    now = datetime.utcnow()
    days = max(7, min(int(days), 365))

    # NOTE: efficiency_analytics expects the DB-native athlete_id type (UUID).
    # Passing a string can lead to no rows returned depending on dialect/casting.
    result = get_efficiency_trends(
        athlete_id=athlete_id,
        db=db,
        days=days,
        include_stability=False,
        include_load_response=False,
        include_annotations=False,
    )

    # Keep payload bounded
    time_series = result.get("time_series") or []
    trimmed_series = time_series[-50:] if isinstance(time_series, list) else time_series

    # Fallback: if the full efficiency pipeline can't compute EF (e.g., missing splits),
    # derive a basic EF directly from pace_per_mile + avg_hr so the coach can still
    # answer "Am I getting fitter?" with evidence-backed values.
    if not trimmed_series:
        cutoff = now - timedelta(days=days)
        activities = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete_id,
                Activity.sport == "run",
                Activity.start_time >= cutoff,
            )
            .order_by(Activity.start_time.asc())
            .limit(50)
            .all()
        )

        derived = []
        for a in activities:
            if not is_quality_activity(a):
                continue
            pace = a.pace_per_mile
            ef = calculate_efficiency_factor(pace_per_mile=pace, avg_hr=a.avg_hr, max_hr=None)
            if ef is None:
                continue
            derived.append(
                {
                    "date": _iso(a.start_time),
                    "efficiency_factor": ef,
                    "pace_per_mile": round(float(pace), 2) if pace is not None else None,
                    "avg_hr": int(a.avg_hr) if a.avg_hr is not None else None,
                    "activity_id": str(a.id),
                }
            )

        trimmed_series = derived[-50:]
        if derived:
            efficiencies = [p["efficiency_factor"] for p in derived if p.get("efficiency_factor") is not None]
            trend_direction = "insufficient_data"
            trend_magnitude = None
            if len(efficiencies) >= 6:
                early_avg = sum(efficiencies[:3]) / 3
                late_avg = sum(efficiencies[-3:]) / 3
                # EF = speed(m/s) / HR — this is the unambiguous speed-based
                # efficiency factor (NOT pace/HR).  Higher IS better for speed/HR.
                # See Athlete Trust Safety Contract for pace/HR ambiguity distinction.
                if late_avg > early_avg:
                    trend_direction = "improving"
                elif late_avg < early_avg:
                    trend_direction = "declining"
                else:
                    trend_direction = "stable"
                trend_magnitude = round(abs(late_avg - early_avg), 2)

            result = {
                "summary": {
                    "total_activities": len(derived),
                    "date_range": {"start": derived[0]["date"], "end": derived[-1]["date"]} if derived else None,
                    "current_efficiency": efficiencies[-1] if efficiencies else None,
                    "average_efficiency": round(sum(efficiencies) / len(efficiencies), 2) if efficiencies else None,
                    "best_efficiency": round(max(efficiencies), 4) if efficiencies else None,
                    "worst_efficiency": round(min(efficiencies), 4) if efficiencies else None,
                    "trend_direction": trend_direction,
                    "trend_magnitude": trend_magnitude,
                    "note": "EF = speed(m/s) / avg_hr (unambiguous: higher = more speed per heartbeat). Not the same as pace/HR ratio.",
                },
                "trend_analysis": {
                    "method": "fallback_basic",
                    "slope_per_week": None,
                    "p_value": None,
                    "r_squared": None,
                },
                "time_series": trimmed_series,
            }

    units = _preferred_units(db, athlete_id)
    evidence: List[Dict[str, Any]] = []
    if isinstance(trimmed_series, list):
        for p in trimmed_series:
            if isinstance(p, dict) and p.get("activity_id") and p.get("date"):
                # date field in efficiency_analytics is ISO datetime string
                date_str = str(p.get("date"))[:10]
                ef = p.get("efficiency_factor")
                pace_mi = p.get("pace_per_mile")
                pace_km = p.get("pace_per_km")
                avg_hr = p.get("avg_hr")
                ef_part = f"EF {ef}" if ef is not None else "EF n/a"
                extras: List[str] = []
                if units == "imperial":
                    if pace_mi is not None:
                        extras.append(f"pace {pace_mi} min/mi")
                else:
                    if pace_km is not None:
                        extras.append(f"pace {pace_km} min/km")
                if avg_hr is not None:
                    extras.append(f"avg HR {avg_hr} bpm")
                value_str = ef_part + (f" ({', '.join(extras)})" if extras else "")

                evidence.append(
                    {
                        "type": "activity",
                        "id": str(p.get("activity_id")),
                        "date": date_str,
                        "value": value_str,
                        # Back-compat keys
                        "activity_id": str(p.get("activity_id")),
                        "start_time": str(p.get("date")),
                    }
                )

    # --- Narrative ---
    summ = result.get("summary") or {}
    ef_current = summ.get("current_efficiency")
    ef_best = summ.get("best_efficiency")
    ef_avg = summ.get("average_efficiency")
    ef_trend = summ.get("trend_direction", "unknown")
    ef_parts: List[str] = [f"Efficiency trend over {days} days: {ef_trend}."]
    if ef_current is not None:
        ef_parts.append(f"Current EF: {ef_current:.2f}.")
    if ef_best is not None:
        ef_parts.append(f"Best EF: {ef_best:.2f}.")
    if ef_avg is not None:
        ef_parts.append(f"Average EF: {ef_avg:.2f}.")
    ef_parts.append("EF here is speed/HR (not pace/HR). Higher = more speed per heartbeat.")
    ef_narrative = " ".join(ef_parts)

    return {
        "ok": True,
        "tool": "get_efficiency_trend",
        "generated_at": _iso(now),
        "narrative": ef_narrative,
        "data": {
            "window_days": days,
            "summary": result.get("summary"),
            "trend_analysis": result.get("trend_analysis"),
            "time_series": trimmed_series,
        },
        "evidence": evidence,
    }



def get_training_paces(db: Session, athlete_id: UUID) -> Dict[str, Any]:
    """
    Get RPI-based training paces for the athlete.

    Returns target paces for easy, threshold, interval, repetition, and marathon training.
    This is THE authoritative source for training paces - do not derive paces from other data.
    """
    from services.timezone_utils import get_athlete_timezone_from_db, athlete_local_today
    _tz = get_athlete_timezone_from_db(db, athlete_id)
    _today = athlete_local_today(_tz)
    now = datetime.utcnow()
    try:
        from services.rpi_calculator import calculate_training_paces as calc_paces

        athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            return {"ok": False, "tool": "get_training_paces", "error": "Athlete not found"}

        rpi = athlete.rpi
        if not rpi:
            return {
                "ok": False,
                "tool": "get_training_paces",
                "error": "No RPI on file. Athlete needs to complete a time trial or race to calculate training paces.",
            }

        units = athlete.preferred_units or "metric"
        paces = calc_paces(rpi)

        # Format for display
        def format_display(pace_key: str) -> str:
            """Format a pace for human-readable display."""
            if pace_key not in paces:
                return "N/A"
            val = paces[pace_key]
            if isinstance(val, dict):
                # Keys are "mi" and "km", not "display_mi"
                pace = val.get("mi" if units == "imperial" else "km")
                if pace:
                    return f"{pace}/mi" if units == "imperial" else f"{pace}/km"
                return "N/A"
            elif isinstance(val, str):
                return val
            return "N/A"

        # --- Narrative ---
        narrative = (
            f"Training paces based on RPI {rpi:.1f}: "
            f"Easy {format_display('easy')} (CEILING — do not run faster than this on easy days), "
            f"Marathon {format_display('marathon')}, "
            f"Threshold {format_display('threshold')}, Interval {format_display('interval')}, "
            f"Repetition {format_display('repetition')}. "
            f"These are THE authoritative paces from actual race data — do not derive paces from other sources. "
            f"NEVER prescribe heart rate zones or HR-based targets."
        )

        return {
            "ok": True,
            "tool": "get_training_paces",
            "generated_at": _iso(now),
            "narrative": narrative,
            "data": {
                "rpi": rpi,  # Keep for backward compatibility
                "preferred_units": units,
                "paces": {
                    "easy": format_display("easy"),
                    "marathon": format_display("marathon"),
                    "threshold": format_display("threshold"),
                    "interval": format_display("interval"),
                    "repetition": format_display("repetition"),
                },
                "raw_seconds_per_mile": {
                    "easy_low": paces.get("easy_pace_low"),
                    "marathon": paces.get("marathon_pace"),
                    "threshold": paces.get("threshold_pace"),
                    "interval": paces.get("interval_pace"),
                    "repetition": paces.get("repetition_pace"),
                },
            },
            "evidence": [
                {
                    "type": "calculation",
                    "id": f"rpi_paces:{athlete_id}",
                    "date": _today.isoformat(),
                    "value": f"RPI {rpi:.1f} → Threshold {format_display('threshold')}, Easy {format_display('easy')}",
                }
            ],
        }
    except Exception as e:
        logger.error(f"get_training_paces failed for {athlete_id}: {e}")
        return {"ok": False, "tool": "get_training_paces", "error": str(e)}



def get_race_predictions(db: Session, athlete_id: UUID) -> Dict[str, Any]:
    """
    Race equivalent times from RPI — the only verified source.

    Uses the athlete's RPI (derived from actual race performances) to calculate
    equivalent times at standard distances. NO theoretical models, NO fitness
    projections, NO population statistics. The athlete's race data is the truth.

    Also surfaces actual race history so the coach can anchor on real performances.
    """
    now = datetime.utcnow()
    try:
        athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            return {"ok": False, "tool": "get_race_predictions", "error": "Athlete not found"}

        distances: List[tuple[str, float]] = [
            ("5K", 5000.0),
            ("10K", 10000.0),
            ("Half Marathon", 21097.0),
            ("Marathon", 42195.0),
        ]

        def _fmt_time(seconds: int) -> str:
            h = seconds // 3600
            m = (seconds % 3600) // 60
            s = seconds % 60
            return f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m}:{s:02d}"

        rpi = float(athlete.rpi) if athlete.rpi else None
        predictions: Dict[str, Any] = {}
        evidence: List[Dict[str, Any]] = []

        if not rpi:
            return {
                "ok": True,
                "tool": "get_race_predictions",
                "generated_at": _iso(now),
                "narrative": (
                    "No RPI on file — the athlete needs to complete a race or time trial "
                    "before equivalent times can be calculated. Do NOT estimate or guess "
                    "race times without RPI."
                ),
                "data": {"rpi": None, "predictions": {}, "race_history": []},
                "evidence": [],
            }

        for label, dist_m in distances:
            seconds = calculate_race_time_from_rpi(rpi, dist_m)
            if seconds:
                pace_sec = seconds / (dist_m / _M_PER_MI)
                pace_m = int(pace_sec // 60)
                pace_s = int(round(pace_sec % 60))
                predictions[label] = {
                    "equivalent_time": _fmt_time(int(seconds)),
                    "equivalent_pace": f"{pace_m}:{pace_s:02d}/mi",
                    "time_seconds": int(seconds),
                }

        # Surface actual race history so the coach anchors on REALITY
        race_history: List[Dict[str, Any]] = []
        try:
            from models import PersonalBest
            pbs = (
                db.query(PersonalBest)
                .filter(PersonalBest.athlete_id == athlete_id)
                .order_by(PersonalBest.achieved_at.desc())
                .limit(10)
                .all()
            )
            for pb in pbs:
                pb_date = (
                    getattr(pb, "achieved_at", None).date().isoformat()
                    if getattr(pb, "achieved_at", None)
                    else None
                )
                pb_time = _fmt_time(pb.time_seconds) if pb.time_seconds else None
                race_history.append({
                    "distance": pb.distance_category,
                    "time": pb_time,
                    "time_seconds": pb.time_seconds,
                    "date": pb_date,
                    "is_race": getattr(pb, "is_race", False),
                })
                if pb_date:
                    evidence.append({
                        "type": "personal_best",
                        "id": str(getattr(pb, "id", "")),
                        "date": pb_date,
                        "value": f"{pb.distance_category}: {pb_time} ({pb_date})",
                    })
        except Exception:
            pass

        pred_parts: List[str] = []
        for label_key in ["5K", "10K", "Half Marathon", "Marathon"]:
            p = predictions.get(label_key)
            if p:
                pred_parts.append(f"{label_key}: {p['equivalent_time']}")
        pred_summary = ", ".join(pred_parts) if pred_parts else "No predictions available"

        narrative = (
            f"RPI-based equivalent race times (RPI {rpi:.1f}): {pred_summary}. "
            f"These are calculated from the athlete's ACTUAL race performances, not "
            f"theoretical models. The athlete's real race history is included below — "
            f"always anchor predictions on what they have actually run."
        )

        return {
            "ok": True,
            "tool": "get_race_predictions",
            "generated_at": _iso(now),
            "narrative": narrative,
            "data": {
                "rpi": rpi,
                "predictions": predictions,
                "race_history": race_history,
            },
            "evidence": evidence,
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "get_race_predictions", "error": str(e)}



def get_pb_patterns(db: Session, athlete_id: UUID) -> Dict[str, Any]:
    """
    Training patterns that preceded personal bests.

    Returns BOTH summary stats AND per-PB detail so coach can cite specifics.
    """
    from services.training_load import TrainingLoadCalculator
    from models import PersonalBest
    from services.timezone_utils import get_athlete_timezone_from_db, athlete_local_today
    _tz = get_athlete_timezone_from_db(db, athlete_id)

    now = datetime.utcnow()
    try:
        start = now - timedelta(days=365)

        # Get all PBs
        pbs = db.query(PersonalBest).filter(
            PersonalBest.athlete_id == athlete_id,
            PersonalBest.achieved_at >= start,
            PersonalBest.achieved_at <= now
        ).all()

        if not pbs:
            return {
                "ok": True,
                "tool": "get_pb_patterns",
                "generated_at": _iso(now),
                "data": {"pb_count": 0, "pbs": []},
                "evidence": [],
            }

        # Get training load history for TSB lookup
        calc = TrainingLoadCalculator(db)
        try:
            history = calc.get_load_history(athlete_id, days=365)
        except Exception:
            history = []

        # Build date lookup
        load_by_date = {}
        items = history if isinstance(history, list) else history.get("daily_loads", [])
        for item in items:
            d = item.date if hasattr(item, 'date') else item.get('date')
            if hasattr(d, 'date'):
                d = d.date()
            elif isinstance(d, str):
                from datetime import datetime as dt
                d = dt.fromisoformat(d).date()
            load_by_date[d] = item

        # Build per-PB detail
        pb_details = []
        tsb_values = []

        for pb in sorted(pbs, key=lambda x: x.achieved_at or now):
            pb_date = pb.achieved_at.date() if pb.achieved_at else None
            if not pb_date:
                continue

            # Get TSB day before
            check_date = pb_date - timedelta(days=1)
            tsb = None
            ctl = None
            if check_date in load_by_date:
                item = load_by_date[check_date]
                tsb = item.tsb if hasattr(item, 'tsb') else item.get('tsb')
                ctl = item.ctl if hasattr(item, 'ctl') else item.get('ctl')
                if tsb is not None:
                    tsb = round(tsb, 1)
                    tsb_values.append(tsb)
                if ctl is not None:
                    ctl = round(ctl, 1)

            dist_km = round((pb.distance_meters or 0) / 1000, 2)
            time_min = round((pb.time_seconds or 0) / 60, 1)
            pace = round(time_min / dist_km, 2) if dist_km > 0 else None

            pb_details.append({
                "personal_best_id": str(pb.id),
                "activity_id": str(pb.activity_id) if getattr(pb, "activity_id", None) else None,
                "date": pb_date.isoformat(),
                "category": pb.distance_category,
                "distance_km": dist_km,
                "time_min": time_min,
                "pace_min_per_km": pace,
                "is_race": pb.is_race,
                "tsb_day_before": tsb,
                "ctl_day_before": ctl,
            })

        # Compute summary stats
        summary = {
            "pb_count": len(pb_details),
            "tsb_min": min(tsb_values) if tsb_values else None,
            "tsb_max": max(tsb_values) if tsb_values else None,
            "tsb_mean": round(sum(tsb_values) / len(tsb_values), 1) if tsb_values else None,
        }

        # Build evidence with actual citations
        evidence = []
        for pb in pb_details:
            anchor_id = pb.get("activity_id") or pb.get("personal_best_id") or f"pb:{pb['date']}:{pb['category']}"
            activity_part = f" (activity {pb.get('activity_id')})" if pb.get("activity_id") else ""
            evidence.append({
                "type": "personal_best",
                "id": anchor_id,
                "date": pb["date"],
                "value": f"{pb['category']} PR: {pb['distance_km']}km in {pb['time_min']}min{activity_part}, TSB was {pb['tsb_day_before']}",
            })

        # --- Narrative ---
        _today = athlete_local_today(_tz)
        pb_narr_parts: List[str] = [f"{len(pb_details)} personal best(s) in the last year."]
        for pbd in pb_details[:3]:
            cat = pbd.get("category", "?")
            t_min = pbd.get("time_min")
            t_str = f"{t_min:.1f} min" if t_min else "?"
            pb_date_str = pbd.get("date", "?")
            try:
                _pb_narr_rel = _relative_date(date.fromisoformat(pb_date_str), _today)
            except (ValueError, TypeError):
                _pb_narr_rel = ""
            tsb_str = f"TSB was {pbd['tsb_day_before']}" if pbd.get("tsb_day_before") is not None else "TSB unknown"
            pb_narr_parts.append(f"{cat} PR on {pb_date_str} {_pb_narr_rel}: {t_str} ({tsb_str}).")
        if summary.get("tsb_mean") is not None:
            pb_narr_parts.append(f"Average TSB before PRs: {summary['tsb_mean']}.")
        pb_narrative = " ".join(pb_narr_parts)

        return {
            "ok": True,
            "tool": "get_pb_patterns",
            "generated_at": _iso(now),
            "narrative": pb_narrative,
            "data": {
                **summary,
                "pbs": pb_details,
            },
            "evidence": evidence,
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "get_pb_patterns", "error": str(e)}



def get_efficiency_by_zone(
    db: Session,
    athlete_id: UUID,
    effort_zone: str = "threshold",
    days: int = 90,
) -> Dict[str, Any]:
    """
    Efficiency trend for specific effort zones (comparable runs only).
    """
    from services.timezone_utils import get_athlete_timezone_from_db, to_activity_local_date, athlete_local_today
    _tz = get_athlete_timezone_from_db(db, athlete_id)
    _today = athlete_local_today(_tz)
    now = datetime.utcnow()
    try:
        days = max(30, min(int(days), 365))
        start = now - timedelta(days=days)

        athlete_id_str = str(athlete_id)
        zone_data = aggregate_efficiency_by_effort_zone(
            athlete_id_str, start, now, db, effort_zone=effort_zone
        )
        trend_data = aggregate_efficiency_trend(
            athlete_id_str, start, now, db, effort_zone=effort_zone
        )

        efficiencies = [e for _, e in (zone_data or [])]
        current = efficiencies[-1] if efficiencies else None
        best = min(efficiencies) if efficiencies else None
        avg = (sum(efficiencies) / len(efficiencies)) if efficiencies else None

        # Evidence: include a few concrete, citable activities that match the zone filter.
        evidence: List[Dict[str, Any]] = []
        try:
            from services.effort_classification import classify_effort_bulk
            zone_map = {"easy": "easy", "threshold": "moderate", "race": "hard"}
            target_class = zone_map.get(effort_zone)
            if target_class:
                    acts_all = (
                        db.query(Activity)
                        .filter(
                            Activity.athlete_id == athlete_id,
                            Activity.sport == "run",
                            Activity.start_time >= start,
                            Activity.start_time <= now,
                            Activity.distance_m >= 3000,
                            Activity.duration_s.isnot(None),
                            Activity.avg_hr.isnot(None),
                        )
                        .order_by(Activity.start_time.desc())
                        .limit(50)
                        .all()
                    )
                    classifications = classify_effort_bulk(acts_all, str(athlete_id), db)
                    acts = [a for a in acts_all if classifications.get(a.id) == target_class][:5]

                    for a in acts:
                        pace_sec_km = float(a.duration_s) / (float(a.distance_m) / 1000.0)
                        eff = pace_sec_km / float(a.avg_hr) if a.avg_hr else None
                        value_parts: List[str] = []
                        if eff is not None:
                            value_parts.append(f"zone_eff {eff:.6f} (sec/km per bpm)")
                        pace = _pace_str(a.duration_s, a.distance_m)
                        if pace:
                            value_parts.append(f"pace {pace}")
                        if a.avg_hr is not None:
                            value_parts.append(f"avg HR {int(a.avg_hr)} bpm")
                        value = ", ".join(value_parts) if value_parts else f"{effort_zone} zone run"

                        evidence.append(
                            {
                                "type": "activity",
                                "id": str(a.id),
                                "date": to_activity_local_date(a, _tz).isoformat(),
                                "value": value,
                                # Back-compat keys
                                "activity_id": str(a.id),
                                "start_time": _iso(a.start_time),
                            }
                        )
        except Exception:
            # Don't fail the tool if evidence enrichment fails.
            pass

        # --- Narrative ---
        ez_parts: List[str] = [f"{effort_zone.capitalize()} zone efficiency over {days} days: {len(zone_data or [])} data points."]
        if current is not None:
            ez_parts.append(f"Current: {current:.4f}.")
        if best is not None:
            ez_parts.append(f"Best: {best:.4f}.")
        if avg is not None:
            ez_parts.append(f"Average: {avg:.4f}.")
        if trend_data:
            trend_pct = round(trend_data[-1][1], 1)
            ez_parts.append(f"Trend vs baseline: {trend_pct:+.1f}% (efficiency ratio shifted).")
        ez_parts.append("Pace/HR ratio is directionally ambiguous — do not infer better/worse from sign alone.")
        ez_narrative = " ".join(ez_parts)

        return {
            "ok": True,
            "tool": "get_efficiency_by_zone",
            "generated_at": _iso(now),
            "narrative": ez_narrative,
            "data": {
                "effort_zone": effort_zone,
                "window_days": days,
                "data_points": len(zone_data or []),
                "current_efficiency": round(current, 6) if current is not None else None,
                "best_efficiency": round(best, 6) if best is not None else None,
                "average_efficiency": round(avg, 6) if avg is not None else None,
                "recent_trend_pct": round(trend_data[-1][1], 2) if trend_data else None,
                "note": "Efficiency is Pace(sec/km)/HR(bpm) — directionally ambiguous (rises when HR drops, falls when pace improves). Do not infer direction from sign alone. See OutputMetricMeta.",
            },
            "evidence": evidence
            + [
                {
                    "type": "derived",
                    "id": f"efficiency_zone:{str(athlete_id)}:{effort_zone}",
                    "date": _today.isoformat(),
                    "value": (
                        f"{effort_zone} zone: {len(zone_data or [])} runs, current {current:.6f}"
                        if current is not None
                        else f"{effort_zone} zone: no data"
                    ),
                }
            ],
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "get_efficiency_by_zone", "error": str(e)}



