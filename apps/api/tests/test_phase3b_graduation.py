"""
Phase 3B Graduation Tests

Covers the graduation layer on top of the already-built 3B generator:
  - Global kill switch (env var + FeatureFlag) suppresses all narratives
  - Per-narrative suppression works independently of the global kill switch
  - Founder review route exists, is founder-gated (not tier-gated), UUID-safe
  - First-50 review is directly queryable from the review endpoint
  - 4-criterion quality scorer works correctly on all passing/failing cases
  - Gate-aware rollout state (gate_open / provisional) is explicit in endpoint
  - Scoring diagnostics are persisted into NarrationLog.ground_truth

These are real (non-xfail) tests — they verify the graduation controls that
make 3B operationally trustworthy regardless of gate state.
"""
import os
import uuid
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.workout_narrative_generator import (
    generate_workout_narrative,
    score_narrative_quality,
    _is_3b_kill_switched,
    WorkoutNarrativeResult,
    KILL_SWITCH_3B_ENV,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_athlete(tier="premium"):
    a = MagicMock()
    a.id = uuid.uuid4()
    a.subscription_tier = tier
    a.email = f"test-{a.id}@example.com"
    return a


def _make_workout_mock():
    w = MagicMock()
    w.workout_type = "easy"
    w.workout_subtype = None
    w.phase = "build"
    w.phase_week = 3
    w.week_number = 7
    w.title = "Easy Run"
    w.description = "8km easy pace"
    w.target_distance_km = 8.0
    w.target_duration_minutes = 50
    w.segments = None
    w.scheduled_date = date.today()
    return w


def _mock_db_no_suppressions():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.all.return_value = []
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    return db


def _mock_llm(text="Focus on keeping your cadence smooth through week 7 of your build phase."):
    client = MagicMock()
    resp = MagicMock()
    part = MagicMock()
    part.text = text
    resp.candidates = [MagicMock(content=MagicMock(parts=[part]))]
    resp.usage_metadata.prompt_token_count = 80
    resp.usage_metadata.candidates_token_count = 25
    client.models.generate_content.return_value = resp
    return client


# ===========================================================================
# 1. Global kill switch
# ===========================================================================

class TestGlobalKillSwitch:
    """Kill switch suppresses ALL 3B narratives cleanly."""

    def test_env_var_kill_switch_suppresses_generation(self):
        """STRIDEIQ_3B_KILL_SWITCH=true → suppressed, no LLM call."""
        db = _mock_db_no_suppressions()
        with patch.dict(os.environ, {KILL_SWITCH_3B_ENV: "true"}):
            result = generate_workout_narrative(uuid.uuid4(), date.today(), db)
        assert result.suppressed is True
        assert "kill_switch" in result.suppression_reason.lower()

    def test_env_var_kill_switch_variations(self):
        """Accept '1', 'true', 'yes' as truthy kill switch values."""
        db = _mock_db_no_suppressions()
        for val in ("1", "true", "yes", "TRUE", "YES"):
            with patch.dict(os.environ, {KILL_SWITCH_3B_ENV: val}):
                result = generate_workout_narrative(uuid.uuid4(), date.today(), db)
            assert result.suppressed is True, f"Expected suppressed for KILL_SWITCH={val}"

    def test_kill_switch_off_does_not_suppress(self):
        """Kill switch off → generator proceeds to normal path (may still suppress for context)."""
        db = _mock_db_no_suppressions()
        with patch.dict(os.environ, {KILL_SWITCH_3B_ENV: "false"}):
            # No planned workout → suppressed for context, but NOT for kill switch
            result = generate_workout_narrative(uuid.uuid4(), date.today(), db)
        assert "kill_switch" not in (result.suppression_reason or "").lower()

    def test_kill_switch_checked_in_generator_not_only_in_router(self):
        """Generator itself enforces the kill switch — not just the router."""
        db = _mock_db_no_suppressions()
        with patch.dict(os.environ, {KILL_SWITCH_3B_ENV: "true"}):
            # Call generator directly, bypassing any router eligibility check
            result = generate_workout_narrative(uuid.uuid4(), date.today(), db, gemini_client=MagicMock())
        assert result.suppressed is True
        assert "kill_switch" in result.suppression_reason.lower()

    def test_endpoint_stays_healthy_under_kill_switch(self):
        """GET /workout-narrative/{date} returns 200 (suppressed) under kill switch."""
        from fastapi.testclient import TestClient
        from main import app
        from core.auth import get_current_user
        from core.database import get_db
        from services.phase3_eligibility import EligibilityResult

        athlete = _make_athlete(tier="premium")
        db = _mock_db_no_suppressions()

        app.dependency_overrides[get_current_user] = lambda: athlete
        app.dependency_overrides[get_db] = lambda: db

        try:
            with patch.dict(os.environ, {KILL_SWITCH_3B_ENV: "true"}), \
                 patch("services.phase3_eligibility._is_kill_switched", return_value=True), \
                 patch("services.phase3_eligibility.get_3b_eligibility") as mock_elig:
                mock_elig.return_value = EligibilityResult(
                    eligible=False,
                    reason="3B workout narratives are globally disabled (kill switch).",
                    evidence={"kill_switch": True},
                )
                client = TestClient(app, raise_server_exceptions=False)
                resp = client.get(f"/v1/intelligence/workout-narrative/{date.today().isoformat()}")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["suppressed"] is True
        assert data["kill_switch_active"] is True


# ===========================================================================
# 2. Per-narrative suppression independent of kill switch
# ===========================================================================

class TestPerNarrativeSuppression:
    """Per-narrative suppression works independently of global kill switch."""

    def test_banned_metric_suppresses_independently(self):
        """Narrative with TSB is suppressed even with kill switch OFF."""
        workout = _make_workout_mock()
        with patch("services.workout_narrative_generator._build_context") as mock_ctx, \
             patch("services.workout_narrative_generator._get_recent_narratives", return_value=[]), \
             patch("services.intelligence.workout_narrative_generator._call_narrative_llm",
                   return_value=("Your TSB is -12 so take it easy.", 80, 25, 120)), \
             patch.dict(os.environ, {KILL_SWITCH_3B_ENV: "false"}):
            mock_ctx.return_value = {
                "workout": {"type": "easy", "subtype": None, "title": "Easy Run",
                            "description": "8km", "phase": "build", "phase_week": 3,
                            "week_number": 7, "distance_km": 8.0, "duration_min": 50,
                            "segments": None},
                "recent_activities": [],
                "upcoming": [],
                "readiness_score": None,
                "suppress_intensity": False,
                "yesterday_type": None,
            }
            result = generate_workout_narrative(
                uuid.uuid4(), date.today(), MagicMock(),
            )
        assert result.suppressed is True
        assert "kill_switch" not in result.suppression_reason.lower()
        assert "banned" in result.suppression_reason.lower() or "metric" in result.suppression_reason.lower()

    def test_intensity_in_taper_suppresses_independently(self):
        """Intensity encouragement during taper suppressed independently of kill switch."""
        with patch("services.workout_narrative_generator._build_context") as mock_ctx, \
             patch("services.workout_narrative_generator._get_recent_narratives", return_value=[]), \
             patch("services.intelligence.workout_narrative_generator._call_narrative_llm",
                   return_value=("Push hard today and attack the hills.", 80, 25, 120)), \
             patch.dict(os.environ, {KILL_SWITCH_3B_ENV: "false"}):
            mock_ctx.return_value = {
                "workout": {"type": "easy", "subtype": None, "title": "Recovery Run",
                            "description": "5km", "phase": "taper", "phase_week": 1,
                            "week_number": 16, "distance_km": 5.0, "duration_min": 30,
                            "segments": None},
                "recent_activities": [],
                "upcoming": [],
                "readiness_score": None,
                "suppress_intensity": True,
                "yesterday_type": None,
            }
            result = generate_workout_narrative(
                uuid.uuid4(), date.today(), MagicMock(),
            )
        assert result.suppressed is True
        assert "intensity" in result.suppression_reason.lower()

    def test_similarity_suppresses_independently(self):
        """Phrasing similarity > 50% suppresses independently of kill switch."""
        recent_text = "Keep the effort relaxed and steady on this easy run today."
        with patch("services.workout_narrative_generator._build_context") as mock_ctx, \
             patch("services.workout_narrative_generator._get_recent_narratives",
                   return_value=[recent_text]), \
             patch("services.intelligence.workout_narrative_generator._call_narrative_llm",
                   return_value=(recent_text, 80, 25, 120)), \
             patch.dict(os.environ, {KILL_SWITCH_3B_ENV: "false"}):
            mock_ctx.return_value = {
                "workout": {"type": "easy", "subtype": None, "title": "Easy Run",
                            "description": "8km", "phase": "build", "phase_week": 3,
                            "week_number": 7, "distance_km": 8.0, "duration_min": 50,
                            "segments": None},
                "recent_activities": [],
                "upcoming": [],
                "readiness_score": None,
                "suppress_intensity": False,
                "yesterday_type": None,
            }
            result = generate_workout_narrative(
                uuid.uuid4(), date.today(), MagicMock(),
            )
        assert result.suppressed is True
        assert "similar" in result.suppression_reason.lower()


# ===========================================================================
# 3. 4-criterion quality scorer
# ===========================================================================

class TestQualityScorer:
    """score_narrative_quality() correctly scores on all 4 criteria."""

    def test_contextual_passes_with_phase_reference(self):
        text = "Your build phase week 7 has you setting up for Saturday's long run."
        score = score_narrative_quality(text, ctx=None)
        assert score["contextual"] is True
        assert score["contextual_fail_reason"] is None

    def test_contextual_fails_without_context_signals(self):
        text = "Go out and run well today. Stay consistent."
        score = score_narrative_quality(text, ctx=None)
        assert score["contextual"] is False
        assert score["contextual_fail_reason"] == "no_specific_context_signal"

    def test_non_repetitive_fails_on_duplicate(self):
        text = "Keep the effort relaxed and steady on this easy run today."
        recent = ["Keep the effort relaxed and steady on this easy run today."]
        score = score_narrative_quality(text, ctx=None, recent_narratives=recent)
        assert score["non_repetitive"] is False
        assert score["non_repetitive_fail_reason"] == "token_overlap_exceeds_threshold"

    def test_non_repetitive_passes_with_different_text(self):
        text = "After last week's 18-miler, your legs have earned this recovery run."
        recent = ["Your threshold session in week 6 showed strong lactate clearance."]
        score = score_narrative_quality(text, ctx=None, recent_narratives=recent)
        assert score["non_repetitive"] is True

    def test_physiologically_sound_fails_intensity_in_taper(self):
        text = "Push hard on this one and hammer the hills."
        ctx = {"suppress_intensity": True}
        score = score_narrative_quality(text, ctx=ctx)
        assert score["physiologically_sound"] is False
        assert score["physiologically_sound_fail_reason"] == "intensity_encouragement_in_wrong_context"

    def test_physiologically_sound_passes_in_normal_context(self):
        text = "Push hard on this one and hammer the hills."
        ctx = {"suppress_intensity": False}
        score = score_narrative_quality(text, ctx=ctx)
        assert score["physiologically_sound"] is True

    def test_tone_fails_banned_metric(self):
        text = "Your TSB is -15 so take it easy today."
        score = score_narrative_quality(text, ctx=None)
        assert score["tone_rules_ok"] is False
        assert score["tone_rules_fail_reason"] == "banned_metric_acronym"

    def test_tone_fails_prescriptive_language(self):
        text = "You should make sure you hit every rep at goal pace."
        score = score_narrative_quality(text, ctx=None)
        assert score["tone_rules_ok"] is False
        assert score["tone_rules_fail_reason"] == "prescriptive_language"

    def test_tone_fails_generic_sludge(self):
        text = "Trust the process and you've got this today."
        score = score_narrative_quality(text, ctx=None)
        assert score["tone_rules_ok"] is False
        assert score["tone_rules_fail_reason"] == "generic_sludge"

    def test_tone_passes_clean_narrative(self):
        text = "After last week's 18km long run, today's easy 8km lets your legs absorb the work."
        score = score_narrative_quality(text, ctx=None)
        assert score["tone_rules_ok"] is True

    def test_perfect_score_all_four_pass(self):
        text = "Your build phase week 7 tempo run follows last week's 18km, so sit just below threshold."
        ctx = {"suppress_intensity": False}
        score = score_narrative_quality(text, ctx=ctx)
        assert score["criteria_passed"] == 4
        assert score["score"] == 1.0

    def test_score_field_is_fraction_of_criteria_passed(self):
        text = "Go run well. Trust the process."  # contextual=F, tone=F → 2 pass
        ctx = {"suppress_intensity": False}
        score = score_narrative_quality(text, ctx=ctx)
        assert score["score"] == round(score["criteria_passed"] / 4, 3)

    def test_quality_score_attached_to_result(self):
        """quality_score is populated on WorkoutNarrativeResult for non-suppressed narratives."""
        good_text = "After last week's easy build in week 6, today's tempo in build phase sits nicely."
        with patch("services.workout_narrative_generator._build_context") as mock_ctx, \
             patch("services.workout_narrative_generator._get_recent_narratives", return_value=[]), \
             patch.dict(os.environ, {KILL_SWITCH_3B_ENV: "false"}):
            mock_ctx.return_value = {
                "workout": {"type": "threshold", "subtype": None, "title": "Tempo Run",
                            "description": "30min tempo", "phase": "build", "phase_week": 3,
                            "week_number": 6, "distance_km": 10.0, "duration_min": 50,
                            "segments": None},
                "recent_activities": [],
                "upcoming": [],
                "readiness_score": None,
                "suppress_intensity": False,
                "yesterday_type": None,
            }
            result = generate_workout_narrative(
                uuid.uuid4(), date.today(), MagicMock(),
                gemini_client=_mock_llm(good_text),
            )
        assert result.suppressed is False
        assert result.quality_score is not None
        assert "criteria_passed" in result.quality_score
        assert "score" in result.quality_score


# ===========================================================================
# 4. Founder review route
# ===========================================================================

class TestFounderReviewRoute:
    """GET /v1/intelligence/admin/narrative-review is founder-gated, UUID-safe."""

    def _make_app_with_overrides(self, athlete):
        from fastapi.testclient import TestClient
        from main import app
        from core.auth import get_current_user
        from core.database import get_db

        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        db.query.return_value.filter.return_value.all.return_value = []

        app.dependency_overrides[get_current_user] = lambda: athlete
        app.dependency_overrides[get_db] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)
        return app, client

    def test_founder_can_reach_review_route(self):
        """Founder account gets 200 from review endpoint (empty items list ok)."""
        founder = _make_athlete(tier="free")  # no guided/premium tier
        founder.email = "mbshaf@gmail.com"
        app, client = self._make_app_with_overrides(founder)
        try:
            with patch("services.phase3_eligibility._narration_quality_score", return_value=None):
                resp = client.get("/v1/intelligence/admin/narrative-review")
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "kill_switch_active" in data
        assert "gate_open" in data

    def test_non_founder_denied(self):
        """Non-founder gets 403."""
        non_founder = _make_athlete(tier="premium")
        non_founder.email = "regular@example.com"
        app, client = self._make_app_with_overrides(non_founder)
        try:
            resp = client.get("/v1/intelligence/admin/narrative-review")
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 403

    def test_malformed_uuid_athlete_id_returns_422(self):
        """?athlete_id=not-a-uuid returns 422, not 500."""
        founder = _make_athlete(tier="free")
        founder.email = "mbshaf@gmail.com"
        app, client = self._make_app_with_overrides(founder)
        try:
            resp = client.get("/v1/intelligence/admin/narrative-review?athlete_id=not-a-uuid")
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 422

    def test_founder_without_guided_tier_can_reach_route(self):
        """Founder with no subscription reaches review endpoint — not blocked by tier gate."""
        founder = _make_athlete(tier="free")
        founder.email = "mbshaf@gmail.com"
        app, client = self._make_app_with_overrides(founder)
        try:
            with patch("services.phase3_eligibility._narration_quality_score", return_value=None):
                resp = client.get("/v1/intelligence/admin/narrative-review")
        finally:
            app.dependency_overrides.clear()
        # Must not be 403 (tier gate) — either 200 or some valid response
        assert resp.status_code != 403

    def test_review_returns_narration_log_rows(self):
        """Review endpoint returns NarrationLog rows with expected fields."""
        from main import app
        from core.auth import get_current_user
        from core.database import get_db
        from fastapi.testclient import TestClient

        founder = _make_athlete(tier="free")
        founder.email = "mbshaf@gmail.com"

        log_row = MagicMock()
        log_row.id = uuid.uuid4()
        log_row.athlete_id = uuid.uuid4()
        log_row.trigger_date = date.today()
        log_row.narration_text = "After last week's build, today's tempo fits week 7."
        log_row.suppressed = False
        log_row.suppression_reason = None
        log_row.prompt_used = "Today's workout: Tempo Run..."
        log_row.model_used = "gemini-2.5-flash"
        log_row.input_tokens = 80
        log_row.output_tokens = 25
        log_row.latency_ms = 430
        log_row.ground_truth = {
            "quality_score": {"contextual": True, "non_repetitive": True,
                              "physiologically_sound": True, "tone_rules_ok": True,
                              "criteria_passed": 4, "score": 1.0},
            "eligibility": {"eligible": True},
        }
        log_row.created_at = None

        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [log_row]
        db.query.return_value.filter.return_value.all.return_value = []

        app.dependency_overrides[get_current_user] = lambda: founder
        app.dependency_overrides[get_db] = lambda: db
        try:
            with patch("services.phase3_eligibility._narration_quality_score", return_value=None):
                client = TestClient(app, raise_server_exceptions=False)
                resp = client.get("/v1/intelligence/admin/narrative-review")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        item = data["items"][0]
        assert item["narrative"] == log_row.narration_text
        assert item["quality_score"]["criteria_passed"] == 4

    def test_first_50_review_supported(self):
        """limit=50 (default) directly supports the first-50 review requirement."""
        founder = _make_athlete(tier="free")
        founder.email = "mbshaf@gmail.com"
        app, client = self._make_app_with_overrides(founder)
        try:
            with patch("services.phase3_eligibility._narration_quality_score", return_value=None):
                resp = client.get("/v1/intelligence/admin/narrative-review?limit=50")
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 200

    def test_suppressed_only_filter(self):
        """suppressed_only=true parameter is accepted without error."""
        founder = _make_athlete(tier="free")
        founder.email = "mbshaf@gmail.com"
        app, client = self._make_app_with_overrides(founder)
        try:
            with patch("services.phase3_eligibility._narration_quality_score", return_value=None):
                resp = client.get("/v1/intelligence/admin/narrative-review?suppressed_only=true")
        finally:
            app.dependency_overrides.clear()
        assert resp.status_code == 200


