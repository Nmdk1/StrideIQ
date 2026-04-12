"""
Run Attribution Service

Answers "Why This Run?" by analyzing a single activity and pulling
signals from all analytics methods.

ADR-015: Why This Run? Activity Attribution

Design Principles:
- Post-run learning: Help athlete understand what drove the result
- Pace Decay priority: For races/long runs, pacing tells the story
- N=1 patterns: Link to YOUR history, not generic advice
- Sparse tone: Non-prescriptive ("Data hints X. Test it.")
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional, Any
from enum import Enum
from uuid import UUID
import logging

from sqlalchemy.orm import Session

from models import Activity, DailyCheckin, ActivitySplit, CachedStreamAnalysis
from services.run_analysis_engine import CONTROLLED_STEADY_TYPES

logger = logging.getLogger(__name__)


class AttributionSource(str, Enum):
    """Sources for run attribution."""
    PACE_DECAY = "pace_decay"
    TSB = "tsb"
    PRE_STATE = "pre_state"
    EFFICIENCY = "efficiency"
    # CRITICAL_SPEED removed - archived to branch archive/cs-model-2026-01


class AttributionConfidence(str, Enum):
    """Confidence levels."""
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


@dataclass
class RunAttribution:
    """Single attribution for a run."""
    source: str
    priority: int
    confidence: str
    title: str
    insight: str
    icon: str
    color: str
    data: Dict[str, Any]


@dataclass
class RunAttributionResult:
    """Complete attribution result for a run."""
    activity_id: str
    activity_name: str
    attributions: List[RunAttribution]
    summary: Optional[str]
    generated_at: datetime


# Priority constants (lower = more important)
PRIORITY_PACE_DECAY = 1
PRIORITY_TSB = 2
PRIORITY_PRE_STATE = 3
PRIORITY_EFFICIENCY = 4
# PRIORITY_CRITICAL_SPEED removed - archived

# Maximum attributions to show
MAX_ATTRIBUTIONS = 5


def get_pace_decay_attribution(
    activity: Activity,
    db: Session
) -> Optional[RunAttribution]:
    """
    Get pace decay attribution for this run.

    Priority for races and long runs.
    """
    try:
        from services.pace_decay import (
            get_athlete_decay_profile
        )

        # Get splits for this activity
        splits = db.query(ActivitySplit).filter(
            ActivitySplit.activity_id == activity.id
        ).order_by(ActivitySplit.split_number).all()

        if len(splits) < 3:
            return None

        # Calculate decay for this run
        split_data = []
        for s in splits:
            if s.distance_m and s.elapsed_time_s and s.elapsed_time_s > 0:
                pace = s.elapsed_time_s / (s.distance_m / 1000)  # sec/km
                split_data.append({
                    "distance_m": s.distance_m,
                    "elapsed_time_s": s.elapsed_time_s,
                    "pace_per_km": pace
                })

        if len(split_data) < 3:
            return None

        # Calculate decay
        first_half = split_data[:len(split_data)//2]
        second_half = split_data[len(split_data)//2:]

        avg_first = sum(s["pace_per_km"] for s in first_half) / len(first_half)
        avg_second = sum(s["pace_per_km"] for s in second_half) / len(second_half)

        decay_pct = ((avg_second - avg_first) / avg_first) * 100 if avg_first > 0 else 0

        # Classify pattern
        if decay_pct < -2:
            pattern = "negative"
            title = "Negative Split"
            insight = f"Strong finish — pace improved {abs(decay_pct):.1f}% in second half. Elite execution."
            color = "emerald"
            confidence = AttributionConfidence.HIGH
        elif decay_pct <= 3:
            pattern = "even"
            title = "Even Pacing"
            insight = f"Decay {decay_pct:.1f}% — controlled execution. Good pacing discipline."
            color = "green"
            confidence = AttributionConfidence.HIGH
        elif decay_pct <= 8:
            pattern = "moderate_positive"
            title = "Moderate Fade"
            insight = f"Pace faded {decay_pct:.1f}% — typical for effort level. Room to improve."
            color = "yellow"
            confidence = AttributionConfidence.MODERATE
        else:
            pattern = "severe_positive"
            title = "Significant Fade"
            insight = f"Pace faded {decay_pct:.1f}% — suggests went out too fast or fueling issue."
            color = "orange"
            confidence = AttributionConfidence.HIGH

        # Compare to historical if available
        try:
            profile = get_athlete_decay_profile(str(activity.athlete_id), db)
            if profile.total_races_analyzed > 3:
                avg_historical = profile.overall_avg_decay
                if decay_pct < avg_historical - 2:
                    insight += f" Better than your avg ({avg_historical:.1f}%)."
                elif decay_pct > avg_historical + 2:
                    insight += f" Worse than your avg ({avg_historical:.1f}%)."
        except Exception:
            pass

        return RunAttribution(
            source=AttributionSource.PACE_DECAY.value,
            priority=PRIORITY_PACE_DECAY,
            confidence=confidence.value,
            title=title,
            insight=insight,
            icon="timer",
            color=color,
            data={
                "decay_percent": round(decay_pct, 1),
                "pattern": pattern,
                "splits_analyzed": len(split_data)
            }
        )

    except Exception as e:
        logger.warning(f"Error in pace decay attribution: {e}")
        return None


def get_tsb_attribution(
    athlete_id: str,
    activity_date: date,
    db: Session
) -> Optional[RunAttribution]:
    """
    Get TSB attribution — was form optimal?
    """
    try:
        from services.training_load import TrainingLoadCalculator, TSBZone

        calculator = TrainingLoadCalculator(db)
        athlete_uuid = UUID(athlete_id)
        load = calculator.calculate_training_load(athlete_uuid)

        if not load or load.current_ctl < 20:
            return None

        tsb = load.current_tsb
        zone_info = calculator.get_tsb_zone(tsb, athlete_id=athlete_uuid)

        if zone_info.zone == TSBZone.RACE_READY:
            title = "Peak Form"
            insight = f"TSB +{int(tsb)} — optimal freshness zone. Good timing for hard effort."
            color = "green"
            confidence = AttributionConfidence.HIGH
        elif zone_info.zone == TSBZone.FRESH:
            title = "Fresh"
            insight = f"TSB +{int(tsb)} — rested but fitness building. Good for quality work."
            color = "blue"
            confidence = AttributionConfidence.MODERATE
        elif zone_info.zone == TSBZone.NEUTRAL:
            title = "Balanced"
            insight = f"TSB {int(tsb)} — balanced load. Typical training state."
            color = "slate"
            confidence = AttributionConfidence.LOW
        elif zone_info.zone == TSBZone.OVERREACHING:
            title = "Under Load"
            insight = f"TSB {int(tsb)} — building fatigue. Expected for build phase."
            color = "yellow"
            confidence = AttributionConfidence.MODERATE
        else:  # OVERTRAINING_RISK
            title = "Fatigued"
            insight = f"TSB {int(tsb)} — high fatigue. May explain sub-par performance."
            color = "orange"
            confidence = AttributionConfidence.HIGH

        return RunAttribution(
            source=AttributionSource.TSB.value,
            priority=PRIORITY_TSB,
            confidence=confidence.value,
            title=title,
            insight=insight,
            icon="battery",
            color=color,
            data={
                "tsb": round(tsb, 1),
                "atl": round(load.current_atl, 1),
                "ctl": round(load.current_ctl, 1),
                "zone": zone_info.zone.value
            }
        )

    except Exception as e:
        logger.warning(f"Error in TSB attribution: {e}")
        return None


def get_pre_state_attribution(
    athlete_id: str,
    activity_date: date,
    db: Session
) -> Optional[RunAttribution]:
    """
    Get pre-run state attribution — did pre-run state match success patterns?
    """
    try:
        from services.pre_race_fingerprinting import generate_readiness_profile

        # Get check-in from activity day
        checkin = db.query(DailyCheckin).filter(
            DailyCheckin.athlete_id == athlete_id,
            DailyCheckin.date == activity_date
        ).first()

        if not checkin:
            return None

        # Get readiness profile
        profile = generate_readiness_profile(athlete_id, db)

        if not profile or profile.confidence_level == "insufficient":
            return None

        # Count matching factors
        matching = []
        if checkin.sleep_h is not None and float(checkin.sleep_h) >= 7:
            matching.append("sleep")
        if checkin.hrv_rmssd is not None:
            matching.append("hrv")
        if checkin.stress_1_5 is not None and checkin.stress_1_5 <= 3:
            matching.append("low_stress")

        match_count = len(matching)
        total_factors = 3
        match_pct = (match_count / total_factors) * 100

        if match_pct >= 80:
            title = "Optimal State"
            insight = f"Pre-run state matches your PR fingerprint ({int(match_pct)}% match)."
            color = "emerald"
            confidence = AttributionConfidence.HIGH
        elif match_pct >= 50:
            title = "Good State"
            insight = f"Pre-run state partially matches success patterns ({int(match_pct)}% match)."
            color = "blue"
            confidence = AttributionConfidence.MODERATE
        else:
            title = "Suboptimal State"
            insight = f"Pre-run state differs from your success patterns ({int(match_pct)}% match)."
            color = "yellow"
            confidence = AttributionConfidence.MODERATE

        return RunAttribution(
            source=AttributionSource.PRE_STATE.value,
            priority=PRIORITY_PRE_STATE,
            confidence=confidence.value,
            title=title,
            insight=insight,
            icon="target",
            color=color,
            data={
                "match_percent": match_pct,
                "matching_factors": matching,
                "sleep_h": float(checkin.sleep_h) if checkin.sleep_h is not None else None,
                "hrv_rmssd": float(checkin.hrv_rmssd) if checkin.hrv_rmssd is not None else None
            }
        )

    except Exception as e:
        logger.warning(f"Error in pre-state attribution: {e}")
        return None


def _compute_gap_efficiency(activity: Activity, db: Session) -> tuple:
    """
    Compute Efficiency Factor (EF) using GAP from splits.

    EF = speed / HR (higher = better).

    Speed is in meters per second, derived from GAP (Grade Adjusted Pace)
    when available, or raw pace as fallback. GAP normalizes for elevation
    so hilly runs aren't penalized for slower raw pace.

    A 20-miler at 122 bpm with 2300ft climbing and GAP of 8:10/mi is
    extremely efficient — high speed-per-heartbeat.

    Returns (ef_value, used_gap: bool). Higher EF = more efficient.
    """
    avg_hr = float(activity.avg_hr)

    # Try to get GAP from splits
    splits = db.query(ActivitySplit).filter(
        ActivitySplit.activity_id == activity.id,
        ActivitySplit.gap_seconds_per_mile.isnot(None),
        ActivitySplit.distance.isnot(None),
    ).all()

    if splits and len(splits) >= 2:
        # Distance-weighted average GAP
        total_dist = 0.0
        weighted_gap = 0.0
        for s in splits:
            dist = float(s.distance) if s.distance else 0
            gap = float(s.gap_seconds_per_mile) if s.gap_seconds_per_mile else 0
            if dist > 0 and gap > 0:
                weighted_gap += gap * dist
                total_dist += dist

        if total_dist > 0:
            avg_gap_spm = weighted_gap / total_dist  # seconds per mile
            # Convert GAP to speed: meters per second
            speed_mps = 1609.34 / avg_gap_spm
            return speed_mps / avg_hr, True

    # Fallback: raw speed / HR
    speed_mps = activity.distance_m / activity.duration_s
    return speed_mps / avg_hr, False


def _get_cached_cardiac_decoupling(activity_id, db: Session) -> Optional[float]:
    """Fetch cardiac decoupling % from cached stream analysis. Returns None if unavailable."""
    from services.stream_analysis_cache import CURRENT_ANALYSIS_VERSION

    row = (
        db.query(CachedStreamAnalysis.result_json)
        .filter(
            CachedStreamAnalysis.activity_id == activity_id,
            CachedStreamAnalysis.analysis_version == CURRENT_ANALYSIS_VERSION,
        )
        .first()
    )
    if row is None:
        return None

    result = row[0]
    drift = result.get("drift") if result else None
    if drift is None:
        return None

    return drift.get("cardiac_pct")


def _get_decoupling_attribution(
    activity: Activity,
    db: Session,
) -> Optional[RunAttribution]:
    """
    Evaluate controlled-steady runs by cardiac decoupling instead of speed/HR.

    Cardiac decoupling measures whether HR drifted upward relative to pace.
    Low decoupling = aerobic system handled the effort well.
    High decoupling = body was working harder over time to maintain pace.

    This is the right metric for easy, recovery, pacing, and marathon-pace runs
    regardless of how hard the effort was. A pacer at 7:00/mi and 9:30/mi
    should both be evaluated on "did HR stay stable relative to pace?"
    """
    decoupling = _get_cached_cardiac_decoupling(activity.id, db)
    if decoupling is None:
        return None

    abs_decouple = abs(decoupling)

    if abs_decouple <= 3.0:
        title = "Well Coupled"
        insight = f"HR stayed stable relative to pace ({decoupling:+.1f}% drift). Aerobically controlled."
        color = "emerald"
        confidence = AttributionConfidence.HIGH
    elif abs_decouple <= 5.0:
        title = "Normal Coupling"
        insight = f"HR drifted {decoupling:+.1f}% — typical for this effort length."
        color = "green"
        confidence = AttributionConfidence.MODERATE
    elif abs_decouple <= 8.0:
        title = "Moderate Drift"
        insight = f"HR drifted {decoupling:+.1f}% relative to pace. May indicate cumulative fatigue or heat."
        color = "yellow"
        confidence = AttributionConfidence.MODERATE
    else:
        title = "Significant Drift"
        insight = f"HR drifted {decoupling:+.1f}% — body worked progressively harder to hold pace."
        color = "orange"
        confidence = AttributionConfidence.HIGH

    return RunAttribution(
        source=AttributionSource.EFFICIENCY.value,
        priority=PRIORITY_EFFICIENCY,
        confidence=confidence.value,
        title=title,
        insight=insight,
        icon="heart-pulse",
        color=color,
        data={
            "cardiac_decoupling_pct": round(decoupling, 1),
            "method": "cardiac_decoupling",
        },
    )


def _is_controlled_steady(activity: Activity) -> bool:
    """Check if this activity's stored workout_type is a controlled-steady effort."""
    wt = getattr(activity, "workout_type", None)
    return bool(wt and wt.lower() in CONTROLLED_STEADY_TYPES)


