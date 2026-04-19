"""
Personal Operating Manual V2 — structured understanding of the athlete.

V1 was a database dump organized by domain.
V2 leads with insight: cascade stories, race character, personal thresholds.
The full domain record remains as a reference layer.

Sources:
  - CorrelationFinding (statistical relationships + L1-L4 enrichment)
  - CorrelationMediator (L3 cascade chains)
  - AthleteFinding (investigation-based findings from race_input_analysis)
  - Activity (race vs training pace comparison)

The manual is deterministic. No LLM calls. The data speaks for itself.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from services.fingerprint_context import COACHING_LANGUAGE

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Domain taxonomy (unchanged from V1)
# ---------------------------------------------------------------------------

DOMAIN_ORDER = [
    "recovery", "sleep", "cardiac", "training_load", "environmental",
    "pace", "race", "subjective", "strength", "training_pattern",
]

DOMAIN_LABELS = {
    "recovery": "Recovery",
    "sleep": "Sleep",
    "cardiac": "Cardiac",
    "training_load": "Training Load",
    "environmental": "Environmental",
    "pace": "Pace & Efficiency",
    "race": "Racing",
    "subjective": "Subjective Feedback",
    "strength": "Strength",
    "training_pattern": "Training Patterns",
}

DOMAIN_DESCRIPTIONS = {
    "recovery": "How your body absorbs and responds to training stress.",
    "sleep": "How sleep duration and quality affect your running.",
    "cardiac": "Heart rate patterns, HRV, and cardiac efficiency.",
    "training_load": "How volume, intensity, and training load affect your performance.",
    "environmental": "How heat, weather, and conditions change your output.",
    "pace": "Your pace efficiency, thresholds, and progression.",
    "race": "Race execution patterns and pre-race signatures.",
    "subjective": "How your subjective feel predicts performance.",
    # Strength v1: an *observation* domain. The Manual reports what
    # the data shows about how strength work tracks with running
    # outputs for THIS athlete. It never prescribes a routine, never
    # recommends a load, never tells the athlete what they should  # noqa: narration-purity
    # do at the gym. See docs/specs/STRENGTH_V1_SCOPE.md §10.
    "strength": "How your strength work tracks with running outputs.",
    "training_pattern": "Weekly structure, session sequencing, and workout variety.",
}

_DOMAIN_RULES: List[Tuple[str, List[str]]] = [
    ("sleep", ["sleep", "hrv", "rmssd"]),
    ("cardiac", ["heart_rate", "hr_", "resting_hr", "cardiac", "vo2"]),
    ("recovery", ["recovery", "days_since", "body_battery", "tsb", "freshness", "rest"]),
    ("environmental", ["heat", "dew_point", "temperature", "weather", "humidity"]),
    ("training_load", ["ctl", "atl", "volume", "weekly_volume", "distance", "load", "session_stress"]),
    ("subjective", ["readiness", "soreness", "motivation", "stress_1_5", "confidence_1_5",
                     "sleep_quality_1_5", "feedback_", "perceived_effort", "leg_feel",
                     "enjoyment", "rpe"]),
    # Strength domain — match canonical engine input names from
    # services/intelligence/correlation_engine.py (ct_strength_*,
    # ct_lower_body_*, ct_heavy_sets, ct_hours_since_strength,
    # ct_strength_frequency_*) and per-set RPE / e1RM signals from
    # phase I. Listed before training_pattern so strength findings
    # don't get bucketed into the catch-all.
    ("strength", ["ct_strength", "ct_lower_body", "ct_upper_body", "ct_heavy_sets",
                   "ct_total_sets", "ct_hours_since_strength",
                   "estimated_1rm", "lift_days_per_week", "lifts_currently",
                   "lift_experience_bucket", "movement_pattern", "muscle_group",
                   "is_unilateral"]),
    ("race", ["race", "pb_events"]),
    ("pace", ["pace", "efficiency", "speed", "cadence", "stride"]),
    ("training_pattern", ["long_run", "consecutive", "run_start_hour", "elevation",
                          "workout_variety"]),
]

_INVESTIGATION_DOMAIN_MAP: Dict[str, str] = {
    "investigate_heat_tax": "environmental",
    "investigate_recovery_cost": "recovery",
    "investigate_post_injury_resilience": "recovery",
    "investigate_pace_at_hr_adaptation": "cardiac",
    "investigate_stride_economy": "pace",
    "investigate_stride_progression": "pace",
    "investigate_long_run_durability": "training_pattern",
    "investigate_back_to_back_durability": "training_pattern",
    "investigate_workout_progression": "pace",
    "investigate_race_execution": "race",
    "investigate_training_recipe": "race",
    "investigate_cruise_interval_quality": "pace",
    "investigate_interval_recovery_trend": "recovery",
    "investigate_workout_variety_effect": "training_pattern",
    "investigate_progressive_run_execution": "pace",
    "detect_adaptation_curves": "training_load",
    "detect_weekly_patterns": "training_pattern",
}

# Garmin passive/behavioral metrics — noise, not physiology.
# Steps inflate from driving, body battery is unreliable, active time
# is passive accelerometer. These should not lead the manual.
_GARMIN_NOISE_INPUTS = frozenset({
    "garmin_steps",
    "garmin_active_time_s",
    "garmin_body_battery_end",
})

# Garmin physiological metrics — real signals, fine to use.
# HRV, sleep architecture, resting HR, stress (HRV-derived),
# intensity minutes (activity-based, requires elevated HR).
_GARMIN_PHYSIO_INPUTS = frozenset({
    "garmin_hrv_5min_high",
    "garmin_sleep_score", "garmin_sleep_deep_s", "garmin_sleep_light_s",
    "garmin_sleep_rem_s", "garmin_sleep_awake_s",
    "garmin_min_hr", "garmin_max_hr",
    "garmin_avg_stress", "garmin_max_stress",
    "garmin_vigorous_intensity_s", "garmin_moderate_intensity_s",
})

# More human-friendly translations for the manual page (overrides COACHING_LANGUAGE
# where the coaching version includes unnecessary parenthetical jargon).
_MANUAL_LANGUAGE: Dict[str, str] = {
    "tsb": "freshness",
    "ctl": "fitness level",
    "atl": "recent training load",
    "daily_session_stress": "session stress",
    "garmin_body_battery_end": "body battery",
    "garmin_sleep_score": "sleep score",
    "garmin_hrv_5min_high": "Recovery HRV",
    "garmin_avg_stress": "stress level",
    "garmin_max_stress": "peak stress",
    "garmin_min_hr": "resting heart rate",
    "garmin_steps": "daily steps",
    "garmin_active_time_s": "active time",
    "garmin_sleep_deep_s": "deep sleep",
    "garmin_sleep_light_s": "light sleep",
    "garmin_sleep_rem_s": "REM sleep",
    "garmin_sleep_awake_s": "time awake",
    "garmin_vigorous_intensity_s": "vigorous activity time",
    "garmin_moderate_intensity_s": "moderate activity time",
    "garmin_max_hr": "max heart rate",
}

_M_PER_MI = 1609.344

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _classify_domain(input_name: str, output_metric: str) -> str:
    combined = f"{input_name} {output_metric}".lower()
    for domain, keywords in _DOMAIN_RULES:
        for kw in keywords:
            if kw in combined:
                return domain
    return "training_pattern"


# Phase I — strength domain finding gate.
#
# Strength v1 is new and observation-driven: we suppress over
# hallucinate. Until a strength finding has at least 4 sample
# observations AND p < 0.05 it stays in the database (visible to
# tuning analysis) but never renders in the Personal Operating
# Manual or any athlete-facing surface. This is *stricter* than
# the engine's general bar.
# See docs/specs/STRENGTH_V1_SCOPE.md §8.2.
_STRENGTH_MIN_SAMPLE_SIZE = 4
_STRENGTH_MAX_P_VALUE = 0.05


def _passes_strength_surface_gate(finding) -> bool:
    """Return True if a strength-domain finding may render to the athlete.

    Non-strength findings always pass (gate is domain-scoped).
    Missing sample_size / p_value attributes also pass (older
    engine snapshots predate the columns; we don't retroactively
    suppress them).
    """
    domain = _classify_domain(finding.input_name, finding.output_metric)
    if domain != "strength":
        return True
    sample_size = getattr(finding, "sample_size", None)
    p_value = getattr(finding, "p_value", None)
    if sample_size is None or p_value is None:
        return True
    return sample_size >= _STRENGTH_MIN_SAMPLE_SIZE and p_value < _STRENGTH_MAX_P_VALUE


def _classify_investigation_domain(investigation_name: str, finding_type: str) -> str:
    if investigation_name in _INVESTIGATION_DOMAIN_MAP:
        return _INVESTIGATION_DOMAIN_MAP[investigation_name]
    ft = finding_type.lower()
    if "heat" in ft or "weather" in ft:
        return "environmental"
    if "recovery" in ft or "durability" in ft:
        return "recovery"
    if "race" in ft:
        return "race"
    if "pace" in ft or "stride" in ft or "efficiency" in ft:
        return "pace"
    if "sleep" in ft:
        return "sleep"
    return "training_pattern"


def _translate(field_name: str) -> str:
    if field_name in _MANUAL_LANGUAGE:
        return _MANUAL_LANGUAGE[field_name]
    if field_name in COACHING_LANGUAGE:
        return COACHING_LANGUAGE[field_name]
    return field_name.replace("_", " ")


def _confidence_tier(times_confirmed: int) -> str:
    if times_confirmed >= 6:
        return "strong"
    if times_confirmed >= 3:
        return "confirmed"
    return "emerging"


def _is_athlete_understandable(input_name: str) -> bool:
    from services.fingerprint_context import _is_suppressed_for_athlete
    return not _is_suppressed_for_athlete(input_name)


_JARGON_REPLACEMENTS = [
    ("freshness (training stress balance)", "freshness"),
    ("freshness (training readiness)", "freshness"),
    ("form (training readiness)", "freshness"),
    ("form (training stress balance)", "freshness"),
    ("fatigue (recent load)", "recent training load"),
    ("chronic training load", "fitness level"),
    ("training session stress", "session stress"),
    ("session intensity", "session stress"),
    ("your tsb ", "your freshness "),
    ("your atl ", "your recent training load "),
    ("your ctl ", "your fitness level "),
    (" tsb is ", " freshness is "),
    (" atl is ", " recent training load is "),
    (" ctl is ", " fitness level is "),
]


def _clean_headline(headline: str) -> str:
    """Strip the template prefix and jargon from stored insight text."""
    prefixes = [
        "Based on your data: YOUR ",
        "Based on your data: your ",
        "Based on your data: ",
    ]
    text = headline
    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break

    for jargon, replacement in _JARGON_REPLACEMENTS:
        text = text.replace(jargon, replacement)

    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    return text


_THRESHOLD_UNITS: Dict[str, str] = {
    "sleep_hours": "hours",
    "sleep_quality_1_5": "",
    "readiness_1_5": "",
    "soreness_1_5": "",
    "motivation_1_5": "",
    "stress_1_5": "",
    "confidence_1_5": "",
    "consecutive_run_days": "days",
    "days_since_rest": "days",
    "days_since_quality": "days",
    "elevation_gain": "m",
    "elevation_gain_m": "m",
    "weekly_volume_km": "km",
    "run_start_hour": "",
    "long_run_ratio": "%",
    "garmin_hrv_5min_high": "ms",
    "garmin_min_hr": "bpm",
    "garmin_max_hr": "bpm",
    "garmin_avg_stress": "",
    "garmin_max_stress": "",
    "garmin_sleep_score": "",
}

# Garmin fields stored in seconds that should display as hours+minutes.
_SECONDS_FIELDS = frozenset({
    "garmin_sleep_deep_s", "garmin_sleep_light_s",
    "garmin_sleep_rem_s", "garmin_sleep_awake_s",
})


def _format_seconds_human(seconds: float) -> str:
    """Format a duration in seconds to a human-readable string."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"