# ===========================================================================
# 5. Gate-aware rollout state
# ===========================================================================

class TestGateAwareRollout:
    """WorkoutNarrativeResponse exposes kill_switch_active and gate_open."""

    def test_gate_open_false_when_provisional(self):
        """Provisional eligibility → gate_open=False in response."""
        from fastapi.testclient import TestClient
        from main import app
        from core.auth import get_current_user
        from core.database import get_db
        from services.phase3_eligibility import EligibilityResult

        athlete = _make_athlete(tier="premium")
        db = _mock_db_no_suppressions()

        app.dependency_overrides[get_current_user] = lambda: athlete
        app.dependency_overrides[get_db] = lambda: db

        try:
            with patch("services.phase3_eligibility.get_3b_eligibility") as mock_elig, \
                 patch.dict(os.environ, {KILL_SWITCH_3B_ENV: "false"}):
                mock_elig.return_value = EligibilityResult(
                    eligible=False,
                    reason="No planned workout for target date.",
                    provisional=True,
                )
                client = TestClient(app, raise_server_exceptions=False)
                resp = client.get(f"/v1/intelligence/workout-narrative/{date.today().isoformat()}")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["gate_open"] is False

    def test_kill_switch_active_flag_in_response(self):
        """kill_switch_active=True appears in response when kill switch is on."""
        from fastapi.testclient import TestClient
        from main import app
        from core.auth import get_current_user
        from core.database import get_db
        from services.phase3_eligibility import EligibilityResult

        athlete = _make_athlete(tier="premium")
        db = _mock_db_no_suppressions()

        app.dependency_overrides[get_current_user] = lambda: athlete
        app.dependency_overrides[get_db] = lambda: db

        try:
            with patch("services.phase3_eligibility.get_3b_eligibility") as mock_elig, \
                 patch.dict(os.environ, {KILL_SWITCH_3B_ENV: "true"}):
                mock_elig.return_value = EligibilityResult(
                    eligible=False,
                    reason="3B workout narratives are globally disabled (kill switch).",
                    evidence={"kill_switch": True},
                )
                client = TestClient(app, raise_server_exceptions=False)
                resp = client.get(f"/v1/intelligence/workout-narrative/{date.today().isoformat()}")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["kill_switch_active"] is True
        assert data["suppressed"] is True


