"""
Personal Operating Manual — assembles everything the system has learned
about an athlete into a structured, domain-organized document.

Sources:
  - CorrelationFinding (statistical relationships + L1-L4 enrichment)
  - CorrelationMediator (L3 cascade chains)
  - AthleteFinding (investigation-based findings from race_input_analysis)

The manual is deterministic. No LLM calls. The data speaks for itself.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from services.fingerprint_context import COACHING_LANGUAGE

logger = logging.getLogger(__name__)


DOMAIN_ORDER = [
    "recovery",
    "sleep",
    "cardiac",
    "training_load",
    "environmental",
    "pace",
    "race",
    "subjective",
    "training_pattern",
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

_DOMAIN_RULES: List[tuple[str, list[str]]] = [
    ("sleep", ["sleep", "hrv", "rmssd"]),
    ("cardiac", ["heart_rate", "hr_", "resting_hr", "cardiac", "vo2"]),
    ("recovery", ["recovery", "days_since", "body_battery", "tsb", "freshness", "rest"]),
    ("environmental", ["heat", "dew_point", "temperature", "weather", "humidity"]),
    ("training_load", ["ctl", "atl", "volume", "weekly_volume", "distance", "load", "session_stress"]),
    ("subjective", ["readiness", "soreness", "motivation", "stress_1_5", "confidence_1_5", "sleep_quality_1_5",
                     "feedback_", "perceived_effort", "leg_feel", "enjoyment", "rpe"]),
    ("race", ["race", "pb_events"]),
    ("pace", ["pace", "efficiency", "speed", "cadence", "stride"]),
    ("training_pattern", ["long_run", "consecutive", "run_start_hour", "elevation", "workout_variety"]),
]


def _classify_domain(input_name: str, output_metric: str) -> str:
    combined = f"{input_name} {output_metric}".lower()
    for domain, keywords in _DOMAIN_RULES:
        for kw in keywords:
            if kw in combined:
                return domain
    return "training_pattern"


def _translate(field_name: str) -> str:
    if field_name in COACHING_LANGUAGE:
        return COACHING_LANGUAGE[field_name]
    return field_name.replace("_", " ")


def _confidence_tier(times_confirmed: int) -> str:
    if times_confirmed >= 6:
        return "strong"
    if times_confirmed >= 3:
        return "confirmed"
    return "emerging"


def _format_threshold(finding) -> Optional[Dict[str, Any]]:
    if finding.threshold_value is None:
        return None
    return {
        "value": round(finding.threshold_value, 1),
        "direction": finding.threshold_direction,
        "label": (
            f"{_translate(finding.input_name)} cliff at {finding.threshold_value:.1f}"
        ),
    }


def _format_asymmetry(finding) -> Optional[Dict[str, Any]]:
    if finding.asymmetry_ratio is None:
        return None
    return {
        "ratio": round(finding.asymmetry_ratio, 1),
        "direction": finding.asymmetry_direction,
        "label": (
            f"{finding.asymmetry_ratio:.1f}x asymmetry ({finding.asymmetry_direction})"
        ),
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


def assemble_manual(athlete_id: UUID, db: Session) -> Dict[str, Any]:
    """Build the Personal Operating Manual for an athlete.

    Returns a structured dict with domain-grouped entries from both
    CorrelationFinding and AthleteFinding, ordered by evidence strength.
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

    mediators_by_finding: Dict[str, list] = {}
    if findings:
        finding_ids = [f.id for f in findings]
        mediators = db.query(CM).filter(CM.finding_id.in_(finding_ids)).all()
        for m in mediators:
            fid = str(m.finding_id)
            mediators_by_finding.setdefault(fid, []).append({
                "mediator": _translate(m.mediator_variable),
                "direct_effect": round(m.direct_effect, 3) if m.direct_effect else None,
                "indirect_effect": round(m.indirect_effect, 3) if m.indirect_effect else None,
                "mediation_ratio": round(m.mediation_ratio, 2) if m.mediation_ratio else None,
                "is_full_mediation": m.is_full_mediation,
            })

    domains: Dict[str, list] = {}

    for f in findings:
        domain = _classify_domain(f.input_name, f.output_metric)
        entry = {
            "id": str(f.id),
            "source": "correlation",
            "input": _translate(f.input_name),
            "output": _translate(f.output_metric),
            "headline": f.insight_text or f"{_translate(f.input_name)} affects {_translate(f.output_metric)}",
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
        }
        domains.setdefault(domain, []).append(entry)

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

    for af in athlete_findings:
        domain = _classify_investigation_domain(af.investigation_name, af.finding_type)
        entry = {
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
        }
        domains.setdefault(domain, []).append(entry)

    for entries in domains.values():
        entries.sort(key=lambda e: e.get("times_confirmed", 0), reverse=True)

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
        },
        "sections": sections,
    }


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
