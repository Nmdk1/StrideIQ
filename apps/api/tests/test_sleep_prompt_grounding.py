"""
Tests for Sleep Data Prompt Grounding Fix (V2)

Builder note: docs/BUILDER_NOTE_2026-02-24_SLEEP_PROMPT_GROUNDING_V2.md
Rubric:       docs/ADVISOR_REVIEW_RUBRIC_2026-02-24_SLEEP_PROMPT_GROUNDING.md

9 required test contracts:
  1. sleep_h in checkin_data_dict — request path
  2. sleep_h in checkin_data_dict — worker path
  3. Prompt contains source-labeled sleep fields
  4. Wellness narrative includes most-recent-entry date prefix
  5. Garmin sleep lookup uses local today → local yesterday fallback
  6. Validator rejects sleep number not in any source
  7. Validator accepts sleep number within rounding tolerance (0.5h)
  8. No numeric sleep claim when no numeric sources exist
  9. Conflict case (Garmin vs check-in) — validator does not invent third value
  + Bonus: Workout-duration numerics do NOT trigger sleep validator (P0.2 false-positive gate)
"""

import sys
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# Path setup — mirror what the worker does
# ---------------------------------------------------------------------------
_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_ROOT not in sys.path:
    sys.path.insert(0, _API_ROOT)


# ---------------------------------------------------------------------------
# Helper: build a minimal mock DailyCheckin
# ---------------------------------------------------------------------------
def _make_checkin(
    sleep_h: Optional[float] = 7.0,
    sleep_quality_1_5: Optional[int] = None,
    readiness_1_5: Optional[int] = 4,
    soreness_1_5: Optional[int] = 1,
) -> MagicMock:
    c = MagicMock()
    c.sleep_h = Decimal(str(sleep_h)) if sleep_h is not None else None
    c.sleep_quality_1_5 = sleep_quality_1_5
    c.readiness_1_5 = readiness_1_5
    c.soreness_1_5 = soreness_1_5
    return c


# ---------------------------------------------------------------------------
# Helper: build a minimal mock GarminDay row
# ---------------------------------------------------------------------------
def _make_garmin_day(sleep_total_s: Optional[int] = 24300) -> MagicMock:  # 6.75h
    g = MagicMock()
    g.sleep_total_s = sleep_total_s
    return g


# ===========================================================================
# Test 1 — sleep_h in checkin_data_dict (request path, home.py)
# ===========================================================================
class TestCheckinDataDictRequestPath:
    """
    The home.py request path (get_home_data) must include sleep_h in the
    checkin_data_dict it passes to generate_coach_home_briefing.
    """

    def test_checkin_data_dict_includes_sleep_h_request_path(self):
        """When DailyCheckin has sleep_h=7.5, checkin_data_dict["sleep_h"] == 7.5."""
        from routers.home import _build_checkin_data_dict

        checkin = _make_checkin(sleep_h=7.5)
        result = _build_checkin_data_dict(checkin)

        assert result is not None
        assert "sleep_h" in result
        assert abs(result["sleep_h"] - 7.5) < 0.01

    def test_checkin_data_dict_sleep_h_none_when_missing(self):
        """When DailyCheckin has no sleep_h, checkin_data_dict['sleep_h'] is None."""
        from routers.home import _build_checkin_data_dict

        checkin = _make_checkin(sleep_h=None)
        result = _build_checkin_data_dict(checkin)

        assert result is not None
        assert result.get("sleep_h") is None