def get_efficiency_attribution(
    activity: Activity,
    db: Session
) -> Optional[RunAttribution]:
    """
    Get efficiency attribution — was this run more/less efficient than trend?

    For CONTROLLED-STEADY runs (easy, recovery, pacing, marathon pace, long):
      Uses cardiac decoupling — did HR stay stable relative to pace?
      If decoupling data unavailable, suppress entirely (silence > wrong).

    For STRUCTURED-QUALITY / RACE / other runs:
      Uses speed/HR efficiency compared against similar runs (same type + distance).
      Only falls through to Tier 1 or Tier 2 comparisons. Tiers 3/4 (distance-only
      or all-recent-runs) are suppressed — apples-to-oranges is worse than silence.
    """
    try:
        if not activity.avg_hr or not activity.distance_m or not activity.duration_s:
            return None

        if activity.avg_hr < 100 or activity.distance_m < 1000:
            return None

        # Route controlled-steady runs to cardiac decoupling evaluation
        if _is_controlled_steady(activity):
            return _get_decoupling_attribution(activity, db)

        efficiency, used_gap = _compute_gap_efficiency(activity, db)

        dist_lo = activity.distance_m * 0.70
        dist_hi = activity.distance_m * 1.30

        end_date = activity.start_time.date()
        start_date_similar = end_date - timedelta(days=90)

        base_filter = [
            Activity.athlete_id == activity.athlete_id,
            Activity.id != activity.id,
            Activity.avg_hr.isnot(None),
            Activity.avg_hr > 100,
            Activity.distance_m > 1000,
            Activity.duration_s > 0,
        ]

        # ---- Tier 1: Same workout type + similar distance (90 days) ----
        similar_activities = []
        comparison_label = "similar runs"

        if activity.workout_type:
            similar_activities = db.query(Activity).filter(
                *base_filter,
                Activity.start_time >= start_date_similar,
                Activity.start_time < end_date,
                Activity.workout_type == activity.workout_type,
                Activity.distance_m >= dist_lo,
                Activity.distance_m <= dist_hi,
            ).all()
            if len(similar_activities) >= 2:
                wt_label = activity.workout_type.lower().replace('_', ' ')
                comparison_label = f"your recent {wt_label}s"

        # ---- Tier 2: Same workout type, any distance (90 days) ----
        if len(similar_activities) < 2 and activity.workout_type:
            similar_activities = db.query(Activity).filter(
                *base_filter,
                Activity.start_time >= start_date_similar,
                Activity.start_time < end_date,
                Activity.workout_type == activity.workout_type,
            ).all()
            if len(similar_activities) >= 2:
                wt_label = activity.workout_type.lower().replace('_', ' ')
                comparison_label = f"your recent {wt_label}s"

        # Tiers 3/4 suppressed: comparing across workout types or all runs
        # produces misleading efficiency claims. Silence > wrong.
        if len(similar_activities) < 2:
            return None

        recent_efficiencies = []
        for act in similar_activities:
            eff, _ = _compute_gap_efficiency(act, db)
            recent_efficiencies.append(eff)

        avg_efficiency = sum(recent_efficiencies) / len(recent_efficiencies)

        diff_pct = ((efficiency - avg_efficiency) / avg_efficiency) * 100

        if diff_pct > 5:
            title = "Very Efficient"
            insight = f"Efficiency {diff_pct:.1f}% better than {comparison_label}."
            color = "emerald"
            confidence = AttributionConfidence.HIGH
        elif diff_pct > 2:
            title = "Efficient"
            insight = f"Efficiency {diff_pct:.1f}% better than {comparison_label}. Good form."
            color = "green"
            confidence = AttributionConfidence.MODERATE
        elif diff_pct >= -2:
            title = "Typical Efficiency"
            insight = f"Efficiency in line with your {comparison_label}."
            color = "slate"
            confidence = AttributionConfidence.LOW
        elif diff_pct >= -5:
            title = "Slightly Below Average"
            insight = f"Efficiency {abs(diff_pct):.1f}% below {comparison_label}."
            color = "yellow"
            confidence = AttributionConfidence.MODERATE
        else:
            title = "Below Average"
            insight = f"Efficiency {abs(diff_pct):.1f}% below {comparison_label}."
            color = "orange"
            confidence = AttributionConfidence.MODERATE

        return RunAttribution(
            source=AttributionSource.EFFICIENCY.value,
            priority=PRIORITY_EFFICIENCY,
            confidence=confidence.value,
            title=title,
            insight=insight,
            icon="gauge",
            color=color,
            data={
                "efficiency": round(efficiency, 4),
                "avg_efficiency": round(avg_efficiency, 4),
                "diff_percent": round(diff_pct, 1),
                "sample_size": len(similar_activities),
                "comparison": comparison_label,
                "method": "gap" if used_gap else "raw_pace",
            }
        )

    except Exception as e:
        logger.warning(f"Error in efficiency attribution: {e}")
        return None


