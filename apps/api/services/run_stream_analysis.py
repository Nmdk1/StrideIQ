"""Run Stream Analysis Engine — Phase 2.

Pure-computation module that transforms per-second stream data into
structured analysis outputs: segments, drift metrics, coachable moments,
and optional plan-vs-execution comparison.

Design principles:
    - N=1: Classification adapts to the individual athlete via tiered
      physiological context. No hard-coded universal HR thresholds.
    - Deterministic: identical input → identical output (AC-4).
    - No DB, no IO, no side effects — pure functions operating on lists.
    - Partial-channel safe: missing channels → null fields, never crashes (AC-6).
    - Typed outputs only: no natural-language strings beyond enum labels (Trust).
    - Plan comparison is additive enrichment, not a gating dependency.
      Athletes without plans receive first-class, complete analysis.

Tiered classification:
    Tier 1: threshold_hr known → HR anchored to real lactate threshold
    Tier 2: max_hr + resting_hr → estimated threshold via Karvonen HRR
    Tier 3: max_hr only → percentage-of-max boundaries
    Tier 4: no athlete data → within-run percentile bands (stream-relative)

Public API:
    analyze_stream(stream_data, channels_available, planned_workout=None,
                   athlete_context=None) → StreamAnalysisResult

Internal functions:
    detect_segments(time, velocity, heartrate, grade, config, athlete_context)
    compute_drift(time, heartrate, velocity, cadence, work_segments)
    detect_moments(time, heartrate, velocity, cadence, grade, segments)
    compare_plan_summary(segments, stream_data, planned_workout)
"""
from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums (typed labels — no prose)
# ---------------------------------------------------------------------------

class SegmentType(str, Enum):
    warmup = "warmup"
    work = "work"
    recovery = "recovery"
    cooldown = "cooldown"
    steady = "steady"


class MomentType(str, Enum):
    cardiac_drift_onset = "cardiac_drift_onset"
    cadence_drop = "cadence_drop"
    cadence_surge = "cadence_surge"
    pace_surge = "pace_surge"
    pace_fade = "pace_fade"
    grade_adjusted_anomaly = "grade_adjusted_anomaly"
    recovery_hr_delay = "recovery_hr_delay"
    effort_zone_transition = "effort_zone_transition"


# ---------------------------------------------------------------------------
# Athlete context — the N=1 data the tool wrapper resolves from the DB
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AthleteContext:
    """Per-athlete physiological profile for individualized classification.

    All fields are Optional. The engine selects the highest-confidence
    tier based on what's available:
        Tier 1: threshold_hr is not None
        Tier 2: max_hr and resting_hr are not None (threshold estimated)
        Tier 3: max_hr is not None
        Tier 4: nothing available (stream-relative fallback)

    The tool wrapper resolves this from the Athlete model. The computation
    layer never touches the DB.
    """
    max_hr: Optional[int] = None
    resting_hr: Optional[int] = None
    threshold_hr: Optional[int] = None
    threshold_pace_per_km: Optional[float] = None


def _resolve_tier(ctx: Optional[AthleteContext]) -> Tuple[str, List[str]]:
    """Determine classification tier and any estimation flags.

    Returns:
        (tier_name, estimated_flags)
    """
    if ctx is None:
        return "tier4_stream_relative", []
    if ctx.threshold_hr is not None and ctx.threshold_hr > 0:
        return "tier1_threshold_hr", []
    if (ctx.max_hr is not None and ctx.max_hr > 0
            and ctx.resting_hr is not None and ctx.resting_hr > 0):
        return "tier2_estimated_hrr", ["threshold_hr_estimated_from_hrr"]
    if ctx.max_hr is not None and ctx.max_hr > 0:
        return "tier3_max_hr", []
    return "tier4_stream_relative", []


def _estimate_threshold_hr(ctx: AthleteContext) -> float:
    """Tier 2: estimate threshold HR from Karvonen HRR at 88%.

    Formula: threshold = resting + 0.88 * (max - resting)
    This is a HEURISTIC, not physiological truth. Labeled as estimated.
    Versioned in config as `tier2_threshold_hrr_fraction`.
    """
    return ctx.resting_hr + 0.88 * (ctx.max_hr - ctx.resting_hr)


# ---------------------------------------------------------------------------
# RSI-Alpha: per-point effort intensity computation (ADR-064)
# ---------------------------------------------------------------------------

_VALID_TIERS = frozenset({
    "tier1_threshold_hr",
    "tier2_estimated_hrr",
    "tier3_max_hr",
    "tier4_stream_relative",
})


def _clamp01(value: float) -> float:
    """Clamp a float to [0.0, 1.0]."""
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def compute_effort_intensity(
    hr: Optional[float] = None,
    ctx: Optional[AthleteContext] = None,
    tier: Optional[str] = None,
    hr_series: Optional[List[float]] = None,
    velocity: Optional[float] = None,
) -> float:
    """Compute a single-point effort intensity scalar in [0.0, 1.0].

    Tier dispatch per ADR-064:
        tier1_threshold_hr:    effort = HR / threshold_hr
        tier2_estimated_hrr:   effort = (HR - resting) / (est_threshold - resting)
        tier3_max_hr:          effort = HR / max_hr
        tier4_stream_relative: percentile rank of HR within hr_series

    Velocity fallback: when hr is None and velocity + threshold_pace_per_km
    are available, effort = velocity / threshold_velocity.

    Raises:
        ValueError: if tier is not None and not in _VALID_TIERS.

    Always returns a float in [0.0, 1.0].
    """
    # --- Validate tier ---
    if tier is not None and tier not in _VALID_TIERS:
        raise ValueError(
            f"Unknown effort tier '{tier}'. "
            f"Valid tiers: {sorted(_VALID_TIERS)}"
        )

    if ctx is None:
        ctx = AthleteContext()

    # --- Velocity fallback when HR is missing ---
    if hr is None:
        if (velocity is not None
                and ctx.threshold_pace_per_km is not None
                and ctx.threshold_pace_per_km > 0):
            threshold_velocity = 1000.0 / ctx.threshold_pace_per_km
            if threshold_velocity <= 0:
                return 0.0
            return _clamp01(velocity / threshold_velocity)
        return 0.0

    hr_float = float(hr)

    # --- Tier 1: HR / threshold_hr ---
    if tier == "tier1_threshold_hr":
        if ctx.threshold_hr is not None and ctx.threshold_hr > 0:
            return _clamp01(hr_float / ctx.threshold_hr)
        return 0.0

    # --- Tier 2: Karvonen HRR ---
    if tier == "tier2_estimated_hrr":
        if (ctx.max_hr is not None and ctx.max_hr > 0
                and ctx.resting_hr is not None and ctx.resting_hr > 0):
            est_threshold = _estimate_threshold_hr(ctx)
            denominator = est_threshold - ctx.resting_hr
            if denominator <= 0:
                return 0.0
            return _clamp01((hr_float - ctx.resting_hr) / denominator)
        return 0.0

    # --- Tier 3: % max HR ---
    if tier == "tier3_max_hr":
        if ctx.max_hr is not None and ctx.max_hr > 0:
            return _clamp01(hr_float / ctx.max_hr)
        return 0.0

    # --- Tier 4: stream-relative percentile ---
    if tier == "tier4_stream_relative":
        if hr_series is not None and len(hr_series) > 0:
            count_below = sum(1 for h in hr_series if h < hr_float)
            return _clamp01(count_below / len(hr_series))
        return 0.0

    # tier is None — no computation possible
    return 0.0


