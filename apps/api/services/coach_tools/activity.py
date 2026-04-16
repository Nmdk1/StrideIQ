from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)

from models import (
    Activity,
    Athlete,
    ActivitySplit,
    ActivityStream,
    TrainingPlan,
    PlannedWorkout,
)
from core.date_utils import calculate_age
from services.rpi_calculator import calculate_training_paces
from services.coach_tools._utils import (
    _iso, _mi_from_m, _pace_str_mi, _pace_str, _relative_date,
    _preferred_units, _fmt_mmss, _pace_seconds_from_text,
    _format_run_context, _guardrails_from_pain, _M_PER_MI,
)


def get_recent_runs(db: Session, athlete_id: UUID, days: int = 7) -> Dict[str, Any]:
    """
    Last N days of run activities.
    """
    from services.timezone_utils import get_athlete_timezone_from_db, to_activity_local_date, athlete_local_today
    now = datetime.utcnow()
    # Allow ~2 years so injury-return + baseline can be compared.
    days = max(1, min(int(days), 730))
    cutoff = now - timedelta(days=days)
    units = _preferred_units(db, athlete_id)
    _ath_tz = get_athlete_timezone_from_db(db, athlete_id)
    _ref_date = athlete_local_today(_ath_tz)

    runs = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.sport == "run",
            Activity.start_time >= cutoff,
        )
        .order_by(Activity.start_time.desc())
        .limit(50)
        .all()
    )

    run_rows: List[Dict[str, Any]] = []
    evidence: List[Dict[str, Any]] = []

    for a in runs:
        distance_km = (float(a.distance_m) / 1000.0) if a.distance_m is not None else None
        distance_mi = _mi_from_m(a.distance_m) if a.distance_m is not None else None
        pace = _pace_str(a.duration_s, a.distance_m)
        pace_mi = _pace_str_mi(a.duration_s, a.distance_m)
        date_str = to_activity_local_date(a, _ath_tz).isoformat()

        # Phase 3: Add elevation, weather, max_hr for richer context
        elevation_gain_m = float(a.total_elevation_gain) if a.total_elevation_gain is not None else None
        elevation_gain_ft = round(elevation_gain_m * 3.28084, 0) if elevation_gain_m is not None else None

        run_rows.append(
            {
                "activity_id": str(a.id),
                "start_time": _iso(a.start_time),
                "name": a.name,
                "distance_m": int(a.distance_m) if a.distance_m is not None else None,
                "distance_mi": round(distance_mi, 2) if distance_mi is not None else None,
                "distance_km": round(distance_km, 2) if distance_km is not None else None,
                "duration_s": int(a.duration_s) if a.duration_s is not None else None,
                "avg_hr": int(a.avg_hr) if a.avg_hr is not None else None,
                "max_hr": int(a.max_hr) if a.max_hr is not None else None,
                "pace_per_km": _pace_str(a.duration_s, a.distance_m),
                "pace_per_mile": pace_mi,
                "workout_type": a.workout_type,
                "intensity_score": float(a.intensity_score) if a.intensity_score is not None else None,
                "elevation_gain_m": round(elevation_gain_m, 1) if elevation_gain_m is not None else None,
                "elevation_gain_ft": int(elevation_gain_ft) if elevation_gain_ft is not None else None,
                "temperature_f": round(float(a.temperature_f), 1) if a.temperature_f is not None else None,
                "humidity_pct": round(float(a.humidity_pct), 0) if a.humidity_pct is not None else None,
                "weather_condition": a.weather_condition,
                "shape_sentence": a.shape_sentence,
                "is_race": bool(getattr(a, "user_verified_race", False) or getattr(a, "is_race_candidate", False)),
            }
        )

        parts: List[str] = []
        run_name = (a.name or "").strip() or "Run"
        parts.append(run_name)
        if units == "imperial":
            if distance_mi is not None:
                parts.append(f"{distance_mi:.1f} mi")
            if pace_mi:
                parts.append(f"@ {pace_mi}")
        else:
            if distance_km is not None:
                parts.append(f"{distance_km:.1f} km")
            if pace:
                parts.append(f"@ {pace}")
        if a.avg_hr is not None:
            parts.append(f"(avg HR {int(a.avg_hr)} bpm)")
        if a.max_hr is not None:
            parts.append(f"(max HR {int(a.max_hr)} bpm)")
        if a.workout_type:
            parts.append(f"[{a.workout_type}]")
        # Phase 3: Add elevation and weather to evidence
        if elevation_gain_ft is not None and elevation_gain_ft > 50:
            parts.append(f"+{int(elevation_gain_ft)}ft")
        if a.temperature_f is not None:
            parts.append(f"{int(a.temperature_f)}°F")
        if a.weather_condition:
            parts.append(f"({a.weather_condition})")
        value_str = " ".join(parts) if parts else "run"

        _run_rel = _relative_date(to_activity_local_date(a, _ath_tz), _ref_date) if a.start_time else ""
        evidence.append(
            {
                "type": "activity",
                "id": str(a.id),
                "ref": str(a.id)[:8],
                "date": f"{date_str} {_run_rel}",
                "value": value_str,
                "activity_id": str(a.id),
                "start_time": _iso(a.start_time),
            }
        )

    total_distance_m = sum((a.distance_m or 0) for a in runs)
    total_duration_s = sum((a.duration_s or 0) for a in runs)

    # --- Narrative ---
    total_mi = round(total_distance_m / _M_PER_MI, 1)
    total_km = round(total_distance_m / 1000.0, 1)
    if units == "imperial":
        dist_str = f"{total_mi} miles"
    else:
        dist_str = f"{total_km} km"
    dur_hrs = round(total_duration_s / 3600.0, 1)

    rr_parts: List[str] = [
        f"{len(runs)} runs in the last {days} days totaling {dist_str} ({dur_hrs} hours)."
    ]
    if run_rows:
        latest = run_rows[0]
        l_name = latest.get("name") or "Run"
        l_date = latest.get("start_time", "")[:10]
        l_dist = latest.get("distance_mi") if units == "imperial" else latest.get("distance_km")
        l_unit = "mi" if units == "imperial" else "km"
        l_pace = latest.get("pace_per_mile") if units == "imperial" else latest.get("pace_per_km")
        try:
            _relative = " " + _relative_date(date.fromisoformat(l_date))
        except (ValueError, TypeError):
            _relative = ""
        rr_parts.append(
            f"Most recent: {l_name} on {l_date}{_relative}, "
            f"{l_dist:.1f} {l_unit} @ {l_pace or 'N/A'}."
        )
    narrative = " ".join(rr_parts)

    return {
        "ok": True,
        "tool": "get_recent_runs",
        "generated_at": _iso(now),
        "narrative": narrative,
        "data": {
            "window_days": days,
            "preferred_units": units,
            "run_count": len(runs),
            "total_distance_km": round(total_distance_m / 1000.0, 2),
            "total_distance_mi": round(total_distance_m / _M_PER_MI, 2),
            "total_duration_min": round(total_duration_s / 60.0, 1),
            "runs": run_rows,
        },
        "evidence": evidence,
    }