# get_cs_attribution REMOVED - archived to branch archive/cs-model-2026-01


def generate_summary(attributions: List[RunAttribution]) -> Optional[str]:
    """
    Generate a one-sentence summary from attributions.
    """
    if not attributions:
        return None

    # Find primary attribution
    primary = attributions[0]

    summaries = {
        "pace_decay": {
            "negative": "Strong negative split execution.",
            "even": "Controlled pacing with good execution.",
            "moderate_positive": "Typical pacing with room to improve.",
            "severe_positive": "Pacing broke down — consider fueling or start pace."
        },
        "tsb": {
            "race_ready": "Peak form contributed to good performance.",
            "fresh": "Fresh legs supported this effort.",
            "neutral": "Balanced training state.",
            "overreaching": "Building fatigue — expected in build phase.",
            "overtraining_risk": "High fatigue may have impacted performance."
        }
    }

    # Try to build summary from primary
    if primary.source == "pace_decay":
        pattern = primary.data.get("pattern", "even")
        return summaries["pace_decay"].get(pattern, "Pacing analyzed.")
    elif primary.source == "tsb":
        zone = primary.data.get("zone", "neutral")
        return summaries["tsb"].get(zone, "Form analyzed.")

    return f"{primary.title}: {primary.insight.split('.')[0]}."