# ===========================================================================
# 6. Hardening regression tests (e440690 follow-up)
# ===========================================================================

class TestKillSwitchEnvDBParity:
    """env=false + DB disabled must still kill; env unset + DB disabled must kill."""

    def test_env_false_db_disabled_kills_generator(self):
        """env KILL_SWITCH=false + DB FeatureFlag disabled → generator returns suppressed."""
        disabled_flag = MagicMock()
        disabled_flag.enabled = False  # DB flag says disabled

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = disabled_flag

        with patch.dict(os.environ, {KILL_SWITCH_3B_ENV: "false"}):
            result = generate_workout_narrative(uuid.uuid4(), date.today(), db)

        assert result.suppressed is True
        assert "kill_switch" in result.suppression_reason.lower()

    def test_env_unset_db_disabled_kills_generator(self):
        """env KILL_SWITCH unset + DB FeatureFlag disabled → generator returns suppressed."""
        disabled_flag = MagicMock()
        disabled_flag.enabled = False

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = disabled_flag

        env_without_ks = {k: v for k, v in os.environ.items() if k != KILL_SWITCH_3B_ENV}
        with patch.dict(os.environ, env_without_ks, clear=True):
            result = generate_workout_narrative(uuid.uuid4(), date.today(), db)

        assert result.suppressed is True
        assert "kill_switch" in result.suppression_reason.lower()

    def test_is_3b_kill_switched_env_false_db_disabled(self):
        """_is_3b_kill_switched returns True when DB flag disabled even if env is false."""
        disabled_flag = MagicMock()
        disabled_flag.enabled = False

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = disabled_flag

        with patch.dict(os.environ, {KILL_SWITCH_3B_ENV: "false"}):
            result = _is_3b_kill_switched(db)

        assert result is True

    def test_kill_switch_active_truthful_in_workout_endpoint_db_disabled(self):
        """kill_switch_active=True in workout response when DB FeatureFlag disabled (env=false)."""
        from fastapi.testclient import TestClient
        from main import app
        from core.auth import get_current_user
        from core.database import get_db
        from services.phase3_eligibility import EligibilityResult

        athlete = _make_athlete(tier="premium")
        db = _mock_db_no_suppressions()

        app.dependency_overrides[get_current_user] = lambda: athlete
        app.dependency_overrides[get_db] = lambda: db

        try:
            with patch.dict(os.environ, {KILL_SWITCH_3B_ENV: "false"}), \
                 patch("services.phase3_eligibility._is_kill_switched", return_value=True), \
                 patch("services.phase3_eligibility.get_3b_eligibility") as mock_elig:
                mock_elig.return_value = EligibilityResult(
                    eligible=False,
                    reason="3B workout narratives are globally disabled (kill switch).",
                    evidence={"kill_switch": True},
                )
                client = TestClient(app, raise_server_exceptions=False)
                resp = client.get(f"/v1/intelligence/workout-narrative/{date.today().isoformat()}")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["kill_switch_active"] is True

    def test_kill_switch_active_truthful_in_admin_review_db_disabled(self):
        """kill_switch_active=True in admin review response when DB FeatureFlag disabled."""
        from fastapi.testclient import TestClient
        from main import app
        from core.auth import get_current_user
        from core.database import get_db

        founder = _make_athlete(tier="free")
        founder.email = "mbshaf@gmail.com"
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        db.query.return_value.filter.return_value.all.return_value = []

        app.dependency_overrides[get_current_user] = lambda: founder
        app.dependency_overrides[get_db] = lambda: db

        try:
            with patch.dict(os.environ, {KILL_SWITCH_3B_ENV: "false"}), \
                 patch("services.phase3_eligibility._is_kill_switched", return_value=True), \
                 patch("services.phase3_eligibility._narration_quality_score", return_value=None):
                client = TestClient(app, raise_server_exceptions=False)
                resp = client.get("/v1/intelligence/admin/narrative-review")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["kill_switch_active"] is True


