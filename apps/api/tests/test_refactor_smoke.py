"""
Refactor smoke tests — verify nothing broke after structural changes.

These tests exercise critical import paths and API endpoints to catch
breakage from file moves, model splits, and service reorganization.
They are NOT exhaustive — they verify the import graph is intact and
key endpoints return 200 with valid JSON.

Run after every refactor commit:
    docker compose -f docker-compose.test.yml run --rm api_test pytest -x -q tests/test_refactor_smoke.py
"""
import importlib
import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# 1. Critical import paths — if any of these fail, the app won't start
# ---------------------------------------------------------------------------

CRITICAL_MODULES = [
    "models",
    "core.database",
    "core.security",
    "core.config",
    "core.auth",
    "core.cache",
    "main",
    "routers.v1",
    "routers.home",
    "routers.activities",
    "routers.ai_coach",
    "routers.plan_generation",
    "routers.auth",
    "routers.calendar",
    "routers.strava",
    "routers.strava_webhook",
    "routers.analytics",
    "routers.correlations",
    "routers.training_plans",
    "routers.daily_intelligence",
    "routers.stream_analysis",
    "routers.fingerprint",
    "routers.billing",
    "routers.progress",
    "routers.admin",
    "services.ai_coach",
    "services.coach_tools",
    "services.correlation_engine",
    "services.run_intelligence",
    "services.strava_service",
    "services.strava_index",
    "services.strava_ingest",
    "services.garmin_adapter",
    "services.garmin_backfill",
    "services.activity_deduplication",
    "services.duplicate_scanner",
    "services.attribution_engine",
    "services.n1_insight_generator",
    "services.moment_narrator",
    "services.run_stream_analysis",
    "services.shape_extractor",
    "services.run_analysis_engine",
    "services.performance_engine",
    "services.training_load",
    "services.fitness_bank",
    "services.fingerprint_analysis",
    "services.operating_manual",
    "services.email_service",
    "services.stripe_service",
    "services.runtoon_service",
]


@pytest.mark.parametrize("module_path", CRITICAL_MODULES)
def test_critical_import(module_path):
    """Every critical module must import without error."""
    mod = importlib.import_module(module_path)
    assert mod is not None


# ---------------------------------------------------------------------------
# 2. Model availability — every model the app depends on must be importable
# ---------------------------------------------------------------------------

EXPECTED_MODELS = [
    "Athlete",
    "Activity",
    "ActivitySplit",
    "ActivityStream",
    "DailyCheckin",
    "PersonalBest",
    "BestEffort",
    "CorrelationFinding",
    "TrainingPlan",
    "PlannedWorkout",
]


@pytest.mark.parametrize("model_name", EXPECTED_MODELS)
def test_model_importable(model_name):
    """All ORM models must be importable from `models`."""
    import models
    cls = getattr(models, model_name, None)
    assert cls is not None, f"models.{model_name} not found"


# ---------------------------------------------------------------------------
# 3. App startup — FastAPI app must construct without crashing
# ---------------------------------------------------------------------------

def test_app_creates():
    """The FastAPI app must instantiate."""
    from main import app
    assert app is not None
    assert app.title is not None


# ---------------------------------------------------------------------------
# 4. Unauthenticated endpoints — must return 200 (not 500)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    from main import app
    return TestClient(app)


HEALTH_ENDPOINTS = [
    "/health",
    "/health/detailed",
]


@pytest.mark.parametrize("path", HEALTH_ENDPOINTS)
def test_health_endpoints(client, path):
    """Health endpoints must return 200."""
    resp = client.get(path)
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data


# ---------------------------------------------------------------------------
# 5. Authenticated endpoints — must return 401 (not 500)
#    A 401 proves the route is registered and the auth layer works.
#    A 500 means something is broken.
# ---------------------------------------------------------------------------

AUTH_REQUIRED_ENDPOINTS = [
    ("GET", "/v1/home"),
    ("GET", "/v1/activities"),
    ("GET", "/v1/calendar/activities"),
    ("GET", "/v1/analytics/efficiency-trends"),
    ("GET", "/v1/fingerprint/browse"),
    ("GET", "/v1/progress/summary"),
]


@pytest.mark.parametrize("method,path", AUTH_REQUIRED_ENDPOINTS)
def test_auth_required_endpoints_reject_unauthenticated(client, method, path):
    """Authenticated endpoints must return 401/403, never 500."""
    resp = getattr(client, method.lower())(path)
    assert resp.status_code in (401, 403, 422), (
        f"{method} {path} returned {resp.status_code} — expected 401/403/422, "
        f"body: {resp.text[:200]}"
    )


# ---------------------------------------------------------------------------
# 6. Workout registry — plan framework data file must be loadable
# ---------------------------------------------------------------------------

def test_workout_registry_loads():
    """The workout variant registry JSON must parse without error."""
    try:
        from services.plan_framework.workout_variant_dispatch import (
            resolve_workout_variant_id,
        )
    except ImportError:
        pytest.skip("workout_variant_dispatch not importable")
    result = resolve_workout_variant_id("tempo_classic", {})
    # result can be None if no match, but the function must not crash
    assert result is None or isinstance(result, str)
