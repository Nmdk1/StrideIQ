"""
Pre-Race State Fingerprinting Service

Discovers YOUR personal readiness patterns by comparing physiological state
before your BEST vs WORST races.

ADR-009: Pre-Race State Fingerprinting

Key Insight (from user data):
> "My best races were after the evening of my lowest HRV"

This contradicts conventional wisdom. The algorithm discovers YOUR patterns,
not population averages.
"""

from datetime import datetime, timedelta, date
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import statistics
import math
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, func


class RaceCategory(str, Enum):
    """Race performance category based on age-graded percentage."""
    BEST = "best"           # Top 25%
    GOOD = "good"           # 50-75th percentile
    AVERAGE = "average"     # 25-50th percentile
    WORST = "worst"         # Bottom 25%


class PatternType(str, Enum):
    """Type of pattern discovered."""
    CONVENTIONAL = "conventional"      # Matches typical wisdom (high HRV = good)
    INVERTED = "inverted"             # Opposite of typical wisdom
    NO_PATTERN = "no_pattern"         # No significant relationship


@dataclass
class PreRaceState:
    """Captured state before a race."""
    race_id: str
    race_date: date
    performance_pct: float  # Age-graded percentage
    
    # HRV metrics (deviation from 30-day baseline)
    hrv_rmssd: Optional[float] = None
    hrv_deviation_pct: Optional[float] = None
    
    # Sleep
    sleep_hours: Optional[float] = None
    
    # Heart rate
    resting_hr: Optional[int] = None
    resting_hr_deviation_pct: Optional[float] = None
    
    # Subjective
    stress_level: Optional[int] = None  # 1-5
    soreness_level: Optional[int] = None  # 1-5
    motivation: Optional[int] = None  # 1-5
    confidence: Optional[int] = None  # 1-5
    
    # Training context
    days_since_hard_workout: Optional[int] = None
    training_load_7d: Optional[float] = None  # ATL


@dataclass
class FeatureAnalysis:
    """Statistical analysis of a single feature."""
    feature_name: str
    best_mean: Optional[float]
    best_std: Optional[float]
    worst_mean: Optional[float]
    worst_std: Optional[float]
    difference: Optional[float]  # best_mean - worst_mean
    p_value: Optional[float]
    cohens_d: Optional[float]
    is_significant: bool
    pattern_type: PatternType
    insight_text: str


@dataclass
class ReadinessProfile:
    """Complete readiness fingerprint for an athlete."""
    athlete_id: str
    total_races: int
    races_with_data: int
    best_races_count: int
    worst_races_count: int
    features: List[FeatureAnalysis]
    primary_insight: Optional[str]
    optimal_ranges: Dict[str, Tuple[float, float]]  # feature -> (min, max)
    has_counter_conventional_findings: bool
    confidence_level: str  # "high", "moderate", "low", "insufficient"


def mann_whitney_u_test(x: List[float], y: List[float]) -> Tuple[float, float]:
    """
    Mann-Whitney U test for comparing two independent samples.
    Non-parametric alternative to t-test.
    
    Returns:
        u_stat: U statistic
        p_value: Two-tailed p-value (approximated)
    """
    n1, n2 = len(x), len(y)
    
    if n1 < 2 or n2 < 2:
        return 0, 1.0
    
    # Combine and rank
    combined = [(val, 'x') for val in x] + [(val, 'y') for val in y]
    combined.sort(key=lambda item: item[0])
    
    # Assign ranks (handle ties by averaging)
    ranks = {}
    i = 0
    while i < len(combined):
        j = i
        while j < len(combined) and combined[j][0] == combined[i][0]:
            j += 1
        avg_rank = (i + 1 + j) / 2
        for k in range(i, j):
            if combined[k] not in ranks:
                ranks[combined[k]] = []
            ranks[combined[k]].append(avg_rank)
        i = j
    
    # Calculate rank sums
    rank_sum_x = sum(i + 1 for i, (val, group) in enumerate(combined) if group == 'x')
    
    # Calculate U statistic
    u1 = rank_sum_x - (n1 * (n1 + 1)) / 2
    u2 = n1 * n2 - u1
    u = min(u1, u2)
    
    # Normal approximation for p-value (valid for n1, n2 >= 8)
    mean_u = n1 * n2 / 2
    std_u = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)
    
    if std_u == 0:
        return u, 1.0
    
    z = (u - mean_u) / std_u
    
    # Approximate p-value from z-score
    p_value = 2 * (1 - _norm_cdf(abs(z)))
    
    return u, min(1.0, max(0.0, p_value))


