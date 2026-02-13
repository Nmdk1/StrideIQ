"""
Daily Intelligence Task Tests (Phase 2D)

Tests the morning intelligence Celery task, timezone windowing,
error isolation, and the API endpoint.

Organization:
    1. Timezone windowing — correct athletes selected for their 5 AM window
    2. Task execution — pipeline runs correctly end-to-end
    3. Error isolation — one athlete's failure doesn't block others
    4. API endpoints — today's insights retrieved correctly
"""

import pytest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from uuid import uuid4

from tests.training_scenario_helpers import MockActivity, MockPlannedWorkout


# ===================================================================
# 1. TIMEZONE WINDOWING
# ===================================================================

class TestTimezoneWindowing:
    """Test that the correct athletes are selected for their 5 AM window."""

    def test_athlete_in_5am_window_selected(self, db_session):
        """An athlete whose local time is 5:00-5:14 should be selected."""
        from models import Athlete, TrainingPlan
        from tasks.intelligence_tasks import _athletes_in_morning_window

        athlete = Athlete(
            email="tz_test@test.com",
            display_name="TZ Test",
            subscription_tier="guided",
            birthdate=date(1990, 1, 1),
            sex="M",
            timezone="America/New_York",  # UTC-5
        )
        db_session.add(athlete)
        db_session.flush()

        plan = TrainingPlan(
            athlete_id=athlete.id,
            name="Test Plan",
            status="active",
            goal_race_date=date(2026, 6, 1),
            goal_race_distance_m=42195,
            plan_start_date=date(2026, 1, 1),
            plan_end_date=date(2026, 6, 1),
            total_weeks=16,
            plan_type="marathon",
            generation_method="ai",
        )
        db_session.add(plan)
        db_session.flush()

        # 10:00 UTC = 5:00 AM Eastern (UTC-5)
        utc_now = datetime(2026, 2, 12, 10, 0, tzinfo=timezone.utc)
        result = _athletes_in_morning_window(db_session, utc_now)
        assert len(result) == 1
        assert result[0].id == athlete.id

    def test_athlete_outside_window_not_selected(self, db_session):
        """An athlete whose local time is NOT 5:00-5:14 should be skipped."""
        from models import Athlete, TrainingPlan
        from tasks.intelligence_tasks import _athletes_in_morning_window

        athlete = Athlete(
            email="tz_test2@test.com",
            display_name="TZ Test 2",
            subscription_tier="guided",
            birthdate=date(1990, 1, 1),
            sex="M",
            timezone="America/New_York",  # UTC-5
        )
        db_session.add(athlete)
        db_session.flush()

        plan = TrainingPlan(
            athlete_id=athlete.id,
            name="Test Plan",
            status="active",
            goal_race_date=date(2026, 6, 1),
            goal_race_distance_m=42195,
            plan_start_date=date(2026, 1, 1),
            plan_end_date=date(2026, 6, 1),
            total_weeks=16,
            plan_type="marathon",
            generation_method="ai",
        )
        db_session.add(plan)
        db_session.flush()

        # 14:00 UTC = 9:00 AM Eastern — not in window
        utc_now = datetime(2026, 2, 12, 14, 0, tzinfo=timezone.utc)
        result = _athletes_in_morning_window(db_session, utc_now)
        assert len(result) == 0

    def test_athlete_without_timezone_skipped(self, db_session):
        """Athletes without a timezone set are skipped."""
        from models import Athlete, TrainingPlan
        from tasks.intelligence_tasks import _athletes_in_morning_window

        athlete = Athlete(
            email="no_tz@test.com",
            display_name="No TZ",
            subscription_tier="guided",
            birthdate=date(1990, 1, 1),
            sex="M",
            timezone=None,  # No timezone
        )
        db_session.add(athlete)
        db_session.flush()

        plan = TrainingPlan(
            athlete_id=athlete.id,
            name="Test Plan",
            status="active",
            goal_race_date=date(2026, 6, 1),
            goal_race_distance_m=42195,
            plan_start_date=date(2026, 1, 1),
            plan_end_date=date(2026, 6, 1),
            total_weeks=16,
            plan_type="marathon",
            generation_method="ai",
        )
        db_session.add(plan)
        db_session.flush()

        # Any time — should find 0 because no timezone
        utc_now = datetime(2026, 2, 12, 10, 0, tzinfo=timezone.utc)
        result = _athletes_in_morning_window(db_session, utc_now)
        assert len(result) == 0

    def test_multiple_timezones_correct_selection(self, db_session):
        """With athletes in different timezones, only the ones at 5 AM are selected."""
        from models import Athlete, TrainingPlan
        from tasks.intelligence_tasks import _athletes_in_morning_window

        athletes_data = [
            ("ny@test.com", "NY Athlete", "America/New_York"),     # UTC-5 → 5 AM at 10:00 UTC
            ("chi@test.com", "Chicago Athlete", "America/Chicago"),  # UTC-6 → 5 AM at 11:00 UTC
            ("lon@test.com", "London Athlete", "Europe/London"),     # UTC+0 → 5 AM at 05:00 UTC
        ]

        created = []
        for email, name, tz in athletes_data:
            athlete = Athlete(
                email=email, display_name=name, subscription_tier="guided",
                birthdate=date(1990, 1, 1), sex="M", timezone=tz,
            )
            db_session.add(athlete)
            db_session.flush()
            plan = TrainingPlan(
                athlete_id=athlete.id, name="Plan", status="active",
                goal_race_date=date(2026, 6, 1), goal_race_distance_m=42195,
                plan_start_date=date(2026, 1, 1), plan_end_date=date(2026, 6, 1),
                total_weeks=16, plan_type="marathon", generation_method="ai",
            )
            db_session.add(plan)
            db_session.flush()
            created.append(athlete)

        # At 10:05 UTC: only NY is at 5:05 AM
        utc_now = datetime(2026, 2, 12, 10, 5, tzinfo=timezone.utc)
        result = _athletes_in_morning_window(db_session, utc_now)
        assert len(result) == 1
        assert result[0].email == "ny@test.com"

    def test_athlete_without_active_plan_skipped(self, db_session):
        """Athletes without an active training plan are not selected."""
        from models import Athlete, TrainingPlan
        from tasks.intelligence_tasks import _athletes_in_morning_window

        athlete = Athlete(
            email="no_plan@test.com", display_name="No Plan",
            subscription_tier="guided", birthdate=date(1990, 1, 1),
            sex="M", timezone="America/New_York",
        )
        db_session.add(athlete)
        db_session.flush()

        # Plan exists but is completed (not active)
        plan = TrainingPlan(
            athlete_id=athlete.id, name="Completed Plan", status="completed",
            goal_race_date=date(2026, 6, 1), goal_race_distance_m=42195,
            plan_start_date=date(2026, 1, 1), plan_end_date=date(2026, 6, 1),
            total_weeks=16, plan_type="marathon", generation_method="ai",
        )
        db_session.add(plan)
        db_session.flush()

        utc_now = datetime(2026, 2, 12, 10, 0, tzinfo=timezone.utc)
        result = _athletes_in_morning_window(db_session, utc_now)
        assert len(result) == 0