def get_run_attribution(
    activity_id: str,
    athlete_id: str,
    db: Session
) -> Optional[RunAttributionResult]:
    """
    Main function: Get complete attribution analysis for a run.

    Args:
        activity_id: Activity UUID string
        athlete_id: Athlete UUID string
        db: Database session

    Returns:
        RunAttributionResult or None
    """
    # Get the activity
    activity = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.athlete_id == athlete_id
    ).first()

    if not activity:
        return None

    activity_date = activity.start_time.date()

    # Collect attributions from all sources
    attributions: List[RunAttribution] = []

    # 1. Pace Decay (priority for races/long runs)
    pace_attr = get_pace_decay_attribution(activity, db)
    if pace_attr:
        attributions.append(pace_attr)

    # 2. TSB Status
    tsb_attr = get_tsb_attribution(str(athlete_id), activity_date, db)
    if tsb_attr:
        attributions.append(tsb_attr)

    # 3. Pre-Run State
    pre_attr = get_pre_state_attribution(str(athlete_id), activity_date, db)
    if pre_attr:
        attributions.append(pre_attr)

    # 4. Efficiency vs Trend
    eff_attr = get_efficiency_attribution(activity, db)
    if eff_attr:
        attributions.append(eff_attr)

    # CS attribution removed - archived to branch archive/cs-model-2026-01

    # Sort by priority
    attributions.sort(key=lambda a: (a.priority, a.confidence != AttributionConfidence.HIGH.value))

    # Limit to max
    attributions = attributions[:MAX_ATTRIBUTIONS]

    # Generate summary
    summary = generate_summary(attributions)

    return RunAttributionResult(
        activity_id=str(activity.id),
        activity_name=activity.name or "Run",
        attributions=attributions,
        summary=summary,
        generated_at=datetime.utcnow()
    )


def run_attribution_to_dict(result: RunAttributionResult) -> Dict[str, Any]:
    """Convert RunAttributionResult to dictionary for API response."""
    return {
        "activity_id": result.activity_id,
        "activity_name": result.activity_name,
        "attributions": [
            {
                "source": a.source,
                "priority": a.priority,
                "confidence": a.confidence,
                "title": a.title,
                "insight": a.insight,
                "icon": a.icon,
                "color": a.color,
                "data": a.data
            }
            for a in result.attributions
        ],
        "summary": result.summary,
        "generated_at": result.generated_at.isoformat()
    }
