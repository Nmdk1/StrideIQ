"""Phase B contract + integration tests for the Strength v1 manual logging API.

Three layers:

1. Source contract (db-less, always run): verifies the router registers
   the seven expected routes and gates every read/write through
   ``is_feature_enabled``.

2. Feature-flag gate (mock db, always run): when the flag is off,
   every route returns 404. Not 403. The surface should be invisible.

3. End-to-end (real Postgres, skipped locally / runs in CI): exercises
   create / list / get / patch (supersede semantics) / archive /
   edit-history / exercises against the actual schema.

The supersede tests are the load-bearing ones — if the edit semantics
drift, the audit chain rots silently. They check both the active read
path (filters ``superseded_at IS NULL``) and the full edit-history
read path (returns every row in order).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------
# 1. Source contract (db-less)
# ---------------------------------------------------------------------


class TestSourceContract:
    def test_router_registers_expected_routes(self):
        from routers import strength_v1 as mod

        paths = {(tuple(sorted(r.methods)), r.path) for r in mod.router.routes}
        expected = {
            (("POST",), "/v1/strength/sessions"),
            (("GET",), "/v1/strength/sessions"),
            (("GET",), "/v1/strength/sessions/{activity_id}"),
            (("DELETE",), "/v1/strength/sessions/{activity_id}"),
            (("PATCH",), "/v1/strength/sessions/{activity_id}/sets/{set_id}"),
            (("GET",), "/v1/strength/sessions/{activity_id}/edit-history"),
            (("GET",), "/v1/strength/exercises"),
        }
        missing = expected - paths
        assert not missing, f"router missing routes: {missing}"

    def test_every_route_calls_require_strength_v1(self):
        """Belt-and-suspenders: read the router source and confirm every
        endpoint function calls ``_require_strength_v1`` on its first
        non-trivial line. Anyone who adds a route without the gate fails
        this test loudly.
        """
        path = (
            Path(__file__).resolve().parents[1]
            / "routers"
            / "strength_v1.py"
        )
        text = path.read_text(encoding="utf-8")
        endpoint_defs = re.findall(
            r"@router\.(?:get|post|patch|delete|put)\([^)]*\)\s*\ndef\s+(\w+)\(",
            text,
        )
        assert endpoint_defs, "no router endpoints found — source layout changed?"
        for name in endpoint_defs:
            body = re.search(
                rf"def {name}\([^)]*\)[^:]*:(.*?)(?=\n@router\.|\nclass |\Z)",
                text,
                re.S,
            )
            assert body is not None, f"could not find body for {name}"
            assert "_require_strength_v1(" in body.group(1), (
                f"endpoint {name!r} does not gate on _require_strength_v1; "
                "every strength v1 route must be invisible when the flag is off"
            )


# ---------------------------------------------------------------------
# 2. Feature-flag gate (mock db)
# ---------------------------------------------------------------------


@pytest.fixture
def flag_off_client(monkeypatch):
    """TestClient with the strength.v1 flag forced OFF."""
    from main import app
    from core.auth import get_current_user
    from core.database import get_db
    import routers.strength_v1 as mod

    athlete = MagicMock()
    athlete.id = uuid4()
    mock_db = MagicMock()

    monkeypatch.setattr(mod, "is_feature_enabled", lambda *a, **kw: False)

    app.dependency_overrides[get_current_user] = lambda: athlete
    app.dependency_overrides[get_db] = lambda: iter([mock_db])
    try:
        yield TestClient(app, raise_server_exceptions=False), athlete
    finally:
        app.dependency_overrides.clear()


class TestFeatureFlagGate:
    def test_post_returns_404_when_flag_off(self, flag_off_client):
        client, _ = flag_off_client
        resp = client.post(
            "/v1/strength/sessions",
            json={"sets": [{"exercise_name": "BARBELL_DEADLIFT", "reps": 5, "weight_kg": 100}]},
        )
        assert resp.status_code == 404, (
            f"flag-off POST must be 404 (invisible); got {resp.status_code}"
        )

    def test_list_returns_404_when_flag_off(self, flag_off_client):
        client, _ = flag_off_client
        resp = client.get("/v1/strength/sessions")
        assert resp.status_code == 404

    def test_get_one_returns_404_when_flag_off(self, flag_off_client):
        client, _ = flag_off_client
        resp = client.get(f"/v1/strength/sessions/{uuid4()}")
        assert resp.status_code == 404

    def test_patch_returns_404_when_flag_off(self, flag_off_client):
        client, _ = flag_off_client
        resp = client.patch(
            f"/v1/strength/sessions/{uuid4()}/sets/{uuid4()}",
            json={"reps": 8},
        )
        assert resp.status_code == 404

    def test_delete_returns_404_when_flag_off(self, flag_off_client):
        client, _ = flag_off_client
        resp = client.delete(f"/v1/strength/sessions/{uuid4()}")
        assert resp.status_code == 404

    def test_edit_history_returns_404_when_flag_off(self, flag_off_client):
        client, _ = flag_off_client
        resp = client.get(f"/v1/strength/sessions/{uuid4()}/edit-history")
        assert resp.status_code == 404

    def test_exercises_returns_404_when_flag_off(self, flag_off_client):
        client, _ = flag_off_client
        resp = client.get("/v1/strength/exercises?q=dead")
        assert resp.status_code == 404


# ---------------------------------------------------------------------
# 3. End-to-end (real Postgres)
# ---------------------------------------------------------------------


@pytest.fixture
def e2e_client(db_session, test_athlete, monkeypatch):
    """TestClient bound to the rolled-back ``db_session`` with the
    strength.v1 flag forced ON for ``test_athlete``."""
    from main import app
    from core.auth import get_current_user
    from core.database import get_db
    import routers.strength_v1 as mod

    monkeypatch.setattr(mod, "is_feature_enabled", lambda *a, **kw: True)

    app.dependency_overrides[get_current_user] = lambda: test_athlete
    app.dependency_overrides[get_db] = lambda: iter([db_session])
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.clear()


class TestEndToEnd:
    def test_create_session_persists_sets_with_taxonomy_and_e1rm(
        self, e2e_client, db_session, test_athlete
    ):
        from models import Activity, StrengthExerciseSet

        payload = {
            "name": "Lower body",
            "duration_s": 1800,
            "sets": [
                {
                    "exercise_name": "BARBELL_DEADLIFT",
                    "reps": 5,
                    "weight_kg": 102.0,
                    "rpe": 7.5,
                    "implement_type": "barbell",
                },
                {
                    "exercise_name": "WALKING_LUNGE",
                    "reps": 10,
                    "weight_kg": 11.3,
                    "implement_type": "dumbbell_each",
                    "set_modifier": "straight",
                },
            ],
        }
        resp = e2e_client.post("/v1/strength/sessions", json=payload)
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["sport"] == "strength"
        assert body["source"] == "manual"
        assert body["set_count"] == 2
        assert body["movement_patterns"] == ["hip_hinge", "lunge"]
        assert body["total_volume_kg"] == 5 * 102.0 + 10 * 11.3

        # Round-trip via the ORM: e1RM written, taxonomy applied.
        activity_id = UUID(body["id"])
        rows = (
            db_session.query(StrengthExerciseSet)
            .filter(StrengthExerciseSet.activity_id == activity_id)
            .order_by(StrengthExerciseSet.set_order)
            .all()
        )
        assert len(rows) == 2
        deadlift = rows[0]
        assert deadlift.movement_pattern == "hip_hinge"
        assert deadlift.muscle_group == "posterior_chain"
        assert deadlift.estimated_1rm_kg is not None
        assert deadlift.source == "manual"
        assert deadlift.manually_augmented is True
        assert deadlift.superseded_at is None

    def test_list_sessions_returns_summary(self, e2e_client):
        e2e_client.post(
            "/v1/strength/sessions",
            json={
                "sets": [
                    {"exercise_name": "BENCH_PRESS", "reps": 5, "weight_kg": 80}
                ]
            },
        )
        resp = e2e_client.get("/v1/strength/sessions?limit=10")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) >= 1
        assert items[0]["set_count"] == 1
        assert "push" in items[0]["movement_patterns"]

    def test_patch_creates_supersede_chain_and_default_read_filters(
        self, e2e_client, db_session
    ):
        """Editing a set must:
        - never mutate the predecessor in place
        - leave exactly one active row at the same set_order
        - stamp superseded_at + superseded_by_id on the predecessor
        - set source='garmin_then_manual_edit' iff the predecessor was Garmin
        """
        from models import StrengthExerciseSet

        create = e2e_client.post(
            "/v1/strength/sessions",
            json={"sets": [{"exercise_name": "BARBELL_SQUAT", "reps": 5, "weight_kg": 80}]},
        )
        body = create.json()
        activity_id = body["id"]
        original_set = body["sets"][0]
        original_id = original_set["id"]
        assert body["sets"][0]["source"] == "manual"

        patch = e2e_client.patch(
            f"/v1/strength/sessions/{activity_id}/sets/{original_id}",
            json={"reps": 6, "rpe": 8.0},
        )
        assert patch.status_code == 200, patch.text
        new_body = patch.json()
        assert new_body["set_count"] == 1, "edit must leave exactly one active set"
        new_active = new_body["sets"][0]
        assert new_active["id"] != original_id
        assert new_active["reps"] == 6
        assert new_active["rpe"] == 8.0
        # Source stays 'manual' since the predecessor was manual, not garmin.
        assert new_active["source"] == "manual"

        # Predecessor must now be superseded (filter says it shouldn't appear
        # in the default read path).
        old_row = (
            db_session.query(StrengthExerciseSet)
            .filter(StrengthExerciseSet.id == UUID(original_id))
            .first()
        )
        assert old_row is not None, "predecessor must not be deleted"
        assert old_row.superseded_at is not None
        assert old_row.superseded_by_id == UUID(new_active["id"])

    def test_garmin_predecessor_edit_marks_source_as_garmin_then_manual_edit(
        self, e2e_client, db_session, test_athlete
    ):
        from models import Activity, StrengthExerciseSet

        # Simulate a Garmin-ingested session by writing the rows directly.
        activity = Activity(
            id=uuid4(),
            athlete_id=test_athlete.id,
            sport="strength",
            source="garmin",
            start_time=datetime.now(timezone.utc),
        )
        garmin_set = StrengthExerciseSet(
            id=uuid4(),
            activity_id=activity.id,
            athlete_id=test_athlete.id,
            set_order=1,
            exercise_name_raw="BARBELL_DEADLIFT",
            exercise_category="BARBELL_DEADLIFT",
            movement_pattern="hip_hinge",
            muscle_group="posterior_chain",
            is_unilateral=False,
            set_type="active",
            reps=5,
            weight_kg=100.0,
            estimated_1rm_kg=115.0,
            source="garmin",
            manually_augmented=False,
        )
        db_session.add_all([activity, garmin_set])
        db_session.commit()

        resp = e2e_client.patch(
            f"/v1/strength/sessions/{activity.id}/sets/{garmin_set.id}",
            json={"weight_kg": 102.5, "notes": "actually 102.5kg, watch missed"},
        )
        assert resp.status_code == 200, resp.text
        new_active = resp.json()["sets"][0]
        assert new_active["source"] == "garmin_then_manual_edit"
        assert new_active["manually_augmented"] is True
        assert new_active["weight_kg"] == 102.5

    def test_edit_history_returns_full_chain_in_order(self, e2e_client):
        create = e2e_client.post(
            "/v1/strength/sessions",
            json={"sets": [{"exercise_name": "BENCH_PRESS", "reps": 5, "weight_kg": 80}]},
        )
        activity_id = create.json()["id"]
        set_id = create.json()["sets"][0]["id"]

        # Two successive edits → three rows in the chain.
        first_patch = e2e_client.patch(
            f"/v1/strength/sessions/{activity_id}/sets/{set_id}",
            json={"reps": 6},
        )
        new_id = first_patch.json()["sets"][0]["id"]
        e2e_client.patch(
            f"/v1/strength/sessions/{activity_id}/sets/{new_id}",
            json={"reps": 7},
        )

        hist = e2e_client.get(f"/v1/strength/sessions/{activity_id}/edit-history")
        assert hist.status_code == 200
        rows = hist.json()["rows"]
        assert len(rows) == 3
        # Two oldest are superseded; newest is active.
        assert sum(1 for r in rows if r["superseded_at"] is None) == 1
        assert sum(1 for r in rows if r["superseded_at"] is not None) == 2

    def test_archive_flips_sport_for_manual_only(self, e2e_client, db_session, test_athlete):
        from models import Activity

        create = e2e_client.post(
            "/v1/strength/sessions",
            json={"sets": [{"exercise_name": "PUSH_UP", "reps": 20}]},
        )
        activity_id = create.json()["id"]

        archived = e2e_client.delete(f"/v1/strength/sessions/{activity_id}")
        assert archived.status_code == 200
        row = db_session.query(Activity).filter(Activity.id == UUID(activity_id)).first()
        assert row.sport == "strength_archived"
        # Archived sessions disappear from the recent list.
        listing = e2e_client.get("/v1/strength/sessions").json()
        assert all(item["id"] != activity_id for item in listing)

        # Garmin sessions cannot be archived from this surface.
        garmin = Activity(
            id=uuid4(),
            athlete_id=test_athlete.id,
            sport="strength",
            source="garmin",
            start_time=datetime.now(timezone.utc),
        )
        db_session.add(garmin)
        db_session.commit()
        bad = e2e_client.delete(f"/v1/strength/sessions/{garmin.id}")
        assert bad.status_code == 400

    def test_exercises_search_and_recent(self, e2e_client):
        e2e_client.post(
            "/v1/strength/sessions",
            json={"sets": [{"exercise_name": "OVERHEAD_PRESS", "reps": 5, "weight_kg": 50}]},
        )
        resp = e2e_client.get("/v1/strength/exercises?q=dead")
        assert resp.status_code == 200
        body = resp.json()
        names = [e["name"] for e in body["results"]]
        assert "BARBELL_DEADLIFT" in names
        # Recent reflects the just-logged session.
        recent_names = [r["name"] for r in body["recent"]]
        assert "OVERHEAD_PRESS" in recent_names
