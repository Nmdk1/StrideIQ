"""
RSI-Alpha — Stream Analysis API Router

Provides GET /v1/activities/{activity_id}/stream-analysis

Returns StreamAnalysisResult + per-point stream data when available, or
lifecycle status responses (pending, unavailable) matching ADR-063 fetch states.

Response shape (success):
    {
        # ... all StreamAnalysisResult fields (flat) ...
        "stream": [               # <-- per-point data for canvas visualization
            {"time": 0, "hr": 120, "pace": 360, "altitude": 100, ...},
            ...
        ]
    }

AC coverage: AC-1 (endpoint contract)
"""
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from core.database import get_db
from core.auth import get_current_user
from models import Activity, ActivityStream, Athlete, PlannedWorkout
from services.run_stream_analysis import (
    AthleteContext,
    analyze_stream,
)
from services.stream_analysis_cache import get_or_compute_analysis

router = APIRouter(prefix="/v1/activities", tags=["stream-analysis"])

# Max points returned in the stream array (LTTB downsampled if needed)
MAX_STREAM_POINTS = 500


def _prepare_stream_points(
    stream_data: Dict[str, List],
    effort_intensity: List[float],
    max_points: int = MAX_STREAM_POINTS,
) -> List[Dict[str, Any]]:
    """Zip raw channel arrays into per-point dicts for canvas visualization.

    Converts Strava channel names to canvas-friendly keys:
        heartrate → hr, velocity_smooth → pace (s/km), grade_smooth → grade

    Applies LTTB downsampling if point count exceeds max_points.
    Includes effort from the analysis result.
    """
    time_arr = stream_data.get("time", [])
    n = len(time_arr)
    if n == 0:
        return []

    hr_arr = stream_data.get("heartrate")
    vel_arr = stream_data.get("velocity_smooth")
    alt_arr = stream_data.get("altitude")
    cad_arr = stream_data.get("cadence")
    grade_arr = stream_data.get("grade_smooth")

    points = []
    for i in range(n):
        pt: Dict[str, Any] = {"time": time_arr[i]}

        # HR
        if hr_arr and i < len(hr_arr) and hr_arr[i] is not None:
            pt["hr"] = hr_arr[i]
        else:
            pt["hr"] = None

        # Pace: convert velocity (m/s) to seconds per km
        if vel_arr and i < len(vel_arr) and vel_arr[i] is not None and vel_arr[i] > 0:
            pt["pace"] = round(1000.0 / vel_arr[i], 1)
        else:
            pt["pace"] = None

        # Altitude
        if alt_arr and i < len(alt_arr) and alt_arr[i] is not None:
            pt["altitude"] = round(alt_arr[i], 1)
        else:
            pt["altitude"] = None

        # Cadence (Strava gives half-strides; double for SPM)
        if cad_arr and i < len(cad_arr) and cad_arr[i] is not None:
            raw = cad_arr[i]
            pt["cadence"] = round(raw * 2 if raw < 120 else raw)
        else:
            pt["cadence"] = None

        # Grade
        if grade_arr and i < len(grade_arr) and grade_arr[i] is not None:
            pt["grade"] = round(grade_arr[i], 2)
        else:
            pt["grade"] = None

        # Effort (from analysis)
        if i < len(effort_intensity):
            pt["effort"] = round(effort_intensity[i], 4)
        else:
            pt["effort"] = 0.0

        points.append(pt)

    # LTTB downsample if too many points (use HR as the reference channel)
    if len(points) > max_points:
        points = _lttb_downsample(points, max_points)

    return points


