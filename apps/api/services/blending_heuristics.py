"""
Adaptive Blending Heuristics

Defines rules for how to blend different coaching methodologies based on:
- Athlete's diagnostic signals
- Training history and response patterns
- Injury history
- Volume tolerance
- Speed vs. endurance background

These heuristics guide the AI coaching engine in selecting and blending
methodologies from the knowledge base.

ARCHITECTURE:
- Internal only - never exposed to clients
- Used by AI coaching engine to determine methodology blend
- Blending rationale stored in CoachingRecommendation.blending_rationale
"""

from typing import Dict, Optional


def determine_methodology_blend(
    diagnostic_signals: Dict,
    athlete_profile: Dict,
    training_history: Optional[Dict] = None
) -> Dict[str, float]:
    """
    Determine optimal methodology blend based on athlete characteristics.
    
    Args:
        diagnostic_signals: Current diagnostic signals (efficiency, recovery, etc.)
        athlete_profile: Athlete characteristics (injury history, volume tolerance, etc.)
        training_history: Historical training patterns (optional)
        
    Returns:
        Dictionary mapping methodology names to blend percentages
        Example: {"Daniels": 0.6, "Pfitzinger": 0.3, "Canova": 0.1}
    """
    blend = {}
    
    # Initialize with base blend (can be adjusted)
    base_blend = {
        "Daniels": 0.4,
        "Pfitzinger": 0.3,
        "Hansons": 0.2,
        "Canova": 0.1
    }
    
    # Rule 1: Volume Tolerance → Lean Pfitzinger/Hansons
    volume_tolerance = athlete_profile.get("volume_tolerance", "moderate")
    if volume_tolerance == "high":
        # High volume tolerance → more Pfitzinger/Hansons (volume-focused)
        blend["Pfitzinger"] = base_blend.get("Pfitzinger", 0.3) + 0.2
        blend["Hansons"] = base_blend.get("Hansons", 0.2) + 0.1
        blend["Daniels"] = base_blend.get("Daniels", 0.4) - 0.2
        blend["Canova"] = base_blend.get("Canova", 0.1) - 0.1
    elif volume_tolerance == "low":
        # Low volume tolerance → more Daniels (quality-focused)
        blend["Daniels"] = base_blend.get("Daniels", 0.4) + 0.2
        blend["Pfitzinger"] = base_blend.get("Pfitzinger", 0.3) - 0.15
        blend["Hansons"] = base_blend.get("Hansons", 0.2) - 0.1
        blend["Canova"] = base_blend.get("Canova", 0.1) + 0.05
    
    # Rule 2: Speed Background → More Daniels I/R Pace Work
    speed_background = athlete_profile.get("speed_background", "balanced")
    if speed_background == "strong":
        # Strong speed background → more Daniels I/R pace work
        blend["Daniels"] = blend.get("Daniels", base_blend["Daniels"]) + 0.15
        blend["Pfitzinger"] = blend.get("Pfitzinger", base_blend["Pfitzinger"]) - 0.1
        blend["Canova"] = blend.get("Canova", base_blend["Canova"]) - 0.05
    elif speed_background == "weak":
        # Weak speed background → more aerobic/endurance focus
        blend["Pfitzinger"] = blend.get("Pfitzinger", base_blend["Pfitzinger"]) + 0.15
        blend["Hansons"] = blend.get("Hansons", base_blend["Hansons"]) + 0.1
        blend["Daniels"] = blend.get("Daniels", base_blend["Daniels"]) - 0.15
        blend["Canova"] = blend.get("Canova", base_blend["Canova"]) - 0.1
    
    # Rule 3: Injury History → Favor Lower-Intensity Specific Endurance (Canova-inspired)
    injury_history = athlete_profile.get("injury_history", "none")
    if injury_history in ["frequent", "recent"]:
        # Injury history → more Canova-style specific endurance (lower intensity, race-specific)
        blend["Canova"] = blend.get("Canova", base_blend["Canova"]) + 0.2
        blend["Daniels"] = blend.get("Daniels", base_blend["Daniels"]) - 0.1
        blend["Pfitzinger"] = blend.get("Pfitzinger", base_blend["Pfitzinger"]) - 0.05
        blend["Hansons"] = blend.get("Hansons", base_blend["Hansons"]) - 0.05
    
    # Rule 4: Recovery Elasticity → Adjust Session Spacing
    recovery_half_life = diagnostic_signals.get("recovery_half_life_hours", 48)
    if recovery_half_life > 72:
        # Slow recovery → favor lower-intensity, more recovery-focused approaches
        blend["Canova"] = blend.get("Canova", base_blend["Canova"]) + 0.15
        blend["Pfitzinger"] = blend.get("Pfitzinger", base_blend["Pfitzinger"]) - 0.1
        blend["Daniels"] = blend.get("Daniels", base_blend["Daniels"]) - 0.05
    elif recovery_half_life < 36:
        # Fast recovery → can handle more intensity/frequency
        blend["Daniels"] = blend.get("Daniels", base_blend["Daniels"]) + 0.1
        blend["Hansons"] = blend.get("Hansons", base_blend["Hansons"]) + 0.1
        blend["Canova"] = blend.get("Canova", base_blend["Canova"]) - 0.1
        blend["Pfitzinger"] = blend.get("Pfitzinger", base_blend["Pfitzinger"]) - 0.1
    
    # Rule 5: Efficiency Trend → Adjust Intensity
    efficiency_trend = diagnostic_signals.get("efficiency_trend", 0.0)
    if efficiency_trend > 0.02:  # Positive trend (improving)
        # Improving efficiency → can increase intensity (more Daniels I/R)
        blend["Daniels"] = blend.get("Daniels", base_blend["Daniels"]) + 0.1
        blend["Canova"] = blend.get("Canova", base_blend["Canova"]) + 0.05
        blend["Pfitzinger"] = blend.get("Pfitzinger", base_blend["Pfitzinger"]) - 0.1
        blend["Hansons"] = blend.get("Hansons", base_blend["Hansons"]) - 0.05
    elif efficiency_trend < -0.02:  # Negative trend (declining)
        # Declining efficiency → reduce intensity, focus on recovery/aerobic
        blend["Pfitzinger"] = blend.get("Pfitzinger", base_blend["Pfitzinger"]) + 0.15
        blend["Hansons"] = blend.get("Hansons", base_blend["Hansons"]) + 0.1
        blend["Daniels"] = blend.get("Daniels", base_blend["Daniels"]) - 0.15
        blend["Canova"] = blend.get("Canova", base_blend["Canova"]) - 0.1
    
    # Rule 6: Durability Index → Adjust Volume
    durability_index = diagnostic_signals.get("durability_index", 50.0)
    if durability_index > 70:
        # High durability → can handle more volume (Pfitzinger/Hansons)
        blend["Pfitzinger"] = blend.get("Pfitzinger", base_blend["Pfitzinger"]) + 0.15
        blend["Hansons"] = blend.get("Hansons", base_blend["Hansons"]) + 0.1
        blend["Daniels"] = blend.get("Daniels", base_blend["Daniels"]) - 0.15
        blend["Canova"] = blend.get("Canova", base_blend["Canova"]) - 0.1
    elif durability_index < 30:
        # Low durability → reduce volume, focus on quality (Daniels)
        blend["Daniels"] = blend.get("Daniels", base_blend["Daniels"]) + 0.2
        blend["Canova"] = blend.get("Canova", base_blend["Canova"]) + 0.1
        blend["Pfitzinger"] = blend.get("Pfitzinger", base_blend["Pfitzinger"]) - 0.2
        blend["Hansons"] = blend.get("Hansons", base_blend["Hansons"]) - 0.1
    
    # Rule 7: Runner Road Magic Alternation Pattern
    # Apply higher weight for high-volume, masters athletes, or when historical data supports
    weekly_mileage = athlete_profile.get("current_base_mileage", 0) or diagnostic_signals.get("current_weekly_mileage", 0)
    age = athlete_profile.get("age", 0)
    work_constraints = athlete_profile.get("work_constraints", False)  # Full-time work, etc.
    risk_tolerance = athlete_profile.get("risk_tolerance", "moderate")  # conservative, moderate, aggressive
    
    alternation_weight = 0.0
    alternation_reason = []
    
    # High volume (60+ mpw) → favor alternation
    if weekly_mileage >= 60:
        alternation_weight += 0.3
        alternation_reason.append(f"High volume ({weekly_mileage:.0f} mpw) supports alternation pattern")
    
    # Masters athletes (50+) → favor alternation
    if age >= 50:
        alternation_weight += 0.2
        alternation_reason.append(f"Masters athlete (age {age}) benefits from alternation")
    
    # Work constraints → favor alternation (sustainability)
    if work_constraints:
        alternation_weight += 0.15
        alternation_reason.append("Work constraints favor sustainable alternation pattern")
    
    # Conservative/balanced risk tolerance → favor alternation
    if risk_tolerance in ["conservative", "balanced", "moderate"]:
        alternation_weight += 0.1
        alternation_reason.append(f"Risk tolerance ({risk_tolerance}) supports alternation")
    
    # Historical data support (if available)
    if training_history:
        threshold_response = training_history.get("threshold_week_efficiency_gain", 0)
        interval_response = training_history.get("interval_week_efficiency_gain", 0)
        alternation_response = training_history.get("alternation_efficiency_gain", 0)
        
        # If alternation shows superior gains, increase weight
        if alternation_response > max(threshold_response, interval_response) * 1.1:
            alternation_weight += 0.25
            alternation_reason.append("Historical data shows superior efficiency gains with alternation")
    
    # Apply alternation weight (reduces other methodologies proportionally)
    if alternation_weight > 0:
        # Add Runner Road Magic to blend
        blend["Runner Road Magic"] = alternation_weight
        
        # Reduce other methodologies proportionally
        reduction_factor = 1.0 - alternation_weight
        for methodology in ["Daniels", "Pfitzinger", "Hansons", "Canova"]:
            if methodology in blend:
                blend[methodology] = blend[methodology] * reduction_factor
    
    # Normalize to ensure percentages sum to 1.0
    total = sum(blend.values())
    if total > 0:
        blend = {k: v / total for k, v in blend.items()}
    else:
        # Fallback to base blend if all rules resulted in zero
        blend = base_blend
    
    # Round to 2 decimal places
    blend = {k: round(v, 2) for k, v in blend.items()}
    
    # Store alternation rationale if applied
    if alternation_weight > 0:
        blend["_alternation_rationale"] = "; ".join(alternation_reason)
    
    return blend


