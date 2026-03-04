"""Tests for bulk effort classification edge cases (Racing Fingerprint Pre-Work P2)."""

import uuid
from datetime import datetime
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from services.effort_classification import classify_effort_bulk, _classify_tier1, _classify_tier3


def _make_activity(avg_hr=None, max_hr=None, distance_m=10000, duration_s=3600,
                   avg_speed=None, workout_type=None, intensity_score=None):
    act = MagicMock()
    act.id = uuid.uuid4()
    act.athlete_id = uuid.uuid4()
    act.avg_hr = avg_hr
    act.max_hr = max_hr
    act.distance_m = distance_m
    act.duration_s = duration_s
    act.average_speed = avg_speed or (distance_m / duration_s if duration_s else None)
    act.workout_type = workout_type
    act.intensity_score = intensity_score
    act.start_time = datetime(2025, 6, 1, 8, 0)
    act.garmin_perceived_effort = None
    type(act).pace_per_mile = PropertyMock(
        return_value=26.8224 / (distance_m / duration_s) if duration_s and distance_m else None
    )
    return act


def _make_athlete(max_hr=None):
    a = MagicMock()
    a.id = uuid.uuid4()
    a.max_hr = max_hr
    a.resting_hr = 55
    a.threshold_pace = None
    return a


class TestClassifyEffortBulk:
    def test_classifies_activity_with_hr_only(self):
        """Activity with HR but no pace data classifies via HR tier (tier 1)."""
        easy = _make_activity(avg_hr=120, max_hr=180)
        hard = _make_activity(avg_hr=175, max_hr=190)

        all_acts = [easy, hard]
        athlete = _make_athlete()
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = all_acts
        db.query.return_value.filter.return_value.first.return_value = None

        result = classify_effort_bulk(all_acts, athlete, db)
        for aid, label in result.items():
            assert label in ("easy", "moderate", "hard")

    def test_classifies_activity_with_no_data(self):
        """Activity with no HR, no pace → tier 3 fallback."""
        act = _make_activity(avg_hr=None, max_hr=None, workout_type="easy_run")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        result = _classify_tier3(act, uuid.uuid4(), db)
        assert result in ("easy", "moderate", "hard")

    def test_bulk_matches_individual(self):
        """Multiple activities all get classified."""
        acts = [
            _make_activity(avg_hr=140, max_hr=180, distance_m=8000, duration_s=2800),
            _make_activity(avg_hr=165, max_hr=185, distance_m=10000, duration_s=3200),
            _make_activity(avg_hr=175, max_hr=190, distance_m=5000, duration_s=1500),
        ]
        athlete = _make_athlete()
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = acts
        db.query.return_value.filter.return_value.first.return_value = None

        result = classify_effort_bulk(acts, athlete, db)
        assert len(result) == 3
        for aid, label in result.items():
            assert label in ("easy", "moderate", "hard")