# ===========================================================================
# Test 2 — sleep_h in checkin_data_dict (worker path, home_briefing_tasks.py)
# ===========================================================================
class TestCheckinDataDictWorkerPath:
    """
    The Celery worker path (_build_briefing_prompt) must include sleep_h
    in the checkin_data_dict it returns.
    """

    def test_checkin_data_dict_includes_sleep_h_worker_path(self):
        """_build_briefing_prompt must include sleep_h in checkin_data_dict."""
        from tasks.home_briefing_tasks import _build_briefing_prompt

        mock_checkin = _make_checkin(sleep_h=6.5)
        mock_db = MagicMock()

        # Stub all DB queries
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        # Patch DailyCheckin query to return our mock
        def side_effect(model):
            q = MagicMock()
            q.filter.return_value.first.return_value = (
                mock_checkin if hasattr(model, "__tablename__") and model.__tablename__ == "daily_checkin"
                else None
            )
            q.filter.return_value.order_by.return_value.first.return_value = None
            q.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
            q.filter.return_value.all.return_value = []
            return q

        mock_db.query.side_effect = side_effect

        # generate_coach_home_briefing is imported lazily inside _build_briefing_prompt;
        # patch at the routers.home module level where the function is defined.
        with patch("routers.home.generate_coach_home_briefing") as mock_gen:
            # Return a 6-tuple (the new format after the fix)
            mock_gen.return_value = (None, "prompt", {}, [], "cache_key", None)

            result = _build_briefing_prompt("athlete-uuid-123", mock_db)

        # result is (prompt, schema_fields, required_fields, checkin_data_dict, race_data_dict, garmin_sleep_h)
        assert result is not None and result is not False
        _, _, _, checkin_data, _, _ = result
        assert checkin_data is not None
        assert "sleep_h" in checkin_data
        assert abs(checkin_data["sleep_h"] - 6.5) < 0.01


# ===========================================================================
# Test 3 — Prompt contains source-labeled sleep fields
# ===========================================================================
class TestPromptContainsSourceLabeledSleepFields:
    """
    generate_coach_home_briefing must inject explicit source-labeled sleep
    fields when checkin_data contains sleep_h.
    """

    def test_prompt_contains_today_checkin_sleep_hours(self):
        """When checkin_data has sleep_h=7.0, prompt includes 'TODAY_CHECKIN_SLEEP_HOURS'."""
        from routers.home import generate_coach_home_briefing

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.limit.return_value.all.return_value = []

        # build_athlete_brief is imported lazily inside generate_coach_home_briefing;
        # patch at the services.coach_tools module where it lives.
        with (
            patch("services.coach_tools.build_athlete_brief", return_value="(Brief unavailable)"),
            patch("routers.home._build_rich_intelligence_context", return_value=""),
            patch("routers.home.compute_coach_noticed", return_value=None),
            patch("routers.home._get_garmin_sleep_h_for_last_night", return_value=(None, str(date.today()))),
        ):
            prep = generate_coach_home_briefing(
                athlete_id="test-athlete-id",
                db=mock_db,
                checkin_data={"readiness_label": "Fine", "sleep_label": "Good", "soreness_label": "None", "sleep_h": 7.0},
                skip_cache=True,
            )

        assert len(prep) == 6
        _, prompt, _, _, _, _ = prep
        assert "TODAY_CHECKIN_SLEEP_HOURS" in prompt
        assert "7.0" in prompt

    def test_prompt_contains_no_synthesis_rule(self):
        """Prompt must include instruction not to synthesize or average sleep values."""
        from routers.home import generate_coach_home_briefing

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        with (
            patch("services.coach_tools.build_athlete_brief", return_value="(Brief unavailable)"),
            patch("routers.home._build_rich_intelligence_context", return_value=""),
            patch("routers.home.compute_coach_noticed", return_value=None),
            patch("routers.home._get_garmin_sleep_h_for_last_night", return_value=(6.75, str(date.today()))),
        ):
            prep = generate_coach_home_briefing(
                athlete_id="test-athlete-id",
                db=mock_db,
                checkin_data={"sleep_h": 7.0, "sleep_label": "Good", "readiness_label": "Fine", "soreness_label": "None"},
                skip_cache=True,
            )

        _, prompt, _, _, _, _ = prep
        assert "synthesize" in prompt.lower() or "average" in prompt.lower() or "invent" in prompt.lower()

    def test_prompt_contains_garmin_sleep_when_available(self):
        """When Garmin sleep is available, prompt includes GARMIN_LAST_NIGHT_SLEEP_HOURS."""
        from routers.home import generate_coach_home_briefing

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        with (
            patch("services.coach_tools.build_athlete_brief", return_value="(Brief unavailable)"),
            patch("routers.home._build_rich_intelligence_context", return_value=""),
            patch("routers.home.compute_coach_noticed", return_value=None),
            patch("routers.home._get_garmin_sleep_h_for_last_night", return_value=(6.75, str(date.today()))),
        ):
            prep = generate_coach_home_briefing(
                athlete_id="test-athlete-id",
                db=mock_db,
                checkin_data={"sleep_h": 7.0, "sleep_label": "Good", "readiness_label": "Fine", "soreness_label": "None"},
                skip_cache=True,
            )

        _, prompt, _, _, _, garmin_sleep_h = prep
        assert garmin_sleep_h == 6.75
        assert "GARMIN_LAST_NIGHT_SLEEP_HOURS" in prompt
        assert "6.75" in prompt


