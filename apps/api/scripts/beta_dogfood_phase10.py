"""
Beta dogfood: Phase 10 Coach Action Automation (propose -> confirm -> apply).

Runs fully locally against the in-process FastAPI app using TestClient, and verifies:
- proposal created
- confirm applies change and returns receipt
- plan_modification_log entries exist (audit) with source="coach"
- admin ops snapshot endpoint returns counts

Usage (inside API container):
  python scripts/beta_dogfood_phase10.py
"""

from __future__ import annotations

import os
import sys
from uuid import UUID, uuid4

# Ensure `/app` (API package root) is on sys.path when executed as a script.
_HERE = os.path.dirname(__file__)
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from fastapi.testclient import TestClient

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models import Athlete, CoachActionProposal, PlanModificationLog, PlannedWorkout, TrainingPlan


client = TestClient(app)


def _headers(user: Athlete) -> dict:
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}", "User-Agent": "beta-dogfood-script"}


def _create_user(db, *, role: str = "athlete") -> Athlete:
    athlete = Athlete(
        email=f"beta_dogfood_{uuid4()}@example.com",
        display_name="Beta Dogfood",
        subscription_tier="free",
        role=role,
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    return athlete


def _create_standard_plan(*, athlete: Athlete) -> str:
    resp = client.post(
        "/v2/plans/standard",
        headers=_headers(athlete),
        json={
            "distance": "10k",
            "duration_weeks": 8,
            "days_per_week": 5,
            "volume_tier": "mid",
            "start_date": None,
            "race_name": "Beta Dogfood Plan",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("success") is True
    return body["plan_id"]


def main() -> int:
    db = SessionLocal()
    athlete = None
    admin = None
    plan_id = None
    proposal_id = None
    try:
        athlete = _create_user(db, role="athlete")
        plan_id = _create_standard_plan(athlete=athlete)
        plan_uuid = UUID(plan_id)

        workouts = (
            db.query(PlannedWorkout)
            .filter(PlannedWorkout.plan_id == plan_uuid, PlannedWorkout.athlete_id == athlete.id)
            .order_by(PlannedWorkout.scheduled_date.asc())
            .all()
        )
        assert len(workouts) >= 2, "expected at least 2 planned workouts"
        w1, w2 = workouts[0], workouts[1]
        d1, d2 = w1.scheduled_date, w2.scheduled_date
        assert d1 and d2 and d1 != d2

        print(f"[setup] athlete_id={athlete.id} plan_id={plan_id}")
        print(f"[setup] w1={w1.id} date={d1.isoformat()} title={w1.title!r}")
        print(f"[setup] w2={w2.id} date={d2.isoformat()} title={w2.title!r}")

        idem = f"beta10_{uuid4().hex}"
        propose = client.post(
            "/v2/coach/actions/propose",
            headers=_headers(athlete),
            json={
                "athlete_id": str(athlete.id),
                "reason": "Dogfood: swap two workouts.",
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
                                "reason": "beta dogfood swap",
                            },
                        }
                    ],
                },
            },
        )
        assert propose.status_code == 200, propose.text
        proposal_id = propose.json()["proposal_id"]
        print(f"[propose] proposal_id={proposal_id} status={propose.json().get('status')}")

        confirm = client.post(
            f"/v2/coach/actions/{proposal_id}/confirm",
            headers=_headers(athlete),
            json={"idempotency_key": f"confirm_{uuid4().hex}"},
        )
        assert confirm.status_code == 200, confirm.text
        body = confirm.json()
        print(f"[confirm] status={body.get('status')} applied_at={body.get('applied_at')}")
        print(f"[receipt] {body.get('receipt')}")

        db.refresh(w1)
        db.refresh(w2)
        print(f"[verify] w1 new_date={w1.scheduled_date} (expected {d2})")
        print(f"[verify] w2 new_date={w2.scheduled_date} (expected {d1})")
        assert w1.scheduled_date == d2
        assert w2.scheduled_date == d1

        audit_rows = (
            db.query(PlanModificationLog)
            .filter(
                PlanModificationLog.athlete_id == athlete.id,
                PlanModificationLog.plan_id == plan_uuid,
                PlanModificationLog.source == "coach",
            )
            .order_by(PlanModificationLog.created_at.desc())
            .limit(10)
            .all()
        )
        print(f"[audit] rows={len(audit_rows)} (expected >= 1)")
        assert len(audit_rows) >= 1
        for r in audit_rows:
            before = (r.before_state or {}).get("scheduled_date")
            after = (r.after_state or {}).get("scheduled_date")
            print(f"  - action={r.action} workout_id={r.workout_id} {before} -> {after}")

        # Ops snapshot (admin-only endpoint)
        admin = _create_user(db, role="admin")
        ops = client.get("/v1/admin/ops/coach-actions?hours=1", headers=_headers(admin))
        assert ops.status_code == 200, ops.text
        print(f"[ops] {ops.json()}")

        print("[ok] Phase 10 propose/confirm/apply + audit verified.")
        return 0
    finally:
        # Best-effort cleanup to keep local DB tidy.
        try:
            if athlete is not None and plan_id is not None:
                plan_uuid = UUID(plan_id)
                db.query(PlanModificationLog).filter(
                    PlanModificationLog.athlete_id == athlete.id,
                    PlanModificationLog.plan_id == plan_uuid,
                ).delete(synchronize_session=False)
                db.query(CoachActionProposal).filter(CoachActionProposal.athlete_id == athlete.id).delete(
                    synchronize_session=False
                )
                db.query(PlannedWorkout).filter(PlannedWorkout.plan_id == plan_uuid).delete(synchronize_session=False)
                db.query(TrainingPlan).filter(TrainingPlan.id == plan_uuid).delete(synchronize_session=False)
            if athlete is not None:
                db.query(Athlete).filter(Athlete.id == athlete.id).delete(synchronize_session=False)
            if admin is not None:
                db.query(Athlete).filter(Athlete.id == admin.id).delete(synchronize_session=False)
            db.commit()
        except Exception:
            db.rollback()
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

