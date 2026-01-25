from __future__ import annotations

from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models import CoachActionProposal, Athlete, PlannedWorkout, TrainingPlan, WorkoutTemplate


client = TestClient(app)


def _headers(user: Athlete) -> dict:
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}", "User-Agent": "pytest"}


def _create_user(db, *, role: str = "athlete", subscription_tier: str = "free") -> Athlete:
    athlete = Athlete(
        email=f"phase10_{uuid4()}@example.com",
        display_name="Phase10 Athlete",
        subscription_tier=subscription_tier,
        role=role,
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    return athlete


def _cleanup(db, *, athlete_ids: list[UUID] | None = None, plan_ids: list[UUID] | None = None) -> None:
    athlete_ids = athlete_ids or []
    plan_ids = plan_ids or []
    try:
        # Proposals first (FK to athlete, plan optional)
        if athlete_ids:
            db.query(CoachActionProposal).filter(CoachActionProposal.athlete_id.in_(athlete_ids)).delete(
                synchronize_session=False
            )

        # Plans/workouts
        if plan_ids:
            db.query(PlannedWorkout).filter(PlannedWorkout.plan_id.in_(plan_ids)).delete(synchronize_session=False)
            db.query(TrainingPlan).filter(TrainingPlan.id.in_(plan_ids)).delete(synchronize_session=False)

        if athlete_ids:
            db.query(Athlete).filter(Athlete.id.in_(athlete_ids)).delete(synchronize_session=False)

        db.commit()
    except Exception:
        db.rollback()


def _create_standard_plan(db, athlete: Athlete) -> str:
    resp = client.post(
        "/v2/plans/standard",
        headers=_headers(athlete),
        json={
            "distance": "10k",
            "duration_weeks": 8,
            "days_per_week": 5,
            "volume_tier": "mid",
            "start_date": None,
            "race_name": "Phase10 Plan",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("success") is True
    return body["plan_id"]


def test_coach_actions_happy_path_swap_days_and_idempotency():
    db = SessionLocal()
    athlete = None
    plan_id = None
    try:
        athlete = _create_user(db)
        plan_id = _create_standard_plan(db, athlete)
        plan_uuid = UUID(plan_id)

        workouts = (
            db.query(PlannedWorkout)
            .filter(PlannedWorkout.plan_id == plan_uuid, PlannedWorkout.athlete_id == athlete.id)
            .order_by(PlannedWorkout.scheduled_date.asc())
            .all()
        )
        assert len(workouts) >= 2
        w1, w2 = workouts[0], workouts[1]
        assert w1.scheduled_date != w2.scheduled_date
        d1 = w1.scheduled_date
        d2 = w2.scheduled_date

        idem = f"p10_{uuid4().hex}"
        propose = client.post(
            "/v2/coach/actions/propose",
            headers=_headers(athlete),
            json={
                "athlete_id": str(athlete.id),
                "reason": "Swap two workouts for schedule reasons.",
                "idempotency_key": idem,
                "actions": {
                    "version": 1,
                    "actions": [
                        {
                            "type": "swap_days",
                            "payload": {
                                "plan_id": plan_id,
                                "workout_id_1": str(w1.id),
                                "workout_id_2": str(w2.id),
                                "reason": "phase10 swap",
                            },
                        }
                    ],
                },
            },
        )
        assert propose.status_code == 200, propose.text
        proposal_id = propose.json()["proposal_id"]
        assert propose.json()["status"] == "proposed"
        assert propose.json()["target_plan_id"] == plan_id

        # Idempotent re-propose returns the same proposal_id
        propose2 = client.post(
            "/v2/coach/actions/propose",
            headers=_headers(athlete),
            json={
                "athlete_id": str(athlete.id),
                "reason": "Swap two workouts for schedule reasons.",
                "idempotency_key": idem,
                "actions": {
                    "version": 1,
                    "actions": [
                        {
                            "type": "swap_days",
                            "payload": {
                                "plan_id": plan_id,
                                "workout_id_1": str(w1.id),
                                "workout_id_2": str(w2.id),
                                "reason": "phase10 swap",
                            },
                        }
                    ],
                },
            },
        )
        assert propose2.status_code == 200, propose2.text
        assert propose2.json()["proposal_id"] == proposal_id

        confirm = client.post(
            f"/v2/coach/actions/{proposal_id}/confirm",
            headers=_headers(athlete),
            json={"idempotency_key": f"confirm_{uuid4().hex}"},
        )
        assert confirm.status_code == 200, confirm.text
        body = confirm.json()
        assert body["status"] == "applied"
        assert body["receipt"]["actions_applied"] == 1

        # Verify DB swap occurred
        db.refresh(w1)
        db.refresh(w2)
        assert w1.scheduled_date == d2
        assert w2.scheduled_date == d1
    finally:
        try:
            if athlete is not None and plan_id is not None:
                _cleanup(db, athlete_ids=[athlete.id], plan_ids=[UUID(plan_id)])
        finally:
            db.close()


def test_coach_actions_require_auth():
    # Provide a syntactically valid body; auth should fail before it matters.
    fake_plan = str(uuid4())
    fake_workout = str(uuid4())
    resp = client.post(
        "/v2/coach/actions/propose",
        json={
            "athlete_id": str(uuid4()),
            "reason": "x" * 10,
            "idempotency_key": f"p10_{uuid4().hex}",
            "actions": {
                "version": 1,
                "actions": [
                    {
                        "type": "skip_or_restore",
                        "payload": {"plan_id": fake_plan, "workout_id": fake_workout, "skipped": True},
                    }
                ],
            },
        },
    )
    assert resp.status_code == 401, resp.text


def test_coach_actions_reject_and_block_confirm():
    db = SessionLocal()
    athlete = None
    plan_id = None
    try:
        athlete = _create_user(db)
        plan_id = _create_standard_plan(db, athlete)
        plan_uuid = UUID(plan_id)
        workout = (
            db.query(PlannedWorkout)
            .filter(PlannedWorkout.plan_id == plan_uuid, PlannedWorkout.athlete_id == athlete.id)
            .first()
        )
        assert workout is not None

        propose = client.post(
            "/v2/coach/actions/propose",
            headers=_headers(athlete),
            json={
                "athlete_id": str(athlete.id),
                "reason": "Skip this workout.",
                "idempotency_key": f"p10_{uuid4().hex}",
                "actions": {
                    "version": 1,
                    "actions": [
                        {
                            "type": "skip_or_restore",
                            "payload": {"plan_id": plan_id, "workout_id": str(workout.id), "skipped": True},
                        }
                    ],
                },
            },
        )
        assert propose.status_code == 200, propose.text
        proposal_id = propose.json()["proposal_id"]

        rej = client.post(
            f"/v2/coach/actions/{proposal_id}/reject",
            headers=_headers(athlete),
            json={"reason": "Not today."},
        )
        assert rej.status_code == 200, rej.text
        assert rej.json()["status"] == "rejected"

        confirm = client.post(
            f"/v2/coach/actions/{proposal_id}/confirm",
            headers=_headers(athlete),
            json={"idempotency_key": f"confirm_{uuid4().hex}"},
        )
        assert confirm.status_code == 409, confirm.text
    finally:
        try:
            if athlete is not None and plan_id is not None:
                _cleanup(db, athlete_ids=[athlete.id], plan_ids=[UUID(plan_id)])
        finally:
            db.close()


def test_coach_actions_forbid_other_user_confirm():
    db = SessionLocal()
    a1 = None
    a2 = None
    plan_id = None
    try:
        a1 = _create_user(db)
        a2 = _create_user(db)
        plan_id = _create_standard_plan(db, a1)
        plan_uuid = UUID(plan_id)
        workout = (
            db.query(PlannedWorkout)
            .filter(PlannedWorkout.plan_id == plan_uuid, PlannedWorkout.athlete_id == a1.id)
            .first()
        )
        assert workout is not None

        propose = client.post(
            "/v2/coach/actions/propose",
            headers=_headers(a1),
            json={
                "athlete_id": str(a1.id),
                "reason": "Skip this workout.",
                "idempotency_key": f"p10_{uuid4().hex}",
                "actions": {
                    "version": 1,
                    "actions": [
                        {
                            "type": "skip_or_restore",
                            "payload": {"plan_id": plan_id, "workout_id": str(workout.id), "skipped": True},
                        }
                    ],
                },
            },
        )
        assert propose.status_code == 200, propose.text
        proposal_id = propose.json()["proposal_id"]

        confirm = client.post(
            f"/v2/coach/actions/{proposal_id}/confirm",
            headers=_headers(a2),
            json={"idempotency_key": f"confirm_{uuid4().hex}"},
        )
        assert confirm.status_code == 403, confirm.text
    finally:
        try:
            ids = [str(x.id) for x in (a1, a2) if x is not None]
            if ids and plan_id:
                _cleanup(db, athlete_ids=[UUID(x) for x in ids], plan_ids=[UUID(plan_id)])
        finally:
            db.close()


def test_coach_actions_replace_with_template_applies_title_change():
    db = SessionLocal()
    athlete = None
    plan_id = None
    try:
        athlete = _create_user(db, subscription_tier="elite")
        plan_id = _create_standard_plan(db, athlete)
        plan_uuid = UUID(plan_id)

        tpl = db.query(WorkoutTemplate).filter(WorkoutTemplate.id == "build_threshold_2x10").first()
        assert tpl is not None, "seeded workout template missing"

        workout = (
            db.query(PlannedWorkout)
            .filter(PlannedWorkout.plan_id == plan_uuid, PlannedWorkout.athlete_id == athlete.id)
            .first()
        )
        assert workout is not None

        propose = client.post(
            "/v2/coach/actions/propose",
            headers=_headers(athlete),
            json={
                "athlete_id": str(athlete.id),
                "reason": "Replace with a known template.",
                "idempotency_key": f"p10_{uuid4().hex}",
                "actions": {
                    "version": 1,
                    "actions": [
                        {
                            "type": "replace_with_template",
                            "payload": {
                                "plan_id": plan_id,
                                "workout_id": str(workout.id),
                                "template_id": tpl.id,
                                "variant": "A",
                            },
                        }
                    ],
                },
            },
        )
        assert propose.status_code == 200, propose.text
        proposal_id = propose.json()["proposal_id"]

        confirm = client.post(
            f"/v2/coach/actions/{proposal_id}/confirm",
            headers=_headers(athlete),
            json={"idempotency_key": f"confirm_{uuid4().hex}"},
        )
        assert confirm.status_code == 200, confirm.text

        db.refresh(workout)
        assert (workout.title or "").startswith(tpl.name)
    finally:
        try:
            if athlete is not None and plan_id is not None:
                _cleanup(db, athlete_ids=[athlete.id], plan_ids=[UUID(plan_id)])
        finally:
            db.close()