_THRESHOLD_SUPPRESS = frozenset({
    "daily_session_stress", "ctl", "atl", "tsb",
})


def _is_baseline_threshold(finding) -> bool:
    """True when the athlete is on one side of the threshold 85%+ of the time.

    A threshold like "sleep > 7h → better efficiency" is useless to someone
    who sleeps under 7h on 95% of nights — it describes their baseline, not
    a lever they can pull.
    """
    n_below = getattr(finding, "n_below_threshold", None)
    n_above = getattr(finding, "n_above_threshold", None)
    if n_below is None or n_above is None:
        return False
    total = n_below + n_above
    if total < 10:
        return False
    dominant_pct = max(n_below, n_above) / total
    return dominant_pct >= 0.85


def _format_threshold(finding) -> Optional[Dict[str, Any]]:
    if finding.threshold_value is None:
        return None

    input_name = finding.input_name
    if input_name in _THRESHOLD_SUPPRESS:
        return None
    if _is_garmin_noise(input_name):
        return None
    if _is_baseline_threshold(finding):
        return None

    human_input = _translate(input_name)
    value = finding.threshold_value
    direction = finding.threshold_direction

    if input_name in _SECONDS_FIELDS:
        value_str = _format_seconds_human(value)
    else:
        if abs(value) >= 100:
            formatted = f"{value:.0f}"
        elif abs(value) >= 10:
            formatted = f"{value:.1f}"
        else:
            formatted = f"{value:.1f}"

        unit = _THRESHOLD_UNITS.get(input_name, "")
        value_str = f"{formatted} {unit}".strip() if unit else formatted

    if direction == "below":
        label = f"Below {value_str} {human_input}, performance drops"
    elif direction == "above":
        label = f"Above {value_str} {human_input}, performance drops"
    else:
        label = f"{human_input} threshold at {value_str}"

    return {
        "value": round(value, 1),
        "direction": direction,
        "label": label,
        "input_name": input_name,
        "human_input": human_input,
    }