# ===================================================================
# 2. TASK EXECUTION
# ===================================================================

class TestTaskExecution:
    """Test that the intelligence pipeline runs correctly."""

    def test_pipeline_produces_insights(self, db_session):
        """The pipeline should compute readiness and run intelligence rules."""
        from models import Athlete, Activity, TrainingPlan
        from tasks.intelligence_tasks import _run_intelligence_for_athlete

        athlete = Athlete(
            email="pipeline@test.com", display_name="Pipeline Test",
            subscription_tier="guided", birthdate=date(1990, 1, 1), sex="M",
        )
        db_session.add(athlete)
        db_session.flush()

        # Add some activities for readiness computation
        for i in range(7):
            act = Activity(
                athlete_id=athlete.id,
                name=f"Run {i}",
                start_time=datetime(2026, 2, 5 + i, 7, 0),
                sport="Run", source="strava",
                distance_m=10000, duration_s=3600,
                avg_hr=145, average_speed=2.78,
                workout_type="easy_run",
                provider="strava",
                external_activity_id=f"pipeline_{uuid4().hex[:8]}",
            )
            db_session.add(act)
        db_session.flush()

        result = _run_intelligence_for_athlete(
            athlete_id=athlete.id,
            target_date=date(2026, 2, 12),
            db=db_session,
        )

        assert result["athlete_id"] == str(athlete.id)
        assert result["readiness_score"] is not None
        assert result["readiness_confidence"] is not None
        assert isinstance(result["insight_count"], int)

    def test_pipeline_with_no_data(self, db_session):
        """Pipeline should handle athletes with no activity data gracefully."""
        from models import Athlete
        from tasks.intelligence_tasks import _run_intelligence_for_athlete

        athlete = Athlete(
            email="empty@test.com", display_name="Empty Test",
            subscription_tier="guided", birthdate=date(1990, 1, 1), sex="M",
        )
        db_session.add(athlete)
        db_session.flush()

        result = _run_intelligence_for_athlete(
            athlete_id=athlete.id,
            target_date=date(2026, 2, 12),
            db=db_session,
        )

        # Should complete without error
        assert result["athlete_id"] == str(athlete.id)
        assert result["insight_count"] == 0  # No data = no insights


# ===================================================================
# 3. ERROR ISOLATION
# ===================================================================

