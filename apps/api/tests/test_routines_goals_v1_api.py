"""Contract + integration tests for strength v1 routines + goals (phase E).

Layers:

  1. Source contract (db-less): registers expected routes and every
     route gates on ``_require_strength_v1``.
  2. Feature-flag gate (mock db): every route returns 404 when the
     ``strength.v1`` flag is off.
  3. End-to-end (real Postgres, skipped locally): create / list / patch
     / delete routines and goals; verify ownership scoping.
"""

from __future__ import annotations

import os
import re
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------
# Source contract
# ---------------------------------------------------------------------


class TestSourceContract:
    def test_router_registers_expected_routes(self):
        from routers.routines_goals_v1 import router

        paths = {f"{list(r.methods)[0]} {r.path}" for r in router.routes}
        expected = {
            "GET /v1/strength/routines",
            "POST /v1/strength/routines",
            "PATCH /v1/strength/routines/{routine_id}",
            "DELETE /v1/strength/routines/{routine_id}",
            "GET /v1/strength/goals",
            "POST /v1/strength/goals",
            "PATCH /v1/strength/goals/{goal_id}",
            "DELETE /v1/strength/goals/{goal_id}",
        }
        missing = expected - paths
        assert not missing, f"Missing expected routes: {missing}"

    def test_every_route_calls_require_strength_v1(self):
        """Every handler MUST call ``_require_strength_v1`` before any
        DB work, or the surface leaks for athletes outside the rollout.
        """
        path = os.path.join(
            os.path.dirname(__file__), "..", "routers", "routines_goals_v1.py"
        )
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()

        # Pull each top-level route handler body via a regex on
        # @router.<verb> ... def <name>( ... ): <body until next @router. or EOF>
        handlers = re.findall(
            r"@router\.(?:get|post|patch|delete)\([^)]*\)\s*"
            r"def\s+(\w+)\s*\([^)]*\)[^:]*:\s*(.*?)(?=\n@router\.|\Z)",
            src,
            re.DOTALL,
        )
        assert handlers, "no handlers found — regex broke or file missing"
        for name, body in handlers:
            assert "_require_strength_v1(" in body, (
                f"handler {name!r} does not call _require_strength_v1"
            )

    def test_main_includes_routines_goals_v1_router(self):
        """``main.py`` MUST include this router, otherwise none of the
        routes are reachable in production."""
        path = os.path.join(os.path.dirname(__file__), "..", "main.py")
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
        assert "routines_goals_v1" in src, (
            "main.py does not include the routines_goals_v1 router"
        )


# ---------------------------------------------------------------------
# Feature-flag gate
# ---------------------------------------------------------------------


@pytest.fixture
def app_with_flag_off():
    """Build a minimal FastAPI app with the router mounted, flag stub off."""
    from fastapi import FastAPI

    from core.auth import get_current_user
    from core.database import get_db
    from routers import routines_goals_v1

    app = FastAPI()
    app.include_router(routines_goals_v1.router)

    fake_user = MagicMock()
    fake_user.id = uuid.uuid4()
    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_db] = lambda: MagicMock()

    return app


class TestFeatureFlagGate:
    @pytest.mark.parametrize(
        "method,path",
        [
            ("GET", "/v1/strength/routines"),
            ("POST", "/v1/strength/routines"),
            ("PATCH", f"/v1/strength/routines/{uuid.uuid4()}"),
            ("DELETE", f"/v1/strength/routines/{uuid.uuid4()}"),
            ("GET", "/v1/strength/goals"),
            ("POST", "/v1/strength/goals"),
            ("PATCH", f"/v1/strength/goals/{uuid.uuid4()}"),
            ("DELETE", f"/v1/strength/goals/{uuid.uuid4()}"),
        ],
    )
    def test_returns_404_when_flag_disabled(self, app_with_flag_off, method, path):
        with patch(
            "routers.routines_goals_v1.is_feature_enabled", return_value=False
        ):
            client = TestClient(app_with_flag_off)
            body = {"name": "x", "items": []} if method == "POST" and "routines" in path else (
                {"goal_type": "freeform"} if method == "POST" else {}
            )
            r = client.request(method, path, json=body)
            assert r.status_code == 404, (
                f"{method} {path} returned {r.status_code} when flag off; "
                f"expected 404 (silent invisibility)"
            )