def _format_asymmetry(finding) -> Optional[Dict[str, Any]]:
    if finding.asymmetry_ratio is None:
        return None
    ratio = finding.asymmetry_ratio
    direction = finding.asymmetry_direction
    if ratio < 0.3 and direction == "positive_dominant":
        label = f"Increases in {_translate(finding.input_name)} help more than decreases hurt"
    elif ratio < 0.3 and direction == "negative_dominant":
        label = f"Decreases in {_translate(finding.input_name)} hurt more than increases help"
    elif 0.8 <= ratio <= 1.2:
        label = "Effect is roughly symmetric in both directions"
    else:
        label = f"{ratio:.1f}x asymmetry ({direction})"
    return {
        "ratio": round(ratio, 1),
        "direction": direction,
        "label": label,
    }


def _format_timing(finding) -> Optional[Dict[str, Any]]:
    parts: Dict[str, Any] = {}
    if finding.decay_half_life_days is not None:
        parts["half_life_days"] = round(finding.decay_half_life_days, 1)
        parts["decay_type"] = finding.decay_type
    if finding.time_lag_days and finding.time_lag_days > 0:
        parts["lag_days"] = finding.time_lag_days
    if not parts:
        return None
    return parts


def _format_pace(seconds_per_mile: float) -> str:
    m = int(seconds_per_mile // 60)
    s = int(round(seconds_per_mile % 60))
    return f"{m}:{s:02d}/mi"


# ---------------------------------------------------------------------------
# Headline rewriter — human language from structured fields
# ---------------------------------------------------------------------------

# Output-specific verbs in infinitive: (positive_verb, negative_verb)
_OUTPUT_VERBS: Dict[str, Tuple[str, str]] = {
    "pace_easy": ("quicken", "slow down"),
    "pace_threshold": ("get faster", "slow down"),
    "race_pace": ("get faster", "slow down"),
    "completion_rate": ("improve", "drop"),
    "completion": ("improve", "drop"),
    "pb_events": ("increase", "decrease"),
}


def _conjugate_3p(verb: str) -> str:
    """Conjugate an infinitive verb to third-person singular present."""
    parts = verb.split(" ", 1)
    base = parts[0]
    rest = " " + parts[1] if len(parts) > 1 else ""
    if base.endswith(("s", "sh", "ch", "x", "z")):
        return base + "es" + rest
    if base.endswith("y") and not base.endswith(("ay", "ey", "oy", "uy")):
        return base[:-1] + "ies" + rest
    return base + "s" + rest

# Higher-input phrasing per input — what "higher" means in plain English.
# Falls back to "is higher" / "is lower" for unlisted inputs.
_INPUT_CONDITIONS: Dict[str, Tuple[str, str]] = {
    "sleep_hours": ("you sleep more", "you sleep less"),
    "sleep_quality_1_5": ("you sleep well", "your sleep is poor"),
    "soreness_1_5": ("you're sore", "soreness is low"),
    "readiness_1_5": ("you feel ready", "your readiness is low"),
    "motivation_1_5": ("your motivation is high", "motivation drops"),
    "stress_1_5": ("your stress is high", "your stress is low"),
    "confidence_1_5": ("you're feeling confident", "confidence is low"),
    "consecutive_run_days": ("you run consecutive days", "you take days off"),
    "days_since_rest": ("it's been a while since rest", "you've rested recently"),
    "days_since_quality": ("it's been a while since a quality session",
                           "you've done quality work recently"),
    "tsb": ("you're fresh", "you're fatigued"),
    "atl": ("your recent training load is high", "your recent load is low"),
    "ctl": ("your fitness level is high", "your fitness level is low"),
    "daily_session_stress": ("the session is hard", "the session is easy"),
    "elevation_gain": ("there's more climbing", "the route is flat"),
    "elevation_gain_m": ("there's more climbing", "the route is flat"),
    "weekly_volume_km": ("your weekly mileage is high", "your mileage is low"),
    "long_run_ratio": ("your long run is a big chunk of weekly volume",
                       "your long run ratio is small"),
    "run_start_hour": ("you run later in the day", "you run early"),
    "garmin_hrv_5min_high": ("your Recovery HRV is higher", "your Recovery HRV drops"),
    "garmin_sleep_score": ("your sleep score is high", "your sleep score is low"),
    "garmin_sleep_deep_s": ("you get more deep sleep", "deep sleep is short"),
    "garmin_min_hr": ("your resting HR is higher", "your resting HR is lower"),
    "garmin_avg_stress": ("your stress level is high", "your stress is low"),
    "garmin_vigorous_intensity_s": ("you log more vigorous activity",
                                    "vigorous activity is low"),
    "garmin_moderate_intensity_s": ("you log more moderate activity",
                                    "moderate activity is low"),
}

_LAG_PHRASES = {
    0: "",
    1: " for about a day",
    2: " over the next couple of days",
    3: " for about 3 days",
    4: " for about 4 days",
    5: " for about 5 days",
    7: " for about a week",
}


def _rewrite_headline(finding) -> str:
    """Build a human-readable headline from structured correlation fields.

    Ignores the stored insight_text template. Reads the structured data
    (input_name, output_metric, direction, r, time_lag_days) and writes
    a sentence that sounds like a person, not a database.
    """
    from services.n1_insight_generator import get_metric_meta

    input_name = finding.input_name
    output_metric = finding.output_metric
    direction = finding.direction
    r = abs(finding.correlation_coefficient)
    lag = finding.time_lag_days or 0

    human_output = _translate(output_metric)
    meta = get_metric_meta(output_metric)

    # Determine if this direction is good or bad for the athlete
    is_unambiguous = not meta.polarity_ambiguous and meta.higher_is_better is not None
    raw_positive = direction == "positive"

    if is_unambiguous:
        beneficial = raw_positive == meta.higher_is_better
    else:
        beneficial = None

    # Lag phrase
    lag_phrase = _LAG_PHRASES.get(lag, f" for about {lag} days")

    # Strength-based confidence: no hedge (strong), "tends to" (moderate), "may" (weak)
    if r >= 0.55:
        hedge = ""
        conjugate = True
    elif r >= 0.35:
        hedge = "tends to "
        conjugate = False
    else:
        hedge = "may "
        conjugate = False

    def _verb(infinitive: str) -> str:
        return _conjugate_3p(infinitive) if conjugate else infinitive

    # Build the "when" clause — start with the athlete's controllable input
    conditions = _INPUT_CONDITIONS.get(input_name)
    if conditions:
        when_high, when_low = conditions
    else:
        human_input = _translate(input_name)
        when_high = f"your {human_input} is higher"
        when_low = f"your {human_input} is lower"

    if beneficial is not None:
        verbs = _OUTPUT_VERBS.get(output_metric)
        if verbs:
            good_inf, bad_inf = verbs
            verb = _verb(good_inf) if beneficial else _verb(bad_inf)
            return f"When {when_high}, your {human_output} {hedge}{verb}{lag_phrase}."
        else:
            verb = _verb("improve") if beneficial else _verb("drop")
            return f"When {when_high}, your {human_output} {hedge}{verb}{lag_phrase}."

    # Ambiguous output — neutral language, no directional claim
    return f"When {when_high}, your {human_output} {hedge}{_verb('shift')}{lag_phrase}."


# ---------------------------------------------------------------------------
# Interestingness scoring
# ---------------------------------------------------------------------------

def _score_interestingness(entry: Dict[str, Any]) -> float:
    """Score a finding by how interesting it is to a human, not how frequent.

    Higher = more interesting = should appear earlier in the manual.
    Cascade chains and non-obvious findings score highest.
    Simple high-frequency correlations score lowest.
    """
    score = 0.0

    has_cascade = bool(entry.get("cascade"))
    has_threshold = bool(entry.get("threshold"))
    has_asymmetry = bool(entry.get("asymmetry"))
    has_timing = bool(entry.get("timing"))
    is_counterintuitive = entry.get("direction_counterintuitive", False)
    input_name = entry.get("_input_name", "")

    is_baseline = entry.get("_is_baseline", False)

    if has_cascade:
        score += 30
    if is_counterintuitive:
        score += 25
    if has_threshold and _is_athlete_understandable(input_name):
        if is_baseline:
            score -= 10
        else:
            score += 20
    if has_asymmetry:
        asym = entry.get("asymmetry", {})
        ratio = asym.get("ratio", 1.0)
        if ratio < 0.5 or ratio > 2.0:
            score += 15
    if has_timing:
        score += 10
    if _is_athlete_understandable(input_name):
        score += 5
    else:
        score -= 20

    return score


# ---------------------------------------------------------------------------
# Race Character
# ---------------------------------------------------------------------------

def _build_race_character(athlete_id: UUID, db: Session) -> Optional[Dict[str, Any]]:
    """Compute the racer-vs-trainer gap.

    For each race, compare race pace against training paces at similar
    distances in the prior 14 days. The gap reveals whether the athlete
    overrides their training-day patterns on race day.
    """
    from models import Activity

    races = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.sport == "run",
            Activity.is_race_candidate.is_(True),
            Activity.distance_m.isnot(None),
            Activity.duration_s.isnot(None),
            Activity.distance_m > 0,
            Activity.duration_s > 0,
        )
        .order_by(Activity.start_time.desc())
        .limit(20)
        .all()
    )

    if not races:
        return None

    race_entries = []
    gap_percentages = []
    pb_count = 0

    for race in races:
        dist_m = race.distance_m
        race_pace = race.duration_s / (dist_m / _M_PER_MI)
        race_date = race.start_time
        window_start = race_date - timedelta(days=14)

        dist_low = dist_m * 0.6
        dist_high = dist_m * 1.4

        training_runs = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete_id,
                Activity.sport == "run",
                Activity.start_time >= window_start,
                Activity.start_time < race_date - timedelta(hours=12),
                Activity.is_race_candidate.is_(False),
                Activity.distance_m >= dist_low,
                Activity.distance_m <= dist_high,
                Activity.distance_m.isnot(None),
                Activity.duration_s.isnot(None),
                Activity.duration_s > 0,
            )
            .all()
        )

        training_paces = []
        for t in training_runs:
            if t.distance_m and t.duration_s and t.distance_m > 0:
                training_paces.append(t.duration_s / (t.distance_m / _M_PER_MI))

        is_pb = getattr(race, "user_verified_race", False)
        if not is_pb:
            is_pb = (race.race_confidence or 0) >= 0.8

        gap_pct = None
        avg_training_pace = None
        if training_paces:
            avg_training_pace = sum(training_paces) / len(training_paces)
            if avg_training_pace > 0:
                gap_pct = (avg_training_pace - race_pace) / avg_training_pace * 100
                gap_percentages.append(gap_pct)

        race_entry = {
            "date": race.start_time.strftime("%Y-%m-%d"),
            "name": race.name or "",
            "distance_mi": round(dist_m / _M_PER_MI, 1),
            "race_pace": _format_pace(race_pace),
            "race_pace_s": round(race_pace, 1),
            "avg_hr": race.avg_hr,
            "is_pb": is_pb,
        }
        if gap_pct is not None:
            race_entry["training_pace"] = _format_pace(avg_training_pace)
            race_entry["gap_pct"] = round(gap_pct, 1)
            race_entry["training_runs_compared"] = len(training_paces)

        if is_pb:
            pb_count += 1

        race_entries.append(race_entry)

    if not gap_percentages:
        if not race_entries:
            return None
        return {
            "races": race_entries,
            "race_count": len(race_entries),
            "has_gap_data": False,
        }

    avg_gap = sum(gap_percentages) / len(gap_percentages)
    all_pbs = pb_count == len(races) and len(races) >= 2

    narrative_parts = []
    if avg_gap > 10:
        narrative_parts.append(
            f"On race day, you run on average {avg_gap:.0f}% faster than "
            f"your training at similar distances."
        )
    elif avg_gap > 0:
        narrative_parts.append(
            f"On race day, you tend to run about {avg_gap:.0f}% faster "
            f"than your training pace at similar distances."
        )

    if all_pbs:
        narrative_parts.append(
            f"Every one of your {len(races)} races was a personal best."
        )
    elif pb_count > 0:
        narrative_parts.append(
            f"{pb_count} of your {len(races)} races were personal bests."
        )

    if avg_gap > 15:
        narrative_parts.append(
            "Training-day patterns about readiness and sleep may not predict "
            "your race-day performance. Your body overrides those signals when it counts."
        )

    counterevidence = _build_race_counterevidence(athlete_id, race_entries, db)

    result = {
        "races": race_entries,
        "race_count": len(race_entries),
        "has_gap_data": True,
        "avg_gap_pct": round(avg_gap, 1),
        "pb_count": pb_count,
        "all_pbs": all_pbs,
        "narrative": " ".join(narrative_parts),
    }
    if counterevidence:
        result["counterevidence"] = counterevidence
    return result