def _compute_effort_array(
    stream_data: Dict[str, List],
    point_count: int,
    tier: str,
    ctx: Optional[AthleteContext],
) -> List[float]:
    """Compute effort intensity for every point in the stream.

    Performance:
        Tiers 1-3: O(n) — single pass, constant-time per point.
        Tier 4: O(n log n) — pre-sorts hr_series, uses bisect for each lookup.

    Args:
        stream_data: channel name -> list of values.
        point_count: number of data points (avoids fragile channel iteration).
        tier: one of _VALID_TIERS.
        ctx: athlete physiological context.

    Returns:
        List of floats with length == point_count, each in [0.0, 1.0].
    """
    import bisect

    hr_series = stream_data.get("heartrate")
    velocity_series = stream_data.get("velocity_smooth")
    has_hr = hr_series is not None and len(hr_series) > 0
    has_vel = velocity_series is not None and len(velocity_series) > 0

    if point_count == 0:
        return []

    if ctx is None:
        ctx = AthleteContext()

    # --- Tier 4 optimisation: pre-sort + bisect for O(n log n) total ---
    sorted_hr: Optional[List[float]] = None
    hr_count = 0
    if tier == "tier4_stream_relative" and has_hr:
        sorted_hr = sorted(float(h) for h in hr_series)
        hr_count = len(sorted_hr)

    # --- Tiers 1-3: pre-compute denominators once ---
    t1_denom: Optional[float] = None
    t2_denom: Optional[float] = None
    t2_resting: float = 0.0
    t3_denom: Optional[float] = None

    if tier == "tier1_threshold_hr" and ctx.threshold_hr and ctx.threshold_hr > 0:
        t1_denom = float(ctx.threshold_hr)
    elif tier == "tier2_estimated_hrr":
        if (ctx.max_hr and ctx.max_hr > 0
                and ctx.resting_hr and ctx.resting_hr > 0):
            est = _estimate_threshold_hr(ctx)
            denom = est - ctx.resting_hr
            if denom > 0:
                t2_denom = denom
                t2_resting = float(ctx.resting_hr)
    elif tier == "tier3_max_hr" and ctx.max_hr and ctx.max_hr > 0:
        t3_denom = float(ctx.max_hr)

    # --- Velocity fallback denominators ---
    vel_denom: Optional[float] = None
    if ctx.threshold_pace_per_km and ctx.threshold_pace_per_km > 0:
        tv = 1000.0 / ctx.threshold_pace_per_km
        if tv > 0:
            vel_denom = tv

    effort = [0.0] * point_count
    for i in range(point_count):
        hr_val = float(hr_series[i]) if has_hr and i < len(hr_series) else None
        vel_val = float(velocity_series[i]) if has_vel and i < len(velocity_series) else None

        # --- No HR: velocity fallback ---
        if hr_val is None:
            if vel_val is not None and vel_denom is not None:
                effort[i] = _clamp01(vel_val / vel_denom)
            # else stays 0.0
            continue

        # --- Tier 1 ---
        if tier == "tier1_threshold_hr":
            if t1_denom is not None:
                effort[i] = _clamp01(hr_val / t1_denom)
            continue

        # --- Tier 2 ---
        if tier == "tier2_estimated_hrr":
            if t2_denom is not None:
                effort[i] = _clamp01((hr_val - t2_resting) / t2_denom)
            continue

        # --- Tier 3 ---
        if tier == "tier3_max_hr":
            if t3_denom is not None:
                effort[i] = _clamp01(hr_val / t3_denom)
            continue

        # --- Tier 4: bisect on pre-sorted array → O(log n) per point ---
        if tier == "tier4_stream_relative":
            if sorted_hr is not None and hr_count > 0:
                rank = bisect.bisect_left(sorted_hr, hr_val)
                effort[i] = _clamp01(rank / hr_count)
            continue

    return effort


# ---------------------------------------------------------------------------
# Configuration (ALL thresholds externalized — zero inline magic numbers)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SegmentConfig:
    """Tunable thresholds for segment detection.

    Every numeric threshold used in classification lives here.
    No inline constants in classification functions.
    """
    # Sliding window size in seconds for smoothing
    window_size: int = 30
    # Minimum segment duration in seconds (anti-chatter)
    min_segment_duration: int = 30

    # --- Position-based boundaries ---
    warmup_position_fraction: float = 0.20   # First 20% of run
    cooldown_position_fraction: float = 0.85  # Last 15% of run

    # --- Velocity thresholds (fractions, not absolute) ---
    warmup_velocity_fraction: float = 0.75   # Below this fraction of v_range = warmup pace
    work_velocity_multiplier: float = 1.15   # Above v_median * this = work (Tier 4)
    work_velocity_frac: float = 0.60         # v_frac above this = work (Tier 4)
    recovery_velocity_ratio: float = 0.80    # Below v_median * this = recovery candidate
    recovery_velocity_frac: float = 0.35     # v_frac below this = recovery candidate (Tier 4)

    # --- Tier 2: Karvonen estimation parameter ---
    tier2_threshold_hrr_fraction: float = 0.88

    # --- Tier 3: Percentage-of-max boundaries ---
    tier3_recovery_ceil: float = 0.70    # Below 70% max_hr = recovery
    tier3_steady_ceil: float = 0.82      # 70-82% max_hr = steady
    tier3_work_ceil: float = 0.90        # 82-90% max_hr = work; above = also work (hard→work)

    # --- Tier 4: Percentile thresholds for stream-relative bands ---
    tier4_low_percentile: float = 0.25   # Below 25th percentile = recovery candidate
    tier4_high_percentile: float = 0.75  # Above 75th percentile = work candidate

    # --- Hysteresis (anti-chatter at zone boundaries) ---
    hysteresis_bpm: float = 3.0          # Must cross threshold ± this before state flip

    # --- Grade-explained detection ---
    grade_threshold_pct: float = 3.0     # abs(grade) >= this = terrain-significant
    grade_sustained_s: int = 30          # Must hold for this many seconds

    # --- Tier 4 tie-break: velocity is primary, HR secondary ---
    # Tiers 1-3: HR wins (with grade override)


