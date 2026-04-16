"""
Regression test: /v1/training-plans/adaptation-proposals/pending must never
500 due to naive-vs-aware datetime comparison.

The PlanAdaptationProposal.expires_at column is DateTime(timezone=True).
Comparing it against datetime.utcnow() (naive) raises TypeError and
produces a 500 on production — see routers/training_plans.py.

Guard the endpoint by exercising both branches (unexpired + expired) with
tz-aware expires_at values and asserting the handler returns cleanly.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def _authed_client(db_session):
    from main import app
    from core.database import get_db
    from core.auth import get_current_athlete
    from models import Athlete

    athlete = Athlete(
        email=f"tp_adapt_{uuid.uuid4()}@example.com",
        display_name="Adapt Test",
        subscription_tier="pro",
        birthdate=date(1985, 1, 1),
        sex="M",
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)

    def _override_db():
        yield db_session

    def _override_auth():
        return athlete

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_athlete] = _override_auth
    try:
        yield TestClient(app), db_session, athlete
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_athlete, None)


def _make_proposal(db_session, athlete, *, expires_at):
    from models import PlanAdaptationProposal, TrainingPlan

    plan = TrainingPlan(
        athlete_id=athlete.id,
        name="Regression Plan",
        goal_race_name="Test 10k",
        goal_race_date=date.today() + timedelta(days=60),
        goal_race_distance_m=10000,
        total_weeks=12,
        plan_start_date=date.today(),
        plan_end_date=date.today() + timedelta(days=84),
        plan_type="10k",
        status="active",
    )
    db_session.add(plan)
    db_session.flush()

    proposal = PlanAdaptationProposal(
        athlete_id=athlete.id,
        plan_id=plan.id,
        trigger_type="missed_long_run",
        trigger_detail={"detected": True},
        proposed_changes=[{"day": "monday", "changed": True}],
        original_snapshot=[{"day": "monday", "changed": False}],
        affected_week_start=1,
        affected_week_end=2,
        status="pending",
        expires_at=expires_at,
        adaptation_number=1,
    )
    db_session.add(proposal)
    db_session.commit()
    db_session.refresh(proposal)
    return proposal


def test_pending_adaptation_proposal_returns_200_for_unexpired(_authed_client):
    client, db, athlete = _authed_client
    future = datetime.now(timezone.utc) + timedelta(hours=6)
    proposal = _make_proposal(db, athlete, expires_at=future)

    resp = client.get("/v1/training-plans/adaptation-proposals/pending")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body is not None
    assert body["id"] == str(proposal.id)
    assert body["status"] == "pending"


def test_pending_adaptation_proposal_expires_past_without_500(_authed_client):
    """The bug: tz-aware expires_at vs naive datetime.utcnow() raised
    TypeError → 500.  After fix, the handler must quietly return None."""
    client, db, athlete = _authed_client
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    proposal = _make_proposal(db, athlete, expires_at=past)

    resp = client.get("/v1/training-plans/adaptation-proposals/pending")
    assert resp.status_code == 200, resp.text
    assert resp.json() is None

    db.refresh(proposal)
    assert proposal.status == "expired"


def test_pending_adaptation_proposal_returns_null_when_none_exist(_authed_client):
    client, _, _ = _authed_client
    resp = client.get("/v1/training-plans/adaptation-proposals/pending")
    assert resp.status_code == 200
    assert resp.json() is None
