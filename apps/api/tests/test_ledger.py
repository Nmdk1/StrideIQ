from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text

from models import Athlete, AthleteFacts, AthleteFactsAudit
from services.coaching.ledger import (
    PendingConflict,
    confirm_fact,
    correct_fact,
    get_ledger,
    get_stale_fields,
    redact_ledger_payload,
    set_fact,
)


def _athlete(db_session):
    athlete = Athlete(
        email=f"ledger_{uuid4()}@example.com",
        display_name="Ledger Athlete",
        subscription_tier="guided",
        ai_consent=True,
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)
    return athlete


def test_ledger_roundtrip_write_read_correct_confirm(db_session):
    athlete = _athlete(db_session)
    asserted_at = datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc)

    audit = set_fact(
        db_session,
        athlete.id,
        "weekly_volume_mpw",
        52.0,
        source="turn_id:abc",
        confidence="athlete_stated",
        asserted_at=asserted_at,
    )
    db_session.commit()

    assert isinstance(audit, AthleteFactsAudit)
    ledger = get_ledger(db_session, athlete.id)
    assert ledger.payload["weekly_volume_mpw"]["value"] == 52.0
    assert ledger.payload["weekly_volume_mpw"]["confidence"] == "athlete_stated"
    assert ledger.payload["weekly_volume_mpw"]["source"] == "turn_id:abc"

    correction = correct_fact(
        db_session,
        athlete.id,
        "weekly_volume_mpw",
        60.0,
        "athlete_corrected_volume",
        asserted_at=asserted_at + timedelta(minutes=1),
    )
    db_session.commit()

    ledger = get_ledger(db_session, athlete.id)
    assert correction.action == "correct_fact"
    assert ledger.payload["weekly_volume_mpw"]["value"] == 60.0
    assert ledger.payload["weekly_volume_mpw"]["audit_trail"][0]["prior_value"] == 52.0

    old_confirm_after = ledger.payload["weekly_volume_mpw"]["confirm_after"]
    confirm = confirm_fact(
        db_session,
        athlete.id,
        "weekly_volume_mpw",
        confirmed_at=asserted_at + timedelta(days=2),
    )
    db_session.commit()
    ledger = get_ledger(db_session, athlete.id)
    assert confirm.action == "confirm_fact"
    assert ledger.payload["weekly_volume_mpw"]["confirm_after"] > old_confirm_after


@pytest.mark.parametrize(
    ("existing_confidence", "new_confidence", "expected_value"),
    [
        ("inferred", "derived", 2),
        ("derived", "athlete_confirmed", 2),
        ("athlete_confirmed", "athlete_stated", 2),
        ("derived", "inferred", 1),
    ],
)
def test_ledger_conflict_resolution_precedence(
    db_session, existing_confidence, new_confidence, expected_value
):
    athlete = _athlete(db_session)
    base_time = datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc)
    set_fact(
        db_session,
        athlete.id,
        "typical_training_days_per_week",
        1,
        source="test",
        confidence=existing_confidence,
        asserted_at=base_time,
    )

    set_fact(
        db_session,
        athlete.id,
        "typical_training_days_per_week",
        2,
        source="test",
        confidence=new_confidence,
        asserted_at=base_time + timedelta(minutes=1),
    )
    db_session.commit()

    ledger = get_ledger(db_session, athlete.id)
    assert ledger.payload["typical_training_days_per_week"]["value"] == expected_value


def test_ledger_same_precedence_newer_wins_older_ignored(db_session):
    athlete = _athlete(db_session)
    base_time = datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc)

    set_fact(
        db_session,
        athlete.id,
        "age",
        57,
        source="turn:a",
        confidence="athlete_stated",
        asserted_at=base_time,
    )
    ignored = set_fact(
        db_session,
        athlete.id,
        "age",
        58,
        source="turn:b",
        confidence="athlete_stated",
        asserted_at=base_time - timedelta(minutes=1),
    )
    applied = set_fact(
        db_session,
        athlete.id,
        "age",
        56,
        source="turn:c",
        confidence="athlete_stated",
        asserted_at=base_time + timedelta(minutes=1),
    )
    db_session.commit()

    assert ignored is None
    assert isinstance(applied, AthleteFactsAudit)
    assert get_ledger(db_session, athlete.id).payload["age"]["value"] == 56


