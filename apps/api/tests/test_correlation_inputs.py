"""
Tests for correlation engine input wiring.

Phase 1: GarminDay signals
Phase 2: Activity-level signals
Phase 3: Feedback/reflection signals
Phase 4: Checkin/composition/nutrition signals
Phase 5: Training pattern signals
Phase 6-9: FRIENDLY_NAMES, DIRECTION_EXPECTATIONS, CONFOUNDER_MAP, ban list
"""
import uuid
from datetime import datetime, timedelta, date, timezone
from unittest.mock import MagicMock

import pytest


# ── Phase 1: GarminDay ──

class TestPhase1GarminDay:

    def test_garmin_sleep_score_in_inputs(self, db_session, test_athlete):
        """GarminDay rows with sleep_score populate inputs['garmin_sleep_score']."""
        from models import GarminDay
        from services.correlation_engine import aggregate_daily_inputs

        gd = GarminDay(
            athlete_id=test_athlete.id,
            calendar_date=date.today(),
            sleep_score=82,
        )
        db_session.add(gd)
        db_session.commit()

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        inputs = aggregate_daily_inputs(str(test_athlete.id), start, end, db_session)

        assert "garmin_sleep_score" in inputs
        assert len(inputs["garmin_sleep_score"]) >= 1
        assert inputs["garmin_sleep_score"][0][1] == 82.0

    def test_garmin_body_battery_in_inputs(self, db_session, test_athlete):
        """body_battery_end populates inputs['garmin_body_battery_end']."""
        from models import GarminDay
        from services.correlation_engine import aggregate_daily_inputs

        gd = GarminDay(
            athlete_id=test_athlete.id,
            calendar_date=date.today(),
            body_battery_end=45,
        )
        db_session.add(gd)
        db_session.commit()

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        inputs = aggregate_daily_inputs(str(test_athlete.id), start, end, db_session)

        assert "garmin_body_battery_end" in inputs
        assert inputs["garmin_body_battery_end"][0][1] == 45.0

    def test_garmin_stress_in_inputs(self, db_session, test_athlete):
        """avg_stress populates inputs['garmin_avg_stress']."""
        from models import GarminDay
        from services.correlation_engine import aggregate_daily_inputs

        gd = GarminDay(
            athlete_id=test_athlete.id,
            calendar_date=date.today(),
            avg_stress=38,
        )
        db_session.add(gd)
        db_session.commit()

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        inputs = aggregate_daily_inputs(str(test_athlete.id), start, end, db_session)

        assert "garmin_avg_stress" in inputs
        assert inputs["garmin_avg_stress"][0][1] == 38.0

    def test_garmin_no_data_returns_empty(self, db_session, test_athlete):
        """No GarminDay rows → all garmin_* keys have empty lists."""
        from services.correlation_engine import aggregate_daily_inputs

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        inputs = aggregate_daily_inputs(str(test_athlete.id), start, end, db_session)

        for key in [
            "garmin_sleep_score", "garmin_body_battery_end",
            "garmin_avg_stress", "garmin_steps",
        ]:
            assert key in inputs
            assert inputs[key] == []

    def test_garmin_null_fields_excluded(self, db_session, test_athlete):
        """Rows with NULL fields produce empty series for those signals."""
        from models import GarminDay
        from services.correlation_engine import aggregate_daily_inputs

        gd = GarminDay(
            athlete_id=test_athlete.id,
            calendar_date=date.today(),
            sleep_score=None,
            body_battery_end=55,
        )
        db_session.add(gd)
        db_session.commit()

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        inputs = aggregate_daily_inputs(str(test_athlete.id), start, end, db_session)

        assert inputs["garmin_sleep_score"] == []
        assert len(inputs["garmin_body_battery_end"]) == 1


# ── Phase 2: Activity-level ──

