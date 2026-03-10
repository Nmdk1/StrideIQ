"""
AI Coaching Engine

Generates personalized coaching recommendations by synthesizing:
1. Knowledge base (coaching principles from books)
2. Diagnostic signals (efficiency trends, load mapping, recovery)
3. Athlete's personal data and history

ARCHITECTURE: Methodology Opacity
- Internal: Uses methodology tags (Daniels, Pfitzinger, etc.) for knowledge base queries
- Client-facing: Translates to neutral physiological terms (threshold pace, VO₂max intervals, etc.)
- Blending: Tracks methodology blends internally but never exposes to clients
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
import json

from services.neutral_terminology import (
    translate_to_neutral,
    strip_methodology_references,
    format_workout_description
)
from services.blending_heuristics import (
    determine_methodology_blend,
    get_blending_rationale
)
from services.plan_generation import generate_hybrid_plan

logger = logging.getLogger(__name__)


def query_knowledge_base(
    tags: Optional[List[str]] = None,
    methodology: Optional[str] = None,
    principle_type: Optional[str] = None,
    concept: Optional[str] = None,
    limit: int = 20,
    db_session = None
) -> List[Dict]:
    """
    Query knowledge base for relevant coaching principles.
    
    Args:
        tags: List of tags to filter by (e.g., ["threshold", "long_run"])
        methodology: Optional filter by methodology (e.g., "Daniels")
        principle_type: Optional filter by principle type (e.g., "periodization")
        concept: Optional text search concept
        limit: Maximum number of results (default: 20)
        db_session: Database session (if None, will create one)
        
    Returns:
        List of relevant principles from knowledge base
    """
    from core.database import get_db_sync
    from models import CoachingKnowledgeEntry
    from sqlalchemy import or_
    import json
    
    # Get database session
    if db_session is None:
        db = get_db_sync()
        should_close = True
    else:
        db = db_session
        should_close = False
    
    try:
        query = db.query(CoachingKnowledgeEntry)
        
        # Filter by tags (JSONB containment)
        if tags:
            for tag in tags:
                # PostgreSQL JSONB: tags @> '["tag"]'
                query = query.filter(CoachingKnowledgeEntry.tags.contains([tag]))
        
        # Filter by methodology
        if methodology:
            query = query.filter(CoachingKnowledgeEntry.methodology.ilike(f"%{methodology}%"))
        
        # Filter by principle type
        if principle_type:
            query = query.filter(CoachingKnowledgeEntry.principle_type == principle_type)
        
        # Search by concept (text search)
        if concept:
            query = query.filter(
                or_(
                    CoachingKnowledgeEntry.text_chunk.ilike(f"%{concept}%"),
                    CoachingKnowledgeEntry.source.ilike(f"%{concept}%")
                )
            )
        
        entries = query.limit(limit).all()
        
        # Convert to dictionaries
        results = []
        for entry in entries:
            tags_list = entry.tags if isinstance(entry.tags, list) else json.loads(entry.tags) if entry.tags else []
            
            results.append({
                "id": str(entry.id),
                "source": entry.source,
                "methodology": entry.methodology,
                "source_type": entry.source_type,
                "principle_type": entry.principle_type,
                "tags": tags_list,
                "text_chunk": entry.text_chunk[:1000] if entry.text_chunk else None,  # Limit text length
                "extracted_principles": json.loads(entry.extracted_principles) if entry.extracted_principles else None,
                "created_at": entry.created_at.isoformat() if entry.created_at else None
            })
        
        return results
    
    finally:
        if should_close:
            db.close()


def generate_training_plan(
    athlete_id: str,
    goal_distance: str,
    current_fitness: Dict,
    diagnostic_signals: Dict,
    athlete_profile: Dict,
    policy: str = "Performance Maximal",
    weeks_to_race: Optional[int] = None,
    db_session = None
) -> Dict:
    """
    Generate AI-powered training plan.
    
    Args:
        athlete_id: Athlete ID
        goal_distance: Target race distance (e.g., "5K", "Marathon")
        current_fitness: Current fitness metrics (RPI, recent race times, etc.)
        diagnostic_signals: Efficiency trends, load mapping, recovery elasticity
        athlete_profile: Athlete characteristics (volume_tolerance, speed_background, injury_history)
        policy: Coaching policy (Performance Maximal, Durability First, Re-Entry)
        weeks_to_race: Weeks until goal race (4-18, enables abbreviated builds)
        db_session: Database session (optional)
        
    Returns:
        Training plan dictionary with workouts, periodization, etc.
        CLIENT-FACING: All methodology references are stripped, neutral terminology used
    """
    # Generate hybrid plan (principle-based with flexible duration)
    client_facing = generate_hybrid_plan(
        athlete_id=athlete_id,
        goal_distance=goal_distance,
        current_fitness=current_fitness,
        diagnostic_signals=diagnostic_signals,
        athlete_profile=athlete_profile,
        duration_weeks=12,  # Default fallback
        weeks_to_race=weeks_to_race,  # Supports abbreviated builds
        db_session=db_session
    )
    
    return client_facing


def translate_recommendation_for_client(internal_recommendation: Dict) -> Dict:
    """
    Translate internal recommendation (with methodology references) to client-facing format.
    
    This is the critical translation layer that ensures methodology opacity.
    
    Args:
        internal_recommendation: Internal recommendation with methodology tags
        
    Returns:
        Client-facing recommendation with neutral terminology only
    """
    client_facing = {}
    
    # Copy non-methodology fields
    for key, value in internal_recommendation.items():
        if key.startswith("_internal"):
            continue  # Skip internal fields
        
        if isinstance(value, str):
            # Strip methodology references from text
            client_facing[key] = strip_methodology_references(value)
        elif isinstance(value, dict):
            # Recursively translate nested dictionaries
            client_facing[key] = translate_recommendation_for_client(value)
        elif isinstance(value, list):
            # Translate list items
            client_facing[key] = [
                translate_recommendation_for_client(item) if isinstance(item, dict)
                else strip_methodology_references(item) if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            client_facing[key] = value
    
    # Recursively strip methodology from ALL text fields
    def strip_all_text_fields(obj):
        """Recursively strip methodology references from all string fields."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, str):
                    obj[key] = strip_methodology_references(value)
                elif isinstance(value, dict):
                    strip_all_text_fields(value)
                elif isinstance(value, list):
                    strip_all_text_fields(value)
        elif isinstance(obj, list):
            for item in obj:
                strip_all_text_fields(item)
    
    # Translate workout types to neutral terminology
    def translate_workouts(obj):
        """Recursively find and translate workouts."""
        if isinstance(obj, dict):
            if "workouts" in obj:
                for workout in obj["workouts"]:
                    if isinstance(workout, dict):
                        if "workout_type" in workout:
                            neutral = translate_to_neutral(workout["workout_type"], workout.get("methodology"))
                            workout["workout_type"] = neutral["neutral"]
                            # Update description if it exists, otherwise add neutral description
                            if "description" in workout:
                                workout["description"] = strip_methodology_references(workout["description"])
                            else:
                                workout["description"] = neutral.get("description", "")
                            workout["effort"] = neutral.get("effort", "")
                            # Remove methodology field
                            workout.pop("methodology", None)
            # Recursively process nested structures
            for k, v in obj.items():
                if k != "workouts":  # Already processed
                    translate_workouts(v)
        elif isinstance(obj, list):
            for item in obj:
                translate_workouts(item)
    
    # First translate workouts, then strip all text fields
    translate_workouts(client_facing)
    strip_all_text_fields(client_facing)
    
    # Add alternation explanation if applied (Tier 3/4 subscription)
    if internal_recommendation.get("plan", {}).get("alternation_applied"):
        alternation_rationale = internal_recommendation.get("plan", {}).get("alternation_rationale")
        if alternation_rationale:
            # Add explanation to plan metadata
            if "plan" in client_facing:
                if "explanation" not in client_facing["plan"]:
                    client_facing["plan"]["explanation"] = ""
                client_facing["plan"]["explanation"] += f"\n\nAlternating focus pattern: {alternation_rationale}. Your plan alternates between threshold-focused weeks (lactate clearance) and interval-focused weeks (VO2max/speed), with marathon-pace long runs every 3rd week. This pattern supports deeper adaptation and sustainability at high mileage."
    
    return client_facing