# ---------------------------------------------------------------------------
# Race-Day Counterevidence
# ---------------------------------------------------------------------------

# Maps CorrelationFinding.input_name to (model, field) for race-day lookup.
# DailyCheckin fields:
_CHECKIN_FIELD_MAP: Dict[str, str] = {
    "sleep_hours": "sleep_h",
    "sleep_quality_1_5": "sleep_quality_1_5",
    "readiness_1_5": "readiness_1_5",
    "soreness_1_5": "soreness_1_5",
    "motivation_1_5": "motivation_1_5",
    "stress_1_5": "stress_1_5",
    "confidence_1_5": "confidence_1_5",
}

# GarminDay fields used for counterevidence (pre-race wellness state).
# Intensity metrics are excluded — they measure activity output, not readiness.
_GARMIN_FIELD_MAP: Dict[str, str] = {
    "garmin_hrv_5min_high": "hrv_5min_high",
    "garmin_sleep_score": "sleep_score",
    "garmin_sleep_deep_s": "sleep_deep_s",
    "garmin_sleep_light_s": "sleep_light_s",
    "garmin_sleep_rem_s": "sleep_rem_s",
    "garmin_sleep_awake_s": "sleep_awake_s",
    "garmin_min_hr": "min_hr",
    "garmin_max_hr": "max_hr",
    "garmin_avg_stress": "avg_stress",
    "garmin_max_stress": "max_stress",
}

