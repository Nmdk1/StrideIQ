"""
Fingerprint → Plan Bridge

Translation layer between the fingerprint engine (correlation findings,
recovery half-life, athlete facts) and the plan engine's decision parameters.

The n1_engine reads FingerprintParams instead of hardcoded defaults.
The fingerprint engine populates them.  Nothing else in the engine
has to change in phase one.

Phase 1 bridges:
  recovery_half_life → cutback_frequency, quality_spacing_min_hours
  correlation findings → limiter, tss_sensitivity
  athlete facts → training_context (confounding variable awareness)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)

DEFAULTS = {
    "cutback_frequency": 3,
    "quality_spacing_min_hours": 48,
    "tss_sensitivity": "moderate",
    "consecutive_day_preference": "standard",
}

ACTIVE_STATES = {"active", "active_fixed", None}
STRUCTURAL_STATES = {"structural", "structural_monitored"}


@dataclass
class FingerprintParams:
    """Plan-engine-readable parameters derived from fingerprint data.

    Defaults match the pre-bridge hardcoded behavior (cutback every 3rd
    week, 48h quality spacing).  Only overridden when real fingerprint
    data is present with sufficient confidence.
    """

    recovery_half_life_hours: Optional[float] = None
    recovery_confidence: float = 0.0

    cutback_frequency: int = 3
    quality_spacing_min_hours: int = 48

    limiter: Optional[str] = None
    primary_quality_emphasis: Optional[str] = None

    tss_sensitivity: str = "moderate"
    consecutive_day_preference: str = "standard"

    training_context: Dict[str, str] = field(default_factory=dict)

    disclosures: List[str] = field(default_factory=list)
    source: str = "defaults"


def _classify_load_tier(
    current_weekly_miles: float,
    peak_weekly_miles: float,
    volume_trend: str,
) -> str:
    """Classify current load tier: high / moderate / low.

    High load = building AND within 10% of peak, or current > 90% of peak.
    Moderate = maintaining or within 70-90% of peak.
    Low = below 70% of peak or declining significantly.
    """
    if peak_weekly_miles <= 0:
        return "low"

    ratio = current_weekly_miles / peak_weekly_miles

    if ratio >= 0.90 or (volume_trend == "building" and ratio >= 0.80):
        return "high"
    elif ratio >= 0.60:
        return "moderate"
    else:
        return "low"


def _map_half_life_to_cutback(half_life: float, load_tier: str = "moderate") -> int:
    """Recovery half-life (hours) × load tier → cutback frequency (weeks).

    VR-11: high load = every 3rd week as safety valve regardless of
    recovery speed.  A fast recoverer at peak load still accumulates
    structural stress (tendon, bone, connective tissue) that doesn't
    follow the same half-life as metabolic recovery.

    Half-life alone:
      ≤ 30h  → every 5 weeks (fast recoverer)
      ≤ 48h  → every 4 weeks (normal)
      > 48h  → every 3 weeks (slow recoverer)

    Load tier override:
      high   → cap at every 3 weeks (safety valve)
      moderate → use half-life mapping
      low    → use half-life mapping
    """
    if half_life <= 30:
        base = 5
    elif half_life <= 48:
        base = 4
    else:
        base = 3

    if load_tier == "high":
        return min(base, 3)

    return base


def _map_half_life_to_spacing(half_life: float) -> int:
    """Recovery half-life (hours) → minimum hours between quality sessions.

    Fast recoverers can tolerate 48h spacing (e.g. Tue/Thu quality).
    Slow recoverers need 72h spacing (e.g. Tue/Fri quality).
    """
    if half_life <= 30:
        return 48
    elif half_life <= 48:
        return 48
    else:
        return 72


def _classify_tss_sensitivity(findings: list) -> str:
    """Derive TSS sensitivity from correlation findings.

    If ATL→efficiency or daily_session_stress→efficiency is strongly
    negative (r < -0.4), the athlete is load-sensitive → conservative.
    If TSB→efficiency is strongly positive, same signal.
    """
    for f in findings:
        inp = f.get("input_name", "")
        out = f.get("output_metric", "")
        r = f.get("correlation_coefficient", 0)
        direction = f.get("direction", "")

        if out != "efficiency":
            continue

        if inp == "daily_session_stress" and direction == "negative" and abs(r) >= 0.4:
            return "high"

        if inp == "tsb" and direction == "positive" and abs(r) >= 0.4:
            return "high"

    return "moderate"


def _detect_limiter(findings: list) -> Optional[str]:
    """Identify the dominant limiter from correlation findings.

    Phase 3: only findings with lifecycle_state in (active, active_fixed)
    drive limiter assignment. Closed findings are solved problems.
    Structural findings drive delivery modifications (handled separately
    in the bridge), not limiter assignment.

    Limiter taxonomy:
      "volume"     — L-VOL: long_run_ratio or weekly_volume → performance
      "recovery"   — L-REC: TSB or rest-day correlations dominate
      "speed"      — L-CEIL: ceiling/vo2 metrics are the bottleneck
      "threshold"  — L-THRESH: days_since_quality → pace_threshold
      "race_specific" — L-SPEC: active_fixed, pre-race integration
    """
    volume_signal = 0.0
    recovery_signal = 0.0
    threshold_signal = 0.0
    has_lspec = False

    for f in findings:
        lifecycle = f.get("lifecycle_state")
        if lifecycle not in ACTIVE_STATES:
            continue

        if lifecycle == "active_fixed":
            has_lspec = True
            continue

        inp = f.get("input_name", "")
        out = f.get("output_metric", "")
        r = abs(f.get("correlation_coefficient", 0))
        confirmed = f.get("times_confirmed", 1)

        weight = min(r * confirmed, 3.0)

        if inp in ("long_run_ratio", "weekly_volume_km", "ctl") and out in ("pace_threshold", "pace_easy", "efficiency"):
            volume_signal += weight

        if inp in ("tsb", "daily_session_stress", "atl", "days_since_rest", "consecutive_run_days") and out in ("pace_threshold", "pace_easy", "efficiency"):
            recovery_signal += weight

        if inp == "days_since_quality" and out == "pace_threshold":
            threshold_signal += weight

    if has_lspec:
        return "race_specific"

    signals = [
        ("volume", volume_signal),
        ("recovery", recovery_signal),
        ("threshold", threshold_signal),
    ]
    signals.sort(key=lambda s: s[1], reverse=True)

    if signals[0][1] > 0.5:
        return signals[0][0]

    return None


def _detect_consecutive_day_preference(findings: list) -> tuple:
    """Detect if the athlete performs better with more consecutive days.

    Returns (preference, confidence_note) where preference is one of:
      "standard" — no signal or insufficient evidence
      "suggested" — signal present but potential selection bias (n < 20)
      "confirmed" — strong signal with sufficient observations

    Larry's data: days_since_rest → PBs positive (r=0.77) at n=11.
    Selection bias risk: athlete may only string consecutive days when
    feeling good.  At n < 20 we flag as "suggested" (hypothesis) rather
    than "confirmed" (causal).  Plan uses it conservatively — won't add
    extra rest days, but won't remove athlete-requested ones either.
    """
    for f in findings:
        inp = f.get("input_name", "")
        direction = f.get("direction", "")
        r = abs(f.get("correlation_coefficient", 0))
        confirmed = f.get("times_confirmed", 1)
        sample_size = f.get("sample_size", confirmed)

        if (inp == "days_since_rest" and direction == "positive"
                and r >= 0.5 and confirmed >= 3):
            if sample_size >= 20 and confirmed >= 5:
                return "confirmed", None
            else:
                return "suggested", (
                    f"Consecutive-day signal detected (r={r:.2f}, n={sample_size}) "
                    f"but sample is small — possible selection bias. "
                    f"Using conservatively until more data confirms."
                )

    return "standard", None


def build_fingerprint_params(
    athlete_id: UUID,
    db,
) -> FingerprintParams:
    """Build FingerprintParams from the athlete's fingerprint data.

    Reads:
      - AthletePlanProfileService for recovery_half_life
      - CorrelationFinding for reproducible findings
      - AthleteFact for training context

    Returns FingerprintParams with confidence-gated overrides.
    Defaults are always safe — this never makes the plan worse.
    """
    params = FingerprintParams()

    try:
        from services.athlete_plan_profile import AthletePlanProfileService
        profile_svc = AthletePlanProfileService()
        profile = profile_svc.derive_profile(athlete_id, db, goal_distance="marathon")

        if profile.recovery_confidence >= 0.3:
            params.recovery_half_life_hours = profile.recovery_half_life_hours
            params.recovery_confidence = profile.recovery_confidence

            load_tier = _classify_load_tier(
                profile.current_weekly_miles,
                profile.peak_weekly_miles,
                profile.volume_trend,
            )
            params.cutback_frequency = _map_half_life_to_cutback(
                profile.recovery_half_life_hours, load_tier=load_tier,
            )
            params.quality_spacing_min_hours = _map_half_life_to_spacing(
                profile.recovery_half_life_hours
            )
            params.source = "fingerprint"

            load_note = ""
            if load_tier == "high" and params.cutback_frequency < profile.suggested_cutback_frequency:
                load_note = (
                    f" (capped from every {profile.suggested_cutback_frequency} weeks "
                    f"— high load safety valve)"
                )
            params.disclosures.append(
                f"Recovery profile: {profile.recovery_half_life_hours:.0f}h half-life, "
                f"{load_tier} load → cutback every {params.cutback_frequency} weeks{load_note}, "
                f"{params.quality_spacing_min_hours}h between quality sessions."
            )
        else:
            params.disclosures.append(
                "Recovery profile: insufficient data, using standard spacing."
            )
    except Exception as ex:
        logger.warning("fingerprint_bridge: profile derivation failed: %s", ex)

    try:
        from models import CorrelationFinding
        findings_q = (
            db.query(CorrelationFinding)
            .filter(
                CorrelationFinding.athlete_id == athlete_id,
                CorrelationFinding.is_active == True,  # noqa: E712
                CorrelationFinding.times_confirmed >= 3,
            )
            .all()
        )
        findings = [
            {
                "input_name": f.input_name,
                "output_metric": f.output_metric,
                "direction": f.direction,
                "correlation_coefficient": f.correlation_coefficient,
                "times_confirmed": f.times_confirmed,
                "sample_size": f.sample_size,
                "lifecycle_state": getattr(f, "lifecycle_state", None),
            }
            for f in findings_q
        ]

        if findings:
            params.tss_sensitivity = _classify_tss_sensitivity(findings)
            params.limiter = _detect_limiter(findings)

            consec_pref, consec_note = _detect_consecutive_day_preference(findings)
            params.consecutive_day_preference = consec_pref
            if consec_note:
                params.disclosures.append(consec_note)

            has_structural_lrec = any(
                f.get("lifecycle_state") in STRUCTURAL_STATES
                and f.get("input_name") in ("tsb", "daily_session_stress", "atl", "consecutive_run_days")
                for f in findings
            )
            if has_structural_lrec:
                monitored = any(
                    f.get("lifecycle_state") == "structural_monitored"
                    and f.get("input_name") in ("tsb", "daily_session_stress", "atl", "consecutive_run_days")
                    for f in findings
                )
                if monitored:
                    params.disclosures.append(
                        "Recovery trait detected (monitored) — this pattern is stable "
                        "but may shift. Delivery modifications applied conservatively."
                    )
                else:
                    params.disclosures.append(
                        "Structural recovery trait detected — delivery modifications "
                        "(spacing, cutback frequency) applied. Session types unchanged."
                    )

            if params.limiter == "volume":
                params.primary_quality_emphasis = "long_run_quality"
                params.disclosures.append(
                    "Limiter analysis: volume is your current lever — "
                    "plan emphasizes long run quality over additional midweek sessions."
                )
            elif params.limiter == "recovery":
                params.primary_quality_emphasis = "conservative_spacing"
                params.disclosures.append(
                    "Limiter analysis: recovery is your current lever — "
                    "plan uses wider spacing between quality sessions."
                )
            elif params.limiter == "threshold":
                params.primary_quality_emphasis = "threshold_emphasis"
                params.disclosures.append(
                    "Limiter analysis: threshold fitness is your current lever — "
                    "plan emphasizes threshold sessions."
                )
            elif params.limiter == "race_specific":
                params.primary_quality_emphasis = "support_crash_block"
                params.disclosures.append(
                    "Race-specific integration phase — plan supports your current "
                    "training block, protects the taper, does not add stimulus."
                )

            if params.tss_sensitivity == "high":
                params.disclosures.append(
                    "Load sensitivity detected: hard sessions have outsized "
                    "impact on your efficiency. Conservative dosing applied."
                )

            if params.consecutive_day_preference == "confirmed":
                params.disclosures.append(
                    "Your data consistently shows you perform better with consecutive "
                    "running days. Rest day scheduling adjusted accordingly."
                )

            params.source = "fingerprint"
    except Exception as ex:
        logger.warning("fingerprint_bridge: correlation query failed: %s", ex)

    try:
        from models import AthleteFact
        context_facts = (
            db.query(AthleteFact)
            .filter(
                AthleteFact.athlete_id == athlete_id,
                AthleteFact.is_active == True,  # noqa: E712
                AthleteFact.fact_type.in_(["training_context", "preference", "life_context"]),
            )
            .all()
        )
        for fact in context_facts:
            params.training_context[fact.fact_key] = fact.fact_value
    except Exception as ex:
        logger.warning("fingerprint_bridge: fact query failed: %s", ex)

    logger.info(
        "fingerprint_bridge: athlete=%s source=%s cutback=%d spacing=%dh "
        "limiter=%s tss=%s consecutive=%s",
        athlete_id, params.source, params.cutback_frequency,
        params.quality_spacing_min_hours, params.limiter,
        params.tss_sensitivity, params.consecutive_day_preference,
    )

    return params