def test_ledger_athlete_stated_conflict_returns_pending_conflict(db_session):
    athlete = _athlete(db_session)
    base_time = datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc)

    set_fact(
        db_session,
        athlete.id,
        "current_weight_lbs",
        190.0,
        source="turn:a",
        confidence="athlete_stated",
        asserted_at=base_time,
    )
    conflict = set_fact(
        db_session,
        athlete.id,
        "current_weight_lbs",
        188.0,
        source="device_sync",
        confidence="derived",
        asserted_at=base_time + timedelta(minutes=1),
    )
    db_session.commit()

    assert isinstance(conflict, PendingConflict)
    assert conflict.field == "current_weight_lbs"
    assert (
        get_ledger(db_session, athlete.id).payload["current_weight_lbs"]["value"]
        == 190.0
    )


def test_ledger_staleness_returns_expired_fields(db_session):
    athlete = _athlete(db_session)
    asserted_at = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    set_fact(
        db_session,
        athlete.id,
        "current_weight_lbs",
        190.0,
        source="turn:a",
        confidence="athlete_stated",
        asserted_at=asserted_at,
    )
    db_session.commit()

    stale = get_stale_fields(
        db_session,
        athlete.id,
        now_utc=asserted_at + timedelta(days=15),
    )

    assert stale == [
        {
            "field": "current_weight_lbs",
            "last_known_value": 190.0,
            "asserted_at": "2026-01-01T12:00:00+00:00",
            "confirm_after": "2026-01-15T12:00:00+00:00",
            "reason": "confirm_after_expired",
        }
    ]


def test_ledger_redacts_sensitive_fields_without_removing_metadata(db_session):
    athlete = _athlete(db_session)
    set_fact(
        db_session,
        athlete.id,
        "current_weight_lbs",
        190.0,
        source="turn:a",
        confidence="athlete_stated",
    )
    set_fact(
        db_session,
        athlete.id,
        "weekly_volume_mpw",
        52.0,
        source="turn:b",
        confidence="athlete_stated",
    )
    db_session.commit()

    payload = get_ledger(db_session, athlete.id).payload
    redacted = redact_ledger_payload(payload)
    redacted_ledger = get_ledger(db_session, athlete.id, redact_sensitive=True)

    assert redacted["current_weight_lbs"]["value"] is None
    assert redacted["current_weight_lbs"]["redacted"] is True
    assert redacted["current_weight_lbs"]["confidence"] == "athlete_stated"
    assert redacted["weekly_volume_mpw"]["value"] == 52.0
    assert redacted_ledger.payload["current_weight_lbs"]["value"] is None
    assert (
        get_ledger(db_session, athlete.id).payload["current_weight_lbs"]["value"]
        == 190.0
    )


def test_ledger_audit_table_is_append_only(db_session):
    athlete = _athlete(db_session)
    audit = set_fact(
        db_session,
        athlete.id,
        "age",
        57,
        source="turn:a",
        confidence="athlete_stated",
    )
    db_session.commit()

    with pytest.raises(Exception, match="athlete_facts_audit is append-only"):
        db_session.execute(
            text("UPDATE athlete_facts_audit SET reason = 'mutated' WHERE id = :id"),
            {"id": audit.id},
        )
        db_session.commit()


def test_ledger_migration_tables_and_indexes_present(db_session):
    inspector = inspect(db_session.bind)

    assert "athlete_facts" in inspector.get_table_names()
    assert "athlete_facts_audit" in inspector.get_table_names()
    facts_columns = {col["name"] for col in inspector.get_columns("athlete_facts")}
    audit_columns = {
        col["name"] for col in inspector.get_columns("athlete_facts_audit")
    }
    audit_indexes = {
        idx["name"] for idx in inspector.get_indexes("athlete_facts_audit")
    }

    assert {"athlete_id", "payload", "created_at", "updated_at"} <= facts_columns
    assert {
        "athlete_id",
        "field",
        "action",
        "previous_value",
        "new_value",
        "created_at",
    } <= audit_columns
    assert "ix_athlete_facts_audit_athlete_field" in audit_indexes
    assert "ix_athlete_facts_audit_athlete_id" in audit_indexes


def test_ledger_model_imports_are_registered():
    assert AthleteFacts.__tablename__ == "athlete_facts"
    assert AthleteFactsAudit.__tablename__ == "athlete_facts_audit"
