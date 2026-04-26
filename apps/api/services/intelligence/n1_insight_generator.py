"""N=1 personalized insight generator (Phase 3C).

Transforms statistically significant per-athlete correlations into
human-readable, data-derived insights.  All insights:
- Pass Bonferroni-corrected significance + effect size + sample gates.
- Use "YOUR …" phrasing — observation, not prescription.
- Never leak internal metric acronyms (TSB, CTL, ATL, EF, VDOT, etc.).
- Scale confidence with data volume + effect strength.

=============================================================================
ATHLETE TRUST SAFETY CONTRACT — Efficiency Interpretation (Phase 3C Scope)
=============================================================================

1. DIRECTIONAL CLAIMS REQUIRE EXPLICIT POLARITY METADATA.
   Athlete-facing "improving / declining / better / worse" is allowed only
   when the output metric's OutputMetricMeta defines unambiguous polarity.

2. TWO-TIER FAIL-CLOSED BEHAVIOR.
   • Tier 1 — Ambiguous polarity (polarity_ambiguous == True):
     Show neutral observation text only; classify as "pattern".
   • Tier 2 — Missing / invalid / conflicting metadata:
     Suppress directional interpretation entirely.  Return structured
     evidence data only, or suppress the insight.

3. NO SIGN-ONLY INFERENCE.
   Correlation sign alone (r > 0 / r < 0) must never determine
   "beneficial" or "harmful" without polarity metadata from the registry.

4. APPROVED DIRECTIONAL OUTPUT WHITELIST (Phase 3C).
   Directional athlete-facing language is permitted ONLY for metrics
   listed in DIRECTIONAL_SAFE_METRICS:
     pace_easy, pace_threshold, race_pace   (lower is better)
     completion_rate, completion, pb_events  (higher is better)
   Any new metric requires OutputMetricMeta registration with explicit
   polarity before directional language is permitted.

5. SINGLE REGISTRY AUTHORITY FOR 3C.
   OutputMetricMeta + OUTPUT_METRIC_REGISTRY is the sole source of truth
   for metric definition, polarity, and interpretation in the 3C pipeline.
   No local overrides, no inline sign-flipping.

6. TRUST OVER VERBOSITY.
   When interpretation certainty is low, prefer short neutral language
   over explanatory directional certainty.

7. REGRESSION PROTECTIONS (REQUIRED).
   Tests must cover: mixed-scenario (same pace / lower HR AND same HR /
   faster pace), ambiguity-neutral wording, and missing-metadata
   suppression.

8. CURRENT SCOPE + DEBT NOTE.
   This contract is enforced now in the 3C insight layer
   (n1_insight_generator → _build_insight_text → _categorize path).
   Legacy services with local polarity logic (load_response_explain,
   causal_attribution, coach_tools, home_signals, calendar_signals,
   pattern_recognition, run_analysis_engine, ai_coach) are tracked as
   migration debt.  See comments referencing OutputMetricMeta in those
   files.
=============================================================================
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from services.intelligence.narration_tiers import evidence_phrase as _n1_evidence_phrase


# ---------------------------------------------------------------------------
# Banned acronym / internal-label check
# ---------------------------------------------------------------------------

BANNED_LABELS = {
    "TSB", "CTL", "ATL", "VDOT", "rMSSD", "SDNN", "EF", "TRIMP",
}

BANNED_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(b) for b in BANNED_LABELS) + r")\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Human-friendly name mapping for correlation inputs
# ---------------------------------------------------------------------------

FRIENDLY_NAMES: Dict[str, str] = {
    "weekly_volume_km": "weekly running volume",
    "weekly_volume_mi": "weekly mileage",
    "long_run_distance_km": "long run distance",
    "long_run_distance_mi": "long run distance",
    "avg_hr": "average heart rate",
    "max_hr": "max heart rate",
    "duration_s": "run duration",
    "intensity_score": "session intensity",
    "sleep_hours": "sleep duration",
    "sleep_h": "sleep duration",
    "daily_protein_g": "daily protein intake",
    "daily_carbs_g": "daily carb intake",
    "hrv_rmssd": "heart-rate variability",
    "resting_hr": "resting heart rate",
    "elevation_gain": "elevation gain",
    "recovery_days": "recovery days between quality sessions",
    "threshold_volume": "threshold training volume",
    "interval_volume": "interval training volume",
    "easy_volume": "easy running volume",
    "efficiency": "running efficiency",
    "pace_easy": "easy pace",
    "completion_rate": "workout completion rate",
    "tsb": "form (training readiness)",
    "ctl": "fitness (training load)",
    "atl": "fatigue (recent load)",
    "chronic_load": "fitness (training load)",
    "acute_load": "fatigue (recent load)",
    "form_score": "form (training readiness)",

    # GarminDay wearable
    "garmin_sleep_score": "Garmin sleep score",
    "garmin_sleep_deep_s": "deep sleep time",
    "garmin_sleep_rem_s": "REM sleep time",
    "garmin_sleep_awake_s": "awake time during sleep",
    # garmin_body_battery_*, garmin_avg_stress, garmin_max_stress are
    # Garmin proprietary model outputs and intentionally not surfaced here.
    "garmin_steps": "daily step count",
    "garmin_active_time_s": "daily active time",
    "garmin_moderate_intensity_s": "moderate intensity time",
    "garmin_vigorous_intensity_s": "vigorous intensity time",
    "garmin_hrv_5min_high": "Recovery HRV",
    "garmin_min_hr": "lowest daily heart rate",
    "hrv_rhr_ratio": "recovery ratio (HRV÷RHR)",
    "garmin_resting_hr": "resting heart rate",
    "garmin_hrv_overnight_avg": "overnight HRV",
    "garmin_vo2max": "Garmin VO2max",

    # Activity-level
    "dew_point_f": "dew point",
    "heat_adjustment_pct": "heat impact",
    "temperature_f": "temperature",
    "humidity_pct": "humidity",
    "elevation_gain_m": "elevation gain",
    "avg_cadence": "running cadence",
    "avg_stride_length_m": "stride length",
    "avg_ground_contact_ms": "ground contact time",
    "avg_vertical_oscillation_cm": "vertical bounce",
    "avg_vertical_ratio_pct": "vertical ratio",
    "avg_power_w": "running power",
    "max_power_w": "peak power",
    "total_descent_m": "descent",
    "moving_time_s": "moving time",
    # garmin_aerobic_te, garmin_anaerobic_te, garmin_body_battery_impact
    # are Garmin proprietary models — not used. garmin_perceived_effort is
    # surfaced (with attribution) only via services/effort_resolver when no
    # ActivityFeedback exists for the activity.
    "activity_intensity_score": "session intensity",
    "active_kcal": "calories burned",
    "run_start_hour": "time of day",

    # Feedback/reflection
    "feedback_perceived_effort": "post-run perceived effort",
    "feedback_energy_pre": "pre-run energy",
    "feedback_energy_post": "post-run energy",
    "feedback_leg_feel": "leg freshness",
    "reflection_vs_expected": "run vs expectations",

    # Checkin/composition/nutrition
    "sleep_quality_1_5": "sleep quality",
    "readiness_1_5": "self-rated readiness",
    "stress_1_5": "stress level",
    "soreness_1_5": "soreness",
    "enjoyment_1_5": "run enjoyment",
    "confidence_1_5": "confidence",
    "rpe_1_10": "perceived effort",
    "body_fat_pct": "body fat percentage",
    "muscle_mass_kg": "muscle mass",
    "daily_fat_g": "daily fat intake",
    "daily_fiber_g": "daily fiber intake",
    "daily_caffeine_mg": "daily caffeine intake",
    "daily_calories": "daily calorie intake",
    "weight_kg": "body weight",
    "bmi": "body mass index",

    # Training patterns
    "days_since_quality": "rest since last hard session",
    "consecutive_run_days": "consecutive running days",
    "days_since_rest": "days without rest",
    "long_run_ratio": "long run proportion",
    "weekly_elevation_m": "weekly elevation gain",

    # Work/life context
    "work_stress": "work stress",
    "work_hours": "hours worked",
    "overnight_avg_hr": "overnight heart rate",
    "hrv_sdnn": "heart-rate variability (SDNN)",
    "daily_session_stress": "training session stress",
    "pace_threshold": "threshold pace",
    "completion": "workout completion",
    "efficiency_threshold": "threshold running efficiency",

    # Cross-training (Phase A)
    "ct_strength_sessions": "strength training sessions",
    "ct_strength_duration_min": "strength training duration",
    "ct_lower_body_sets": "lower body strength sets",
    "ct_upper_body_sets": "upper body strength sets",
    "ct_core_sets": "core training sets",
    "ct_plyometric_sets": "explosive/plyometric sets",
    "ct_heavy_sets": "heavy resistance sets",
    "ct_total_volume_kg": "total strength volume",
    "ct_unilateral_sets": "single-leg exercise sets",
    "ct_strength_lag_24h": "strength within 24 hours before run",
    "ct_strength_lag_48h": "strength within 48 hours before run",
    "ct_strength_lag_72h": "strength within 72 hours before run",
    "ct_hours_since_strength": "hours between strength and running",
    "ct_strength_frequency_7d": "strength sessions per week",
    "ct_cycling_duration_min": "cycling duration",
    "ct_cycling_tss": "cycling training stress",
    "ct_flexibility_sessions_7d": "flexibility sessions per week",
    "ct_strength_sessions_7d": "strength sessions (7-day)",
    "ct_strength_tss_7d": "strength training stress (7-day)",
    "ct_cycling_tss_7d": "cycling training stress (7-day)",
    "ct_cross_training_tss_7d": "cross-training load (7-day)",
    "ct_hours_since_cross_training": "hours since last cross-training",

    # V2 derived signals
    "garmin_hrv_5min_high_trend_3d": "3-day HRV trend",
    "garmin_hrv_5min_high_trend_5d": "5-day HRV trend",
    "garmin_hrv_overnight_avg_trend_3d": "3-day overnight HRV trend",
    "garmin_hrv_overnight_avg_trend_5d": "5-day overnight HRV trend",
    "garmin_resting_hr_trend_5d": "5-day resting HR trend",
    "garmin_resting_hr_trend_14d": "14-day resting HR trend",
    "garmin_min_hr_trend_5d": "5-day minimum HR trend",
    "garmin_min_hr_trend_14d": "14-day minimum HR trend",
    "garmin_sleep_score_trend_3d": "3-day sleep trend",
    "garmin_sleep_score_trend_5d": "5-day sleep trend",
    "garmin_hrv_5min_high_deviation": "HRV deviation from baseline",
    "garmin_hrv_overnight_avg_deviation": "overnight HRV deviation from baseline",
    "garmin_resting_hr_deviation": "resting HR deviation from baseline",
    "garmin_min_hr_deviation": "minimum HR deviation from baseline",
    "tsb_trend_5d": "5-day freshness trend",
    "tsb_trend_14d": "14-day freshness trend",
    "tsb_state_days": "days above/below normal freshness",

    # V2 interaction terms
    "load_x_recovery": "training load × recovery interaction",
    "sleep_quality_x_session_intensity": "sleep quality × session intensity",
    "hrv_rhr_convergence": "HRV-RHR recovery convergence",
    "heat_stress_index": "combined heat stress",
    "hrv_rhr_divergence_flag": "HRV-RHR trend divergence",
}


def _friendly(raw_name: str) -> str:
    """Convert internal metric name to human-friendly label."""
    return FRIENDLY_NAMES.get(raw_name, raw_name.replace("_", " "))


def friendly_signal_name(raw_name: str) -> str:
    """Public alias for _friendly(). Import this in routers/renderers."""
    return _friendly(raw_name)


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------

@dataclass
class N1Insight:
    text: str
    source: str = "n1"
    confidence: float = 0.0
    evidence: Dict[str, Any] = field(default_factory=dict)
    category: str = "pattern"  # "what_works", "what_doesnt", "pattern"
    fingerprint: str = ""      # stable suppression key: input_name:direction:output_metric


# ---------------------------------------------------------------------------
# Canonical output-metric contract
# ---------------------------------------------------------------------------
# Each output metric carries explicit metadata so that downstream consumers
# (insight text, categorisation, coach tools) never guess polarity from sign.
#
# DESIGN RULE: raw `efficiency` (pace_sec_km / avg_hr, uncontrolled) is
# directionally ambiguous — its ratio rises when HR drops at fixed pace
# (good) but falls when pace improves at fixed HR (also good).  We therefore
# mark it `polarity_ambiguous=True` and refuse to emit directional claims
# ("what works / doesn't") from it.  Unambiguous alternatives exist:
#   - pace_at_effort  (zone-filtered pace; lower = faster = better)
#   - hr_at_fixed_pace (lower = better)
#   - speed_at_fixed_hr (higher = better)
#   - completion / completion_rate (higher = better)

@dataclass
class OutputMetricMeta:
    """Contract describing how to interpret an output metric's direction."""
    metric_key: str
    metric_definition: str
    higher_is_better: Optional[bool]       # None → ambiguous
    polarity_ambiguous: bool               # True → no directional claims allowed
    direction_interpretation: str          # human-readable note for audit


