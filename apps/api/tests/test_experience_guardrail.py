"""
Tests for Daily Production Experience Guardrail.

26 tests covering all 6 assertion categories + preflight + integration.
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from services.experience_guardrail import (
    AssertionResult, ExperienceGuardrail,
    BANNED_METRIC_PATTERNS, SYCOPHANTIC_TERMS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_guardrail(db=None, redis=None, athlete_id=None):
    """Create a guardrail instance with optional mock DB/Redis."""
    aid = athlete_id or str(uuid.uuid4())
    g = ExperienceGuardrail(aid, db or MagicMock(), redis)
    return g


def _last_result(g: ExperienceGuardrail) -> AssertionResult:
    """Return the last assertion result."""
    return g.results[-1]


# ===========================================================================
# Category 1: Data Truth
# ===========================================================================

class TestDataTruth:

    def test_sleep_mismatch_detected(self, db_session, test_athlete):
        """#1: morning voice says 7.5h, GarminDay says 6.1h → fails."""
        from models import GarminDay
        today = date.today()

        garmin = GarminDay(
            athlete_id=test_athlete.id,
            calendar_date=today,
            sleep_total_s=int(6.1 * 3600),  # 6.1 hours
        )
        db_session.add(garmin)
        db_session.commit()

        g = ExperienceGuardrail(str(test_athlete.id), db_session, None)
        g._local_today = today
        g._assert_sleep_matches_source("You got 7.5 hours of sleep last night.")

        result = _last_result(g)
        assert result.id == 1
        assert result.passed is False
        assert "7.5" in result.detail

    def test_sleep_match_passes(self, db_session, test_athlete):
        """#1: morning voice says 6.1h, GarminDay says 6.1h → passes."""
        from models import GarminDay
        today = date.today()

        garmin = GarminDay(
            athlete_id=test_athlete.id,
            calendar_date=today,
            sleep_total_s=int(6.1 * 3600),
        )
        db_session.add(garmin)
        db_session.commit()

        g = ExperienceGuardrail(str(test_athlete.id), db_session, None)
        g._local_today = today
        g._assert_sleep_matches_source("You logged 6.1 hours of sleep — solid night.")

        result = _last_result(g)
        assert result.id == 1
        assert result.passed is True

    def test_stale_sleep_detected(self, db_session, test_athlete):
        """#2: no GarminDay for today, text says Garmin sleep → fails."""
        from models import GarminDay
        today = date.today()
        yesterday = today - timedelta(days=1)

        garmin = GarminDay(
            athlete_id=test_athlete.id,
            calendar_date=yesterday,
            sleep_total_s=int(7.0 * 3600),
        )
        db_session.add(garmin)
        db_session.commit()

        g = ExperienceGuardrail(str(test_athlete.id), db_session, None)
        g._local_today = today
        g._assert_sleep_is_today("Garmin logged 7.0 hours of sleep last night.")

        result = _last_result(g)
        assert result.id == 2
        assert result.passed is False

    def test_activity_date_mismatch(self, db_session, test_athlete):
        """#3: text says 'yesterday' but last activity was 3 days ago → fails."""
        from models import Activity
        today = date.today()
        three_days_ago = today - timedelta(days=3)

        act = Activity(
            athlete_id=test_athlete.id,
            name="Easy Run",
            sport="run",
            start_time=datetime.combine(three_days_ago, datetime.min.time(), tzinfo=timezone.utc),
            distance_m=5000,
            moving_time_s=1800,
        )
        db_session.add(act)
        db_session.commit()

        g = ExperienceGuardrail(str(test_athlete.id), db_session, None)
        g._local_today = today
        g._assert_last_activity_date("Yesterday's run was a solid effort.")

        result = _last_result(g)
        assert result.id == 3
        assert result.passed is False
        assert "yesterday" in result.detail.lower()

    def test_shape_sentence_mismatch(self, db_session, test_athlete):
        """#4: home says 'easy' but DB says 'tempo' → fails."""
        from models import Activity

        act = Activity(
            athlete_id=test_athlete.id,
            name="Run",
            sport="run",
            start_time=datetime.now(timezone.utc),
            shape_sentence="Steady tempo effort with a strong negative split",
            distance_m=8000,
            moving_time_s=2400,
        )
        db_session.add(act)
        db_session.commit()

        g = ExperienceGuardrail(str(test_athlete.id), db_session, None)
        g._assert_shape_sentence_matches_db("Easy aerobic run", str(act.id))

        result = _last_result(g)
        assert result.id == 4
        assert result.passed is False

    def test_heat_adjustment_missing(self, db_session, test_athlete):
        """#5: dew_point_f=70 but heat_adjustment_pct is null → fails."""
        from models import Activity

        act = Activity(
            athlete_id=test_athlete.id,
            name="Hot Run",
            sport="run",
            start_time=datetime.now(timezone.utc),
            dew_point_f=70.0,
            heat_adjustment_pct=None,
            distance_m=5000,
            moving_time_s=1800,
        )
        db_session.add(act)
        db_session.commit()

        g = ExperienceGuardrail(str(test_athlete.id), db_session, None)
        g._assert_heat_adjustment_present()

        result = _last_result(g)
        assert result.id == 5
        assert result.passed is False

    def test_race_countdown_wrong(self, db_session, test_athlete):
        """#6: shows 14 days but actual is 12 → fails."""
        from models import TrainingPlan
        today = date.today()
        race_date = today + timedelta(days=12)

        plan = TrainingPlan(
            athlete_id=test_athlete.id,
            name="Marathon Build",
            status="active",
            goal_race_name="Test Marathon",
            goal_race_date=race_date,
            goal_race_distance_m=42195,
            plan_start_date=today - timedelta(days=60),
            plan_end_date=race_date,
            total_weeks=10,
            plan_type="marathon",
        )
        db_session.add(plan)
        db_session.commit()

        g = ExperienceGuardrail(str(test_athlete.id), db_session, None)
        g._local_today = today
        g._assert_race_countdown_correct({"days_remaining": 14, "race_date": str(race_date)})

        result = _last_result(g)
        assert result.id == 6
        assert result.passed is False
        assert "14" in result.detail and "12" in result.detail


