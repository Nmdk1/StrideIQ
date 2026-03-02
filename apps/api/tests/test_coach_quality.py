"""
Coach Quality regression tests — March 2026.

Covers the three production failures identified on 2026-03-02:
  1. GarminDay Health API data missing from coach context / wellness tool
  2. coach_noticed insight staleness (same insight repeated for 4+ days)
  3. Coach hallucinations (fabricated soreness, wrong plan distance, this-week runs)
  4. km distances in context (should always be miles)

All tests are fully offline — mocked DB sessions and Redis, no real API calls.
"""

import inspect
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_garmin_day(**kwargs):
    """Return a lightweight mock GarminDay with sensible defaults."""
    g = MagicMock()
    g.id = uuid.uuid4()
    g.athlete_id = kwargs.get("athlete_id", uuid.uuid4())
    g.calendar_date = kwargs.get("calendar_date", date.today() - timedelta(days=1))
    g.sleep_total_s = kwargs.get("sleep_total_s", 25200)   # 7h
    g.sleep_score = kwargs.get("sleep_score", 78)
    g.hrv_overnight_avg = kwargs.get("hrv_overnight_avg", 42)
    g.resting_hr = kwargs.get("resting_hr", 51)
    g.avg_stress = kwargs.get("avg_stress", 27)
    g.body_battery_end = kwargs.get("body_battery_end", 65)
    g.steps = kwargs.get("steps", 8000)
    g.active_kcal = kwargs.get("active_kcal", 400)
    return g


def _make_activity(**kwargs):
    """Return a lightweight mock Activity."""
    a = MagicMock()
    a.id = uuid.uuid4()
    a.athlete_id = kwargs.get("athlete_id", uuid.uuid4())
    a.start_time = kwargs.get("start_time", datetime.now(tz=timezone.utc) - timedelta(days=1))
    a.distance_m = kwargs.get("distance_m", 16093)   # ~10 miles
    a.duration_s = kwargs.get("duration_s", 4500)    # 75 min
    a.avg_hr = kwargs.get("avg_hr", 148)
    a.sport = kwargs.get("sport", "run")
    return a


def _make_athlete(**kwargs):
    a = MagicMock()
    a.id = kwargs.get("id", uuid.uuid4())
    a.display_name = kwargs.get("display_name", "Test Athlete")
    a.birthdate = kwargs.get("birthdate", date(1985, 6, 15))
    a.rpi = kwargs.get("rpi", 3.0)
    a.resting_hr = kwargs.get("resting_hr", None)
    a.max_hr = kwargs.get("max_hr", None)
    return a


def _make_db_for_build_context(
    athlete,
    recent_activities=None,
    month_activities=None,
    checkins=None,
    garmin_days=None,
):
    """Mock DB that returns correct data for build_context()."""
    db = MagicMock()

    def _query_side(model):
        from models import (
            Athlete as AthleteModel,
            Activity as ActivityModel,
            DailyCheckin as CheckinModel,
            GarminDay as GarminDayModel,
            PersonalBest as PBModel,
            TrainingPlan as PlanModel,
        )
        q = MagicMock()
        if model is AthleteModel:
            q.filter.return_value.first.return_value = athlete
        elif model is ActivityModel:
            q.filter.return_value.order_by.return_value.all.return_value = (
                recent_activities or []
            )
        elif model is CheckinModel:
            q.filter.return_value.order_by.return_value.limit.return_value.all.return_value = (
                checkins or []
            )
        elif model is GarminDayModel:
            q.filter.return_value.order_by.return_value.limit.return_value.all.return_value = (
                garmin_days or []
            )
        elif model is PBModel:
            q.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        elif model is PlanModel:
            q.filter.return_value.first.return_value = None
        else:
            pass
        return q

    db.query.side_effect = _query_side
    return db


# ---------------------------------------------------------------------------
# 1. test_build_context_includes_garmin_day
# ---------------------------------------------------------------------------

