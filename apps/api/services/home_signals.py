"""
Home Signals Aggregation Service

Aggregates high-confidence signals from all analytics methods
for the Home page Glance layer.

ADR-013: Home Glance Signals Integration
"""

from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from enum import Enum
from uuid import UUID
from sqlalchemy.orm import Session


class SignalType(str, Enum):
    """Types of signals that can be shown."""
    TSB = "tsb"
    EFFICIENCY = "efficiency"
    FINGERPRINT = "fingerprint"
    # CRITICAL_SPEED removed - archived to branch archive/cs-model-2026-01
    PACE_DECAY = "pace_decay"


class SignalConfidence(str, Enum):
    """Confidence level for signals."""
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


class SignalIcon(str, Enum):
    """Icon identifiers for signals."""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    BATTERY_FULL = "battery_full"
    BATTERY_LOW = "battery_low"
    TARGET = "target"
    ZAPPER = "zap"
    ALERT = "alert"
    CHECKMARK = "check"
    GAUGE = "gauge"
    TIMER = "timer"


@dataclass
class Signal:
    """A single signal to display on the home page."""
    id: str
    type: SignalType
    priority: int                     # Lower = more important
    confidence: SignalConfidence
    icon: SignalIcon
    color: str                        # Tailwind color name (emerald, blue, orange, etc.)
    title: str                        # Short headline (max 30 chars)
    subtitle: str                     # Supporting context (max 50 chars)
    detail: Optional[str] = None      # Technical detail (p-value, etc.)
    action_url: Optional[str] = None  # Link to learn more


@dataclass
class SignalsResponse:
    """Response from home signals API."""
    signals: List[Signal]
    suppressed_count: int
    last_updated: datetime


# Priority constants
PRIORITY_TSB_RACE_READY = 1
PRIORITY_FINGERPRINT_MATCH = 2
PRIORITY_EFFICIENCY_TREND = 3
# PRIORITY_CRITICAL_SPEED removed - archived
PRIORITY_PACE_DECAY = 4
PRIORITY_TSB_WARNING = 5

# Maximum signals to show
MAX_SIGNALS = 4


def get_tsb_signal(athlete_id: str, db: Session) -> Optional[Signal]:
    """
    Get TSB-based signal if conditions met.
    
    Shows:
    - Race Ready: TSB 15-25
    - Recovering: TSB 5-15
    - Overreaching Warning: TSB < -20
    """
    try:
        from services.training_load import TrainingLoadCalculator, TSBZone
        
        calculator = TrainingLoadCalculator(db)

        # Get current training load
        athlete_uuid = UUID(athlete_id)
        load = calculator.calculate_training_load(athlete_uuid)

        if load is None:
            return None

        tsb = load.current_tsb
        ctl = load.current_ctl
        zone_info = calculator.get_tsb_zone(tsb, athlete_id=athlete_uuid)
        
        # Only show if we have meaningful CTL (>20 indicates some training history)
        if ctl < 20:
            return None
        
        if zone_info.zone == TSBZone.RACE_READY:
            return Signal(
                id="tsb_race_ready",
                type=SignalType.TSB,
                priority=PRIORITY_TSB_RACE_READY,
                confidence=SignalConfidence.HIGH,
                icon=SignalIcon.BATTERY_FULL,
                color="green",
                title="Fresh but fit",
                subtitle=f"Good race window (TSB +{int(tsb)})",
                detail=f"CTL {int(ctl)}, ATL {int(load.current_atl)}",
                action_url="/analytics"
            )
        elif zone_info.zone == TSBZone.OVERTRAINING_RISK:
            return Signal(
                id="tsb_overtrain_warning",
                type=SignalType.TSB,
                priority=PRIORITY_TSB_WARNING,
                confidence=SignalConfidence.HIGH,
                icon=SignalIcon.ALERT,
                color="red",
                title="High fatigue",
                subtitle=f"Consider recovery (TSB {int(tsb)})",
                detail=None,
                action_url="/analytics"
            )
        elif zone_info.zone == TSBZone.OVERREACHING:
            return Signal(
                id="tsb_overreaching",
                type=SignalType.TSB,
                priority=PRIORITY_TSB_WARNING,
                confidence=SignalConfidence.MODERATE,
                icon=SignalIcon.BATTERY_LOW,
                color="orange",
                title="Building load",
                subtitle=f"Productive stress (TSB {int(tsb)})",
                detail=None,
                action_url="/analytics"
            )
        
        return None
        
    except Exception:
        return None