# ===========================================================================
# Test 4 — Wellness trends includes most-recent-entry date prefix
# ===========================================================================
class TestWellnessTrendsRecentPrefix:
    """
    get_wellness_trends must prefix the narrative with the most recent
    entry date and value to anchor LLM temporal reasoning.
    """

    def test_wellness_trends_includes_most_recent_date_prefix(self):
        """Narrative should start with 'Most recent:' entry with date."""
        from services.coach_tools import get_wellness_trends
        from uuid import uuid4

        mock_db = MagicMock()
        today = date.today()
        yesterday = today - timedelta(days=1)

        checkin_today = _make_checkin(sleep_h=7.0)
        checkin_today.date = today
        checkin_today.stress_1_5 = 2
        checkin_today.soreness_1_5 = 1
        checkin_today.hrv_rmssd = None
        checkin_today.resting_hr = None
        checkin_today.enjoyment_1_5 = None
        checkin_today.confidence_1_5 = None
        checkin_today.readiness_1_5 = None

        checkin_yesterday = _make_checkin(sleep_h=6.5)
        checkin_yesterday.date = yesterday
        checkin_yesterday.stress_1_5 = 3
        checkin_yesterday.soreness_1_5 = 2
        checkin_yesterday.hrv_rmssd = None
        checkin_yesterday.resting_hr = None
        checkin_yesterday.enjoyment_1_5 = None
        checkin_yesterday.confidence_1_5 = None
        checkin_yesterday.readiness_1_5 = None

        q = MagicMock()
        q.filter.return_value.order_by.return_value.all.return_value = [checkin_today, checkin_yesterday]
        mock_db.query.return_value = q

        result = get_wellness_trends(mock_db, uuid4(), days=28)

        narrative = result.get("narrative", "")
        assert "Most recent" in narrative or "most recent" in narrative or today.isoformat() in narrative


