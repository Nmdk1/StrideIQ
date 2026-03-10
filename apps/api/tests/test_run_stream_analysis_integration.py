"""Category 2 — Integration Tests for run stream analysis.

Tests the full path: DB activity + stream → coach tool → structured response.
Uses transactional rollback via db_session fixture.

AC coverage:
    AC-7: Error contract (STREAMS_NOT_FOUND, STREAMS_UNAVAILABLE, etc.)
    Tool response envelope contract (ok, tool, generated_at, activity_id, errors, analysis)
"""
import sys
import os
import pytest
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cryptography.fernet import Fernet
from models import Activity, ActivityStream, Athlete, PlannedWorkout, TrainingPlan
from fixtures.stream_fixtures import make_easy_run_stream, make_interval_stream


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _ensure_encryption_key():
    """Ensure valid Fernet key for token encryption."""
    import services.token_encryption as te_mod
    key = Fernet.generate_key().decode()
    old_val = os.environ.get("TOKEN_ENCRYPTION_KEY")
    os.environ["TOKEN_ENCRYPTION_KEY"] = key
    te_mod._token_encryption = None
    yield
    te_mod._token_encryption = None
    if old_val is not None:
        os.environ["TOKEN_ENCRYPTION_KEY"] = old_val
    elif "TOKEN_ENCRYPTION_KEY" in os.environ:
        del os.environ["TOKEN_ENCRYPTION_KEY"]


@pytest.fixture
def test_athlete(db_session):
    """Create a test athlete."""
    from services.token_encryption import encrypt_token
    athlete = Athlete(
        email=f"stream_analysis_{uuid4()}@example.com",
        display_name="Stream Analysis Test",
        subscription_tier="free",
        birthdate=date(1990, 1, 1),
        sex="M",
        strava_access_token=encrypt_token("fake_token"),
        strava_refresh_token=encrypt_token("fake_refresh"),
        strava_athlete_id=99999,
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)
    return athlete


@pytest.fixture
def activity_with_stream(db_session, test_athlete):
    """Activity with successfully fetched stream data."""
    activity = Activity(
        athlete_id=test_athlete.id,
        name="Test Easy Run",
        start_time=datetime.now(timezone.utc) - timedelta(days=1),
        sport="run",
        source="strava",
        provider="strava",
        external_activity_id="stream_analysis_test_1",
        duration_s=3600,
        distance_m=10000,
        avg_hr=145,
        stream_fetch_status="success",
    )
    db_session.add(activity)
    db_session.commit()

    stream_data = make_easy_run_stream(duration_s=3600)
    stream = ActivityStream(
        activity_id=activity.id,
        stream_data=stream_data,
        channels_available=list(stream_data.keys()),
        point_count=3600,
        source="strava",
    )
    db_session.add(stream)
    db_session.commit()
    db_session.refresh(activity)
    return activity


@pytest.fixture
def activity_no_stream(db_session, test_athlete):
    """Activity with pending stream fetch (no stream data yet)."""
    activity = Activity(
        athlete_id=test_athlete.id,
        name="Pending Stream Run",
        start_time=datetime.now(timezone.utc) - timedelta(days=2),
        sport="run",
        source="strava",
        provider="strava",
        external_activity_id="stream_analysis_test_2",
        duration_s=1800,
        distance_m=5000,
        stream_fetch_status="pending",
    )
    db_session.add(activity)
    db_session.commit()
    db_session.refresh(activity)
    return activity


@pytest.fixture
def activity_unavailable_stream(db_session, test_athlete):
    """Manual activity with unavailable streams (terminal)."""
    activity = Activity(
        athlete_id=test_athlete.id,
        name="Manual Run",
        start_time=datetime.now(timezone.utc) - timedelta(days=3),
        sport="run",
        source="manual",
        provider=None,
        external_activity_id=None,
        duration_s=1800,
        distance_m=5000,
        stream_fetch_status="unavailable",
    )
    db_session.add(activity)
    db_session.commit()
    db_session.refresh(activity)
    return activity


# ===========================================================================
# TOOL RESPONSE ENVELOPE
# ===========================================================================

