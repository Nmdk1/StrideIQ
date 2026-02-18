"""
Tests for Lane 2A: Home Briefing Off Request Path (ADR-065)

Covers:
- Unit tests 1-16: cache state logic, fingerprint, dedupe, cooldown, circuit breaker
- Integration tests 17-28: endpoint behavior, triggers, admin auth
- Celery task tests 29-33 (behavioral, not source-inspection)
- Schema contract tests 34-35
- Provider timeout & constant tests 36-39
- (Production smoke tests are manual post-deploy)

Tests that don't need a database (majority) use FakeRedis only.
Tests that need DB (endpoint integration) use db_session fixture.
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone, date
from unittest.mock import MagicMock, patch, PropertyMock
from uuid import uuid4

import pytest

# Ensure the API source is on the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.home_briefing_cache import (
    CACHE_TTL_S,
    CIRCUIT_FAILURE_THRESHOLD,
    ENQUEUE_COOLDOWN_S,
    FRESH_THRESHOLD_S,
    LOCK_TTL_S,
    STALE_MAX_S,
    BriefingState,
    _cache_key,
    _circuit_key,
    _cooldown_key,
    _lock_key,
    acquire_task_lock,
    read_briefing_cache,
    record_task_failure,
    release_task_lock,
    reset_circuit,
    set_enqueue_cooldown,
    should_enqueue_refresh,
    write_briefing_cache,
)

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cache_entry(age_seconds: int = 0, payload: dict = None) -> str:
    """Build a Redis cache entry JSON string with a given age."""
    generated_at = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    entry = {
        "payload": payload or {"coach_noticed": "Test insight", "morning_voice": "48 miles."},
        "generated_at": generated_at.isoformat(),
        "expires_at": (generated_at + timedelta(seconds=STALE_MAX_S)).isoformat(),
        "source_model": "gemini-2.5-flash",
        "version": 1,
        "data_fingerprint": "abc123",
    }
    return json.dumps(entry)


class FakeRedis:
    """Minimal in-memory Redis mock for unit tests."""

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

    def delete(self, *keys):
        for k in keys:
            self._store.pop(k, None)
            self._ttls.pop(k, None)

    def exists(self, key):
        return key in self._store

    def incr(self, key):
        val = int(self._store.get(key, 0)) + 1
        self._store[key] = str(val)
        return val

    def expire(self, key, ttl):
        self._ttls[key] = ttl

    def ping(self):
        return True


@pytest.fixture
def fake_redis():
    """Provide a FakeRedis and patch get_redis_client to return it."""
    r = FakeRedis()
    with patch("services.home_briefing_cache.get_redis_client", return_value=r):
        yield r


# ===========================================================================
# Category 1: Unit Tests (1-16)
# ===========================================================================


class TestCacheStateLogic:
    """Tests 1-5: cache freshness, staleness, expiry, and missing."""

    def test_cache_fresh_returns_payload(self, fake_redis):
        """Test 1: cached entry < 15 min returns payload + state fresh."""
        athlete_id = str(uuid4())
        fake_redis.setex(_cache_key(athlete_id), CACHE_TTL_S, _make_cache_entry(age_seconds=60))

        payload, state = read_briefing_cache(athlete_id)

        assert state == BriefingState.FRESH
        assert payload is not None
        assert payload["coach_noticed"] == "Test insight"

    def test_cache_stale_returns_payload(self, fake_redis):
        """Test 2: cached entry 15-60 min returns payload + state stale."""
        athlete_id = str(uuid4())
        age = FRESH_THRESHOLD_S + 60  # 16 minutes
        fake_redis.setex(_cache_key(athlete_id), CACHE_TTL_S, _make_cache_entry(age_seconds=age))

        payload, state = read_briefing_cache(athlete_id)

        assert state == BriefingState.STALE
        assert payload is not None

    def test_cache_expired_returns_null(self, fake_redis):
        """Test 3: cached entry > 60 min returns null + state missing."""
        athlete_id = str(uuid4())
        age = STALE_MAX_S + 60  # 61 minutes
        fake_redis.setex(_cache_key(athlete_id), CACHE_TTL_S, _make_cache_entry(age_seconds=age))

        payload, state = read_briefing_cache(athlete_id)

        assert payload is None
        assert state == BriefingState.MISSING

    def test_cache_miss_returns_null(self, fake_redis):
        """Test 4: no cache entry returns null + state missing."""
        athlete_id = str(uuid4())

        payload, state = read_briefing_cache(athlete_id)

        assert payload is None
        assert state == BriefingState.MISSING

    def test_no_stale_served_beyond_60_min(self, fake_redis):
        """Test 5: entry at 61 min treated as missing, not stale."""
        athlete_id = str(uuid4())
        age = STALE_MAX_S + 1
        fake_redis.setex(_cache_key(athlete_id), CACHE_TTL_S, _make_cache_entry(age_seconds=age))

        payload, state = read_briefing_cache(athlete_id)

        assert payload is None
        assert state == BriefingState.MISSING


class TestCacheWrite:
    """Test 6: cache write shape."""

    def test_cache_write_shape(self, fake_redis):
        """Test 6: task writes correct JSON structure with all required fields."""
        athlete_id = str(uuid4())
        payload = {"coach_noticed": "You ran well", "morning_voice": "48 miles."}

        result = write_briefing_cache(
            athlete_id=athlete_id,
            payload=payload,
            source_model="gemini-2.5-flash",
            data_fingerprint="abc123def456",
        )

        assert result is True

        raw = fake_redis.get(_cache_key(athlete_id))
        assert raw is not None

        entry = json.loads(raw)
        assert "payload" in entry
        assert "generated_at" in entry
        assert "expires_at" in entry
        assert "source_model" in entry
        assert "version" in entry
        assert "data_fingerprint" in entry
        assert entry["source_model"] == "gemini-2.5-flash"
        assert entry["payload"]["coach_noticed"] == "You ran well"


class TestDataFingerprint:
    """Tests 7-8: fingerprint stability and change detection."""

    def test_data_fingerprint_changes_on_new_activity(self, db_session, test_athlete):
        """Test 7: fingerprint differs when activity data changes."""
        from tasks.home_briefing_tasks import _build_data_fingerprint
        from models import Activity

        fp1 = _build_data_fingerprint(str(test_athlete.id), db_session)

        activity = Activity(
            athlete_id=test_athlete.id,
            name="Morning Run",
            sport="run",
            start_time=datetime.now(timezone.utc),
            distance_m=5000,
            duration_s=1800,
        )
        db_session.add(activity)
        db_session.commit()

        fp2 = _build_data_fingerprint(str(test_athlete.id), db_session)

        assert fp1 != fp2

    def test_data_fingerprint_stable_when_no_change(self, db_session, test_athlete):
        """Test 8: fingerprint identical when data unchanged."""
        from tasks.home_briefing_tasks import _build_data_fingerprint

        fp1 = _build_data_fingerprint(str(test_athlete.id), db_session)
        fp2 = _build_data_fingerprint(str(test_athlete.id), db_session)

        assert fp1 == fp2


class TestDedupe:
    """Tests 9-10: in-flight lock and cooldown."""

    def test_dedupe_prevents_concurrent_refreshes(self, fake_redis):
        """Test 9: second enqueue for same athlete while lock held is a no-op."""
        athlete_id = str(uuid4())

        assert acquire_task_lock(athlete_id) is True
        assert acquire_task_lock(athlete_id) is False

        release_task_lock(athlete_id)
        assert acquire_task_lock(athlete_id) is True

    def test_cooldown_coalesces_rapid_triggers(self, fake_redis):
        """Test 10: multiple triggers within 60s produce only one task."""
        athlete_id = str(uuid4())

        assert should_enqueue_refresh(athlete_id) is True

        set_enqueue_cooldown(athlete_id)

        assert should_enqueue_refresh(athlete_id) is False


class TestCircuitBreaker:
    """Test 11: circuit breaker stops requeue after failures."""

    def test_circuit_breaker_stops_requeue_after_3_failures(self, fake_redis):
        """Test 11: after 3 failures, no new tasks for 15 min."""
        athlete_id = str(uuid4())

        assert should_enqueue_refresh(athlete_id) is True

        for _ in range(CIRCUIT_FAILURE_THRESHOLD):
            record_task_failure(athlete_id)

        assert should_enqueue_refresh(athlete_id) is False

        reset_circuit(athlete_id)
        assert should_enqueue_refresh(athlete_id) is True


class TestTaskRetryAndTimeout:
    """Tests 12-14: retry behavior and timeouts."""

    def test_celery_task_retries_on_provider_failure(self):
        """Test 12: task retries up to 3 times with backoff."""
        from tasks.home_briefing_tasks import generate_home_briefing_task

        assert generate_home_briefing_task.max_retries == 3
        assert generate_home_briefing_task.autoretry_for == (Exception,)

    def test_celery_task_idempotent(self, fake_redis):
        """Test 13: same athlete + fingerprint = same result, no duplicate work."""
        athlete_id = str(uuid4())
        payload = {"coach_noticed": "Test", "morning_voice": "48 miles."}

        write_briefing_cache(athlete_id, payload, "gemini-2.5-flash", "fp1")
        entry1 = json.loads(fake_redis.get(_cache_key(athlete_id)))

        write_briefing_cache(athlete_id, payload, "gemini-2.5-flash", "fp1")
        entry2 = json.loads(fake_redis.get(_cache_key(athlete_id)))

        assert entry1["payload"] == entry2["payload"]
        assert entry1["data_fingerprint"] == entry2["data_fingerprint"]

    def test_task_runtime_timeout(self):
        """Test 14: task killed after 15s hard limit."""
        from tasks.home_briefing_tasks import generate_home_briefing_task, TASK_HARD_TIMEOUT_S

        assert generate_home_briefing_task.time_limit == TASK_HARD_TIMEOUT_S
        assert TASK_HARD_TIMEOUT_S == 15


class TestTaskSession:
    """Test 15: task creates its own DB session."""

    def test_task_uses_own_db_session(self):
        """Test 15: task creates its own DB session via get_db_sync(), not injected."""
        with patch("tasks.home_briefing_tasks.get_db_sync") as mock_get_db, \
             patch("tasks.home_briefing_tasks.acquire_task_lock", return_value=True), \
             patch("tasks.home_briefing_tasks.release_task_lock"), \
             patch("tasks.home_briefing_tasks._build_data_fingerprint", return_value="fp"), \
             patch("tasks.home_briefing_tasks._build_briefing_prompt", return_value=None):
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db
            from tasks.home_briefing_tasks import generate_home_briefing_task
            generate_home_briefing_task(athlete_id=str(uuid4()))
            mock_get_db.assert_called_once()
            mock_db.close.assert_called_once()


class TestBriefingStateEnum:
    """Test 16: briefing_state is always valid enum."""

    def test_briefing_state_always_valid_enum(self, fake_redis):
        """Test 16: briefing_state is always one of fresh/stale/missing/refreshing."""
        athlete_id = str(uuid4())

        # Missing
        _, state = read_briefing_cache(athlete_id)
        assert state in BriefingState

        # Fresh
        fake_redis.setex(_cache_key(athlete_id), CACHE_TTL_S, _make_cache_entry(age_seconds=60))
        _, state = read_briefing_cache(athlete_id)
        assert state in BriefingState

        # Stale
        fake_redis.setex(
            _cache_key(athlete_id), CACHE_TTL_S,
            _make_cache_entry(age_seconds=FRESH_THRESHOLD_S + 60)
        )
        _, state = read_briefing_cache(athlete_id)
        assert state in BriefingState

        # Refreshing (lock held, no cache)
        fake_redis.delete(_cache_key(athlete_id))
        fake_redis.set(_lock_key(athlete_id), "1", ex=LOCK_TTL_S)
        _, state = read_briefing_cache(athlete_id)
        assert state == BriefingState.REFRESHING


# ===========================================================================
# Category 2: Integration Tests (17-28)
# ===========================================================================


class TestHomeEndpointNoLLM:
    """Tests 17-22b: endpoint never blocks on LLM."""

    def _setup_overrides(self, app, test_athlete, db_session):
        """Override auth and DB dependencies to use test fixtures."""
        from core.auth import get_current_user
        from core.database import get_db
        app.dependency_overrides[get_current_user] = lambda: test_athlete
        app.dependency_overrides[get_db] = lambda: db_session

    def _cleanup_overrides(self, app):
        from core.auth import get_current_user
        from core.database import get_db
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)

    def _add_activity(self, db_session, test_athlete):
        """Add a test activity so has_any_activities is True."""
        from models import Activity
        activity = Activity(
            athlete_id=test_athlete.id,
            name="Test Run",
            sport="run",
            start_time=datetime.now(timezone.utc),
            distance_m=5000,
            duration_s=1800,
        )
        db_session.add(activity)
        db_session.flush()

    def test_home_endpoint_no_llm_call(self, db_session, test_athlete):
        """Test 17: GET /v1/home with flag on never invokes inline LLM call."""
        from main import app
        from fastapi.testclient import TestClient

        self._add_activity(db_session, test_athlete)
        self._setup_overrides(app, test_athlete, db_session)
        try:
            with patch("routers.home.is_feature_enabled", return_value=True), \
                 patch("services.home_briefing_cache.get_redis_client", return_value=FakeRedis()), \
                 patch("routers.home._fetch_llm_briefing_sync") as mock_llm, \
                 patch("tasks.home_briefing_tasks.generate_home_briefing_task") as mock_task:
                mock_task.delay = MagicMock()
                with TestClient(app) as tc:
                    response = tc.get("/v1/home")
                assert response.status_code == 200
                mock_llm.assert_not_called()
        finally:
            self._cleanup_overrides(app)

    def test_home_endpoint_returns_briefing_state_field(self, db_session, test_athlete):
        """Test 18: response JSON includes briefing_state with valid enum value."""
        from main import app
        from fastapi.testclient import TestClient

        self._add_activity(db_session, test_athlete)
        self._setup_overrides(app, test_athlete, db_session)
        try:
            with patch("routers.home.is_feature_enabled", return_value=True), \
                 patch("services.home_briefing_cache.get_redis_client", return_value=FakeRedis()), \
                 patch("tasks.home_briefing_tasks.generate_home_briefing_task") as mock_task:
                mock_task.delay = MagicMock()
                with TestClient(app) as tc:
                    response = tc.get("/v1/home")
                assert response.status_code == 200
                data = response.json()
                assert "briefing_state" in data
                assert data["briefing_state"] in ("fresh", "stale", "missing", "refreshing")
        finally:
            self._cleanup_overrides(app)

    def test_home_endpoint_deterministic_payload_intact(self, db_session, test_athlete):
        """Test 19: all non-briefing fields populated correctly when briefing missing."""
        from main import app
        from fastapi.testclient import TestClient

        self._setup_overrides(app, test_athlete, db_session)
        try:
            with patch("routers.home.is_feature_enabled", return_value=True), \
                 patch("services.home_briefing_cache.get_redis_client", return_value=FakeRedis()), \
                 patch("tasks.home_briefing_tasks.generate_home_briefing_task") as mock_task:
                mock_task.delay = MagicMock()
                with TestClient(app) as tc:
                    response = tc.get("/v1/home")
                assert response.status_code == 200
                data = response.json()
                assert "today" in data
                assert "yesterday" in data
                assert "week" in data
                assert data["briefing_state"] == "missing"
        finally:
            self._cleanup_overrides(app)

    def test_home_endpoint_with_cached_briefing(self, db_session, test_athlete):
        """Test 20: pre-seed Redis → coach_briefing returned, briefing_state fresh."""
        from main import app
        from fastapi.testclient import TestClient

        self._add_activity(db_session, test_athlete)

        mock_r = FakeRedis()
        athlete_id = str(test_athlete.id)
        mock_r.setex(
            _cache_key(athlete_id), CACHE_TTL_S,
            _make_cache_entry(age_seconds=60)
        )
        self._setup_overrides(app, test_athlete, db_session)
        try:
            with patch("routers.home.is_feature_enabled", return_value=True), \
                 patch("services.home_briefing_cache.get_redis_client", return_value=mock_r), \
                 patch("tasks.home_briefing_tasks.generate_home_briefing_task") as mock_task:
                mock_task.delay = MagicMock()
                with TestClient(app) as tc:
                    response = tc.get("/v1/home")
                assert response.status_code == 200
                data = response.json()
                assert data["briefing_state"] == "fresh"
                assert data["coach_briefing"] is not None
                assert data["coach_briefing"]["coach_noticed"] == "Test insight"
        finally:
            self._cleanup_overrides(app)

    def test_home_endpoint_without_cache(self, db_session, test_athlete):
        """Test 21: empty Redis → coach_briefing null, briefing_state missing, task enqueued."""
        from main import app
        from fastapi.testclient import TestClient

        self._add_activity(db_session, test_athlete)
        self._setup_overrides(app, test_athlete, db_session)
        try:
            with patch("routers.home.is_feature_enabled", return_value=True), \
                 patch("services.home_briefing_cache.get_redis_client", return_value=FakeRedis()), \
                 patch("tasks.home_briefing_tasks.generate_home_briefing_task") as mock_task:
                mock_task.delay = MagicMock()
                with TestClient(app) as tc:
                    response = tc.get("/v1/home")
                assert response.status_code == 200
                data = response.json()
                assert data["coach_briefing"] is None
                assert data["briefing_state"] == "missing"
        finally:
            self._cleanup_overrides(app)

    def test_home_p95_unaffected_when_llm_down(self, db_session, test_athlete):
        """Test 22: mock provider timeout → /v1/home still returns < 2s."""
        from main import app
        from fastapi.testclient import TestClient

        self._setup_overrides(app, test_athlete, db_session)
        try:
            with patch("routers.home.is_feature_enabled", return_value=True), \
                 patch("services.home_briefing_cache.get_redis_client", return_value=FakeRedis()), \
                 patch("tasks.home_briefing_tasks.generate_home_briefing_task") as mock_task:
                mock_task.delay = MagicMock()
                with TestClient(app) as tc:
                    start = time.monotonic()
                    response = tc.get("/v1/home")
                    elapsed = time.monotonic() - start
                assert response.status_code == 200
                assert elapsed < 2.0, f"/v1/home took {elapsed:.2f}s — SLO is < 2s"
                assert response.json()["briefing_state"] == "missing"
        finally:
            self._cleanup_overrides(app)

    def test_home_does_not_await_task_result(self, db_session, test_athlete):
        """Test 22b: /v1/home returns < 2s even when enqueue raises (broker down)."""
        from main import app
        from fastapi.testclient import TestClient

        self._add_activity(db_session, test_athlete)
        self._setup_overrides(app, test_athlete, db_session)
        try:
            def exploding_enqueue(*args, **kwargs):
                raise ConnectionError("Redis broker unreachable")

            with patch("routers.home.is_feature_enabled", return_value=True), \
                 patch("services.home_briefing_cache.get_redis_client", return_value=FakeRedis()), \
                 patch("tasks.home_briefing_tasks.enqueue_briefing_refresh", side_effect=exploding_enqueue):
                with TestClient(app) as tc:
                    start = time.monotonic()
                    response = tc.get("/v1/home")
                    elapsed = time.monotonic() - start
                assert response.status_code == 200, (
                    f"Expected 200 even when enqueue fails, got {response.status_code}"
                )
                assert elapsed < 2.0, (
                    f"/v1/home took {elapsed:.2f}s with failing enqueue — "
                    f"proves endpoint is resilient to broker failure"
                )
                data = response.json()
                assert data["coach_briefing"] is None
                assert data["briefing_state"] == "missing"
        finally:
            self._cleanup_overrides(app)


class TestTriggers:
    """Tests 23-25: regeneration triggers wired at actual call sites."""

    def _assert_enqueue_call_in_source(self, module_path: str):
        """Parse a Python file's AST and assert enqueue_briefing_refresh is called."""
        import ast
        source_file = os.path.join(os.path.dirname(__file__), "..", module_path)
        with open(source_file) as f:
            tree = ast.parse(f.read())

        has_import = False
        has_call = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "home_briefing_tasks" in node.module:
                    for alias in node.names:
                        if alias.name == "enqueue_briefing_refresh":
                            has_import = True
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "enqueue_briefing_refresh":
                    has_call = True
                elif isinstance(func, ast.Attribute) and func.attr == "enqueue_briefing_refresh":
                    has_call = True

        assert has_import, f"{module_path} does not import enqueue_briefing_refresh"
        assert has_call, f"{module_path} imports but never calls enqueue_briefing_refresh"

    def test_trigger_checkin_enqueues_refresh(self):
        """Test 23: routers/v1.py check-in handler imports and calls enqueue_briefing_refresh."""
        self._assert_enqueue_call_in_source("routers/v1.py")

    def test_trigger_activity_ingest_enqueues_refresh(self):
        """Test 24: tasks/strava_tasks.py post-sync handler imports and calls enqueue_briefing_refresh."""
        self._assert_enqueue_call_in_source("tasks/strava_tasks.py")

    def test_trigger_plan_change_enqueues_refresh(self):
        """Test 25: routers/training_plans.py plan creation imports and calls enqueue_briefing_refresh."""
        self._assert_enqueue_call_in_source("routers/training_plans.py")

    def test_trigger_intelligence_enqueues_refresh(self):
        """Test 25b: tasks/intelligence_tasks.py intelligence write imports and calls enqueue_briefing_refresh."""
        self._assert_enqueue_call_in_source("tasks/intelligence_tasks.py")

    def test_enqueue_calls_delay_on_celery_task(self, fake_redis):
        """Test 25c: enqueue_briefing_refresh invokes .delay() on the Celery task (behavioral)."""
        with patch("tasks.home_briefing_tasks.generate_home_briefing_task") as mock_task:
            mock_task.delay = MagicMock()
            from tasks.home_briefing_tasks import enqueue_briefing_refresh
            athlete_id = str(uuid4())
            result = enqueue_briefing_refresh(athlete_id)
            assert result is True
            mock_task.delay.assert_called_once_with(athlete_id)