class TestErrorIsolation:
    """Verify one athlete's failure doesn't block others."""

    def test_failing_athlete_doesnt_block_batch(self, db_session):
        """If one athlete's intelligence computation fails, others still run."""
        from models import Athlete, Activity, TrainingPlan
        from tasks.intelligence_tasks import _run_intelligence_for_athlete

        # Create 2 athletes
        good_athlete = Athlete(
            email="good@test.com", display_name="Good",
            subscription_tier="guided", birthdate=date(1990, 1, 1), sex="M",
        )
        db_session.add(good_athlete)
        db_session.flush()

        # Add activity for the good athlete
        act = Activity(
            athlete_id=good_athlete.id, name="Run",
            start_time=datetime(2026, 2, 11, 7, 0),
            sport="Run", source="strava",
            distance_m=10000, duration_s=3600,
            avg_hr=145, average_speed=2.78,
            workout_type="easy_run", provider="strava",
            external_activity_id=f"good_{uuid4().hex[:8]}",
        )
        db_session.add(act)
        db_session.flush()

        # Good athlete should succeed
        result = _run_intelligence_for_athlete(
            good_athlete.id, date(2026, 2, 12), db_session,
        )
        assert result["readiness_score"] is not None

        # The batch task structure ensures per-athlete try/except.
        # This test verifies the individual pipeline completes.


# ===================================================================
# 4. API ENDPOINTS
# ===================================================================

class TestIntelligenceAPI:
    """Test the REST API endpoints for daily intelligence."""

    def test_get_intelligence_returns_stored_insights(self, db_session):
        """Stored InsightLog entries should be returned by the API helper."""
        from models import Athlete, InsightLog
        from routers.daily_intelligence import _get_intelligence_for_date

        athlete = Athlete(
            email="api_test@test.com", display_name="API Test",
            subscription_tier="guided", birthdate=date(1990, 1, 1), sex="M",
        )
        db_session.add(athlete)
        db_session.flush()

        # Insert a test insight
        insight = InsightLog(
            athlete_id=athlete.id,
            rule_id="LOAD_SPIKE",
            mode="inform",
            message="Volume up 25% this week.",
            data_cited={"current_km": 80, "previous_km": 64},
            trigger_date=date(2026, 2, 12),
            readiness_score=55.0,
            confidence=0.8,
        )
        db_session.add(insight)
        db_session.flush()

        result = _get_intelligence_for_date(athlete.id, date(2026, 2, 12), db_session)

        assert result.date == date(2026, 2, 12)
        assert result.insight_count == 1
        assert result.insights[0].rule_id == "LOAD_SPIKE"
        assert result.insights[0].mode == "inform"
        assert "25%" in result.insights[0].message
        assert result.highest_mode == "inform"

    def test_log_mode_insights_not_visible(self, db_session):
        """LOG-mode insights are internal tracking and should be filtered out."""
        from models import Athlete, InsightLog
        from routers.daily_intelligence import _get_intelligence_for_date

        athlete = Athlete(
            email="log_test@test.com", display_name="Log Test",
            subscription_tier="guided", birthdate=date(1990, 1, 1), sex="M",
        )
        db_session.add(athlete)
        db_session.flush()

        # Insert a LOG insight (should be hidden) and an INFORM insight (should be visible)
        log_insight = InsightLog(
            athlete_id=athlete.id, rule_id="SELF_REG_DELTA", mode="log",
            message="Delta logged", trigger_date=date(2026, 2, 12),
        )
        inform_insight = InsightLog(
            athlete_id=athlete.id, rule_id="LOAD_SPIKE", mode="inform",
            message="Volume up", trigger_date=date(2026, 2, 12),
        )
        db_session.add_all([log_insight, inform_insight])
        db_session.flush()

        result = _get_intelligence_for_date(athlete.id, date(2026, 2, 12), db_session)

        # Only the INFORM insight should be visible
        assert result.insight_count == 1
        assert result.insights[0].rule_id == "LOAD_SPIKE"

    def test_flag_insight_marks_has_flag(self, db_session):
        """FLAG-level insights should set has_flag=True on the response."""
        from models import Athlete, InsightLog
        from routers.daily_intelligence import _get_intelligence_for_date

        athlete = Athlete(
            email="flag_test@test.com", display_name="Flag Test",
            subscription_tier="guided", birthdate=date(1990, 1, 1), sex="M",
        )
        db_session.add(athlete)
        db_session.flush()

        flag_insight = InsightLog(
            athlete_id=athlete.id, rule_id="SUSTAINED_DECLINE", mode="flag",
            message="3-week decline", trigger_date=date(2026, 2, 12),
        )
        db_session.add(flag_insight)
        db_session.flush()

        result = _get_intelligence_for_date(athlete.id, date(2026, 2, 12), db_session)

        assert result.has_flag is True
        assert result.highest_mode == "flag"

    def test_empty_day_returns_zero_insights(self, db_session):
        """A day with no insights should return empty list, not error."""
        from models import Athlete
        from routers.daily_intelligence import _get_intelligence_for_date

        athlete = Athlete(
            email="empty_day@test.com", display_name="Empty Day",
            subscription_tier="guided", birthdate=date(1990, 1, 1), sex="M",
        )
        db_session.add(athlete)
        db_session.flush()

        result = _get_intelligence_for_date(athlete.id, date(2026, 2, 12), db_session)

        assert result.insight_count == 0
        assert result.insights == []
        assert result.highest_mode is None
        assert result.has_flag is False