def _norm_cdf(z: float) -> float:
    """Standard normal CDF approximation."""
    z = max(-37, min(37, z))
    
    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911
    
    sign = 1 if z >= 0 else -1
    z = abs(z)
    
    t = 1.0 / (1.0 + p * z)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-z * z / 2)
    
    return 0.5 * (1.0 + sign * y)


def calculate_cohens_d(x: List[float], y: List[float]) -> Optional[float]:
    """
    Calculate Cohen's d effect size.
    
    Interpretation:
    - |d| < 0.2: negligible
    - 0.2 <= |d| < 0.5: small
    - 0.5 <= |d| < 0.8: medium
    - |d| >= 0.8: large
    """
    if len(x) < 2 or len(y) < 2:
        return None
    
    mean_x = statistics.mean(x)
    mean_y = statistics.mean(y)
    
    var_x = statistics.variance(x)
    var_y = statistics.variance(y)
    
    n_x, n_y = len(x), len(y)
    
    # Pooled standard deviation
    pooled_var = ((n_x - 1) * var_x + (n_y - 1) * var_y) / (n_x + n_y - 2)
    pooled_std = math.sqrt(pooled_var) if pooled_var > 0 else 0.001
    
    return (mean_x - mean_y) / pooled_std


def extract_pre_race_state(
    race,  # Activity object
    db: Session,
    lookback_days: int = 2
) -> Optional[PreRaceState]:
    """
    Extract physiological state from 24-72 hours before a race.
    
    Args:
        race: Activity marked as race
        db: Database session
        lookback_days: Days before race to check (default 2 = race eve + day before)
    
    Returns:
        PreRaceState or None if insufficient data
    """
    from models import Activity, DailyCheckin
    
    race_date = race.start_time.date()
    
    # Performance percentage (age-graded)
    performance_pct = None
    if race.performance_percentage:
        performance_pct = float(race.performance_percentage)
    elif race.performance_percentage_national:
        performance_pct = float(race.performance_percentage_national)
    
    if performance_pct is None:
        return None  # Can't classify race without performance
    
    # Get check-ins from days before race
    check_in_dates = [race_date - timedelta(days=i) for i in range(1, lookback_days + 1)]
    
    checkins = db.query(DailyCheckin).filter(
        DailyCheckin.athlete_id == race.athlete_id,
        DailyCheckin.date.in_(check_in_dates)
    ).all()
    
    if not checkins:
        return PreRaceState(
            race_id=str(race.id),
            race_date=race_date,
            performance_pct=performance_pct
        )
    
    # Get the most recent pre-race check-in (race eve preferred)
    checkins.sort(key=lambda c: c.date, reverse=True)
    primary_checkin = checkins[0]
    
    # Calculate HRV baseline (30-day average before the race)
    baseline_start = race_date - timedelta(days=37)  # 30 days before the week prior
    baseline_end = race_date - timedelta(days=7)     # Stop 7 days before race
    
    baseline_hrv = db.query(func.avg(DailyCheckin.hrv_rmssd)).filter(
        DailyCheckin.athlete_id == race.athlete_id,
        DailyCheckin.date >= baseline_start,
        DailyCheckin.date <= baseline_end,
        DailyCheckin.hrv_rmssd.isnot(None)
    ).scalar()
    
    baseline_rhr = db.query(func.avg(DailyCheckin.resting_hr)).filter(
        DailyCheckin.athlete_id == race.athlete_id,
        DailyCheckin.date >= baseline_start,
        DailyCheckin.date <= baseline_end,
        DailyCheckin.resting_hr.isnot(None)
    ).scalar()
    
    # Calculate deviations
    hrv_deviation_pct = None
    if primary_checkin.hrv_rmssd and baseline_hrv:
        hrv_val = float(primary_checkin.hrv_rmssd)
        baseline_val = float(baseline_hrv)
        if baseline_val > 0:
            hrv_deviation_pct = ((hrv_val - baseline_val) / baseline_val) * 100
    
    rhr_deviation_pct = None
    if primary_checkin.resting_hr and baseline_rhr:
        rhr_val = primary_checkin.resting_hr
        baseline_val = float(baseline_rhr)
        if baseline_val > 0:
            rhr_deviation_pct = ((rhr_val - baseline_val) / baseline_val) * 100
    
    # Find days since last hard workout
    hard_workout_types = ['tempo', 'threshold', 'interval', 'race', 'vo2max', 'speed']
    
    last_hard = db.query(Activity).filter(
        Activity.athlete_id == race.athlete_id,
        Activity.start_time < race.start_time,
        Activity.workout_type.in_(hard_workout_types)
    ).order_by(Activity.start_time.desc()).first()
    
    days_since_hard = None
    if last_hard:
        days_diff = (race_date - last_hard.start_time.date()).days
        days_since_hard = max(0, days_diff)
    
    return PreRaceState(
        race_id=str(race.id),
        race_date=race_date,
        performance_pct=performance_pct,
        hrv_rmssd=float(primary_checkin.hrv_rmssd) if primary_checkin.hrv_rmssd else None,
        hrv_deviation_pct=hrv_deviation_pct,
        sleep_hours=float(primary_checkin.sleep_h) if primary_checkin.sleep_h else None,
        resting_hr=primary_checkin.resting_hr,
        resting_hr_deviation_pct=rhr_deviation_pct,
        stress_level=primary_checkin.stress_1_5,
        soreness_level=primary_checkin.soreness_1_5,
        motivation=primary_checkin.motivation_1_5,
        confidence=primary_checkin.confidence_1_5,
        days_since_hard_workout=days_since_hard
    )