class TestBuildContextGarminDay:
    """GarminDay data must appear in build_context() output when records exist."""

    def test_build_context_includes_garmin_day(self):
        from services.ai_coach import AICoach

        athlete = _make_athlete()
        garmin = _make_garmin_day(
            athlete_id=athlete.id,
            sleep_total_s=22320,   # 6.2h
            hrv_overnight_avg=38,
            resting_hr=53,
            avg_stress=31,
        )
        db = _make_db_for_build_context(athlete, garmin_days=[garmin])

        coach = AICoach.__new__(AICoach)
        coach.db = db

        ctx = coach.build_context(athlete.id)

        assert "Garmin Watch Data" in ctx, "GarminDay section header missing"
        assert "HRV: 38ms" in ctx or "HRV" in ctx, "HRV missing from context"
        assert "6.2h" in ctx or "6.1h" in ctx or "Sleep:" in ctx, "Sleep missing"
        assert "53 bpm" in ctx or "Resting HR" in ctx, "Resting HR missing"
        assert "31" in ctx or "Stress" in ctx, "Stress missing"

    def test_build_context_includes_garmin_attribution(self):
        """Context must credit Health API as source, not self-report."""
        from services.ai_coach import AICoach

        athlete = _make_athlete()
        garmin = _make_garmin_day(athlete_id=athlete.id)
        db = _make_db_for_build_context(athlete, garmin_days=[garmin])

        coach = AICoach.__new__(AICoach)
        coach.db = db

        ctx = coach.build_context(athlete.id)
        # The section header must make the source clear
        assert "Health API" in ctx or "Garmin Watch" in ctx, (
            "Garmin Health API attribution missing from context"
        )


# ---------------------------------------------------------------------------
# 2. test_build_context_no_garmin_day_graceful
# ---------------------------------------------------------------------------

class TestBuildContextNoGarminDay:
    """Context must build cleanly (no crash, no stub text) when no GarminDay data."""

    def test_build_context_no_garmin_day_graceful(self):
        from services.ai_coach import AICoach

        athlete = _make_athlete()
        db = _make_db_for_build_context(athlete, garmin_days=[])

        coach = AICoach.__new__(AICoach)
        coach.db = db

        ctx = coach.build_context(athlete.id)

        assert isinstance(ctx, str), "build_context must return a string"
        assert "## Athlete Profile" in ctx, "Athlete profile section missing"
        # Must not hallucinate Garmin data when none exists
        assert "Garmin Watch Data" not in ctx, (
            "Garmin Watch section must not appear when no GarminDay records exist"
        )


# ---------------------------------------------------------------------------
# 3. test_build_context_distances_in_miles
# ---------------------------------------------------------------------------

class TestBuildContextDistancesInMiles:
    """All distances in build_context() must be in miles, never km."""

    def test_build_context_distances_in_miles(self):
        from services.ai_coach import AICoach

        athlete = _make_athlete()
        # A 10-mile (16,093m) run
        activity = _make_activity(distance_m=16093, duration_s=4500)
        db = _make_db_for_build_context(
            athlete,
            recent_activities=[activity],
            month_activities=[activity],
        )

        coach = AICoach.__new__(AICoach)
        coach.db = db

        ctx = coach.build_context(athlete.id)

        assert " mi" in ctx or "/mi" in ctx, "Miles unit not found in context"
        assert " km" not in ctx, "km found in context — distances must always be miles"
        assert "/km" not in ctx, "/km pace found in context — pace must always be /mi"

    def test_format_pace_returns_miles(self):
        """_format_pace helper must return /mi not /km."""
        from services.ai_coach import AICoach

        coach = AICoach.__new__(AICoach)
        pace_str = coach._format_pace(3600, 1609)  # 1 mile in ~1h = 60:00/mi
        assert "/mi" in pace_str, f"Expected /mi pace, got: {pace_str}"
        assert "/km" not in pace_str, f"Got /km pace, expected /mi: {pace_str}"


# ---------------------------------------------------------------------------
# 4. test_wellness_trends_includes_garmin_data
# ---------------------------------------------------------------------------