OUTPUT_METRIC_REGISTRY: Dict[str, OutputMetricMeta] = {
    "efficiency": OutputMetricMeta(
        metric_key="efficiency",
        metric_definition="pace(sec/km) / avg_hr(bpm) — uncontrolled ratio",
        higher_is_better=None,
        polarity_ambiguous=True,
        direction_interpretation=(
            "Ambiguous: ratio rises when HR drops (good) but falls when "
            "pace improves (also good). Do not infer direction from sign."
        ),
    ),
    "efficiency_threshold": OutputMetricMeta(
        metric_key="efficiency_threshold",
        metric_definition="pace(sec/km) / avg_hr within threshold HR zone (80-88% max HR)",
        higher_is_better=None,
        polarity_ambiguous=True,
        direction_interpretation=(
            "Zone-filtered but still a ratio of two co-moving variables. "
            "Safer than raw efficiency but not fully unambiguous."
        ),
    ),
    "efficiency_easy": OutputMetricMeta(
        metric_key="efficiency_easy",
        metric_definition="pace(sec/km) / avg_hr within easy HR zone (<75% max HR)",
        higher_is_better=None,
        polarity_ambiguous=True,
        direction_interpretation="Zone-filtered efficiency ratio — still ambiguous.",
    ),
    "efficiency_race": OutputMetricMeta(
        metric_key="efficiency_race",
        metric_definition="pace(sec/km) / avg_hr within race HR zone (>88% max HR)",
        higher_is_better=None,
        polarity_ambiguous=True,
        direction_interpretation="Zone-filtered efficiency ratio — still ambiguous.",
    ),
    "efficiency_hard": OutputMetricMeta(
        metric_key="efficiency_hard",
        metric_definition="pace(sec/km) / avg_hr for interval/VO2max sessions",
        higher_is_better=None,
        polarity_ambiguous=True,
        direction_interpretation="Zone-filtered efficiency ratio — still ambiguous.",
    ),
    "recovery_rate": OutputMetricMeta(
        metric_key="recovery_rate",
        metric_definition="HRV rebound 48h after hard session (delta / pre-session HRV)",
        higher_is_better=True,
        polarity_ambiguous=False,
        direction_interpretation="Higher = faster HRV recovery after hard sessions = better.",
    ),
    "efficiency_trend": OutputMetricMeta(
        metric_key="efficiency_trend",
        metric_definition="Rolling % change in zone-filtered efficiency vs baseline",
        higher_is_better=None,
        polarity_ambiguous=True,
        direction_interpretation="Trend of ambiguous base metric — inherits ambiguity.",
    ),
    "pace_easy": OutputMetricMeta(
        metric_key="pace_easy",
        metric_definition="pace(sec/km) at easy effort — single controlled variable",
        higher_is_better=False,
        polarity_ambiguous=False,
        direction_interpretation="Lower pace = faster at easy effort = unambiguously better.",
    ),
    "pace_threshold": OutputMetricMeta(
        metric_key="pace_threshold",
        metric_definition="pace(sec/km) at threshold effort — single controlled variable",
        higher_is_better=False,
        polarity_ambiguous=False,
        direction_interpretation="Lower pace = faster at threshold effort = unambiguously better.",
    ),
    "completion_rate": OutputMetricMeta(
        metric_key="completion_rate",
        metric_definition="Fraction of planned workout completed",
        higher_is_better=True,
        polarity_ambiguous=False,
        direction_interpretation="Higher = more of the plan completed = unambiguously better.",
    ),
    "completion": OutputMetricMeta(
        metric_key="completion",
        metric_definition="Binary/fractional workout completion",
        higher_is_better=True,
        polarity_ambiguous=False,
        direction_interpretation="Higher = completed more = unambiguously better.",
    ),
    "pb_events": OutputMetricMeta(
        metric_key="pb_events",
        metric_definition="Personal best event occurrences",
        higher_is_better=True,
        polarity_ambiguous=False,
        direction_interpretation="More PB events = unambiguously better.",
    ),
    "race_pace": OutputMetricMeta(
        metric_key="race_pace",
        metric_definition="pace(sec/km) in race activities",
        higher_is_better=False,
        polarity_ambiguous=False,
        direction_interpretation="Lower pace = faster race = unambiguously better.",
    ),
    # --- Phase 2: Run Stream Analysis metrics ---
    "cardiac_drift_pct": OutputMetricMeta(
        metric_key="cardiac_drift_pct",
        metric_definition="Percentage HR rise from first-half to second-half of work/steady segments",
        higher_is_better=None,
        polarity_ambiguous=True,
        direction_interpretation=(
            "Ambiguous: drift rises with fatigue (expected in long runs) but also "
            "with dehydration or heat. Context-dependent — do not infer directional quality."
        ),
    ),
    "pace_drift_pct": OutputMetricMeta(
        metric_key="pace_drift_pct",
        metric_definition="Percentage velocity change from first-half to second-half of work segments",
        higher_is_better=None,
        polarity_ambiguous=True,
        direction_interpretation=(
            "Ambiguous: positive = got faster (negative split, often good) but also "
            "could mean started too slow. Negative = slowed (normal in long runs). "
            "Do not infer direction without workout context."
        ),
    ),
    "cadence_trend_bpm_per_km": OutputMetricMeta(
        metric_key="cadence_trend_bpm_per_km",
        metric_definition="Linear cadence change (steps/min) per km over work segments",
        higher_is_better=None,
        polarity_ambiguous=True,
        direction_interpretation=(
            "Ambiguous: cadence changes interact with pace, fatigue, and terrain. "
            "Dropping cadence may indicate fatigue or intentional lengthening. "
            "Do not infer directional quality."
        ),
    ),
    "plan_execution_variance": OutputMetricMeta(
        metric_key="plan_execution_variance",
        metric_definition="Summary-level delta between planned and actual workout metrics",
        higher_is_better=None,
        polarity_ambiguous=True,
        direction_interpretation=(
            "Ambiguous: over-executing a plan may be harmful (injury risk), "
            "under-executing may be adaptive (recovery). Do not infer direction."
        ),
    ),
}