def get_blending_rationale(
    blend: Dict[str, float],
    diagnostic_signals: Dict,
    athlete_profile: Dict
) -> Dict:
    """
    Generate human-readable rationale for methodology blend.
    
    Args:
        blend: Methodology blend percentages
        diagnostic_signals: Current diagnostic signals
        athlete_profile: Athlete characteristics
        
    Returns:
        Dictionary with rationale explanation
    """
    rationale_parts = []
    
    # Sort methodologies by percentage (highest first)
    sorted_methodologies = sorted(blend.items(), key=lambda x: x[1], reverse=True)
    
    primary = sorted_methodologies[0]
    rationale_parts.append(f"Primary approach: {primary[0]} ({primary[1]*100:.0f}%)")
    
    if len(sorted_methodologies) > 1 and sorted_methodologies[1][1] > 0.15:
        secondary = sorted_methodologies[1]
        rationale_parts.append(f"Secondary: {secondary[0]} ({secondary[1]*100:.0f}%)")
    
    # Add reasoning based on key factors
    if athlete_profile.get("volume_tolerance") == "high":
        rationale_parts.append("Higher volume tolerance supports volume-focused approaches")
    elif athlete_profile.get("volume_tolerance") == "low":
        rationale_parts.append("Lower volume tolerance favors quality-focused training")
    
    if athlete_profile.get("speed_background") == "strong":
        rationale_parts.append("Strong speed background supports higher-intensity interval work")
    elif athlete_profile.get("speed_background") == "weak":
        rationale_parts.append("Aerobic development prioritized due to speed background")
    
    if athlete_profile.get("injury_history") in ["frequent", "recent"]:
        rationale_parts.append("Injury history favors lower-intensity, race-specific training")
    
    recovery_half_life = diagnostic_signals.get("recovery_half_life_hours", 48)
    if recovery_half_life > 72:
        rationale_parts.append(f"Extended recovery needs ({recovery_half_life:.0f}h) require more spacing between hard sessions")
    elif recovery_half_life < 36:
        rationale_parts.append(f"Fast recovery ({recovery_half_life:.0f}h) allows higher training frequency")
    
    efficiency_trend = diagnostic_signals.get("efficiency_trend", 0.0)
    if efficiency_trend > 0.02:
        rationale_parts.append("Positive efficiency trend supports increased intensity")
    elif efficiency_trend < -0.02:
        rationale_parts.append("Declining efficiency requires reduced intensity and recovery focus")
    
    return {
        "methodologies": blend,
        "reason": "; ".join(rationale_parts)
    }

