"""
GDPR Compliance Endpoints

Provides data export and account deletion endpoints for GDPR compliance.
Tone: Neutral, empowering, no guilt-inducing language.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from typing import Any, Dict, Optional
from datetime import datetime, timezone

from core.database import get_db
from core.auth import get_current_user
from core.cache import invalidate_athlete_cache
from models import (
    Athlete,
    Activity,
    ActivitySplit,
    NutritionEntry,
    BodyComposition,
    WorkPattern,
    DailyCheckin,
    ActivityFeedback,
    TrainingAvailability,
    InsightFeedback,
    TrainingPlan,
    AthleteDataImportJob,
)

router = APIRouter(prefix="/v1/gdpr", tags=["gdpr"])

DEFAULT_EXPORT_LIMIT = 25
MAX_EXPORT_LIMIT = 100


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    try:
        return dt.isoformat()
    except Exception:
        return None


def _safe_stats_summary(stats: Any) -> Dict[str, Any]:
    """
    Return a bounded, safe summary of import job stats.

    Explicitly exclude any keys that could contain raw file content or large blobs.
    """
    if not isinstance(stats, dict):
        return {}

    allow_int_keys = [
        "activities_parsed",
        "activities_inserted",
        "activities_updated",
        "activities_skipped_duplicate",
        "errors_count",
        "files_parsed",
        "pages_fetched",
    ]
    allow_list_keys = ["error_codes", "parser_types_used"]

    out: Dict[str, Any] = {}
    for k in allow_int_keys:
        v = stats.get(k)
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            out[k] = int(v)

    for k in allow_list_keys:
        v = stats.get(k)
        if isinstance(v, list):
            safe_items: list[str] = []
            for item in v[:20]:
                if isinstance(item, str):
                    s = item.strip()
                    if s:
                        safe_items.append(s[:100])
            out[k] = safe_items

    # Nested extraction stats (bounded).
    extraction = stats.get("extraction")
    if isinstance(extraction, dict):
        ex_out: Dict[str, Any] = {}
        for k in ("extracted_files", "extracted_bytes"):
            v = extraction.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                ex_out[k] = int(v)
        if ex_out:
            out["extraction"] = ex_out

    return out


@router.get("/export")
def export_user_data(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = DEFAULT_EXPORT_LIMIT,
) -> Dict:
    """
    GDPR export skeleton (Phase 8 / Sprint 2).
    
    Goal: provide a safe, bounded export suitable for compliance workflows
    without performing a full data dump yet.

    This endpoint intentionally returns:
    - profile subset (no tokens/secrets)
    - high-level counts
    - recent plans + recent import jobs (bounded)
    """
    athlete_id = current_user.id

    safe_limit = int(limit or DEFAULT_EXPORT_LIMIT)
    safe_limit = max(1, min(safe_limit, MAX_EXPORT_LIMIT))

    # Counts (high-level only)
    activities_total = int(
        db.query(func.count(Activity.id)).filter(Activity.athlete_id == athlete_id).scalar() or 0
    )
    plans_total = int(
        db.query(func.count(TrainingPlan.id)).filter(TrainingPlan.athlete_id == athlete_id).scalar() or 0
    )
    imports_jobs_total = int(
        db.query(func.count(AthleteDataImportJob.id)).filter(AthleteDataImportJob.athlete_id == athlete_id).scalar() or 0
    )

    plans_recent_rows = (
        db.query(TrainingPlan)
        .filter(TrainingPlan.athlete_id == athlete_id)
        .order_by(TrainingPlan.created_at.desc())
        .limit(safe_limit)
        .all()
    )
    plans_recent = [
        {
            "id": str(p.id),
            "name": p.name,
            "status": p.status,
            "plan_type": p.plan_type,
            "generation_method": getattr(p, "generation_method", None),
            "created_at": _iso(getattr(p, "created_at", None)),
            "plan_start_date": p.plan_start_date.isoformat() if getattr(p, "plan_start_date", None) else None,
            "plan_end_date": p.plan_end_date.isoformat() if getattr(p, "plan_end_date", None) else None,
            "goal_race_name": getattr(p, "goal_race_name", None),
            "goal_race_date": p.goal_race_date.isoformat() if getattr(p, "goal_race_date", None) else None,
        }
        for p in plans_recent_rows
    ]

    jobs_recent_rows = (
        db.query(AthleteDataImportJob)
        .filter(AthleteDataImportJob.athlete_id == athlete_id)
        .order_by(AthleteDataImportJob.created_at.desc())
        .limit(safe_limit)
        .all()
    )
    import_jobs_recent = [
        {
            "id": str(j.id),
            "provider": j.provider,
            "status": j.status,
            "created_at": _iso(getattr(j, "created_at", None)),
            "started_at": _iso(getattr(j, "started_at", None)),
            "finished_at": _iso(getattr(j, "finished_at", None)),
            "original_filename": getattr(j, "original_filename", None),
            "stats_summary": _safe_stats_summary(getattr(j, "stats", None)),
        }
        for j in jobs_recent_rows
    ]

    now = datetime.now(timezone.utc)

    return {
        "metadata": {
            "generated_at": now.isoformat(),
            "athlete_id": str(athlete_id),
            "version": "v1_skeleton",
            "bounds": {
                "recent_limit": safe_limit,
                "max_limit": MAX_EXPORT_LIMIT,
                "notes": "High-level only; not a full data dump yet.",
            },
        },
        "profile": {
            "email": current_user.email,
            "display_name": current_user.display_name,
            "created_at": _iso(getattr(current_user, "created_at", None)),
            "preferred_units": getattr(current_user, "preferred_units", None),
            "birthdate": current_user.birthdate.isoformat() if getattr(current_user, "birthdate", None) else None,
            "sex": getattr(current_user, "sex", None),
        },
        "counts": {
            "activities_total": activities_total,
            "plans_total": plans_total,
            "imports_jobs_total": imports_jobs_total,
        },
        "plans_recent": plans_recent,
        "import_jobs_recent": import_jobs_recent,
    }


@router.delete("/delete-account")
def delete_account(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict:
    """
    Delete user account and all associated data.
    
    This action is permanent and cannot be undone.
    All data will be deleted including:
    - Profile
    - Activities
    - Nutrition entries
    - Body composition
    - Work patterns
    - Daily check-ins
    - Activity feedback
    - Training availability
    - Insight feedback
    
    Tone: Neutral, clear, no guilt-inducing language.
    """
    athlete_id = current_user.id
    
    # Delete all associated data (cascade deletes handled by foreign keys)
    # But we'll be explicit for clarity
    
    # Delete insight feedback
    db.query(InsightFeedback).filter(InsightFeedback.athlete_id == athlete_id).delete()
    
    # Delete training availability
    db.query(TrainingAvailability).filter(TrainingAvailability.athlete_id == athlete_id).delete()
    
    # Delete activity feedback
    db.query(ActivityFeedback).filter(ActivityFeedback.athlete_id == athlete_id).delete()
    
    # Delete daily check-ins
    db.query(DailyCheckin).filter(DailyCheckin.athlete_id == athlete_id).delete()
    
    # Delete work patterns
    db.query(WorkPattern).filter(WorkPattern.athlete_id == athlete_id).delete()
    
    # Delete body composition
    db.query(BodyComposition).filter(BodyComposition.athlete_id == athlete_id).delete()
    
    # Delete nutrition entries
    db.query(NutritionEntry).filter(NutritionEntry.athlete_id == athlete_id).delete()
    
    # Delete activity splits (cascade from activities, but explicit for clarity)
    activities = db.query(Activity).filter(Activity.athlete_id == athlete_id).all()
    for activity in activities:
        db.query(ActivitySplit).filter(ActivitySplit.activity_id == activity.id).delete()
    
    # Delete activities
    db.query(Activity).filter(Activity.athlete_id == athlete_id).delete()
    
    # Delete athlete (this will cascade to any remaining relationships)
    db.delete(current_user)
    
    db.commit()
    
    # Invalidate cache
    invalidate_athlete_cache(str(athlete_id))
    
    return {
        "message": "Account deleted successfully",
        "deleted_at": datetime.utcnow().isoformat()
    }