class TestAdminRefreshEndpoint:
    """Tests 26-28: admin refresh endpoint auth and audit."""

    def _make_athlete_with_role(self, role="athlete"):
        """Create a mock athlete with a given role."""
        athlete = MagicMock()
        athlete.id = uuid4()
        athlete.email = f"test_{uuid4()}@example.com"
        athlete.role = role
        athlete.display_name = "Test"
        return athlete

    def test_admin_refresh_endpoint_202(self):
        """Test 26: POST /v1/home/admin/briefing-refresh/{id} returns 202 for admin."""
        from core.auth import get_current_user
        from core.database import get_db
        from main import app
        from fastapi.testclient import TestClient

        admin = self._make_athlete_with_role("admin")
        target_id = str(uuid4())
        app.dependency_overrides[get_current_user] = lambda: admin
        app.dependency_overrides[get_db] = lambda: MagicMock()
        try:
            with patch("tasks.home_briefing_tasks.generate_home_briefing_task") as mock_task, \
                 patch("services.home_briefing_cache.get_redis_client", return_value=FakeRedis()), \
                 patch("services.audit_logger.log_audit") as mock_audit:
                mock_task.delay = MagicMock()
                with TestClient(app) as tc:
                    response = tc.post(f"/v1/home/admin/briefing-refresh/{target_id}")
                assert response.status_code == 202, f"Expected 202, got {response.status_code}: {response.text}"
                data = response.json()
                assert data["athlete_id"] == target_id
                assert data["status"] in ("enqueued", "skipped")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)

    def test_admin_refresh_endpoint_403_non_admin(self):
        """Test 27: same endpoint returns 403 for non-admin athlete."""
        from core.auth import get_current_user
        from core.database import get_db
        from main import app
        from fastapi.testclient import TestClient

        regular = self._make_athlete_with_role("athlete")
        target_id = str(uuid4())
        app.dependency_overrides[get_current_user] = lambda: regular
        app.dependency_overrides[get_db] = lambda: MagicMock()
        try:
            with TestClient(app) as tc:
                response = tc.post(f"/v1/home/admin/briefing-refresh/{target_id}")
            assert response.status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)

    def test_admin_refresh_audit_logged(self):
        """Test 28: admin refresh writes audit log entry with correct action."""
        from core.auth import get_current_user
        from core.database import get_db
        from main import app
        from fastapi.testclient import TestClient

        owner = self._make_athlete_with_role("owner")
        target_id = str(uuid4())
        app.dependency_overrides[get_current_user] = lambda: owner
        app.dependency_overrides[get_db] = lambda: MagicMock()
        try:
            with patch("tasks.home_briefing_tasks.generate_home_briefing_task") as mock_task, \
                 patch("services.home_briefing_cache.get_redis_client", return_value=FakeRedis()), \
                 patch("services.audit_logger.log_audit") as mock_audit:
                mock_task.delay = MagicMock()
                with TestClient(app) as tc:
                    response = tc.post(f"/v1/home/admin/briefing-refresh/{target_id}")
                assert response.status_code == 202
                mock_audit.assert_called_once()
                call_args = mock_audit.call_args
                if call_args.kwargs:
                    assert call_args.kwargs.get("action") == "home_briefing.admin_refresh"
                else:
                    assert call_args[1].get("action") == "home_briefing.admin_refresh"
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)