@dataclass(frozen=True)
class MomentConfig:
    """Tunable thresholds for coachable moment detection."""
    # Cardiac drift: rolling window and threshold
    drift_window_s: int = 300
    drift_onset_hr_rise_pct: float = 3.0
    # Stabilization skip at start of steady segment
    drift_stabilize_s: int = 120
    # Cadence thresholds (spm deviation from segment average)
    cadence_drop_threshold: float = 5.0
    cadence_surge_threshold: float = 5.0
    # Pace thresholds (fraction of segment average velocity)
    pace_surge_fraction: float = 0.10
    pace_fade_fraction: float = 0.10
    # Minimum sustained duration to emit a moment
    min_moment_duration: int = 15
    # Grade threshold for grade-adjusted anomaly
    grade_threshold_pct: float = 3.0
    # Pace deviation fraction for grade anomaly
    grade_pace_deviation: float = 0.85
    # HR fraction of segment max for grade anomaly
    grade_hr_fraction: float = 0.70


# ---------------------------------------------------------------------------
# Data classes — strictly typed output schema
# ---------------------------------------------------------------------------

@dataclass
class Segment:
    type: str  # SegmentType value
    start_index: int
    end_index: int
    start_time_s: int
    end_time_s: int
    duration_s: int
    avg_pace_s_km: Optional[float] = None
    avg_hr: Optional[float] = None
    avg_cadence: Optional[float] = None
    avg_grade: Optional[float] = None

    def __eq__(self, other):
        if not isinstance(other, Segment):
            return NotImplemented
        return (self.type == other.type and self.start_index == other.start_index
                and self.end_index == other.end_index)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DriftAnalysis:
    cardiac_pct: Optional[float] = None
    pace_pct: Optional[float] = None
    cadence_trend_bpm_per_km: Optional[float] = None

    def __eq__(self, other):
        if not isinstance(other, DriftAnalysis):
            return NotImplemented
        return (self.cardiac_pct == other.cardiac_pct
                and self.pace_pct == other.pace_pct
                and self.cadence_trend_bpm_per_km == other.cadence_trend_bpm_per_km)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Moment:
    type: str  # MomentType value
    index: int
    time_s: int
    value: Optional[float] = None
    context: Optional[str] = None  # Short enum-level label, not prose

    def __eq__(self, other):
        if not isinstance(other, Moment):
            return NotImplemented
        return (self.type == other.type and self.index == other.index
                and self.time_s == other.time_s)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PlanComparison:
    planned_duration_min: Optional[float] = None
    actual_duration_min: Optional[float] = None
    duration_delta_min: Optional[float] = None
    planned_distance_km: Optional[float] = None
    actual_distance_km: Optional[float] = None
    distance_delta_km: Optional[float] = None
    planned_pace_s_km: Optional[float] = None
    actual_pace_s_km: Optional[float] = None
    pace_delta_s_km: Optional[float] = None
    planned_interval_count: Optional[int] = None
    detected_work_count: Optional[int] = None
    interval_count_match: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StreamAnalysisResult:
    segments: List[Segment] = field(default_factory=list)
    drift: DriftAnalysis = field(default_factory=DriftAnalysis)
    moments: List[Moment] = field(default_factory=list)
    plan_comparison: Optional[PlanComparison] = None
    channels_present: List[str] = field(default_factory=list)
    channels_missing: List[str] = field(default_factory=list)
    point_count: int = 0
    confidence: float = 0.0
    # --- Provenance (N=1 transparency) ---
    tier_used: str = "tier4_stream_relative"
    estimated_flags: List[str] = field(default_factory=list)
    cross_run_comparable: bool = False
    # --- RSI-Alpha: per-point effort intensity [0.0, 1.0] ---
    effort_intensity: List[float] = field(default_factory=list)

    def __eq__(self, other):
        if not isinstance(other, StreamAnalysisResult):
            return NotImplemented
        return (self.segments == other.segments
                and self.drift == other.drift
                and self.moments == other.moments
                and self.confidence == other.confidence
                and self.tier_used == other.tier_used)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segments": [s.to_dict() for s in self.segments],
            "drift": self.drift.to_dict(),
            "moments": [m.to_dict() for m in self.moments],
            "plan_comparison": self.plan_comparison.to_dict() if self.plan_comparison else None,
            "channels_present": self.channels_present,
            "channels_missing": self.channels_missing,
            "point_count": self.point_count,
            "confidence": self.confidence,
            "tier_used": self.tier_used,
            "estimated_flags": self.estimated_flags,
            "cross_run_comparable": self.cross_run_comparable,
            "effort_intensity": self.effort_intensity,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALL_CHANNELS = {"time", "heartrate", "velocity_smooth", "cadence",
                "distance", "altitude", "grade_smooth"}


def _clamp(lo: float, hi: float, value: float) -> float:
    """Clamp value to [lo, hi]."""
    return max(lo, min(hi, value))


def _safe_list(stream_data: Dict, key: str, expected_len: int) -> Optional[List]:
    """Extract channel from stream_data, validating type and length."""
    val = stream_data.get(key)
    if val is None:
        return None
    if not isinstance(val, list):
        return None
    if len(val) != expected_len:
        return None
    return val


def _sliding_avg(data: List[float], window: int) -> List[float]:
    """Simple centered sliding average. Deterministic."""
    n = len(data)
    if n == 0:
        return []
    half = window // 2
    result = []
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        result.append(sum(data[lo:hi]) / (hi - lo))
    return result


def _velocity_to_pace_s_km(velocity_m_s: float) -> Optional[float]:
    """Convert m/s to seconds per km. Returns None if velocity <= 0."""
    if velocity_m_s <= 0:
        return None
    return 1000.0 / velocity_m_s


def _percentile(sorted_data: List[float], p: float) -> float:
    """Compute percentile from pre-sorted data. Deterministic (nearest-rank)."""
    if not sorted_data:
        return 0.0
    idx = int(p * (len(sorted_data) - 1))
    return sorted_data[idx]