class TestToolResponseEnvelope:
    """Coach tool response follows the standard contract."""

    def test_success_response_has_required_fields(self, db_session, test_athlete, activity_with_stream):
        """Successful analysis → ok=True, tool name, generated_at, analysis populated."""
        from services.coach_tools import analyze_run_streams

        result = analyze_run_streams(db_session, test_athlete.id, activity_id=str(activity_with_stream.id))

        assert result["ok"] is True
        assert result["tool"] == "analyze_run_streams"
        assert "generated_at" in result
        assert result["data"]["activity_id"] == str(activity_with_stream.id)
        assert "analysis" in result["data"]
        assert result["data"]["errors"] == []

    def test_analysis_has_all_schema_fields(self, db_session, test_athlete, activity_with_stream):
        """Analysis object contains all fields from the typed schema."""
        from services.coach_tools import analyze_run_streams

        result = analyze_run_streams(db_session, test_athlete.id, activity_id=str(activity_with_stream.id))
        analysis = result["data"]["analysis"]

        assert "segments" in analysis
        assert "drift" in analysis
        assert "moments" in analysis
        assert "plan_comparison" in analysis
        assert "channels_present" in analysis
        assert "channels_missing" in analysis
        assert "point_count" in analysis
        assert "confidence" in analysis

    def test_drift_has_all_fields(self, db_session, test_athlete, activity_with_stream):
        """Drift object has cardiac_pct, pace_pct, cadence_trend_bpm_per_km."""
        from services.coach_tools import analyze_run_streams

        result = analyze_run_streams(db_session, test_athlete.id, activity_id=str(activity_with_stream.id))
        drift = result["data"]["analysis"]["drift"]

        assert "cardiac_pct" in drift
        assert "pace_pct" in drift
        assert "cadence_trend_bpm_per_km" in drift


# ===========================================================================
# ERROR PATHS — AC-7
# ===========================================================================

class TestErrorPaths:
    """Error contract: typed errors for various failure modes."""

    def test_streams_not_found_pending(self, db_session, test_athlete, activity_no_stream):
        """Activity with pending stream → STREAMS_NOT_FOUND error."""
        from services.coach_tools import analyze_run_streams

        result = analyze_run_streams(db_session, test_athlete.id, activity_id=str(activity_no_stream.id))

        assert result["ok"] is False or len(result["data"]["errors"]) > 0
        error_codes = [e["code"] for e in result["data"]["errors"]]
        assert "STREAMS_NOT_FOUND" in error_codes

    def test_streams_unavailable_manual(self, db_session, test_athlete, activity_unavailable_stream):
        """Manual activity (unavailable) → STREAMS_UNAVAILABLE error, non-retryable."""
        from services.coach_tools import analyze_run_streams

        result = analyze_run_streams(db_session, test_athlete.id, activity_id=str(activity_unavailable_stream.id))

        assert result["ok"] is False or len(result["data"]["errors"]) > 0
        errors = result["data"]["errors"]
        error_codes = [e["code"] for e in errors]
        assert "STREAMS_UNAVAILABLE" in error_codes
        # Non-retryable
        unavail_error = next(e for e in errors if e["code"] == "STREAMS_UNAVAILABLE")
        assert unavail_error["retryable"] is False

    def test_nonexistent_activity_returns_error(self, db_session, test_athlete):
        """Activity ID that doesn't exist → error response."""
        from services.coach_tools import analyze_run_streams

        result = analyze_run_streams(db_session, test_athlete.id, activity_id=str(uuid4()))

        assert result["ok"] is False

    def test_wrong_athlete_cannot_access(self, db_session, test_athlete, activity_with_stream):
        """Different athlete_id → cannot access another's activity."""
        from services.coach_tools import analyze_run_streams

        other_athlete_id = uuid4()
        result = analyze_run_streams(db_session, other_athlete_id, activity_id=str(activity_with_stream.id))

        assert result["ok"] is False


# ===========================================================================
# PLAN-LINKED ACTIVITY
# ===========================================================================