def classify_races(pre_race_states: List[PreRaceState]) -> Dict[RaceCategory, List[PreRaceState]]:
    """
    Classify races into performance categories using percentiles.
    """
    if len(pre_race_states) < 4:
        return {}
    
    # Sort by performance
    sorted_races = sorted(pre_race_states, key=lambda r: r.performance_pct, reverse=True)
    n = len(sorted_races)
    
    # Calculate quartile boundaries
    q25_idx = n // 4
    q50_idx = n // 2
    q75_idx = (3 * n) // 4
    
    return {
        RaceCategory.BEST: sorted_races[:q25_idx] if q25_idx > 0 else sorted_races[:1],
        RaceCategory.GOOD: sorted_races[q25_idx:q50_idx],
        RaceCategory.AVERAGE: sorted_races[q50_idx:q75_idx],
        RaceCategory.WORST: sorted_races[q75_idx:]
    }


def analyze_feature(
    feature_name: str,
    best_values: List[float],
    worst_values: List[float],
    conventional_better_direction: str = "higher"  # "higher" or "lower"
) -> FeatureAnalysis:
    """
    Analyze a single feature comparing best vs worst races.
    
    Args:
        feature_name: Name of the feature
        best_values: Values for best race category
        worst_values: Values for worst race category
        conventional_better_direction: What conventional wisdom says is better
    """
    if len(best_values) < 2 or len(worst_values) < 2:
        return FeatureAnalysis(
            feature_name=feature_name,
            best_mean=None,
            best_std=None,
            worst_mean=None,
            worst_std=None,
            difference=None,
            p_value=None,
            cohens_d=None,
            is_significant=False,
            pattern_type=PatternType.NO_PATTERN,
            insight_text=f"Insufficient data for {feature_name}"
        )
    
    best_mean = statistics.mean(best_values)
    best_std = statistics.stdev(best_values) if len(best_values) > 1 else 0
    worst_mean = statistics.mean(worst_values)
    worst_std = statistics.stdev(worst_values) if len(worst_values) > 1 else 0
    
    difference = best_mean - worst_mean
    
    # Statistical tests
    _, p_value = mann_whitney_u_test(best_values, worst_values)
    cohens_d = calculate_cohens_d(best_values, worst_values)
    
    # Determine significance (p < 0.05 and |d| > 0.5)
    is_significant = p_value < 0.05 and abs(cohens_d or 0) > 0.5
    
    # Determine pattern type
    if not is_significant:
        pattern_type = PatternType.NO_PATTERN
    else:
        # Check if pattern matches conventional wisdom
        if conventional_better_direction == "higher":
            # Conventional: higher is better for best races
            if difference > 0:  # best_mean > worst_mean
                pattern_type = PatternType.CONVENTIONAL
            else:
                pattern_type = PatternType.INVERTED
        else:  # lower is better conventionally
            if difference < 0:  # best_mean < worst_mean
                pattern_type = PatternType.CONVENTIONAL
            else:
                pattern_type = PatternType.INVERTED
    
    # Generate insight text
    insight_text = _generate_feature_insight(
        feature_name, best_mean, worst_mean, difference, 
        p_value, cohens_d, is_significant, pattern_type
    )
    
    return FeatureAnalysis(
        feature_name=feature_name,
        best_mean=round(best_mean, 2),
        best_std=round(best_std, 2),
        worst_mean=round(worst_mean, 2),
        worst_std=round(worst_std, 2),
        difference=round(difference, 2) if difference else None,
        p_value=round(p_value, 4) if p_value else None,
        cohens_d=round(cohens_d, 2) if cohens_d else None,
        is_significant=is_significant,
        pattern_type=pattern_type,
        insight_text=insight_text
    )