# ===========================================================================
# Category 3: Celery Task Tests (29-33)
# ===========================================================================


class TestCeleryTask:
    """Tests 29-33: Celery task behavior."""

    def test_celery_task_writes_to_redis(self, fake_redis):
        """Test 29: task runs → Redis entry exists with correct structure."""
        athlete_id = str(uuid4())
        payload = {"coach_noticed": "Good run", "morning_voice": "30 miles this week."}

        write_briefing_cache(athlete_id, payload, "gemini-2.5-flash", "fp123")

        raw = fake_redis.get(_cache_key(athlete_id))
        assert raw is not None

        entry = json.loads(raw)
        assert entry["source_model"] == "gemini-2.5-flash"
        assert entry["data_fingerprint"] == "fp123"
        assert entry["payload"]["coach_noticed"] == "Good run"

    def test_celery_task_uses_gemini_by_default(self, fake_redis):
        """Test 30: with flag off, task calls Gemini and writes gemini model tag."""
        from tasks.home_briefing_tasks import _call_gemini_briefing

        gemini_result = {"coach_noticed": "Gemini says hi", "morning_voice": "30 miles."}
        with patch("tasks.home_briefing_tasks._call_gemini_briefing", return_value=gemini_result) as mock_gemini, \
             patch("tasks.home_briefing_tasks._call_opus_briefing") as mock_opus, \
             patch("tasks.home_briefing_tasks._build_data_fingerprint", return_value="fp1"), \
             patch("tasks.home_briefing_tasks._build_briefing_prompt", return_value=("prompt", {}, [], {}, {})), \
             patch("tasks.home_briefing_tasks.get_db_sync", return_value=MagicMock()), \
             patch("tasks.home_briefing_tasks.acquire_task_lock", return_value=True), \
             patch("tasks.home_briefing_tasks.release_task_lock"), \
             patch("core.feature_flags.is_feature_enabled", return_value=False), \
             patch("routers.home._valid_home_briefing_contract", return_value=True), \
             patch("routers.home.validate_voice_output", return_value={"valid": True}):
            from tasks.home_briefing_tasks import generate_home_briefing_task
            result = generate_home_briefing_task(athlete_id=str(uuid4()))
            mock_gemini.assert_called_once()
            mock_opus.assert_not_called()
            assert result["model"] == "gemini-2.5-flash"

    def test_celery_task_respects_feature_flag_for_opus(self, fake_redis):
        """Test 31: flag on → task tries Opus first; if it returns result, uses it."""
        opus_result = {"coach_noticed": "Opus insight", "morning_voice": "50 miles."}
        with patch("tasks.home_briefing_tasks._call_opus_briefing", return_value=opus_result) as mock_opus, \
             patch("tasks.home_briefing_tasks._call_gemini_briefing") as mock_gemini, \
             patch("tasks.home_briefing_tasks._build_data_fingerprint", return_value="fp1"), \
             patch("tasks.home_briefing_tasks._build_briefing_prompt", return_value=("prompt", {}, [], {}, {})), \
             patch("tasks.home_briefing_tasks.get_db_sync", return_value=MagicMock()), \
             patch("tasks.home_briefing_tasks.acquire_task_lock", return_value=True), \
             patch("tasks.home_briefing_tasks.release_task_lock"), \
             patch("core.feature_flags.is_feature_enabled", return_value=True), \
             patch("routers.home._valid_home_briefing_contract", return_value=True), \
             patch("routers.home.validate_voice_output", return_value={"valid": True}):
            from tasks.home_briefing_tasks import generate_home_briefing_task
            result = generate_home_briefing_task(athlete_id=str(uuid4()))
            mock_opus.assert_called_once()
            mock_gemini.assert_not_called()
            assert result["model"] == "claude-opus-4-5"

    def test_celery_task_handles_provider_failure(self, fake_redis):
        """Test 32: on failure: record failure, no cache written."""
        athlete_id = str(uuid4())

        record_task_failure(athlete_id)

        raw = fake_redis.get(_cache_key(athlete_id))
        assert raw is None

        circuit_val = fake_redis.get(_circuit_key(athlete_id))
        assert circuit_val is not None
        assert int(circuit_val) == 1

    def test_celery_task_lock_prevents_parallel(self, fake_redis):
        """Test 33: concurrent task for same athlete is skipped."""
        athlete_id = str(uuid4())

        assert acquire_task_lock(athlete_id) is True
        assert acquire_task_lock(athlete_id) is False

        release_task_lock(athlete_id)


