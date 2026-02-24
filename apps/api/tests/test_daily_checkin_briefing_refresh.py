"""
Tests for check-in -> briefing refresh contract (builder note 2026-02-24).

Required coverage:
  1. _trigger_briefing_refresh calls mark_briefing_dirty + enqueue_briefing_refresh (unit)
  2. _trigger_briefing_refresh covers both create and update paths via endpoint wiring (unit + DB-backed)
  3. If dirty/enqueue helpers throw, _trigger_briefing_refresh never raises (unit)
  4. mark_briefing_dirty removes payload key (unit, see also TestMarkBriefingDirtyUnit)
  5. mark_briefing_dirty no-ops when Redis unavailable/errors (unit)

Tests 1-3 and 4-5 are pure-unit (no DB required).
Tests ending in _with_db require a real PostgreSQL session via conftest fixtures.
"""
import os
import sys
from unittest.mock import MagicMock, patch, call
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


# ---------------------------------------------------------------------------
# FakeRedis (minimal, same pattern as test_home_briefing_cache.py)
# ---------------------------------------------------------------------------

class FakeRedis:
    def __init__(self):
        self._store: dict = {}

    def setex(self, key, ttl, value):
        self._store[key] = value

    def delete(self, *keys):
        for k in keys:
            self._store.pop(k, None)

    def exists(self, key):
        return key in self._store

    def ping(self):
        return True


# ===========================================================================
# Test 1 & 2: _trigger_briefing_refresh wires to correct helpers
# ===========================================================================

class TestTriggerBriefingRefreshUnit:
    """
    Test that _trigger_briefing_refresh calls both helpers.
    Both create and update paths call _trigger_briefing_refresh — testing
    the function directly covers the shared contract.
    """

    def test_calls_mark_dirty_with_athlete_id(self):
        """Test 1a: mark_briefing_dirty receives correct athlete_id."""
        from routers.daily_checkin import _trigger_briefing_refresh

        athlete_id = str(uuid4())
        with patch("services.home_briefing_cache.mark_briefing_dirty") as mock_dirty, \
             patch("tasks.home_briefing_tasks.enqueue_briefing_refresh"):
            _trigger_briefing_refresh(athlete_id)

        mock_dirty.assert_called_once_with(athlete_id)

    def test_calls_enqueue_with_athlete_id(self):
        """Test 1b: enqueue_briefing_refresh receives correct athlete_id."""
        from routers.daily_checkin import _trigger_briefing_refresh

        athlete_id = str(uuid4())
        with patch("services.home_briefing_cache.mark_briefing_dirty"), \
             patch("tasks.home_briefing_tasks.enqueue_briefing_refresh") as mock_enq:
            _trigger_briefing_refresh(athlete_id)

        mock_enq.assert_called_once_with(athlete_id)

    def test_calls_dirty_before_enqueue(self):
        """Test 1c: mark_briefing_dirty is called before enqueue_briefing_refresh."""
        from routers.daily_checkin import _trigger_briefing_refresh

        athlete_id = str(uuid4())
        call_order = []

        with patch("services.home_briefing_cache.mark_briefing_dirty",
                   side_effect=lambda _: call_order.append("dirty")), \
             patch("tasks.home_briefing_tasks.enqueue_briefing_refresh",
                   side_effect=lambda _: call_order.append("enqueue")):
            _trigger_briefing_refresh(athlete_id)

        assert call_order == ["dirty", "enqueue"], \
            f"Expected dirty before enqueue, got: {call_order}"


# ===========================================================================
# Test 3: Non-blocking — helpers throwing must not propagate
# ===========================================================================

class TestTriggerBriefingRefreshNonBlocking:
    """Test 3: _trigger_briefing_refresh is non-blocking even when helpers raise."""

    def test_mark_dirty_raising_does_not_propagate(self):
        """Test 3a: exception in mark_briefing_dirty is caught; function returns cleanly."""
        from routers.daily_checkin import _trigger_briefing_refresh

        athlete_id = str(uuid4())
        with patch("services.home_briefing_cache.mark_briefing_dirty",
                   side_effect=RuntimeError("Redis gone")), \
             patch("tasks.home_briefing_tasks.enqueue_briefing_refresh") as mock_enq:
            _trigger_briefing_refresh(athlete_id)  # Must not raise

        # enqueue must still be attempted even when dirty raised
        mock_enq.assert_called_once_with(athlete_id)

    def test_enqueue_raising_does_not_propagate(self):
        """Test 3b: exception in enqueue_briefing_refresh is caught; function returns cleanly."""
        from routers.daily_checkin import _trigger_briefing_refresh

        athlete_id = str(uuid4())
        with patch("services.home_briefing_cache.mark_briefing_dirty") as mock_dirty, \
             patch("tasks.home_briefing_tasks.enqueue_briefing_refresh",
                   side_effect=ConnectionError("Broker offline")):
            _trigger_briefing_refresh(athlete_id)  # Must not raise

        mock_dirty.assert_called_once_with(athlete_id)

    def test_both_raising_does_not_propagate(self):
        """Test 3c: both helpers raising; function still returns cleanly."""
        from routers.daily_checkin import _trigger_briefing_refresh

        athlete_id = str(uuid4())
        with patch("services.home_briefing_cache.mark_briefing_dirty",
                   side_effect=RuntimeError("dirty fail")), \
             patch("tasks.home_briefing_tasks.enqueue_briefing_refresh",
                   side_effect=RuntimeError("enqueue fail")):
            _trigger_briefing_refresh(athlete_id)  # Must not raise


# ===========================================================================
# Tests 4-5: mark_briefing_dirty unit tests
# ===========================================================================