class TestPhase2ActivityLevel:

    def _make_activity(self, db_session, test_athlete, **kwargs):
        from models import Activity
        defaults = dict(
            athlete_id=test_athlete.id,
            start_time=datetime.now(timezone.utc),
            sport="run",
            source="strava",
            distance_m=5000,
            duration_s=1500,
            avg_hr=145,
        )
        defaults.update(kwargs)
        a = Activity(**defaults)
        db_session.add(a)
        db_session.commit()
        return a

    def test_activity_dew_point_input(self, db_session, test_athlete):
        from services.correlation_engine import aggregate_activity_level_inputs
        self._make_activity(db_session, test_athlete, dew_point_f=62.5)
        end = datetime.now(timezone.utc) + timedelta(days=1)
        start = end - timedelta(days=7)
        inputs = aggregate_activity_level_inputs(str(test_athlete.id), start, end, db_session)
        assert "dew_point_f" in inputs
        assert inputs["dew_point_f"][0][1] == 62.5

    def test_activity_cadence_input(self, db_session, test_athlete):
        from services.correlation_engine import aggregate_activity_level_inputs
        self._make_activity(db_session, test_athlete, avg_cadence=178)
        end = datetime.now(timezone.utc) + timedelta(days=1)
        start = end - timedelta(days=7)
        inputs = aggregate_activity_level_inputs(str(test_athlete.id), start, end, db_session)
        assert "avg_cadence" in inputs
        assert inputs["avg_cadence"][0][1] == 178.0

    def test_activity_multi_run_day_takes_longest(self, db_session, test_athlete):
        """Two runs on same day → longest run's values used."""
        from services.correlation_engine import aggregate_activity_level_inputs
        morning = datetime(2026, 3, 10, 7, 0, tzinfo=timezone.utc)
        self._make_activity(
            db_session, test_athlete, start_time=morning, distance_m=3000,
            avg_cadence=170,
        )
        self._make_activity(
            db_session, test_athlete, start_time=morning + timedelta(hours=4),
            distance_m=10000, avg_cadence=180,
        )
        end = morning + timedelta(days=1)
        start = end - timedelta(days=7)
        inputs = aggregate_activity_level_inputs(str(test_athlete.id), start, end, db_session)
        assert inputs["avg_cadence"][0][1] == 180.0

    def test_activity_run_start_hour(self, db_session, test_athlete):
        from services.correlation_engine import aggregate_activity_level_inputs
        morning = datetime(2026, 3, 10, 6, 30, tzinfo=timezone.utc)
        self._make_activity(db_session, test_athlete, start_time=morning)
        end = morning + timedelta(days=1)
        start = end - timedelta(days=7)
        inputs = aggregate_activity_level_inputs(str(test_athlete.id), start, end, db_session)
        assert "run_start_hour" in inputs
        assert inputs["run_start_hour"][0][1] == 6.0

    def test_activity_elevation_input(self, db_session, test_athlete):
        from services.correlation_engine import aggregate_activity_level_inputs
        self._make_activity(db_session, test_athlete, total_elevation_gain=125.5)
        end = datetime.now(timezone.utc) + timedelta(days=1)
        start = end - timedelta(days=7)
        inputs = aggregate_activity_level_inputs(str(test_athlete.id), start, end, db_session)
        assert "elevation_gain_m" in inputs
        assert inputs["elevation_gain_m"][0][1] == 125.5


# ── Phase 3: Feedback/Reflection ──