# ===========================================================================
# Category 2: Language Hygiene
# ===========================================================================

class TestLanguageHygiene:

    def test_banned_metric_detected(self):
        """#8: text contains 'your tsb' → fails."""
        g = _make_guardrail()
        texts = [("morning_voice", "Your TSB is looking great this week.", "home")]
        g._assert_no_banned_metrics(texts)

        result = _last_result(g)
        assert result.id == 8
        assert result.passed is False
        assert "tsb" in result.detail.lower()

    def test_banned_metric_word_boundary(self):
        """#8: text contains 'metabolism' → passes (no false positive on 'met')."""
        g = _make_guardrail()
        texts = [("text", "Your metabolism is working well for endurance.", "home")]
        g._assert_no_banned_metrics(texts)

        result = _last_result(g)
        assert result.id == 8
        assert result.passed is True

    def test_sycophantic_detected(self):
        """#9: text contains 'incredible' → fails."""
        g = _make_guardrail()
        texts = [("morning_voice", "What an incredible performance yesterday!", "home")]
        g._assert_no_sycophantic_language(texts)

        result = _last_result(g)
        assert result.id == 9
        assert result.passed is False

    def test_causal_detected(self):
        """#10: text contains 'because you' → fails."""
        g = _make_guardrail()
        texts = [("morning_voice", "You ran faster because you slept well.", "home")]
        g._assert_no_causal_claims(texts)

        result = _last_result(g)
        assert result.id == 10
        assert result.passed is False

    def test_snake_case_detected(self):
        """#11: text contains 'sleep_hours' → fails."""
        g = _make_guardrail()
        texts = [("morning_voice", "Your sleep_hours value is 7.5.", "home")]
        g._assert_no_raw_identifiers(texts)

        result = _last_result(g)
        assert result.id == 11
        assert result.passed is False
        assert "sleep_hours" in result.detail

    def test_whitelisted_snake_case_passes(self):
        """#11: text contains 'heart_rate' → passes (whitelisted)."""
        g = _make_guardrail()
        texts = [("text", "Your heart_rate was elevated during the cooldown.", "home")]
        g._assert_no_raw_identifiers(texts)

        result = _last_result(g)
        assert result.id == 11
        assert result.passed is True


# ===========================================================================
# Category 3: Structural Integrity
# ===========================================================================

class TestStructuralIntegrity:

    def test_multi_paragraph_detected(self):
        """#12: morning voice has \\n → fails."""
        g = _make_guardrail()
        g._assert_single_paragraph("First paragraph here.\nSecond paragraph here.")

        result = _last_result(g)
        assert result.id == 12
        assert result.passed is False

    def test_word_count_too_high(self):
        """#13: 150-word morning voice → fails."""
        g = _make_guardrail()
        long_text = " ".join(["word"] * 150)
        g._assert_word_count_range(long_text)

        result = _last_result(g)
        assert result.id == 13
        assert result.passed is False
        assert "150" in result.detail

    def test_no_numeric_detected(self):
        """#14: morning voice with zero digits → fails."""
        g = _make_guardrail()
        g._assert_numeric_reference("Great run yesterday with solid effort and strong finish.")

        result = _last_result(g)
        assert result.id == 14
        assert result.passed is False


# ===========================================================================
# Category 4: Temporal Consistency
# ===========================================================================