# Garmin metrics that measure what the athlete DID, not how they felt.
# These should never appear in counterevidence (pre-race state comparison).
_GARMIN_ACTIVITY_METRICS = frozenset({
    "garmin_vigorous_intensity_s",
    "garmin_moderate_intensity_s",
})


def _build_race_counterevidence(
    athlete_id: UUID,
    race_entries: List[Dict[str, Any]],
    db: Session,
) -> List[Dict[str, Any]]:
    """Find training-day findings that race-day performance contradicts.

    For each race where the athlete performed well (positive gap vs training,
    or a PB), pull their wellness data on race day and compare against
    threshold findings. If the athlete was on the "bad" side of a threshold
    yet still raced well, that's character — not luck.
    """
    from models import CorrelationFinding, DailyCheckin

    good_races = [
        r for r in race_entries
        if (r.get("gap_pct") or 0) > 0 or r.get("is_pb")
    ]
    if not good_races:
        return []

    threshold_findings = (
        db.query(CorrelationFinding)
        .filter(
            CorrelationFinding.athlete_id == athlete_id,
            CorrelationFinding.is_active.is_(True),
            CorrelationFinding.threshold_value.isnot(None),
            CorrelationFinding.threshold_direction.isnot(None),
            CorrelationFinding.times_confirmed >= 3,
        )
        .all()
    )
    if not threshold_findings:
        return []

    try:
        from models import GarminDay
        has_garmin = True
    except ImportError:
        has_garmin = False

    contradictions: List[Dict[str, Any]] = []

    for race in good_races:
        race_date_str = race.get("date")
        if not race_date_str:
            continue
        race_date = datetime.strptime(race_date_str, "%Y-%m-%d").date()

        checkin = (
            db.query(DailyCheckin)
            .filter(DailyCheckin.athlete_id == athlete_id, DailyCheckin.date == race_date)
            .first()
        )
        garmin = None
        if has_garmin:
            garmin = (
                db.query(GarminDay)
                .filter(GarminDay.athlete_id == athlete_id, GarminDay.calendar_date == race_date)
                .first()
            )

        if not checkin and not garmin:
            continue

        race_day_values: Dict[str, float] = {}
        if checkin:
            for input_name, field in _CHECKIN_FIELD_MAP.items():
                val = getattr(checkin, field, None)
                if val is not None:
                    race_day_values[input_name] = float(val)
        if garmin:
            for input_name, field in _GARMIN_FIELD_MAP.items():
                val = getattr(garmin, field, None)
                if val is not None:
                    race_day_values[input_name] = float(val)

        if not race_day_values:
            continue

        for f in threshold_findings:
            if f.input_name not in race_day_values:
                continue
            if _is_garmin_noise(f.input_name):
                continue
            if f.input_name in _GARMIN_ACTIVITY_METRICS:
                continue

            actual_value = race_day_values[f.input_name]
            threshold = f.threshold_value
            direction = f.threshold_direction

            on_bad_side = False
            if direction == "below_matters" and actual_value < threshold:
                on_bad_side = True
            elif direction == "above_matters" and actual_value > threshold:
                on_bad_side = True

            if not on_bad_side:
                continue

            human_input = _translate(f.input_name)
            human_output = _translate(f.output_metric)

            if f.input_name in _SECONDS_FIELDS:
                val_str = _format_seconds_human(actual_value)
                thr_str = _format_seconds_human(threshold)
            else:
                unit = _THRESHOLD_UNITS.get(f.input_name, "")
                if unit:
                    val_str = f"{actual_value:.0f} {unit}".strip()
                    thr_str = f"{threshold:.0f} {unit}".strip()
                else:
                    val_str = f"{actual_value:.1f}"
                    thr_str = f"{threshold:.1f}"

            preposition = "below" if direction == "below_matters" else "above"
            outcome_parts = [
                f"During training, {human_input} {preposition} {thr_str} "
                f"precedes lower {human_output}.",
                f"On {race['date']}, your {human_input} was {val_str}",
            ]
            gap = race.get("gap_pct")
            if gap and gap > 0:
                outcome_parts.append(f"and you ran {gap}% faster than training.")
            elif race.get("is_pb"):
                name = race.get("name")
                dist = race.get("distance_mi")
                outcome_parts.append(
                    f"and you set a PB{f' at {name}' if name else ''}"
                    f"{f' ({dist}mi)' if dist else ''}."
                )
            else:
                outcome_parts.append("and you raced well.")
            text = " ".join(outcome_parts)

            contradictions.append({
                "race_date": race["date"],
                "race_name": race.get("name", ""),
                "gap_pct": race.get("gap_pct"),
                "finding_input": f.input_name,
                "finding_output": f.output_metric,
                "threshold": round(threshold, 1),
                "threshold_direction": direction,
                "actual_value": round(actual_value, 1),
                "times_confirmed": f.times_confirmed,
                "text": text,
            })

    contradictions.sort(key=lambda c: -c["times_confirmed"])
    return contradictions