class TestMarkBriefingDirtyUnit:
    """Tests 4-5: mark_briefing_dirty behaviour."""

    def test_removes_payload_key_when_present(self):
        """Test 4: deletes home_briefing:<id> when key exists."""
        from services.home_briefing_cache import mark_briefing_dirty, _cache_key

        athlete_id = str(uuid4())
        fake_r = FakeRedis()
        fake_r._store[_cache_key(athlete_id)] = '{"payload": "stale"}'

        with patch("services.home_briefing_cache.get_redis_client", return_value=fake_r):
            mark_briefing_dirty(athlete_id)

        assert not fake_r.exists(_cache_key(athlete_id)), \
            "mark_briefing_dirty must evict the payload key"

    def test_safe_when_key_absent(self):
        """Test 4b: no-op when key doesn't exist — no exception."""
        from services.home_briefing_cache import mark_briefing_dirty

        athlete_id = str(uuid4())
        fake_r = FakeRedis()

        with patch("services.home_briefing_cache.get_redis_client", return_value=fake_r):
            mark_briefing_dirty(athlete_id)  # Must not raise

    def test_does_not_delete_lock_or_cooldown_keys(self):
        """Test 4c: only the payload key is deleted; lock/cooldown/circuit survive."""
        from services.home_briefing_cache import (
            mark_briefing_dirty, _cache_key, _lock_key, _cooldown_key, _circuit_key,
        )

        athlete_id = str(uuid4())
        fake_r = FakeRedis()
        fake_r._store[_cache_key(athlete_id)] = '{"payload": "stale"}'
        fake_r._store[_lock_key(athlete_id)] = "1"
        fake_r._store[_cooldown_key(athlete_id)] = "1"
        fake_r._store[_circuit_key(athlete_id)] = "2"

        with patch("services.home_briefing_cache.get_redis_client", return_value=fake_r):
            mark_briefing_dirty(athlete_id)

        assert not fake_r.exists(_cache_key(athlete_id)), "payload key must be gone"
        assert fake_r.exists(_lock_key(athlete_id)), "lock key must survive"
        assert fake_r.exists(_cooldown_key(athlete_id)), "cooldown key must survive"
        assert fake_r.exists(_circuit_key(athlete_id)), "circuit key must survive"

    def test_swallows_redis_exception(self):
        """Test 5: Redis error during delete is caught; no exception raised."""
        from services.home_briefing_cache import mark_briefing_dirty

        athlete_id = str(uuid4())
        broken = MagicMock()
        broken.delete.side_effect = ConnectionError("Redis unreachable")

        with patch("services.home_briefing_cache.get_redis_client", return_value=broken):
            mark_briefing_dirty(athlete_id)  # Must not raise

    def test_no_ops_when_redis_client_is_none(self):
        """Test 5b: returns cleanly when get_redis_client() returns None."""
        from services.home_briefing_cache import mark_briefing_dirty

        athlete_id = str(uuid4())
        with patch("services.home_briefing_cache.get_redis_client", return_value=None):
            mark_briefing_dirty(athlete_id)  # Must not raise


# ===========================================================================
# DB-backed wiring tests (require real Postgres via conftest)
# ===========================================================================

class TestEndpointWiringWithDB:
    """
    Integration tests: verify the actual HTTP endpoint calls _trigger_briefing_refresh.
    Skipped automatically when DB is unavailable (outside Docker).
    """

    def test_create_path_calls_trigger(self, db_session, test_athlete):
        """Test 1 (DB): POST /v1/daily-checkin (new) calls _trigger_briefing_refresh."""
        try:
            from fastapi.testclient import TestClient
            from main import app
            from core.database import get_db
            from core.auth import get_current_user
            import routers.daily_checkin as dc_mod
        except Exception:
            pytest.skip("App imports unavailable")

        app.dependency_overrides[get_current_user] = lambda: test_athlete
        app.dependency_overrides[get_db] = lambda: db_session
        try:
            with patch.object(dc_mod, "_trigger_briefing_refresh") as mock_trigger:
                mock_trigger.return_value = None
                with TestClient(app) as tc:
                    resp = tc.post("/v1/daily-checkin", json={
                        "date": "2026-02-24",
                        "motivation_1_5": 4,
                        "sleep_quality_1_5": 3,
                        "sleep_h": 7.0,
                        "soreness_1_5": 1,
                    })
            assert resp.status_code == 201, f"Expected 201: {resp.status_code} {resp.text}"
            mock_trigger.assert_called_once_with(str(test_athlete.id))
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)

    def test_update_path_calls_trigger(self, db_session, test_athlete):
        """Test 2 (DB): POST /v1/daily-checkin (existing) calls _trigger_briefing_refresh."""
        try:
            from fastapi.testclient import TestClient
            from main import app
            from core.database import get_db
            from core.auth import get_current_user
            from models import DailyCheckin
            from datetime import date
            import routers.daily_checkin as dc_mod
        except Exception:
            pytest.skip("App imports unavailable")

        # Pre-seed an existing check-in
        existing = DailyCheckin(
            athlete_id=test_athlete.id,
            date=date(2026, 2, 24),
            motivation_1_5=2,
        )
        db_session.add(existing)
        db_session.commit()

        app.dependency_overrides[get_current_user] = lambda: test_athlete
        app.dependency_overrides[get_db] = lambda: db_session
        try:
            with patch.object(dc_mod, "_trigger_briefing_refresh") as mock_trigger:
                mock_trigger.return_value = None
                with TestClient(app) as tc:
                    resp = tc.post("/v1/daily-checkin", json={
                        "date": "2026-02-24",
                        "motivation_1_5": 4,
                        "sleep_quality_1_5": 3,
                    })
            assert resp.status_code == 201, f"Expected 201: {resp.status_code} {resp.text}"
            mock_trigger.assert_called_once_with(str(test_athlete.id))
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)
