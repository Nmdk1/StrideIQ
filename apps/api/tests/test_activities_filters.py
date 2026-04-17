"""
Phase 1 — Activities-list filters: backend contract tests.

Spec: docs/specs/phase1_filters_design.md

Tests cover:
1. New filter query params on GET /v1/activities
   - workout_type (comma-separated multi-value)
   - temp_min / temp_max (°F)
   - dew_min / dew_max (°F)
   - elev_gain_min / elev_gain_max (meters)
2. New endpoint GET /v1/activities/filter-distributions
   - Per-dimension histograms (16 buckets)
   - workout_types with counts
   - available=false when <5 activities have values
3. Suppression rules (no surface for missing data)
4. Backward compatibility: existing filters unchanged.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models import Activity, Athlete

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def filter_athlete():
    """Dedicated athlete for filter tests with a known activity distribution."""
    db = SessionLocal()
    try:
        athlete = Athlete(
            email=f"test_filters_{uuid4()}@example.com",
            display_name="Filter Athlete",
            subscription_tier="free",
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)
        yield athlete
        # Cleanup
        db.query(Activity).filter(Activity.athlete_id == athlete.id).delete()
        db.delete(athlete)
        db.commit()
    finally:
        db.close()


@pytest.fixture
def filter_token(filter_athlete):
    return create_access_token({"sub": str(filter_athlete.id)})


@pytest.fixture
def filter_headers(filter_token):
    return {"Authorization": f"Bearer {filter_token}"}


def _make_activity(
    *,
    athlete_id,
    days_ago: int = 1,
    distance_m: int = 5000,
    workout_type: str | None = "easy_run",
    temperature_f: float | None = 65.0,
    dew_point_f: float | None = 55.0,
    elevation_gain_m: float | None = 100.0,
    sport: str = "run",
):
    """Build an Activity instance with the fields used by filter tests."""
    return Activity(
        athlete_id=athlete_id,
        start_time=datetime.now(timezone.utc) - timedelta(days=days_ago),
        sport=sport,
        source="test",
        duration_s=1800,
        distance_m=distance_m,
        avg_hr=150,
        average_speed=Decimal("2.78"),
        workout_type=workout_type,
        temperature_f=temperature_f,
        dew_point_f=dew_point_f,
        total_elevation_gain=Decimal(str(elevation_gain_m)) if elevation_gain_m is not None else None,
    )


@pytest.fixture
def filter_dataset(filter_athlete):
    """
    Insert a known activity distribution we can assert against.

    Layout (12 activities):
        - 4 easy runs at 5km, dew ~50, temp ~60, ~50m gain
        - 4 long runs at 18km, dew ~70, temp ~80, ~250m gain
        - 3 threshold runs at 8km, dew ~55, temp ~68, ~80m gain
        - 1 trail run with NULL workout_type, NULL temp, NULL dew, 800m gain
    """
    db = SessionLocal()
    rows: list[Activity] = []
    try:
        for i in range(4):
            rows.append(_make_activity(
                athlete_id=filter_athlete.id,
                days_ago=i + 1,
                distance_m=5000,
                workout_type="easy_run",
                temperature_f=60.0 + i,
                dew_point_f=50.0 + i,
                elevation_gain_m=50.0 + i,
            ))
        for i in range(4):
            rows.append(_make_activity(
                athlete_id=filter_athlete.id,
                days_ago=i + 10,
                distance_m=18000,
                workout_type="long_run",
                temperature_f=80.0 - i,
                dew_point_f=70.0 - i,
                elevation_gain_m=250.0 - i * 5,
            ))
        for i in range(3):
            rows.append(_make_activity(
                athlete_id=filter_athlete.id,
                days_ago=i + 20,
                distance_m=8000,
                workout_type="threshold",
                temperature_f=68.0,
                dew_point_f=55.0,
                elevation_gain_m=80.0,
            ))
        rows.append(_make_activity(
            athlete_id=filter_athlete.id,
            days_ago=30,
            distance_m=10000,
            workout_type=None,
            temperature_f=None,
            dew_point_f=None,
            elevation_gain_m=800.0,
            sport="run",
        ))
        for r in rows:
            db.add(r)
        db.commit()
        for r in rows:
            db.refresh(r)
        yield rows
    finally:
        db.query(Activity).filter(Activity.athlete_id == filter_athlete.id).delete()
        db.commit()
        db.close()


# ---------------------------------------------------------------------------
# Backward compatibility: existing endpoint behavior unchanged
# ---------------------------------------------------------------------------


def test_list_activities_without_new_filters_returns_all(
    filter_athlete, filter_headers, filter_dataset
):
    """Regression guard: no new params → identical to legacy behavior, all activities returned.

    NOT xfailed — this must pass before AND after Phase 1.
    """
    resp = client.get("/v1/activities?limit=100", headers=filter_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == len(filter_dataset)


def test_existing_distance_filter_still_works(
    filter_athlete, filter_headers, filter_dataset
):
    """Regression guard: legacy min_distance_m / max_distance_m parameters preserved.

    NOT xfailed — this must pass before AND after Phase 1.
    """
    resp = client.get(
        "/v1/activities?min_distance_m=15000&limit=100", headers=filter_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert all(a["distance"] >= 15000 for a in body)
    assert len(body) == 4  # the 4 long runs at 18k


# ---------------------------------------------------------------------------
# workout_type (comma-separated multi-value)
# ---------------------------------------------------------------------------


def test_workout_type_filter_single_value(
    filter_athlete, filter_headers, filter_dataset
):
    resp = client.get(
        "/v1/activities?workout_type=long_run&limit=100", headers=filter_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 4


def test_workout_type_filter_multi_value_csv(
    filter_athlete, filter_headers, filter_dataset
):
    resp = client.get(
        "/v1/activities?workout_type=long_run,threshold&limit=100",
        headers=filter_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 7  # 4 long + 3 threshold


def test_workout_type_filter_excludes_null_workout_type(
    filter_athlete, filter_headers, filter_dataset
):
    """The activity with NULL workout_type must NOT appear when this filter is active."""
    resp = client.get(
        "/v1/activities?workout_type=easy_run&limit=100", headers=filter_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 4
    # Activity with NULL workout_type at distance 10000 should not be present
    assert all(a["distance"] != 10000 for a in body)


# ---------------------------------------------------------------------------
# Temperature / dew point range filters
# ---------------------------------------------------------------------------


def test_dew_point_range_filter_inclusive_bounds(
    filter_athlete, filter_headers, filter_dataset
):
    """dew_min=55, dew_max=70 should include activities whose dew is in [55, 70]."""
    resp = client.get(
        "/v1/activities?dew_min=55&dew_max=70&limit=100", headers=filter_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    # 4 long runs (dew 67–70), 3 thresholds (dew 55) → 7
    assert len(body) == 7


def test_temp_range_filter_excludes_null_temperature(
    filter_athlete, filter_headers, filter_dataset
):
    """When temp filter is active, activities with NULL temp must be excluded."""
    resp = client.get(
        "/v1/activities?temp_min=50&temp_max=100&limit=100", headers=filter_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 11  # the NULL-temp trail run is excluded


def test_invalid_range_min_greater_than_max_returns_400(
    filter_athlete, filter_headers, filter_dataset
):
    resp = client.get(
        "/v1/activities?dew_min=80&dew_max=60", headers=filter_headers
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Elevation gain range
# ---------------------------------------------------------------------------


def test_elevation_gain_filter(
    filter_athlete, filter_headers, filter_dataset
):
    resp = client.get(
        "/v1/activities?elev_gain_min=200&limit=100", headers=filter_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    # 4 long runs (200–250m gain) + 1 trail run (800m) = 5
    assert len(body) == 5


# ---------------------------------------------------------------------------
# Combined filters AND together
# ---------------------------------------------------------------------------


def test_combined_filters_all_and_together(
    filter_athlete, filter_headers, filter_dataset
):
    resp = client.get(
        "/v1/activities?workout_type=long_run&dew_min=68&dew_max=70&limit=100",
        headers=filter_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    # Long runs at dew 67/68/69/70 -> only those where dew >= 68: 3 of 4
    assert len(body) == 3


# ---------------------------------------------------------------------------
# /v1/activities/filter-distributions endpoint
# ---------------------------------------------------------------------------


def test_filter_distributions_endpoint_returns_workout_types_with_counts(
    filter_athlete, filter_headers, filter_dataset
):
    resp = client.get(
        "/v1/activities/filter-distributions", headers=filter_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "workout_types" in body
    types = {row["value"]: row["count"] for row in body["workout_types"]}
    # NULL workout_type is excluded from the chip strip — only present types are listed
    assert types.get("easy_run") == 4
    assert types.get("long_run") == 4
    assert types.get("threshold") == 3
    assert None not in types


def test_filter_distributions_returns_distance_histogram_with_buckets(
    filter_athlete, filter_headers, filter_dataset
):
    resp = client.get(
        "/v1/activities/filter-distributions", headers=filter_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    dist = body["distance_m"]
    assert dist["available"] is True
    assert dist["min"] == 5000
    assert dist["max"] == 18000
    assert isinstance(dist["buckets"], list)
    assert len(dist["buckets"]) == 16
    total_count = sum(b["count"] for b in dist["buckets"])
    assert total_count == 12


def test_filter_distributions_marks_dew_unavailable_when_too_few(filter_athlete, filter_headers):
    """With <5 activities having dew data, dew_point_f.available must be False."""
    db = SessionLocal()
    try:
        for i in range(3):
            act = _make_activity(
                athlete_id=filter_athlete.id,
                days_ago=i + 1,
                dew_point_f=55.0 + i,
            )
            db.add(act)
        db.commit()
        resp = client.get(
            "/v1/activities/filter-distributions", headers=filter_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["dew_point_f"]["available"] is False
    finally:
        db.query(Activity).filter(Activity.athlete_id == filter_athlete.id).delete()
        db.commit()
        db.close()


def test_filter_distributions_unavailable_when_zero_data(filter_athlete, filter_headers):
    """An athlete with no activities at all gets all dimensions marked unavailable."""
    resp = client.get(
        "/v1/activities/filter-distributions", headers=filter_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["distance_m"]["available"] is False
    assert body["temp_f"]["available"] is False
    assert body["dew_point_f"]["available"] is False
    assert body["elevation_gain_m"]["available"] is False
    assert body["workout_types"] == []


def test_filter_distributions_requires_auth(filter_athlete, filter_dataset):
    resp = client.get("/v1/activities/filter-distributions")
    assert resp.status_code == 401
