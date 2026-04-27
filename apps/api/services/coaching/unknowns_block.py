from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from services.coaching.ledger import get_ledger

QUERY_REQUIRED_FIELDS = {
    "interval_pace_question": ["pace_zones", "recent_injuries"],
    "nutrition_planning": ["gut_sensitivity", "standing_overrides"],
    "injury_assessment": ["recent_injuries", "weekly_volume_mpw"],
    "volume_question": ["weekly_volume_mpw", "current_block_phase"],
    "race_planning": ["target_event", "pace_zones", "recent_injuries"],
    "weight_loss_planning": ["current_weight_lbs", "target_weight_lbs", "cut_active"],
    "general": [],
}

SUGGESTED_QUESTIONS = {
    "weekly_volume_mpw": "What weekly mileage are you actually averaging right now?",
    "current_block_phase": "What phase are you in right now: base, build, peak, taper, recovery, or unstructured?",
    "target_event": "What race distance and date are we aiming this decision around?",
    "recent_injuries": "Any current injury, pain site, or return-from-injury constraint I need to honor?",
    "current_weight_lbs": "What is your current weight?",
    "target_weight_lbs": "What target weight are you aiming for, if any?",
    "pace_zones": "What paces are currently true for easy, threshold, interval, and repetition work?",
    "gut_sensitivity": "Any gut sensitivity or fueling constraint I need to respect?",
    "cut_active": "Are you actively cutting weight right now, and what deficit are you targeting?",
    "standing_overrides": "Any standing coaching boundary I should keep applying?",
}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def detect_query_class(message: str) -> str:
    lower = (message or "").lower()
    if any(
        term in lower
        for term in (
            "weight",
            "cut",
            "drop pounds",
            "lose pounds",
            "mass reduction",
            "body composition",
            "body comp",
        )
    ):
        return "weight_loss_planning"
    if any(
        term in lower
        for term in ("interval", "repetition", "rep pace", "5k pace", "threshold pace")
    ):
        return "interval_pace_question"
    if any(
        term in lower
        for term in (
            "fuel",
            "fueling",
            "breakfast",
            "eat",
            "gel",
            "nutrition",
            "stomach",
            "gut",
        )
    ):
        return "nutrition_planning"
    if any(
        term in lower
        for term in ("injury", "injured", "pain", "hurts", "niggle", "sore")
    ):
        return "injury_assessment"
    if any(term in lower for term in ("mileage", "volume", "mpw", "miles per week")):
        return "volume_question"
    if any(
        term in lower
        for term in ("race", "5k", "10k", "half marathon", "marathon", "pace plan")
    ):
        return "race_planning"
    return "general"


def compute_unknowns(
    db: Session | None,
    athlete_id: UUID,
    query_class: str,
    *,
    now_utc: datetime | None = None,
) -> list[dict[str, Any]]:
    required_fields = QUERY_REQUIRED_FIELDS.get(query_class, [])
    if not required_fields:
        return []
    now = now_utc or _now()
    payload = {}
    if db is not None:
        try:
            payload = get_ledger(db, athlete_id).payload or {}
        except Exception:
            payload = {}

    unknowns = []
    for field in required_fields:
        entry = payload.get(field) or {}
        value = entry.get("value")
        asserted_at = entry.get("asserted_at")
        confirm_after = _parse_time(entry.get("confirm_after"))
        expired = bool(confirm_after and confirm_after <= now)
        if value is None or expired:
            unknowns.append(
                {
                    "field": field,
                    "last_known_value_or_null": value,
                    "asserted_at": asserted_at,
                    "field_required_for": query_class,
                    "suggested_question": SUGGESTED_QUESTIONS.get(
                        field, f"What should I know about {field}?"
                    ),
                    "reason": "expired_at" if expired else "missing_required_field",
                }
            )
    return unknowns