# ---------------------------------------------------------------------------
# Directional-safe whitelist (Contract §4)
# ---------------------------------------------------------------------------
# Only these metrics may produce "what_works" / "what_doesnt" categories
# or "tends to improve / decline" athlete-facing text.  All others are
# observation-only.  Adding a metric here requires a registered
# OutputMetricMeta with polarity_ambiguous=False.

DIRECTIONAL_SAFE_METRICS: frozenset = frozenset({
    "pace_easy",
    "pace_threshold",
    "race_pace",
    "completion_rate",
    "completion",
    "pb_events",
    "recovery_rate",
})


def get_metric_meta(output_metric: str) -> OutputMetricMeta:
    """Look up metric metadata.  Unknown metrics are treated as ambiguous."""
    return OUTPUT_METRIC_REGISTRY.get(
        output_metric,
        OutputMetricMeta(
            metric_key=output_metric,
            metric_definition=f"Unknown metric: {output_metric}",
            higher_is_better=None,
            polarity_ambiguous=True,
            direction_interpretation="Unknown metric — polarity not registered.",
        ),
    )


def _validate_metric_meta(meta: OutputMetricMeta) -> bool:
    """Check whether metric metadata is valid and internally consistent.

    Returns False (→ tier-2 suppression) when:
    - polarity_ambiguous is False but higher_is_better is None (conflicting)
    - polarity_ambiguous is True but higher_is_better is not None (conflicting)
    - metric_definition is empty
    """
    if not meta.metric_definition:
        return False
    if meta.polarity_ambiguous and meta.higher_is_better is not None:
        return False  # Conflicting: claims ambiguous but also declares polarity
    if not meta.polarity_ambiguous and meta.higher_is_better is None:
        return False  # Conflicting: claims unambiguous but has no polarity
    return True


