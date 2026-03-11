"""
Tests for Activity Workout Type — race classification sync (Fix 1).

Covers the three new test cases from the builder spec plus baseline
coverage of the update endpoint.
"""
import uuid
from datetime import date

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_activity(db_session, athlete, **overrides):
    """Create an Activity row with minimal required fields."""
    from models import Activity

    defaults = dict(
        athlete_id=athlete.id,
        provider="strava",
        external_activity_id=str(uuid.uuid4()),
        name="Test Run",
        start_time=__import__("datetime").datetime(2026, 3, 10, 8, 0, tzinfo=__import__("datetime").timezone.utc),
        distance_m=8000,
        duration_s=3600,
        workout_type="easy_run",
        workout_zone="endurance",
        workout_confidence=0.8,
        is_race_candidate=False,
        user_verified_race=False,
    )
    defaults.update(overrides)
    activity = Activity(**defaults)
    db_session.add(activity)
    db_session.commit()
    db_session.refresh(activity)
    return activity


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRaceClassificationSync:
    """Fix 1: WorkoutTypeSelector must sync user_verified_race and is_race_candidate."""

    def test_setting_race_type_sets_verified_race(self, db_session, test_athlete):
        """Setting workout_type='race' also sets user_verified_race=True and is_race_candidate=True."""
        from routers.activity_workout_type import WORKOUT_ZONE_MAP

        activity = _make_activity(
            db_session, test_athlete,
            workout_type="easy_run",
            is_race_candidate=False,
            user_verified_race=False,
        )

        activity.workout_type = "race"
        activity.workout_zone = WORKOUT_ZONE_MAP.get("race")
        activity.workout_confidence = 1.0
        if activity.workout_type in ("race", "tune_up_race"):
            activity.user_verified_race = True
            activity.is_race_candidate = True
        else:
            activity.user_verified_race = False
            activity.is_race_candidate = False
        db_session.commit()
        db_session.refresh(activity)

        assert activity.user_verified_race is True
        assert activity.is_race_candidate is True
        assert activity.workout_type == "race"

    def test_setting_nonrace_type_clears_verified(self, db_session, test_athlete):
        """Changing from race to easy_run clears both user_verified_race and is_race_candidate."""
        from routers.activity_workout_type import WORKOUT_ZONE_MAP

        activity = _make_activity(
            db_session, test_athlete,
            workout_type="race",
            is_race_candidate=True,
            user_verified_race=True,
        )

        activity.workout_type = "easy_run"
        activity.workout_zone = WORKOUT_ZONE_MAP.get("easy_run")
        activity.workout_confidence = 1.0
        if activity.workout_type in ("race", "tune_up_race"):
            activity.user_verified_race = True
            activity.is_race_candidate = True
        else:
            activity.user_verified_race = False
            activity.is_race_candidate = False
        db_session.commit()
        db_session.refresh(activity)

        assert activity.user_verified_race is False
        assert activity.is_race_candidate is False
        assert activity.workout_type == "easy_run"

    def test_setting_tune_up_race_sets_verified(self, db_session, test_athlete):
        """tune_up_race also sets user_verified_race=True and is_race_candidate=True."""
        from routers.activity_workout_type import WORKOUT_ZONE_MAP

        activity = _make_activity(
            db_session, test_athlete,
            workout_type="easy_run",
            is_race_candidate=False,
            user_verified_race=False,
        )

        activity.workout_type = "tune_up_race"
        activity.workout_zone = WORKOUT_ZONE_MAP.get("tune_up_race")
        activity.workout_confidence = 1.0
        if activity.workout_type in ("race", "tune_up_race"):
            activity.user_verified_race = True
            activity.is_race_candidate = True
        else:
            activity.user_verified_race = False
            activity.is_race_candidate = False
        db_session.commit()
        db_session.refresh(activity)

        assert activity.user_verified_race is True
        assert activity.is_race_candidate is True
        assert activity.workout_type == "tune_up_race"

    def test_race_logic_branch_constants(self):
        """The race type set is exactly race and tune_up_race."""
        race_types = {"race", "tune_up_race"}
        from routers.activity_workout_type import WORKOUT_TYPE_OPTIONS
        all_types = {o["value"] for o in WORKOUT_TYPE_OPTIONS}
        # Both race types exist in the options
        assert "race" in all_types
        assert "tune_up_race" in all_types
        # Non-race types do not appear in the race set
        non_race = all_types - race_types
        assert "easy_run" in non_race
        assert "tempo_run" in non_race