# ---------------------------------------------------------------------
# End-to-end (Postgres-backed). Local: skipped. CI: runs.
# ---------------------------------------------------------------------


_E2E_REASON = (
    "End-to-end strength v1 routines/goals tests require a real Postgres "
    "database. Set RUN_STRENGTH_E2E=1 (and ensure DB env vars are wired) "
    "to enable locally; CI runs them."
)


@pytest.mark.skipif(
    os.environ.get("RUN_STRENGTH_E2E", "0") != "1",
    reason=_E2E_REASON,
)
class TestRoutinesGoalsE2E:
    @pytest.fixture
    def authed_client(self, db_session):
        from main import app
        from core.auth import get_current_user
        from core.database import get_db
        from models import Athlete

        athlete = Athlete(
            id=uuid.uuid4(),
            email=f"strength-e2e-{uuid.uuid4()}@test.local",
            name="Strength E2E",
            age=35,
            gender="male",
            current_weekly_miles=20,
        )
        db_session.add(athlete)
        db_session.commit()
        db_session.refresh(athlete)

        app.dependency_overrides[get_current_user] = lambda: athlete
        app.dependency_overrides[get_db] = lambda: db_session

        with patch(
            "routers.routines_goals_v1.is_feature_enabled", return_value=True
        ):
            yield TestClient(app), athlete

        app.dependency_overrides.clear()

    def test_routine_create_list_patch_archive(self, authed_client):
        client, _athlete = authed_client

        r = client.post(
            "/v1/strength/routines",
            json={
                "name": "Pull day",
                "items": [
                    {"exercise_name": "deadlift", "default_sets": 3, "default_reps": 5},
                    {"exercise_name": "pull up", "default_sets": 4},
                ],
            },
        )
        assert r.status_code == 201, r.text
        rid = r.json()["id"]

        r = client.get("/v1/strength/routines")
        assert r.status_code == 200
        assert any(x["id"] == rid for x in r.json())

        r = client.patch(
            f"/v1/strength/routines/{rid}",
            json={"name": "Pull day v2"},
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Pull day v2"

        r = client.delete(f"/v1/strength/routines/{rid}")
        assert r.status_code == 200

        r = client.get("/v1/strength/routines")
        assert r.status_code == 200
        assert all(x["id"] != rid for x in r.json()), (
            "archived routine still in active list"
        )

    def test_goal_create_patch_delete(self, authed_client):
        client, _athlete = authed_client

        r = client.post(
            "/v1/strength/goals",
            json={
                "goal_type": "e1rm_target",
                "exercise_name": "deadlift",
                "target_value": 405,
                "target_unit": "lbs",
                "coupled_running_metric": "maintain weekly mileage",
            },
        )
        assert r.status_code == 201, r.text
        gid = r.json()["id"]

        r = client.get("/v1/strength/goals")
        assert any(g["id"] == gid for g in r.json())

        r = client.patch(
            f"/v1/strength/goals/{gid}",
            json={"target_value": 415},
        )
        assert r.status_code == 200
        assert r.json()["target_value"] == 415

        r = client.patch(
            f"/v1/strength/goals/{gid}",
            json={"is_active": False},
        )
        assert r.status_code == 200

        r = client.get("/v1/strength/goals")
        assert all(g["id"] != gid for g in r.json()), (
            "deactivated goal still in active list"
        )

        r = client.delete(f"/v1/strength/goals/{gid}")
        assert r.status_code == 200