def _generate_feature_insight(
    feature_name: str,
    best_mean: float,
    worst_mean: float,
    difference: float,
    p_value: float,
    cohens_d: Optional[float],
    is_significant: bool,
    pattern_type: PatternType
) -> str:
    """Generate human-readable insight for a feature."""
    
    if not is_significant:
        return f"{feature_name}: No significant pattern detected."
    
    direction = "higher" if difference > 0 else "lower"
    effect_size = "large" if abs(cohens_d or 0) >= 0.8 else "medium" if abs(cohens_d or 0) >= 0.5 else "small"
    
    if pattern_type == PatternType.INVERTED:
        if "hrv" in feature_name.lower():
            return f"Counter-intuitive: Your best races followed {direction} HRV ({best_mean:.1f} vs {worst_mean:.1f}). This suggests sympathetic activation primes you for performance."
        else:
            return f"Unexpected pattern: Your best races had {direction} {feature_name} ({best_mean:.1f} vs {worst_mean:.1f}, {effect_size} effect)."
    else:
        return f"Your best races had {direction} {feature_name} ({best_mean:.1f} vs {worst_mean:.1f}, {effect_size} effect)."


def generate_readiness_profile(
    athlete_id: str,
    db: Session,
    min_races: int = 5
) -> ReadinessProfile:
    """
    Generate complete readiness fingerprint for an athlete.
    
    Args:
        athlete_id: Athlete UUID
        db: Database session
        min_races: Minimum races required for analysis
    
    Returns:
        ReadinessProfile with discovered patterns
    """
    from models import Activity
    
    # Get all races for athlete
    races = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.workout_type == 'race'
    ).order_by(Activity.start_time.desc()).all()
    
    # Also check is_race_candidate
    if len(races) < min_races:
        race_candidates = db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.is_race_candidate == True,
            Activity.id.notin_([r.id for r in races])
        ).all()
        races.extend(race_candidates)
    
    if len(races) < min_races:
        return ReadinessProfile(
            athlete_id=athlete_id,
            total_races=len(races),
            races_with_data=0,
            best_races_count=0,
            worst_races_count=0,
            features=[],
            primary_insight=f"Need at least {min_races} races to build readiness profile. Currently have {len(races)}.",
            optimal_ranges={},
            has_counter_conventional_findings=False,
            confidence_level="insufficient"
        )
    
    # Extract pre-race states
    pre_race_states = []
    for race in races:
        state = extract_pre_race_state(race, db)
        if state and state.performance_pct:
            pre_race_states.append(state)
    
    if len(pre_race_states) < min_races:
        return ReadinessProfile(
            athlete_id=athlete_id,
            total_races=len(races),
            races_with_data=len(pre_race_states),
            best_races_count=0,
            worst_races_count=0,
            features=[],
            primary_insight=f"Need pre-race check-in data for at least {min_races} races. Currently have {len(pre_race_states)}.",
            optimal_ranges={},
            has_counter_conventional_findings=False,
            confidence_level="insufficient"
        )
    
    # Classify races
    categories = classify_races(pre_race_states)
    
    if not categories:
        return ReadinessProfile(
            athlete_id=athlete_id,
            total_races=len(races),
            races_with_data=len(pre_race_states),
            best_races_count=0,
            worst_races_count=0,
            features=[],
            primary_insight="Unable to classify races into performance categories.",
            optimal_ranges={},
            has_counter_conventional_findings=False,
            confidence_level="insufficient"
        )
    
    best_races = categories.get(RaceCategory.BEST, [])
    worst_races = categories.get(RaceCategory.WORST, [])
    
    # Define features to analyze with conventional wisdom direction
    feature_configs = [
        ("hrv_deviation_pct", "HRV Deviation", "higher"),  # Conventional: higher HRV = better
        ("sleep_hours", "Sleep Hours", "higher"),  # More sleep = better
        ("resting_hr_deviation_pct", "Resting HR Deviation", "lower"),  # Lower = better
        ("stress_level", "Stress Level", "lower"),  # Lower stress = better
        ("soreness_level", "Soreness Level", "lower"),  # Lower soreness = better
        ("motivation", "Motivation", "higher"),  # Higher motivation = better
        ("confidence", "Confidence", "higher"),  # Higher confidence = better
        ("days_since_hard_workout", "Days Since Hard Workout", "higher"),  # More rest = better (conventional)
    ]
    
    features = []
    optimal_ranges = {}
    
    for attr_name, display_name, conventional_dir in feature_configs:
        # Extract values for best and worst races
        best_values = [getattr(r, attr_name) for r in best_races if getattr(r, attr_name) is not None]
        worst_values = [getattr(r, attr_name) for r in worst_races if getattr(r, attr_name) is not None]
        
        if best_values and worst_values:
            analysis = analyze_feature(display_name, best_values, worst_values, conventional_dir)
            features.append(analysis)
            
            # If significant, calculate optimal range
            if analysis.is_significant and best_values:
                optimal_ranges[display_name] = (
                    min(best_values),
                    max(best_values)
                )
    
    # Determine primary insight
    significant_features = [f for f in features if f.is_significant]
    counter_conventional = [f for f in significant_features if f.pattern_type == PatternType.INVERTED]
    
    primary_insight = None
    if counter_conventional:
        # Prioritize counter-conventional findings
        top_finding = sorted(counter_conventional, key=lambda f: abs(f.cohens_d or 0), reverse=True)[0]
        primary_insight = top_finding.insight_text
    elif significant_features:
        top_finding = sorted(significant_features, key=lambda f: abs(f.cohens_d or 0), reverse=True)[0]
        primary_insight = top_finding.insight_text
    else:
        primary_insight = "No significant patterns found yet. Continue logging pre-race data to discover your readiness signature."
    
    # Determine confidence level
    if len(pre_race_states) >= 15 and len(significant_features) >= 2:
        confidence = "high"
    elif len(pre_race_states) >= 8 and len(significant_features) >= 1:
        confidence = "moderate"
    elif len(pre_race_states) >= 5:
        confidence = "low"
    else:
        confidence = "insufficient"
    
    return ReadinessProfile(
        athlete_id=athlete_id,
        total_races=len(races),
        races_with_data=len(pre_race_states),
        best_races_count=len(best_races),
        worst_races_count=len(worst_races),
        features=features,
        primary_insight=primary_insight,
        optimal_ranges=optimal_ranges,
        has_counter_conventional_findings=len(counter_conventional) > 0,
        confidence_level=confidence
    )