def _is_grade_sustained(
    grade: List[float], center: int, window_s: int, threshold_pct: float,
) -> bool:
    """Check if grade >= threshold is sustained over a rolling window."""
    n = len(grade)
    half = window_s // 2
    lo = max(0, center - half)
    hi = min(n, center + half + 1)
    if hi - lo < max(1, window_s // 2):  # Need at least half the window
        return False
    count_above = sum(1 for g in grade[lo:hi] if abs(g) >= threshold_pct)
    return count_above >= (hi - lo) * 0.7  # 70% of window must exceed threshold


# ---------------------------------------------------------------------------
# 1) SEGMENT DETECTION — tiered, config-driven, hysteresis-protected
# ---------------------------------------------------------------------------

def detect_segments(
    time: List[int],
    velocity: Optional[List[float]],
    heartrate: Optional[List[float]],
    grade: Optional[List[float]],
    config: Optional[SegmentConfig] = None,
    athlete_context: Optional[AthleteContext] = None,
) -> List[Segment]:
    """Detect run segments using tiered N=1 classification.

    The classification tier is selected automatically based on the
    athlete context available. All thresholds come from config.

    Returns segments covering the full time range with no gaps.
    """
    if config is None:
        config = SegmentConfig()

    n = len(time)
    if n < config.min_segment_duration:
        return []

    # Need at least velocity to detect segments
    if velocity is None or len(velocity) != n:
        if n > 0:
            return [Segment(
                type=SegmentType.steady.value,
                start_index=0, end_index=n - 1,
                start_time_s=time[0], end_time_s=time[-1],
                duration_s=time[-1] - time[0],
            )]
        return []

    # Resolve tier
    tier, _ = _resolve_tier(athlete_context)

    # Smooth channels
    smooth_v = _sliding_avg(velocity, config.window_size)
    smooth_hr = None
    if heartrate is not None and len(heartrate) == n:
        smooth_hr = _sliding_avg(heartrate, config.window_size)

    # Velocity statistics (all tiers need these)
    valid_v = [v for v in smooth_v if v > 0.5]
    if not valid_v:
        return [Segment(
            type=SegmentType.steady.value,
            start_index=0, end_index=n - 1,
            start_time_s=time[0], end_time_s=time[-1],
            duration_s=time[-1] - time[0],
        )]

    v_median = statistics.median(valid_v)
    v_max = max(valid_v)
    v_min = min(valid_v)
    v_range = v_max - v_min if v_max > v_min else 1.0

    # Tier-specific HR reference points
    hr_threshold = None  # The work/steady boundary in absolute bpm
    if tier == "tier1_threshold_hr":
        hr_threshold = float(athlete_context.threshold_hr)
    elif tier == "tier2_estimated_hrr":
        hr_threshold = _estimate_threshold_hr(athlete_context)

    # Tier 3: compute absolute HR boundaries from max_hr
    tier3_recovery_hr = None
    tier3_steady_hr = None
    tier3_work_hr = None
    if tier == "tier3_max_hr":
        max_hr = float(athlete_context.max_hr)
        tier3_recovery_hr = max_hr * config.tier3_recovery_ceil
        tier3_steady_hr = max_hr * config.tier3_steady_ceil
        tier3_work_hr = max_hr * config.tier3_work_ceil

    # Tier 4: compute percentile bands from stream data
    hr_p25 = hr_p75 = v_p25 = v_p75 = None
    if tier == "tier4_stream_relative":
        sorted_v = sorted(valid_v)
        v_p25 = _percentile(sorted_v, config.tier4_low_percentile)
        v_p75 = _percentile(sorted_v, config.tier4_high_percentile)
        if smooth_hr:
            valid_hr = sorted([h for h in smooth_hr if h > 0])
            if valid_hr:
                hr_p25 = _percentile(valid_hr, config.tier4_low_percentile)
                hr_p75 = _percentile(valid_hr, config.tier4_high_percentile)

    # --- Phase 1: Classify each second ---
    labels: List[str] = []
    for i in range(n):
        v = smooth_v[i]
        hr = smooth_hr[i] if smooth_hr else None
        g = grade[i] if grade is not None and i < len(grade) else 0.0
        frac_pos = i / n if n > 0 else 0.5

        # Grade-sustained check
        grade_active = False
        if grade is not None and abs(g) >= config.grade_threshold_pct:
            grade_active = _is_grade_sustained(
                grade, i, config.grade_sustained_s, config.grade_threshold_pct)

        label = _classify_point_tiered(
            tier, i, n, v, hr, g, frac_pos, grade_active,
            v_median, v_max, v_range, v_min,
            hr_threshold, tier3_recovery_hr, tier3_steady_hr, tier3_work_hr,
            v_p25, v_p75, hr_p25, hr_p75,
            config,
        )
        labels.append(label)

    # --- Phase 2: Hysteresis pass (anti-chatter) ---
    if smooth_hr and hr_threshold is not None:
        labels = _apply_hysteresis(labels, smooth_hr, hr_threshold, config)

    # --- Phase 3: Merge adjacent same-type labels into segments ---
    raw_segments = _merge_labels(labels, time, velocity, heartrate, grade)

    # --- Phase 4: Enforce minimum duration, merge small segments ---
    merged = _enforce_minimum_duration(raw_segments, config.min_segment_duration)

    # --- Phase 5: Recompute averages for final segments ---
    final = _compute_segment_averages(merged, time, velocity, heartrate, grade)

    return final


def _classify_point_tiered(
    tier: str,
    i: int, n: int,
    v: float, hr: Optional[float], g: float,
    frac_pos: float, grade_active: bool,
    v_median: float, v_max: float, v_range: float, v_min: float,
    hr_threshold: Optional[float],
    tier3_recovery_hr: Optional[float],
    tier3_steady_hr: Optional[float],
    tier3_work_hr: Optional[float],
    v_p25: Optional[float], v_p75: Optional[float],
    hr_p25: Optional[float], hr_p75: Optional[float],
    config: SegmentConfig,
) -> str:
    """Classify a single time point using the appropriate tier.

    Tiers 1-3: HR is primary signal (with grade override).
    Tier 4: Velocity is primary, HR is secondary.
    """
    is_early = frac_pos < config.warmup_position_fraction
    is_late = frac_pos > config.cooldown_position_fraction
    v_frac = (v - v_min) / v_range if v_range > 0 else 0.5

    # --- Warmup / Cooldown (all tiers, position + velocity) ---
    if is_early and v_frac < config.warmup_velocity_fraction:
        return SegmentType.warmup.value
    if is_late and v_frac < config.warmup_velocity_fraction:
        return SegmentType.cooldown.value

    # --- Grade-explained work: sustained steep grade + high effort ---
    # Applies to all tiers: slow pace on a hill with high HR = work
    if grade_active and hr is not None:
        if tier in ("tier1_threshold_hr", "tier2_estimated_hrr") and hr_threshold:
            if hr >= hr_threshold - config.hysteresis_bpm:
                return SegmentType.work.value
        elif tier == "tier3_max_hr" and tier3_steady_hr:
            if hr >= tier3_steady_hr:
                return SegmentType.work.value
        elif tier == "tier4_stream_relative" and hr_p75:
            if hr >= hr_p75:
                return SegmentType.work.value

    # --- Tier-specific effort classification ---
    if tier in ("tier1_threshold_hr", "tier2_estimated_hrr"):
        return _classify_hr_anchored(
            v, hr, v_frac, hr_threshold, config, is_early, is_late)

    elif tier == "tier3_max_hr":
        return _classify_max_hr_pct(
            v, hr, v_frac, tier3_recovery_hr, tier3_steady_hr, tier3_work_hr,
            config, is_early, is_late)

    else:  # tier4
        return _classify_stream_relative(
            v, hr, v_frac, v_median, v_p25, v_p75, hr_p25, hr_p75,
            config, is_early, is_late)


def _classify_hr_anchored(
    v: float, hr: Optional[float], v_frac: float,
    hr_threshold: float, config: SegmentConfig,
    is_early: bool, is_late: bool,
) -> str:
    """Tiers 1 & 2: HR anchored to (actual or estimated) threshold.

    HR wins. If HR says work and pace says easy, it's work.
    """
    if hr is not None and hr_threshold > 0:
        if hr >= hr_threshold:
            return SegmentType.work.value
        # Well below threshold = recovery (only if also slow)
        if hr < hr_threshold - config.hysteresis_bpm * 3:
            if v_frac < config.recovery_velocity_frac + 0.15:
                return SegmentType.recovery.value
        return SegmentType.steady.value

    # No HR data — fall back to velocity-only
    if v_frac > config.work_velocity_frac:
        return SegmentType.work.value
    if v_frac < config.recovery_velocity_frac:
        return SegmentType.recovery.value
    return SegmentType.steady.value


def _classify_max_hr_pct(
    v: float, hr: Optional[float], v_frac: float,
    recovery_hr: float, steady_hr: float, work_hr: float,
    config: SegmentConfig, is_early: bool, is_late: bool,
) -> str:
    """Tier 3: Percentage-of-max boundaries. HR wins."""
    if hr is not None:
        if hr >= steady_hr:
            return SegmentType.work.value  # 82%+ max → work (including "hard" > 90%)
        if hr < recovery_hr:
            if v_frac < config.recovery_velocity_frac + 0.15:
                return SegmentType.recovery.value
        return SegmentType.steady.value

    # No HR → velocity only
    if v_frac > config.work_velocity_frac:
        return SegmentType.work.value
    if v_frac < config.recovery_velocity_frac:
        return SegmentType.recovery.value
    return SegmentType.steady.value


def _classify_stream_relative(
    v: float, hr: Optional[float], v_frac: float,
    v_median: float,
    v_p25: Optional[float], v_p75: Optional[float],
    hr_p25: Optional[float], hr_p75: Optional[float],
    config: SegmentConfig, is_early: bool, is_late: bool,
) -> str:
    """Tier 4: Stream-relative percentile bands.

    Velocity is primary. HR is tiebreaker.
    Within-run labeling only — not comparable across runs.
    """
    # Work: high velocity
    if v_p75 is not None and v > v_p75:
        return SegmentType.work.value

    # Recovery: low velocity (AND low HR if available)
    if v_p25 is not None and v < v_p25:
        if hr is None or hr_p25 is None:
            return SegmentType.recovery.value
        if hr < hr_p75:  # Not at high HR (e.g. walking recovery with elevated HR)
            return SegmentType.recovery.value

    # HR-based tiebreak for mid-range velocity
    if hr is not None and hr_p75 is not None and hr >= hr_p75:
        return SegmentType.work.value

    return SegmentType.steady.value


# ---------------------------------------------------------------------------
# Hysteresis (anti-chatter)
# ---------------------------------------------------------------------------

def _apply_hysteresis(
    labels: List[str],
    smooth_hr: List[float],
    hr_threshold: float,
    config: SegmentConfig,
) -> List[str]:
    """Post-classification pass to prevent rapid state flipping.

    Once in 'work', must drop below threshold - hysteresis before flipping out.
    Once in non-work, must rise above threshold + hysteresis before flipping in.
    """
    result = list(labels)
    in_work = labels[0] == SegmentType.work.value
    hyst = config.hysteresis_bpm

    for i in range(1, len(labels)):
        hr = smooth_hr[i] if i < len(smooth_hr) else None
        if hr is None:
            continue

        current_label = labels[i]

        if in_work:
            # Stay in work until HR drops below threshold - hysteresis
            if current_label != SegmentType.work.value:
                if hr > hr_threshold - hyst:
                    result[i] = SegmentType.work.value  # Suppress flip
                else:
                    in_work = False
        else:
            # Stay out of work until HR rises above threshold + hysteresis
            if current_label == SegmentType.work.value:
                if hr < hr_threshold + hyst:
                    result[i] = SegmentType.steady.value  # Suppress flip
                else:
                    in_work = True

    return result


# ---------------------------------------------------------------------------
# Segment merge, enforce min duration, compute averages
# ---------------------------------------------------------------------------

def _merge_labels(
    labels: List[str], time: List[int],
    velocity: Optional[List[float]], heartrate: Optional[List[float]],
    grade: Optional[List[float]],
) -> List[Segment]:
    """Merge consecutive same-type labels into Segment objects."""
    if not labels:
        return []

    segments: List[Segment] = []
    current_type = labels[0]
    start_idx = 0

    for i in range(1, len(labels)):
        if labels[i] != current_type:
            segments.append(Segment(
                type=current_type, start_index=start_idx, end_index=i - 1,
                start_time_s=time[start_idx], end_time_s=time[i - 1],
                duration_s=time[i - 1] - time[start_idx],
            ))
            current_type = labels[i]
            start_idx = i

    segments.append(Segment(
        type=current_type, start_index=start_idx, end_index=len(labels) - 1,
        start_time_s=time[start_idx], end_time_s=time[-1],
        duration_s=time[-1] - time[start_idx],
    ))
    return segments


def _enforce_minimum_duration(
    segments: List[Segment], min_duration: int,
) -> List[Segment]:
    """Merge segments shorter than min_duration into neighbors."""
    if len(segments) <= 1:
        return segments

    merged = list(segments)
    changed = True
    while changed:
        changed = False
        new_merged = []
        i = 0
        while i < len(merged):
            seg = merged[i]
            if seg.duration_s < min_duration and len(new_merged) > 0:
                prev = new_merged[-1]
                new_merged[-1] = Segment(
                    type=prev.type, start_index=prev.start_index,
                    end_index=seg.end_index, start_time_s=prev.start_time_s,
                    end_time_s=seg.end_time_s,
                    duration_s=seg.end_time_s - prev.start_time_s,
                )
                changed = True
            elif seg.duration_s < min_duration and i + 1 < len(merged):
                nxt = merged[i + 1]
                merged[i + 1] = Segment(
                    type=nxt.type, start_index=seg.start_index,
                    end_index=nxt.end_index, start_time_s=seg.start_time_s,
                    end_time_s=nxt.end_time_s,
                    duration_s=nxt.end_time_s - seg.start_time_s,
                )
                changed = True
                i += 1
                continue
            else:
                new_merged.append(seg)
            i += 1
        merged = new_merged

    # Consolidate adjacent same-type
    if len(merged) <= 1:
        return merged
    consolidated: List[Segment] = [merged[0]]
    for seg in merged[1:]:
        if seg.type == consolidated[-1].type:
            prev = consolidated[-1]
            consolidated[-1] = Segment(
                type=prev.type, start_index=prev.start_index,
                end_index=seg.end_index, start_time_s=prev.start_time_s,
                end_time_s=seg.end_time_s,
                duration_s=seg.end_time_s - prev.start_time_s,
            )
        else:
            consolidated.append(seg)
    return consolidated


def _compute_segment_averages(
    segments: List[Segment], time: List[int],
    velocity: Optional[List[float]], heartrate: Optional[List[float]],
    grade: Optional[List[float]],
) -> List[Segment]:
    """Recompute average metrics for each segment from raw data."""
    result = []
    for seg in segments:
        si, ei = seg.start_index, seg.end_index
        count = ei - si + 1

        avg_pace = None
        if velocity is not None and count > 0:
            avg_v = sum(velocity[si:ei + 1]) / count
            avg_pace = _velocity_to_pace_s_km(avg_v)

        avg_hr = None
        if heartrate is not None and len(heartrate) > ei:
            avg_hr = round(sum(heartrate[si:ei + 1]) / count, 1)

        avg_grade_val = None
        if grade is not None and len(grade) > ei:
            avg_grade_val = round(sum(grade[si:ei + 1]) / count, 2)

        result.append(Segment(
            type=seg.type, start_index=seg.start_index, end_index=seg.end_index,
            start_time_s=seg.start_time_s, end_time_s=seg.end_time_s,
            duration_s=seg.duration_s,
            avg_pace_s_km=round(avg_pace, 1) if avg_pace is not None else None,
            avg_hr=avg_hr, avg_grade=avg_grade_val,
        ))
    return result


# ---------------------------------------------------------------------------
# 2) DRIFT ANALYSIS
# ---------------------------------------------------------------------------

def compute_drift(
    time: List[int],
    heartrate: Optional[List[float]],
    velocity: Optional[List[float]],
    cadence: Optional[List[float]],
    work_segments: List[Segment],
) -> DriftAnalysis:
    """Compute cardiac drift, pace drift, and cadence trend.

    Measured over work/steady segments only.
    Uses first-half vs second-half comparison.
    """
    cardiac_pct = None
    pace_pct = None
    cadence_trend = None

    if not work_segments:
        return DriftAnalysis(cardiac_pct=cardiac_pct, pace_pct=pace_pct,
                             cadence_trend_bpm_per_km=cadence_trend)

    work_indices = []
    for seg in work_segments:
        work_indices.extend(range(seg.start_index, seg.end_index + 1))

    if len(work_indices) < 60:
        return DriftAnalysis(cardiac_pct=cardiac_pct, pace_pct=pace_pct,
                             cadence_trend_bpm_per_km=cadence_trend)

    mid = len(work_indices) // 2
    first_half_idx = work_indices[:mid]
    second_half_idx = work_indices[mid:]

    # --- Cardiac drift ---
    if heartrate is not None and len(heartrate) >= len(time):
        first_hr = [heartrate[i] for i in first_half_idx if i < len(heartrate)]
        second_hr = [heartrate[i] for i in second_half_idx if i < len(heartrate)]
        if first_hr and second_hr:
            avg_first = sum(first_hr) / len(first_hr)
            avg_second = sum(second_hr) / len(second_hr)
            if avg_first > 0:
                cardiac_pct = round((avg_second - avg_first) / avg_first * 100, 2)

    # --- Pace drift ---
    if velocity is not None and len(velocity) >= len(time):
        first_v = [velocity[i] for i in first_half_idx if i < len(velocity) and velocity[i] > 0.5]
        second_v = [velocity[i] for i in second_half_idx if i < len(velocity) and velocity[i] > 0.5]
        if first_v and second_v:
            avg_first_v = sum(first_v) / len(first_v)
            avg_second_v = sum(second_v) / len(second_v)
            if avg_first_v > 0:
                pace_pct = round((avg_second_v - avg_first_v) / avg_first_v * 100, 2)

    # --- Cadence trend ---
    if cadence is not None and len(cadence) >= len(time) and velocity is not None:
        cum_distance = 0.0
        km_cadences: Dict[int, List[float]] = {}
        prev_idx = work_indices[0]
        for idx in work_indices:
            if idx < len(velocity) and idx < len(cadence):
                if idx > prev_idx:
                    cum_distance += velocity[idx]
                km_bucket = int(cum_distance / 1000)
                km_cadences.setdefault(km_bucket, []).append(cadence[idx])
                prev_idx = idx

        if len(km_cadences) >= 2:
            km_avgs = [(km, sum(vals) / len(vals))
                       for km, vals in sorted(km_cadences.items()) if vals]
            if len(km_avgs) >= 2:
                n_km = len(km_avgs)
                x_mean = sum(k for k, _ in km_avgs) / n_km
                y_mean = sum(c for _, c in km_avgs) / n_km
                num = sum((k - x_mean) * (c - y_mean) for k, c in km_avgs)
                den = sum((k - x_mean) ** 2 for k, _ in km_avgs)
                if den > 0:
                    cadence_trend = round(num / den, 3)

    return DriftAnalysis(
        cardiac_pct=cardiac_pct, pace_pct=pace_pct,
        cadence_trend_bpm_per_km=cadence_trend,
    )


# ---------------------------------------------------------------------------
# 3) COACHABLE MOMENT DETECTION
# ---------------------------------------------------------------------------

def detect_moments(
    time: List[int],
    heartrate: Optional[List[float]],
    velocity: Optional[List[float]],
    cadence: Optional[List[float]],
    grade: Optional[List[float]],
    segments: List[Segment],
    config: Optional[MomentConfig] = None,
) -> List[Moment]:
    """Detect timestamped coachable moments.

    Moments are observations, not directives.
    """
    if config is None:
        config = MomentConfig()

    n = len(time)
    if n < 60:
        return []

    moments: List[Moment] = []

    if heartrate is not None and len(heartrate) == n:
        drift_moment = _detect_cardiac_drift_onset(time, heartrate, segments, config)
        if drift_moment is not None:
            moments.append(drift_moment)

    if velocity is not None and len(velocity) == n:
        moments.extend(_detect_pace_anomalies(time, velocity, segments, config))

    if cadence is not None and len(cadence) == n:
        moments.extend(_detect_cadence_anomalies(time, cadence, segments, config))

    if (velocity is not None and len(velocity) == n
            and grade is not None and len(grade) == n
            and heartrate is not None and len(heartrate) == n):
        moments.extend(_detect_grade_anomalies(
            time, velocity, heartrate, grade, segments, config))

    moments.sort(key=lambda m: m.time_s)
    return moments


def _detect_cardiac_drift_onset(
    time: List[int], heartrate: List[float],
    segments: List[Segment], config: MomentConfig,
) -> Optional[Moment]:
    """Detect where cardiac drift becomes notable."""
    work_steady = [s for s in segments if s.type in ("work", "steady")]
    if not work_steady:
        return None

    first_seg = work_steady[0]
    stabilize_s = config.drift_stabilize_s
    baseline_start = min(first_seg.start_index + stabilize_s, first_seg.end_index)
    baseline_end = min(baseline_start + config.drift_window_s, first_seg.end_index)
    baseline_hr_vals = heartrate[baseline_start:baseline_end + 1]
    if not baseline_hr_vals or len(baseline_hr_vals) < 60:
        return None
    baseline_hr = sum(baseline_hr_vals) / len(baseline_hr_vals)
    if baseline_hr <= 0:
        return None

    half_w = config.drift_window_s // 2
    scan_start = baseline_end + config.drift_window_s
    for seg in work_steady:
        seg_scan_start = max(seg.start_index, scan_start)
        for i in range(seg_scan_start, seg.end_index + 1):
            lo = max(seg.start_index, i - half_w)
            hi = min(seg.end_index, i + half_w)
            window_hr = heartrate[lo:hi + 1]
            if not window_hr:
                continue
            avg_hr = sum(window_hr) / len(window_hr)
            rise_pct = (avg_hr - baseline_hr) / baseline_hr * 100
            if rise_pct >= config.drift_onset_hr_rise_pct:
                return Moment(
                    type=MomentType.cardiac_drift_onset.value,
                    index=i, time_s=time[i], value=round(rise_pct, 2),
                )
    return None


def _detect_pace_anomalies(
    time: List[int], velocity: List[float],
    segments: List[Segment], config: MomentConfig,
) -> List[Moment]:
    """Detect pace surges and fades within segments."""
    moments = []
    for seg in segments:
        if seg.type in ("warmup", "cooldown") or seg.duration_s < 60:
            continue
        si, ei = seg.start_index, seg.end_index
        v_slice = velocity[si:ei + 1]
        valid_v = [v for v in v_slice if v > 0.5]
        if not valid_v:
            continue
        seg_avg_v = sum(valid_v) / len(valid_v)
        if seg_avg_v <= 0:
            continue

        surge_start = fade_start = None
        for j, v in enumerate(v_slice):
            idx = si + j
            if v > seg_avg_v * (1 + config.pace_surge_fraction):
                if surge_start is None:
                    surge_start = idx
                elif idx - surge_start >= config.min_moment_duration:
                    moments.append(Moment(
                        type=MomentType.pace_surge.value, index=surge_start,
                        time_s=time[surge_start],
                        value=round((v / seg_avg_v - 1) * 100, 1),
                    ))
                    surge_start = None
            else:
                surge_start = None

            if v < seg_avg_v * (1 - config.pace_fade_fraction) and v > 0.5:
                if fade_start is None:
                    fade_start = idx
                elif idx - fade_start >= config.min_moment_duration:
                    moments.append(Moment(
                        type=MomentType.pace_fade.value, index=fade_start,
                        time_s=time[fade_start],
                        value=round((1 - v / seg_avg_v) * 100, 1),
                    ))
                    fade_start = None
            else:
                fade_start = None
    return moments


def _detect_cadence_anomalies(
    time: List[int], cadence: List[float],
    segments: List[Segment], config: MomentConfig,
) -> List[Moment]:
    """Detect cadence drops and surges within segments."""
    moments = []
    for seg in segments:
        if seg.duration_s < 60:
            continue
        si, ei = seg.start_index, seg.end_index
        cad_slice = cadence[si:ei + 1]
        valid_cad = [c for c in cad_slice if c > 0]
        if not valid_cad:
            continue
        seg_avg_cad = sum(valid_cad) / len(valid_cad)

        drop_start = surge_start = None
        for j, c in enumerate(cad_slice):
            idx = si + j
            if c < seg_avg_cad - config.cadence_drop_threshold:
                if drop_start is None:
                    drop_start = idx
                elif idx - drop_start >= config.min_moment_duration:
                    moments.append(Moment(
                        type=MomentType.cadence_drop.value, index=drop_start,
                        time_s=time[drop_start],
                        value=round(seg_avg_cad - c, 1),
                    ))
                    drop_start = None
            else:
                drop_start = None

            if c > seg_avg_cad + config.cadence_surge_threshold:
                if surge_start is None:
                    surge_start = idx
                elif idx - surge_start >= config.min_moment_duration:
                    moments.append(Moment(
                        type=MomentType.cadence_surge.value, index=surge_start,
                        time_s=time[surge_start],
                        value=round(c - seg_avg_cad, 1),
                    ))
                    surge_start = None
            else:
                surge_start = None
    return moments


def _detect_grade_anomalies(
    time: List[int], velocity: List[float], heartrate: List[float],
    grade: List[float], segments: List[Segment], config: MomentConfig,
) -> List[Moment]:
    """Detect points where pace anomaly is explained by grade."""
    moments = []
    for seg in segments:
        if seg.duration_s < 60 or seg.type in ("warmup", "cooldown"):
            continue
        si, ei = seg.start_index, seg.end_index
        v_slice = velocity[si:ei + 1]
        valid_v = [v for v in v_slice if v > 0.5]
        if not valid_v:
            continue
        seg_avg_v = sum(valid_v) / len(valid_v)
        seg_max_hr = max(heartrate[si:ei + 1]) if heartrate else 0

        for j in range(len(v_slice)):
            idx = si + j
            v = v_slice[j]
            g = grade[idx] if idx < len(grade) else 0
            hr = heartrate[idx] if idx < len(heartrate) else 0

            if (abs(g) >= config.grade_threshold_pct
                    and v < seg_avg_v * config.grade_pace_deviation
                    and seg_max_hr > 0
                    and hr > config.grade_hr_fraction * seg_max_hr):
                moments.append(Moment(
                    type=MomentType.grade_adjusted_anomaly.value,
                    index=idx, time_s=time[idx], value=round(g, 1),
                ))
                break  # One per segment
    return moments


# ---------------------------------------------------------------------------
# 4) PLAN SUMMARY COMPARISON
# ---------------------------------------------------------------------------

def compare_plan_summary(
    segments: List[Segment],
    stream_data: Dict[str, List],
    planned_workout: Optional[Dict[str, Any]],
) -> Optional[PlanComparison]:
    """Compare detected segments against a planned workout (summary level).

    Additive enrichment — returns None when no plan exists.
    """
    if planned_workout is None:
        return None

    time = stream_data.get("time", [])
    distance = stream_data.get("distance", [])
    velocity = stream_data.get("velocity_smooth", [])

    actual_duration_min = None
    if time and len(time) >= 2:
        actual_duration_min = round((time[-1] - time[0]) / 60.0, 1)

    actual_distance_km = None
    if distance and len(distance) >= 2:
        actual_distance_km = round(distance[-1] / 1000.0, 2)

    actual_pace_s_km = None
    if velocity:
        valid_v = [v for v in velocity if v > 0.5]
        if valid_v:
            avg_v = sum(valid_v) / len(valid_v)
            actual_pace_s_km = round(1000.0 / avg_v, 1) if avg_v > 0 else None

    planned_duration_min = planned_workout.get("target_duration_minutes")
    if planned_duration_min is not None:
        planned_duration_min = float(planned_duration_min)

    planned_distance_km = planned_workout.get("target_distance_km")
    if planned_distance_km is not None:
        planned_distance_km = float(planned_distance_km)

    planned_pace_s_km = planned_workout.get("target_pace_per_km_seconds")
    if planned_pace_s_km is not None:
        planned_pace_s_km = float(planned_pace_s_km)

    duration_delta = None
    if actual_duration_min is not None and planned_duration_min is not None:
        duration_delta = round(actual_duration_min - planned_duration_min, 1)

    distance_delta = None
    if actual_distance_km is not None and planned_distance_km is not None:
        distance_delta = round(actual_distance_km - planned_distance_km, 2)

    pace_delta = None
    if actual_pace_s_km is not None and planned_pace_s_km is not None:
        pace_delta = round(actual_pace_s_km - planned_pace_s_km, 1)

    planned_interval_count = None
    detected_work_count = None
    interval_count_match = None
    plan_segments = planned_workout.get("segments")
    if plan_segments and isinstance(plan_segments, list):
        for ps in plan_segments:
            if isinstance(ps, dict) and ps.get("type") == "interval":
                planned_interval_count = ps.get("reps")
                break
        if planned_interval_count is not None:
            detected_work_count = len([s for s in segments if s.type == SegmentType.work.value])
            interval_count_match = detected_work_count == planned_interval_count

    return PlanComparison(
        planned_duration_min=planned_duration_min,
        actual_duration_min=actual_duration_min,
        duration_delta_min=duration_delta,
        planned_distance_km=planned_distance_km,
        actual_distance_km=actual_distance_km,
        distance_delta_km=distance_delta,
        planned_pace_s_km=planned_pace_s_km,
        actual_pace_s_km=actual_pace_s_km,
        pace_delta_s_km=pace_delta,
        planned_interval_count=planned_interval_count,
        detected_work_count=detected_work_count,
        interval_count_match=interval_count_match,
    )


# ---------------------------------------------------------------------------
# 5) TOP-LEVEL ORCHESTRATOR
# ---------------------------------------------------------------------------

def analyze_stream(
    stream_data: Dict[str, List],
    channels_available: List[str],
    planned_workout: Optional[Dict[str, Any]] = None,
    athlete_context: Optional[AthleteContext] = None,
) -> StreamAnalysisResult:
    """Analyze a run's per-second stream data.

    Main entry point. Returns a complete, first-class result regardless
    of whether a plan or athlete profile exists.

    Args:
        stream_data: Dict mapping channel names to lists of values.
        channels_available: List of channel names present.
        planned_workout: Optional plan metadata. None is normal.
        athlete_context: Optional athlete physiology. None → Tier 4.
    """
    tier, estimated_flags = _resolve_tier(athlete_context)
    cross_run_comparable = not tier.startswith("tier4")

    channels_present = [ch for ch in channels_available if ch in stream_data]
    channels_missing = [ch for ch in ALL_CHANNELS if ch not in channels_present]

    time = stream_data.get("time")
    if not isinstance(time, list) or len(time) < 2:
        return StreamAnalysisResult(
            channels_present=channels_present,
            channels_missing=list(ALL_CHANNELS),
            point_count=0 if not isinstance(time, list) else len(time),
            confidence=0.0,
            tier_used=tier, estimated_flags=estimated_flags,
            cross_run_comparable=cross_run_comparable,
        )

    n = len(time)
    velocity = _safe_list(stream_data, "velocity_smooth", n)
    heartrate = _safe_list(stream_data, "heartrate", n)
    cadence = _safe_list(stream_data, "cadence", n)
    grade = _safe_list(stream_data, "grade_smooth", n)

    segments = detect_segments(
        time, velocity, heartrate, grade,
        athlete_context=athlete_context,
    )

    work_steady = [s for s in segments if s.type in (
        SegmentType.work.value, SegmentType.steady.value)]
    drift = compute_drift(time, heartrate, velocity, cadence, work_steady)

    moments = detect_moments(time, heartrate, velocity, cadence, grade, segments)

    plan_comparison = compare_plan_summary(segments, stream_data, planned_workout)

    confidence = _compute_confidence(tier, n, channels_present, segments)

    # RSI-Alpha: per-point effort intensity
    effort_array = _compute_effort_array(
        stream_data=stream_data,
        point_count=n,
        tier=tier,
        ctx=athlete_context,
    )

    return StreamAnalysisResult(
        segments=segments, drift=drift, moments=moments,
        plan_comparison=plan_comparison,
        channels_present=channels_present, channels_missing=channels_missing,
        point_count=n, confidence=confidence,
        tier_used=tier, estimated_flags=estimated_flags,
        cross_run_comparable=cross_run_comparable,
        effort_intensity=effort_array,
    )


# ---------------------------------------------------------------------------
# Confidence (tier-anchored, data-quality-adjusted)
# ---------------------------------------------------------------------------

# Base confidence by tier — higher tier = better physiological calibration
_TIER_BASE_CONFIDENCE = {
    "tier1_threshold_hr": 0.90,
    "tier2_estimated_hrr": 0.75,
    "tier3_max_hr": 0.60,
    "tier4_stream_relative": 0.45,
}


def _compute_confidence(
    tier: str,
    point_count: int,
    channels_present: List[str],
    segments: List[Segment],
) -> float:
    """Deterministic confidence score in [0, 1].

    Anchored by tier, adjusted for data quality:
        - Volume factor (plateau at 3600 points)
        - Channel coverage (-0.10 per missing key channel)
        - Segment quality (+0.05 for 2+ distinct types)

    NOT affected by whether a plan exists.
    Guarantees: tier1 >= tier2 >= tier3 >= tier4 on identical data.
    """
    base = _TIER_BASE_CONFIDENCE.get(tier, 0.45)

    # Volume factor: 0.0 at 0 points, 1.0 at 3600+ points
    volume_factor = min(1.0, point_count / 3600.0)

    # Channel penalty: -0.10 per missing key channel
    key_channels = {"velocity_smooth", "heartrate", "cadence"}
    missing_key = sum(1 for ch in key_channels if ch not in channels_present)
    channel_adjustment = -0.10 * missing_key

    # Segment quality bonus
    distinct_types = len(set(s.type for s in segments))
    segment_bonus = 0.05 if distinct_types >= 2 else 0.0

    confidence = base * volume_factor + channel_adjustment + segment_bonus

    return round(_clamp(0.0, 1.0, confidence), 4)
