"""
Query Engine Service

A flexible, powerful query system for mining athlete data.
Supports both single-athlete queries and cross-athlete aggregate analysis.

Access Levels:
- Athletes: Own data only, guided queries
- Top Tier: Own data + advanced queries
- Admin/Owner: Cross-athlete anonymized aggregates + all queries

Architecture:
- QueryBuilder: Constructs queries from DSL
- QueryExecutor: Runs queries with proper access control
- QueryResult: Standardized output format

This is designed for extensibility - new query types can be added
without modifying existing code.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID
from datetime import datetime, timedelta
from enum import Enum
import logging
from functools import reduce

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc, asc, case, cast, Float
from sqlalchemy.sql import text

from models import (
    Athlete, Activity, NutritionEntry, WorkPattern, 
    BodyComposition, ActivityFeedback, 
    TrainingPlan, PlannedWorkout, DailyCheckin
)

logger = logging.getLogger(__name__)


class QueryScope(str, Enum):
    """Who can run this query type"""
    SELF_ONLY = "self_only"           # Own data only
    TOP_TIER = "top_tier"             # Own data + advanced  
    ADMIN_ONLY = "admin_only"         # Cross-athlete aggregates


class AggregationType(str, Enum):
    """Available aggregation methods"""
    NONE = "none"
    AVG = "avg"
    SUM = "sum"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    STDDEV = "stddev"
    PERCENTILE = "percentile"


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


@dataclass
class QueryFilter:
    """A single filter condition"""
    field: str
    operator: str  # eq, ne, gt, gte, lt, lte, in, not_in, like, between
    value: Any
    
    def apply(self, query, model):
        """Apply filter to SQLAlchemy query"""
        column = getattr(model, self.field, None)
        if column is None:
            logger.warning(f"Unknown field: {self.field}")
            return query
            
        if self.operator == "eq":
            return query.filter(column == self.value)
        elif self.operator == "ne":
            return query.filter(column != self.value)
        elif self.operator == "gt":
            return query.filter(column > self.value)
        elif self.operator == "gte":
            return query.filter(column >= self.value)
        elif self.operator == "lt":
            return query.filter(column < self.value)
        elif self.operator == "lte":
            return query.filter(column <= self.value)
        elif self.operator == "in":
            return query.filter(column.in_(self.value))
        elif self.operator == "not_in":
            return query.filter(~column.in_(self.value))
        elif self.operator == "like":
            return query.filter(column.ilike(f"%{self.value}%"))
        elif self.operator == "between":
            if isinstance(self.value, (list, tuple)) and len(self.value) == 2:
                return query.filter(column.between(self.value[0], self.value[1]))
        elif self.operator == "is_null":
            return query.filter(column.is_(None)) if self.value else query.filter(column.isnot(None))
        
        return query


@dataclass
class QuerySpec:
    """Full specification for a query"""
    # What to query
    entity: str  # activity, nutrition, body_composition, correlation, etc.
    
    # Filters
    filters: List[QueryFilter] = field(default_factory=list)
    
    # Time range (convenience)
    days: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
    # Aggregation
    group_by: Optional[List[str]] = None
    aggregations: Optional[Dict[str, AggregationType]] = None
    
    # Selection
    fields: Optional[List[str]] = None  # Specific fields to return
    
    # Sorting
    sort_by: Optional[str] = None
    sort_order: SortOrder = SortOrder.DESC
    
    # Pagination
    limit: int = 100
    offset: int = 0
    
    # Scope
    athlete_id: Optional[UUID] = None  # None = cross-athlete (admin only)
    anonymize: bool = True  # For cross-athlete queries


@dataclass 
class QueryResult:
    """Standardized query result"""
    success: bool
    data: List[Dict[str, Any]]
    total_count: int
    query_type: str
    execution_time_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class QueryEngine:
    """
    Main query engine for data mining.
    
    Example usage:
        engine = QueryEngine(db)
        spec = QuerySpec(
            entity="activity",
            filters=[QueryFilter("workout_type", "eq", "tempo_run")],
            days=180,
            aggregations={"efficiency": AggregationType.AVG},
            group_by=["workout_type"]
        )
        result = engine.execute(spec, requesting_user, scope=QueryScope.ADMIN_ONLY)
    """
    
    # Entity to model mapping
    ENTITY_MODELS = {
        "activity": Activity,
        "nutrition": NutritionEntry,
        "body_composition": BodyComposition,
        "work_pattern": WorkPattern,
        "daily_checkin": DailyCheckin,
        "feedback": ActivityFeedback,
        "athlete": Athlete,
        "training_plan": TrainingPlan,
        "planned_workout": PlannedWorkout,
    }
    
    # Date field for each entity
    DATE_FIELDS = {
        "activity": "start_time",
        "nutrition": "date",
        "body_composition": "measured_at",
        "work_pattern": "date",
        "daily_checkin": "date",
        "feedback": "created_at",
        "athlete": "created_at",
        "training_plan": "created_at",
        "planned_workout": "scheduled_date",
    }
    
    def __init__(self, db: Session):
        self.db = db
    
    def execute(
        self, 
        spec: QuerySpec, 
        requesting_user: Athlete,
        scope: QueryScope = QueryScope.SELF_ONLY
    ) -> QueryResult:
        """Execute a query with proper access control"""
        import time
        start = time.time()
        
        try:
            # Access control
            if not self._check_access(requesting_user, spec, scope):
                return QueryResult(
                    success=False,
                    data=[],
                    total_count=0,
                    query_type=spec.entity,
                    execution_time_ms=0,
                    error="Access denied for this query scope"
                )
            
            # Get model
            model = self.ENTITY_MODELS.get(spec.entity)
            if not model:
                return QueryResult(
                    success=False,
                    data=[],
                    total_count=0,
                    query_type=spec.entity,
                    execution_time_ms=0,
                    error=f"Unknown entity: {spec.entity}"
                )
            
            # Build base query
            query = self.db.query(model)
            
            # Apply athlete filter for non-admin queries
            if scope != QueryScope.ADMIN_ONLY and hasattr(model, 'athlete_id'):
                query = query.filter(model.athlete_id == requesting_user.id)
            elif spec.athlete_id and hasattr(model, 'athlete_id'):
                query = query.filter(model.athlete_id == spec.athlete_id)
            
            # Apply time range
            query = self._apply_time_filter(query, model, spec)
            
            # Apply custom filters
            for f in spec.filters:
                query = f.apply(query, model)
            
            # Get total count before pagination
            total_count = query.count()
            
            # Apply aggregations if specified
            if spec.aggregations and spec.group_by:
                data = self._execute_aggregation(query, model, spec)
            else:
                # Apply sorting
                if spec.sort_by and hasattr(model, spec.sort_by):
                    sort_col = getattr(model, spec.sort_by)
                    query = query.order_by(desc(sort_col) if spec.sort_order == SortOrder.DESC else asc(sort_col))
                
                # Apply pagination
                query = query.offset(spec.offset).limit(spec.limit)
                
                # Execute and serialize
                rows = query.all()
                data = [self._serialize(row, spec.fields, spec.anonymize) for row in rows]
            
            execution_time = (time.time() - start) * 1000
            
            return QueryResult(
                success=True,
                data=data,
                total_count=total_count,
                query_type=spec.entity,
                execution_time_ms=round(execution_time, 2),
                metadata={
                    "scope": scope.value,
                    "filters_applied": len(spec.filters),
                    "aggregated": bool(spec.aggregations),
                }
            )
            
        except Exception as e:
            logger.error(f"Query execution error: {str(e)}", exc_info=True)
            return QueryResult(
                success=False,
                data=[],
                total_count=0,
                query_type=spec.entity,
                execution_time_ms=(time.time() - start) * 1000,
                error=str(e)
            )
    
    def _check_access(self, user: Athlete, spec: QuerySpec, scope: QueryScope) -> bool:
        """Verify user has access to requested query scope"""
        if scope == QueryScope.ADMIN_ONLY:
            return user.role in ('admin', 'owner')
        elif scope == QueryScope.TOP_TIER:
            return user.role in ('admin', 'owner') or user.subscription_tier in ('premium', 'pro', 'elite')
        return True  # SELF_ONLY is always allowed
    
    def _apply_time_filter(self, query, model, spec: QuerySpec):
        """Apply time-based filtering"""
        date_field = self.DATE_FIELDS.get(spec.entity)
        if not date_field or not hasattr(model, date_field):
            return query
        
        col = getattr(model, date_field)
        
        if spec.days:
            cutoff = datetime.now() - timedelta(days=spec.days)
            query = query.filter(col >= cutoff)
        elif spec.start_date:
            query = query.filter(col >= spec.start_date)
            if spec.end_date:
                query = query.filter(col <= spec.end_date)
        
        return query
    
    def _execute_aggregation(self, query, model, spec: QuerySpec) -> List[Dict]:
        """Execute aggregation query"""
        select_cols = []
        
        # Group by columns
        for gb in spec.group_by or []:
            if hasattr(model, gb):
                select_cols.append(getattr(model, gb).label(gb))
        
        # Aggregation columns
        for field_name, agg_type in (spec.aggregations or {}).items():
            if hasattr(model, field_name):
                col = getattr(model, field_name)
                if agg_type == AggregationType.AVG:
                    select_cols.append(func.avg(cast(col, Float)).label(f"avg_{field_name}"))
                elif agg_type == AggregationType.SUM:
                    select_cols.append(func.sum(col).label(f"sum_{field_name}"))
                elif agg_type == AggregationType.MIN:
                    select_cols.append(func.min(col).label(f"min_{field_name}"))
                elif agg_type == AggregationType.MAX:
                    select_cols.append(func.max(col).label(f"max_{field_name}"))
                elif agg_type == AggregationType.COUNT:
                    select_cols.append(func.count(col).label(f"count_{field_name}"))
                elif agg_type == AggregationType.STDDEV:
                    select_cols.append(func.stddev(cast(col, Float)).label(f"stddev_{field_name}"))
        
        # Add count
        select_cols.append(func.count().label("record_count"))
        
        # Build aggregation query
        agg_query = self.db.query(*select_cols)
        
        # Apply filters from base query (replicate the filter conditions)
        # Note: This is simplified - in production you'd want to pass the filtered subquery
        if hasattr(model, 'athlete_id') and spec.athlete_id:
            agg_query = agg_query.filter(model.athlete_id == spec.athlete_id)
        
        # Time filter
        agg_query = self._apply_time_filter(agg_query, model, spec)
        
        # Apply custom filters
        for f in spec.filters:
            agg_query = f.apply(agg_query, model)
        
        # Group by
        group_cols = [getattr(model, gb) for gb in (spec.group_by or []) if hasattr(model, gb)]
        if group_cols:
            agg_query = agg_query.group_by(*group_cols)
        
        # Execute
        results = agg_query.all()
        
        # Convert to dicts
        data = []
        for row in results:
            row_dict = {}
            for i, col in enumerate(select_cols):
                key = col.key if hasattr(col, 'key') else f"col_{i}"
                value = row[i]
                if isinstance(value, float):
                    value = round(value, 4)
                row_dict[key] = value
            data.append(row_dict)
        
        return data
    
    def _serialize(self, obj, fields: Optional[List[str]], anonymize: bool) -> Dict:
        """Serialize a model object to dict"""
        if fields:
            return {f: getattr(obj, f, None) for f in fields if hasattr(obj, f)}
        
        # Default serialization
        result = {}
        for col in obj.__table__.columns:
            value = getattr(obj, col.name)
            
            # Handle special types
            if isinstance(value, datetime):
                value = value.isoformat()
            elif isinstance(value, UUID):
                if anonymize and col.name in ('athlete_id', 'id'):
                    value = "***"  # Anonymize IDs
                else:
                    value = str(value)
            
            # Skip sensitive fields if anonymizing
            if anonymize and col.name in ('email', 'password_hash', 'strava_access_token', 'strava_refresh_token'):
                continue
            
            result[col.name] = value
        
        return result


# Pre-built query templates for common operations
class QueryTemplates:
    """
    Pre-built query templates for common data mining tasks.
    These are the "guided queries" for athletes and power queries for admins.
    """
    
    @staticmethod
    def efficiency_by_workout_type(
        athlete_id: Optional[UUID] = None,
        days: int = 180
    ) -> QuerySpec:
        """Average efficiency by workout type"""
        return QuerySpec(
            entity="activity",
            days=days,
            athlete_id=athlete_id,
            filters=[
                QueryFilter("workout_type", "is_null", False),
                QueryFilter("efficiency", "is_null", False),
            ],
            group_by=["workout_type"],
            aggregations={
                "efficiency": AggregationType.AVG,
                "average_heartrate": AggregationType.AVG,
            }
        )
    
    @staticmethod
    def performance_over_time(
        athlete_id: UUID,
        workout_type: Optional[str] = None,
        days: int = 365
    ) -> QuerySpec:
        """Track performance metrics over time"""
        filters = []
        if workout_type:
            filters.append(QueryFilter("workout_type", "eq", workout_type))
        
        return QuerySpec(
            entity="activity",
            days=days,
            athlete_id=athlete_id,
            filters=filters,
            fields=["start_time", "distance_m", "duration_s", "efficiency", "intensity_score", "workout_type"],
            sort_by="start_time",
            sort_order=SortOrder.ASC,
            limit=500,
        )
    
    @staticmethod
    def nutrition_correlation(
        athlete_id: UUID,
        days: int = 90
    ) -> QuerySpec:
        """Nutrition entries for correlation analysis"""
        return QuerySpec(
            entity="nutrition",
            days=days,
            athlete_id=athlete_id,
            fields=["date", "total_calories", "protein_g", "carbs_g", "fat_g", "hydration_ml", "pre_run_fuel_quality"],
            sort_by="date",
            limit=500,
        )
    
    @staticmethod
    def body_composition_trend(
        athlete_id: UUID,
        days: int = 365
    ) -> QuerySpec:
        """Body composition over time"""
        return QuerySpec(
            entity="body_composition",
            days=days,
            athlete_id=athlete_id,
            fields=["measured_at", "weight_kg", "body_fat_pct", "bmi"],
            sort_by="measured_at",
            limit=500,
        )
    
    @staticmethod
    def cross_athlete_efficiency_distribution(days: int = 180) -> QuerySpec:
        """
        Admin only: Distribution of efficiency scores across all athletes.
        Useful for benchmarking and understanding population patterns.
        """
        return QuerySpec(
            entity="activity",
            days=days,
            athlete_id=None,  # Cross-athlete
            filters=[
                QueryFilter("efficiency", "is_null", False),
                QueryFilter("efficiency", "gt", 0),
            ],
            group_by=["workout_type"],
            aggregations={
                "efficiency": AggregationType.AVG,
            },
            anonymize=True,
        )
    
    @staticmethod
    def workout_type_distribution(days: int = 90) -> QuerySpec:
        """Admin only: What workout types are athletes doing?"""
        return QuerySpec(
            entity="activity",
            days=days,
            athlete_id=None,
            filters=[
                QueryFilter("workout_type", "is_null", False),
            ],
            group_by=["workout_type"],
            aggregations={
                "id": AggregationType.COUNT,
            },
            anonymize=True,
        )
    
    @staticmethod
    def correlation_patterns(min_strength: float = 0.3) -> QuerySpec:
        """Admin only: What correlations are we finding across athletes?"""
        return QuerySpec(
            entity="correlation",
            filters=[
                QueryFilter("strength", "gte", min_strength),
                QueryFilter("is_significant", "eq", True),
            ],
            group_by=["factor", "outcome"],
            aggregations={
                "strength": AggregationType.AVG,
            },
            sort_by="strength",
            anonymize=True,
        )