class TestPhase3Feedback:

    def test_feedback_leg_feel_ordinal(self, db_session, test_athlete):
        from models import ActivityFeedback, Activity
        from services.correlation_engine import aggregate_feedback_inputs

        a = Activity(
            athlete_id=test_athlete.id, start_time=datetime.now(timezone.utc),
            sport="run", source="strava",
        )
        db_session.add(a)
        db_session.flush()

        fb = ActivityFeedback(
            activity_id=a.id, athlete_id=test_athlete.id,
            leg_feel="fresh",
            submitted_at=datetime.now(timezone.utc),
        )
        db_session.add(fb)
        db_session.commit()

        end = datetime.now(timezone.utc) + timedelta(days=1)
        start = end - timedelta(days=7)
        inputs = aggregate_feedback_inputs(str(test_athlete.id), start, end, db_session)
        assert "feedback_leg_feel" in inputs
        assert inputs["feedback_leg_feel"][0][1] == 5.0

    def test_reflection_ordinal(self, db_session, test_athlete):
        from models import ActivityReflection, Activity
        from services.correlation_engine import aggregate_feedback_inputs

        a = Activity(
            athlete_id=test_athlete.id, start_time=datetime.now(timezone.utc),
            sport="run", source="strava",
        )
        db_session.add(a)
        db_session.flush()

        ref = ActivityReflection(
            activity_id=a.id, athlete_id=test_athlete.id,
            response="easier",
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(ref)
        db_session.commit()

        end = datetime.now(timezone.utc) + timedelta(days=1)
        start = end - timedelta(days=7)
        inputs = aggregate_feedback_inputs(str(test_athlete.id), start, end, db_session)
        assert "reflection_vs_expected" in inputs
        assert inputs["reflection_vs_expected"][0][1] == 1.0

    def test_feedback_empty_when_no_data(self, db_session, test_athlete):
        from services.correlation_engine import aggregate_feedback_inputs
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        inputs = aggregate_feedback_inputs(str(test_athlete.id), start, end, db_session)
        assert inputs == {}


# ── Phase 4: Checkin/Composition/Nutrition ──

class TestPhase4CheckinComposition:

    def test_sleep_quality_in_inputs(self, db_session, test_athlete):
        from models import DailyCheckin
        from services.correlation_engine import aggregate_daily_inputs

        dc = DailyCheckin(
            athlete_id=test_athlete.id,
            date=date.today(),
            sleep_quality_1_5=4,
        )
        db_session.add(dc)
        db_session.commit()

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        inputs = aggregate_daily_inputs(str(test_athlete.id), start, end, db_session)
        assert "sleep_quality_1_5" in inputs
        assert inputs["sleep_quality_1_5"][0][1] == 4.0

    def test_body_fat_pct_in_inputs(self, db_session, test_athlete):
        from models import BodyComposition
        from services.correlation_engine import aggregate_daily_inputs

        bc = BodyComposition(
            athlete_id=test_athlete.id,
            date=date.today(),
            body_fat_pct=15.2,
        )
        db_session.add(bc)
        db_session.commit()

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        inputs = aggregate_daily_inputs(str(test_athlete.id), start, end, db_session)
        assert "body_fat_pct" in inputs
        assert inputs["body_fat_pct"][0][1] == 15.2

    def test_daily_calories_in_inputs(self, db_session, test_athlete):
        from models import NutritionEntry
        from services.correlation_engine import aggregate_daily_inputs

        n1 = NutritionEntry(
            athlete_id=test_athlete.id,
            date=date.today(),
            calories=800,
            entry_type="daily",
        )
        n2 = NutritionEntry(
            athlete_id=test_athlete.id,
            date=date.today(),
            calories=1200,
            entry_type="daily",
        )
        db_session.add_all([n1, n2])
        db_session.commit()

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        inputs = aggregate_daily_inputs(str(test_athlete.id), start, end, db_session)
        assert "daily_calories" in inputs
        assert inputs["daily_calories"][0][1] == 2000.0


# ── Phase 5: Training Patterns ──

class TestPhase5TrainingPatterns:

    def _make_run(self, db_session, test_athlete, days_ago, distance_m=5000, workout_type=None):
        from models import Activity
        a = Activity(
            athlete_id=test_athlete.id,
            start_time=datetime.now(timezone.utc) - timedelta(days=days_ago),
            sport="run", source="strava",
            distance_m=distance_m, duration_s=1500, avg_hr=140,
            workout_type=workout_type,
        )
        db_session.add(a)
        return a

    def test_days_since_quality(self, db_session, test_athlete):
        from services.correlation_engine import aggregate_training_pattern_inputs
        self._make_run(db_session, test_athlete, days_ago=3, workout_type="intervals")
        self._make_run(db_session, test_athlete, days_ago=2)
        self._make_run(db_session, test_athlete, days_ago=1)
        db_session.commit()

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        inputs = aggregate_training_pattern_inputs(str(test_athlete.id), start, end, db_session)
        assert "days_since_quality" in inputs
        values = {d: v for d, v in inputs["days_since_quality"]}
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
        assert values.get(yesterday) == 2.0

    def test_consecutive_run_days(self, db_session, test_athlete):
        from services.correlation_engine import aggregate_training_pattern_inputs
        self._make_run(db_session, test_athlete, days_ago=3)
        self._make_run(db_session, test_athlete, days_ago=2)
        self._make_run(db_session, test_athlete, days_ago=1)
        db_session.commit()

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        inputs = aggregate_training_pattern_inputs(str(test_athlete.id), start, end, db_session)
        assert "consecutive_run_days" in inputs
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
        values = {d: v for d, v in inputs["consecutive_run_days"]}
        assert values.get(yesterday) == 3.0

    def test_weekly_volume_km(self, db_session, test_athlete):
        from services.correlation_engine import aggregate_training_pattern_inputs
        self._make_run(db_session, test_athlete, days_ago=1, distance_m=10000)
        self._make_run(db_session, test_athlete, days_ago=2, distance_m=5000)
        db_session.commit()

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        inputs = aggregate_training_pattern_inputs(str(test_athlete.id), start, end, db_session)
        assert "weekly_volume_km" in inputs
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
        values = {d: v for d, v in inputs["weekly_volume_km"]}
        assert values.get(yesterday) == 15.0

    def test_long_run_ratio(self, db_session, test_athlete):
        from services.correlation_engine import aggregate_training_pattern_inputs
        self._make_run(db_session, test_athlete, days_ago=1, distance_m=20000)
        self._make_run(db_session, test_athlete, days_ago=3, distance_m=5000)
        self._make_run(db_session, test_athlete, days_ago=5, distance_m=5000)
        self._make_run(db_session, test_athlete, days_ago=6, distance_m=5000)
        self._make_run(db_session, test_athlete, days_ago=7, distance_m=5000)
        db_session.commit()

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=10)
        inputs = aggregate_training_pattern_inputs(str(test_athlete.id), start, end, db_session)
        assert "long_run_ratio" in inputs
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
        values = {d: v for d, v in inputs["long_run_ratio"]}
        assert values.get(yesterday) == 0.5