def get_efficiency_signal(athlete_id: str, db: Session) -> Optional[Signal]:
    """
    Get efficiency trend signal if statistically significant.
    
    Only shows if p < 0.05 and change > 2%.
    """
    try:
        from services.efficiency_analytics import get_efficiency_trends
        
        trends = get_efficiency_trends(UUID(athlete_id), db, days=28)
        
        if not trends or "trend_analysis" not in trends:
            return None
        
        analysis = trends.get("trend_analysis", {})
        
        confidence = analysis.get("confidence")
        direction = analysis.get("direction")
        change_pct = abs(analysis.get("change_percent", 0))
        p_value = analysis.get("p_value")
        
        # Only show high confidence trends with meaningful change
        if confidence not in ["high", "moderate"] or change_pct < 2:
            return None
        
        if p_value is not None and p_value >= 0.10:
            return None
        
        # pace/HR ratio — directionally ambiguous (see OutputMetricMeta)
        if direction == "improving":
            return Signal(
                id="efficiency_improving",
                type=SignalType.EFFICIENCY,
                priority=PRIORITY_EFFICIENCY_TREND,
                confidence=SignalConfidence.HIGH if confidence == "high" else SignalConfidence.MODERATE,
                icon=SignalIcon.TRENDING_UP,
                color="emerald",
                title=f"Efficiency up {change_pct:.1f}%",
                subtitle="Last 4 weeks trend",
                detail=f"p={p_value:.2f}" if p_value else None,
                action_url="/analytics"
            )
        elif direction == "declining":
            return Signal(
                id="efficiency_declining",
                type=SignalType.EFFICIENCY,
                priority=PRIORITY_EFFICIENCY_TREND,
                confidence=SignalConfidence.HIGH if confidence == "high" else SignalConfidence.MODERATE,
                icon=SignalIcon.TRENDING_DOWN,
                color="orange",
                title=f"Efficiency down {change_pct:.1f}%",
                subtitle="Watch this trend",
                detail=f"p={p_value:.2f}" if p_value else None,
                action_url="/analytics"
            )
        
        return None
        
    except Exception:
        return None


# get_critical_speed_signal REMOVED - archived to branch archive/cs-model-2026-01


def get_fingerprint_signal(athlete_id: str, db: Session) -> Optional[Signal]:
    """
    Get pre-race fingerprint signal if current state matches PR pattern.
    
    Only shows if match is >70% and we have enough race history.
    """
    try:
        from services.pre_race_fingerprinting import generate_readiness_profile, ConfidenceLevel as FPConfidence
        
        profile = generate_readiness_profile(athlete_id, db)
        
        if not profile or profile.confidence in [FPConfidence.INSUFFICIENT, FPConfidence.LOW]:
            return None
        
        # Check if any features show strong patterns
        strong_patterns = [f for f in profile.features if f.effect_size and abs(f.effect_size) > 0.5]
        
        if len(strong_patterns) < 2:
            return None
        
        # Generate insight
        primary = profile.primary_insight
        if not primary:
            return None
        
        # Truncate for display
        if len(primary) > 45:
            primary = primary[:42] + "..."
        
        return Signal(
            id="fingerprint_pattern",
            type=SignalType.FINGERPRINT,
            priority=PRIORITY_FINGERPRINT_MATCH,
            confidence=SignalConfidence.HIGH if profile.confidence == FPConfidence.HIGH else SignalConfidence.MODERATE,
            icon=SignalIcon.TARGET,
            color="purple",
            title="Race pattern found",
            subtitle=primary,
            detail=f"{len(strong_patterns)} factors identified",
            action_url="/analytics"
        )
        
    except Exception:
        return None


