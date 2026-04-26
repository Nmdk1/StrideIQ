from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from models import AthleteFacts, AthleteFactsAudit

VALID_FACT_FIELDS = frozenset(
    {
        "weekly_volume_mpw",
        "current_block_phase",
        "target_event",
        "pr_per_distance",
        "recent_injuries",
        "current_weight_lbs",
        "target_weight_lbs",
        "age",
        "coaching_voice_preference",
        "pace_zones",
        "gut_sensitivity",
        "cut_active",
        "typical_training_days_per_week",
        "standing_overrides",
    }
)

SENSITIVE_FACT_FIELDS = frozenset(
    {
        "recent_injuries",
        "current_weight_lbs",
        "target_weight_lbs",
        "gut_sensitivity",
        "cut_active",
    }
)

CONFIDENCE_PRECEDENCE = {
    "inferred": 1,
    "derived": 2,
    "athlete_confirmed": 3,
    "athlete_stated": 4,
}

DEFAULT_CONFIRM_DAYS = {
    "weekly_volume_mpw": 30,
    "current_weight_lbs": 14,
    "recent_injuries": 7,
    "pace_zones": 60,
    "cut_active": 14,
}


@dataclass(frozen=True)
class PendingConflict:
    field: str
    existing: dict[str, Any]
    proposed: dict[str, Any]
    reason: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _parse_iso(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _confirm_after(field: str, value: Any, asserted_at: datetime) -> str:
    if field == "target_event" and isinstance(value, dict) and value.get("date"):
        try:
            race_date = datetime.fromisoformat(str(value["date"])).replace(
                tzinfo=timezone.utc
            )
            return _iso(race_date + timedelta(days=1))
        except ValueError:
            pass
    days = DEFAULT_CONFIRM_DAYS.get(field, 60)
    return _iso(asserted_at + timedelta(days=days))


def _validate_field(field: str) -> None:
    if field not in VALID_FACT_FIELDS:
        raise ValueError(f"unsupported_athlete_fact_field:{field}")


def _validate_confidence(confidence: str) -> None:
    if confidence not in CONFIDENCE_PRECEDENCE:
        raise ValueError(f"unsupported_athlete_fact_confidence:{confidence}")


def _fact_entry(
    *,
    value: Any,
    source: str,
    confidence: str,
    asserted_at: datetime,
    audit_trail: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "value": value,
        "confidence": confidence,
        "source": source,
        "asserted_at": _iso(asserted_at),
        "confirm_after": _confirm_after(field="", value=None, asserted_at=asserted_at),
        "audit_trail": audit_trail or [],
    }


def _entry_for_field(
    *,
    field: str,
    value: Any,
    source: str,
    confidence: str,
    asserted_at: datetime,
    audit_trail: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    entry = _fact_entry(
        value=value,
        source=source,
        confidence=confidence,
        asserted_at=asserted_at,
        audit_trail=audit_trail,
    )
    entry["confirm_after"] = _confirm_after(field, value, asserted_at)
    return entry


def get_ledger(
    db: Session,
    athlete_id: UUID,
    *,
    create: bool = True,
    redact_sensitive: bool = False,
) -> AthleteFacts:
    ledger = (
        db.query(AthleteFacts)
        .filter(AthleteFacts.athlete_id == athlete_id)
        .one_or_none()
    )
    if ledger is None:
        if not create:
            raise LookupError(f"athlete_facts_missing:{athlete_id}")
        ledger = AthleteFacts(athlete_id=athlete_id, payload={})
        db.add(ledger)
        db.flush()
    if redact_sensitive:
        return AthleteFacts(
            id=ledger.id,
            athlete_id=ledger.athlete_id,
            payload=redact_ledger_payload(ledger.payload or {}),
            created_at=ledger.created_at,
            updated_at=ledger.updated_at,
        )
    return ledger


def redact_ledger_payload(payload: dict[str, Any]) -> dict[str, Any]:
    redacted = deepcopy(payload or {})
    for field in SENSITIVE_FACT_FIELDS:
        if field in redacted:
            metadata = dict(redacted[field])
            metadata["value"] = None
            metadata["redacted"] = True
            redacted[field] = metadata
    return redacted


def set_fact(
    db: Session,
    athlete_id: UUID,
    field: str,
    value: Any,
    source: str,
    confidence: str,
    asserted_at: datetime | None = None,
) -> AthleteFactsAudit | PendingConflict | None:
    _validate_field(field)
    _validate_confidence(confidence)
    asserted = asserted_at or _now()
    ledger = get_ledger(db, athlete_id)
    payload = deepcopy(ledger.payload or {})
    existing = payload.get(field)

    if existing:
        existing_value = existing.get("value")
        existing_confidence = existing.get("confidence")
        existing_rank = CONFIDENCE_PRECEDENCE.get(existing_confidence, 0)
        proposed_rank = CONFIDENCE_PRECEDENCE[confidence]
        existing_asserted = _parse_iso(
            existing.get("asserted_at")
        ) or datetime.min.replace(tzinfo=timezone.utc)

        if (
            existing_value != value
            and existing_confidence == "athlete_stated"
            and confidence != "athlete_stated"
        ):
            return PendingConflict(
                field=field,
                existing=deepcopy(existing),
                proposed=_entry_for_field(
                    field=field,
                    value=value,
                    source=source,
                    confidence=confidence,
                    asserted_at=asserted,
                ),
                reason="athlete_stated_fact_requires_confirmation_before_overwrite",
            )

        if proposed_rank < existing_rank:
            return None
        if proposed_rank == existing_rank and asserted <= existing_asserted:
            return None

    audit_trail = list((existing or {}).get("audit_trail") or [])
    if existing:
        audit_trail.append(
            {
                "prior_value": existing.get("value"),
                "prior_confidence": existing.get("confidence"),
                "prior_source": existing.get("source"),
                "changed_at": _iso(asserted),
                "change_reason": "set_fact",
            }
        )

    new_entry = _entry_for_field(
        field=field,
        value=value,
        source=source,
        confidence=confidence,
        asserted_at=asserted,
        audit_trail=audit_trail,
    )
    payload[field] = new_entry
    ledger.payload = payload
    ledger.updated_at = _now()
    audit = AthleteFactsAudit(
        athlete_id=athlete_id,
        field=field,
        action="set_fact",
        previous_value=existing,
        new_value=new_entry,
        confidence=confidence,
        source=source,
        reason=None,
        asserted_at=asserted,
    )
    db.add(audit)
    db.flush()
    return audit


def correct_fact(
    db: Session,
    athlete_id: UUID,
    field: str,
    new_value: Any,
    reason: str,
    *,
    asserted_at: datetime | None = None,
) -> AthleteFactsAudit:
    _validate_field(field)
    asserted = asserted_at or _now()
    ledger = get_ledger(db, athlete_id)
    payload = deepcopy(ledger.payload or {})
    existing = payload.get(field)
    audit_trail = list((existing or {}).get("audit_trail") or [])
    if existing:
        audit_trail.append(
            {
                "prior_value": existing.get("value"),
                "prior_confidence": existing.get("confidence"),
                "prior_source": existing.get("source"),
                "changed_at": _iso(asserted),
                "change_reason": reason,
            }
        )
    new_entry = _entry_for_field(
        field=field,
        value=new_value,
        source="manual_edit",
        confidence="athlete_stated",
        asserted_at=asserted,
        audit_trail=audit_trail,
    )
    payload[field] = new_entry
    ledger.payload = payload
    ledger.updated_at = _now()
    audit = AthleteFactsAudit(
        athlete_id=athlete_id,
        field=field,
        action="correct_fact",
        previous_value=existing,
        new_value=new_entry,
        confidence="athlete_stated",
        source="manual_edit",
        reason=reason,
        asserted_at=asserted,
    )
    db.add(audit)
    db.flush()
    return audit


def confirm_fact(
    db: Session,
    athlete_id: UUID,
    field: str,
    *,
    confirmed_at: datetime | None = None,
) -> AthleteFactsAudit:
    _validate_field(field)
    confirmed = confirmed_at or _now()
    ledger = get_ledger(db, athlete_id, create=False)
    payload = deepcopy(ledger.payload or {})
    existing = payload.get(field)
    if not existing:
        raise LookupError(f"athlete_fact_missing:{field}")
    updated = deepcopy(existing)
    updated["confirm_after"] = _confirm_after(field, updated.get("value"), confirmed)
    payload[field] = updated
    ledger.payload = payload
    ledger.updated_at = _now()
    audit = AthleteFactsAudit(
        athlete_id=athlete_id,
        field=field,
        action="confirm_fact",
        previous_value=existing,
        new_value=updated,
        confidence=updated.get("confidence"),
        source="athlete_confirmed",
        reason="confirm_after_reset",
        asserted_at=confirmed,
    )
    db.add(audit)
    db.flush()
    return audit


def get_stale_fields(
    db: Session,
    athlete_id: UUID,
    *,
    now_utc: datetime | None = None,
) -> list[dict[str, Any]]:
    now = now_utc or _now()
    ledger = get_ledger(db, athlete_id, create=False)
    stale = []
    for field, entry in (ledger.payload or {}).items():
        confirm_after = _parse_iso(entry.get("confirm_after"))
        if confirm_after and confirm_after <= now:
            stale.append(
                {
                    "field": field,
                    "last_known_value": entry.get("value"),
                    "asserted_at": entry.get("asserted_at"),
                    "confirm_after": entry.get("confirm_after"),
                    "reason": "confirm_after_expired",
                }
            )
    return stale