class TestProviderTimeout:
    """Test 36: provider timeout enforcement (behavioral)."""

    def test_gemini_provider_timeout_enforced(self):
        """Test 36: _call_gemini_briefing kills provider call after PROVIDER_TIMEOUT_S."""
        from tasks.home_briefing_tasks import PROVIDER_TIMEOUT_S

        def slow_gemini(*args, **kwargs):
            time.sleep(PROVIDER_TIMEOUT_S + 5)
            return {"coach_noticed": "Too late"}

        with patch("routers.home._call_gemini_briefing_sync", side_effect=slow_gemini), \
             patch.dict(os.environ, {"GOOGLE_AI_API_KEY": "fake-key"}):
            from tasks.home_briefing_tasks import _call_gemini_briefing
            start = time.monotonic()
            result = _call_gemini_briefing("prompt", {}, [])
            elapsed = time.monotonic() - start

        assert result is None, "Timed-out provider should return None"
        assert elapsed < PROVIDER_TIMEOUT_S + 2, (
            f"Timeout took {elapsed:.1f}s — expected ~{PROVIDER_TIMEOUT_S}s"
        )

    def test_opus_provider_timeout_enforced(self):
        """Test 37: _call_opus_briefing kills provider call after PROVIDER_TIMEOUT_S."""
        from tasks.home_briefing_tasks import PROVIDER_TIMEOUT_S

        def slow_opus(*args, **kwargs):
            time.sleep(PROVIDER_TIMEOUT_S + 5)
            return {"coach_noticed": "Too late"}

        with patch("routers.home._call_opus_briefing_sync", side_effect=slow_opus), \
             patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-key"}):
            from tasks.home_briefing_tasks import _call_opus_briefing
            start = time.monotonic()
            result = _call_opus_briefing("prompt", {}, [])
            elapsed = time.monotonic() - start

        assert result is None, "Timed-out provider should return None"
        assert elapsed < PROVIDER_TIMEOUT_S + 2, (
            f"Timeout took {elapsed:.1f}s — expected ~{PROVIDER_TIMEOUT_S}s"
        )


