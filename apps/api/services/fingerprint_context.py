"""
Shared helper for formatting confirmed CorrelationFinding rows with
layer intelligence (thresholds, asymmetry, decay) for prompt injection.

Used by both the morning voice (_build_rich_intelligence_context) and
the coach brief (build_athlete_brief). Single source of truth for
formatting, limits, and ordering.

Phase 4 additions:
  - COACHING_LANGUAGE dictionary for DB field → coaching language translation
  - Lifecycle-state-aware labeling in format_finding_line
  - Closed findings grouped into a single summary line
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ── Athlete-facing suppression gates ──────────────────────────────────
# These signals produce statistically real correlations but are either
# unreliable (passive sensor noise) or universally true (every runner is
# slower in humidity). They stay in the correlation engine for internal
# use but NEVER reach the athlete through any surface.

_SUPPRESSED_SIGNALS: frozenset = frozenset({
    "garmin_steps",         # counts driving, stairs, fidgeting — not reliable
    "daily_step_count",     # alias
    "garmin_active_time_s", # passive accelerometer, same noise source
    "garmin_body_battery_end",   # proprietary model output (founder rule)
    "garmin_avg_stress",         # proprietary model output (founder rule)
    "garmin_max_stress",         # proprietary model output (founder rule)
    "garmin_aerobic_te",         # proprietary model output (founder rule)
    "garmin_anaerobic_te",       # proprietary model output (founder rule)
    "garmin_body_battery_impact",  # proprietary model output (founder rule)
})

_ENVIRONMENT_SIGNALS: frozenset = frozenset({
    "dew_point_f",
    "temperature_f",
    "humidity_pct",
    "heat_adjustment_pct",
})


def _is_suppressed_for_athlete(input_name: str) -> bool:
    """True if this signal should never appear in athlete-facing surfaces.

    Derived signals and interaction terms inherit suppression from their
    parent signals. The engine still tests them internally — suppression
    is a display-time decision, not a computation-time decision.
    """
    if input_name in _SUPPRESSED_SIGNALS or input_name in _ENVIRONMENT_SIGNALS:
        return True

    for parent in _SUPPRESSED_SIGNALS | _ENVIRONMENT_SIGNALS:
        if input_name.startswith(parent + "_"):
            return True

    _SUPPRESSED_INTERACTIONS = frozenset({
        "heat_stress_index",
    })
    return input_name in _SUPPRESSED_INTERACTIONS


SIGNAL_UNITS: Dict[str, str] = {
    "sleep_hours": "hours", "sleep_h": "hours",
    "pace_easy": "min/mi", "pace_threshold": "min/mi",
    "efficiency": "", "efficiency_threshold": "",
    "avg_hr": "bpm", "max_hr": "bpm", "resting_hr": "bpm",
    "heart_rate_avg": "bpm", "overnight_avg_hr": "bpm",
    "garmin_min_hr": "bpm",
    "hrv_rmssd": "ms", "hrv_sdnn": "ms", "garmin_hrv_5min_high": "ms",
    "garmin_sleep_score": "/100",
    # garmin_body_battery_end / garmin_avg_stress / garmin_max_stress are
    # Garmin proprietary model outputs and intentionally not registered.
    "garmin_vo2max": "",
    "soreness_1_5": "/5", "sleep_quality_1_5": "/5", "readiness_1_5": "/5",
    "stress_1_5": "/5", "confidence_1_5": "/5", "enjoyment_1_5": "/5",
    "motivation_1_5": "/5",
    "feedback_perceived_effort": "/10", "feedback_energy_pre": "/10",
    "feedback_energy_post": "/10", "feedback_leg_feel": "/5",
    "rpe_1_10": "/10",
    "run_start_hour": "hour",
    "temperature_f": "°F", "dew_point_f": "°F",
    "humidity_pct": "%", "heat_adjustment_pct": "%", "body_fat_pct": "%",
    "elevation_gain_m": "ft", "weekly_elevation_m": "ft",
    "weekly_volume_mi": "mi", "long_run_distance_mi": "mi",
    "weekly_volume_km": "km", "long_run_distance_km": "km",
    "distance_km": "km",
    "duration_s": "min",
    "days_since_quality": "days", "days_since_rest": "days",
    "consecutive_run_days": "days", "recovery_days": "days",
    "ct_hours_since_strength": "hours", "ct_hours_since_cross_training": "hours",
    "ct_strength_sessions_7d": "sessions", "ct_strength_sessions": "sessions",
    "ct_flexibility_sessions_7d": "sessions",
    "intensity_score": "", "activity_intensity_score": "",
    "daily_session_stress": "",
    "avg_cadence": "spm", "max_cadence": "spm",
    "avg_power_w": "W", "max_power_w": "W",
    "avg_stride_length_m": "m", "avg_ground_contact_ms": "ms",
    "avg_vertical_oscillation_cm": "cm", "avg_vertical_ratio_pct": "%",
    "total_descent_m": "ft", "moving_time_s": "min",
    "garmin_steps": "steps",
    "garmin_sleep_deep_s": "min", "garmin_sleep_rem_s": "min",
    "garmin_sleep_awake_s": "min",
    "garmin_active_time_s": "min",
    "garmin_moderate_intensity_s": "min", "garmin_vigorous_intensity_s": "min",
    "hrv_rhr_ratio": "",
    "garmin_resting_hr": "bpm",
    "garmin_hrv_overnight_avg": "ms",
    # NOTE: garmin_aerobic_te / garmin_anaerobic_te / garmin_body_battery_impact
    # intentionally NOT registered. They are Garmin proprietary model outputs,
    # not measurements, and we do not surface them in correlations or coach
    # context. The columns remain on Activity for backward compat but are no
    # longer populated. garmin_perceived_effort is also omitted here; it is
    # surfaced (with attribution) only via services/effort_resolver when the
    # athlete has not provided their own ActivityFeedback.perceived_effort.
    "active_kcal": "kcal",
    "weight_kg": "lbs", "muscle_mass_kg": "lbs",
    "daily_calories": "kcal", "daily_protein_g": "g", "daily_carbs_g": "g",
    "daily_fat_g": "g", "daily_fiber_g": "g",
    "long_run_ratio": "%",
    "completion_rate": "%", "completion": "%",
    "ct_strength_tss_7d": "TSS", "ct_cycling_tss_7d": "TSS",
    "ct_cross_training_tss_7d": "TSS", "ct_cycling_tss": "TSS",
    "ct_strength_duration_min": "min", "ct_cycling_duration_min": "min",
    "ct_total_volume_kg": "kg",
    "ct_lower_body_sets": "sets", "ct_upper_body_sets": "sets",
    "ct_core_sets": "sets", "ct_plyometric_sets": "sets",
    "ct_heavy_sets": "sets", "ct_unilateral_sets": "sets",
    "work_hours": "hours",
}


def _format_value_with_unit(value: float, signal_name: str) -> str:
    """Format a numeric value with the correct unit for athlete-facing display.

    Special cases: pace (M:SS/mi), time of day (7 AM), durations in seconds
    converted to minutes, elevation in meters converted to feet.
    """
    unit = SIGNAL_UNITS.get(signal_name, "")

    if unit == "min/mi":
        minutes = int(value)
        seconds = int((value - minutes) * 60)
        return f"{minutes}:{seconds:02d}/mi"

    if unit == "hour":
        hour = int(round(value))
        if hour == 0:
            return "midnight"
        if hour == 12:
            return "noon"
        suffix = "AM" if hour < 12 else "PM"
        display = hour if hour <= 12 else hour - 12
        return f"{display} {suffix}"

    if signal_name in ("elevation_gain_m", "weekly_elevation_m"):
        feet = value * 3.281
        return f"{feet:.0f} ft"

    if signal_name in ("weight_kg", "muscle_mass_kg"):
        lbs = value * 2.205
        return f"{lbs:.0f} lbs"

    if signal_name.endswith("_s") and unit == "min":
        minutes = value / 60
        return f"{minutes:.0f} min"

    if unit == "%":
        return f"{value:.0f}%"

    if unit in ("/5", "/10", "/100"):
        return f"{value:.1f}{unit}"

    if unit:
        return f"{value:.1f} {unit}"

    return f"{value:.1f}"


COACHING_LANGUAGE: Dict[str, str] = {
    "long_run_ratio": "long runs",
    "weekly_volume_km": "weekly mileage",
    "ctl": "chronic training load",
    "tsb": "freshness (training stress balance)",
    "daily_session_stress": "session intensity",
    "atl": "recent training load",
    "consecutive_run_days": "consecutive running days",
    # garmin_body_battery_end is proprietary — no coaching language registered.
    "sleep_hours": "sleep duration",
    "days_since_quality": "days since last quality session",
    "days_since_rest": "days since rest",
    "cadence": "running cadence",
    "elevation_gain": "elevation gain",
    "elevation_gain_m": "elevation gain",
    "heart_rate_avg": "average heart rate",
    "pace_threshold": "threshold pace",
    "pace_easy": "easy pace",
    "efficiency": "running efficiency",
    "efficiency_threshold": "threshold efficiency",
    "efficiency_trend": "efficiency trend",
    "vo2_estimate": "VO2 estimate",
    "distance_km": "run distance",
    "readiness_1_5": "readiness",
    "soreness_1_5": "soreness",
    "motivation_1_5": "motivation",
    "stress_1_5": "stress level",
    "confidence_1_5": "confidence",
    "sleep_quality_1_5": "sleep quality",
    "feedback_leg_feel": "leg freshness",
    "feedback_perceived_effort": "perceived effort",
    "run_start_hour": "time of day",
    "hrv_rhr_ratio": "recovery ratio",
    "garmin_resting_hr": "resting heart rate",
    "garmin_hrv_overnight_avg": "overnight HRV",
    "load_x_recovery": "training load × recovery",
    "sleep_quality_x_session_intensity": "sleep × session intensity",
    "hrv_rhr_convergence": "HRV-RHR convergence",
    "hrv_rhr_divergence_flag": "HRV-RHR divergence",
    # Strength v1 — descriptive labels only. The Manual surfaces these
    # in observation form ("your easy pace runs 6 sec/mi faster the day
    # after a heavy lower-body session"). The labels never imply a
    # prescription. See docs/specs/STRENGTH_V1_SCOPE.md §10 for the
    # narration purity contract.
    "ct_strength_sessions_7d": "strength sessions (last 7 days)",
    "ct_strength_sessions": "strength sessions",
    "ct_strength_duration_min": "strength session duration",
    "ct_strength_tss_7d": "strength load (last 7 days)",
    "ct_total_volume_kg": "total lifting volume",
    "ct_total_sets": "total sets",
    "ct_lower_body_sets": "lower-body sets",
    "ct_upper_body_sets": "upper-body sets",
    "ct_core_sets": "core sets",
    "ct_plyometric_sets": "plyometric sets",
    "ct_heavy_sets": "heavy sets",
    "ct_unilateral_sets": "unilateral sets",
    "ct_hours_since_strength": "hours since last strength session",
    "lifts_currently": "currently lifting",
    "lift_days_per_week": "lifting frequency",
    "lift_experience_bucket": "lifting experience",
    "estimated_1rm": "estimated 1RM",
}


def _translate(field_name: str) -> str:
    """Translate a DB field name to coaching language.

    Falls back to a cleaned version of the field name if not in the dictionary.
    """
    if field_name in COACHING_LANGUAGE:
        return COACHING_LANGUAGE[field_name]
    return field_name.replace("_", " ")


def get_confirmed_findings(
    athlete_id: UUID,
    db: Session,
    min_confirmed: int = 1,
    limit: int = 12,
):
    """Return active CorrelationFinding rows ordered by evidence weight.

    Routes through ``services.intelligence.finding_eligibility`` so that
    counterintuitive findings, confounded findings, sleep-derived
    findings during invalid-sleep windows, and contradictory pairs are
    suppressed. The ``min_confirmed`` floor is honored, but rows below
    the standard surfacing threshold are still returned when the caller
    asks for them (the LLM brief surfaces emerging patterns by design).
    """
    from services.intelligence.finding_eligibility import select_eligible_findings

    return select_eligible_findings(
        athlete_id,
        db,
        min_confirmations=min_confirmed,
        limit=limit,
    )


def format_finding_line(f, verbose: bool = False) -> str:
    """Format a single CorrelationFinding into a prompt-ready string.

    Lifecycle-aware: uses lifecycle_state when available for labeling.
    All field names go through the COACHING_LANGUAGE translator.
    """
    lifecycle = getattr(f, "lifecycle_state", None)

    if lifecycle == "emerging":
        tier = "EMERGING — ask athlete"
    elif lifecycle == "resolving":
        tier = "RESOLVING"
    elif lifecycle in ("structural", "structural_monitored"):
        tier = "STRUCTURAL"
    elif lifecycle == "active_fixed":
        tier = "ACTIVE (race-specific)"
    elif lifecycle == "active":
        tier = "ACTIVE"
    elif lifecycle == "closed":
        tier = "CLOSED"
    elif f.times_confirmed >= 10:
        tier = "CONFIRMED"
    elif f.times_confirmed >= 6:
        tier = "REPEATED"
    elif f.times_confirmed >= 3:
        tier = "EMERGING"
    else:
        tier = "EMERGING"

    inp = _translate(f.input_name)
    out = _translate(f.output_metric)

    entry = (
        f"[{tier} {f.times_confirmed}x] {inp} → {out}: "
        f"{f.insight_text or f.direction} "
        f"(strength: {f.strength}, n={f.sample_size})"
    )

    if lifecycle == "resolving" and getattr(f, "resolving_context", None):
        entry += f" — Attribution: {f.resolving_context}"

    details = []
    if f.threshold_value is not None:
        thresh_fmt = _format_value_with_unit(f.threshold_value, f.input_name)
        if verbose:
            n_below = f.n_below_threshold or 0
            n_above = f.n_above_threshold or 0
            details.append(
                f"Personal threshold: {inp} cliff at "
                f"{thresh_fmt} ({f.threshold_direction}). "
                f"Below: {n_below} observations, "
                f"Above: {n_above} observations"
            )
        else:
            details.append(f"Threshold: {inp} cliff at {thresh_fmt}")

    if f.asymmetry_ratio is not None:
        asym_dir = f.asymmetry_direction or ""
        if "negative" in asym_dir:
            asym_plain = "the downside hits harder than the upside helps"
        elif "positive" in asym_dir:
            asym_plain = "the upside helps more than the downside hurts"
        else:
            asym_plain = f"asymmetric ({asym_dir})"
        if verbose:
            details.append(
                f"Asymmetry: {f.asymmetry_ratio:.1f}x — {asym_plain}"
            )
        else:
            details.append(f"Asymmetry: {f.asymmetry_ratio:.1f}x — {asym_plain}")

    if f.decay_half_life_days is not None:
        details.append(
            f"Timing: half-life {f.decay_half_life_days:.1f} days ({f.decay_type})"
        )

    if f.time_lag_days and f.time_lag_days > 0:
        details.append(f"Lag: {f.time_lag_days} day(s)")

    if details:
        if verbose:
            return "- " + entry + "\n" + "\n".join(f"    {d}" for d in details)
        return "  " + entry + " — " + ", ".join(details)

    return ("- " if verbose else "  ") + entry


def _format_closed_summary(closed_findings: list) -> str:
    """Format closed findings as a single grouped summary line.

    Instead of listing each closed finding individually (wasting prompt space),
    produce: "Previously solved: long runs (closed 8mo ago), sleep duration (closed 3mo ago)"
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    parts = []
    for f in closed_findings:
        inp = _translate(f.input_name)
        updated = getattr(f, "lifecycle_state_updated_at", None)
        if updated:
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            months = max(1, (now - updated).days // 30)
            parts.append(f"{inp} (closed {months}mo ago)")
        else:
            parts.append(f"{inp} (closed)")
    return "  Previously solved: " + ", ".join(parts)


def build_fingerprint_prompt_section(
    athlete_id: UUID,
    db: Session,
    verbose: bool = False,
    max_findings: int = 8,
    include_emerging_question: bool = True,
) -> Optional[str]:
    """
    Build the full fingerprint prompt section for injection.

    verbose=True: used by morning voice (full layer detail with newlines).
    verbose=False: used by coach brief (compact single-line per finding).

    include_emerging_question: when False, the EMERGING PATTERN block is
    rewritten as an *observation* with no "ASK ABOUT THIS FIRST" framing
    and no "Suggested question" template. The morning_voice lane sets
    this False because the briefing is one-way; the conversational coach
    keeps it True because a follow-up question is appropriate there.
    Added 2026-04-18 after a production briefing surfaced a literal
    "What do you think is driving this?" to the athlete.

    Phase 4: findings are grouped by lifecycle state. Closed findings are
    compressed to a single summary line. Emerging findings get an explicit
    "ask athlete" label so the coach knows to probe.

    Returns None if no confirmed findings exist.
    """
    findings = get_confirmed_findings(athlete_id, db, limit=max_findings)
    if not findings:
        return None

    active: List = []
    emerging: List = []
    resolving: List = []
    structural: List = []
    closed: List = []

    finding_ids = {f.id for f in findings}

    for f in findings:
        ls = getattr(f, "lifecycle_state", None)
        if ls == "closed":
            closed.append(f)
        elif ls == "emerging":
            emerging.append(f)
        elif ls == "resolving":
            resolving.append(f)
        elif ls in ("structural", "structural_monitored"):
            structural.append(f)
        else:
            active.append(f)

    all_suppressed = _SUPPRESSED_SIGNALS | _ENVIRONMENT_SIGNALS

    if not emerging:
        from models import CorrelationFinding as CF

        extra_emerging = (
            db.query(CF)
            .filter(
                CF.athlete_id == athlete_id,
                CF.is_active == True,  # noqa: E712
                CF.lifecycle_state == "emerging",
                ~CF.input_name.in_(all_suppressed),
                ~CF.id.in_(finding_ids) if finding_ids else True,
            )
            .order_by(CF.lifecycle_state_updated_at.desc().nullslast())
            .limit(1)
            .all()
        )
        emerging.extend(extra_emerging)
    else:
        emerging = [e for e in emerging if e.input_name not in all_suppressed]

    if emerging:
        emerging.sort(
            key=lambda f: (
                getattr(f, "lifecycle_state_updated_at", None)
                or getattr(f, "first_detected_at", None)
                or datetime.min
            ),
            reverse=True,
        )
        emerging = emerging[:1]

    sections = []

    if emerging:
        ef = emerging[0]
        inp = _translate(ef.input_name)
        out = _translate(ef.output_metric)
        direction_word = "improves" if ef.direction == "positive" else "declines"
        first_det = getattr(ef, "first_detected_at", None)
        if first_det:
            from datetime import timezone as _tz

            if first_det.tzinfo is None:
                first_det = first_det.replace(tzinfo=_tz.utc)
            age_days = max(1, (datetime.now(_tz.utc) - first_det).days)
        else:
            age_days = None
        age_str = f"Forming over the last {age_days} days." if age_days else ""

        evidence_parts = []
        if ef.threshold_value is not None:
            thresh_fmt = _format_value_with_unit(ef.threshold_value, ef.input_name)
            above_below = ef.threshold_direction or "below"
            evidence_parts.append(
                f"There appears to be a threshold around {thresh_fmt} — "
                f"your {out} responds differently {above_below} that point"
            )
            if ef.n_below_threshold and ef.n_above_threshold:
                evidence_parts.append(
                    f"{ef.n_below_threshold} observations below, "
                    f"{ef.n_above_threshold} above"
                )
        if ef.time_lag_days and ef.time_lag_days > 0:
            evidence_parts.append(
                f"the effect appears {ef.time_lag_days} day(s) later"
            )

        evidence_block = ". ".join(evidence_parts) + "." if evidence_parts else ""

        if include_emerging_question:
            question = (
                f"Your data shows a pattern: your {out} {direction_word} "
                f"based on {inp}. {ef.times_confirmed}x observed. "
                f"{evidence_block} "
                f"What do you think is driving this?"
            )
            sections.append(
                f"=== EMERGING PATTERN — ASK ABOUT THIS FIRST ===\n"
                f"Before discussing other training data, ask the athlete "
                f"about this pattern. Be SPECIFIC — include the threshold, "
                f"observation count, and direction. Frame as curiosity, "
                f"not statistics.\n"
                f"\n"
                f"Your data suggests {inp} {direction_word} your {out}. "
                f"{age_str} Observed {ef.times_confirmed}x so far — not "
                f"yet confirmed as a durable pattern.\n"
            )
            if evidence_block:
                sections[-1] += f"Evidence detail: {evidence_block}\n"
            sections[-1] += (
                f"\n"
                f'Suggested question (rewrite in your coaching voice, '
                f'keeping the specifics): "{question}"\n'
                f"=== END EMERGING ==="
            )
        else:
            # Morning-voice lane: do NOT ask the athlete a question. The
            # briefing is one-way. State the emerging pattern as an
            # observation only, and keep it gated behind the "not yet
            # confirmed" qualifier so the LLM treats it as low-confidence
            # context, not a finding to lead with.
            sections.append(
                f"=== EMERGING PATTERN (low confidence — context only) ===\n"
                f"An emerging pattern is being tracked: {inp} appears to "
                f"{direction_word.replace('s', '')} {out}, observed "
                f"{ef.times_confirmed}x so far. Not yet confirmed as a "
                f"durable finding.\n"
                f"USAGE: Do NOT lead the briefing with this. Do NOT ask "
                f"the athlete a question about it. You may reference it "
                f"only if it is directly relevant to today's session, and "
                f"only as an observation, never as advice.\n"
                f"=== END EMERGING ==="
            )

    if verbose:
        header = (
            "--- Personal Fingerprint (data-proven patterns) ---\n"
            "ACTIVE = proven — state as fact in coaching language.\n"
            "RESOLVING = improving — attribute to the athlete's work.\n"
            "STRUCTURAL = physiological trait — adjust delivery, do not try to fix.\n"
            "Do not expose statistical internals to the athlete.\n"
            "Use threshold/decay data for specific advice.\n"
        )
    else:
        n_active = len(active)
        header = (
            f"({n_active} active, "
            f"{len(resolving)} resolving, {len(structural)} structural, "
            f"{len(closed)} closed patterns. "
            "Treat ACTIVE as fact. "
            "Attribute RESOLVING to the athlete's work.)"
        )
    sections.append(header)

    for group in (active, structural, resolving):
        for f in group:
            sections.append(format_finding_line(f, verbose=verbose))

    if closed:
        sections.append(_format_closed_summary(closed))

    return "\n".join(sections)