def _lttb_downsample(
    points: List[Dict[str, Any]], target: int
) -> List[Dict[str, Any]]:
    """Largest-Triangle-Three-Buckets downsampling on time/hr."""
    n = len(points)
    if n <= target:
        return points

    sampled = [points[0]]
    bucket_size = (n - 2) / (target - 2)

    a_idx = 0
    for i in range(1, target - 1):
        bucket_start = int((i - 1) * bucket_size) + 1
        bucket_end = int(i * bucket_size) + 1
        bucket_end = min(bucket_end, n - 1)

        next_start = int(i * bucket_size) + 1
        next_end = int((i + 1) * bucket_size) + 1
        next_end = min(next_end, n)

        # Average of next bucket (for triangle area)
        avg_time = sum(p["time"] for p in points[next_start:next_end]) / max(1, next_end - next_start)
        avg_hr = 0.0
        hr_count = 0
        for p in points[next_start:next_end]:
            if p.get("hr") is not None:
                avg_hr += p["hr"]
                hr_count += 1
        if hr_count > 0:
            avg_hr /= hr_count

        # Pick point with max triangle area
        max_area = -1
        best_idx = bucket_start
        a_time = points[a_idx]["time"]
        a_hr = points[a_idx].get("hr") or 0

        for j in range(bucket_start, bucket_end):
            p_time = points[j]["time"]
            p_hr = points[j].get("hr") or 0
            area = abs(
                (a_time - avg_time) * (p_hr - a_hr)
                - (a_time - p_time) * (avg_hr - a_hr)
            )
            if area > max_area:
                max_area = area
                best_idx = j

        sampled.append(points[best_idx])
        a_idx = best_idx

    sampled.append(points[-1])
    return sampled


@router.get("/{activity_id}/stream-analysis")
def get_stream_analysis(
    activity_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Analyze per-second stream data for a completed run.

    Returns:
        - Full StreamAnalysisResult when stream_fetch_status == 'success'
        - {"status": "pending"} when fetch is in progress
        - {"status": "unavailable"} for manual activities
        - 404 when activity not found or not owned by current user
        - 401 when not authenticated
    """
    # --- Activity lookup + ownership check ---
    activity = (
        db.query(Activity)
        .filter(Activity.id == activity_id)
        .first()
    )
    if activity is None or activity.athlete_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found",
        )

    # --- Lifecycle state handling (ADR-063) ---
    fetch_status = getattr(activity, "stream_fetch_status", None)

    if fetch_status == "unavailable":
        return {"status": "unavailable"}

    if fetch_status in ("pending", "fetching", "failed", None):
        return {"status": "pending"}

    # --- Load stream data ---
    stream_row = (
        db.query(ActivityStream)
        .filter(ActivityStream.activity_id == activity_id)
        .first()
    )
    if stream_row is None:
        return {"status": "pending"}

    # --- Resolve N=1 athlete context ---
    athlete_ctx = AthleteContext(
        max_hr=getattr(current_user, "max_hr", None),
        resting_hr=getattr(current_user, "resting_hr", None),
        threshold_hr=getattr(current_user, "threshold_hr", None),
    )

    # --- Resolve linked planned workout (additive) ---
    planned_workout_dict = None
    linked_plan = (
        db.query(PlannedWorkout)
        .filter(PlannedWorkout.completed_activity_id == activity_id)
        .first()
    )
    if linked_plan is not None:
        planned_workout_dict = {
            "title": linked_plan.title,
            "workout_type": linked_plan.workout_type,
            "target_duration_minutes": linked_plan.target_duration_minutes,
            "target_distance_km": getattr(linked_plan, "target_distance_km", None),
            "segments": getattr(linked_plan, "segments", None),
        }

    # --- Get Gemini client for A3 moment narratives (best-effort) ---
    gemini_client = None
    try:
        from tasks.intelligence_tasks import _get_gemini_client
        gemini_client = _get_gemini_client()
    except Exception:
        pass

    # --- Get analysis from cache or compute + cache ---
    # Spec decision: "Cache full StreamAnalysisResult in DB."
    response = get_or_compute_analysis(
        activity_id=activity_id,
        stream_row=stream_row,
        athlete_ctx=athlete_ctx,
        db=db,
        planned_workout_dict=planned_workout_dict,
        gemini_client=gemini_client,
    )

    # --- Append per-point stream data for canvas visualization ---
    # Zips raw channels into [{time, hr, pace, altitude, grade, cadence, effort}],
    # LTTB downsampled to ≤500 points server-side.
    # Note: stream points are NOT cached (they're derived from raw data + effort_intensity).
    response["stream"] = _prepare_stream_points(
        stream_data=stream_row.stream_data,
        effort_intensity=response.get("effort_intensity", []),
    )

    return response