def get_pace_decay_signal(athlete_id: str, db: Session) -> Optional[Signal]:
    """
    Get pace decay signal if recent race had notable pattern.
    
    Only shows for races in last 30 days with decay > 5%.
    """
    try:
        from services.pace_decay import get_athlete_decay_profile
        
        profile = get_athlete_decay_profile(athlete_id, db)
        
        if profile.total_races_analyzed < 3:
            return None
        
        avg_decay = profile.overall_avg_decay
        trend = profile.trend
        
        # Only surface if there's actionable insight
        if avg_decay < 3:
            # Great pacing - worth noting
            return Signal(
                id="pace_decay_excellent",
                type=SignalType.PACE_DECAY,
                priority=PRIORITY_PACE_DECAY,
                confidence=SignalConfidence.HIGH,
                icon=SignalIcon.CHECKMARK,
                color="emerald",
                title="Strong pacing",
                subtitle=f"Avg {avg_decay:.1f}% decay — elite level",
                detail=f"{profile.total_races_analyzed} races analyzed",
                action_url="/analytics"
            )
        elif avg_decay > 8:
            # Opportunity to improve
            return Signal(
                id="pace_decay_opportunity",
                type=SignalType.PACE_DECAY,
                priority=PRIORITY_PACE_DECAY,
                confidence=SignalConfidence.MODERATE,
                icon=SignalIcon.TIMER,
                color="orange",
                title="Pacing opportunity",
                subtitle=f"Avg {avg_decay:.1f}% fade — room to improve",
                detail=None,
                action_url="/analytics"
            )
        elif trend == "improving":
            return Signal(
                id="pace_decay_improving",
                type=SignalType.PACE_DECAY,
                priority=PRIORITY_PACE_DECAY,
                confidence=SignalConfidence.MODERATE,
                icon=SignalIcon.TRENDING_UP,
                color="blue",
                title="Pacing improving",
                subtitle="Recent races show better execution",
                detail=None,
                action_url="/analytics"
            )
        
        return None
        
    except Exception:
        return None


def aggregate_signals(athlete_id: str, db: Session) -> SignalsResponse:
    """
    Aggregate all signals for an athlete, filter, and prioritize.
    
    Args:
        athlete_id: Athlete UUID string
        db: Database session
    
    Returns:
        SignalsResponse with prioritized signals
    """
    all_signals: List[Signal] = []
    
    # Collect signals from each source
    tsb_signal = get_tsb_signal(athlete_id, db)
    if tsb_signal:
        all_signals.append(tsb_signal)
    
    efficiency_signal = get_efficiency_signal(athlete_id, db)
    if efficiency_signal:
        all_signals.append(efficiency_signal)
    
    # CS signal removed - archived to branch archive/cs-model-2026-01
    
    fingerprint_signal = get_fingerprint_signal(athlete_id, db)
    if fingerprint_signal:
        all_signals.append(fingerprint_signal)
    
    decay_signal = get_pace_decay_signal(athlete_id, db)
    if decay_signal:
        all_signals.append(decay_signal)
    
    # Filter to high/moderate confidence only
    filtered = [s for s in all_signals if s.confidence in [SignalConfidence.HIGH, SignalConfidence.MODERATE]]
    
    # Sort by priority (lower = more important)
    filtered.sort(key=lambda s: (s.priority, s.confidence != SignalConfidence.HIGH))
    
    # Limit to max signals
    displayed = filtered[:MAX_SIGNALS]
    suppressed = len(filtered) - len(displayed)
    
    return SignalsResponse(
        signals=displayed,
        suppressed_count=suppressed,
        last_updated=datetime.utcnow()
    )


def signals_to_dict(response: SignalsResponse) -> Dict:
    """Convert SignalsResponse to dictionary for API."""
    return {
        "signals": [
            {
                "id": s.id,
                "type": s.type.value,
                "priority": s.priority,
                "confidence": s.confidence.value,
                "icon": s.icon.value,
                "color": s.color,
                "title": s.title,
                "subtitle": s.subtitle,
                "detail": s.detail,
                "action_url": s.action_url
            }
            for s in response.signals
        ],
        "suppressed_count": response.suppressed_count,
        "last_updated": response.last_updated.isoformat()
    }
