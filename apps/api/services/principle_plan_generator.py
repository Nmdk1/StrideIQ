"""
Principle-Based Plan Generator

Generates training plans by synthesizing principles from the knowledge base.
Supports flexible durations (4-18 weeks) with abbreviated builds.

ARCHITECTURE:
- Modular phase allocation (base/build/sharpen/taper)
- Dynamic duration based on weeks_to_race
- Principle synthesis from KB queries
- VDOT-based workout prescriptions
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
import math

from services.plan_generation import (
    query_knowledge_base_internal,
    get_phase_tags,
    validate_plan_coherence
)
from services.blending_heuristics import determine_methodology_blend, get_blending_rationale
from services.vdot_calculator import calculate_training_paces, calculate_vdot_from_race_time
from services.neutral_terminology import format_workout_description

logger = logging.getLogger(__name__)


def allocate_phases(weeks_to_race: int, current_base_mileage: float = 0) -> Dict[str, int]:
    """
    Allocate weeks across training phases based on time available.
    
    Args:
        weeks_to_race: Total weeks until goal race
        current_base_mileage: Current weekly mileage (helps determine if base needed)
        
    Returns:
        Dictionary mapping phase names to week counts
        Example: {"base": 4, "build": 6, "sharpen": 3, "taper": 2}
    """
    allocation = {"base": 0, "build": 0, "sharpen": 0, "taper": 0}
    
    # Taper is always included, scaled to race distance
    # For now, use 2 weeks as default (can be parameterized by distance)
    taper_weeks = 2
    if weeks_to_race >= 18:
        taper_weeks = 3  # Longer taper for marathon
    elif weeks_to_race <= 6:
        taper_weeks = 1  # Shorter taper for shorter plans
    
    allocation["taper"] = taper_weeks
    remaining_weeks = weeks_to_race - taper_weeks
    
    # Ultra-short plans (4-6 weeks): Mostly sharpen + minimal build
    if weeks_to_race <= 6:
        allocation["sharpen"] = max(2, remaining_weeks - 1)
        allocation["build"] = remaining_weeks - allocation["sharpen"]
        return allocation
    
    # Short plans (7-10 weeks): Compress phases, prioritize specificity
    if weeks_to_race <= 10:
        allocation["sharpen"] = 3
        allocation["build"] = remaining_weeks - allocation["sharpen"]
        # Minimal base if already high mileage
        if current_base_mileage < 30:
            allocation["base"] = 1
            allocation["build"] -= 1
        return allocation
    
    # Medium plans (11-14 weeks): Balanced phases
    if weeks_to_race <= 14:
        allocation["sharpen"] = 3
        allocation["build"] = 6
        remaining_after_build = remaining_weeks - allocation["build"] - allocation["sharpen"]
        allocation["base"] = max(0, remaining_after_build)
        return allocation
    
    # Full plans (15-18 weeks): Full base emphasis
    allocation["sharpen"] = 3
    allocation["build"] = 6
    allocation["base"] = remaining_weeks - allocation["build"] - allocation["sharpen"]
    
    return allocation


def generate_weekly_skeleton(phase: str, week_num: int, total_weeks: int) -> Dict:
    """
    Generate weekly skeleton structure with workout slots.
    
    Args:
        phase: Current training phase
        week_num: Week number in plan
        total_weeks: Total plan duration
        
    Returns:
        Week structure with workout slots
    """
    # Base structure: 7 days with slots
    days = []
    
    # Determine workout frequency based on phase
    if phase == "base":
        # Base: 1 quality session, focus on aerobic volume
        quality_sessions = 1
        long_run = True
    elif phase == "build":
        # Build: 2 quality sessions, increasing volume
        quality_sessions = 2
        long_run = True
    elif phase == "sharpen":
        # Sharpen: 2-3 quality sessions, race-specific
        quality_sessions = 2
        long_run = True  # Maintained but shorter
    elif phase == "taper":
        # Taper: Reduced volume, maintain sharpness
        quality_sessions = 1
        long_run = False  # Or very short
    else:
        quality_sessions = 1
        long_run = True
    
    # Build day structure
    # Day 1: Easy/Recovery
    days.append({"day": 1, "type": "easy", "workout": None})
    
    # Day 2: Quality session 1
    if quality_sessions >= 1:
        days.append({"day": 2, "type": "quality", "workout": None})
        days.append({"day": 3, "type": "easy", "workout": None})
    
    # Day 4: Quality session 2 (if applicable)
    if quality_sessions >= 2:
        days.append({"day": 4, "type": "quality", "workout": None})
        days.append({"day": 5, "type": "easy", "workout": None})
    else:
        days.append({"day": 4, "type": "easy", "workout": None})
        days.append({"day": 5, "type": "easy", "workout": None})
    
    # Day 6: Long run (if applicable)
    if long_run:
        days.append({"day": 6, "type": "long_run", "workout": None})
    else:
        days.append({"day": 6, "type": "easy", "workout": None})
    
    # Day 7: Recovery/Off
    days.append({"day": 7, "type": "recovery", "workout": None})
    
    return {
        "week": week_num,
        "phase": phase,
        "days": days,
        "total_mileage": 0,  # Will be calculated
        "quality_sessions": quality_sessions
    }


def synthesize_workout_from_principles(
    slot_type: str,
    phase: str,
    methodologies: Dict[str, float],
    vdot: float,
    week_num: int,
    alternation_focus: Optional[str] = None,
    db_session = None
) -> Optional[Dict]:
    """
    Synthesize a workout from principles based on slot type and phase.
    
    Args:
        slot_type: Type of workout slot ("quality", "long_run", "easy")
        phase: Current training phase
        methodologies: Methodology blend
        vdot: Athlete's VDOT
        week_num: Week number (for progression)
        db_session: Database session
        
    Returns:
        Workout dictionary or None
    """
    # Get phase-specific tags
    phase_tags = get_phase_tags(phase)
    
    # Add slot-specific tags
    if slot_type == "quality":
        slot_tags = ["threshold", "tempo", "interval", "vo2max", "speed"]
    elif slot_type == "long_run":
        slot_tags = ["long_run", "aerobic", "endurance"]
    else:  # easy/recovery
        slot_tags = ["easy_run", "aerobic", "recovery"]
    
    # Combine tags
    query_tags = phase_tags + slot_tags
    
    # Query principles from blended methodologies
    all_principles = []
    for methodology, weight in methodologies.items():
        if weight > 0.1:
            principles = query_knowledge_base_internal(
                tags=query_tags,
                methodology=methodology,
                limit=int(3 * weight),
                db_session=db_session
            )
            all_principles.extend(principles)
    
    if not all_principles:
        logger.warning(f"No principles found for {slot_type} in {phase}")
        return None
    
    # Get training paces from VDOT
    paces = calculate_training_paces(vdot)
    if not paces:
        logger.warning(f"Could not calculate paces for VDOT {vdot}")
        return None
    
    # Synthesize workout based on slot type
    if slot_type == "quality":
        # Apply alternation pattern if specified
        if alternation_focus == "threshold":
            # Threshold-focused week: Emphasize tempo/threshold work
            workout_type = "threshold"
            pace = paces.get("t_pace", "6:00/mi")
            description = f"Threshold tempo run at {pace}"
        elif alternation_focus == "interval":
            # Interval-focused week: Emphasize VO2max/speed work
            workout_type = "vo2max"
            pace = paces.get("i_pace", "5:30/mi")
            description = f"VO₂max intervals at {pace}"
        elif alternation_focus == "mp_long":
            # MP long week: Reduced quality session intensity
            workout_type = "moderate"
            pace = paces.get("m_pace", "6:15/mi")
            description = f"Moderate pace run at {pace}"
        elif phase == "base":
            # Base: Threshold/tempo work
            workout_type = "threshold"
            pace = paces.get("t_pace", "6:00/mi")
            description = f"Threshold intervals at {pace}"
        elif phase == "build":
            # Build: Mix threshold and VO2max (default alternation if not explicitly set)
            if week_num % 2 == 0:
                workout_type = "threshold"
                pace = paces.get("t_pace", "6:00/mi")
                description = f"Threshold tempo run at {pace}"
            else:
                workout_type = "vo2max"
                pace = paces.get("i_pace", "5:30/mi")
                description = f"VO₂max intervals at {pace}"
        elif phase == "sharpen":
            # Sharpen: Race-specific pace work
            workout_type = "race_pace"
            pace = paces.get("m_pace", "6:15/mi")  # Marathon pace as default
            description = f"Race-pace intervals at {pace}"
        else:  # taper
            workout_type = "sharpening"
            pace = paces.get("i_pace", "5:30/mi")
            description = f"Sharpening intervals at {pace}"
        
        # Generate specific prescription
        # TODO: Extract from principles for more sophisticated prescriptions
        if "interval" in workout_type.lower():
            prescription = f"5 x 1000m at {pace} with 2-3 min recovery"
        elif "tempo" in workout_type.lower():
            prescription = f"20-30 minutes continuous at {pace}"
        else:
            prescription = f"Workout at {pace}"
        
        return {
            "workout_type": workout_type,
            "description": description,
            "prescription": prescription,
            "pace": pace,
            "effort": "Moderately hard to hard"
        }
    
    elif slot_type == "long_run":
        # Apply alternation pattern: MP+ longs only every 3rd week
        if alternation_focus == "mp_long":
            # MP long week: Include marathon pace segments
            base_distance = 10  # miles
            if phase == "base":
                distance = base_distance + (week_num * 1)
            elif phase == "build":
                distance = base_distance + 6 + (week_num * 0.5)
            elif phase == "sharpen":
                distance = base_distance + 4
            else:  # taper
                distance = base_distance - 4
            
            mp_pace = paces.get("m_pace", "6:15/mi")
            easy_pace = paces.get("e_pace", "7:30/mi")
            
            return {
                "workout_type": "long_run",
                "description": f"Long run with marathon pace segments",
                "prescription": f"{distance:.1f} miles: {distance-3:.1f} miles easy ({easy_pace}), 3 miles at marathon pace ({mp_pace})",
                "pace": easy_pace,
                "distance_miles": distance,
                "effort": "Moderate to hard (MP segments)",
                "alternation_note": "MP long run - reduced quality session intensity this week"
            }
        else:
            # Threshold/Interval weeks: Easy to moderate pace only, no MP+ segments
            base_distance = 10  # miles
            if phase == "base":
                distance = base_distance + (week_num * 1)  # Progressive
            elif phase == "build":
                distance = base_distance + 6 + (week_num * 0.5)
            elif phase == "sharpen":
                distance = base_distance + 4  # Maintained but shorter
            else:  # taper
                distance = base_distance - 4  # Reduced
            
            pace = paces.get("e_pace", "7:30/mi")
            
            return {
                "workout_type": "long_run",
                "description": f"Long aerobic run for endurance development",
                "prescription": f"{distance:.1f} miles at easy to moderate pace ({pace})",
                "pace": pace,
                "distance_miles": distance,
                "effort": "Easy to moderate",
                "alternation_note": "Easy pace long run - quality session focus this week"
            }
    
    else:  # easy/recovery
        pace = paces.get("e_pace", "7:30/mi")
        distance = 4 + (week_num * 0.2)  # Slight progression
        
        return {
            "workout_type": "easy_run",
            "description": "Easy aerobic run",
            "prescription": f"{distance:.1f} miles at easy pace ({pace})",
            "pace": pace,
            "distance_miles": distance,
            "effort": "Easy - conversational pace"
        }


def generate_principle_based_plan(
    athlete_id: str,
    goal_distance: str,
    current_fitness: Dict,
    diagnostic_signals: Dict,
    athlete_profile: Dict,
    weeks_to_race: int = 12,
    db_session = None
) -> Dict:
    """
    Generate a training plan from principles (not templates).
    
    Args:
        athlete_id: Athlete ID
        goal_distance: Target race distance
        current_fitness: Current fitness metrics (must include VDOT or recent race time)
        diagnostic_signals: Diagnostic signals
        athlete_profile: Athlete characteristics
        weeks_to_race: Weeks until goal race (4-18)
        db_session: Database session
        
    Returns:
        Generated training plan (client-facing)
    """
    # Validate weeks_to_race
    weeks_to_race = max(4, min(18, weeks_to_race))
    
    # Step 1: Determine methodology blend
    methodologies = determine_methodology_blend(
        diagnostic_signals=diagnostic_signals,
        athlete_profile=athlete_profile
    )
    
    # Step 2: Get VDOT
    vdot = current_fitness.get("vdot")
    if not vdot:
        # Try to calculate from recent race time
        recent_race_time = current_fitness.get("recent_race_time_seconds")
        recent_race_distance = current_fitness.get("recent_race_distance_meters")
        if recent_race_time and recent_race_distance:
            vdot = calculate_vdot_from_race_time(recent_race_distance, recent_race_time)
        
        if not vdot:
            # Default VDOT
            vdot = 50.0
            logger.warning(f"Using default VDOT {vdot} for athlete {athlete_id}")
    
    # Step 3: Allocate phases
    current_mileage = athlete_profile.get("current_base_mileage", 0) or diagnostic_signals.get("current_weekly_mileage", 0)
    phase_allocation = allocate_phases(weeks_to_race, current_mileage)
    
    # Step 4: Check if alternation pattern should be applied
    alternation_applied = False
    alternation_rationale = None
    if "Runner Road Magic" in methodologies and methodologies["Runner Road Magic"] > 0.15:
        alternation_applied = True
        alternation_rationale = methodologies.get("_alternation_rationale", "Alternation pattern supports sustainability at high volume")
    
    # Step 5: Generate week-by-week structure
    weeks = []
    current_phase = "base"
    week_num = 1
    alternation_week_counter = 0  # Track alternation cycle (0=threshold, 1=interval, 2=MP long)
    
    for phase, phase_weeks in phase_allocation.items():
        if phase_weeks == 0:
            continue
        
        for i in range(phase_weeks):
            week = generate_weekly_skeleton(phase, week_num, weeks_to_race)
            
            # Determine alternation focus for this week (if alternation applied)
            alternation_focus = None
            if alternation_applied and phase in ["build", "sharpen"]:
                alternation_week_counter = (week_num - 1) % 3
                if alternation_week_counter == 0:
                    alternation_focus = "threshold"  # Threshold-focused week
                elif alternation_week_counter == 1:
                    alternation_focus = "interval"  # Interval-focused week
                else:  # alternation_week_counter == 2
                    alternation_focus = "mp_long"  # MP long run week
            
            # Fill workout slots
            total_mileage = 0
            workouts = []
            
            for day in week["days"]:
                slot_type = day["type"]
                
                # Skip recovery/off days for mileage calculation
                if slot_type == "recovery":
                    day["workout"] = {"workout_type": "rest", "description": "Rest day"}
                    continue
                
                workout = synthesize_workout_from_principles(
                    slot_type=slot_type,
                    phase=phase,
                    methodologies=methodologies,
                    vdot=vdot,
                    week_num=week_num,
                    alternation_focus=alternation_focus if alternation_applied else None,
                    db_session=db_session
                )
                
                # Fallback if no principles found
                if not workout:
                    # Generate default workout based on slot type
                    paces = calculate_training_paces(vdot) or {}
                    if slot_type == "easy":
                        workout = {
                            "workout_type": "easy_run",
                            "description": "Easy aerobic run",
                            "prescription": f"4-6 miles at easy pace",
                            "pace": paces.get("e_pace", "7:30/mi"),
                            "distance_miles": 5,
                            "effort": "Easy - conversational pace"
                        }
                    elif slot_type == "quality":
                        workout = {
                            "workout_type": "threshold",
                            "description": "Threshold workout",
                            "prescription": f"20 minutes at threshold pace",
                            "pace": paces.get("t_pace", "6:00/mi"),
                            "effort": "Comfortably hard"
                        }
                    elif slot_type == "long_run":
                        workout = {
                            "workout_type": "long_run",
                            "description": "Long aerobic run",
                            "prescription": f"10-12 miles at easy pace",
                            "pace": paces.get("e_pace", "7:30/mi"),
                            "distance_miles": 11,
                            "effort": "Easy to moderate"
                        }
                
                if workout:
                    day["workout"] = workout
                    # Only count non-rest workouts
                    if workout.get("workout_type") != "rest":
                        workouts.append(workout)
                    
                    # Estimate mileage from workout
                    if "distance_miles" in workout:
                        total_mileage += workout["distance_miles"]
                    elif slot_type == "easy":
                        total_mileage += 5  # Default easy run
                    elif slot_type == "quality":
                        total_mileage += 6  # Quality session estimate
                    elif slot_type == "long_run":
                        total_mileage += 11  # Default long run
            
            week["total_mileage"] = round(total_mileage, 1)
            week["workouts"] = workouts
            
            # Add alternation focus to week metadata if applied
            if alternation_applied and alternation_focus:
                week["alternation_focus"] = alternation_focus
            
            weeks.append(week)
            week_num += 1
    
    # Step 6: Generate blending rationale
    blending_rationale = get_blending_rationale(
        blend=methodologies,
        diagnostic_signals=diagnostic_signals,
        athlete_profile=athlete_profile
    )
    
    # Step 7: Structure plan response
    internal_plan = {
        "athlete_id": athlete_id,
        "goal_distance": goal_distance,
        "generated_at": datetime.now().isoformat(),
        "plan": {
            "weeks": weeks,
            "total_weeks": weeks_to_race,
            "alternation_applied": alternation_applied,
            "alternation_rationale": alternation_rationale,
            "phase_allocation": phase_allocation,
            "vdot_used": vdot
        },
        "rationale": f"Principle-based plan generated for {weeks_to_race} weeks using blended methodologies",
        "_internal": {
            "blending_rationale": blending_rationale,
            "methodologies_used": methodologies,
            "generation_method": "principle_based"
        }
    }
    
    # Step 7: Validate plan
    is_valid, warnings = validate_plan_coherence(internal_plan)
    internal_plan["plan"]["validation"] = {
        "is_valid": is_valid,
        "warnings": warnings
    }
    
    # Step 8: Translate to client-facing
    from services.ai_coaching_engine import translate_recommendation_for_client
    client_facing = translate_recommendation_for_client(internal_plan)
    
    return client_facing