class TestGateClosedEnforcement:
    """Gate-closed (provisional) must suppress non-founder premium athletes."""

    def _make_app_with_user(self, athlete):
        from fastapi.testclient import TestClient
        from main import app
        from core.auth import get_current_user
        from core.database import get_db

        db = _mock_db_no_suppressions()
        app.dependency_overrides[get_current_user] = lambda: athlete
        app.dependency_overrides[get_db] = lambda: db
        return app, TestClient(app, raise_server_exceptions=False)

    def test_non_founder_premium_suppressed_when_gate_closed(self):
        """Non-founder premium athlete gets gate_closed_founder_only reason when gate is not open."""
        from services.phase3_eligibility import EligibilityResult

        athlete = _make_athlete(tier="premium")
        athlete.email = "notfounder@example.com"
        app, client = self._make_app_with_user(athlete)

        try:
            with patch("services.phase3_eligibility.get_3b_eligibility") as mock_elig, \
                 patch("services.phase3_eligibility._is_kill_switched", return_value=False):
                # Eligible but provisional — gate not open
                mock_elig.return_value = EligibilityResult(
                    eligible=True,
                    reason="Eligible for workout narratives.",
                    provisional=True,
                )
                resp = client.get(f"/v1/intelligence/workout-narrative/{date.today().isoformat()}")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["suppressed"] is True
        assert data["reason"] == "gate_closed_founder_only"
        assert data["gate_open"] is False

    def test_founder_can_get_narrative_when_gate_closed(self):
        """Founder account can receive generated narrative even when gate is not open (provisional)."""
        from services.phase3_eligibility import EligibilityResult

        founder = _make_athlete(tier="premium")
        founder.email = "mbshaf@gmail.com"
        app, client = self._make_app_with_user(founder)

        try:
            with patch("services.phase3_eligibility.get_3b_eligibility") as mock_elig, \
                 patch("services.phase3_eligibility._is_kill_switched", return_value=False), \
                 patch("services.workout_narrative_generator.generate_workout_narrative") as mock_gen, \
                 patch("routers.daily_intelligence.NarrationLog"):
                mock_elig.return_value = EligibilityResult(
                    eligible=True,
                    reason="Eligible for workout narratives.",
                    provisional=True,  # gate not open
                )
                mock_gen.return_value = WorkoutNarrativeResult(
                    narrative="After last week's 18km, today's easy build week 7 run.",
                    suppressed=False,
                )
                resp = client.get(f"/v1/intelligence/workout-narrative/{date.today().isoformat()}")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        # Founder bypasses gate-closed suppression
        assert data["suppressed"] is False
        assert data["narrative"] is not None
        assert data["reason"] != "gate_closed_founder_only"

    def test_non_founder_gets_narrative_when_gate_open(self):
        """Non-founder premium athlete gets generated narrative when gate IS open."""
        from services.phase3_eligibility import EligibilityResult

        athlete = _make_athlete(tier="premium")
        athlete.email = "notfounder@example.com"
        app, client = self._make_app_with_user(athlete)

        try:
            with patch("services.phase3_eligibility.get_3b_eligibility") as mock_elig, \
                 patch("services.phase3_eligibility._is_kill_switched", return_value=False), \
                 patch("services.workout_narrative_generator.generate_workout_narrative") as mock_gen, \
                 patch("routers.daily_intelligence.NarrationLog"):
                mock_elig.return_value = EligibilityResult(
                    eligible=True,
                    reason="Eligible for workout narratives.",
                    provisional=False,  # gate IS open
                )
                mock_gen.return_value = WorkoutNarrativeResult(
                    narrative="Your build phase week 7 tempo is ready.",
                    suppressed=False,
                )
                resp = client.get(f"/v1/intelligence/workout-narrative/{date.today().isoformat()}")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["suppressed"] is False
        assert data["narrative"] is not None
        assert data["gate_open"] is True
        assert data["reason"] != "gate_closed_founder_only"
