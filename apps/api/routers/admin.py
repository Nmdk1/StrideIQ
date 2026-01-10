"""
Admin/Owners Dashboard API Router

Comprehensive command center for site management, monitoring, testing, and debugging.
Owner/admin role only.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_
from typing import List, Optional, Dict
from uuid import UUID
from datetime import datetime, timedelta

from core.database import get_db
from core.auth import require_admin
from models import Athlete, Activity, NutritionEntry, WorkPattern, BodyComposition, ActivityFeedback, InsightFeedback
from schemas import AthleteResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin", tags=["admin"])


@router.get("/users")
def list_users(
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
    search: Optional[str] = Query(None, description="Search by email or display name"),
    role: Optional[str] = Query(None, description="Filter by role"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    List all users with filtering and pagination.
    Admin/owner only.
    """
    query = db.query(Athlete)
    
    if search:
        query = query.filter(
            or_(
                Athlete.email.ilike(f"%{search}%"),
                Athlete.display_name.ilike(f"%{search}%")
            )
        )
    
    if role:
        query = query.filter(Athlete.role == role)
    
    total = query.count()
    users = query.order_by(Athlete.created_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "total": total,
        "users": [
            {
                "id": str(user.id),
                "email": user.email,
                "display_name": user.display_name,
                "role": user.role,
                "subscription_tier": user.subscription_tier,
                "created_at": user.created_at.isoformat(),
                "onboarding_completed": user.onboarding_completed,
            }
            for user in users
        ],
        "offset": offset,
        "limit": limit,
    }


