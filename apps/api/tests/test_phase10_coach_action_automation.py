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


def _impersonation_headers(*, impersonated: Athlete, impersonated_by: Athlete) -> dict:
    """
    Create an impersonation token payload consistent with /v1/admin/users/{id}/impersonate.
    """
    token = create_access_token(
        {
            "sub": str(impersonated.id),
            "is_impersonation": True,
            "impersonated_by": str(impersonated_by.id),
        }
    )
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


def test_coach_actions_block_confirm_under_impersonation_without_explicit_permission():
    """
    Production beta safety: confirm/apply is blocked under impersonation unless the impersonator
    has explicit permission `coach.actions.apply_impersonation`.
    """
    db = SessionLocal()
    athlete = None
    owner = None
    plan_id = None
    try:
        athlete = _create_user(db)
        owner = _create_user(db, role="owner", subscription_tier="elite")
        # owner has NO explicit permissions by default in this test (strict).
        owner.admin_permissions = []
        db.add(owner)
        db.commit()

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
                        {"type": "skip_or_restore", "payload": {"plan_id": plan_id, "workout_id": str(workout.id), "skipped": True}}
                    ],
                },
            },
        )
        assert propose.status_code == 200, propose.text
        proposal_id = propose.json()["proposal_id"]

        confirm = client.post(
            f"/v2/coach/actions/{proposal_id}/confirm",
            headers=_impersonation_headers(impersonated=athlete, impersonated_by=owner),
            json={"idempotency_key": f"confirm_{uuid4().hex}"},
        )
        assert confirm.status_code == 403, confirm.text
        detail = confirm.json().get("detail")
        assert isinstance(detail, str)
        assert detail.startswith("impersonation_not_allowed:"), detail
    finally:
        try:
            ids = [x.id for x in (athlete, owner) if x is not None]
            if ids and plan_id:
                _cleanup(db, athlete_ids=ids, plan_ids=[UUID(plan_id)])
            elif ids:
                _cleanup(db, athlete_ids=ids, plan_ids=[])
        finally:
            db.close()


def test_coach_actions_apply_failure_rolls_back_and_persists_failed_status():
    """
    If apply fails, plan/workout mutations must be rolled back, but the proposal should
    persist as status=failed with an error string.
    """
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
        d1 = w1.scheduled_date
        d2 = w2.scheduled_date
        w2_snapshot = {
            "id": w2.id,
            "plan_id": w2.plan_id,
            "athlete_id": w2.athlete_id,
            "scheduled_date": w2.scheduled_date,
            "week_number": w2.week_number,
            "day_of_week": w2.day_of_week,
            "workout_type": w2.workout_type,
            "workout_subtype": w2.workout_subtype,
            "title": w2.title,
            "description": w2.description,
            "phase": w2.phase,
            "phase_week": w2.phase_week,
            "target_duration_minutes": w2.target_duration_minutes,
            "target_distance_km": w2.target_distance_km,
            "target_pace_per_km_seconds": w2.target_pace_per_km_seconds,
            "target_pace_per_km_seconds_max": w2.target_pace_per_km_seconds_max,
            "target_hr_min": w2.target_hr_min,
            "target_hr_max": w2.target_hr_max,
            "segments": w2.segments,
            "completed": w2.completed,
            "skipped": w2.skipped,
            "skip_reason": w2.skip_reason,
        }

        # Propose a swap
        propose = client.post(
            "/v2/coach/actions/propose",
            headers=_headers(athlete),
            json={
                "athlete_id": str(athlete.id),
                "reason": "Swap two workouts.",
                "idempotency_key": f"p10_{uuid4().hex}",
                "actions": {
                    "version": 1,
                    "actions": [
                        {
                            "type": "swap_days",
                            "payload": {"plan_id": plan_id, "workout_id_1": str(w1.id), "workout_id_2": str(w2.id)},
                        }
                    ],
                },
            },
        )
        assert propose.status_code == 200, propose.text
        proposal_id = propose.json()["proposal_id"]

        # Delete one workout BEFORE confirm to force apply to fail (404 in _require_workout_owner).
        db.delete(w2)
        db.commit()

        confirm = client.post(
            f"/v2/coach/actions/{proposal_id}/confirm",
            headers=_headers(athlete),
            json={"idempotency_key": f"confirm_{uuid4().hex}"},
        )
        assert confirm.status_code in (404, 500), confirm.text

        # Ensure proposal is marked failed in DB.
        failed = db.query(CoachActionProposal).filter(CoachActionProposal.id == UUID(proposal_id)).first()
        assert failed is not None
        assert failed.status == "failed"
        assert failed.error is not None

        # Ensure no swap occurred (w1 should still be at original date).
        db.refresh(w1)
        assert w1.scheduled_date == d1
        # w2 is deleted; ensure no other workout moved into d1 unexpectedly.
        other_on_d1 = db.query(PlannedWorkout).filter(
            PlannedWorkout.plan_id == plan_uuid,
            PlannedWorkout.athlete_id == athlete.id,
            PlannedWorkout.scheduled_date == d1,
        ).count()
        assert other_on_d1 >= 1

        # Now fix the underlying cause and retry confirm (must be allowed for failed proposals).
        repaired = PlannedWorkout(
            id=w2_snapshot["id"],
            plan_id=w2_snapshot["plan_id"],
            athlete_id=w2_snapshot["athlete_id"],
            scheduled_date=w2_snapshot["scheduled_date"],
            week_number=w2_snapshot["week_number"],
            day_of_week=w2_snapshot["day_of_week"],
            workout_type=w2_snapshot["workout_type"],
            workout_subtype=w2_snapshot["workout_subtype"],
            title=w2_snapshot["title"],
            description=w2_snapshot["description"],
            phase=w2_snapshot["phase"],
            phase_week=w2_snapshot["phase_week"],
            target_duration_minutes=w2_snapshot["target_duration_minutes"],
            target_distance_km=w2_snapshot["target_distance_km"],
            target_pace_per_km_seconds=w2_snapshot["target_pace_per_km_seconds"],
            target_pace_per_km_seconds_max=w2_snapshot["target_pace_per_km_seconds_max"],
            target_hr_min=w2_snapshot["target_hr_min"],
            target_hr_max=w2_snapshot["target_hr_max"],
            segments=w2_snapshot["segments"],
            completed=bool(w2_snapshot["completed"]),
            skipped=bool(w2_snapshot["skipped"]),
            skip_reason=w2_snapshot["skip_reason"],
        )
        db.add(repaired)
        db.commit()

        confirm2 = client.post(
            f"/v2/coach/actions/{proposal_id}/confirm",
            headers=_headers(athlete),
            json={"idempotency_key": f"confirm_{uuid4().hex}"},
        )
        assert confirm2.status_code == 200, confirm2.text
        assert confirm2.json()["status"] == "applied"

        # Verify swap occurred on retry
        db.refresh(w1)
        db.refresh(repaired)
        assert w1.scheduled_date == d2
        assert repaired.scheduled_date == d1
    finally:
        try:
            if athlete is not None and plan_id is not None:
                _cleanup(db, athlete_ids=[athlete.id], plan_ids=[UUID(plan_id)])
        finally:
            db.close()

