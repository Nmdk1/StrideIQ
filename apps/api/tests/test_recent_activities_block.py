from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from services.coaching import recent_activities_block as block


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


class FakeDb:
    def __init__(self, activities):
        self.activities = activities

    def query(self, model):
        if model.__name__ == "Activity":
            return FakeQuery(self.activities)
        return FakeQuery([])


def _activity(
    *,
    activity_id=None,
    days_ago=0,
    workout_type="easy_run",
    distance_m=8046,
    duration_s=2400,
    intensity_score=None,
    name="Morning Run",
):
    now = datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc)
    return SimpleNamespace(
        id=activity_id or uuid4(),
        athlete_id=uuid4(),
        name=name,
        start_time=now - timedelta(days=days_ago),
        sport="run",
        workout_type=workout_type,
        distance_m=distance_m,
        duration_s=duration_s,
        moving_time_s=duration_s,
        avg_hr=145,
        intensity_score=intensity_score,
        user_verified_race=False,
        is_race_candidate=False,
        garmin_perceived_effort=None,
    )


def _split(number, pace_s_mile, *, lap_type=None, interval_number=None):
    distance = 1609.344
    return SimpleNamespace(
        split_number=number,
        distance=distance,
        moving_time=int(round(pace_s_mile)),
        elapsed_time=int(round(pace_s_mile)),
        lap_type=lap_type,
        interval_number=interval_number,
    )


def test_recent_activities_block_populates_atoms_and_window(monkeypatch):
    athlete_id = uuid4()
    activity = _activity(workout_type="easy_run", days_ago=1)
    old_activity = _activity(workout_type="easy_run", days_ago=20)
    db = FakeDb([activity, old_activity])
    monkeypatch.setattr(block, "_query_splits", lambda db, activity_id: [])
    monkeypatch.setattr(
        block,
        "_query_feedback",
        lambda db, activity_id: SimpleNamespace(perceived_effort=4),
    )

    result = block.compute_recent_activities(
        db,
        athlete_id,
        now_utc=datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc),
    )

    assert len(result["data"]["recent_activities"]) == 1
    assert old_activity.id != result["data"]["recent_activities"][0]["activity_id"]
    assert result["schema_version"] == "coach_runtime_v2.recent_activities.v1"
    assert result["data"]["recent_activities"] == [
        {
            "activity_id": str(activity.id),
            "type": "easy_run",
            "date": "2026-04-25",
            "distance": {"meters": 8046.0, "miles": 5.0},
            "duration": {"seconds": 2400},
            "avg_pace": {"seconds_per_mile": 480.0, "display": "8:00/mi"},
            "avg_hr": 145,
            "perceived_effort": 4,
            "planned_vs_executed_delta": None,
            "notable_features": [],
            "structured_workout_summary": None,
        }
    ]


def test_notable_features_detect_pace_drift_fade_and_missed_rep(monkeypatch):
    activity = _activity(
        workout_type="threshold_intervals",
        name="4x1 mile threshold",
        duration_s=3600,
    )
    splits = [
        _split(1, 390, lap_type="work", interval_number=1),
        _split(2, 400, lap_type="work", interval_number=2),
        _split(3, 415, lap_type="work", interval_number=3),
        _split(4, 430, lap_type="rest"),
    ]
    monkeypatch.setattr(block, "_query_splits", lambda db, activity_id: splits)
    monkeypatch.setattr(block, "_query_feedback", lambda db, activity_id: None)

    result = block.compute_recent_activities(
        FakeDb([activity]),
        uuid4(),
        now_utc=datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc),
    )

    atom = result["data"]["recent_activities"][0]
    feature_types = {feature["type"] for feature in atom["notable_features"]}
    assert {"pace_drift", "fade", "missed_rep"} <= feature_types
    assert atom["structured_workout_summary"]["planned_rep_count"] == 4
    assert atom["structured_workout_summary"]["observed_work_rep_count"] == 3


def test_notable_features_detect_strong_finish(monkeypatch):
    activity = _activity(workout_type="long_run")
    splits = [
        _split(1, 500),
        _split(2, 500),
        _split(3, 500),
        _split(4, 470),
    ]
    monkeypatch.setattr(block, "_query_splits", lambda db, activity_id: splits)
    monkeypatch.setattr(block, "_query_feedback", lambda db, activity_id: None)

    result = block.compute_recent_activities(
        FakeDb([activity]),
        uuid4(),
        now_utc=datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc),
    )

    feature_types = {
        feature["type"]
        for feature in result["data"]["recent_activities"][0]["notable_features"]
    }
    assert "strong_finish" in feature_types


def test_aggregates_weekly_volume_hard_days_and_last_by_type(monkeypatch):
    activities = [
        _activity(workout_type="easy_run", days_ago=1, distance_m=8046),
        _activity(workout_type="threshold_run", days_ago=2, distance_m=5000),
        _activity(workout_type="long_run", days_ago=9, distance_m=16093),
    ]
    monkeypatch.setattr(block, "_query_splits", lambda db, activity_id: [])
    monkeypatch.setattr(block, "_query_feedback", lambda db, activity_id: None)

    result = block.compute_recent_activities(
        FakeDb(activities),
        uuid4(),
        now_utc=datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc),
    )

    aggregates = result["data"]["aggregates"]
    assert aggregates["last_4_weeks"][-1]["weekly_volume_miles"] == 8.11
    assert aggregates["last_4_weeks"][-1]["weekly_hard_day_count"] == 1
    assert (
        aggregates["last_session_by_major_type"]["easy_default"]["type"] == "easy_run"
    )
    assert (
        aggregates["last_session_by_major_type"]["threshold"]["type"] == "threshold_run"
    )
    assert aggregates["last_session_by_major_type"]["long"]["type"] == "long_run"


def test_token_cap_truncates_oldest_activities(monkeypatch):
    activities = [
        _activity(
            days_ago=day,
            name="Very long activity name " * 40,
            workout_type="easy_run",
        )
        for day in range(30)
    ]
    monkeypatch.setattr(block, "_query_splits", lambda db, activity_id: [])
    monkeypatch.setattr(block, "_query_feedback", lambda db, activity_id: None)

    result = block.compute_recent_activities(
        FakeDb(activities),
        uuid4(),
        window_days=30,
        now_utc=datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc),
    )

    assert result["token_budget"]["estimated_tokens"] <= 2500
    assert len(result["data"]["recent_activities"]) < len(activities)
    assert result["data"]["recent_activities"][0]["date"] == "2026-04-26"
