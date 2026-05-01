from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from models import Athlete
from services.coaching.ledger import set_fact
from services.coaching.runtime_v2_packet import assemble_v2_packet
from services.coaching.unknowns_block import compute_unknowns, detect_query_class


def test_query_class_detection_routes_common_questions():
    assert (
        detect_query_class("What should my interval pace be?")
        == "interval_pace_question"
    )
    assert (
        detect_query_class("What should I eat for race morning?")
        == "nutrition_planning"
    )
    assert detect_query_class("My achilles hurts, should I run?") == "injury_assessment"
    assert detect_query_class("Should I raise weekly mileage?") == "volume_question"
    assert detect_query_class("Give me a 10k race plan") == "race_planning"
    assert (
        detect_query_class("I want to drop pounds this summer")
        == "weight_loss_planning"
    )
    assert (
        detect_query_class("How should nutrition support body composition goals?")
        == "weight_loss_planning"
    )


def test_missing_required_field_surfaces_unknown_with_question(db_session):
    athlete = Athlete(
        email=f"unknowns_{uuid4()}@example.com",
        display_name="Unknowns Athlete",
        subscription_tier="guided",
        ai_consent=True,
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)

    unknowns = compute_unknowns(db_session, athlete.id, "race_planning")

    fields = {unknown["field"] for unknown in unknowns}
    assert {"target_event", "pace_zones", "recent_injuries"} <= fields
    target = next(unknown for unknown in unknowns if unknown["field"] == "target_event")
    assert target["field_required_for"] == "race_planning"
    assert target["last_known_value_or_null"] is None
    assert target["reason"] == "missing_required_field"
    assert "race distance and date" in target["suggested_question"]


def test_expired_required_field_surfaces_with_expired_reason(db_session):
    athlete = Athlete(
        email=f"unknowns_expired_{uuid4()}@example.com",
        display_name="Unknowns Expired Athlete",
        subscription_tier="guided",
        ai_consent=True,
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)
    asserted = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    set_fact(
        db_session,
        athlete.id,
        "weekly_volume_mpw",
        60.0,
        source="turn:test",
        confidence="athlete_stated",
        asserted_at=asserted,
    )
    db_session.commit()

    # injury_assessment requires weekly_volume_mpw; volume_question does not
    # (volume is derivable from recent activities).
    unknowns = compute_unknowns(
        db_session,
        athlete.id,
        "injury_assessment",
        now_utc=asserted + timedelta(days=31),
    )

    weekly = next(
        unknown for unknown in unknowns if unknown["field"] == "weekly_volume_mpw"
    )
    assert weekly["last_known_value_or_null"] == 60.0
    assert weekly["reason"] == "expired_at"


def test_packet_unknowns_block_replaces_empty_unknowns_for_required_fields():
    packet = assemble_v2_packet(
        athlete_id=uuid4(),
        message="Give me a 10k race plan.",
        conversation_context=[],
        legacy_athlete_state="ATHLETE STATE",
    )

    assert packet["conversation_mode"]["query_class"] == "race_planning"
    assert packet["blocks"]["unknowns"]["data"]
    assert (
        packet["blocks"]["unknowns"]["unknowns"] == packet["blocks"]["unknowns"]["data"]
    )
    assert packet["telemetry"]["unknown_count"] >= len(
        packet["blocks"]["unknowns"]["data"]
    )