def get_calendar_day_context(db: Session, athlete_id: UUID, day: str) -> Dict[str, Any]:
    """
    Calendar day context (plan + actual).

    Use this when the athlete asks about a specific day from the calendar.
    Returns planned workout + actual activities for that date with IDs for citations.
    """
    now = datetime.utcnow()
    try:
        day_date = date.fromisoformat(day)
    except Exception:
        return {
            "ok": False,
            "tool": "get_calendar_day_context",
            "generated_at": _iso(now),
            "error": "Invalid date format. Use YYYY-MM-DD.",
            "data": {},
            "evidence": [],
        }

    plan = (
        db.query(TrainingPlan)
        .filter(TrainingPlan.athlete_id == athlete_id, TrainingPlan.status == "active")
        .first()
    )
    units = _preferred_units(db, athlete_id)

    planned = None
    if plan:
        planned = (
            db.query(PlannedWorkout)
            .filter(PlannedWorkout.plan_id == plan.id, PlannedWorkout.scheduled_date == day_date)
            .first()
        )

    acts = (
        db.query(Activity)
        .filter(Activity.athlete_id == athlete_id, Activity.sport == "run")
        .filter(func.date(Activity.start_time) == day_date)
        .order_by(Activity.start_time.asc())
        .all()
    )

    weekday_name = day_date.strftime("%A")
    weekday_index = day_date.weekday()

    marathon_pace_per_mile: Optional[str] = None
    marathon_pace_per_km: Optional[str] = None
    marathon_pace_sec_per_mile: Optional[int] = None
    try:
        athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if athlete and athlete.rpi:
            paces = calculate_training_paces(float(athlete.rpi))
            marathon_block = paces.get("marathon")
            if isinstance(marathon_block, dict):
                mi_val = marathon_block.get("mi")
                km_val = marathon_block.get("km")
                if isinstance(mi_val, str) and mi_val:
                    marathon_pace_per_mile = f"{mi_val}/mi"
                    marathon_pace_sec_per_mile = _pace_seconds_from_text(mi_val)
                if isinstance(km_val, str) and km_val:
                    marathon_pace_per_km = f"{km_val}/km"
            if marathon_pace_sec_per_mile is None:
                raw_mi = paces.get("marathon_pace")
                if isinstance(raw_mi, (int, float)) and raw_mi > 0:
                    marathon_pace_sec_per_mile = int(round(float(raw_mi)))
                    marathon_pace_per_mile = f"{_fmt_mmss(marathon_pace_sec_per_mile)}/mi"
    except Exception as _paces_exc:
        # Keep day-context available even if pace references are unavailable,
        # but log so silent NameError / import regressions don't ship.
        logger.warning(
            "calendar_day_context: marathon pace resolution failed: %s",
            _paces_exc,
        )

    planned_data: Optional[Dict[str, Any]] = None
    evidence: List[Dict[str, Any]] = []
    if planned:
        planned_mi = _mi_from_m(planned.target_distance_km * 1000.0) if planned.target_distance_km is not None else None
        planned_data = {
            "planned_workout_id": str(planned.id),
            "plan_id": str(planned.plan_id),
            "date": planned.scheduled_date.isoformat() if planned.scheduled_date else None,
            "week_number": planned.week_number,
            "phase": planned.phase,
            "workout_type": planned.workout_type,
            "workout_subtype": planned.workout_subtype,
            "title": planned.title,
            "coach_notes": planned.coach_notes,
            "description": planned.description,
            "target_distance_km": float(planned.target_distance_km) if planned.target_distance_km is not None else None,
            "target_distance_mi": round(planned_mi, 2) if planned_mi is not None else None,
            "target_duration_minutes": planned.target_duration_minutes,
            "completed": bool(planned.completed),
            "skipped": bool(planned.skipped),
        }
        evidence.append(
            {
                "type": "planned_workout",
                "id": str(planned.id),
                "date": day_date.isoformat(),
                "value": f"{planned.title} [{planned.workout_type}]",
            }
        )

    activity_rows: List[Dict[str, Any]] = []
    for a in acts:
        distance_km = (float(a.distance_m) / 1000.0) if a.distance_m is not None else None
        distance_mi = _mi_from_m(a.distance_m) if a.distance_m is not None else None
        pace_mi_str = _pace_str_mi(a.duration_s, a.distance_m)
        pace_km_str = _pace_str(a.duration_s, a.distance_m)
        pace_sec_per_mile = _pace_seconds_from_text(pace_mi_str)
        pace_vs_marathon_label: Optional[str] = None
        pace_vs_marathon_seconds_per_mile: Optional[int] = None
        pace_vs_marathon_direction: Optional[str] = None
        if (
            pace_sec_per_mile is not None
            and marathon_pace_sec_per_mile is not None
            and marathon_pace_sec_per_mile > 0
        ):
            delta = int(round(pace_sec_per_mile - marathon_pace_sec_per_mile))
            pace_vs_marathon_seconds_per_mile = delta
            if delta < 0:
                pace_vs_marathon_direction = "faster"
                pace_vs_marathon_label = f"faster by {_fmt_mmss(delta)}/mi"
            elif delta > 0:
                pace_vs_marathon_direction = "slower"
                pace_vs_marathon_label = f"slower by {_fmt_mmss(delta)}/mi"
            else:
                pace_vs_marathon_direction = "equal"
                pace_vs_marathon_label = "on marathon pace"
        activity_rows.append(
            {
                "activity_id": str(a.id),
                "start_time": _iso(a.start_time),
                "name": a.name,
                "distance_m": int(a.distance_m) if a.distance_m is not None else None,
                "distance_mi": round(distance_mi, 2) if distance_mi is not None else None,
                "distance_km": round(distance_km, 2) if distance_km is not None else None,
                "duration_s": int(a.duration_s) if a.duration_s is not None else None,
                "avg_hr": int(a.avg_hr) if a.avg_hr is not None else None,
                "pace_per_km": pace_km_str,
                "pace_per_mile": pace_mi_str,
                "pace_vs_marathon_label": pace_vs_marathon_label,
                "pace_vs_marathon_seconds_per_mile": pace_vs_marathon_seconds_per_mile,
                "pace_vs_marathon_direction": pace_vs_marathon_direction,
                "workout_type": a.workout_type,
                "intensity_score": float(a.intensity_score) if a.intensity_score is not None else None,
            }
        )

        parts: List[str] = []
        run_name = (a.name or "").strip() or "Run"
        parts.append(run_name)
        if units == "imperial":
            if distance_mi is not None:
                parts.append(f"{distance_mi:.1f} mi")
            pace_mi = _pace_str_mi(a.duration_s, a.distance_m)
            if pace_mi:
                parts.append(f"@ {pace_mi}")
        else:
            if distance_km is not None:
                parts.append(f"{distance_km:.1f} km")
            pace = _pace_str(a.duration_s, a.distance_m)
            if pace:
                parts.append(f"@ {pace}")
        if a.avg_hr is not None:
            parts.append(f"(avg HR {int(a.avg_hr)} bpm)")
        if a.workout_type:
            parts.append(f"[{a.workout_type}]")
        evidence.append(
            {
                "type": "activity",
                "id": str(a.id),
                "ref": str(a.id)[:8],
                "date": day_date.isoformat(),
                "value": " ".join(parts) if parts else "run",
            }
        )

    # --- Narrative ---
    _cd_rel = _relative_date(day_date)
    cd_parts: List[str] = [f"Calendar day {day_date.isoformat()} ({weekday_name}) {_cd_rel}:"]
    if planned_data:
        status = "completed" if planned_data.get("completed") else ("skipped" if planned_data.get("skipped") else "not yet completed")
        cd_parts.append(
            f"Planned: {planned_data.get('title', 'workout')} ({planned_data.get('workout_type', 'N/A')}) — {status}."
        )
    else:
        cd_parts.append("No workout was planned for this day.")
    if activity_rows:
        for ar in activity_rows:
            d_val = ar.get("distance_mi") if units == "imperial" else ar.get("distance_km")
            d_unit = "mi" if units == "imperial" else "km"
            p_val = ar.get("pace_per_mile") if units == "imperial" else ar.get("pace_per_km")
            cd_parts.append(
                f"Actual: {ar.get('name', 'Run')} — {d_val:.1f} {d_unit} @ {p_val or 'N/A'}"
                + (f" (avg HR {ar['avg_hr']} bpm)" if ar.get("avg_hr") else "")
                + "."
            )
    else:
        cd_parts.append("No runs recorded on this day.")
    cd_narrative = " ".join(cd_parts)

    return {
        "ok": True,
        "tool": "get_calendar_day_context",
        "generated_at": _iso(now),
        "narrative": cd_narrative,
        "data": {
            "date": day_date.isoformat(),
            "weekday": weekday_name,
            "weekday_index": weekday_index,
            "preferred_units": units,
            "active_plan_id": str(plan.id) if plan else None,
            "marathon_pace_per_mile": marathon_pace_per_mile,
            "marathon_pace_per_km": marathon_pace_per_km,
            "planned_workout": planned_data,
            "activities": activity_rows,
        },
        "evidence": evidence,
    }



