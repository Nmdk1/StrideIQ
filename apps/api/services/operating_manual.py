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
    "pace", "race", "subjective", "training_pattern",
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

# Garmin raw fields that athletes don't understand or control.
# Findings with these inputs are valid correlations but should not lead
# the manual — they belong in the full record only.
_GARMIN_INTERNAL_INPUTS = frozenset({
    "garmin_steps", "garmin_active_time_s", "garmin_vigorous_intensity_s",
    "garmin_moderate_intensity_s", "garmin_min_hr", "garmin_max_hr",
    "garmin_avg_stress", "garmin_max_stress", "garmin_body_battery_end",
    "garmin_sleep_score", "garmin_sleep_awake_s", "garmin_sleep_deep_s",
    "garmin_sleep_light_s", "garmin_sleep_rem_s",
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
    "garmin_hrv_5min_high": "HRV",
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
    return input_name not in _GARMIN_INTERNAL_INPUTS


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
}

_THRESHOLD_SUPPRESS = frozenset({
    "daily_session_stress", "ctl", "atl", "tsb",
})


def _format_threshold(finding) -> Optional[Dict[str, Any]]:
    if finding.threshold_value is None:
        return None

    input_name = finding.input_name
    if input_name in _THRESHOLD_SUPPRESS:
        return None
    if _is_garmin_internal(input_name):
        return None

    human_input = _translate(input_name)
    value = finding.threshold_value
    direction = finding.threshold_direction

    # Format value with appropriate precision
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

    if has_cascade:
        score += 30
    if is_counterintuitive:
        score += 25
    if has_threshold and _is_athlete_understandable(input_name):
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

    return {
        "races": race_entries,
        "race_count": len(race_entries),
        "has_gap_data": True,
        "avg_gap_pct": round(avg_gap, 1),
        "pb_count": pb_count,
        "all_pbs": all_pbs,
        "narrative": " ".join(narrative_parts),
    }


# ---------------------------------------------------------------------------
# Cascade Stories
# ---------------------------------------------------------------------------

def _is_garmin_internal(field_name: str) -> bool:
    """Check if a field is a garmin internal metric (not athlete-controllable)."""
    return field_name.startswith("garmin_") or field_name in _GARMIN_INTERNAL_INPUTS


def _build_cascade_stories(
    all_entries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Group findings with cascade chains into connected stories.

    Filters out stories where the input is a garmin internal metric.
    Prioritizes non-garmin mediators in the chain visualization.
    """
    cascade_entries = [
        e for e in all_entries
        if e.get("cascade") and not _is_garmin_internal(e.get("_input_name", ""))
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
                if _is_garmin_internal(med_var):
                    existing = garmin_mediators.get(med_name, 0)
                    garmin_mediators[med_name] = max(existing, ratio)
                else:
                    existing = meaningful_mediators.get(med_name, 0)
                    meaningful_mediators[med_name] = max(existing, ratio)

        # Prefer meaningful mediators; fall back to garmin if nothing else
        display_mediators = meaningful_mediators if meaningful_mediators else garmin_mediators
        if not display_mediators:
            continue

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

        stories.append({
            "id": f"cascade_{input_name}",
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
    Garmin internal metrics are excluded from highlights.
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
        entries.sort(key=lambda e: e.get("times_confirmed", 0), reverse=True)

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
        raw_headline = f.insight_text or f"{_translate(f.input_name)} affects {_translate(f.output_metric)}"

        entry = {
            "id": str(f.id),
            "source": "correlation",
            "input": _translate(f.input_name),
            "output": _translate(f.output_metric),
            "headline": _clean_headline(raw_headline),
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