def generate_weekly_guidance(
    athlete_id: str,
    current_phase: str,
    diagnostic_signals: Dict,
    recent_activities: List[Dict],
    methodologies_used: Optional[Dict[str, float]] = None
) -> Dict:
    """
    Generate weekly coaching guidance.
    
    Args:
        athlete_id: Athlete ID
        current_phase: Current training phase (base, sharpening, peaking, etc.)
        diagnostic_signals: Current diagnostic signals
        recent_activities: Recent activity history
        methodologies_used: Internal tracking of methodology blend
        
    Returns:
        Weekly guidance with workout recommendations (CLIENT-FACING: neutral terminology)
    """
    # TODO: Implement weekly guidance generation
    # 1. Query knowledge base for phase-specific principles
    # 2. Synthesize with diagnostic signals
    # 3. Generate personalized workouts
    # 4. Translate to neutral terminology
    
    blending_rationale = None
    if methodologies_used:
        blending_rationale = {
            "methodologies": methodologies_used,
            "phase": current_phase,
            "reason": f"Blended methodologies based on {current_phase} phase and diagnostic signals"
        }
    
    return {
        "athlete_id": athlete_id,
        "week_start": datetime.now().isoformat(),
        "guidance": {},
        "workouts": [],
        # Internal only - not exposed to clients
        "_internal": {
            "blending_rationale": blending_rationale,
            "methodologies_used": methodologies_used
        }
    }