def get_best_runs(
    db: Session,
    athlete_id: UUID,
    days: int = 365,
    metric: str = "efficiency",
    limit: int = 5,
    effort_zone: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return the "best" runs by an explicit, auditable definition.

    Metrics:
      - efficiency: highest speed/HR — unambiguous (higher = more speed per heartbeat)
      - pace: fastest pace (min/mi or min/km depending on units)
      - distance: longest distance
      - intensity_score: highest intensity_score

    Optional effort_zone filters by athlete max_hr:
      - easy / threshold / race (same mapping used elsewhere)
    """
    from services.timezone_utils import get_athlete_timezone_from_db, to_activity_local_date
    _tz = get_athlete_timezone_from_db(db, athlete_id)
    now = datetime.utcnow()
    try:
        days = max(7, min(int(days), 730))
        limit = max(1, min(int(limit), 10))
        units = _preferred_units(db, athlete_id)

        cutoff = now - timedelta(days=days)
        q = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete_id,
                Activity.sport == "run",
                Activity.start_time >= cutoff,
                Activity.distance_m.isnot(None),
                Activity.duration_s.isnot(None),
            )
        )

        _effort_zone_filter = None
        if effort_zone:
            ez = effort_zone.lower().strip()
            zone_map = {"easy": "easy", "threshold": "moderate", "race": "hard"}
            _effort_zone_filter = zone_map.get(ez)

        acts_raw = q.order_by(Activity.start_time.desc()).limit(200).all()  # bounded

        if _effort_zone_filter:
            from services.effort_classification import classify_effort_bulk
            classifications = classify_effort_bulk(acts_raw, str(athlete_id), db)
            acts = [a for a in acts_raw if classifications.get(a.id) == _effort_zone_filter]
        else:
            acts = acts_raw

        rows: List[Dict[str, Any]] = []
        for a in acts:
            distance_m = float(a.distance_m or 0)
            duration_s = float(a.duration_s or 0)
            if distance_m <= 0 or duration_s <= 0:
                continue

            duration_s / (distance_m / 1000.0)
            pace_mi = _pace_str_mi(int(a.duration_s) if a.duration_s else None, int(a.distance_m) if a.distance_m else None)
            pace_km = _pace_str(int(a.duration_s) if a.duration_s else None, int(a.distance_m) if a.distance_m else None)
            speed_mps = (distance_m / duration_s) if duration_s > 0 else None
            eff = (speed_mps / float(a.avg_hr)) if (speed_mps and a.avg_hr) else None

            _a_local_date = to_activity_local_date(a, _tz)
            _br_rel = _relative_date(_a_local_date)
            rows.append(
                {
                    "activity_id": str(a.id),
                    "date": f"{_a_local_date.isoformat()} {_br_rel}",
                    "name": (a.name or "").strip() or "Run",
                    "distance_km": round(distance_m / 1000.0, 2),
                    "distance_mi": round(distance_m / _M_PER_MI, 2),
                    "duration_s": int(duration_s),
                    "avg_hr": int(a.avg_hr) if a.avg_hr is not None else None,
                    "pace_per_km": pace_km,
                    "pace_per_mile": pace_mi,
                    "intensity_score": float(a.intensity_score) if a.intensity_score is not None else None,
                    "efficiency_speed_per_hr": round(eff, 6) if eff is not None else None,
                }
            )

        def _score(r: Dict[str, Any]) -> float:
            if metric == "efficiency":
                v = r.get("efficiency_speed_per_hr")
                return -float(v) if v is not None else 1e9  # speed/HR: higher is better (unambiguous)
            if metric == "pace":
                # lower seconds per km is better; derive from formatted pace if possible
                # fall back to distance/duration
                dur = r.get("duration_s") or 0
                dist_km = r.get("distance_km") or 0
                if dur and dist_km:
                    return float(dur) / float(dist_km)
                return 1e9
            if metric == "distance":
                return -float(r.get("distance_km") or 0)  # negative so sort ascending works
            if metric == "intensity_score":
                return -float(r.get("intensity_score") or 0)
            return 0.0

        # Sort: for some metrics we inverted the sign so "best" is still smallest _score.
        rows_sorted = sorted(rows, key=_score)
        best = rows_sorted[:limit]

        evidence: List[Dict[str, Any]] = []
        for r in best:
            dist = r["distance_mi"] if units == "imperial" else r["distance_km"]
            unit = "mi" if units == "imperial" else "km"
            pace = r["pace_per_mile"] if units == "imperial" else r["pace_per_km"]
            parts = [r["name"], f"{dist:.1f} {unit}", f"@ {pace}"]
            if r.get("avg_hr") is not None:
                parts.append(f"(avg HR {r['avg_hr']} bpm)")
            if metric == "efficiency" and r.get("efficiency_speed_per_hr") is not None:
                parts.append(f"[eff {r['efficiency_speed_per_hr']:.6f}]")
            evidence.append(
                {
                    "type": "activity",
                    "id": r["activity_id"],
                    "ref": r["activity_id"][:8],
                    "date": r["date"],
                    "value": " ".join(parts),
                }
            )

        # --- Narrative ---
        br_parts: List[str] = [f"Top {len(best)} runs by {metric} in the last {days} days:"]
        for i, r in enumerate(best, 1):
            d = r["distance_mi"] if units == "imperial" else r["distance_km"]
            u = "mi" if units == "imperial" else "km"
            p = r["pace_per_mile"] if units == "imperial" else r["pace_per_km"]
            hr_str = f", avg HR {r['avg_hr']}" if r.get("avg_hr") else ""
            br_parts.append(f"{i}. {r['name']} ({r['date']}): {d:.1f} {u} @ {p}{hr_str}.")
        br_narrative = " ".join(br_parts) if best else f"No qualifying runs found by {metric} in the last {days} days."

        return {
            "ok": True,
            "tool": "get_best_runs",
            "generated_at": _iso(now),
            "narrative": br_narrative,
            "data": {
                "preferred_units": units,
                "window_days": days,
                "metric": metric,
                "effort_zone": effort_zone,
                "results": best,
            },
            "evidence": evidence,
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "get_best_runs", "error": str(e)}



def _to_float_list(values: Any) -> List[float]:
    out: List[float] = []
    if not isinstance(values, list):
        return out
    for value in values:
        try:
            out.append(float(value))
        except Exception:
            continue
    return out



def _interpolate_time_at_distance(samples: List[Tuple[float, float]], target_distance: float) -> Optional[float]:
    if not samples:
        return None
    if target_distance <= samples[0][0]:
        return samples[0][1]

    for idx in range(1, len(samples)):
        prev_dist, prev_time = samples[idx - 1]
        curr_dist, curr_time = samples[idx]
        if curr_dist < target_distance:
            continue
        if curr_dist == prev_dist:
            return curr_time
        ratio = (target_distance - prev_dist) / (curr_dist - prev_dist)
        return prev_time + ratio * (curr_time - prev_time)
    return None



def _format_duration_hms(total_seconds: float) -> str:
    total = max(0, int(round(total_seconds)))
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"



def get_mile_splits(
    db: Session,
    athlete_id: UUID,
    activity_id: str,
    unit: str = "mi",
) -> Dict[str, Any]:
    """Return distance-based split data from stream data and/or device laps."""
    from services.timezone_utils import get_athlete_timezone_from_db, to_activity_local_date
    _tz = get_athlete_timezone_from_db(db, athlete_id)
    now = datetime.utcnow()
    tool_name = "get_mile_splits"
    normalized_unit = (unit or "mi").strip().lower()
    if normalized_unit not in ("mi", "km"):
        return {
            "ok": False,
            "tool": tool_name,
            "generated_at": _iso(now),
            "error": "Invalid unit. Use 'mi' or 'km'.",
            "data": {},
            "evidence": [],
        }

    try:
        activity_uuid = UUID(str(activity_id))
    except Exception:
        return {
            "ok": False,
            "tool": tool_name,
            "generated_at": _iso(now),
            "error": "Invalid activity_id format.",
            "data": {},
            "evidence": [],
        }

    activity = db.query(Activity).filter(Activity.id == activity_uuid).first()
    if activity is None:
        return {
            "ok": False,
            "tool": tool_name,
            "generated_at": _iso(now),
            "error": "Activity not found.",
            "data": {},
            "evidence": [],
        }
    if activity.athlete_id != athlete_id:
        return {
            "ok": False,
            "tool": tool_name,
            "generated_at": _iso(now),
            "error": "Access denied: activity does not belong to this athlete.",
            "data": {},
            "evidence": [],
        }

    laps = (
        db.query(ActivitySplit)
        .filter(ActivitySplit.activity_id == activity_uuid)
        .order_by(ActivitySplit.split_number.asc())
        .all()
    )
    unit_distance_m = _M_PER_MI if normalized_unit == "mi" else 1000.0
    unit_label = "mile" if normalized_unit == "mi" else "km"

    device_laps: List[Dict[str, Any]] = []
    for lap in laps:
        lap_distance_m = float(lap.distance) if lap.distance is not None else None
        lap_distance_units = (lap_distance_m / unit_distance_m) if lap_distance_m else None
        lap_elapsed = int(lap.elapsed_time) if lap.elapsed_time is not None else None
        pace_seconds_per_unit = None
        if lap_elapsed and lap_distance_units and lap_distance_units > 0:
            pace_seconds_per_unit = lap_elapsed / lap_distance_units
        device_laps.append(
            {
                "split_number": int(lap.split_number),
                "distance_m": round(lap_distance_m, 2) if lap_distance_m is not None else None,
                "distance_units": round(lap_distance_units, 3) if lap_distance_units is not None else None,
                "elapsed_seconds": lap_elapsed,
                "elapsed_time": _format_duration_hms(lap_elapsed) if lap_elapsed is not None else None,
                "pace_per_unit": f"{_fmt_mmss(pace_seconds_per_unit)}/{normalized_unit}" if pace_seconds_per_unit else None,
                "average_heartrate": int(lap.average_heartrate) if lap.average_heartrate is not None else None,
                "moving_time_seconds": int(lap.moving_time) if lap.moving_time is not None else None,
            }
        )

    stream_row = (
        db.query(ActivityStream)
        .filter(ActivityStream.activity_id == activity_uuid)
        .first()
    )

    stream_splits: List[Dict[str, Any]] = []
    split_meta: Dict[str, Any] = {}
    stream_warning: Optional[str] = None

    if stream_row and isinstance(stream_row.stream_data, dict):
        distances = _to_float_list(stream_row.stream_data.get("distance"))
        times = _to_float_list(stream_row.stream_data.get("time"))
        heartrate = _to_float_list(stream_row.stream_data.get("heartrate"))
        if len(distances) >= 2 and len(times) >= 2:
            pair_count = min(len(distances), len(times))
            samples: List[Tuple[float, float]] = []
            samples_with_hr: List[Tuple[float, float, Optional[float]]] = []
            dropped_points = 0
            for idx in range(pair_count):
                d_val = distances[idx]
                t_val = times[idx]
                hr_val = heartrate[idx] if idx < len(heartrate) else None
                if d_val < 0 or t_val < 0:
                    dropped_points += 1
                    continue
                if samples:
                    prev_d, prev_t = samples[-1]
                    if d_val < prev_d or t_val < prev_t:
                        dropped_points += 1
                        continue
                samples.append((d_val, t_val))
                samples_with_hr.append((d_val, t_val, hr_val))

            if len(samples) >= 2 and samples[-1][0] > 0:
                total_distance_m = samples[-1][0]
                total_time_s = samples[-1][1]
                target = unit_distance_m
                boundaries = [0.0]
                while target <= total_distance_m:
                    boundaries.append(target)
                    target += unit_distance_m
                if boundaries[-1] < total_distance_m:
                    boundaries.append(total_distance_m)

                boundary_times: List[float] = []
                for boundary in boundaries:
                    boundary_time = _interpolate_time_at_distance(samples, boundary)
                    if boundary_time is None:
                        boundary_times = []
                        break
                    boundary_times.append(boundary_time)

                if boundary_times:
                    for idx in range(1, len(boundaries)):
                        start_d = boundaries[idx - 1]
                        end_d = boundaries[idx]
                        start_t = boundary_times[idx - 1]
                        end_t = boundary_times[idx]
                        elapsed = max(0.0, end_t - start_t)
                        split_distance_m = max(0.0, end_d - start_d)
                        split_distance_units = split_distance_m / unit_distance_m if unit_distance_m > 0 else None
                        pace_seconds_per_unit = (
                            elapsed / split_distance_units
                            if split_distance_units and split_distance_units > 0
                            else None
                        )
                        avg_hr = None
                        if samples_with_hr:
                            hr_window = [
                                row[2]
                                for row in samples_with_hr
                                if row[2] is not None and start_d <= row[0] <= end_d
                            ]
                            if hr_window:
                                avg_hr = round(sum(hr_window) / len(hr_window))

                        stream_splits.append(
                            {
                                "split_number": idx,
                                "is_partial": split_distance_m < (unit_distance_m - 1e-6),
                                "distance_m": round(split_distance_m, 2),
                                "distance_units": round(split_distance_units, 3) if split_distance_units is not None else None,
                                "elapsed_seconds": round(elapsed),
                                "elapsed_time": _format_duration_hms(elapsed),
                                "pace_per_unit": f"{_fmt_mmss(pace_seconds_per_unit)}/{normalized_unit}" if pace_seconds_per_unit else None,
                                "average_heartrate": avg_hr,
                            }
                        )

                    half_time = _interpolate_time_at_distance(samples, total_distance_m / 2.0)
                    split_meta = {
                        "total_distance_m": round(total_distance_m, 2),
                        "total_distance_units": round(total_distance_m / unit_distance_m, 3),
                        "total_elapsed_seconds": round(total_time_s),
                        "first_half_seconds": round(half_time) if half_time is not None else None,
                        "second_half_seconds": round(total_time_s - half_time) if half_time is not None else None,
                        "first_half_time": _format_duration_hms(half_time) if half_time is not None else None,
                        "second_half_time": _format_duration_hms(total_time_s - half_time) if half_time is not None else None,
                    }
                else:
                    stream_warning = "Could not interpolate split boundaries from stream data."
            else:
                stream_warning = "Stream data is non-monotonic or missing cumulative distance."
        else:
            stream_warning = "Stream data missing required 'distance' and 'time' channels."

    if stream_splits:
        narrative = (
            f"Computed {len(stream_splits)} {unit_label} splits from stream data "
            f"for {(activity.name or 'run').strip() or 'run'}."
        )
        if split_meta.get("first_half_time") and split_meta.get("second_half_time"):
            narrative += (
                f" First half: {split_meta['first_half_time']}, "
                f"second half: {split_meta['second_half_time']}."
            )
        return {
            "ok": True,
            "tool": tool_name,
            "generated_at": _iso(now),
            "narrative": narrative,
            "data": {
                "activity_id": str(activity_uuid),
                "activity_name": activity.name,
                "unit": normalized_unit,
                "source": "stream",
                "splits": stream_splits,
                "summary": split_meta,
                "device_laps": device_laps,
            },
            "evidence": [
                {
                    "type": "activity",
                    "id": str(activity_uuid),
                    "date": to_activity_local_date(activity, _tz).isoformat() if activity.start_time else _iso(now)[:10],
                    "value": f"{(activity.name or 'Run').strip() or 'Run'} split analysis from stream data",
                }
            ],
        }

    if device_laps:
        return {
            "ok": True,
            "tool": tool_name,
            "generated_at": _iso(now),
            "narrative": (
                f"Stream splits unavailable; returning {len(device_laps)} device lap splits "
                f"for {(activity.name or 'run').strip() or 'run'}."
            ),
            "data": {
                "activity_id": str(activity_uuid),
                "activity_name": activity.name,
                "unit": normalized_unit,
                "source": "device_laps",
                "splits": [],
                "summary": {},
                "device_laps": device_laps,
                "warning": stream_warning,
            },
            "evidence": [
                {
                    "type": "activity",
                    "id": str(activity_uuid),
                    "date": to_activity_local_date(activity, _tz).isoformat() if activity.start_time else _iso(now)[:10],
                    "value": f"{(activity.name or 'Run').strip() or 'Run'} split analysis from device laps",
                }
            ],
        }

    return {
        "ok": False,
        "tool": tool_name,
        "generated_at": _iso(now),
        "error": "No split-capable data available for this activity.",
        "data": {
            "activity_id": str(activity_uuid),
            "activity_name": activity.name,
            "unit": normalized_unit,
            "source": "none",
            "splits": [],
            "summary": {},
            "device_laps": [],
            "warning": stream_warning or "No stream data and no device laps found.",
        },
        "evidence": [],
    }


# ---------------------------------------------------------------------------
# ANALYZE RUN STREAMS — Phase 2 coach tool
# ---------------------------------------------------------------------------



def analyze_run_streams(
    db: Session,
    athlete_id: UUID,
    activity_id: str,
) -> Dict[str, Any]:
    """Analyze per-second stream data for a single run activity.

    Resolves the athlete's physiological context (N=1) from the DB,
    loads the stored stream, invokes the pure-computation engine,
    and returns the standard coach tool envelope.

    Returns:
        Standard envelope with:
            data.activity_id: str
            data.analysis: dict (segments, drift, moments, plan_comparison,
                                 channels_present, channels_missing, point_count,
                                 confidence, tier_used, estimated_flags,
                                 cross_run_comparable)
            data.errors: List[dict] with {code, message, retryable}
    """
    from models import ActivityStream
    from services.run_stream_analysis import (
        AthleteContext, analyze_stream,
    )
    from services.timezone_utils import get_athlete_timezone_from_db, to_activity_local_date
    _tz = get_athlete_timezone_from_db(db, athlete_id)

    now = datetime.utcnow()
    tool_name = "analyze_run_streams"
    errors: List[Dict[str, Any]] = []

    try:
        activity_uuid = UUID(activity_id)
    except (ValueError, TypeError):
        return {
            "ok": False, "tool": tool_name, "generated_at": _iso(now),
            "error": "Invalid activity_id format",
            "data": {"activity_id": activity_id, "analysis": None, "errors": [
                {"code": "INVALID_INPUT", "message": "activity_id is not a valid UUID", "retryable": False},
            ]},
            "evidence": [],
        }

    # --- Verify activity exists and belongs to this athlete ---
    activity = (
        db.query(Activity)
        .filter(Activity.id == activity_uuid)
        .first()
    )
    if activity is None:
        return {
            "ok": False, "tool": tool_name, "generated_at": _iso(now),
            "error": "Activity not found",
            "data": {"activity_id": activity_id, "analysis": None, "errors": [
                {"code": "ACTIVITY_NOT_FOUND", "message": "No activity with this ID", "retryable": False},
            ]},
            "evidence": [],
        }

    if activity.athlete_id != athlete_id:
        return {
            "ok": False, "tool": tool_name, "generated_at": _iso(now),
            "error": "Access denied",
            "data": {"activity_id": activity_id, "analysis": None, "errors": [
                {"code": "ACCESS_DENIED", "message": "Activity does not belong to this athlete", "retryable": False},
            ]},
            "evidence": [],
        }

    # --- Check stream availability ---
    if activity.stream_fetch_status == "unavailable":
        errors.append({
            "code": "STREAMS_UNAVAILABLE",
            "message": "Stream data is permanently unavailable for this activity (manual entry or API limitation)",
            "retryable": False,
        })
        return {
            "ok": False, "tool": tool_name, "generated_at": _iso(now),
            "data": {"activity_id": activity_id, "analysis": None, "errors": errors},
            "evidence": [],
        }

    # --- Load stream data ---
    stream_row = (
        db.query(ActivityStream)
        .filter(ActivityStream.activity_id == activity_uuid)
        .first()
    )
    if stream_row is None:
        code = "STREAMS_NOT_FOUND"
        retryable = activity.stream_fetch_status in ("pending", "failed")
        errors.append({
            "code": code,
            "message": f"No stream data stored (fetch status: {activity.stream_fetch_status})",
            "retryable": retryable,
        })
        return {
            "ok": False, "tool": tool_name, "generated_at": _iso(now),
            "data": {"activity_id": activity_id, "analysis": None, "errors": errors},
            "evidence": [],
        }

    stream_data = stream_row.stream_data
    channels_available = stream_row.channels_available or list(stream_data.keys())

    # --- Resolve N=1 athlete context ---
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    athlete_ctx = None
    if athlete is not None:
        athlete_ctx = AthleteContext(
            max_hr=athlete.max_hr,
            resting_hr=athlete.resting_hr,
            threshold_hr=athlete.threshold_hr,
            threshold_pace_per_km=getattr(athlete, "threshold_pace_per_km", None),
            rpi=getattr(athlete, "rpi", None),
        )

    # --- Resolve linked planned workout (additive) ---
    planned_workout_dict = None
    linked_plan = (
        db.query(PlannedWorkout)
        .filter(PlannedWorkout.completed_activity_id == activity_uuid)
        .first()
    )
    if linked_plan is not None:
        planned_workout_dict = {
            "target_duration_minutes": linked_plan.target_duration_minutes,
            "target_distance_km": linked_plan.target_distance_km,
            "target_pace_per_km_seconds": linked_plan.target_pace_per_km_seconds,
            "segments": linked_plan.segments,  # JSONB — may be None or list of dicts
        }

    # --- Run analysis ---
    try:
        result = analyze_stream(
            stream_data=stream_data,
            channels_available=channels_available,
            planned_workout=planned_workout_dict,
            athlete_context=athlete_ctx,
        )
    except Exception as e:
        logger.exception("analyze_stream failed for activity %s", activity_id)
        return {
            "ok": False, "tool": tool_name, "generated_at": _iso(now),
            "error": str(e),
            "data": {"activity_id": activity_id, "analysis": None, "errors": [
                {"code": "ANALYSIS_FAILED", "message": str(e), "retryable": True},
            ]},
            "evidence": [],
        }

    return {
        "ok": True,
        "tool": tool_name,
        "generated_at": _iso(now),
        "data": {
            "activity_id": activity_id,
            "analysis": result.to_dict(),
            "errors": [],
        },
        "evidence": [{
            "type": "stream_analysis",
            "id": f"stream:{activity_id}",
        "date": to_activity_local_date(activity, _tz).isoformat() if activity.start_time else _iso(now)[:10],
        "value": f"tier={result.tier_used}, confidence={result.confidence}, "
                 f"segments={len(result.segments)}, moments={len(result.moments)}",
        }],
    }