class TestWellnessTrendsGarminData:
    """get_wellness_trends must include GarminDay Health API data alongside DailyCheckin."""

    def test_wellness_trends_includes_garmin_data(self):
        from services.coach_tools import get_wellness_trends

        athlete_id = uuid.uuid4()

        garmin = _make_garmin_day(
            athlete_id=athlete_id,
            sleep_total_s=25200,   # 7.0h
            hrv_overnight_avg=44,
            resting_hr=50,
            avg_stress=22,
            sleep_score=82,
        )

        # get_wellness_trends calls db.query(DailyCheckin) first, then db.query(GarminDay).
        # Use side_effect with a call counter to return different results per call order.
        db = MagicMock()
        _call_idx = [0]

        def _query_side(model):
            q = MagicMock()
            idx = _call_idx[0]
            _call_idx[0] += 1
            if idx == 0:
                # First call: DailyCheckin — return empty
                q.filter.return_value.order_by.return_value.all.return_value = []
            else:
                # Second call: GarminDay — return one record
                q.filter.return_value.order_by.return_value.all.return_value = [garmin]
            return q

        db.query.side_effect = _query_side

        result = get_wellness_trends(db, athlete_id, days=7)

        assert result.get("ok"), f"get_wellness_trends failed: {result}"
        narrative = result.get("narrative", "")
        data = result.get("data", {})

        assert "Garmin" in narrative, "Garmin data missing from wellness narrative"
        assert "garmin_health_api" in data, "garmin_health_api key missing from data"
        garmin_data = data["garmin_health_api"]
        assert garmin_data.get("data_points") == 1
        # HRV should be ~44ms
        assert garmin_data.get("hrv_overnight_avg_ms") is not None
        assert abs(garmin_data["hrv_overnight_avg_ms"] - 44.0) < 0.5

    def test_wellness_trends_graceful_no_garmin(self):
        """get_wellness_trends must not crash when no GarminDay or DailyCheckin records exist."""
        from services.coach_tools import get_wellness_trends

        athlete_id = uuid.uuid4()
        db = MagicMock()

        def _query_side(model):
            q = MagicMock()
            q.filter.return_value.order_by.return_value.all.return_value = []
            return q

        db.query.side_effect = _query_side

        result = get_wellness_trends(db, athlete_id, days=7)
        assert isinstance(result, dict), "Must return a dict"
        assert "tool" in result


# ---------------------------------------------------------------------------
# 5. test_insight_rotation_suppresses_repeat_48h
# ---------------------------------------------------------------------------

