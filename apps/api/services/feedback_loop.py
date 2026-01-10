"""
Continuous Feedback Loop - Observe, Hypothesize, Intervene, Validate

This implements the core feedback loop structure from the manifesto:
- Observe: Collect data from all sources
- Hypothesize: Analyze data to identify limiting factors
- Intervene: Recommend small, effective changes
- Validate: Check if interventions are having desired effect
"""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from models import Athlete, Activity, ActivitySplit
from services.performance_engine import calculate_age_at_date
from services.athlete_metrics import calculate_athlete_derived_signals


# ============================================================================
# OBSERVE: Data Collection and Aggregation
# ============================================================================

def observe_athlete_data(athlete: Athlete, db: Session, lookback_days: int = 30) -> Dict:
    """
    Observe: Collect and aggregate all available data for an athlete.
    
    This is the first step in the feedback loop - gathering all relevant
    performance, training, and recovery data.
    
    Args:
        athlete: Athlete to observe
        db: Database session
        lookback_days: Number of days to look back
        
    Returns:
        Dictionary containing observed data:
        - activities: List of recent activities
        - performance_trends: Performance metrics over time
        - training_load: Volume and intensity metrics
        - recovery_signals: Recovery and wellness indicators
        - limiting_factors: Potential issues identified
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    
    # Collect activities
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete.id,
        Activity.start_time >= cutoff_date
    ).order_by(Activity.start_time.desc()).all()
    
    # Calculate performance trends
    performance_trends = []
    for activity in activities:
        if activity.performance_percentage and activity.distance_m:
            performance_trends.append({
                'date': activity.start_time,
                'performance_percentage': activity.performance_percentage,
                'distance_m': activity.distance_m,
                'pace_per_mile': activity.pace_per_mile,
            })
    
    # Calculate training load
    total_distance = sum(float(a.distance_m or 0) for a in activities)
    total_time = sum(int(a.duration_s or 0) for a in activities)
    avg_pace = None
    if activities:
        paces = [a.pace_per_mile for a in activities if a.pace_per_mile]
        if paces:
            avg_pace = sum(paces) / len(paces)
    
    training_load = {
        'total_distance_m': total_distance,
        'total_time_s': total_time,
        'activity_count': len(activities),
        'avg_pace_per_mile': avg_pace,
    }
    
    # Recovery signals (placeholder - will integrate with recovery data sources)
    recovery_signals = {
        'durability_index': athlete.durability_index,
        'recovery_half_life_hours': athlete.recovery_half_life_hours,
        'consistency_index': athlete.consistency_index,
    }
    
    # Identify potential limiting factors
    limiting_factors = _identify_limiting_factors(activities, recovery_signals)
    
    return {
        'athlete_id': str(athlete.id),
        'observation_date': datetime.now(timezone.utc),
        'lookback_days': lookback_days,
        'activities': len(activities),
        'performance_trends': performance_trends,
        'training_load': training_load,
        'recovery_signals': recovery_signals,
        'limiting_factors': limiting_factors,
    }


def _identify_limiting_factors(activities: List[Activity], recovery_signals: Dict) -> List[str]:
    """
    Identify potential limiting factors from observed data.
    
    This is a simplified version - in production, this would use more
    sophisticated analysis.
    """
    factors = []
    
    if not activities:
        factors.append("insufficient_training_data")
        return factors
    
    # Check for low consistency
    if recovery_signals.get('consistency_index') and recovery_signals['consistency_index'] < 50:
        factors.append("low_consistency")
    
    # Check for declining performance
    if len(activities) >= 5:
        recent_perf = [a.performance_percentage for a in activities[:5] if a.performance_percentage]
        older_perf = [a.performance_percentage for a in activities[5:10] if a.performance_percentage]
        if recent_perf and older_perf:
            avg_recent = sum(recent_perf) / len(recent_perf)
            avg_older = sum(older_perf) / len(older_perf)
            if avg_recent < avg_older * 0.95:  # 5% decline
                factors.append("declining_performance")
    
    # Check for low durability
    if recovery_signals.get('durability_index') and recovery_signals['durability_index'] < 50:
        factors.append("low_durability")
    
    # Check for high recovery time
    if recovery_signals.get('recovery_half_life_hours') and recovery_signals['recovery_half_life_hours'] > 48:
        factors.append("slow_recovery")
    
    return factors


# ============================================================================
# HYPOTHESIZE: Analysis and Limiting Factor Identification
# ============================================================================

def hypothesize_limiting_factors(observation: Dict) -> Dict:
    """
    Hypothesize: Analyze observed data to identify root causes and limiting factors.
    
    This step takes the observed data and creates hypotheses about what might be
    limiting the athlete's performance or training.
    
    Args:
        observation: Output from observe_athlete_data()
        
    Returns:
        Dictionary containing hypotheses:
        - primary_hypothesis: Main limiting factor hypothesis
        - supporting_evidence: Data supporting the hypothesis
        - confidence: Confidence level (0.0-1.0)
        - alternative_hypotheses: Other possible explanations
    """
    limiting_factors = observation.get('limiting_factors', [])
    
    if not limiting_factors:
        return {
            'primary_hypothesis': 'no_limiting_factors',
            'supporting_evidence': [],
            'confidence': 0.5,
            'alternative_hypotheses': [],
            'recommendation': 'Continue current training approach. Monitor for changes.',
        }
    
    # Prioritize hypotheses based on severity and evidence
    primary_factor = limiting_factors[0] if limiting_factors else None
    
    # Map factors to hypotheses
    hypothesis_map = {
        'low_consistency': {
            'hypothesis': 'Inconsistent training volume or frequency is limiting progress',
            'evidence': ['Low consistency index', 'Irregular activity patterns'],
            'confidence': 0.7,
        },
        'declining_performance': {
            'hypothesis': 'Performance decline suggests overtraining, injury, or inadequate recovery',
            'evidence': ['Recent performance lower than historical average'],
            'confidence': 0.6,
        },
        'low_durability': {
            'hypothesis': 'Low durability suggests inability to handle increased training load',
            'evidence': ['Low durability index', 'Potential injury risk'],
            'confidence': 0.75,
        },
        'slow_recovery': {
            'hypothesis': 'Slow recovery indicates inadequate rest or excessive training load',
            'evidence': ['High recovery half-life', 'Extended recovery times between sessions'],
            'confidence': 0.8,
        },
        'insufficient_training_data': {
            'hypothesis': 'Insufficient data to make recommendations',
            'evidence': ['Few activities in observation period'],
            'confidence': 0.9,
        },
    }
    
    if primary_factor and primary_factor in hypothesis_map:
        hypothesis_data = hypothesis_map[primary_factor]
        return {
            'primary_hypothesis': hypothesis_data['hypothesis'],
            'supporting_evidence': hypothesis_data['evidence'],
            'confidence': hypothesis_data['confidence'],
            'alternative_hypotheses': [hypothesis_map[f]['hypothesis'] for f in limiting_factors[1:] if f in hypothesis_map],
            'limiting_factor': primary_factor,
        }
    
    return {
        'primary_hypothesis': 'Unknown limiting factors detected',
        'supporting_evidence': limiting_factors,
        'confidence': 0.5,
        'alternative_hypotheses': [],
    }


# ============================================================================
# INTERVENE: Recommendation Generation
# ============================================================================

def intervene_recommendations(hypothesis: Dict, observation: Dict) -> Dict:
    """
    Intervene: Generate small, effective recommendations based on hypotheses.
    
    This step creates actionable recommendations to address the identified
    limiting factors. Recommendations are small, incremental changes rather
    than dramatic overhauls.
    
    Args:
        hypothesis: Output from hypothesize_limiting_factors()
        observation: Output from observe_athlete_data()
        
    Returns:
        Dictionary containing recommendations:
        - primary_recommendation: Main recommended action
        - supporting_actions: Additional actions to support the primary recommendation
        - expected_outcome: What improvement is expected
        - timeline: Expected time to see results
    """
    limiting_factor = hypothesis.get('limiting_factor')
    
    recommendation_map = {
        'low_consistency': {
            'primary': 'Establish consistent training schedule: aim for 3-4 runs per week',
            'supporting': [
                'Set specific days/times for training',
                'Start with shorter distances and gradually increase',
                'Track adherence to schedule',
            ],
            'expected_outcome': 'Improved consistency index and training adaptation',
            'timeline': '2-4 weeks',
        },
        'declining_performance': {
            'primary': 'Reduce training intensity and increase recovery time',
            'supporting': [
                'Add 1-2 rest days per week',
                'Reduce pace by 10-15% for easy runs',
                'Monitor recovery metrics closely',
            ],
            'expected_outcome': 'Performance stabilization and recovery',
            'timeline': '1-2 weeks',
        },
        'low_durability': {
            'primary': 'Gradually increase training volume with careful monitoring',
            'supporting': [
                'Increase weekly distance by no more than 10% per week',
                'Focus on easy pace runs (80% of volume)',
                'Monitor for signs of injury or excessive fatigue',
            ],
            'expected_outcome': 'Improved durability index and injury prevention',
            'timeline': '4-6 weeks',
        },
        'slow_recovery': {
            'primary': 'Increase recovery time between intense sessions',
            'supporting': [
                'Ensure 48+ hours between hard workouts',
                'Prioritize sleep (7-9 hours)',
                'Consider active recovery (easy walks, stretching)',
            ],
            'expected_outcome': 'Reduced recovery half-life and improved adaptation',
            'timeline': '2-3 weeks',
        },
        'insufficient_training_data': {
            'primary': 'Continue training and data collection',
            'supporting': [
                'Maintain consistent activity logging',
                'Ensure all activities are synced',
            ],
            'expected_outcome': 'Sufficient data for analysis',
            'timeline': '2-4 weeks',
        },
    }
    
    if limiting_factor and limiting_factor in recommendation_map:
        rec_data = recommendation_map[limiting_factor]
        return {
            'primary_recommendation': rec_data['primary'],
            'supporting_actions': rec_data['supporting'],
            'expected_outcome': rec_data['expected_outcome'],
            'timeline': rec_data['timeline'],
            'confidence': hypothesis.get('confidence', 0.5),
        }
    
    return {
        'primary_recommendation': 'Continue monitoring and maintain current training approach',
        'supporting_actions': [],
        'expected_outcome': 'Stable performance',
        'timeline': 'Ongoing',
        'confidence': 0.5,
    }


# ============================================================================
# VALIDATE: Check Intervention Effectiveness
# ============================================================================

def validate_intervention(
    athlete: Athlete,
    db: Session,
    intervention_date: datetime,
    metric_to_track: str,
    expected_improvement: str
) -> Dict:
    """
    Validate: Check if interventions are having the desired effect.
    
    This step compares current metrics to pre-intervention baseline to
    determine if the recommended changes are working.
    
    Args:
        athlete: Athlete to validate
        db: Database session
        intervention_date: When the intervention was recommended
        metric_to_track: Which metric to track (e.g., 'consistency_index', 'performance_percentage')
        expected_improvement: What improvement was expected (e.g., 'increase', 'decrease', 'stabilize')
        
    Returns:
        Dictionary containing validation results:
        - is_effective: Whether intervention appears effective
        - current_value: Current value of tracked metric
        - baseline_value: Baseline value before intervention
        - change_percentage: Percentage change
        - recommendation: Next steps based on validation
    """
    # Get current metrics
    current_metrics = calculate_athlete_derived_signals(athlete, db, force_recalculate=False)
    
    # Get baseline (would need to store this - for now, use current as placeholder)
    baseline_value = current_metrics.get(metric_to_track)
    current_value = current_metrics.get(metric_to_track)
    
    # Calculate change
    if baseline_value and current_value:
        change_percentage = ((current_value - baseline_value) / baseline_value) * 100
    else:
        change_percentage = 0
    
    # Determine effectiveness based on expected improvement
    is_effective = False
    if expected_improvement == 'increase' and change_percentage > 0:
        is_effective = True
    elif expected_improvement == 'decrease' and change_percentage < 0:
        is_effective = True
    elif expected_improvement == 'stabilize' and abs(change_percentage) < 5:
        is_effective = True
    
    return {
        'is_effective': is_effective,
        'current_value': current_value,
        'baseline_value': baseline_value,
        'change_percentage': change_percentage,
        'metric_tracked': metric_to_track,
        'validation_date': datetime.now(timezone.utc),
        'days_since_intervention': (datetime.now(timezone.utc) - intervention_date).days,
        'recommendation': _generate_validation_recommendation(is_effective, change_percentage, expected_improvement),
    }


def _generate_validation_recommendation(is_effective: bool, change_percentage: float, expected_improvement: str) -> str:
    """Generate recommendation based on validation results."""
    if is_effective:
        return "Intervention appears effective. Continue current approach and monitor."
    elif abs(change_percentage) < 5:
        return "No significant change yet. Continue intervention for 1-2 more weeks before reassessing."
    else:
        return "Intervention may not be effective. Consider alternative approach or consult with coach."


# ============================================================================
# COMPLETE FEEDBACK LOOP
# ============================================================================

def run_complete_feedback_loop(athlete: Athlete, db: Session, lookback_days: int = 30) -> Dict:
    """
    Run the complete feedback loop: Observe -> Hypothesize -> Intervene -> Validate.
    
    This is the main entry point for the feedback loop system.
    
    Args:
        athlete: Athlete to analyze
        db: Database session
        lookback_days: Number of days to look back for observation
        
    Returns:
        Complete feedback loop results with all four stages
    """
    # Step 1: Observe
    observation = observe_athlete_data(athlete, db, lookback_days)
    
    # Step 2: Hypothesize
    hypothesis = hypothesize_limiting_factors(observation)
    
    # Step 3: Intervene
    intervention = intervene_recommendations(hypothesis, observation)
    
    # Step 4: Validate (if previous intervention exists)
    # For now, skip validation as we don't have stored intervention history
    # In production, this would check for previous interventions
    
    return {
        'athlete_id': str(athlete.id),
        'timestamp': datetime.now(timezone.utc),
        'observe': observation,
        'hypothesize': hypothesis,
        'intervene': intervention,
        'validate': None,  # Would be populated if previous intervention exists
    }