@router.get("/users/{user_id}")
def get_user(
    user_id: UUID,
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Get detailed user information.
    Admin/owner only.
    """
    user = db.query(Athlete).filter(Athlete.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get activity count
    activity_count = db.query(Activity).filter(Activity.athlete_id == user_id).count()
    
    # Get data collection stats
    nutrition_count = db.query(NutritionEntry).filter(NutritionEntry.athlete_id == user_id).count()
    work_pattern_count = db.query(WorkPattern).filter(WorkPattern.athlete_id == user_id).count()
    body_comp_count = db.query(BodyComposition).filter(BodyComposition.athlete_id == user_id).count()
    
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "subscription_tier": user.subscription_tier,
        "created_at": user.created_at.isoformat(),
        "onboarding_completed": user.onboarding_completed,
        "onboarding_stage": user.onboarding_stage,
        "stats": {
            "activities": activity_count,
            "nutrition_entries": nutrition_count,
            "work_patterns": work_pattern_count,
            "body_composition_entries": body_comp_count,
        },
    }


@router.post("/users/{user_id}/impersonate")
def start_impersonation(
    user_id: UUID,
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Start impersonation session for a user.
    Returns a temporary token that can be used to act as that user.
    Admin/owner only.
    """
    target_user = db.query(Athlete).filter(Athlete.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Generate impersonation token (simplified - in production, use proper JWT with impersonation claim)
    from core.security import create_access_token
    impersonation_token = create_access_token(
        data={
            "sub": str(target_user.id),
            "email": target_user.email,
            "role": target_user.role,
            "impersonated_by": str(current_user.id),
            "is_impersonation": True,
        }
    )
    
    logger.warning(f"Admin {current_user.email} started impersonation of {target_user.email}")
    
    return {
        "token": impersonation_token,
        "user": {
            "id": str(target_user.id),
            "email": target_user.email,
            "display_name": target_user.display_name,
        },
        "impersonated_by": {
            "id": str(current_user.id),
            "email": current_user.email,
        },
    }


@router.get("/health")
def get_system_health(
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Get detailed system health metrics.
    Admin/owner only.
    """
    # Database health
    try:
        db.execute(func.now())
        db_healthy = True
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        db_healthy = False
    
    # User counts
    total_users = db.query(Athlete).count()
    active_users = db.query(Athlete).filter(
        Athlete.created_at >= datetime.now() - timedelta(days=30)
    ).count()
    
    # Activity counts
    total_activities = db.query(Activity).count()
    recent_activities = db.query(Activity).filter(
        Activity.start_time >= datetime.now() - timedelta(days=7)
    ).count()
    
    # Data collection stats
    nutrition_entries = db.query(NutritionEntry).count()
    work_patterns = db.query(WorkPattern).count()
    body_composition = db.query(BodyComposition).count()
    
    return {
        "database": "healthy" if db_healthy else "unhealthy",
        "users": {
            "total": total_users,
            "active_30d": active_users,
        },
        "activities": {
            "total": total_activities,
            "last_7d": recent_activities,
        },
        "data_collection": {
            "nutrition_entries": nutrition_entries,
            "work_patterns": work_patterns,
            "body_composition": body_composition,
        },
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/metrics")
def get_site_metrics(
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
):
    """
    Get site-wide metrics for growth and engagement.
    Admin/owner only.
    """
    cutoff_date = datetime.now() - timedelta(days=days)
    
    # User growth
    new_users = db.query(Athlete).filter(
        Athlete.created_at >= cutoff_date
    ).count()
    
    # Engagement metrics
    users_with_activities = db.query(func.count(func.distinct(Activity.athlete_id))).filter(
        Activity.start_time >= cutoff_date
    ).scalar()
    
    users_with_nutrition = db.query(func.count(func.distinct(NutritionEntry.athlete_id))).filter(
        NutritionEntry.date >= cutoff_date.date()
    ).scalar()
    
    # Average activities per user
    avg_activities = db.query(
        func.avg(func.count(Activity.id))
    ).filter(
        Activity.start_time >= cutoff_date
    ).group_by(Activity.athlete_id).scalar() or 0
    
    return {
        "period_days": days,
        "user_growth": {
            "new_users": new_users,
            "growth_rate": round((new_users / max(1, db.query(Athlete).filter(Athlete.created_at < cutoff_date).count())) * 100, 2),
        },
        "engagement": {
            "users_with_activities": users_with_activities,
            "users_with_nutrition": users_with_nutrition,
            "avg_activities_per_user": round(float(avg_activities), 2),
        },
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/correlations/test")
def test_correlation_calculation(
    athlete_id: UUID = Query(..., description="Athlete ID to test"),
    days: int = Query(90, ge=30, le=365),
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Trigger correlation calculation for a specific athlete and return raw output.
    Admin/owner only.
    """
    from services.correlation_engine import analyze_correlations
    
    try:
        result = analyze_correlations(
            athlete_id=str(athlete_id),
            days=days,
            db=db
        )
        
        return {
            "status": "success",
            "athlete_id": str(athlete_id),
            "days": days,
            "result": result,
        }
    except Exception as e:
        logger.error(f"Error testing correlations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )


@router.get("/query/templates")
def list_query_templates(
    current_user: Athlete = Depends(require_admin),
):
    """
    List available query templates.
    Admin/owner only.
    """
    return {
        "templates": [
            {
                "name": "efficiency_by_workout_type",
                "description": "Average efficiency by workout type",
                "scope": "admin",
                "params": ["athlete_id (optional)", "days"],
            },
            {
                "name": "workout_type_distribution", 
                "description": "Distribution of workout types across all athletes",
                "scope": "admin",
                "params": ["days"],
            },
            {
                "name": "correlation_patterns",
                "description": "Significant correlations found across athletes",
                "scope": "admin", 
                "params": ["min_strength"],
            },
            {
                "name": "cross_athlete_efficiency",
                "description": "Efficiency distribution across population",
                "scope": "admin",
                "params": ["days"],
            },
            {
                "name": "performance_over_time",
                "description": "Track an athlete's performance metrics over time",
                "scope": "admin",
                "params": ["athlete_id", "workout_type (optional)", "days"],
            },
        ]
    }


@router.post("/query/execute")
def execute_query_template(
    template: str = Query(..., description="Template name"),
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
    athlete_id: Optional[UUID] = Query(None, description="Athlete ID for single-athlete queries"),
    days: int = Query(180, ge=1, le=730),
    workout_type: Optional[str] = Query(None, description="Filter by workout type"),
    min_strength: float = Query(0.3, ge=0.0, le=1.0, description="Min correlation strength"),
):
    """
    Execute a pre-built query template.
    Admin/owner only.
    """
    from services.query_engine import QueryEngine, QueryTemplates, QueryScope
    
    engine = QueryEngine(db)
    
    # Get the appropriate template
    if template == "efficiency_by_workout_type":
        spec = QueryTemplates.efficiency_by_workout_type(athlete_id=athlete_id, days=days)
    elif template == "workout_type_distribution":
        spec = QueryTemplates.workout_type_distribution(days=days)
    elif template == "correlation_patterns":
        spec = QueryTemplates.correlation_patterns(min_strength=min_strength)
    elif template == "cross_athlete_efficiency":
        spec = QueryTemplates.cross_athlete_efficiency_distribution(days=days)
    elif template == "performance_over_time":
        if not athlete_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="athlete_id required for performance_over_time template"
            )
        spec = QueryTemplates.performance_over_time(
            athlete_id=athlete_id, 
            workout_type=workout_type,
            days=days
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown template: {template}"
        )
    
    # Execute with admin scope
    result = engine.execute(spec, current_user, scope=QueryScope.ADMIN_ONLY)
    
    return {
        "template": template,
        "success": result.success,
        "data": result.data,
        "total_count": result.total_count,
        "execution_time_ms": result.execution_time_ms,
        "metadata": result.metadata,
        "error": result.error,
    }


@router.post("/query/custom")
def execute_custom_query(
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
    entity: str = Query(..., description="Entity to query: activity, nutrition, body_composition, correlation"),
    days: int = Query(180, ge=1, le=730),
    athlete_id: Optional[UUID] = Query(None, description="Filter to specific athlete"),
    group_by: Optional[str] = Query(None, description="Comma-separated fields to group by"),
    aggregations: Optional[str] = Query(None, description="Comma-separated field:agg_type pairs (e.g., 'efficiency:avg,distance_m:sum')"),
    filters_json: Optional[str] = Query(None, description="JSON array of filter objects [{field, operator, value}]"),
    sort_by: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    Execute a custom query with full flexibility.
    Admin/owner only.
    
    This is the power user interface - allows arbitrary queries
    with proper access control.
    """
    from services.query_engine import (
        QueryEngine, QuerySpec, QueryFilter, QueryScope, AggregationType
    )
    import json
    
    engine = QueryEngine(db)
    
    # Parse filters
    query_filters = []
    if filters_json:
        try:
            filter_list = json.loads(filters_json)
            for f in filter_list:
                query_filters.append(QueryFilter(
                    field=f.get("field"),
                    operator=f.get("operator", "eq"),
                    value=f.get("value")
                ))
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid filters_json: {str(e)}"
            )
    
    # Parse group_by
    group_by_list = group_by.split(",") if group_by else None
    
    # Parse aggregations
    agg_dict = None
    if aggregations:
        agg_dict = {}
        for pair in aggregations.split(","):
            if ":" in pair:
                field, agg_type = pair.split(":", 1)
                try:
                    agg_dict[field.strip()] = AggregationType(agg_type.strip())
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid aggregation type: {agg_type}"
                    )
    
    # Build spec
    spec = QuerySpec(
        entity=entity,
        days=days,
        athlete_id=athlete_id,
        filters=query_filters,
        group_by=group_by_list,
        aggregations=agg_dict,
        sort_by=sort_by,
        limit=limit,
        anonymize=True,
    )
    
    # Execute
    result = engine.execute(spec, current_user, scope=QueryScope.ADMIN_ONLY)
    
    return {
        "entity": entity,
        "success": result.success,
        "data": result.data,
        "total_count": result.total_count,
        "execution_time_ms": result.execution_time_ms,
        "metadata": result.metadata,
        "error": result.error,
    }


@router.get("/query/entities")
def list_queryable_entities(
    current_user: Athlete = Depends(require_admin),
):
    """
    List all entities that can be queried with their available fields.
    Admin/owner only.
    """
    from services.query_engine import QueryEngine
    
    entities = {}
    for entity_name, model in QueryEngine.ENTITY_MODELS.items():
        entities[entity_name] = {
            "fields": [col.name for col in model.__table__.columns],
            "date_field": QueryEngine.DATE_FIELDS.get(entity_name),
        }
    
    return {"entities": entities}


@router.get("/query")
def cross_athlete_query(
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
    query_type: str = Query(..., description="Query type: 'avg_efficiency', 'correlation_patterns', 'workout_distribution'"),
    min_activities: int = Query(10, ge=1, description="Minimum activities per athlete"),
    days: int = Query(180, ge=1, le=730),
):
    """
    Cross-athlete anonymized aggregate queries (legacy endpoint).
    Use /query/execute or /query/custom for full functionality.
    Admin/owner only.
    """
    from services.query_engine import QueryEngine, QueryTemplates, QueryScope
    
    engine = QueryEngine(db)
    
    if query_type == "avg_efficiency":
        spec = QueryTemplates.efficiency_by_workout_type(days=days)
        result = engine.execute(spec, current_user, scope=QueryScope.ADMIN_ONLY)
        return {
            "query_type": query_type,
            "data": result.data,
            "execution_time_ms": result.execution_time_ms,
        }
    
    elif query_type == "correlation_patterns":
        spec = QueryTemplates.correlation_patterns()
        result = engine.execute(spec, current_user, scope=QueryScope.ADMIN_ONLY)
        return {
            "query_type": query_type,
            "data": result.data,
            "execution_time_ms": result.execution_time_ms,
        }
    
    elif query_type == "workout_distribution":
        spec = QueryTemplates.workout_type_distribution(days=days)
        result = engine.execute(spec, current_user, scope=QueryScope.ADMIN_ONLY)
        return {
            "query_type": query_type,
            "data": result.data,
            "execution_time_ms": result.execution_time_ms,
        }
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown query type: {query_type}. Use /query/templates to see available options."
        )

