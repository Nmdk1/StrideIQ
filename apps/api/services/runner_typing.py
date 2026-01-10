"""
Runner Typing Service (McMillan-inspired)

Automatically classifies runners based on their race history:
- SPEEDSTER: Better at short distances relative to long
- ENDURANCE_MONSTER: Better at long distances relative to short  
- BALANCED: Consistent across distances

This allows us to tailor training recommendations.
"""

from typing import Optional, Tuple, Dict, List
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID
import logging

from sqlalchemy.orm import Session
from sqlalchemy import func

from models import Athlete, Activity

logger = logging.getLogger(__name__)


@dataclass
class RunnerTypeResult:
    """Result of runner type classification"""
    runner_type: str  # 'speedster', 'endurance_monster', 'balanced'
    confidence: float  # 0-1
    analysis: Dict  # Supporting data
    recommendation: str  # What this means for training


# Distance buckets for analysis
DISTANCE_BUCKETS = {
    'short': (0, 8000),        # Up to 8K (5K range)
    'medium': (8000, 18000),   # 8K-18K (10K-15K range)
    'long': (18000, 35000),    # 18K-35K (half marathon range)
    'ultra_long': (35000, None)  # 35K+ (marathon+)
}

# VDOT equivalency ratios (from Jack Daniels)
# If you're balanced, your race performances should follow these ratios
VDOT_RATIOS = {
    '5K_to_10K': 1.06,      # 10K should be ~1.06x 5K pace
    '10K_to_HM': 1.035,     # HM should be ~1.035x 10K pace
    'HM_to_M': 1.045,       # Marathon should be ~1.045x HM pace
}


def classify_runner_type(db: Session, athlete_id: UUID) -> Optional[RunnerTypeResult]:
    """
    Classify a runner's type based on their race history.
    
    Compares performance across distances to determine if they're
    naturally better at shorter or longer distances.
    """
    # Get race results from last 2 years
    cutoff = datetime.now() - timedelta(days=730)
    
    races = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.start_time >= cutoff,
        Activity.is_race_candidate == True,
        Activity.distance_m >= 3000,  # At least 3K
        Activity.duration_s > 0
    ).all()
    
    if len(races) < 3:
        return RunnerTypeResult(
            runner_type='unknown',
            confidence=0.0,
            analysis={'reason': 'Not enough race data (need at least 3 races)'},
            recommendation='Race more to get a classification!'
        )
    
    # Group races by distance bucket
    bucket_performances = {bucket: [] for bucket in DISTANCE_BUCKETS}
    
    for race in races:
        dist = race.distance_m
        pace = race.duration_s / race.distance_m  # seconds per meter
        
        for bucket, (min_d, max_d) in DISTANCE_BUCKETS.items():
            if min_d <= dist and (max_d is None or dist < max_d):
                bucket_performances[bucket].append({
                    'pace_per_km': pace * 1000,  # Convert to sec/km
                    'distance': dist,
                    'date': race.start_time
                })
                break
    
    # Need at least 2 buckets with data
    buckets_with_data = [b for b, perfs in bucket_performances.items() if len(perfs) > 0]
    if len(buckets_with_data) < 2:
        return RunnerTypeResult(
            runner_type='unknown',
            confidence=0.0,
            analysis={'reason': 'Need races at different distances'},
            recommendation='Try racing at different distances!'
        )
    
    # Calculate average pace for each bucket (best performance)
    bucket_best_paces = {}
    for bucket, perfs in bucket_performances.items():
        if perfs:
            bucket_best_paces[bucket] = min(p['pace_per_km'] for p in perfs)
    
    # Compare to expected ratios
    speedster_score = 0
    endurance_score = 0
    comparisons = []
    
    # Short vs long comparison
    if 'short' in bucket_best_paces and 'long' in bucket_best_paces:
        short_pace = bucket_best_paces['short']
        long_pace = bucket_best_paces['long']
        expected_ratio = 1.08  # Long should be ~8% slower
        actual_ratio = long_pace / short_pace
        
        if actual_ratio < expected_ratio:
            # Long distance is relatively faster - endurance monster
            endurance_score += 2
            comparisons.append('Strong at long distances relative to short')
        elif actual_ratio > expected_ratio * 1.05:
            # Short distance is relatively faster - speedster
            speedster_score += 2
            comparisons.append('Strong at short distances relative to long')
        else:
            comparisons.append('Balanced between short and long distances')
    
    # Medium distance comparison
    if 'medium' in bucket_best_paces:
        medium_pace = bucket_best_paces['medium']
        
        if 'short' in bucket_best_paces:
            short_pace = bucket_best_paces['short']
            expected_ratio = 1.04
            actual_ratio = medium_pace / short_pace
            
            if actual_ratio < expected_ratio:
                endurance_score += 1
            elif actual_ratio > expected_ratio * 1.03:
                speedster_score += 1
        
        if 'long' in bucket_best_paces:
            long_pace = bucket_best_paces['long']
            expected_ratio = 1.04
            actual_ratio = long_pace / medium_pace
            
            if actual_ratio < expected_ratio:
                endurance_score += 1
            elif actual_ratio > expected_ratio * 1.03:
                speedster_score += 1
    
    # Determine type
    total_score = speedster_score + endurance_score
    if total_score == 0:
        runner_type = 'balanced'
        confidence = 0.7
        recommendation = 'You perform consistently across distances. You can train either end.'
    elif speedster_score > endurance_score:
        runner_type = 'speedster'
        confidence = min(0.9, 0.5 + (speedster_score - endurance_score) * 0.1)
        recommendation = 'Focus on building endurance while maintaining your natural speed. More tempo runs, long runs.'
    else:
        runner_type = 'endurance_monster'
        confidence = min(0.9, 0.5 + (endurance_score - speedster_score) * 0.1)
        recommendation = 'Focus on developing speed while leveraging your endurance. More intervals, strides, track work.'
    
    return RunnerTypeResult(
        runner_type=runner_type,
        confidence=confidence,
        analysis={
            'races_analyzed': len(races),
            'buckets_with_data': buckets_with_data,
            'best_paces': bucket_best_paces,
            'speedster_score': speedster_score,
            'endurance_score': endurance_score,
            'comparisons': comparisons
        },
        recommendation=recommendation
    )


def update_athlete_runner_type(db: Session, athlete_id: UUID) -> Optional[RunnerTypeResult]:
    """
    Classify and store runner type for an athlete.
    """
    result = classify_runner_type(db, athlete_id)
    
    if result and result.runner_type != 'unknown':
        athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if athlete:
            athlete.runner_type = result.runner_type
            athlete.runner_type_confidence = result.confidence
            athlete.runner_type_last_calculated = datetime.now()
            db.commit()
    
    return result


