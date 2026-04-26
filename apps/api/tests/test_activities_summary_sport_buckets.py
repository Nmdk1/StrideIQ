"""Integration tests: /v1/activities/summary returns sport-separated buckets.

Contract: the summary MUST expose three views so the UI can render them
independently without silently mixing sports.

  - `running`:  sport == 'run' only — canonical training metric.
  - `other`:    non-running activity, `by_sport` breakdown (walking, strength,
                cycling, hiking, flexibility, ...).
  - `combined`: every activity.

Backwards-compatible top-level fields mirror `running` so existing clients
keep working. All distances are in meters, durations in seconds, pace in
seconds per kilometre.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models import Athlete, Activity


client = TestClient(app)


@pytest.fixture
def athlete_with_mixed_sports():
    """An athlete with one run, one walk, and one strength session in the
    last week. Exercises the three-bucket separation."""
    db = SessionLocal()
    try:
        ath = Athlete(
            email=f"summary_{uuid4()}@example.com",
            display_name="Summary Test",
            subscription_tier="free",
        )
        db.add(ath)
        db.commit()
        db.refresh(ath)

        now = datetime.utcnow() - timedelta(hours=1)
        activities = [
            Activity(
                athlete_id=ath.id, start_time=now,
                sport="run", source="manual",
                duration_s=1800, distance_m=10000, average_speed=Decimal("2.78"),
            ),
            Activity(
                athlete_id=ath.id, start_time=now - timedelta(hours=2),
                sport="walking", source="manual",
                duration_s=1200, distance_m=1500, average_speed=Decimal("1.25"),
            ),
            Activity(
                athlete_id=ath.id, start_time=now - timedelta(hours=4),
                sport="strength", source="manual",
                duration_s=2400, distance_m=None, average_speed=None,
            ),
        ]
        for a in activities:
            db.add(a)
        db.commit()
        for a in activities:
            db.refresh(a)

        yield ath, activities

        for a in activities:
            db.query(Activity).filter(Activity.id == a.id).delete()
        db.query(Athlete).filter(Athlete.id == ath.id).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture
def auth_headers(athlete_with_mixed_sports):
    ath, _ = athlete_with_mixed_sports
    token = create_access_token(data={"sub": str(ath.id), "email": ath.email, "role": "athlete"})
    return {"Authorization": f"Bearer {token}"}


def test_summary_returns_running_other_combined_buckets(auth_headers):
    r = client.get("/v1/activities/summary?days=30", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()

    assert "running" in body
    assert "other" in body
    assert "combined" in body

    for key in ("total_activities", "total_distance_m", "total_duration_s"):
        assert key in body["running"]
        assert key in body["other"]
        assert key in body["combined"]

    assert "by_sport" in body["other"]


def test_running_bucket_excludes_walks_and_strength(auth_headers):
    r = client.get("/v1/activities/summary?days=30", headers=auth_headers)
    body = r.json()
    running = body["running"]

    assert running["total_activities"] == 1
    assert running["total_distance_m"] >= 10000


def test_other_bucket_breaks_down_by_sport(auth_headers):
    r = client.get("/v1/activities/summary?days=30", headers=auth_headers)
    body = r.json()
    by_sport = body["other"]["by_sport"]

    assert "walking" in by_sport
    assert "strength" in by_sport
    assert "run" not in by_sport, "runs must not appear in the 'other' bucket"
    assert by_sport["walking"]["total_activities"] == 1
    assert by_sport["strength"]["total_activities"] == 1


def test_combined_bucket_is_the_sum(auth_headers):
    r = client.get("/v1/activities/summary?days=30", headers=auth_headers)
    body = r.json()
    assert body["combined"]["total_activities"] == (
        body["running"]["total_activities"] + body["other"]["total_activities"]
    )


def test_backwards_compat_top_level_mirrors_running(auth_headers):
    """Clients that read the old top-level fields (no buckets) keep working."""
    r = client.get("/v1/activities/summary?days=30", headers=auth_headers)
    body = r.json()
    assert body["total_activities"] == body["running"]["total_activities"]
    assert body["total_distance_m"] == body["running"]["total_distance_m"]
    assert body["race_count"] == body["running"].get("race_count", 0)


def test_avg_pace_only_on_running_bucket(auth_headers):
    """Pace averages across walks + strength + runs are meaningless, so
    avg_pace lives on the running bucket and is None on others (or omitted)."""
    r = client.get("/v1/activities/summary?days=30", headers=auth_headers)
    body = r.json()
    assert "avg_pace_s_per_km" in body["running"]
    assert body["other"].get("avg_pace_s_per_km") in (None, )
