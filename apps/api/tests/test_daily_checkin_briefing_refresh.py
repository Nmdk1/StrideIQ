"""
Tests for check-in -> briefing refresh contract (builder note 2026-02-24).
Hotfix tests added 2026-02-24: force-enqueue bypass of cooldown.

Required coverage:
  1. _trigger_briefing_refresh calls mark_briefing_dirty + enqueue_briefing_refresh (unit)
  2. _trigger_briefing_refresh covers both create and update paths via endpoint wiring (unit + DB-backed)
  3. If dirty/enqueue helpers throw, _trigger_briefing_refresh never raises (unit)
  4. mark_briefing_dirty removes payload key (unit, see also TestMarkBriefingDirtyUnit)
  5. mark_briefing_dirty no-ops when Redis unavailable/errors (unit)
  6. force=False + cooldown => skip (hotfix)
  7. force=True + cooldown + closed circuit => enqueue (hotfix)
  8. force=True + open circuit => block (hotfix)

Tests 1-5 and 6-8 are pure-unit (no DB required).
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
        self._ttls: dict = {}

    def get(self, key):
        return self._store.get(key)

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self._store:
            return False
        self._store[key] = value
        if ex:
            self._ttls[key] = ex
        return True

    def setex(self, key, ttl, value):
        self._store[key] = value
        self._ttls[key] = ttl

    def exists(self, key):
        return key in self._store

    def delete(self, *keys):
        for k in keys:
            self._store.pop(k, None)
            self._ttls.pop(k, None)

    def incr(self, key):
        val = int(self._store.get(key, 0)) + 1
        self._store[key] = str(val)
        return val

    def expire(self, key, ttl):
        self._ttls[key] = ttl

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

        mock_enq.assert_called_once_with(athlete_id, force=True)

    def test_calls_enqueue_with_force_true(self):
        """Test 1d: _trigger_briefing_refresh always passes force=True."""
        from routers.daily_checkin import _trigger_briefing_refresh

        athlete_id = str(uuid4())
        with patch("services.home_briefing_cache.mark_briefing_dirty"), \
             patch("tasks.home_briefing_tasks.enqueue_briefing_refresh") as mock_enq:
            _trigger_briefing_refresh(athlete_id)

        args, kwargs = mock_enq.call_args
        force_value = kwargs.get("force", args[1] if len(args) > 1 else None)
        assert force_value is True, \
            f"_trigger_briefing_refresh must pass force=True, got force={force_value}"

    def test_calls_dirty_before_enqueue(self):
        """Test 1c: mark_briefing_dirty is called before enqueue_briefing_refresh."""
        from routers.daily_checkin import _trigger_briefing_refresh

        athlete_id = str(uuid4())
        call_order = []

        with patch("services.home_briefing_cache.mark_briefing_dirty",
                   side_effect=lambda _: call_order.append("dirty")), \
             patch("tasks.home_briefing_tasks.enqueue_briefing_refresh",
                   side_effect=lambda *a, **kw: call_order.append("enqueue")):
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

        mock_enq.assert_called_once_with(athlete_id, force=True)

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
        fake_r._store[_cache_key(athlete_id)] = '{"payload": "old"}'
        fake_r._store[_lock_key(athlete_id)] = "1"
        fake_r._store[_cooldown_key(athlete_id)] = "1"
        fake_r._store[_circuit_key(athlete_id)] = "2"

        with patch("services.home_briefing_cache.get_redis_client", return_value=fake_r):
            mark_briefing_dirty(athlete_id)

        assert not fake_r.exists(_cache_key(athlete_id)), "payload key must be deleted"
        assert fake_r.exists(_lock_key(athlete_id)), "lock must survive"
        assert fake_r.exists(_cooldown_key(athlete_id)), "cooldown must survive"
        assert fake_r.exists(_circuit_key(athlete_id)), "circuit must survive"

    def test_swallows_redis_exception(self):
        """Test 5: Redis exception during delete is caught; function returns cleanly."""
        from services.home_briefing_cache import mark_briefing_dirty

        athlete_id = str(uuid4())
        broken = MagicMock()
        broken.delete.side_effect = ConnectionError("Redis down")

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
                        "readiness_1_5": 4,
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
            readiness_1_5=2,
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
                        "readiness_1_5": 4,
                        "sleep_quality_1_5": 3,
                    })
            assert resp.status_code == 201, f"Expected 201: {resp.status_code} {resp.text}"
            mock_trigger.assert_called_once_with(str(test_athlete.id))
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)


# ===========================================================================
# Tests 6-8: Force-enqueue behavior (hotfix 2026-02-24)
# ===========================================================================

class TestForceEnqueueBehavior:
    """
    Tests 6-8: force path behavior in enqueue_briefing_refresh.

    6. force=False + cooldown present => enqueue skipped
    7. force=True + cooldown present + circuit closed => enqueue allowed
    8. force=True + circuit open => enqueue blocked
    """

    def test_force_false_with_cooldown_skips(self):
        """Test 6: normal call is blocked when cooldown key exists."""
        from tasks.home_briefing_tasks import enqueue_briefing_refresh
        from services.home_briefing_cache import _cooldown_key

        athlete_id = str(uuid4())
        fake_r = FakeRedis()
        fake_r.setex(_cooldown_key(athlete_id), 60, "1")  # cooldown active

        with patch("services.home_briefing_cache.get_redis_client", return_value=fake_r), \
             patch("tasks.home_briefing_tasks.generate_home_briefing_task") as mock_task:
            result = enqueue_briefing_refresh(athlete_id, force=False)

        assert result is False, "force=False + cooldown must skip enqueue"
        mock_task.apply_async.assert_not_called()

    def test_force_true_with_cooldown_skips_for_normal_priority(self):
        """Test 7: force=True still honors cooldown for normal-priority traffic."""
        from tasks.home_briefing_tasks import enqueue_briefing_refresh
        from services.home_briefing_cache import _cooldown_key

        athlete_id = str(uuid4())
        fake_r = FakeRedis()
        fake_r.setex(_cooldown_key(athlete_id), 60, "1")  # cooldown active; circuit closed

        with patch("services.home_briefing_cache.get_redis_client", return_value=fake_r), \
             patch("tasks.home_briefing_tasks.generate_home_briefing_task") as mock_task:
            result = enqueue_briefing_refresh(athlete_id, force=True)

        assert result is False, "force=True + cooldown + normal priority must skip enqueue"
        mock_task.apply_async.assert_not_called()

    def test_force_true_with_cooldown_enqueues_for_high_priority(self):
        """force=True bypasses cooldown only for high-priority user-blocking refreshes."""
        from tasks.home_briefing_tasks import enqueue_briefing_refresh
        from services.home_briefing_cache import _cooldown_key

        athlete_id = str(uuid4())
        fake_r = FakeRedis()
        fake_r.setex(_cooldown_key(athlete_id), 60, "1")

        with patch("services.home_briefing_cache.get_redis_client", return_value=fake_r), \
             patch("tasks.home_briefing_tasks.generate_home_briefing_task") as mock_task:
            result = enqueue_briefing_refresh(athlete_id, force=True, priority="high")

        assert result is True
        mock_task.apply_async.assert_called_once_with(args=[athlete_id], queue="briefing_high")

    def test_force_true_with_open_circuit_blocks(self):
        """Test 8: force=True is still blocked when circuit is open."""
        from tasks.home_briefing_tasks import enqueue_briefing_refresh
        from services.home_briefing_cache import _circuit_key, CIRCUIT_FAILURE_THRESHOLD

        athlete_id = str(uuid4())
        fake_r = FakeRedis()
        # Open the circuit: write failure count >= threshold
        fake_r._store[_circuit_key(athlete_id)] = str(CIRCUIT_FAILURE_THRESHOLD)

        with patch("services.home_briefing_cache.get_redis_client", return_value=fake_r), \
             patch("tasks.home_briefing_tasks.generate_home_briefing_task") as mock_task:
            result = enqueue_briefing_refresh(athlete_id, force=True)

        assert result is False, "force=True + open circuit must still block enqueue"
        mock_task.apply_async.assert_not_called()

    def test_force_probe_with_open_circuit_enqueues(self):
        """force + probe mode bypasses open circuit for data-change recovery."""
        from tasks.home_briefing_tasks import enqueue_briefing_refresh
        from services.home_briefing_cache import _circuit_key, CIRCUIT_FAILURE_THRESHOLD

        athlete_id = str(uuid4())
        fake_r = FakeRedis()
        fake_r._store[_circuit_key(athlete_id)] = str(CIRCUIT_FAILURE_THRESHOLD)

        with patch("services.home_briefing_cache.get_redis_client", return_value=fake_r), \
             patch("tasks.home_briefing_tasks.generate_home_briefing_task") as mock_task:
            result = enqueue_briefing_refresh(
                athlete_id,
                force=True,
                allow_circuit_probe=True,
            )

        assert result is True
        mock_task.apply_async.assert_called_once_with(args=[athlete_id], queue="briefing")

    def test_force_true_sets_cooldown_after_enqueue(self):
        """Test 7b: force path sets cooldown after enqueuing (prevents burst)."""
        from tasks.home_briefing_tasks import enqueue_briefing_refresh
        from services.home_briefing_cache import _cooldown_key

        athlete_id = str(uuid4())
        fake_r = FakeRedis()

        with patch("services.home_briefing_cache.get_redis_client", return_value=fake_r), \
             patch("tasks.home_briefing_tasks.generate_home_briefing_task"):
            enqueue_briefing_refresh(athlete_id, force=True)

        assert fake_r.exists(_cooldown_key(athlete_id)), \
            "force enqueue must set cooldown to prevent immediate re-trigger"

    def test_is_circuit_open_returns_false_when_circuit_closed(self):
        """Test: is_circuit_open helper returns False when no failures recorded."""
        from services.home_briefing_cache import is_circuit_open

        athlete_id = str(uuid4())
        fake_r = FakeRedis()

        with patch("services.home_briefing_cache.get_redis_client", return_value=fake_r):
            result = is_circuit_open(athlete_id)

        assert result is False

    def test_is_circuit_open_returns_true_when_circuit_open(self):
        """Test: is_circuit_open helper returns True when failure threshold is met."""
        from services.home_briefing_cache import is_circuit_open, _circuit_key, CIRCUIT_FAILURE_THRESHOLD

        athlete_id = str(uuid4())
        fake_r = FakeRedis()
        fake_r._store[_circuit_key(athlete_id)] = str(CIRCUIT_FAILURE_THRESHOLD)

        with patch("services.home_briefing_cache.get_redis_client", return_value=fake_r):
            result = is_circuit_open(athlete_id)

        assert result is True
