from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from models import Athlete
from services.coaching.ledger import get_ledger
from services.coaching.ledger_extraction import (
    extract_facts_from_turn,
    persist_proposed_facts,
)


def _fact_map(message: str):
    asserted_at = datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc)
    facts = extract_facts_from_turn(
        uuid4(),
        message,
        source="turn_id:test",
        asserted_at=asserted_at,
    )
    return {fact.field: fact for fact in facts}


def test_extracts_weekly_volume_from_mpw_phrase():
    facts = _fact_map("I'm a 60mpw runner right now.")

    assert facts["weekly_volume_mpw"].value == 60.0
    assert facts["weekly_volume_mpw"].confidence == "athlete_stated"
    assert facts["weekly_volume_mpw"].source == "turn_id:test"


def test_extracts_age_correction_before_wrong_age():
    facts = _fact_map("I only do trap bar deadlifts and I'm 57 NOT 58.")

    assert facts["age"].value == 57
    assert facts["standing_overrides"].value == [
        {
            "domain": "strength_lift_preference",
            "value": "trap_bar_deadlift_only",
            "asserted_at": "2026-04-26T12:00:00+00:00",
        }
    ]


def test_extracts_weight_cut_and_target_event_goal():
    facts = _fact_map(
        "My plan is to drop 30 pounds before fall. Goals are sub 18 5k in fall."
    )

    assert facts["cut_active"].value == {
        "flag": True,
        "start_date": "2026-04-26",
        "target_deficit_kcal": None,
        "target_loss_lbs": 30.0,
    }
    assert facts["target_event"].value == {
        "distance": "5k",
        "date": None,
        "goal_time": "sub18",
    }


def test_extracts_recent_injury_and_population_override():
    facts = _fact_map("We don't operate on population models. I came back post injury.")

    assert facts["recent_injuries"].value == [
        {
            "site": None,
            "severity": None,
            "started_at": None,
            "status": "recent_or_returning",
        }
    ]
    assert facts["standing_overrides"].value == [
        {
            "domain": "avoid_population_model_assumptions",
            "value": "avoid_population_model_assumptions",
            "asserted_at": "2026-04-26T12:00:00+00:00",
        }
    ]


def test_persist_proposed_facts_writes_standing_override_to_ledger(db_session):
    athlete = Athlete(
        email=f"ledger_extract_{uuid4()}@example.com",
        display_name="Ledger Extract Athlete",
        subscription_tier="guided",
        ai_consent=True,
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)

    facts = extract_facts_from_turn(
        athlete.id,
        "No thank you, no fueling advice unless I ask.",
        source="turn_id:test",
        asserted_at=datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc),
    )
    persist_proposed_facts(db_session, athlete.id, facts)
    db_session.commit()

    ledger = get_ledger(db_session, athlete.id)
    assert ledger.payload["standing_overrides"]["value"] == [
        {
            "domain": "no_unsolicited_fueling_advice",
            "value": "no_unsolicited_fueling_advice",
            "asserted_at": "2026-04-26T12:00:00+00:00",
        }
    ]