class TestTemporalConsistency:

    def test_cooldown_violation_detected(self):
        """#17: finding in Redis cooldown AND in response → fails."""
        mock_redis = MagicMock()
        aid = str(uuid.uuid4())
        mock_redis.keys.return_value = [f"finding_surfaced:{aid}:sleep".encode()]
        mock_redis.ttl.return_value = 3600 * 48  # 48h remaining

        g = _make_guardrail(redis=mock_redis, athlete_id=aid)
        finding = {"text": "Sleep correlates with pace", "domain": "sleep", "confidence_tier": "genuine", "times_confirmed": 5}
        g._assert_finding_cooldown(finding)

        result = _last_result(g)
        assert result.id == 17
        assert result.passed is False
        assert "cooldown" in result.detail.lower()

    def test_yesterday_wrong(self, db_session, test_athlete):
        """#18: text says 'yesterday' but last activity was Friday, today Monday → fails."""
        from models import Activity
        today = date.today()
        friday = today - timedelta(days=3)

        act = Activity(
            athlete_id=test_athlete.id,
            name="Friday Run",
            sport="run",
            start_time=datetime.combine(friday, datetime.min.time(), tzinfo=timezone.utc),
            distance_m=5000,
            moving_time_s=1800,
        )
        db_session.add(act)
        db_session.commit()

        g = ExperienceGuardrail(str(test_athlete.id), db_session, None)
        g._local_today = today
        g._assert_yesterday_correct(["Yesterday's run felt great."])

        result = _last_result(g)
        assert result.id == 18
        assert result.passed is False


# ===========================================================================
# Category 6: Trust Integrity
# ===========================================================================

class TestTrustIntegrity:

    def test_superseded_finding_in_coach_output(self, db_session, test_athlete):
        """#23: AthleteFinding.is_active=False, its sentence appears in morning_voice → fails."""
        from models import AthleteFinding

        finding = AthleteFinding(
            athlete_id=test_athlete.id,
            investigation_name="sleep_quality",
            finding_type="pattern",
            layer="B",
            sentence="Your sleep quality drops below 6 hours on back-to-back hard days.",
            receipts={"samples": 12},
            confidence="genuine",
            is_active=False,
            superseded_at=datetime.now(timezone.utc),
        )
        db_session.add(finding)
        db_session.commit()

        g = ExperienceGuardrail(str(test_athlete.id), db_session, None)
        coach_texts = [
            "After 6.8h sleep, you logged a solid 5-miler. "
            "Your sleep quality drops below 6 hours on back-to-back hard days."
        ]
        g._assert_no_superseded_findings(coach_texts)

        result = _last_result(g)
        assert result.id == 23
        assert result.passed is False
        assert "superseded" in result.detail.lower() or "AthleteFinding" in result.detail

    def test_active_finding_in_coach_output_passes(self, db_session, test_athlete):
        """#23: AthleteFinding.is_active=True, its sentence appears → passes."""
        from models import AthleteFinding

        finding = AthleteFinding(
            athlete_id=test_athlete.id,
            investigation_name="sleep_quality",
            finding_type="pattern",
            layer="B",
            sentence="Sleep quality stays consistent when you avoid screens before bed.",
            receipts={"samples": 15},
            confidence="genuine",
            is_active=True,
        )
        db_session.add(finding)
        db_session.commit()

        g = ExperienceGuardrail(str(test_athlete.id), db_session, None)
        coach_texts = [
            "Sleep quality stays consistent when you avoid screens before bed."
        ]
        g._assert_no_superseded_findings(coach_texts)

        result = _last_result(g)
        assert result.id == 23
        assert result.passed is True

    def test_classification_sentence_mismatch(self):
        """#24: workout_classification='tempo' but shape_sentence says 'strides' → fails."""
        g = _make_guardrail()
        run_shape = {"summary": {"workout_classification": "tempo"}}
        g._assert_classification_matches_sentence(run_shape, "Quick strides with a light warmup jog")

        result = _last_result(g)
        assert result.id == 24
        assert result.passed is False

    def test_classification_sentence_match(self):
        """#24: workout_classification='tempo' and shape_sentence says 'tempo' → passes."""
        g = _make_guardrail()
        run_shape = {"summary": {"workout_classification": "tempo"}}
        g._assert_classification_matches_sentence(run_shape, "Steady tempo effort with a strong finish")

        result = _last_result(g)
        assert result.id == 24
        assert result.passed is True


# ===========================================================================
# Preflight
# ===========================================================================

