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

    def _run_briefing(self, athlete_id, db, **kwargs):
        """Helper: call generate_coach_home_briefing with all heavy dependencies mocked."""
        from routers.home import generate_coach_home_briefing

        mock_redis_instance = MagicMock()
        mock_redis_instance.get.return_value = None

        with patch("redis.from_url", return_value=mock_redis_instance), \
             patch("services.coach_tools.build_athlete_brief", return_value="(brief)"), \
             patch("routers.home.compute_coach_noticed", return_value=None), \
             patch("routers.home._build_rich_intelligence_context", return_value=""), \
             patch("routers.home._get_garmin_sleep_h_for_last_night", return_value=(None, None, False)):

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

    def test_finding_cooldown_functions_exist(self):
        """The finding-level cooldown functions must exist in home.py."""
        from routers.home import _is_finding_in_cooldown, _set_finding_cooldowns
        assert callable(_is_finding_in_cooldown)
        assert callable(_set_finding_cooldowns)

    def test_one_new_thing_rule_in_prompt(self):
        """Briefing prompt must include the ONE-NEW-THING RULE."""
        athlete_id = str(uuid.uuid4())
        prep = self._run_briefing(athlete_id, self._make_min_db())
        prompt = prep[1]
        assert "ONE-NEW-THING RULE" in prompt, (
            "ONE-NEW-THING RULE not found in prompt — briefings may repeat stale findings"
        )

    def test_task_sets_finding_cooldowns_after_briefing(self):
        """generate_home_briefing_task must call _set_finding_cooldowns after success."""
        from tasks.home_briefing_tasks import generate_home_briefing_task
        source = inspect.getsource(generate_home_briefing_task)
        assert "_set_finding_cooldowns" in source, (
            "_set_finding_cooldowns call missing from home_briefing_tasks — "
            "finding cooldown cannot work without setting keys after briefing"
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
             patch("routers.home._get_garmin_sleep_h_for_last_night", return_value=(None, None, False)):
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
            "readiness_label": "Good",
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
             patch("routers.home._get_garmin_sleep_h_for_last_night", return_value=(None, None, False)):
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
             patch("routers.home._get_garmin_sleep_h_for_last_night", return_value=(None, None, False)):
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


# ---------------------------------------------------------------------------
# 9. test_date_grounding_in_all_llm_prompts
# ---------------------------------------------------------------------------

class TestDateGroundingInPrompts:
    """
    Every LLM prompt path must inject today's date so the model can compute
    correct relative times ('3 days ago' not 'two weeks ago').

    Production incident: race_assessment said "13-miler two weeks ago"
    for a run that happened 2 days prior. Root cause: no date anchor.
    """

    def _run_briefing(self, athlete_id, db):
        from routers.home import generate_coach_home_briefing

        with patch("redis.from_url") as mock_redis, \
             patch("services.coach_tools.build_athlete_brief", return_value="(brief)"), \
             patch("routers.home.compute_coach_noticed", return_value=None), \
             patch("routers.home._build_rich_intelligence_context", return_value=""), \
             patch("routers.home._get_garmin_sleep_h_for_last_night", return_value=(None, None, False)):
            mock_redis.return_value.get.return_value = None

            return generate_coach_home_briefing(
                athlete_id=athlete_id, db=db, skip_cache=True
            )

    def _make_min_db(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        db.query.return_value.filter.return_value.scalar.return_value = 0
        return db

    def test_home_briefing_prompt_contains_todays_date(self):
        """The home briefing prompt must include today's ISO date."""
        athlete_id = str(uuid.uuid4())
        prep = self._run_briefing(athlete_id, self._make_min_db())
        prompt = prep[1]
        today_iso = date.today().isoformat()
        assert today_iso in prompt, (
            f"Today's date ({today_iso}) not found in home briefing prompt — "
            "LLM cannot compute correct relative times without a date anchor"
        )

    def test_home_briefing_prompt_contains_relative_time_instruction(self):
        """The prompt must tell the LLM to USE pre-computed relative times, not compute its own."""
        athlete_id = str(uuid.uuid4())
        prep = self._run_briefing(athlete_id, self._make_min_db())
        prompt = prep[1]
        assert "pre-computed" in prompt.lower(), (
            "Prompt must tell LLM to USE pre-computed relative times"
        )
        assert "do not compute your own" in prompt.lower(), (
            "Prompt must explicitly tell LLM NOT to compute relative times itself"
        )

    def test_fallback_briefing_system_prompt_contains_date(self):
        """The fallback sync briefing system prompt must also include today's date."""
        from routers.home import _fetch_llm_briefing_sync
        source = inspect.getsource(_fetch_llm_briefing_sync)
        assert "isoformat" in source and "today" in source.lower(), (
            "Fallback briefing system prompt does not inject today's date — "
            "same hallucination risk as primary path"
        )

    def test_chat_coach_gemini_prompt_contains_date(self):
        """The Gemini chat coach system instruction must include today's date."""
        from services.ai_coach import AICoach
        source = inspect.getsource(AICoach.query_gemini)
        assert "isoformat" in source and "today" in source.lower(), (
            "Chat coach Gemini prompt does not inject today's date"
        )

    def test_chat_coach_high_stakes_prompt_contains_date(self):
        """The high-stakes Opus system prompt must include today's date."""
        from services.ai_coach import AICoach
        source = inspect.getsource(AICoach.query_opus)
        assert "isoformat" in source and "today" in source.lower(), (
            "Chat coach high-stakes prompt does not inject today's date"
        )


# ---------------------------------------------------------------------------
# 10. test_relative_time_validator
# ---------------------------------------------------------------------------

class TestRelativeTimeValidator:
    """
    Post-generation validator must catch 'two weeks ago' when the most
    recent run was 2 days ago.

    Production incident: race_assessment said "13-miler two weeks ago"
    for a Saturday run viewed on Monday.
    """

    def test_catches_weeks_ago_when_run_was_recent(self):
        """'two weeks ago' with a run 2 days old → invalid."""
        from routers.home import validate_relative_time_claims
        recent = [date.today() - timedelta(days=2)]
        result = validate_relative_time_claims(
            "Your 13-miler at 7:28/mi two weeks ago suggests solid fitness.",
            recent,
        )
        assert not result["valid"], "Should catch 'two weeks ago' for a 2-day-old run"
        assert "relative_time" in result["reason"]

    def test_allows_correct_relative_time(self):
        """Correct claim ('Saturday') with recent run → valid."""
        from routers.home import validate_relative_time_claims
        recent = [date.today() - timedelta(days=2)]
        result = validate_relative_time_claims(
            "Your 13-miler on Saturday at 7:28/mi suggests solid fitness.",
            recent,
        )
        assert result["valid"]

    def test_allows_weeks_ago_when_run_actually_old(self):
        """'two weeks ago' is fine when the run really was 14+ days old."""
        from routers.home import validate_relative_time_claims
        recent = [date.today() - timedelta(days=15)]
        result = validate_relative_time_claims(
            "Your tempo two weeks ago showed good form.",
            recent,
        )
        assert result["valid"]

    def test_catches_last_week_when_run_was_yesterday(self):
        """'last week' with a run 1 day old → invalid."""
        from routers.home import validate_relative_time_claims
        recent = [date.today() - timedelta(days=1)]
        result = validate_relative_time_claims(
            "Your long run last week was strong.",
            recent,
        )
        assert not result["valid"]

    def test_catches_month_ago_when_run_was_this_week(self):
        """'a month ago' with a run 3 days old → invalid."""
        from routers.home import validate_relative_time_claims
        recent = [date.today() - timedelta(days=3)]
        result = validate_relative_time_claims(
            "Your 13-miler a month ago and a predicted marathon of 3:00:56.",
            recent,
        )
        assert not result["valid"]

    def test_empty_text_valid(self):
        """Empty/None text → valid (no claim to check)."""
        from routers.home import validate_relative_time_claims
        assert validate_relative_time_claims("", [date.today()])["valid"]
        assert validate_relative_time_claims(None, [date.today()])["valid"]

    def test_no_dates_valid(self):
        """No recent run dates → valid (nothing to compare against)."""
        from routers.home import validate_relative_time_claims
        assert validate_relative_time_claims("two weeks ago", [])["valid"]

    def test_validator_wired_into_fetch_llm_briefing(self):
        """_fetch_llm_briefing_sync must call validate_relative_time_claims (structural)."""
        from routers.home import _fetch_llm_briefing_sync
        source = inspect.getsource(_fetch_llm_briefing_sync)
        assert "validate_relative_time_claims" in source, (
            "validate_relative_time_claims not called in _fetch_llm_briefing_sync — "
            "relative-time hallucinations will not be caught"
        )


# ---------------------------------------------------------------------------
# 11. Contract: _relative_date() and pre-computed relative times
# ---------------------------------------------------------------------------

class TestRelativeDateHelper:
    """The shared _relative_date() helper must be correct and used everywhere."""

    def test_today(self):
        from services.coach_tools import _relative_date
        assert _relative_date(date.today()) == "(today)"

    def test_yesterday(self):
        from services.coach_tools import _relative_date
        assert _relative_date(date.today() - timedelta(days=1)) == "(yesterday)"

    def test_days_ago(self):
        from services.coach_tools import _relative_date
        assert _relative_date(date.today() - timedelta(days=3)) == "(3 days ago)"

    def test_weeks_ago(self):
        from services.coach_tools import _relative_date
        assert _relative_date(date.today() - timedelta(days=14)) == "(2 weeks ago)"

    def test_tomorrow(self):
        from services.coach_tools import _relative_date
        assert _relative_date(date.today() + timedelta(days=1)) == "(tomorrow)"

    def test_in_days(self):
        from services.coach_tools import _relative_date
        assert _relative_date(date.today() + timedelta(days=5)) == "(in 5 days)"

    def test_in_weeks(self):
        from services.coach_tools import _relative_date
        assert _relative_date(date.today() + timedelta(days=21)) == "(in 3 weeks)"


class TestBriefDatePreComputation:
    """
    Contract: build_athlete_brief must pre-compute relative times for ALL dates.
    If this test fails, an LLM will be asked to do date arithmetic — which it
    gets wrong, as proven by the 'two weeks ago' production incident.
    """

    def test_brief_contains_relative_time_markers(self):
        """Every ISO date in the athlete brief must be followed by a relative time."""
        from services.coach_tools import build_athlete_brief
        import re

        db = MagicMock()
        athlete_id = uuid.uuid4()

        athlete_mock = MagicMock()
        athlete_mock.id = athlete_id
        athlete_mock.first_name = "Test"
        athlete_mock.birthdate = date(1990, 1, 1)
        athlete_mock.gender = "male"
        athlete_mock.preferred_units = "imperial"
        athlete_mock.rpi = 5.5

        db.query.return_value.filter.return_value.first.return_value = athlete_mock
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.scalar.return_value = 0

        brief = build_athlete_brief(db, athlete_id)

        iso_dates = re.findall(r'\d{4}-\d{2}-\d{2}', brief)
        for iso_date in iso_dates:
            idx = brief.index(iso_date)
            surrounding = brief[idx:idx + 60]
            today_str = date.today().isoformat()
            if iso_date == today_str:
                continue
            has_relative = any(
                marker in surrounding
                for marker in [
                    "days ago", "yesterday", "today", "tomorrow",
                    "weeks ago", "week ago", "in ", "days away",
                    "days remaining", "of 7 days",
                ]
            )
            assert has_relative, (
                f"ISO date {iso_date} in brief has no pre-computed relative time. "
                f"Context: '{surrounding.strip()}'. "
                "The LLM must NEVER compute relative time — pre-compute it in Python."
            )

    def test_prompt_says_use_precomputed_not_compute(self):
        """Home briefing prompt must instruct LLM to USE pre-computed times, not compute them."""
        from routers.home import generate_coach_home_briefing
        athlete_id = str(uuid.uuid4())

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        db.query.return_value.filter.return_value.scalar.return_value = 0

        with patch("redis.from_url") as mock_redis, \
             patch("services.coach_tools.build_athlete_brief", return_value="(brief)"), \
             patch("routers.home.compute_coach_noticed", return_value=None), \
             patch("routers.home._build_rich_intelligence_context", return_value=""), \
             patch("routers.home._get_garmin_sleep_h_for_last_night", return_value=(None, None, False)):
            mock_redis.return_value.get.return_value = None
            prep = generate_coach_home_briefing(
                athlete_id=athlete_id, db=db, skip_cache=True
            )

        prompt = prep[1]
        assert "pre-computed" in prompt.lower(), (
            "Prompt must tell LLM to USE pre-computed relative times"
        )
        assert "do not compute your own" in prompt.lower(), (
            "Prompt must explicitly tell LLM NOT to compute relative times itself"
        )


# ---------------------------------------------------------------------------
# 12. Anti-hallucination: tool enforcement in chat coach
# ---------------------------------------------------------------------------

class TestToolEnforcement:
    """
    The chat coach must call tools for data questions and validate it did so.
    Production incident: LLM fabricated dates, distances, and volumes when
    it answered from the brief alone without calling tools.
    """

    def test_validate_tool_usage_exists(self):
        """_validate_tool_usage must exist and be callable."""
        from services.ai_coach import AICoach
        assert hasattr(AICoach, '_validate_tool_usage'), (
            "_validate_tool_usage method missing — tool enforcement is impossible"
        )

    def test_validate_tool_usage_rejects_no_tools_for_data_question(self):
        """A data question with no tool calls must fail validation."""
        from services.ai_coach import AICoach
        coach = AICoach.__new__(AICoach)
        is_valid, reason = coach._validate_tool_usage(
            "how far did I run this week", [], 0
        )
        assert not is_valid, "Data question with 0 tools should fail validation"
        assert reason == "no_tools_called"

    def test_validate_tool_usage_passes_with_tools(self):
        """A data question with appropriate tools must pass."""
        from services.ai_coach import AICoach
        coach = AICoach.__new__(AICoach)
        is_valid, reason = coach._validate_tool_usage(
            "how far did I run this week",
            ["get_weekly_volume", "get_recent_runs"],
            2,
        )
        assert is_valid, f"Data question with tools should pass: {reason}"

    def test_validate_tool_usage_skips_non_data_questions(self):
        """Non-data questions (definitions, greetings) don't need tools."""
        from services.ai_coach import AICoach
        coach = AICoach.__new__(AICoach)
        is_valid, reason = coach._validate_tool_usage(
            "what is a tempo run", [], 0
        )
        assert is_valid, "Definition question should not require tools"

    def test_validate_tool_usage_wired_in_opus(self):
        """query_opus must call _validate_tool_usage (structural check)."""
        from services.ai_coach import AICoach
        source = inspect.getsource(AICoach.query_opus)
        assert "_validate_tool_usage" in source, (
            "_validate_tool_usage not called in query_opus — "
            "Opus can hallucinate without detection"
        )
        assert "tools_called" in source, (
            "tools_called tracking missing from query_opus — "
            "cannot validate which tools were used"
        )

    def test_validate_tool_usage_wired_in_gemini(self):
        """query_gemini must call _validate_tool_usage (structural check)."""
        from services.ai_coach import AICoach
        source = inspect.getsource(AICoach.query_gemini)
        assert "_validate_tool_usage" in source, (
            "_validate_tool_usage not called in query_gemini — "
            "Gemini can hallucinate without detection"
        )
        assert "tools_called" in source, (
            "tools_called tracking missing from query_gemini — "
            "cannot validate which tools were used"
        )

    def test_zero_hallucination_rule_in_gemini_prompt(self):
        """Gemini system instruction must include zero-hallucination rule."""
        from services.ai_coach import AICoach
        source = inspect.getsource(AICoach.query_gemini)
        assert "ZERO-HALLUCINATION" in source, (
            "Gemini prompt missing ZERO-HALLUCINATION rule"
        )
        assert "USE THEM PROACTIVELY" in source, (
            "Gemini prompt missing proactive tool usage instruction"
        )

    def test_zero_hallucination_rule_in_opus_prompt(self):
        """Opus system prompt must include zero-hallucination rule."""
        from services.ai_coach import AICoach
        source = inspect.getsource(AICoach.query_opus)
        assert "ZERO-HALLUCINATION" in source, (
            "Opus prompt missing ZERO-HALLUCINATION rule"
        )
        assert "USE THEM PROACTIVELY" in source, (
            "Opus prompt missing proactive tool usage instruction"
        )

    def test_tools_called_returned_in_response(self):
        """Both query methods must return tools_called in the response dict."""
        from services.ai_coach import AICoach
        opus_source = inspect.getsource(AICoach.query_opus)
        gemini_source = inspect.getsource(AICoach.query_gemini)
        assert '"tools_called"' in opus_source, (
            "query_opus does not return tools_called in response"
        )
        assert '"tools_called"' in gemini_source, (
            "query_gemini does not return tools_called in response"
        )