# =============================================================================
# TAPER PATTERN ANALYSIS (Phase 1D — ADR-062)
# =============================================================================

@dataclass
class ObservedTaperPattern:
    """Taper pattern derived from an athlete's best race performances."""
    taper_days: int                # Weighted average taper duration (days)
    confidence: float              # 0.0-1.0
    n_races_analyzed: int
    volume_drop_pct: float         # Average volume reduction during taper
    best_race_taper_days: int      # Taper duration before the single best race
    patterns: List[Dict]           # Per-race breakdown for transparency
    rationale: str                 # Human-readable explanation


def derive_pre_race_taper_pattern(
    activities: List,  # Activity objects with start_time, distance_m, sport
    races: List,       # Race activities with performance_percentage or age-graded %
    min_races: int = 2,
    lookback_days: int = 21,
) -> Optional[ObservedTaperPattern]:
    """
    Analyze pre-race volume patterns for the athlete's best races.

    For each race, look at the ``lookback_days`` prior:
    - Calculate daily volume
    - Identify the volume inflection point (when did they start tapering?)
    - Measure taper duration in days
    - Correlate with race performance (age-graded %)

    Returns the pattern from their best performances, or None if
    insufficient race data.

    ADR-062 Priority 1 signal.  Minimum 2 races (approved in review —
    no artificial confidence penalty beyond what the data naturally produces).
    """
    if len(races) < min_races:
        return None

    # Sort races by performance (best first)
    scored_races = []
    for r in races:
        perf = _get_race_performance(r)
        if perf is not None:
            scored_races.append((perf, r))
    scored_races.sort(key=lambda x: x[0], reverse=True)

    if len(scored_races) < min_races:
        return None

    # Build a date-keyed daily mileage index from all activities
    daily_miles: Dict[date, float] = {}
    for a in activities:
        if getattr(a, "sport", "run") not in ("run", "Run", "running"):
            continue
        a_date = _activity_date(a)
        if a_date is None:
            continue
        miles = (getattr(a, "distance_m", 0) or 0) / 1609.344
        daily_miles[a_date] = daily_miles.get(a_date, 0.0) + miles

    # Analyze the top half of races (best 50%)
    analyze_count = max(min_races, len(scored_races) // 2)
    best_races = scored_races[:analyze_count]

    patterns = []
    for perf_pct, race in best_races:
        race_date = _activity_date(race)
        if race_date is None:
            continue

        taper_info = _measure_taper_before_race(
            daily_miles, race_date, lookback_days
        )
        if taper_info is not None:
            patterns.append({
                "race_date": race_date.isoformat(),
                "performance_pct": round(perf_pct, 1),
                "taper_days": taper_info["taper_days"],
                "volume_drop_pct": round(taper_info["volume_drop_pct"], 1),
            })

    if not patterns:
        return None

    # Weight by performance: better race → higher weight
    total_weight = 0.0
    weighted_days = 0.0
    weighted_drop = 0.0
    for p in patterns:
        weight = p["performance_pct"] / 100.0  # 0-1ish scale
        weighted_days += p["taper_days"] * weight
        weighted_drop += p["volume_drop_pct"] * weight
        total_weight += weight

    avg_taper_days = round(weighted_days / total_weight) if total_weight > 0 else 14
    avg_volume_drop = weighted_drop / total_weight if total_weight > 0 else 50.0

    # Confidence: scales naturally with data quantity
    # 2 races → ~0.5, 3 → ~0.65, 5+ → 0.8+
    confidence = min(1.0, 0.3 + 0.1 * len(patterns))

    # Best race taper
    best_race_taper = patterns[0]["taper_days"] if patterns else avg_taper_days

    rationale = (
        f"Analyzed {len(patterns)} of your best races. "
        f"Your best performances followed ~{avg_taper_days}-day tapers with "
        f"~{avg_volume_drop:.0f}% volume reduction."
    )

    return ObservedTaperPattern(
        taper_days=avg_taper_days,
        confidence=confidence,
        n_races_analyzed=len(patterns),
        volume_drop_pct=avg_volume_drop,
        best_race_taper_days=best_race_taper,
        patterns=patterns,
        rationale=rationale,
    )


def _get_race_performance(race) -> Optional[float]:
    """Extract performance percentage from a race activity."""
    perf = getattr(race, "performance_percentage", None)
    if perf is not None:
        return float(perf)
    perf = getattr(race, "performance_percentage_national", None)
    if perf is not None:
        return float(perf)
    return None


def _activity_date(a) -> Optional[date]:
    """Get the date from an activity's start_time."""
    st = getattr(a, "start_time", None)
    if st is None:
        return None
    if isinstance(st, datetime):
        return st.date()
    if isinstance(st, date):
        return st
    return None


def _measure_taper_before_race(
    daily_miles: Dict[date, float],
    race_date: date,
    lookback_days: int = 21,
) -> Optional[Dict]:
    """
    Measure the taper pattern in the days before a race.

    Compares the volume in the lookback window to a "training baseline"
    (4 weeks ending 1 week before the lookback window) to find:
    - When volume started dropping (taper onset)
    - How much volume dropped

    Returns dict with taper_days and volume_drop_pct, or None.
    """
    # Baseline: 4-week block ending 1 week before the lookback window
    baseline_end = race_date - timedelta(days=lookback_days + 7)
    baseline_start = baseline_end - timedelta(days=28)

    baseline_daily = []
    d = baseline_start
    while d <= baseline_end:
        baseline_daily.append(daily_miles.get(d, 0.0))
        d += timedelta(days=1)

    if not baseline_daily or sum(baseline_daily) == 0:
        return None

    baseline_weekly_avg = sum(baseline_daily) / len(baseline_daily) * 7

    # Pre-race window: daily volumes for lookback_days before race
    pre_race_daily = []
    for offset in range(lookback_days, 0, -1):
        d = race_date - timedelta(days=offset)
        pre_race_daily.append(daily_miles.get(d, 0.0))

    if not pre_race_daily:
        return None

    # Find the inflection point: first 7-day window that drops below
    # 75% of baseline weekly volume, scanning from race day backwards.
    taper_onset_idx = len(pre_race_daily)  # default: entire window is taper

    for i in range(len(pre_race_daily) - 7, -1, -1):
        window = pre_race_daily[i:i + 7]
        window_total = sum(window)
        if window_total >= baseline_weekly_avg * 0.75:
            # This 7-day window is still at training volume — taper
            # starts AFTER this point.
            taper_onset_idx = i + 7
            break

    taper_days = len(pre_race_daily) - taper_onset_idx
    taper_days = max(3, min(lookback_days, taper_days))  # clamp 3-21

    # Volume drop: average daily miles in taper vs baseline
    taper_window = pre_race_daily[taper_onset_idx:]
    if taper_window and baseline_weekly_avg > 0:
        taper_weekly_equiv = sum(taper_window) / len(taper_window) * 7
        volume_drop_pct = (1 - taper_weekly_equiv / baseline_weekly_avg) * 100
        volume_drop_pct = max(0, min(100, volume_drop_pct))
    else:
        volume_drop_pct = 50.0  # reasonable default

    return {
        "taper_days": taper_days,
        "volume_drop_pct": volume_drop_pct,
    }


def to_dict(profile: ReadinessProfile) -> Dict:
    """Convert ReadinessProfile to dictionary for API response."""
    return {
        "athlete_id": profile.athlete_id,
        "total_races": profile.total_races,
        "races_with_data": profile.races_with_data,
        "best_races_count": profile.best_races_count,
        "worst_races_count": profile.worst_races_count,
        "features": [
            {
                "feature_name": f.feature_name,
                "best_mean": f.best_mean,
                "best_std": f.best_std,
                "worst_mean": f.worst_mean,
                "worst_std": f.worst_std,
                "difference": f.difference,
                "p_value": f.p_value,
                "cohens_d": f.cohens_d,
                "is_significant": f.is_significant,
                "pattern_type": f.pattern_type.value,
                "insight_text": f.insight_text
            }
            for f in profile.features
        ],
        "primary_insight": profile.primary_insight,
        "optimal_ranges": profile.optimal_ranges,
        "has_counter_conventional_findings": profile.has_counter_conventional_findings,
        "confidence_level": profile.confidence_level
    }