# ---------------------------------------------------------------------------
# Novelty gate — suppress findings that are obvious to any runner
# ---------------------------------------------------------------------------
# These input→output pairs are universally known. "Fresh legs help
# performance" and "more sleep helps" are not insights — they're axioms.
# A finding is only worth saying if the athlete would say "I didn't know that."

_OBVIOUS_PAIRS: frozenset = frozenset({
    ("feedback_leg_feel", "efficiency"),
    ("feedback_leg_feel", "efficiency_easy"),
    ("feedback_leg_feel", "efficiency_threshold"),
    ("feedback_leg_feel", "pace_easy"),
    ("feedback_leg_feel", "pace_threshold"),
    ("feedback_energy_pre", "efficiency"),
    ("feedback_energy_pre", "pace_easy"),
    ("readiness_1_5", "efficiency"),
    ("readiness_1_5", "pace_easy"),
    ("soreness_1_5", "efficiency"),
    ("soreness_1_5", "pace_easy"),
    ("sleep_quality_1_5", "efficiency"),
    ("sleep_quality_1_5", "efficiency_easy"),
    ("sleep_quality_1_5", "efficiency_threshold"),
    ("sleep_quality_1_5", "pace_easy"),
    ("sleep_hours", "efficiency"),
    ("sleep_hours", "efficiency_easy"),
    ("sleep_hours", "efficiency_threshold"),
    ("sleep_h", "efficiency"),
    ("sleep_h", "efficiency_easy"),
    ("garmin_sleep_score", "efficiency"),
    ("garmin_sleep_score", "efficiency_easy"),
    ("garmin_sleep_score", "pace_easy"),
})