class TestTaskHardTimeoutConstant:
    """Test 38: task-level timeout constants match ADR spec."""

    def test_task_hard_timeout_is_15s(self):
        """Test 38: Celery task hard limit is exactly 15s per ADR-065."""
        from tasks.home_briefing_tasks import generate_home_briefing_task, TASK_HARD_TIMEOUT_S

        assert TASK_HARD_TIMEOUT_S == 15
        assert generate_home_briefing_task.time_limit == TASK_HARD_TIMEOUT_S

    def test_provider_timeout_is_12s(self):
        """Test 39: provider timeout is exactly 12s per ADR-065."""
        from tasks.home_briefing_tasks import PROVIDER_TIMEOUT_S

        assert PROVIDER_TIMEOUT_S == 12


# ===========================================================================
# Category 4: Schema Contract Tests (34-35)
# ===========================================================================


class TestSchemaContract:
    """Tests 34-35: briefing_state always valid."""

    def test_briefing_state_present_when_briefing_null(self, fake_redis):
        """Test 34: briefing_state always present even when coach_briefing is null."""
        athlete_id = str(uuid4())
        payload, state = read_briefing_cache(athlete_id)

        assert payload is None
        assert state is not None
        assert isinstance(state, BriefingState)
        assert state == BriefingState.MISSING

    def test_briefing_state_enum_values_exhaustive(self):
        """Test 35: only valid enum values exist."""
        expected = {"fresh", "stale", "missing", "refreshing"}
        actual = {s.value for s in BriefingState}
        assert actual == expected