def personalize_coaching_principle(
    principle: Dict,
    diagnostic_signals: Dict
) -> Dict:
    """
    Personalize a coaching principle based on diagnostic signals.
    
    INTERNAL: Tracks methodology source for blending rationale
    CLIENT-FACING: Returns neutral terminology only
    
    Example (internal):
        Principle: "Daniels suggests 48h between hard sessions"
        Diagnostic: Recovery elasticity = 72h
        Internal Result: {"methodology": "Daniels", "original": "48h", "adjusted": "72h"}
        
    Example (client-facing):
        "Space hard sessions 72h apart based on your recovery profile"
        
    Args:
        principle: Coaching principle from knowledge base (may contain methodology tags)
        diagnostic_signals: Athlete's diagnostic signals
        
    Returns:
        Personalized principle (CLIENT-FACING: neutral terminology)
    """
    # TODO: Implement personalization logic
    # Map diagnostic signals to principle adjustments
    
    # Extract methodology for internal tracking
    methodology = principle.get("methodology")
    
    # Personalize based on diagnostic signals
    personalized = principle.copy()
    adjustments = []
    rationale = ""
    
    # Example: Adjust recovery time based on recovery_half_life_hours
    if "recovery" in principle.get("principle_type", "").lower():
        recovery_half_life = diagnostic_signals.get("recovery_half_life_hours")
        if recovery_half_life:
            # Adjust recovery recommendations based on personal recovery profile
            adjustments.append(f"Recovery time adjusted to {recovery_half_life:.1f}h based on your recovery profile")
            rationale = f"Your recovery profile indicates {recovery_half_life:.1f}h recovery time"
    
    # Translate to neutral terminology for client-facing output
    client_facing = {
        "personalized": strip_methodology_references(str(personalized.get("text", ""))),
        "adjustments": [strip_methodology_references(adj) for adj in adjustments],
        "rationale": strip_methodology_references(rationale) if rationale else ""
    }
    
    # Internal tracking (not exposed to clients)
    return {
        **client_facing,
        "_internal": {
            "original_principle": principle,
            "methodology": methodology,
            "adjustments_made": adjustments
        }
    }