# These inputs are universally known to affect performance.
# Only worth showing if threshold data makes them specific.
_OBVIOUS_INPUTS_IF_NO_THRESHOLD: frozenset = frozenset({
    "feedback_leg_feel",
    "feedback_energy_pre",
    "readiness_1_5",
    "sleep_quality_1_5",
    "sleep_hours",
    "sleep_h",
    "garmin_sleep_score",
})


def _is_obvious(input_name: str, output_metric: str, has_threshold: bool = False) -> bool:
    """Return True if this finding is too obvious to surface.

    Findings with specific threshold data are promoted past the gate —
    "fresh legs help" is obvious, but "your pace suffers specifically
    when leg freshness drops below 3/5" is not.
    """
    if (input_name, output_metric) in _OBVIOUS_PAIRS and not has_threshold:
        return True
    if input_name in _OBVIOUS_INPUTS_IF_NO_THRESHOLD and not has_threshold:
        return True
    return False


def _is_beneficial(direction: str, output_metric: str) -> Optional[bool]:
    """Determine if the correlation direction is beneficial for the athlete.

    Implements the two-tier fail-closed contract:
      - Tier 1 (ambiguous polarity): returns None → neutral text
      - Tier 2 (invalid/missing metadata OR not in whitelist): returns None
      - Unambiguous + whitelisted: returns True/False

    Returns:
        True  — beneficial (what_works)  — only for whitelisted unambiguous metrics
        False — harmful   (what_doesnt) — only for whitelisted unambiguous metrics
        None  — neutral   (pattern)     — ambiguous, invalid, or not whitelisted
    """
    meta = get_metric_meta(output_metric)

    # Tier 2: invalid / conflicting metadata → suppress directional output
    if not _validate_metric_meta(meta):
        return None

    # Tier 1: ambiguous polarity → neutral observation only
    if meta.polarity_ambiguous:
        return None

    # Whitelist gate (Contract §4): even if metadata says unambiguous,
    # directional language requires explicit whitelist membership
    if output_metric not in DIRECTIONAL_SAFE_METRICS:
        return None

    raw_positive = direction == "positive"
    return raw_positive == meta.higher_is_better