# ===========================================================================
# Test 5 — Garmin sleep lookup uses local today → local yesterday fallback
# ===========================================================================
class TestGarminSleepLocalDateFallback:
    """
    _get_garmin_sleep_h_for_last_night must use athlete-local date,
    try local_today first, then fall back to local_today - 1 day.
    """

    def test_garmin_sleep_uses_local_today_first(self):
        """Returns sleep_h from local_today when GarminDay exists for that date."""
        from routers.home import _get_garmin_sleep_h_for_last_night

        mock_db = MagicMock()
        mock_athlete = MagicMock()
        mock_athlete.timezone = "America/New_York"

        garmin_row = _make_garmin_day(sleep_total_s=25200)  # 7h

        def query_side_effect(model):
            q = MagicMock()
            if hasattr(model, "__tablename__"):
                if model.__tablename__ == "athlete":
                    q.filter.return_value.first.return_value = mock_athlete
                elif model.__tablename__ == "garmin_day":
                    # First call (today) returns a row; second call (yesterday) should not be reached
                    q.filter.return_value.first.return_value = garmin_row
            return q

        mock_db.query.side_effect = query_side_effect

        sleep_h, date_used = _get_garmin_sleep_h_for_last_night("athlete-id", mock_db)
        assert sleep_h == pytest.approx(7.0, abs=0.05)

    def test_garmin_sleep_falls_back_to_yesterday_on_delayed_sync(self):
        """Falls back to local_today - 1 when today has no GarminDay row."""
        from routers.home import _get_garmin_sleep_h_for_last_night

        mock_db = MagicMock()
        mock_athlete = MagicMock()
        mock_athlete.timezone = "America/Chicago"

        garmin_row = _make_garmin_day(sleep_total_s=23400)  # 6.5h
        call_count = {"n": 0}

        def query_side_effect(model):
            q = MagicMock()
            if hasattr(model, "__tablename__"):
                if model.__tablename__ == "athlete":
                    q.filter.return_value.first.return_value = mock_athlete
                elif model.__tablename__ == "garmin_day":
                    call_count["n"] += 1
                    # First call returns None (today), second returns a row (yesterday)
                    q.filter.return_value.first.return_value = (
                        None if call_count["n"] == 1 else garmin_row
                    )
            return q

        mock_db.query.side_effect = query_side_effect

        sleep_h, date_used = _get_garmin_sleep_h_for_last_night("athlete-id", mock_db)
        assert sleep_h == pytest.approx(6.5, abs=0.05)

    def test_garmin_sleep_uses_utc_fallback_when_no_timezone(self):
        """When athlete has no timezone, uses UTC date without raising."""
        from routers.home import _get_garmin_sleep_h_for_last_night

        mock_db = MagicMock()
        mock_athlete = MagicMock()
        mock_athlete.timezone = None  # Explicit: no timezone

        garmin_row = _make_garmin_day(sleep_total_s=24300)  # 6.75h

        def query_side_effect(model):
            q = MagicMock()
            if hasattr(model, "__tablename__"):
                if model.__tablename__ == "athlete":
                    q.filter.return_value.first.return_value = mock_athlete
                elif model.__tablename__ == "garmin_day":
                    q.filter.return_value.first.return_value = garmin_row
            return q

        mock_db.query.side_effect = query_side_effect

        sleep_h, date_used = _get_garmin_sleep_h_for_last_night("athlete-id", mock_db)
        assert sleep_h == pytest.approx(6.75, abs=0.05)
        assert date_used != "unknown"  # Must return a real date, not error


# ===========================================================================
# Test 6 — Validator rejects sleep number not in sources
# ===========================================================================
class TestValidatorRejectsSleepNumberNotInSources:

    def test_validator_rejects_sleep_number_not_in_sources(self):
        """7.5h claim in sleep-context sentence rejected when sources are 6.0 and 6.5."""
        from routers.home import validate_sleep_claims

        text = "You slept 7.5 hours last night which is great recovery."
        result = validate_sleep_claims(text, garmin_sleep_h=6.0, checkin_sleep_h=6.5)

        assert result["valid"] is False
        assert result.get("claim") == pytest.approx(7.5, abs=0.1)

    def test_validator_rejects_when_only_garmin_present_and_claim_wrong(self):
        """Claim of 8h rejected when only Garmin source (6.75h) is present."""
        from routers.home import validate_sleep_claims

        text = "You slept 8 hours last night — excellent."
        result = validate_sleep_claims(text, garmin_sleep_h=6.75, checkin_sleep_h=None)

        assert result["valid"] is False


# ===========================================================================
# Test 7 — Validator accepts sleep number within rounding tolerance
# ===========================================================================
class TestValidatorAcceptsWithinTolerance:

    def test_validator_accepts_within_half_hour_of_checkin(self):
        """7.0h claim accepted when check-in is 7.0h (exact match)."""
        from routers.home import validate_sleep_claims

        text = "You logged 7 hours of sleep last night."
        result = validate_sleep_claims(text, garmin_sleep_h=None, checkin_sleep_h=7.0)

        assert result["valid"] is True

    def test_validator_accepts_within_tolerance_of_garmin(self):
        """7.0h claim accepted when Garmin says 6.75h (delta = 0.25h < 0.5h tolerance)."""
        from routers.home import validate_sleep_claims

        text = "Your device recorded 7 hours of sleep last night."
        result = validate_sleep_claims(text, garmin_sleep_h=6.75, checkin_sleep_h=None)

        assert result["valid"] is True

    def test_validator_accepts_claim_matching_either_source(self):
        """In conflict case, claim matching either source (within tolerance) is accepted."""
        from routers.home import validate_sleep_claims

        # Garmin: 6.75, check-in: 7.0. Claim of 7.0h matches check-in exactly.
        text = "You reported 7 hours of sleep last night."
        result = validate_sleep_claims(text, garmin_sleep_h=6.75, checkin_sleep_h=7.0)

        assert result["valid"] is True