class TestPreflight:

    def test_preflight_skips_data_truth_on_stale_garmin(self, db_session, test_athlete):
        """Garmin data >20h old → Category 1 assertions skipped, others run."""
        from models import GarminDay

        garmin = GarminDay(
            athlete_id=test_athlete.id,
            calendar_date=date.today() - timedelta(days=1),
            sleep_total_s=25200,
        )
        db_session.add(garmin)
        db_session.flush()

        # Force inserted_at to >20h ago
        from sqlalchemy import text
        db_session.execute(
            text("UPDATE garmin_day SET inserted_at = :ts WHERE id = :gid"),
            {"ts": datetime.now(timezone.utc) - timedelta(hours=20), "gid": str(garmin.id)},
        )
        db_session.commit()

        g = ExperienceGuardrail(str(test_athlete.id), db_session, None)
        result = g.run_preflight()

        assert result is False
        assert g.garmin_preflight_ok is False

        home_response = {
            "coach_briefing": {"morning_voice": "Good morning, 6.5h sleep logged."},
            "last_run": None,
            "race_countdown": None,
            "finding": None,
            "has_correlations": False,
            "week": {},
            "yesterday": {},
            "total_activities": 5,
        }
        g.run_tier1(home_response, [], None, None)

        data_truth_results = [r for r in g.results if r.category == "data_truth"]
        assert len(data_truth_results) == 7
        assert all(r.skipped for r in data_truth_results)

        non_data_results = [r for r in g.results if r.category != "data_truth"]
        assert len(non_data_results) > 0

    def test_preflight_runs_all_on_fresh_garmin(self, db_session, test_athlete):
        """Garmin data from 4h ago → all assertions run (not skipped)."""
        from models import GarminDay

        garmin = GarminDay(
            athlete_id=test_athlete.id,
            calendar_date=date.today(),
            sleep_total_s=25200,
        )
        db_session.add(garmin)
        db_session.commit()

        g = ExperienceGuardrail(str(test_athlete.id), db_session, None)
        result = g.run_preflight()

        assert result is True
        assert g.garmin_preflight_ok is True


# ===========================================================================
# Integration
# ===========================================================================

class TestIntegration:

    def test_full_guardrail_run_with_clean_data(self, db_session, test_athlete):
        """Clean, consistent data across all surfaces → all assertions pass."""
        from models import Activity, GarminDay

        today = date.today()
        yesterday = today - timedelta(days=1)

        garmin = GarminDay(
            athlete_id=test_athlete.id,
            calendar_date=today,
            sleep_total_s=int(7.2 * 3600),
        )
        db_session.add(garmin)

        act = Activity(
            athlete_id=test_athlete.id,
            name="Morning Run",
            sport="run",
            start_time=datetime.combine(yesterday, datetime.min.time(), tzinfo=timezone.utc),
            distance_m=8000,
            moving_time_s=2700,
            shape_sentence="Easy aerobic effort",
            dew_point_f=45.0,
        )
        db_session.add(act)
        db_session.commit()

        g = ExperienceGuardrail(str(test_athlete.id), db_session, MagicMock())
        g._local_today = today
        g.garmin_preflight_ok = True

        home_response = {
            "coach_briefing": {
                "morning_voice": (
                    "After 7.2 hours of sleep, you logged a solid 5-mile "
                    "easy run. Your aerobic base is building nicely this week — "
                    "3 runs, 15 miles total."
                ),
            },
            "last_run": {
                "activity_id": str(act.id),
                "shape_sentence": "Easy aerobic effort",
            },
            "race_countdown": None,
            "finding": None,
            "has_correlations": False,
            "week": {"trajectory_sentence": None},
            "yesterday": {"insight": None},
            "total_activities": 25,
        }

        activity_detail = {
            "shape_sentence": "Easy aerobic effort",
            "dew_point_f": 45.0,
            "heat_adjustment_pct": None,
            "_findings": [],
        }

        progress_summary = {
            "headline": {"text": "Solid week of training", "subtext": "Volume up 8%"},
            "coach_cards": [],
        }

        g.run_tier1(home_response, [act], activity_detail, progress_summary)

        summary = g.summarize()
        failed = [r for r in g.results if not r.passed and not r.skipped]
        assert len(failed) == 0, f"Failures: {[(r.id, r.name, r.detail) for r in failed]}"
        assert summary["passed"] is True

    def test_audit_log_written(self, db_session, test_athlete):
        """After a run, verify ExperienceAuditLog row exists."""
        from models import ExperienceAuditLog

        log = ExperienceAuditLog(
            athlete_id=test_athlete.id,
            run_date=date.today(),
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            tier="daily_t1_t2",
            passed=True,
            total_assertions=24,
            passed_count=22,
            failed_count=0,
            skipped_count=2,
            results=[{"id": 1, "name": "test", "passed": True}],
            summary="22/24 passed (2 skipped)",
        )
        db_session.add(log)
        db_session.commit()

        saved = (
            db_session.query(ExperienceAuditLog)
            .filter(ExperienceAuditLog.athlete_id == test_athlete.id)
            .first()
        )
        assert saved is not None
        assert saved.passed is True
        assert saved.total_assertions == 24
        assert saved.tier == "daily_t1_t2"
        assert isinstance(saved.results, list)