# ---------------------------------------------------------------------------
# Insight text generation
# ---------------------------------------------------------------------------

def _build_insight_text(
    input_name: str,
    direction: str,
    strength: str,
    r: float,
    lag_days: int,
    output_metric: str = "efficiency",
    threshold_value: Optional[float] = None,
    threshold_direction: Optional[str] = None,
    times_confirmed: Optional[int] = None,
) -> Optional[str]:
    """Build a coaching-voice insight sentence from correlation data.

    When threshold data is available, produces specific language:
      "When your sleep drops below 6.5 hours, your easy pace tends to
       suffer the next day."

    Without threshold data, produces a general but still coaching-voiced
    observation:
      "Your easy pace is linked to your sleep duration — more sleep,
       faster easy pace the next day."

    Respects the Athlete Trust Safety Contract:
      - Ambiguous metrics get neutral language (no "improves/declines")
      - Directional claims only for whitelisted unambiguous metrics
    """
    friendly_input = _friendly(input_name)
    friendly_output = _friendly(output_metric)

    if lag_days == 0:
        timing = ""
    elif lag_days == 1:
        timing = " the next day"
    else:
        timing = f" over the next {lag_days} days"

    confirmation = ""
    if times_confirmed and times_confirmed >= 3:
        confirmation = f" Pattern {_n1_evidence_phrase(times_confirmed)}."

    beneficial = _is_beneficial(direction, output_metric)

    # --- THRESHOLD PATH: specific language with threshold enrichment ---
    if threshold_value is not None and threshold_direction:
        threshold_rounded = _format_threshold(input_name, threshold_value)

        if threshold_direction == "below_matters":
            condition = f"When your {friendly_input} drops below {threshold_rounded}"
            # Below threshold = less input. If more input helps (beneficial),
            # then less input hurts → "suffers". Vice versa.
            outcome_is_bad = beneficial is True
        else:
            condition = f"When your {friendly_input} goes above {threshold_rounded}"
            # Above threshold = more input. If more input helps (beneficial),
            # then more input helps → "benefits". Vice versa.
            outcome_is_bad = beneficial is False

        if beneficial is None:
            return None
        elif outcome_is_bad:
            text = f"{condition}, your {friendly_output} tends to suffer{timing}.{confirmation}"
        else:
            text = f"{condition}, your {friendly_output} tends to benefit{timing}.{confirmation}"

        return text

    # --- GENERAL PATH: no threshold, coaching-voiced observation ---
    # beneficial=True means MORE input is good for the athlete.
    # beneficial=False means MORE input is bad.
    # The correlation direction (positive/negative) determines the
    # input-output mechanical relationship, but the athlete cares about
    # what to DO — more or less of the input.
    if beneficial is None:
        return None
    elif beneficial:
        text = (
            f"More {friendly_input} tends to help your {friendly_output}{timing}."
            f"{confirmation}"
        )
    else:
        text = (
            f"More {friendly_input} tends to hurt your {friendly_output}{timing}."
            f"{confirmation}"
        )

    return text


