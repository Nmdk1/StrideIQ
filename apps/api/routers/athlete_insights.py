"""
Athlete Insights API Router

Guided query interface for athletes to explore their own data.
Access: All authenticated athletes (own data only)
Advanced queries: Top tier subscribers only

This provides the "self-query" functionality discussed in requirements:
- Athletes can filter and analyze their own activities
- Pre-built templates for common questions
- No cross-athlete access (that's admin only)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta
from pydantic import BaseModel

from core.database import get_db
from core.auth import get_current_athlete, require_query_access, TOP_TIERS
from models import Athlete, Activity
from services.query_engine import (
    QueryEngine, QuerySpec, QueryFilter, QueryScope,
    QueryTemplates, AggregationType, SortOrder
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/athlete/insights", tags=["athlete-insights"])


class InsightTemplate(BaseModel):
    """Template definition for UI"""
    id: str
    name: str
    description: str
    category: str
    requires_premium: bool
    params: List[str]


# Available insight templates for athletes
ATHLETE_TEMPLATES = [
    InsightTemplate(
        id="efficiency_trend",
        name="Efficiency Trend",
        description="See how your running efficiency has changed over time",
        category="performance",
        requires_premium=False,
        params=["days"],
    ),
    InsightTemplate(
        id="workout_distribution",
        name="Workout Distribution",
        description="Breakdown of your training by workout type",
        category="training",
        requires_premium=False,
        params=["days"],
    ),
    InsightTemplate(
        id="best_performances",
        name="Best Performances",
        description="Your top runs by efficiency score",
        category="performance",
        requires_premium=False,
        params=["days", "limit"],
    ),
    InsightTemplate(
        id="weather_impact",
        name="Weather Impact",
        description="How temperature affects your performance",
        category="conditions",
        requires_premium=True,
        params=["days"],
    ),
    InsightTemplate(
        id="weekly_volume",
        name="Weekly Volume",
        description="Training volume trends by week",
        category="training",
        requires_premium=False,
        params=["weeks"],
    ),
    InsightTemplate(
        id="heart_rate_zones",
        name="Heart Rate Analysis",
        description="Time and distance at different heart rate levels",
        category="physiology",
        requires_premium=True,
        params=["days"],
    ),
    InsightTemplate(
        id="personal_records",
        name="Personal Records",
        description="Your best efforts by distance",
        category="performance",
        requires_premium=False,
        params=[],
    ),
    InsightTemplate(
        id="consistency_score",
        name="Consistency Score",
        description="How consistent is your training week-to-week?",
        category="training",
        requires_premium=True,
        params=["weeks"],
    ),
]


@router.get("/templates")
def get_insight_templates(
    athlete: Athlete = Depends(get_current_athlete),
):
    """
    Get available insight templates for the current athlete.
    
    Some templates require premium subscription.
    """
    is_premium = athlete.subscription_tier in TOP_TIERS or athlete.role in ("admin", "owner")
    
    return {
        "templates": [
            {
                **t.model_dump(),
                "available": not t.requires_premium or is_premium,
            }
            for t in ATHLETE_TEMPLATES
        ],
        "is_premium": is_premium,
    }


@router.post("/execute/{template_id}")
def execute_insight(
    template_id: str,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
    days: int = Query(90, ge=7, le=365),
    weeks: int = Query(12, ge=4, le=52),
    limit: int = Query(10, ge=1, le=50),
):
    """
    Execute an insight template for the current athlete.
    
    Returns analyzed data based on the template.
    """
    import time
    start = time.time()
    
    # Find template
    template = next((t for t in ATHLETE_TEMPLATES if t.id == template_id), None)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")
    
    # Check premium access
    is_premium = athlete.subscription_tier in TOP_TIERS or athlete.role in ("admin", "owner")
    if template.requires_premium and not is_premium:
        raise HTTPException(
            status_code=403, 
            detail="This insight requires a premium subscription"
        )
    
    engine = QueryEngine(db)
    result_data = None
    
    try:
        if template_id == "efficiency_trend":
            result_data = _get_efficiency_trend(engine, athlete, days)
        
        elif template_id == "workout_distribution":
            result_data = _get_workout_distribution(engine, athlete, days)
        
        elif template_id == "best_performances":
            result_data = _get_best_performances(engine, athlete, days, limit)
        
        elif template_id == "weather_impact":
            result_data = _get_weather_impact(engine, athlete, days)
        
        elif template_id == "weekly_volume":
            result_data = _get_weekly_volume(db, athlete, weeks)
        
        elif template_id == "heart_rate_zones":
            result_data = _get_hr_analysis(engine, athlete, days)
        
        elif template_id == "personal_records":
            result_data = _get_personal_records(db, athlete)
        
        elif template_id == "consistency_score":
            result_data = _get_consistency_score(db, athlete, weeks)
        
        else:
            raise HTTPException(status_code=400, detail=f"Template not implemented: {template_id}")
        
        execution_time = (time.time() - start) * 1000
        
        return {
            "template_id": template_id,
            "template_name": template.name,
            "success": True,
            "data": result_data,
            "execution_time_ms": round(execution_time, 2),
        }
        
    except Exception as e:
        logger.error(f"Insight execution error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _get_efficiency_trend(engine: QueryEngine, athlete: Athlete, days: int) -> dict:
    """Get efficiency over time"""
    spec = QuerySpec(
        entity="activity",
        days=days,
        athlete_id=athlete.id,
        filters=[
            QueryFilter("efficiency", "is_null", False),
            QueryFilter("distance_m", "gte", 3000),  # At least 3km
        ],
        fields=["start_time", "efficiency", "distance_m", "workout_type", "avg_hr"],
        sort_by="start_time",
        sort_order=SortOrder.ASC,
        limit=500,
    )
    result = engine.execute(spec, athlete, scope=QueryScope.SELF_ONLY)
    
    # Calculate trend
    data = result.data
    if len(data) >= 2:
        first_half = data[:len(data)//2]
        second_half = data[len(data)//2:]
        
        avg_first = sum(d.get('efficiency', 0) or 0 for d in first_half) / len(first_half) if first_half else 0
        avg_second = sum(d.get('efficiency', 0) or 0 for d in second_half) / len(second_half) if second_half else 0
        
        if avg_first > 0:
            change_pct = ((avg_second - avg_first) / avg_first) * 100
            trend = "improving" if change_pct > 2 else "declining" if change_pct < -2 else "stable"
        else:
            change_pct = 0
            trend = "stable"
    else:
        trend = "insufficient_data"
        change_pct = 0
    
    return {
        "activities": data,
        "count": len(data),
        "trend": trend,
        "change_pct": round(change_pct, 1),
        "period_days": days,
    }


def _get_workout_distribution(engine: QueryEngine, athlete: Athlete, days: int) -> dict:
    """Get workout type breakdown"""
    spec = QuerySpec(
        entity="activity",
        days=days,
        athlete_id=athlete.id,
        filters=[
            QueryFilter("workout_type", "is_null", False),
        ],
        group_by=["workout_type"],
        aggregations={
            "distance_m": AggregationType.SUM,
            "duration_s": AggregationType.SUM,
        },
    )
    result = engine.execute(spec, athlete, scope=QueryScope.SELF_ONLY)
    
    # Calculate percentages
    total_distance = sum(d.get('sum_distance_m', 0) or 0 for d in result.data)
    total_time = sum(d.get('sum_duration_s', 0) or 0 for d in result.data)
    
    distribution = []
    for item in result.data:
        dist = item.get('sum_distance_m', 0) or 0
        time_s = item.get('sum_duration_s', 0) or 0
        
        distribution.append({
            "workout_type": item.get('workout_type'),
            "distance_km": round(dist / 1000, 1),
            "distance_pct": round((dist / total_distance * 100) if total_distance else 0, 1),
            "time_hours": round(time_s / 3600, 1),
            "time_pct": round((time_s / total_time * 100) if total_time else 0, 1),
            "count": item.get('record_count', 0),
        })
    
    # Sort by distance
    distribution.sort(key=lambda x: x['distance_km'], reverse=True)
    
    return {
        "distribution": distribution,
        "total_distance_km": round(total_distance / 1000, 1),
        "total_time_hours": round(total_time / 3600, 1),
        "period_days": days,
    }


def _get_best_performances(engine: QueryEngine, athlete: Athlete, days: int, limit: int) -> dict:
    """Get top performances by efficiency"""
    spec = QuerySpec(
        entity="activity",
        days=days,
        athlete_id=athlete.id,
        filters=[
            QueryFilter("efficiency", "is_null", False),
            QueryFilter("distance_m", "gte", 5000),  # At least 5km
        ],
        fields=["id", "name", "start_time", "distance_m", "duration_s", "efficiency", "workout_type", "avg_hr"],
        sort_by="efficiency",
        sort_order=SortOrder.DESC,
        limit=limit,
    )
    result = engine.execute(spec, athlete, scope=QueryScope.SELF_ONLY)
    
    return {
        "performances": result.data,
        "count": len(result.data),
        "period_days": days,
    }


def _get_weather_impact(engine: QueryEngine, athlete: Athlete, days: int) -> dict:
    """Analyze performance by temperature"""
    # Get activities with temperature data
    spec = QuerySpec(
        entity="activity",
        days=days,
        athlete_id=athlete.id,
        filters=[
            QueryFilter("temperature_f", "is_null", False),
            QueryFilter("efficiency", "is_null", False),
            QueryFilter("distance_m", "gte", 5000),
        ],
        fields=["start_time", "temperature_f", "efficiency", "distance_m", "workout_type"],
        limit=500,
    )
    result = engine.execute(spec, athlete, scope=QueryScope.SELF_ONLY)
    
    # Bucket by temperature ranges
    buckets = {
        "cold": {"range": "<50°F", "activities": [], "avg_eff": 0},
        "cool": {"range": "50-65°F", "activities": [], "avg_eff": 0},
        "moderate": {"range": "65-75°F", "activities": [], "avg_eff": 0},
        "warm": {"range": "75-85°F", "activities": [], "avg_eff": 0},
        "hot": {"range": ">85°F", "activities": [], "avg_eff": 0},
    }
    
    for act in result.data:
        temp = act.get('temperature_f')
        eff = act.get('efficiency')
        if temp is None or eff is None:
            continue
        
        if temp < 50:
            buckets["cold"]["activities"].append(eff)
        elif temp < 65:
            buckets["cool"]["activities"].append(eff)
        elif temp < 75:
            buckets["moderate"]["activities"].append(eff)
        elif temp < 85:
            buckets["warm"]["activities"].append(eff)
        else:
            buckets["hot"]["activities"].append(eff)
    
    # Calculate averages
    weather_impact = []
    for key, bucket in buckets.items():
        activities = bucket["activities"]
        if activities:
            avg_eff = sum(activities) / len(activities)
            weather_impact.append({
                "condition": key,
                "range": bucket["range"],
                "count": len(activities),
                "avg_efficiency": round(avg_eff, 4),
            })
    
    # Find best conditions
    best = max(weather_impact, key=lambda x: x["avg_efficiency"]) if weather_impact else None
    
    return {
        "by_temperature": weather_impact,
        "best_conditions": best["condition"] if best else None,
        "total_activities": len(result.data),
        "period_days": days,
    }


def _get_weekly_volume(db: Session, athlete: Athlete, weeks: int) -> dict:
    """Get weekly training volume"""
    from sqlalchemy import func, extract
    
    cutoff = datetime.now() - timedelta(weeks=weeks)
    
    # Query activities grouped by week
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete.id,
        Activity.start_time >= cutoff,
        Activity.distance_m.isnot(None),
    ).order_by(Activity.start_time).all()
    
    # Group by week
    from collections import defaultdict
    weekly = defaultdict(lambda: {"distance_km": 0, "time_hours": 0, "count": 0})
    
    for act in activities:
        week_start = act.start_time - timedelta(days=act.start_time.weekday())
        week_key = week_start.strftime("%Y-%m-%d")
        
        weekly[week_key]["distance_km"] += (act.distance_m or 0) / 1000
        weekly[week_key]["time_hours"] += (act.duration_s or 0) / 3600
        weekly[week_key]["count"] += 1
    
    # Convert to list and sort
    volume_data = [
        {
            "week": key,
            "distance_km": round(val["distance_km"], 1),
            "time_hours": round(val["time_hours"], 1),
            "count": val["count"],
        }
        for key, val in sorted(weekly.items())
    ]
    
    # Calculate averages
    if volume_data:
        avg_dist = sum(w["distance_km"] for w in volume_data) / len(volume_data)
        avg_time = sum(w["time_hours"] for w in volume_data) / len(volume_data)
    else:
        avg_dist = avg_time = 0
    
    return {
        "weeks": volume_data,
        "avg_weekly_distance_km": round(avg_dist, 1),
        "avg_weekly_time_hours": round(avg_time, 1),
        "total_weeks": len(volume_data),
    }


def _get_hr_analysis(engine: QueryEngine, athlete: Athlete, days: int) -> dict:
    """Analyze heart rate distribution"""
    spec = QuerySpec(
        entity="activity",
        days=days,
        athlete_id=athlete.id,
        filters=[
            QueryFilter("avg_hr", "is_null", False),
            QueryFilter("avg_hr", "gte", 80),
        ],
        fields=["avg_hr", "max_hr", "distance_m", "duration_s", "workout_type"],
        limit=500,
    )
    result = engine.execute(spec, athlete, scope=QueryScope.SELF_ONLY)
    
    # Estimate zones (simplified - would be better with actual threshold data)
    # Zone 1: <65% max HR, Zone 2: 65-75%, Zone 3: 75-85%, Zone 4: 85-92%, Zone 5: >92%
    zones = {
        "zone1_easy": {"distance_km": 0, "time_hours": 0, "count": 0},
        "zone2_aerobic": {"distance_km": 0, "time_hours": 0, "count": 0},
        "zone3_tempo": {"distance_km": 0, "time_hours": 0, "count": 0},
        "zone4_threshold": {"distance_km": 0, "time_hours": 0, "count": 0},
        "zone5_vo2max": {"distance_km": 0, "time_hours": 0, "count": 0},
    }
    
    # Estimate max HR from data (or use 220-age if we had age)
    max_hrs = [d.get('max_hr') for d in result.data if d.get('max_hr')]
    est_max_hr = max(max_hrs) if max_hrs else 185
    
    for act in result.data:
        avg_hr = act.get('avg_hr')
        if not avg_hr:
            continue
        
        pct_max = avg_hr / est_max_hr * 100
        dist = (act.get('distance_m') or 0) / 1000
        time_h = (act.get('duration_s') or 0) / 3600
        
        if pct_max < 65:
            zone = "zone1_easy"
        elif pct_max < 75:
            zone = "zone2_aerobic"
        elif pct_max < 85:
            zone = "zone3_tempo"
        elif pct_max < 92:
            zone = "zone4_threshold"
        else:
            zone = "zone5_vo2max"
        
        zones[zone]["distance_km"] += dist
        zones[zone]["time_hours"] += time_h
        zones[zone]["count"] += 1
    
    # Format output
    hr_distribution = [
        {
            "zone": key.replace("zone", "Zone ").replace("_", " - ").title(),
            "distance_km": round(val["distance_km"], 1),
            "time_hours": round(val["time_hours"], 1),
            "count": val["count"],
        }
        for key, val in zones.items()
    ]
    
    return {
        "distribution": hr_distribution,
        "estimated_max_hr": est_max_hr,
        "total_activities": len(result.data),
        "period_days": days,
    }


def _get_personal_records(db: Session, athlete: Athlete) -> dict:
    """Get personal records by distance"""
    from models import PersonalBest
    
    pbs = db.query(PersonalBest).filter(
        PersonalBest.athlete_id == athlete.id
    ).order_by(PersonalBest.distance_category).all()
    
    records = []
    for pb in pbs:
        records.append({
            "distance": pb.distance_category,
            "distance_meters": pb.distance_meters,
            "time_seconds": pb.time_seconds,
            "time_formatted": _format_duration(pb.time_seconds),
            "pace_per_mile": pb.pace_per_mile,
            "date": pb.achieved_at.isoformat() if pb.achieved_at else None,
            "activity_id": str(pb.activity_id) if pb.activity_id else None,
            "is_race": pb.is_race,
        })
    
    return {
        "records": records,
        "count": len(records),
    }


def _get_consistency_score(db: Session, athlete: Athlete, weeks: int) -> dict:
    """Calculate training consistency"""
    cutoff = datetime.now() - timedelta(weeks=weeks)
    
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete.id,
        Activity.start_time >= cutoff,
    ).all()
    
    # Count activities per week
    from collections import defaultdict
    weekly_counts = defaultdict(int)
    weekly_distance = defaultdict(float)
    
    for act in activities:
        week_start = act.start_time - timedelta(days=act.start_time.weekday())
        week_key = week_start.strftime("%Y-%m-%d")
        weekly_counts[week_key] += 1
        weekly_distance[week_key] += (act.distance_m or 0) / 1000
    
    # Calculate consistency metrics
    counts = list(weekly_counts.values())
    distances = list(weekly_distance.values())
    
    if len(counts) < 2:
        return {"score": 0, "message": "Need at least 2 weeks of data"}
    
    # Consistency = inverse of coefficient of variation
    import statistics
    
    avg_count = statistics.mean(counts)
    avg_dist = statistics.mean(distances)
    
    if avg_count > 0:
        cv_count = statistics.stdev(counts) / avg_count if len(counts) > 1 else 0
    else:
        cv_count = 1
    
    if avg_dist > 0:
        cv_dist = statistics.stdev(distances) / avg_dist if len(distances) > 1 else 0
    else:
        cv_dist = 1
    
    # Score 0-100 (100 = perfectly consistent)
    score = max(0, min(100, 100 - (cv_count + cv_dist) * 50))
    
    # Rating
    if score >= 80:
        rating = "Excellent"
        message = "Your training is very consistent. Keep it up!"
    elif score >= 60:
        rating = "Good"
        message = "Solid consistency. Minor variations week to week."
    elif score >= 40:
        rating = "Fair"
        message = "Some inconsistency in training load. Try to maintain steadier volume."
    else:
        rating = "Needs Work"
        message = "Training is quite variable. Consider establishing a more regular routine."
    
    return {
        "score": round(score, 1),
        "rating": rating,
        "message": message,
        "avg_runs_per_week": round(avg_count, 1),
        "avg_km_per_week": round(avg_dist, 1),
        "weeks_analyzed": len(counts),
    }


def _format_duration(seconds: int) -> str:
    """Format seconds as H:MM:SS or MM:SS"""
    if seconds is None:
        return "-"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"