# ---------------------------------------------------------------------------
# Cascade Stories
# ---------------------------------------------------------------------------

def _is_garmin_noise(field_name: str) -> bool:
    """Check if a field is garmin noise or universally-true environment."""
    from services.fingerprint_context import _is_suppressed_for_athlete
    return _is_suppressed_for_athlete(field_name)


# Subjective inputs and the Garmin metrics that measure the same phenomenon.
# If the mediator is just a device measurement of what the athlete already
# reported, the chain is confounded (common cause), not causal.
_CONFOUNDED_PAIRS: Dict[str, frozenset] = {
    "readiness_1_5": frozenset({
        "garmin_sleep_awake_s", "garmin_body_battery_end",
        "garmin_sleep_score", "garmin_avg_stress",
    }),
    "sleep_quality_1_5": frozenset({
        "garmin_sleep_awake_s", "garmin_sleep_score",
        "garmin_sleep_deep_s", "garmin_sleep_light_s",
        "garmin_sleep_rem_s",
    }),
    "soreness_1_5": frozenset({
        "garmin_body_battery_end", "garmin_avg_stress",
        "garmin_max_stress",
    }),
    "stress_1_5": frozenset({
        "garmin_avg_stress", "garmin_max_stress",
    }),
    "sleep_hours": frozenset({
        "garmin_sleep_awake_s", "garmin_sleep_score",
        "garmin_sleep_deep_s", "garmin_sleep_light_s",
        "garmin_sleep_rem_s",
    }),
}


def _is_confounded_mediator(input_name: str, mediator_variable: str) -> bool:
    """True when input and mediator measure the same underlying phenomenon."""
    confounds = _CONFOUNDED_PAIRS.get(input_name)
    if confounds and mediator_variable in confounds:
        return True
    return False