def _format_threshold(input_name: str, value: float) -> str:
    """Format a threshold value with appropriate units and precision."""
    if "hours" in input_name or input_name in ("sleep_h", "sleep_hours", "work_hours"):
        return f"{value:.1f} hours"
    if "1_5" in input_name:
        return f"{value:.0f}/5"
    if "1_10" in input_name:
        return f"{value:.0f}/10"
    if input_name in ("hrv_rmssd", "garmin_hrv_5min_high", "garmin_hrv_overnight_avg"):
        return f"{value:.0f}ms"
    if "hr" in input_name.lower() and "ratio" not in input_name:
        return f"{value:.0f} bpm"
    if "pct" in input_name or "ratio" in input_name:
        return f"{value:.0f}%"
    if "temperature" in input_name:
        return f"{value:.0f}°F"
    if value == int(value):
        return str(int(value))
    return f"{value:.1f}"


def _compute_confidence(r: float, p_adj: float, n: int) -> float:
    """Scale confidence with effect strength + data volume."""
    # Effect component: |r| scaled 0-1
    effect = min(abs(r), 1.0)
    # Volume component: logarithmic scaling, caps at ~100 samples
    import math
    volume = min(math.log(max(n, 1)) / math.log(100), 1.0)
    # Significance component: inverse p, capped
    sig = max(1.0 - p_adj, 0.0)
    # Weighted average
    return round(0.4 * effect + 0.3 * volume + 0.3 * sig, 3)