class TestInsightRotation:
    """
    Insight rotation must suppress the same coach_noticed for 48h.

    Test strategy:
    - Verify that the prompt includes a ROTATION CONSTRAINT when Redis has
      a stored coach_noticed for this athlete.
    - Verify the constraint contains the stored text.
    - Time-frozen: we mock Redis so the stored text is always present.
    """

    def _run_briefing(self, athlete_id, db, last_notice=None, **kwargs):
        """Helper: call generate_coach_home_briefing with all heavy dependencies mocked.

        We patch redis.from_url at the redis-module level (not routers.home.redis)
        because the rotation code uses 'import redis as _redis_rot' inside the
        function — patching routers.home.redis would not intercept that local import.
        """
        from routers.home import generate_coach_home_briefing

        mock_redis_instance = MagicMock()
        mock_redis_instance.get.return_value = last_notice

        with patch("redis.from_url", return_value=mock_redis_instance), \
             patch("services.coach_tools.build_athlete_brief", return_value="(brief)"), \
             patch("routers.home.compute_coach_noticed", return_value=None), \
             patch("routers.home._build_rich_intelligence_context", return_value=""), \
             patch("routers.home._get_garmin_sleep_h_for_last_night", return_value=(None, None)):

            return generate_coach_home_briefing(
                athlete_id=athlete_id, db=db, skip_cache=True, **kwargs
            )

    def _make_min_db(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        db.query.return_value.filter.return_value.scalar.return_value = 0
        return db

    def test_insight_rotation_injects_constraint_when_last_notice_exists(self):
        """When coach_noticed_last:{athlete_id} exists in Redis, the prompt must
        include a ROTATION CONSTRAINT instructing the LLM to avoid repeating it."""
        athlete_id = str(uuid.uuid4())
        last_notice = "Your efficiency tends to improve within 2 days of better sleep."

        prep = self._run_briefing(athlete_id, self._make_min_db(), last_notice=last_notice)

        # Result is a tuple: (None, prompt, schema_fields, required_fields, cache_key, garmin_sleep_h)
        assert len(prep) >= 2, "Expected tuple from generate_coach_home_briefing"
        prompt = prep[1]
        assert "ROTATION CONSTRAINT" in prompt, (
            "ROTATION CONSTRAINT not found in prompt — same insight can repeat indefinitely"
        )
        assert last_notice[:60] in prompt, (
            "Last coach_noticed text not injected into rotation constraint"
        )

    def test_insight_rotation_not_injected_when_no_stored_notice(self):
        """When no prior coach_noticed exists, prompt must NOT include ROTATION CONSTRAINT."""
        athlete_id = str(uuid.uuid4())
        prep = self._run_briefing(athlete_id, self._make_min_db(), last_notice=None)
        prompt = prep[1]
        assert "ROTATION CONSTRAINT" not in prompt

    def test_task_records_coach_noticed_after_write(self):
        """generate_home_briefing_task must persist coach_noticed to Redis after success."""
        from tasks.home_briefing_tasks import generate_home_briefing_task
        source = inspect.getsource(generate_home_briefing_task)
        # Structural: must contain the Redis write for coach_noticed_last
        assert "coach_noticed_last" in source, (
            "coach_noticed_last key missing from home_briefing_tasks — "
            "insight rotation cannot work without persisting the last notice"
        )
        assert "setex" in source or "set(" in source, (
            "Redis setex/set call missing from home_briefing_tasks"
        )


# ---------------------------------------------------------------------------
# 6. test_coach_no_fabricated_soreness
# ---------------------------------------------------------------------------

class TestCoachNoFabricatedSoreness:
    """When soreness is null/None in the check-in, the prompt must not claim any soreness."""

    def _run_briefing(self, athlete_id, db, checkin_data=None, planned_workout=None):
        from routers.home import generate_coach_home_briefing

        with patch("routers.home.redis") as mock_redis_mod, \
             patch("services.coach_tools.build_athlete_brief", return_value="(brief)"), \
             patch("routers.home.compute_coach_noticed", return_value=None), \
             patch("routers.home._build_rich_intelligence_context", return_value=""), \
             patch("routers.home._get_garmin_sleep_h_for_last_night", return_value=(None, None)):
            mock_redis_mod.from_url.return_value.get.return_value = None

            return generate_coach_home_briefing(
                athlete_id=athlete_id,
                db=db,
                checkin_data=checkin_data,
                planned_workout=planned_workout,
                skip_cache=True,
            )

    def _make_min_db(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        db.query.return_value.filter.return_value.scalar.return_value = 0
        return db

    def test_soreness_not_reported_prevents_claim(self):
        """soreness_label=None in checkin_data → prompt must say 'not reported today'."""
        athlete_id = str(uuid.uuid4())
        checkin_data = {
            "motivation_label": "Fine",
            "sleep_label": "OK",
            "soreness_label": None,  # Not reported
            "sleep_h": 7.0,
        }

        prep = self._run_briefing(athlete_id, self._make_min_db(), checkin_data=checkin_data)
        prompt = prep[1]

        assert "not reported today" in prompt, (
            "Prompt does not say soreness 'not reported' — LLM may fabricate soreness"
        )
        assert "do NOT claim any soreness" in prompt, (
            "Explicit soreness ban missing from prompt"
        )


# ---------------------------------------------------------------------------
# 7. test_coach_plan_distance_matches_db
# ---------------------------------------------------------------------------

class TestCoachPlanDistanceMatchesDb:
    """Planned workout distance in context must come from DB, not LLM confabulation."""

    def test_planned_workout_distance_from_db(self):
        """The PlannedWorkout distance must be read from target_distance_km and passed
        to the LLM prompt as PLANNED miles — not inferred or estimated."""
        from tasks.home_briefing_tasks import _build_briefing_prompt
        source = inspect.getsource(_build_briefing_prompt)

        # Must read target_distance_km from PlannedWorkout and convert to miles
        assert "target_distance_km" in source, (
            "target_distance_km not read from PlannedWorkout — distance may be hallucinated"
        )
        assert "0.621371" in source or "1609" in source or "miles" in source.lower(), (
            "Distance conversion to miles not found in _build_briefing_prompt"
        )
        assert "distance_mi" in source, (
            "distance_mi not in briefing prompt — planned distance not grounded"
        )

    def _run_briefing(self, athlete_id, db, planned_workout=None):
        from routers.home import generate_coach_home_briefing

        with patch("routers.home.redis") as mock_redis_mod, \
             patch("services.coach_tools.build_athlete_brief", return_value="(brief)"), \
             patch("routers.home.compute_coach_noticed", return_value=None), \
             patch("routers.home._build_rich_intelligence_context", return_value=""), \
             patch("routers.home._get_garmin_sleep_h_for_last_night", return_value=(None, None)):
            mock_redis_mod.from_url.return_value.get.return_value = None

            return generate_coach_home_briefing(
                athlete_id=athlete_id,
                db=db,
                planned_workout=planned_workout,
                skip_cache=True,
            )

    def _make_min_db(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        db.query.return_value.filter.return_value.scalar.return_value = 0
        return db

    def test_planned_workout_distance_injected_into_prompt(self):
        """PLANNED line in prompt must include the actual distance_mi from DB."""
        athlete_id = str(uuid.uuid4())
        planned_workout = {
            "has_workout": True,
            "workout_type": "long_run",
            "title": "Long run",
            "distance_mi": 10.0,   # From DB: 10 miles (not 15)
        }

        prep = self._run_briefing(athlete_id, self._make_min_db(), planned_workout=planned_workout)
        prompt = prep[1]
        assert "10.0mi" in prompt or "10.0 mi" in prompt, (
            f"Planned distance 10.0mi not in prompt. Prompt excerpt: {prompt[:500]}"
        )


# ---------------------------------------------------------------------------
# 8. test_coach_no_this_week_runs_before_week_start
# ---------------------------------------------------------------------------

class TestCoachNoThisWeekRunsBeforeWeekStart:
    """On Monday pre-run state, runs_this_week = 0; prompt must ground this clearly."""

    def _run_briefing(self, athlete_id, db):
        from routers.home import generate_coach_home_briefing

        with patch("routers.home.redis") as mock_redis_mod, \
             patch("services.coach_tools.build_athlete_brief", return_value="(brief)"), \
             patch("routers.home.compute_coach_noticed", return_value=None), \
             patch("routers.home._build_rich_intelligence_context", return_value=""), \
             patch("routers.home._get_garmin_sleep_h_for_last_night", return_value=(None, None)):
            mock_redis_mod.from_url.return_value.get.return_value = None

            return generate_coach_home_briefing(
                athlete_id=athlete_id, db=db, skip_cache=True
            )

    def _make_min_db(self, runs_this_week=0):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        db.query.return_value.filter.return_value.scalar.return_value = runs_this_week
        return db

    def test_week_run_count_grounded_in_prompt(self):
        """Prompt must include 'Runs completed this week so far' grounding statement."""
        athlete_id = str(uuid.uuid4())
        # 0 runs — Monday pre-run state
        prep = self._run_briefing(athlete_id, self._make_min_db(runs_this_week=0))
        prompt = prep[1]

        assert "Runs completed this week so far" in prompt, (
            "Week run count grounding statement missing from prompt — "
            "LLM may fabricate 'you cut runs short this week' claims"
        )
        assert "Do NOT claim" in prompt, (
            "Explicit ban on fabricated week-run claims missing from prompt"
        )

    def test_week_run_count_present_in_briefing_tasks(self):
        """home_briefing_tasks source must not remove the week-run grounding (regression)."""
        # The grounding is built in generate_coach_home_briefing (routers/home.py),
        # not in the task itself. This test verifies the task calls the right builder.
        from tasks import home_briefing_tasks
        source = inspect.getsource(home_briefing_tasks._build_briefing_prompt)
        # The task calls generate_coach_home_briefing which owns the grounding
        assert "generate_coach_home_briefing" in source, (
            "generate_coach_home_briefing call missing from _build_briefing_prompt"
        )