# ── Phase 6-9: Integration ──

class TestPhaseIntegration:

    def test_friendly_names_cover_all_new_inputs(self):
        """Every new input key has a FRIENDLY_NAMES entry."""
        from services.n1_insight_generator import FRIENDLY_NAMES

        ALL_NEW_KEYS = [
            # GarminDay
            "garmin_sleep_score", "garmin_sleep_deep_s", "garmin_sleep_rem_s",
            "garmin_sleep_awake_s", "garmin_body_battery_end",
            "garmin_avg_stress", "garmin_max_stress", "garmin_steps",
            "garmin_active_time_s", "garmin_moderate_intensity_s",
            "garmin_vigorous_intensity_s", "garmin_hrv_5min_high",
            "garmin_min_hr", "garmin_vo2max",
            # Activity
            "dew_point_f", "heat_adjustment_pct", "temperature_f",
            "humidity_pct", "elevation_gain_m", "avg_cadence",
            "avg_stride_length_m", "avg_ground_contact_ms",
            "avg_vertical_oscillation_cm", "avg_vertical_ratio_pct",
            "avg_power_w", "garmin_aerobic_te", "garmin_anaerobic_te",
            "garmin_perceived_effort", "garmin_body_battery_impact",
            "activity_intensity_score", "active_kcal", "run_start_hour",
            # Feedback
            "feedback_perceived_effort", "feedback_energy_pre",
            "feedback_energy_post", "feedback_leg_feel",
            "reflection_vs_expected",
            # Checkin/comp/nutrition
            "sleep_quality_1_5", "body_fat_pct", "muscle_mass_kg",
            "daily_fat_g", "daily_fiber_g", "daily_calories",
            # Training patterns
            "days_since_quality", "consecutive_run_days",
            "days_since_rest", "weekly_volume_km", "long_run_ratio",
            "weekly_elevation_m",
        ]

        missing = [k for k in ALL_NEW_KEYS if k not in FRIENDLY_NAMES]
        assert missing == [], f"Missing FRIENDLY_NAMES: {missing}"

    def test_no_new_inputs_on_ban_list(self):
        """No new input key appears in _VOICE_INTERNAL_METRICS."""
        import importlib

        home_mod = importlib.import_module("routers.home")
        ban_list = getattr(home_mod, "_VOICE_INTERNAL_METRICS", [])

        ALL_NEW_KEYS = [
            "garmin_sleep_score", "garmin_body_battery_end",
            "dew_point_f", "avg_cadence", "feedback_leg_feel",
            "sleep_quality_1_5", "days_since_quality",
        ]

        banned = [k for k in ALL_NEW_KEYS if k in ban_list]
        assert banned == [], f"These should NOT be banned: {banned}"