# ===========================================================================
# Test 8 — No numeric sleep claim when no numeric sources
# ===========================================================================
class TestNoNumericClaimWhenNoSources:

    def test_no_sources_and_no_claim_is_valid(self):
        """Text with no numeric sleep claim is valid when no sources exist."""
        from routers.home import validate_sleep_claims

        text = "Your sleep quality was good last night — keep it up."
        result = validate_sleep_claims(text, garmin_sleep_h=None, checkin_sleep_h=None)

        assert result["valid"] is True

    def test_no_sources_but_numeric_claim_is_invalid(self):
        """Numeric sleep claim without any source is invalid."""
        from routers.home import validate_sleep_claims

        text = "You slept 7.5 hours last night."
        result = validate_sleep_claims(text, garmin_sleep_h=None, checkin_sleep_h=None)

        assert result["valid"] is False


# ===========================================================================
# Test 9 — Conflict case: Garmin vs check-in does not invent third value
# ===========================================================================
class TestConflictCaseDoesNotInventThirdValue:

    def test_garmin_and_checkin_differ_and_claim_matches_one_source(self):
        """Garmin 6.75, check-in 7.0 — claim of 6.75h is valid (matches Garmin)."""
        from routers.home import validate_sleep_claims

        text = "Your Garmin recorded 6.75 hours of sleep last night."
        result = validate_sleep_claims(text, garmin_sleep_h=6.75, checkin_sleep_h=7.0)

        assert result["valid"] is True

    def test_garmin_and_checkin_differ_and_invented_value_rejected(self):
        """Garmin 6.75, check-in 7.0 — claim of 8.5h (invented) is rejected."""
        from routers.home import validate_sleep_claims

        text = "You slept 8.5 hours last night, perfect recovery."
        result = validate_sleep_claims(text, garmin_sleep_h=6.75, checkin_sleep_h=7.0)

        assert result["valid"] is False


# ===========================================================================
# Bonus — P0.2 gate: workout-duration numerics do NOT trigger sleep validator
# ===========================================================================
class TestFalsePositivePrevention:

    def test_workout_duration_does_not_trigger_sleep_validator(self):
        """'60-minute tempo run' should NOT be flagged as an ungrounded sleep claim."""
        from routers.home import validate_sleep_claims

        text = "Today's plan is a 60-minute tempo run at threshold effort."
        result = validate_sleep_claims(text, garmin_sleep_h=None, checkin_sleep_h=None)

        assert result["valid"] is True

    def test_race_time_does_not_trigger_sleep_validator(self):
        """'Finish in 3 hours 45 minutes' should NOT be flagged as a sleep claim.
        The sentence has no sleep-context keywords (sleep/slept/overnight/last night).
        """
        from routers.home import validate_sleep_claims

        text = "Your goal is to finish the marathon in 3 hours and 45 minutes."
        result = validate_sleep_claims(text, garmin_sleep_h=None, checkin_sleep_h=None)

        assert result["valid"] is True

    def test_pace_notation_does_not_trigger_sleep_validator(self):
        """'8:30/mi' or '5:20/km' should NOT be flagged."""
        from routers.home import validate_sleep_claims

        text = "Yesterday you averaged 8:30 per mile over 10 miles."
        result = validate_sleep_claims(text, garmin_sleep_h=None, checkin_sleep_h=None)

        assert result["valid"] is True