def _categorize(direction: str, output_metric: str = "efficiency") -> str:
    """Map correlation to insight category using polarity-aware logic.

    Returns "pattern" (neutral) when the output metric is ambiguous,
    preventing false "what works / what doesn't" claims.
    """
    beneficial = _is_beneficial(direction, output_metric)
    if beneficial is None:
        return "pattern"  # Ambiguous — no directional claim
    return "what_works" if beneficial else "what_doesnt"


def _insight_fingerprint(input_name: str, direction: str, output_metric: str) -> str:
    """Build a stable suppression fingerprint for an insight pattern.

    Keyed on input_name:direction:output_metric — stable across text changes.
    Used by the suppression system so a founder can suppress the pattern
    permanently regardless of how the insight text evolves.
    """
    import hashlib
    raw = f"{input_name}:{direction}:{output_metric}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_n1_insights(
    athlete_id: UUID,
    db: Session,
    days_window: Optional[int] = None,
    output_metric: str = "efficiency",
    max_insights: int = 10,
) -> List[N1Insight]:
    """Generate N=1 insights for an athlete from correlation engine output.

    Args:
        athlete_id: Athlete UUID.
        db: Database session.
        days_window: Analysis window (auto-selects up to 365 if None).
        output_metric: Target output metric for correlations.
        max_insights: Maximum insights to return.

    Returns:
        List of N1Insight objects, sorted by confidence descending.
        Only includes findings that survive Bonferroni correction and
        are not suppressed by a per-insight suppression record.
    """
    # Determine window from history if not specified
    if days_window is None:
        from services.phase3_eligibility import _history_stats
        stats = _history_stats(athlete_id, db)
        days_window = min(stats.get("history_span_days", 90), 365)
        days_window = max(days_window, 30)  # floor

    # Load active suppression fingerprints for this athlete
    suppressed_fingerprints: set = set()
    try:
        from models import N1InsightSuppression
        rows = db.query(N1InsightSuppression).filter(
            N1InsightSuppression.athlete_id == athlete_id
        ).all()
        suppressed_fingerprints = {r.insight_fingerprint for r in rows}
    except Exception:
        pass  # suppression table unavailable — fail open (show all insights)

    # Run correlation engine
    try:
        from services.correlation_engine import analyze_correlations
        result = analyze_correlations(
            athlete_id=str(athlete_id),
            days=days_window,
            db=db,
            output_metric=output_metric,
        )
    except Exception:
        return []

    raw = result.get("correlations", [])
    if not raw:
        return []

    # Bonferroni correction
    n_tests = max(len(raw), 1)
    insights: List[N1Insight] = []

    for c in raw:
        p_adj = min(c["p_value"] * n_tests, 1.0)
        r_val = c["correlation_coefficient"]
        n_val = c["sample_size"]

        # Gate: corrected significance + effect size + sample size
        if p_adj >= 0.05 or abs(r_val) < 0.3 or n_val < 10:
            continue

        input_name = c.get("input_name", "unknown")
        direction = c.get("direction", "positive")
        strength = c.get("strength", "moderate")
        lag = c.get("time_lag_days", 0)

        # Novelty gate: skip obvious findings (live path has no threshold data)
        if _is_obvious(input_name, output_metric, has_threshold=False):
            continue

        # Suppression check: skip if founder has suppressed this pattern
        fingerprint = _insight_fingerprint(input_name, direction, output_metric)
        if fingerprint in suppressed_fingerprints:
            continue

        text = _build_insight_text(
            input_name=input_name,
            direction=direction,
            strength=strength,
            r=r_val,
            lag_days=lag,
            output_metric=output_metric,
        )
        if text is None:
            continue

        # Safety: reject if banned acronyms leak through friendly-name mapping
        if BANNED_PATTERN.search(text):
            continue

        confidence = _compute_confidence(r_val, p_adj, n_val)
        evidence = {
            "r": round(r_val, 4),
            "p": round(c["p_value"], 6),
            "p_adjusted": round(p_adj, 6),
            "n": n_val,
            "lag_days": lag,
            "input_name": input_name,
        }

        insights.append(N1Insight(
            text=text,
            source="n1",
            confidence=confidence,
            evidence=evidence,
            category=_categorize(direction, output_metric),
            fingerprint=fingerprint,
        ))

    # Sort by confidence descending, cap at max_insights
    insights.sort(key=lambda i: i.confidence, reverse=True)
    return insights[:max_insights]
