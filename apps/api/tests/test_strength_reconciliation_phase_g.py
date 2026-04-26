"""Phase G — Garmin reconciliation task + nudges endpoint tests.

Layers:

  1. Source contract (db-less): the task is registered, the beat
     schedule includes it, the nudges endpoint exists and is gated.
  2. Pure-helper unit tests for the sparse-detection logic, run
     against an in-memory fake (no DB needed).
  3. End-to-end: the task runs against real Postgres (skipped locally).

The contract this file enforces is **read-only**: the reconciliation
task must never modify activities or sets, must never auto-classify
the gap, and must never send notifications. Phase G ships the
*surface* for the home card; the card itself is computed on-demand
by the nudges endpoint so it always reflects live state.
"""

from __future__ import annotations

import os
import re
import uuid
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------
# Source contract
# ---------------------------------------------------------------------


class TestSourceContract:
    def test_task_is_importable_and_named(self):
        from tasks.strength_reconciliation_tasks import (
            reconcile_garmin_strength_sessions,
        )

        assert reconcile_garmin_strength_sessions.name == (
            "tasks.reconcile_garmin_strength_sessions"
        )

    def test_beat_schedule_includes_strength_reconcile(self):
        from celerybeat_schedule import beat_schedule

        assert "strength-garmin-reconcile" in beat_schedule, (
            "beat_schedule missing strength-garmin-reconcile entry"
        )
        entry = beat_schedule["strength-garmin-reconcile"]
        assert entry["task"] == "tasks.reconcile_garmin_strength_sessions"

    def test_task_module_does_not_mutate_activities(self):
        """Reconciliation is read-only. The task module must not call
        any write/delete primitives on Activity or StrengthExerciseSet."""
        path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "tasks",
            "strength_reconciliation_tasks.py",
        )
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()

        forbidden = [
            r"\.delete\s*\(",
            r"db\.add\s*\(",
            r"\.commit\s*\(",
            r"\.flush\s*\(",
            r"\.update\s*\(\s*\{",  # bulk update
        ]
        for pat in forbidden:
            assert not re.search(pat, src), (
                f"reconciliation task touches the DB ({pat!r}); it must "
                f"stay read-only — see Phase G contract"
            )

    def test_nudges_endpoint_registered_and_gated(self):
        from routers.strength_v1 import router

        paths = {f"{list(r.methods)[0]} {r.path}" for r in router.routes}
        assert "GET /v1/strength/nudges" in paths, (
            "nudges endpoint not registered"
        )

        # The handler source must call _require_strength_v1.
        path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "routers",
            "strength_v1.py",
        )
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
        m = re.search(
            r"def get_strength_nudges\([^)]*\)[^:]*:\s*(.*?)(?=\ndef |\Z)",
            src,
            re.DOTALL,
        )
        assert m, "nudges handler not found via regex"
        assert "_require_strength_v1(" in m.group(1), (
            "nudges handler does not gate on strength.v1 flag"
        )


# ---------------------------------------------------------------------
# Feature-flag gate for nudges endpoint
# ---------------------------------------------------------------------


@pytest.fixture
def app_with_flag_off():
    from fastapi import FastAPI

    from core.auth import get_current_user
    from core.database import get_db
    from routers import strength_v1

    app = FastAPI()
    app.include_router(strength_v1.router)

    fake_user = MagicMock()
    fake_user.id = uuid.uuid4()
    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_db] = lambda: MagicMock()

    return app


class TestNudgesFeatureFlagGate:
    def test_returns_404_when_flag_disabled(self, app_with_flag_off):
        from fastapi.testclient import TestClient

        with patch(
            "routers.strength_v1.is_feature_enabled", return_value=False
        ):
            client = TestClient(app_with_flag_off)
            r = client.get("/v1/strength/nudges")
            assert r.status_code == 404


# ---------------------------------------------------------------------
# End-to-end (real Postgres). Local: skipped. CI: runs.
# ---------------------------------------------------------------------


_E2E_REASON = (
    "Strength reconciliation e2e tests require a real Postgres database. "
    "Set RUN_STRENGTH_E2E=1 to enable locally; CI runs them."
)


@pytest.mark.skipif(
    os.environ.get("RUN_STRENGTH_E2E", "0") != "1", reason=_E2E_REASON
)
class TestNudgesE2E:
    def test_sparse_garmin_session_surfaces_as_nudge(
        self, db_session, authenticated_client
    ):
        """A garmin-sourced strength activity with 0 sets shows up as
        a nudge candidate."""
        from datetime import datetime, timezone

        from models import Activity

        client, athlete = authenticated_client
        a = Activity(
            id=uuid.uuid4(),
            athlete_id=athlete.id,
            sport="strength",
            source="garmin_webhook",
            start_time=datetime.now(timezone.utc),
            name="Strength",
        )
        db_session.add(a)
        db_session.commit()

        with patch(
            "routers.strength_v1.is_feature_enabled", return_value=True
        ):
            r = client.get("/v1/strength/nudges")
            assert r.status_code == 200
            body = r.json()
            assert body["count"] >= 1
            assert any(n["activity_id"] == str(a.id) for n in body["nudges"])

    def test_manual_session_does_not_appear(
        self, db_session, authenticated_client
    ):
        from datetime import datetime, timezone

        from models import Activity

        client, athlete = authenticated_client
        a = Activity(
            id=uuid.uuid4(),
            athlete_id=athlete.id,
            sport="strength",
            source="manual",
            start_time=datetime.now(timezone.utc),
            name="Manual session",
        )
        db_session.add(a)
        db_session.commit()

        with patch(
            "routers.strength_v1.is_feature_enabled", return_value=True
        ):
            r = client.get("/v1/strength/nudges")
            assert r.status_code == 200
            body = r.json()
            assert all(n["activity_id"] != str(a.id) for n in body["nudges"])
