"""
Neutral Terminology Mapping Service

Translates methodology-specific terminology to neutral, physiological terms
for client-facing outputs. Keeps methodology references internal only.

Architecture Decision:
- Internal knowledge base uses methodology tags (Daniels, Pfitzinger, etc.)
- Client-facing outputs use neutral physiological terms
- This allows fluid blending of methodologies without exposing sources
"""

from typing import Dict, Optional, List
import re


# Neutral terminology mapping
# Maps methodology-specific terms to neutral physiological descriptions
NEUTRAL_TERMINOLOGY: Dict[str, Dict[str, str]] = {
    # Daniels Running Formula
    "daniels_e_pace": {
        "neutral": "Easy aerobic pace",
        "description": "Comfortable, conversational pace that builds aerobic base",
        "effort": "Easy effort - you can hold a conversation"
    },
    "daniels_m_pace": {
        "neutral": "Marathon effort pace",
        "description": "Pace you could sustain for a marathon",
        "effort": "Moderately hard - sustainable for ~26 miles"
    },
    "daniels_t_pace": {
        "neutral": "Threshold pace",
        "description": "Comfortably hard pace at lactate threshold (~10K effort)",
        "effort": "Comfortably hard - sustainable for ~20-60 minutes"
    },
    "daniels_i_pace": {
        "neutral": "VO₂max interval pace",
        "description": "Pace that targets your maximum oxygen uptake",
        "effort": "Hard - sustainable for ~3-5 minutes per interval"
    },
    "daniels_r_pace": {
        "neutral": "Repetition pace",
        "description": "Fast pace for speed development (faster than VO₂max)",
        "effort": "Very hard - short bursts for speed work"
    },
    
    # Pfitzinger
    "pfitzinger_marathon_pace": {
        "neutral": "Marathon effort pace",
        "description": "Pace you could sustain for a marathon",
        "effort": "Moderately hard - sustainable for ~26 miles"
    },
    "pfitzinger_lactate_threshold": {
        "neutral": "Threshold pace",
        "description": "Comfortably hard pace at lactate threshold",
        "effort": "Comfortably hard - sustainable for ~20-60 minutes"
    },
    "pfitzinger_vo2max": {
        "neutral": "VO₂max interval pace",
        "description": "Pace that targets your maximum oxygen uptake",
        "effort": "Hard - sustainable for ~3-5 minutes per interval"
    },
    
    # Hansons
    "hansons_easy": {
        "neutral": "Easy aerobic pace",
        "description": "Comfortable, conversational pace",
        "effort": "Easy effort - you can hold a conversation"
    },
    "hansons_sos": {
        "neutral": "Something of substance (tempo/threshold)",
        "description": "Moderate to hard effort that builds fitness",
        "effort": "Moderately hard to hard - sustainable for workout duration"
    },
    "hansons_goal_pace": {
        "neutral": "Goal race pace",
        "description": "Pace you're targeting for your goal race",
        "effort": "Race-specific effort"
    },
    
    # Canova
    "canova_special_endurance": {
        "neutral": "Race-specific endurance pace",
        "description": "Pace specific to your target race distance",
        "effort": "Race-specific effort"
    },
    "canova_extensive_tempo": {
        "neutral": "Extended tempo pace",
        "description": "Sustained tempo effort for endurance development",
        "effort": "Moderately hard - sustainable for extended periods"
    },
    
    # Generic workout types
    "long_run": {
        "neutral": "Long run",
        "description": "Extended aerobic run for endurance development",
        "effort": "Easy to moderate - builds aerobic capacity"
    },
    "tempo_run": {
        "neutral": "Tempo run",
        "description": "Sustained effort at threshold pace",
        "effort": "Comfortably hard - sustainable for workout duration"
    },
    "cruise_intervals": {
        "neutral": "Threshold intervals",
        "description": "Repeated efforts at threshold pace with short recovery",
        "effort": "Comfortably hard - sustainable for each interval"
    },
    "marathon_goal_pace_segments": {
        "neutral": "Marathon-effort segments",
        "description": "Sections of your run at marathon race pace",
        "effort": "Moderately hard - sustainable for ~26 miles"
    },
    "easy_plus_strides": {
        "neutral": "Aerobic run with form drills",
        "description": "Easy run followed by short acceleration drills to sharpen form",
        "effort": "Easy run with brief faster efforts"
    },
    "interval_workout": {
        "neutral": "Interval workout",
        "description": "Repeated hard efforts with recovery",
        "effort": "Hard efforts with recovery periods"
    },
    "recovery_run": {
        "neutral": "Recovery run",
        "description": "Easy pace for active recovery",
        "effort": "Very easy - promotes recovery"
    },
    "progression_run": {
        "neutral": "Progression run",
        "description": "Run that gradually increases in pace",
        "effort": "Starts easy, finishes moderate to hard"
    },
}


