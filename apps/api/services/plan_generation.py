"""
Plan Generation Service - Hybrid Approach

Implements Grok's recommended hybrid approach:
1. Extract template plans from knowledge base
2. Modify templates using principles from other methodologies
3. Validate plan coherence before delivery

ARCHITECTURE:
- Template-based generation (80% template, 20% principle-modded in v1)
- Phase-aware blending (base → build → sharpen → taper)
- Validation checks (load balance, intensity distribution, recovery spacing)
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import json
import logging

from services.blending_heuristics import determine_methodology_blend, get_blending_rationale

# Import query_knowledge_base directly to avoid circular import
from core.database import get_db_sync
from models import CoachingKnowledgeEntry
from sqlalchemy import or_
import json

logger = logging.getLogger(__name__)


def query_knowledge_base_internal(
    tags: Optional[List[str]] = None,
    methodology: Optional[str] = None,
    principle_type: Optional[str] = None,
    concept: Optional[str] = None,
    limit: int = 20,
    db_session = None
) -> List[Dict]:
    """Internal query function to avoid circular imports."""
    if db_session is None:
        db = get_db_sync()
        should_close = True
    else:
        db = db_session
        should_close = False
    
    try:
        query = db.query(CoachingKnowledgeEntry)
        
        if tags:
            for tag in tags:
                query = query.filter(CoachingKnowledgeEntry.tags.contains([tag]))
        
        if methodology:
            query = query.filter(CoachingKnowledgeEntry.methodology.ilike(f"%{methodology}%"))
        
        if principle_type:
            query = query.filter(CoachingKnowledgeEntry.principle_type == principle_type)
        
        if concept:
            query = query.filter(
                or_(
                    CoachingKnowledgeEntry.text_chunk.ilike(f"%{concept}%"),
                    CoachingKnowledgeEntry.source.ilike(f"%{concept}%")
                )
            )
        
        entries = query.limit(limit).all()
        
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
                "text_chunk": entry.text_chunk[:1000] if entry.text_chunk else None,
                "extracted_principles": json.loads(entry.extracted_principles) if entry.extracted_principles else None,
                "created_at": entry.created_at.isoformat() if entry.created_at else None
            })
        
        return results
    finally:
        if should_close:
            db.close()


def extract_template_plan(
    goal_distance: str,
    methodology: str,
    duration_weeks: int = 12,
    db_session = None
) -> Optional[Dict]:
    """
    Extract a template training plan from knowledge base.
    
    Args:
        goal_distance: Target race distance (e.g., "5K", "Marathon")
        methodology: Methodology name (e.g., "Daniels", "Pfitzinger")
        duration_weeks: Desired plan duration in weeks
        db_session: Database session
        
    Returns:
        Template plan dictionary or None if not found
    """
    # Query for training plans matching criteria
    plans = query_knowledge_base_internal(
        principle_type="training_plan",
        methodology=methodology,
        concept=goal_distance.lower(),
        limit=5,
        db_session=db_session
    )
    
    if not plans:
        logger.warning(f"No template plans found for {methodology} {goal_distance}")
        return None
    
    # Select best matching plan (prefer plans with matching duration)
    # For now, return first match (can be enhanced with duration matching)
    plan_entry = plans[0]
    
    # Parse extracted principles if available
    principles = plan_entry.get("extracted_principles")
    if principles and isinstance(principles, dict):
        # Extract plan structure from principles
        return {
            "source": plan_entry["source"],
            "methodology": plan_entry["methodology"],
            "weeks": principles.get("weeks", []),
            "total_weeks": principles.get("total_weeks", duration_weeks),
            "phases": principles.get("phases", []),
            "workout_types": principles.get("workout_types", []),
            "text_chunk": plan_entry.get("text_chunk", "")
        }
    
    # Fallback: parse from text_chunk if principles not structured
    return {
        "source": plan_entry["source"],
        "methodology": plan_entry["methodology"],
        "weeks": [],
        "total_weeks": duration_weeks,
        "phases": [],
        "workout_types": [],
        "text_chunk": plan_entry.get("text_chunk", "")
    }


def get_phase_tags(phase: str) -> List[str]:
    """
    Get relevant tags for a training phase.
    
    Args:
        phase: Training phase (base, build, sharpen, taper)
        
    Returns:
        List of relevant tags for querying principles
    """
    phase_tag_map = {
        "base": ["aerobic", "easy_run", "long_run", "base_building"],
        "build": ["threshold", "tempo", "long_run", "volume"],
        "sharpen": ["vo2max", "interval", "speed", "race_pace"],
        "taper": ["recovery", "race_pace", "taper", "sharpening"]
    }
    return phase_tag_map.get(phase.lower(), ["threshold", "long_run"])


def inject_principles_into_plan(
    template_plan: Dict,
    phase: str,
    methodologies: Dict[str, float],
    diagnostic_signals: Dict,
    athlete_profile: Dict,
    db_session = None
) -> Dict:
    """
    Inject principles from blended methodologies into template plan.
    
    Args:
        template_plan: Template plan structure
        phase: Current training phase
        methodologies: Methodology blend percentages
        diagnostic_signals: Current diagnostic signals
        athlete_profile: Athlete characteristics
        db_session: Database session
        
    Returns:
        Modified plan with principles injected
    """
    modified_plan = template_plan.copy()
    
    # Get phase-specific tags
    phase_tags = get_phase_tags(phase)
    
    # Query principles from blended methodologies
    all_principles = []
    for methodology, weight in methodologies.items():
        if weight > 0.1:  # Only query significant methodologies
            principles = query_knowledge_base_internal(
                tags=phase_tags,
                methodology=methodology,
                principle_type="periodization",  # Or "workout", "general"
                limit=int(5 * weight),
                db_session=db_session
            )
            all_principles.extend(principles)
    
    # Apply modifications based on principles and profile
    modifications = []
    
    # Example: If injury history, reduce intensity
    if athlete_profile.get("injury_history") in ["frequent", "recent"]:
        modifications.append({
            "type": "reduce_intensity",
            "reason": "Injury history requires lower-intensity approach"
        })
    
    # Example: If efficiency declining, add recovery
    if diagnostic_signals.get("efficiency_trend", 0) < -0.02:
        modifications.append({
            "type": "add_recovery",
            "reason": "Declining efficiency requires recovery focus"
        })
    
    # Store modifications in plan metadata
    modified_plan["modifications"] = modifications
    modified_plan["principles_used"] = [p["id"] for p in all_principles]
    
    return modified_plan


def validate_plan_coherence(plan: Dict) -> Tuple[bool, List[str]]:
    """
    Validate plan coherence and safety.
    
    Args:
        plan: Generated plan dictionary
        
    Returns:
        Tuple of (is_valid, list_of_warnings)
    """
    warnings = []
    
    # Check 1: Volume progression (should ramp 5-10% per week)
    weeks = plan.get("plan", {}).get("weeks", [])
    if len(weeks) > 1:
        volumes = []
        for week in weeks:
            # Extract volume from week structure (placeholder logic)
            volume = week.get("total_mileage", 0) or week.get("volume", 0)
            if volume:
                volumes.append(volume)
        
        if len(volumes) > 1:
            for i in range(1, len(volumes)):
                if volumes[i] > 0 and volumes[i-1] > 0:
                    increase_pct = (volumes[i] - volumes[i-1]) / volumes[i-1]
                    if increase_pct > 0.15:  # >15% increase
                        warnings.append(f"Week {i+1} volume increase ({increase_pct*100:.1f}%) exceeds safe 10-15% guideline")
                    elif increase_pct < -0.2:  # >20% decrease
                        warnings.append(f"Week {i+1} volume decrease ({increase_pct*100:.1f}%) is very large")
    
    # Check 2: Intensity balance (should be ~20% quality sessions)
    quality_workouts = ["threshold", "tempo", "interval", "vo2max", "speed", "repetition"]
    total_workouts = 0
    quality_count = 0
    
    for week in weeks:
        week_workouts = week.get("workouts", [])
        total_workouts += len(week_workouts)
        for workout in week_workouts:
            workout_type = str(workout.get("workout_type", "")).lower()
            if any(q in workout_type for q in quality_workouts):
                quality_count += 1
    
    if total_workouts > 0:
        quality_pct = (quality_count / total_workouts) * 100
        if quality_pct > 30:
            warnings.append(f"Intensity too high: {quality_pct:.1f}% quality sessions (target: 15-25%)")
        elif quality_pct < 10:
            warnings.append(f"Intensity too low: {quality_pct:.1f}% quality sessions (target: 15-25%)")
    
    # Check 3: Recovery spacing (no back-to-back hard days unless Hansons-influenced)
    # Hard days are threshold, tempo, interval, vo2max, speed work
    hard_day_types = ["threshold", "tempo", "interval", "vo2max", "speed", "repetition", "race"]
    
    for week in weeks:
        workouts = week.get("workouts", [])
        for i in range(len(workouts) - 1):
            current_type = str(workouts[i].get("workout_type", "")).lower()
            next_type = str(workouts[i+1].get("workout_type", "")).lower()
            
            current_is_hard = any(h in current_type for h in hard_day_types)
            next_is_hard = any(h in next_type for h in hard_day_types)
            
            if current_is_hard and next_is_hard:
                # Check if plan explicitly allows this (e.g., Hansons cumulative fatigue)
                week_num = week.get("week", "unknown")
                warnings.append(
                    f"Week {week_num}: Back-to-back hard days detected "
                    f"({workouts[i].get('workout_type', 'unknown')} → {workouts[i+1].get('workout_type', 'unknown')}). "
                    f"Ensure adequate recovery unless using cumulative fatigue approach."
                )
    
    # Check 4: Acute:chronic load ratio (<1.5)
    # Calculate rolling 4-week averages
    volumes = []
    for week in weeks:
        volume = week.get("total_mileage", 0) or week.get("volume", 0) or week.get("distance", 0)
        if volume:
            volumes.append(float(volume))
    
    if len(volumes) >= 4:
        # Acute load = last week
        # Chronic load = average of last 4 weeks
        acute_load = volumes[-1]
        chronic_load = sum(volumes[-4:]) / 4
        
        if chronic_load > 0:
            load_ratio = acute_load / chronic_load
            if load_ratio > 1.5:
                warnings.append(
                    f"Acute:chronic load ratio ({load_ratio:.2f}) exceeds safe threshold (1.5). "
                    f"Risk of overtraining."
                )
            elif load_ratio < 0.5:
                warnings.append(
                    f"Acute:chronic load ratio ({load_ratio:.2f}) is very low (<0.5). "
                    f"May indicate insufficient training stimulus."
                )
    
    # Check 5: Taper integrity (final 2-3 weeks must show volume drop)
    if len(volumes) >= 3:
        final_3_weeks = volumes[-3:]
        peak_volume = max(volumes[:-2]) if len(volumes) > 2 else max(volumes)
        
        if peak_volume > 0:
            taper_volume = final_3_weeks[-1]  # Last week
            volume_drop_pct = ((peak_volume - taper_volume) / peak_volume) * 100
            
            if volume_drop_pct < 20:
                warnings.append(
                    f"Taper volume drop ({volume_drop_pct:.1f}%) is insufficient. "
                    f"Target: 20-50% reduction in final weeks."
                )
            elif volume_drop_pct > 60:
                warnings.append(
                    f"Taper volume drop ({volume_drop_pct:.1f}%) is very large (>60%). "
                    f"May be too aggressive."
                )
    
    is_valid = len(warnings) == 0 or all("exceeds" not in w.lower() for w in warnings)
    
    return is_valid, warnings


def generate_hybrid_plan(
    athlete_id: str,
    goal_distance: str,
    current_fitness: Dict,
    diagnostic_signals: Dict,
    athlete_profile: Dict,
    duration_weeks: int = 12,
    weeks_to_race: Optional[int] = None,
    db_session = None
) -> Dict:
    """
    Generate a hybrid training plan using template + principles approach.
    
    Since templates are unstructured, this now uses principle-based generation
    with flexible duration support (4-18 weeks).
    
    Args:
        athlete_id: Athlete ID
        goal_distance: Target race distance
        current_fitness: Current fitness metrics
        diagnostic_signals: Diagnostic signals
        athlete_profile: Athlete characteristics
        duration_weeks: Plan duration in weeks (legacy param)
        weeks_to_race: Weeks until goal race (4-18, overrides duration_weeks)
        db_session: Database session
        
    Returns:
        Generated training plan (client-facing, methodology stripped)
    """
    # Use principle-based generation (templates are unstructured)
    from services.principle_plan_generator import generate_principle_based_plan
    
    # Use weeks_to_race if provided, otherwise duration_weeks
    effective_weeks = weeks_to_race if weeks_to_race else duration_weeks
    
    return generate_principle_based_plan(
        athlete_id=athlete_id,
        goal_distance=goal_distance,
        current_fitness=current_fitness,
        diagnostic_signals=diagnostic_signals,
        athlete_profile=athlete_profile,
        weeks_to_race=effective_weeks,
        db_session=db_session
    )
    # Step 1: Determine methodology blend
    methodologies = determine_methodology_blend(
        diagnostic_signals=diagnostic_signals,
        athlete_profile=athlete_profile
    )
    
    # Step 2: Select primary methodology for template
    primary_methodology = max(methodologies.items(), key=lambda x: x[1])[0]
    
    # Step 3: Extract template plan
    template_plan = extract_template_plan(
        goal_distance=goal_distance,
        methodology=primary_methodology,
        duration_weeks=duration_weeks,
        db_session=db_session
    )
    
    if not template_plan:
        logger.warning(f"No template found for {primary_methodology}, falling back to principle-only generation")
        # Fallback: Generate from principles only (future implementation)
        template_plan = {
            "source": "Generated from principles",
            "methodology": primary_methodology,
            "weeks": [],
            "total_weeks": duration_weeks,
            "phases": ["base", "build", "sharpen", "taper"]
        }
    
    # Step 4: Inject principles from blended methodologies
    # For now, inject into base phase (can be extended to all phases)
    modified_plan = inject_principles_into_plan(
        template_plan=template_plan,
        phase="base",
        methodologies=methodologies,
        diagnostic_signals=diagnostic_signals,
        athlete_profile=athlete_profile,
        db_session=db_session
    )
    
    # Step 5: Generate blending rationale
    blending_rationale = get_blending_rationale(
        blend=methodologies,
        diagnostic_signals=diagnostic_signals,
        athlete_profile=athlete_profile
    )
    
    # Step 6: Validate plan
    is_valid, warnings = validate_plan_coherence(modified_plan)
    
    # Step 7: Structure plan response
    internal_plan = {
        "athlete_id": athlete_id,
        "goal_distance": goal_distance,
        "generated_at": datetime.now().isoformat(),
        "plan": {
            "weeks": modified_plan.get("weeks", []),
            "total_weeks": modified_plan.get("total_weeks", duration_weeks),
            "phases": modified_plan.get("phases", []),
            "template_source": modified_plan.get("source"),
            "modifications": modified_plan.get("modifications", []),
            "validation": {
                "is_valid": is_valid,
                "warnings": warnings
            }
        },
        "rationale": f"Hybrid plan generated using {primary_methodology} template with principles from blended methodologies",
        "_internal": {
            "blending_rationale": blending_rationale,
            "methodologies_used": methodologies,
            "template_methodology": primary_methodology,
            "principles_used": modified_plan.get("principles_used", [])
        }
    }
    
    # Step 8: Translate to client-facing (strip methodology references)
    # Import here to avoid circular import
    from services.ai_coaching_engine import translate_recommendation_for_client
    client_facing = translate_recommendation_for_client(internal_plan)
    
    return client_facing