class TestPlanLinkedActivity:
    """Integration: activity linked to planned workout → plan_comparison populated."""

    def test_plan_linked_activity_has_comparison(self, db_session, test_athlete, activity_with_stream):
        """Activity with linked PlannedWorkout → plan_comparison is not None."""
        from services.coach_tools import analyze_run_streams

        # Create parent training plan (required FK)
        training_plan = TrainingPlan(
            athlete_id=test_athlete.id,
            name="Test Plan",
            status="active",
            goal_race_date=date(2026, 6, 1),
            goal_race_distance_m=42195,
            plan_start_date=date(2026, 1, 1),
            plan_end_date=date(2026, 6, 1),
            total_weeks=22,
            plan_type="marathon",
        )
        db_session.add(training_plan)
        db_session.commit()

        # Create a planned workout linked to this activity
        plan = PlannedWorkout(
            plan_id=training_plan.id,
            athlete_id=test_athlete.id,
            scheduled_date=activity_with_stream.start_time.date(),
            week_number=1,
            day_of_week=1,
            workout_type="easy",
            title="Easy 60 min",
            phase="base",
            target_duration_minutes=60,
            target_distance_km=10.0,
            target_pace_per_km_seconds=360,
            completed=True,
            completed_activity_id=activity_with_stream.id,
        )
        db_session.add(plan)
        db_session.commit()

        result = analyze_run_streams(db_session, test_athlete.id, activity_id=str(activity_with_stream.id))

        assert result["ok"] is True
        analysis = result["data"]["analysis"]
        assert analysis["plan_comparison"] is not None
        assert "planned_duration_min" in analysis["plan_comparison"]
        assert "actual_duration_min" in analysis["plan_comparison"]
        assert "duration_delta_min" in analysis["plan_comparison"]

    def test_no_plan_linked_has_null_comparison(self, db_session, test_athlete, activity_with_stream):
        """Activity with no PlannedWorkout → plan_comparison is None."""
        from services.coach_tools import analyze_run_streams

        result = analyze_run_streams(db_session, test_athlete.id, activity_id=str(activity_with_stream.id))

        assert result["ok"] is True
        assert result["data"]["analysis"]["plan_comparison"] is None


# ===========================================================================
# AI COACH DISPATCH — tool #24 is routable
# ===========================================================================

class TestAICoachDispatch:
    """Verify analyze_run_streams is declared and dispatchable by ai_coach."""

    def test_opus_tool_declarations_include_analyze_run_streams(self, db_session):
        """analyze_run_streams appears in the Opus tool list."""
        from unittest.mock import patch
        from services.ai_coach import AICoach

        with patch.object(AICoach, "__init__", lambda self, db: None):
            coach = AICoach(db_session)

        opus_tools = coach._opus_tools()
        tool_names = [t["name"] for t in opus_tools]
        assert "analyze_run_streams" in tool_names

        # Verify schema: activity_id is required
        tool_def = next(t for t in opus_tools if t["name"] == "analyze_run_streams")
        assert "activity_id" in tool_def["input_schema"]["properties"]
        assert "activity_id" in tool_def["input_schema"]["required"]

    def test_execute_opus_tool_routes_to_analyze_run_streams(self, db_session, test_athlete, activity_with_stream):
        """_execute_opus_tool dispatches analyze_run_streams, not 'Unknown tool'."""
        from unittest.mock import patch
        from services.ai_coach import AICoach
        import json

        with patch.object(AICoach, "__init__", lambda self, db: None):
            coach = AICoach(db_session)
        coach.db = db_session

        result_json = coach._execute_opus_tool(
            test_athlete.id,
            "analyze_run_streams",
            {"activity_id": str(activity_with_stream.id)},
        )
        result = json.loads(result_json)

        assert "error" not in result or result.get("ok") is True
        assert result["ok"] is True
        assert result["tool"] == "analyze_run_streams"
        assert result["data"]["analysis"] is not None


# ===========================================================================
# INTERVAL COUNT MATCH — plan segments flow through
# ===========================================================================