def _build_cascade_stories(
    all_entries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Group findings with cascade chains into connected stories.

    Filters out stories where the input is a garmin noise metric.
    Prioritizes non-garmin-noise mediators in the chain visualization.
    """
    cascade_entries = [
        e for e in all_entries
        if e.get("cascade") and not _is_garmin_noise(e.get("_input_name", ""))
    ]
    if not cascade_entries:
        return []

    by_input: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in cascade_entries:
        by_input[e.get("_input_name", "unknown")].append(e)

    stories = []

    for input_name, entries in by_input.items():
        meaningful_mediators: Dict[str, float] = {}
        garmin_mediators: Dict[str, float] = {}
        all_outputs = set()
        max_confirmed = 0
        finding_ids = []

        for e in entries:
            all_outputs.add(e.get("output", ""))
            max_confirmed = max(max_confirmed, e.get("times_confirmed", 0))
            finding_ids.append(e.get("id"))
            for c in e.get("cascade", []):
                med_var = c.get("mediator_variable", "")
                med_name = c.get("mediator", "")
                ratio = c.get("mediation_ratio")
                if not med_name or ratio is None:
                    continue
                if _is_garmin_noise(med_var) or _is_confounded_mediator(input_name, med_var):
                    existing = garmin_mediators.get(med_name, 0)
                    garmin_mediators[med_name] = max(existing, ratio)
                else:
                    existing = meaningful_mediators.get(med_name, 0)
                    meaningful_mediators[med_name] = max(existing, ratio)

        # Skip stories where the only mediators are noise or confounded.
        # "readiness → time awake → efficiency" isn't a mechanism —
        # poor sleep causes both low readiness and high awake time.
        if not meaningful_mediators:
            continue
        display_mediators = meaningful_mediators

        human_input = _translate(input_name)
        human_outputs = sorted(all_outputs)
        sorted_meds = sorted(display_mediators.items(), key=lambda x: -x[1])
        top_med_name, top_med_ratio = sorted_meds[0]

        chain = [human_input, top_med_name]
        if len(human_outputs) == 1:
            chain.append(human_outputs[0])
        elif len(human_outputs) <= 3:
            chain.append(", ".join(human_outputs))
        else:
            chain.append(f"{len(human_outputs)} outcomes")

        med_pct = round(top_med_ratio * 100)
        parts = []

        if len(human_outputs) == 1:
            parts.append(
                f"{human_input.capitalize()} affects your {human_outputs[0]} "
                f"through {top_med_name}."
            )
        else:
            output_list = ", ".join(human_outputs[:3])
            parts.append(
                f"{human_input.capitalize()} affects your running through "
                f"{top_med_name} — impacting {output_list}."
            )

        if med_pct >= 70:
            parts.append(
                f"{med_pct}% of the effect travels through {top_med_name}. "
                f"The link is not direct — it's mediated."
            )
        elif med_pct >= 40:
            parts.append(
                f"About {med_pct}% of the effect is mediated through {top_med_name}."
            )

        if len(human_outputs) == 1:
            title = f"How {human_input} shapes your {human_outputs[0]}"
        else:
            title = f"How {human_input} drives {len(human_outputs)} outcomes through {top_med_name}"

        stories.append({
            "id": f"cascade_{input_name}",
            "title": title,
            "input": human_input,
            "input_name": input_name,
            "outputs": human_outputs,
            "chain": chain,
            "mediators": [
                {"name": m, "mediation_pct": round(r * 100)}
                for m, r in sorted_meds[:3]
            ],
            "narrative": " ".join(parts),
            "times_confirmed": max_confirmed,
            "finding_count": len(entries),
            "finding_ids": finding_ids,
        })

    stories.sort(key=lambda s: (-len(s.get("mediators", [])), -s["times_confirmed"]))
    return stories


# ---------------------------------------------------------------------------
# Highlighted findings (interestingness-ranked, human-language)
# ---------------------------------------------------------------------------

def _build_highlighted_findings(
    all_entries: List[Dict[str, Any]],
    max_highlights: int = 12,
) -> List[Dict[str, Any]]:
    """Select the most interesting findings for the lead section.

    Not sorted by confirmation count. Sorted by interestingness:
    cascade chains > counterintuitive > thresholds > asymmetry > timing.
    Garmin noise metrics (steps, body battery) are excluded from highlights.
    """
    scored = []
    for e in all_entries:
        if e.get("source") != "correlation":
            continue
        score = _score_interestingness(e)
        if score <= 0:
            continue
        scored.append((score, e))

    scored.sort(key=lambda x: -x[0])
    return [e for _, e in scored[:max_highlights]]


# ---------------------------------------------------------------------------
# Full record (V1 domain sections)
# ---------------------------------------------------------------------------

def _build_full_record(
    all_entries: List[Dict[str, Any]],
    investigation_entries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build the V1 domain-grouped sections as the full reference layer."""
    domains: Dict[str, List] = {}

    for entry in all_entries:
        domain = entry.get("_domain", "training_pattern")
        domains.setdefault(domain, []).append(entry)

    for entry in investigation_entries:
        domain = entry.get("_domain", "training_pattern")
        domains.setdefault(domain, []).append(entry)

    for entries in domains.values():
        entries.sort(key=lambda e: (-_score_interestingness(e), -e.get("times_confirmed", 0)))

    sections = []
    for domain_key in DOMAIN_ORDER:
        entries = domains.get(domain_key, [])
        if not entries:
            continue
        sections.append({
            "domain": domain_key,
            "label": DOMAIN_LABELS.get(domain_key, domain_key),
            "description": DOMAIN_DESCRIPTIONS.get(domain_key, ""),
            "entry_count": len(entries),
            "entries": entries,
        })

    uncategorized = {k: v for k, v in domains.items() if k not in DOMAIN_ORDER}
    for domain_key, entries in uncategorized.items():
        sections.append({
            "domain": domain_key,
            "label": domain_key.replace("_", " ").title(),
            "description": "",
            "entry_count": len(entries),
            "entries": entries,
        })

    return sections


# ---------------------------------------------------------------------------
# Main assembler
# ---------------------------------------------------------------------------

def assemble_manual(athlete_id: UUID, db: Session) -> Dict[str, Any]:
    """Build the Personal Operating Manual V2.

    Returns a structured dict with:
      - race_character: racer-vs-trainer gap analysis
      - cascade_stories: connected multi-finding narratives
      - highlighted_findings: interestingness-ranked top findings
      - sections: full V1 domain-grouped record
      - summary: aggregate statistics

    Cached for 1800s (30 minutes) at the router level.
    """
    from models import CorrelationFinding as CF, CorrelationMediator as CM

    findings = (
        db.query(CF)
        .filter(
            CF.athlete_id == athlete_id,
            CF.is_active.is_(True),
            CF.times_confirmed >= 1,
        )
        .order_by(CF.times_confirmed.desc())
        .limit(150)
        .all()
    )

    # Load all mediators for cascade data
    mediators_by_finding: Dict[str, list] = {}
    if findings:
        finding_ids = [f.id for f in findings]
        mediators = db.query(CM).filter(CM.finding_id.in_(finding_ids)).all()
        for m in mediators:
            fid = str(m.finding_id)
            mediators_by_finding.setdefault(fid, []).append({
                "mediator": _translate(m.mediator_variable),
                "mediator_variable": m.mediator_variable,
                "direct_effect": round(m.direct_effect, 3) if m.direct_effect else None,
                "indirect_effect": round(m.indirect_effect, 3) if m.indirect_effect else None,
                "mediation_ratio": round(m.mediation_ratio, 2) if m.mediation_ratio else None,
                "is_full_mediation": m.is_full_mediation,
            })

    # Build correlation entries with cleaned headlines
    all_entries: List[Dict[str, Any]] = []

    for f in findings:
        domain = _classify_domain(f.input_name, f.output_metric)

        if not _passes_strength_surface_gate(f):
            continue

        entry = {
            "id": str(f.id),
            "source": "correlation",
            "input": _translate(f.input_name),
            "output": _translate(f.output_metric),
            "headline": _rewrite_headline(f),
            "direction": f.direction,
            "r": round(f.correlation_coefficient, 2),
            "strength": f.strength,
            "times_confirmed": f.times_confirmed,
            "confidence_tier": _confidence_tier(f.times_confirmed),
            "category": f.category,
            "first_detected": f.first_detected_at.isoformat() if f.first_detected_at else None,
            "last_confirmed": f.last_confirmed_at.isoformat() if f.last_confirmed_at else None,
            "threshold": _format_threshold(f),
            "asymmetry": _format_asymmetry(f),
            "timing": _format_timing(f),
            "cascade": mediators_by_finding.get(str(f.id)),
            "lifecycle_state": getattr(f, "lifecycle_state", None),
            "direction_counterintuitive": getattr(f, "direction_counterintuitive", False),
            # Internal fields for scoring (not rendered by frontend)
            "_input_name": f.input_name,
            "_output_metric": f.output_metric,
            "_domain": domain,
            "_is_baseline": _is_baseline_threshold(f),
        }
        all_entries.append(entry)

    # Build investigation entries
    from models import AthleteFinding as AF

    athlete_findings = (
        db.query(AF)
        .filter(
            AF.athlete_id == athlete_id,
            AF.is_active.is_(True),
        )
        .order_by(AF.last_confirmed_at.desc())
        .limit(100)
        .all()
    )

    investigation_entries: List[Dict[str, Any]] = []
    for af in athlete_findings:
        domain = _classify_investigation_domain(af.investigation_name, af.finding_type)
        investigation_entries.append({
            "id": str(af.id),
            "source": "investigation",
            "investigation": af.investigation_name,
            "finding_type": af.finding_type,
            "headline": af.sentence,
            "confidence": af.confidence,
            "layer": af.layer,
            "first_detected": af.first_detected_at.isoformat() if af.first_detected_at else None,
            "last_confirmed": af.last_confirmed_at.isoformat() if af.last_confirmed_at else None,
            "receipts": af.receipts,
            "_domain": domain,
        })

    # ── Assemble V2 sections ──

    race_character = None
    try:
        race_character = _build_race_character(athlete_id, db)
    except Exception as ex:
        logger.warning("operating_manual: race_character build failed: %s", ex)

    cascade_stories = _build_cascade_stories(all_entries)
    highlighted_findings = _build_highlighted_findings(all_entries)
    sections = _build_full_record(all_entries, investigation_entries)

    # ── Summary stats ──

    now = datetime.now(timezone.utc)
    total_correlation = len(findings)
    confirmed_correlation = sum(1 for f in findings if f.times_confirmed >= 3)
    strong_correlation = sum(1 for f in findings if f.times_confirmed >= 6)
    total_investigation = len(athlete_findings)

    oldest_finding = None
    if findings:
        dates = [f.first_detected_at for f in findings if f.first_detected_at]
        if dates:
            oldest_finding = min(dates).isoformat()

    return {
        "generated_at": now.isoformat(),
        "summary": {
            "total_entries": total_correlation + total_investigation,
            "correlation_findings": total_correlation,
            "confirmed_findings": confirmed_correlation,
            "strong_findings": strong_correlation,
            "investigation_findings": total_investigation,
            "domains_covered": len(sections),
            "learning_since": oldest_finding,
            "cascade_story_count": len(cascade_stories),
        },
        "race_character": race_character,
        "cascade_stories": cascade_stories,
        "highlighted_findings": highlighted_findings,
        "sections": sections,
    }
