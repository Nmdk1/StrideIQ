"""
Enhanced Efficiency Calculation Service

Calculates Efficiency Factor (EF) using Normalized Grade Pace (NGP) with:
- Cardio lag filter (excludes initial 6 minutes)
- Aerobic decoupling calculation (first half vs second half EF)
"""

from typing import List, Optional, Dict, Tuple
from decimal import Decimal
from sqlalchemy.orm import Session
from models import Activity, ActivitySplit


# Cardio lag filter: exclude first 6 minutes to avoid O₂ debt skewing
CARDIO_LAG_SECONDS = 6 * 60  # 6 minutes in seconds


def calculate_efficiency_factor_from_ngp(
    ngp_seconds_per_mile: float,
    avg_hr: int,
    max_hr: Optional[int] = None
) -> Optional[float]:
    """
    Calculate Efficiency Factor (EF) from Normalized Grade Pace (NGP).
    
    EF = speed / HR

    Higher EF = more efficient (more speed produced per heartbeat).
    
    Args:
        ngp_seconds_per_mile: Normalized Grade Pace in seconds per mile
        avg_hr: Average heart rate
        max_hr: Unused. Kept for API compatibility.
    
    Returns:
        Efficiency Factor (float), or None if invalid inputs
    """
    if ngp_seconds_per_mile <= 0 or avg_hr <= 0:
        return None
    
    # Convert NGP to speed (meters per second)
    speed_mps = 1609.34 / ngp_seconds_per_mile
    ef = speed_mps / avg_hr
    return round(ef, 4)


def calculate_activity_efficiency_with_decoupling(
    activity: Activity,
    splits: List[ActivitySplit],
    max_hr: Optional[int] = None
) -> Dict:
    """
    Calculate efficiency metrics for an activity with cardio lag filter and decoupling.
    
    Args:
        activity: Activity object
        splits: List of ActivitySplit objects (ordered by split_number)
        max_hr: Maximum heart rate (optional)
    
    Returns:
        Dictionary with:
        - efficiency_factor: Overall EF (excluding cardio lag period)
        - decoupling_percent: Aerobic decoupling percentage (first half vs second half EF)
        - decoupling_status: "green" (<5%), "yellow" (5-8%), "red" (>8%)
        - first_half_ef: EF for first half of run
        - second_half_ef: EF for second half of run
        - splits_used: Number of splits used in calculation
    """
    if not splits or len(splits) == 0:
        return {
            "efficiency_factor": None,
            "decoupling_percent": None,
            "decoupling_status": None,
            "first_half_ef": None,
            "second_half_ef": None,
            "splits_used": 0
        }
    
    # Filter splits: exclude those in cardio lag period (first 6 minutes)
    filtered_splits = []
    cumulative_time = 0
    
    for split in sorted(splits, key=lambda s: s.split_number):
        if split.moving_time:
            cumulative_time += split.moving_time
            # Only include splits after cardio lag period
            if cumulative_time > CARDIO_LAG_SECONDS:
                filtered_splits.append(split)
    
    if len(filtered_splits) == 0:
        # Not enough data after cardio lag filter
        return {
            "efficiency_factor": None,
            "decoupling_percent": None,
            "decoupling_status": None,
            "first_half_ef": None,
            "second_half_ef": None,
            "splits_used": 0
        }
    
    # Calculate EF for each split
    split_efs = []
    for split in filtered_splits:
        # Use GAP if available, otherwise calculate from raw pace
        if split.gap_seconds_per_mile:
            ngp = float(split.gap_seconds_per_mile)
        else:
            # Fallback: calculate NGP from raw pace (assume flat if no elevation data)
            if split.distance and split.moving_time:
                distance_miles = float(split.distance) / 1609.34
                ngp = split.moving_time / distance_miles
            else:
                continue
        
        if split.average_heartrate:
            ef = calculate_efficiency_factor_from_ngp(ngp, split.average_heartrate, max_hr)
            if ef:
                split_efs.append({
                    "split_number": split.split_number,
                    "ef": ef,
                    "ngp": ngp,
                    "hr": split.average_heartrate
                })
    
    if len(split_efs) == 0:
        return {
            "efficiency_factor": None,
            "decoupling_percent": None,
            "decoupling_status": None,
            "first_half_ef": None,
            "second_half_ef": None,
            "splits_used": 0
        }
    
    # Calculate overall EF (average of all splits after cardio lag)
    overall_ef = sum(s["ef"] for s in split_efs) / len(split_efs)
    
    # Calculate decoupling: compare first half vs second half
    # Split the filtered splits in half
    mid_point = len(split_efs) // 2
    first_half_efs = [s["ef"] for s in split_efs[:mid_point]]
    second_half_efs = [s["ef"] for s in split_efs[mid_point:]]
    
    decoupling_percent = None
    decoupling_status = None
    first_half_ef = None
    second_half_ef = None
    
    if len(first_half_efs) > 0 and len(second_half_efs) > 0:
        first_half_ef = sum(first_half_efs) / len(first_half_efs)
        second_half_ef = sum(second_half_efs) / len(second_half_efs)
        
        # For EF = speed/HR (higher is better):
        # Decoupling = % drop in EF from first half to second half.
        # Positive = less efficient in second half (drift).
        # Negative = more efficient in second half (strong finish).
        if first_half_ef > 0:
            decoupling_percent = ((first_half_ef - second_half_ef) / first_half_ef) * 100.0
            
            # Traffic light system
            if decoupling_percent < 5.0:
                decoupling_status = "green"  # Excellent durability
            elif decoupling_percent < 8.0:
                decoupling_status = "yellow"  # Moderate drift
            else:
                decoupling_status = "red"  # Significant cardiac drift
    
    return {
        "efficiency_factor": round(overall_ef, 4),
        "decoupling_percent": round(decoupling_percent, 1) if decoupling_percent is not None else None,
        "decoupling_status": decoupling_status,
        "first_half_ef": round(first_half_ef, 4) if first_half_ef is not None else None,
        "second_half_ef": round(second_half_ef, 4) if second_half_ef is not None else None,
        "splits_used": len(split_efs)
    }