class TestIntervalCountMatch:
    """Verify planned_interval_count and interval_count_match populate when plan has segments."""

    def test_interval_count_populated_when_plan_has_segments(self, db_session, test_athlete):
        """PlannedWorkout with segments JSONB → interval_count_match is not None."""
        from services.coach_tools import analyze_run_streams

        # Create interval activity with stream
        stream_data = make_interval_stream(reps=5)
        activity = Activity(
            athlete_id=test_athlete.id,
            name="Interval Session",
            start_time=datetime.now(timezone.utc) - timedelta(days=1),
            sport="run",
            source="strava",
            provider="strava",
            external_activity_id=f"interval_test_{uuid4()}",
            duration_s=len(stream_data["time"]),
            distance_m=8000,
            avg_hr=160,
            stream_fetch_status="success",
        )
        db_session.add(activity)
        db_session.commit()

        stream = ActivityStream(
            activity_id=activity.id,
            stream_data=stream_data,
            channels_available=list(stream_data.keys()),
            point_count=len(stream_data["time"]),
            source="strava",
        )
        db_session.add(stream)
        db_session.commit()

        # Create plan with segments containing interval spec
        training_plan = TrainingPlan(
            athlete_id=test_athlete.id,
            name="Interval Plan",
            status="active",
            goal_race_date=date(2026, 6, 1),
            goal_race_distance_m=10000,
            plan_start_date=date(2026, 1, 1),
            plan_end_date=date(2026, 6, 1),
            total_weeks=22,
            plan_type="10k",
        )
        db_session.add(training_plan)
        db_session.commit()

        plan = PlannedWorkout(
            plan_id=training_plan.id,
            athlete_id=test_athlete.id,
            scheduled_date=activity.start_time.date(),
            week_number=1,
            day_of_week=2,
            workout_type="intervals",
            title="5x90s Intervals",
            phase="build",
            target_duration_minutes=30,
            target_distance_km=8.0,
            target_pace_per_km_seconds=240,
            completed=True,
            completed_activity_id=activity.id,
            segments=[
                {"type": "warmup", "duration_minutes": 10},
                {"type": "interval", "reps": 5, "work_duration_s": 90, "rest_duration_s": 90},
                {"type": "cooldown", "duration_minutes": 5},
            ],
        )
        db_session.add(plan)
        db_session.commit()

        result = analyze_run_streams(db_session, test_athlete.id, activity_id=str(activity.id))

        assert result["ok"] is True
        comparison = result["data"]["analysis"]["plan_comparison"]
        assert comparison is not None
        assert comparison["planned_interval_count"] == 5
        assert comparison["detected_work_count"] is not None
        assert comparison["interval_count_match"] is not None  # bool, not None

    def test_no_segments_in_plan_yields_null_interval_count(self, db_session, test_athlete, activity_with_stream):
        """PlannedWorkout without segments → interval fields are None."""
        from services.coach_tools import analyze_run_streams

        training_plan = TrainingPlan(
            athlete_id=test_athlete.id,
            name="Easy Plan",
            status="active",
            goal_race_date=date(2026, 6, 1),
            goal_race_distance_m=42195,
            plan_start_date=date(2026, 1, 1),
            plan_end_date=date(2026, 6, 1),
            total_weeks=22,
            plan_type="marathon",
        )
        db_session.add(training_plan)
        db_session.commit()

        plan = PlannedWorkout(
            plan_id=training_plan.id,
            athlete_id=test_athlete.id,
            scheduled_date=activity_with_stream.start_time.date(),
            week_number=1,
            day_of_week=1,
            workout_type="easy",
            title="Easy Run",
            phase="base",
            target_duration_minutes=60,
            target_distance_km=10.0,
            target_pace_per_km_seconds=360,
            completed=True,
            completed_activity_id=activity_with_stream.id,
            segments=None,  # No segments
        )
        db_session.add(plan)
        db_session.commit()

        result = analyze_run_streams(db_session, test_athlete.id, activity_id=str(activity_with_stream.id))

        assert result["ok"] is True
        comparison = result["data"]["analysis"]["plan_comparison"]
        assert comparison is not None
        # No segments → interval count fields should be None
        assert comparison["planned_interval_count"] is None
        assert comparison["interval_count_match"] is None