def translate_to_neutral(term: str, methodology: Optional[str] = None) -> Dict[str, str]:
    """
    Translate a methodology-specific term to neutral terminology.
    
    Args:
        term: Methodology-specific term (e.g., "daniels_t_pace", "hansons_sos")
        methodology: Optional methodology name for context
        
    Returns:
        Dictionary with neutral term, description, and effort level
    """
    # Try exact match first
    if term.lower() in NEUTRAL_TERMINOLOGY:
        return NEUTRAL_TERMINOLOGY[term.lower()]
    
    # Try pattern matching
    term_lower = term.lower()
    
    # Check for common patterns
    if "e_pace" in term_lower or "easy" in term_lower:
        return NEUTRAL_TERMINOLOGY["daniels_e_pace"]
    elif "t_pace" in term_lower or "threshold" in term_lower or "tempo" in term_lower:
        return NEUTRAL_TERMINOLOGY["daniels_t_pace"]
    elif "i_pace" in term_lower or "vo2max" in term_lower or "interval" in term_lower:
        return NEUTRAL_TERMINOLOGY["daniels_i_pace"]
    elif "r_pace" in term_lower or "repetition" in term_lower or "speed" in term_lower:
        return NEUTRAL_TERMINOLOGY["daniels_r_pace"]
    elif "marathon_pace" in term_lower or "m_pace" in term_lower:
        return NEUTRAL_TERMINOLOGY["daniels_m_pace"]
    elif "long_run" in term_lower or "long" in term_lower:
        return NEUTRAL_TERMINOLOGY["long_run"]
    elif "recovery" in term_lower:
        return NEUTRAL_TERMINOLOGY["recovery_run"]
    elif "progression" in term_lower:
        return NEUTRAL_TERMINOLOGY["progression_run"]
    
    # Default fallback
    return {
        "neutral": term.replace("_", " ").title(),
        "description": f"Training pace based on your current fitness",
        "effort": "Moderate effort"
    }


def strip_methodology_references(text: str) -> str:
    """
    Remove methodology references from text.
    
    Args:
        text: Text that may contain methodology references
        
    Returns:
        Text with methodology references removed or replaced
    """
    methodology_names = [
        "Daniels", "Pfitzinger", "Canova", "Hanson", "Hansons",
        "Roche", "Bitter", "Hudson", "Tinman", "Lydiard"
    ]
    
    result = text
    for method in methodology_names:
        # Remove methodology name followed by possessive or descriptive terms
        patterns = [
            rf"{method}'s?\s+(pace|method|system|approach|plan|principles|methodology|training|style|threshold|volume|work)",
            rf"{method}\s+(pace|method|system|approach|plan|principles|methodology|training|style|threshold|volume|work)",
            rf"based on {method}",
            rf"from {method}",
            rf"{method} style",
            rf"{method}-style",
            rf"{method}-inspired",
            rf"following {method}'s?",
            rf"using {method}'s?",
            rf"per {method}'s?",
            rf"{method}'s? (?:RPI|threshold|tempo|interval)",
            # Catch blended contexts: "Blended X with Y" or "combines X with Y"
            rf"\b(?:blended|combines?|mixes?|uses?)\s+{method}'s?\s+(?:with|and)",
            rf"{method}'s?\s+(?:with|and)",
            # Catch standalone methodology names in rationale/description contexts
            rf"\b{method}'s?\b",
        ]
        for pattern in patterns:
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)
    
    # Clean up extra spaces and punctuation
    result = re.sub(r'\s+', ' ', result)  # Multiple spaces to single
    result = re.sub(r'\s+([,\.;:])', r'\1', result)  # Space before punctuation
    result = re.sub(r'([,\.;:])\s*,\s*', r'\1 ', result)  # Double punctuation
    result = result.strip()
    
    # If result is empty or just punctuation, return a generic message
    if not result or result in [".", ",", ";", ":"]:
        return "Based on proven training principles"
    
    return result


def format_workout_description(
    workout_type: str,
    pace: Optional[str] = None,
    duration: Optional[str] = None,
    methodology: Optional[str] = None
) -> str:
    """
    Format a workout description using neutral terminology.
    
    Args:
        workout_type: Type of workout (e.g., "threshold", "long_run")
        pace: Pace information (will be translated to neutral)
        duration: Duration/distance of workout
        methodology: Methodology name (for internal tracking, not exposed)
        
    Returns:
        Client-facing workout description
    """
    neutral = translate_to_neutral(workout_type, methodology)
    
    description = neutral["neutral"]
    if neutral.get("description"):
        description += f": {neutral['description']}"
    
    if pace:
        description += f" ({pace})"
    
    if duration:
        description += f" for {duration}"
    
    if neutral.get("effort"):
        description += f". Effort: {neutral['effort']}"
    
    return description


def get_neutral_workout_labels() -> List[str]:
    """
    Get list of all neutral workout labels for UI/API.
    
    Returns:
        List of neutral workout type labels
    """
    return [
        "Easy aerobic run",
        "Marathon effort run",
        "Threshold run",
        "VO₂max intervals",
        "Speed/Repetition work",
        "Long run",
        "Tempo run",
        "Recovery run",
        "Progression run",
        "Race-specific endurance",
    ]

