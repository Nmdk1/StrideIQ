"""Calendar running vs other sport separation (Dejan-class bug guard)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from routers.calendar import get_day_status, split_day_distance_duration_by_sport


def _act(sport: str, distance_m: int, duration_s: int = 0) -> MagicMock:
    a = MagicMock()
    a.sport = sport
    a.distance_m = distance_m
    a.duration_s = duration_s
    return a


def test_split_totals_separates_run_from_walk():
    run = _act("run", 16130, 3600)
    walk = _act("walking", 1560, 2000)
    rd, rs, od, os_, td, ts = split_day_distance_duration_by_sport([run, walk])
    assert rd == 16130
    assert od == 1560
    assert td == 17690
    assert ts == 5600


def test_get_day_status_walk_only_does_not_complete_planned_run():
    planned = MagicMock()
    planned.workout_type = "easy"
    planned.target_distance_km = 16.0
    planned.completed = False
    planned.skipped = False
    planned.completed_activity_id = None

    walk = _act("walking", 1560, 2000)
    past = date(2026, 4, 22)
    today = date(2026, 4, 23)
    assert get_day_status(planned, [walk], past, today=today) == "missed"


def test_get_day_status_run_plus_walk_completes_planned_run():
    planned = MagicMock()
    planned.workout_type = "long"
    planned.target_distance_km = 16.0
    planned.completed = False
    planned.skipped = False
    planned.completed_activity_id = None

    run = _act("run", 16130, 3600)
    walk = _act("walking", 1560, 2000)
    past = date(2026, 4, 22)
    today = date(2026, 4, 23)
    assert get_day_status(planned, [run, walk], past, today=today) == "completed"


def test_get_day_status_cross_training_only_today_is_future():
    planned = MagicMock()
    planned.workout_type = "easy"
    planned.target_distance_km = 10.0
    planned.completed = False
    planned.skipped = False
    planned.completed_activity_id = None

    walk = _act("walking", 5000, 1000)
    today = date(2026, 4, 23)
    assert get_day_status(planned, [walk], today, today=today) == "future"
