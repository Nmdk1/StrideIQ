"""
Regression tests for:
  1. next(get_db_sync()) crash in Celery tasks (morning voice / intelligence)
  2. Nested aggregate GroupingError in /v1/admin/metrics

Both bugs caused visible production regressions:
- Morning intelligence task crashed on every run with TypeError
- Admin metrics endpoint returned 500 on every call
"""
import pytest
from unittest.mock import MagicMock, patch, call
from types import GeneratorType

from core.database import get_db_sync


# ---------------------------------------------------------------------------
# Bug 1: get_db_sync() returns a Session directly, not a generator
# ---------------------------------------------------------------------------

class TestGetDbSyncIsNotGenerator:
    """
    get_db_sync() must return a Session directly.
    Any caller using next(get_db_sync()) would raise TypeError.
    This test locks in the direct-return contract.
    """

    def test_get_db_sync_returns_session_not_generator(self):
        from sqlalchemy.orm import Session
        session = get_db_sync()
        try:
            assert not isinstance(session, GeneratorType), (
                "get_db_sync() must return a Session directly. "
                "Callers must NOT use next() around it."
            )
            assert hasattr(session, "query"), "get_db_sync() must return a SQLAlchemy Session"
        finally:
            session.close()

    def test_next_on_get_db_sync_would_raise(self):
        """Confirm that wrapping in next() raises TypeError — so callers must not do it."""
        session = get_db_sync()
        try:
            with pytest.raises(TypeError):
                next(session)  # type: ignore[call-overload]
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Bug 1b: All task call sites use get_db_sync() directly (no next())
# ---------------------------------------------------------------------------

class TestTaskCallSitesDoNotUseNext:
    """
    Structural test: grep the task modules for next(get_db_sync()) patterns.
    This would have caught the bug before deployment.
    """

    def test_intelligence_tasks_no_next_get_db_sync(self):
        import ast, pathlib
        src = pathlib.Path("tasks/intelligence_tasks.py").read_text()
        assert "next(get_db_sync())" not in src, (
            "tasks/intelligence_tasks.py must not use next(get_db_sync()). "
            "Replace with get_db_sync() directly."
        )

    def test_digest_tasks_no_next_get_db_sync(self):
        import pathlib
        src = pathlib.Path("tasks/digest_tasks.py").read_text()
        assert "next(get_db_sync())" not in src, (
            "tasks/digest_tasks.py must not use next(get_db_sync()). "
            "Replace with get_db_sync() directly."
        )


# ---------------------------------------------------------------------------
# Bug 1c: run_morning_intelligence task acquires db without crashing
# ---------------------------------------------------------------------------

class TestRunMorningIntelligenceDbAcquisition:
    """
    run_morning_intelligence must reach the athlete-query stage.
    If db acquisition fails the task would crash before any athlete logic.
    """

    def test_morning_intelligence_db_acquired_successfully(self):
        from tasks.intelligence_tasks import run_morning_intelligence

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch("tasks.intelligence_tasks.get_db_sync", return_value=mock_db):
            with patch("tasks.intelligence_tasks._athletes_in_morning_window", return_value=[]):
                result = run_morning_intelligence()

        assert result["status"] in ("success", "skipped", "no_athletes", "ok")
        mock_db.close.assert_called_once()

    def test_run_intelligence_for_athlete_db_acquired_successfully(self):
        from tasks.intelligence_tasks import run_intelligence_for_athlete_task
        from uuid import uuid4

        mock_db = MagicMock()
        athlete_id = str(uuid4())

        with patch("tasks.intelligence_tasks.get_db_sync", return_value=mock_db):
            with patch("tasks.intelligence_tasks._run_intelligence_for_athlete",
                       return_value={"status": "ok"}):
                result = run_intelligence_for_athlete_task(athlete_id)

        assert result == {"status": "ok"}
        mock_db.close.assert_called_once()

    def test_refresh_living_fingerprint_db_acquired_successfully(self):
        from tasks.intelligence_tasks import refresh_living_fingerprint

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.distinct.return_value.all.return_value = []

        with patch("tasks.intelligence_tasks.get_db_sync", return_value=mock_db):
            result = refresh_living_fingerprint()

        assert result.get("refreshed") == 0
        mock_db.close.assert_called_once()


# ---------------------------------------------------------------------------
# Bug 2: /v1/admin/metrics nested aggregate crash
# ---------------------------------------------------------------------------

class TestAdminMetricsNonNested:
    """
    The original query used func.avg(func.count(...)) which Postgres rejects
    as a nested aggregate. The fix uses a raw SQL subquery.
    This test verifies the endpoint does not contain the broken ORM pattern.
    """

    def test_metrics_endpoint_no_nested_func_avg_count(self):
        import pathlib
        src = pathlib.Path("routers/admin.py").read_text()
        assert "func.avg(func.count(" not in src, (
            "routers/admin.py must not use func.avg(func.count(...)) — "
            "nested aggregates are rejected by Postgres. Use a subquery."
        )

    def test_admin_metrics_returns_200(self):
        """
        Admin metrics endpoint must return 200, not 500.
        """
        from fastapi.testclient import TestClient
        from main import app
        from core.security import create_access_token
        from core.database import SessionLocal
        from models import Athlete

        db = SessionLocal()
        try:
            admin = db.query(Athlete).filter(Athlete.role == "admin").first()
            if not admin:
                pytest.skip("No admin user in test database")
            token = create_access_token(
                data={"sub": str(admin.id), "email": admin.email, "role": admin.role}
            )
        finally:
            db.close()

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/v1/admin/metrics?days=30",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, (
            f"Admin metrics returned {resp.status_code}: {resp.text[:300]}"
        )
        body = resp.json()
        assert "avg_activities_per_user" in body.get("engagement", {}), (
            "Response must include avg_activities_per_user"
        )
