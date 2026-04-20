"""Phase D contract + integration tests for the symptom log API.

Mirrors ``test_strength_v1_api.py`` layout:

1. Source contract (db-less): the four expected routes are registered
   and every endpoint gates on ``_require_strength_v1``.
2. Feature-flag gate (mock db): when ``strength.v1`` is off for the
   athlete, every route returns 404 (not 403, not 401 — invisible).
3. End-to-end (real Postgres, skipped locally): exercises create /
   list (active vs history) / patch (resolved_at validation) /
   delete against the actual schema.
"""

from __future__ import annotations

import os
import re
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------
# 1. Source contract (db-less)
# ---------------------------------------------------------------------


class TestSourceContract:
    def test_router_registers_expected_routes(self):
        from routers import symptoms_v1 as mod

        paths = {(tuple(sorted(r.methods)), r.path) for r in mod.router.routes}
        expected = {
            (("GET",), "/v1/symptoms"),
            (("POST",), "/v1/symptoms"),
            (("PATCH",), "/v1/symptoms/{symptom_id}"),
            (("DELETE",), "/v1/symptoms/{symptom_id}"),
        }
        missing = expected - paths
        assert not missing, f"router missing routes: {missing}"

    def test_every_route_calls_require_strength_v1(self):
        path = (
            Path(__file__).resolve().parents[1]
            / "routers"
            / "symptoms_v1.py"
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
                "every symptom v1 route must be invisible when the flag is off"
            )

    def test_main_includes_router(self):
        path = (
            Path(__file__).resolve().parents[1] / "main.py"
        )
        text = path.read_text(encoding="utf-8")
        assert "from routers import symptoms_v1" in text, (
            "main.py must conditionally include symptoms_v1 router"
        )


# ---------------------------------------------------------------------
# 2. Feature-flag gate (mock db)
# ---------------------------------------------------------------------


@pytest.fixture
def flag_off_client(monkeypatch):
    from main import app
    from core.auth import get_current_user
    from core.database import get_db
    import routers.symptoms_v1 as mod

    athlete = MagicMock()
    athlete.id = uuid4()
    mock_db = MagicMock()

    monkeypatch.setattr(mod, "is_feature_enabled", lambda *a, **kw: False)

    app.dependency_overrides[get_current_user] = lambda: athlete
    app.dependency_overrides[get_db] = lambda: iter([mock_db])
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.clear()


class TestFeatureFlagGate:
    def test_get_returns_404_when_flag_off(self, flag_off_client):
        resp = flag_off_client.get("/v1/symptoms")
        assert resp.status_code == 404

    def test_post_returns_404_when_flag_off(self, flag_off_client):
        resp = flag_off_client.post(
            "/v1/symptoms",
            json={
                "body_area": "left_calf",
                "severity": "niggle",
                "started_at": str(date.today()),
            },
        )
        assert resp.status_code == 404

    def test_patch_returns_404_when_flag_off(self, flag_off_client):
        resp = flag_off_client.patch(
            f"/v1/symptoms/{uuid4()}",
            json={"resolved_at": str(date.today())},
        )
        assert resp.status_code == 404

    def test_delete_returns_404_when_flag_off(self, flag_off_client):
        resp = flag_off_client.delete(f"/v1/symptoms/{uuid4()}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------
# 3. End-to-end (real Postgres)
# ---------------------------------------------------------------------


pytestmark_e2e = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="end-to-end tests require DATABASE_URL (CI provides one)",
)


@pytest.fixture
def e2e_client():
    """TestClient with strength.v1 forced ON for a synthetic athlete."""
    from main import app
    from core.auth import get_current_user
    from core.database import get_db, SessionLocal
    from models import Athlete
    import routers.symptoms_v1 as mod

    db = SessionLocal()
    try:
        athlete = (
            db.query(Athlete)
            .filter(Athlete.email == "symptoms_v1_e2e@strideiq.test")
            .first()
        )
        if not athlete:
            athlete = Athlete(
                email="symptoms_v1_e2e@strideiq.test",
                hashed_password="x",
                name="symptoms v1 e2e",
            )
            db.add(athlete)
            db.commit()
            db.refresh(athlete)

        original_flag = mod.is_feature_enabled
        mod.is_feature_enabled = lambda *a, **kw: True  # type: ignore[assignment]
        app.dependency_overrides[get_current_user] = lambda: athlete
        app.dependency_overrides[get_db] = lambda: iter([SessionLocal()])
        try:
            yield TestClient(app, raise_server_exceptions=False), athlete
        finally:
            app.dependency_overrides.clear()
            mod.is_feature_enabled = original_flag  # type: ignore[assignment]
    finally:
        db.close()


@pytestmark_e2e
class TestEndToEnd:
    def test_create_then_list_returns_active_then_resolved(self, e2e_client):
        client, athlete = e2e_client
        today = date.today()

        r1 = client.post(
            "/v1/symptoms",
            json={
                "body_area": "left_calf",
                "severity": "niggle",
                "started_at": str(today - timedelta(days=2)),
                "triggered_by": "after long run",
            },
        )
        assert r1.status_code == 201, r1.text
        sym_id = r1.json()["id"]

        listing = client.get("/v1/symptoms").json()
        active_ids = {s["id"] for s in listing["active"]}
        assert sym_id in active_ids
        history_ids = {s["id"] for s in listing["history"]}
        assert sym_id not in history_ids

        # Resolve it.
        r2 = client.patch(
            f"/v1/symptoms/{sym_id}",
            json={"resolved_at": str(today)},
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["resolved_at"] == str(today)

        listing2 = client.get("/v1/symptoms").json()
        assert sym_id not in {s["id"] for s in listing2["active"]}
        assert sym_id in {s["id"] for s in listing2["history"]}

        # Cleanup.
        assert (
            client.delete(f"/v1/symptoms/{sym_id}").status_code == 200
        )

    def test_resolved_at_before_started_at_is_400(self, e2e_client):
        client, _ = e2e_client
        today = date.today()
        r = client.post(
            "/v1/symptoms",
            json={
                "body_area": "right_knee",
                "severity": "ache",
                "started_at": str(today),
                "resolved_at": str(today - timedelta(days=1)),
            },
        )
        assert r.status_code == 400
