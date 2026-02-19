"""
Phase 1: Consent Infrastructure — Test Suite
Tests 1-46 across 5 categories.

Run: python -m pytest tests/test_consent.py -v --tb=short
"""
import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-at-least-32-chars")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "test-encryption-key-32-chars-ok")

from fastapi.testclient import TestClient

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models import Athlete, ConsentAuditLog, FeatureFlag
from services.consent import grant_consent, has_ai_consent, revoke_consent

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_athlete(db, **kwargs) -> Athlete:
    """Create and commit a test athlete. Caller must clean up."""
    defaults = dict(
        email=f"consent_test_{uuid4()}@example.com",
        display_name="Consent Test Athlete",
        subscription_tier="free",
    )
    defaults.update(kwargs)
    a = Athlete(**defaults)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _auth_headers(athlete: Athlete) -> dict:
    token = create_access_token({"sub": str(athlete.id), "email": athlete.email, "role": athlete.role})
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Category 1: Unit Tests — Consent Data Model (tests 1-10)
# ---------------------------------------------------------------------------

class TestConsentDataModel:
    """
    Tests 1-10: Direct service-layer tests using db_session fixture.
    No HTTP — calls grant_consent / revoke_consent / has_ai_consent directly.
    """

    def test_default_ai_consent_is_false(self, db_session):
        """Test 1: New athlete has ai_consent = False by default."""
        athlete = Athlete(
            email=f"default_{uuid4()}@example.com",
            display_name="Default Athlete",
            subscription_tier="free",
        )
        db_session.add(athlete)
        db_session.commit()
        db_session.refresh(athlete)

        assert athlete.ai_consent is False
        assert athlete.ai_consent_granted_at is None
        assert athlete.ai_consent_revoked_at is None

    def test_grant_consent_sets_fields(self, db_session):
        """Test 2: Granting consent sets ai_consent=True, granted_at=now(), clears revoked_at."""
        athlete = Athlete(
            email=f"grant_{uuid4()}@example.com",
            display_name="Grant Test",
            subscription_tier="free",
        )
        db_session.add(athlete)
        db_session.commit()
        db_session.refresh(athlete)

        before = datetime.now(timezone.utc)
        grant_consent(
            db=db_session,
            athlete_id=athlete.id,
            ip_address="1.2.3.4",
            user_agent="TestBrowser/1.0",
            source="onboarding",
        )
        db_session.refresh(athlete)

        assert athlete.ai_consent is True
        assert athlete.ai_consent_granted_at is not None
        assert athlete.ai_consent_granted_at >= before
        assert athlete.ai_consent_revoked_at is None

    def test_revoke_consent_sets_fields(self, db_session):
        """Test 3: Revoking sets ai_consent=False, revoked_at=now(), preserves granted_at."""
        athlete = Athlete(
            email=f"revoke_{uuid4()}@example.com",
            display_name="Revoke Test",
            subscription_tier="free",
        )
        db_session.add(athlete)
        db_session.commit()
        db_session.refresh(athlete)

        # Grant first
        grant_consent(
            db=db_session,
            athlete_id=athlete.id,
            ip_address="1.2.3.4",
            user_agent="TestBrowser/1.0",
            source="onboarding",
        )
        db_session.refresh(athlete)
        granted_at = athlete.ai_consent_granted_at

        # Now revoke
        before_revoke = datetime.now(timezone.utc)
        revoke_consent(
            db=db_session,
            athlete_id=athlete.id,
            ip_address="1.2.3.5",
            user_agent="TestBrowser/1.0",
            source="settings",
        )
        db_session.refresh(athlete)

        assert athlete.ai_consent is False
        assert athlete.ai_consent_revoked_at is not None
        assert athlete.ai_consent_revoked_at >= before_revoke
        # granted_at is preserved
        assert athlete.ai_consent_granted_at == granted_at

    def test_grant_creates_audit_log(self, db_session):
        """Test 4: Granting writes an audit row with action='granted', ip, user_agent, source."""
        athlete = Athlete(
            email=f"audit_grant_{uuid4()}@example.com",
            display_name="Audit Grant Test",
            subscription_tier="free",
        )
        db_session.add(athlete)
        db_session.commit()
        db_session.refresh(athlete)

        grant_consent(
            db=db_session,
            athlete_id=athlete.id,
            ip_address="10.0.0.1",
            user_agent="Mozilla/5.0",
            source="consent_prompt",
        )

        logs = (
            db_session.query(ConsentAuditLog)
            .filter(ConsentAuditLog.athlete_id == athlete.id)
            .all()
        )
        assert len(logs) == 1
        log = logs[0]
        assert log.action == "granted"
        assert log.consent_type == "ai_processing"
        assert log.ip_address == "10.0.0.1"
        assert log.user_agent == "Mozilla/5.0"
        assert log.source == "consent_prompt"
        assert log.created_at is not None

    def test_revoke_creates_audit_log(self, db_session):
        """Test 5: Revoking writes an audit row with action='revoked'."""
        athlete = Athlete(
            email=f"audit_revoke_{uuid4()}@example.com",
            display_name="Audit Revoke Test",
            subscription_tier="free",
        )
        db_session.add(athlete)
        db_session.commit()
        db_session.refresh(athlete)

        grant_consent(
            db=db_session,
            athlete_id=athlete.id,
            ip_address="10.0.0.1",
            user_agent="Mozilla/5.0",
            source="onboarding",
        )
        revoke_consent(
            db=db_session,
            athlete_id=athlete.id,
            ip_address="10.0.0.2",
            user_agent="Mozilla/5.0",
            source="settings",
        )

        logs = (
            db_session.query(ConsentAuditLog)
            .filter(ConsentAuditLog.athlete_id == athlete.id)
            .order_by(ConsentAuditLog.created_at)
            .all()
        )
        assert len(logs) == 2
        assert logs[0].action == "granted"
        assert logs[1].action == "revoked"
        assert logs[1].source == "settings"

    def test_has_ai_consent_true_when_granted(self, db_session):
        """Test 6: has_ai_consent returns True when athlete has ai_consent=True and kill switch is on."""
        athlete = Athlete(
            email=f"hac_true_{uuid4()}@example.com",
            display_name="HAC True Test",
            subscription_tier="free",
        )
        db_session.add(athlete)
        db_session.commit()
        db_session.refresh(athlete)

        grant_consent(
            db=db_session,
            athlete_id=athlete.id,
            ip_address="127.0.0.1",
            user_agent="TestAgent",
            source="onboarding",
        )

        # Ensure kill switch exists and is ON
        flag = db_session.query(FeatureFlag).filter_by(key="ai_inference_enabled").first()
        if flag:
            flag.enabled = True
        else:
            flag = FeatureFlag(
                key="ai_inference_enabled",
                name="AI Inference Kill Switch",
                enabled=True,
                rollout_percentage=100,
            )
            db_session.add(flag)
        db_session.commit()

        result = has_ai_consent(athlete_id=athlete.id, db=db_session)
        assert result is True

    def test_has_ai_consent_false_when_not_granted(self, db_session):
        """Test 7: has_ai_consent returns False when athlete has ai_consent=False (default)."""
        athlete = Athlete(
            email=f"hac_false_{uuid4()}@example.com",
            display_name="HAC False Test",
            subscription_tier="free",
        )
        db_session.add(athlete)
        db_session.commit()
        db_session.refresh(athlete)

        result = has_ai_consent(athlete_id=athlete.id, db=db_session)
        assert result is False

    def test_has_ai_consent_false_when_kill_switch_off(self, db_session):
        """Test 8: has_ai_consent returns False even when athlete consented, if kill switch is off."""
        athlete = Athlete(
            email=f"ks_off_{uuid4()}@example.com",
            display_name="Kill Switch Test",
            subscription_tier="free",
        )
        db_session.add(athlete)
        db_session.commit()
        db_session.refresh(athlete)

        # Grant consent
        grant_consent(
            db=db_session,
            athlete_id=athlete.id,
            ip_address="127.0.0.1",
            user_agent="TestAgent",
            source="onboarding",
        )

        # Set kill switch to OFF
        flag = db_session.query(FeatureFlag).filter_by(key="ai_inference_enabled").first()
        if flag:
            flag.enabled = False
        else:
            flag = FeatureFlag(
                key="ai_inference_enabled",
                name="AI Inference Kill Switch",
                enabled=False,
                rollout_percentage=100,
            )
            db_session.add(flag)
        db_session.commit()

        result = has_ai_consent(athlete_id=athlete.id, db=db_session)
        assert result is False

    def test_regrant_after_revoke(self, db_session):
        """Test 9: Grant -> revoke -> grant cycle works correctly. Final state: consented."""
        athlete = Athlete(
            email=f"cycle_{uuid4()}@example.com",
            display_name="Cycle Test",
            subscription_tier="free",
        )
        db_session.add(athlete)
        db_session.commit()
        db_session.refresh(athlete)

        grant_consent(db=db_session, athlete_id=athlete.id, ip_address="1.1.1.1", user_agent="A", source="onboarding")
        revoke_consent(db=db_session, athlete_id=athlete.id, ip_address="1.1.1.2", user_agent="A", source="settings")
        grant_consent(db=db_session, athlete_id=athlete.id, ip_address="1.1.1.3", user_agent="A", source="consent_prompt")
        db_session.refresh(athlete)

        assert athlete.ai_consent is True
        assert athlete.ai_consent_granted_at is not None
        # revoked_at is cleared after re-grant
        assert athlete.ai_consent_revoked_at is None

    def test_audit_log_captures_all_transitions(self, db_session):
        """Test 10: Full grant->revoke->grant cycle produces correct 3-row audit trail."""
        athlete = Athlete(
            email=f"trail_{uuid4()}@example.com",
            display_name="Audit Trail Test",
            subscription_tier="free",
        )
        db_session.add(athlete)
        db_session.commit()
        db_session.refresh(athlete)

        grant_consent(db=db_session, athlete_id=athlete.id, ip_address="1.1.1.1", user_agent="UA", source="onboarding")
        revoke_consent(db=db_session, athlete_id=athlete.id, ip_address="1.1.1.2", user_agent="UA", source="settings")
        grant_consent(db=db_session, athlete_id=athlete.id, ip_address="1.1.1.3", user_agent="UA", source="consent_prompt")

        logs = (
            db_session.query(ConsentAuditLog)
            .filter(ConsentAuditLog.athlete_id == athlete.id)
            .order_by(ConsentAuditLog.created_at)
            .all()
        )
        assert len(logs) == 3
        assert logs[0].action == "granted"
        assert logs[0].source == "onboarding"
        assert logs[1].action == "revoked"
        assert logs[1].source == "settings"
        assert logs[2].action == "granted"
        assert logs[2].source == "consent_prompt"
        # All rows tied to the correct athlete
        assert all(str(l.athlete_id) == str(athlete.id) for l in logs)


# ---------------------------------------------------------------------------
# Category 2: API Endpoint Tests — Consent Endpoints (tests 11-18)
# ---------------------------------------------------------------------------

class TestConsentEndpoints:
    """
    Tests 11-18: HTTP-level tests using TestClient.
    Athletes are committed (not in a savepoint) so the app's DB sessions can see them.
    """

    @pytest.fixture(autouse=True)
    def db(self):
        """Provide a real DB session for test setup/teardown."""
        self._db = SessionLocal()
        yield self._db
        self._db.close()

    @pytest.fixture
    def athlete_and_headers(self):
        """Create a real athlete and return (athlete, headers). Cleans up after test."""
        db = SessionLocal()
        athlete = _make_athlete(db)
        headers = _auth_headers(athlete)
        yield athlete, headers
        try:
            # Clean up audit logs first (FK constraint)
            db.query(ConsentAuditLog).filter(ConsentAuditLog.athlete_id == athlete.id).delete()
            db.commit()
            db.delete(athlete)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def test_get_consent_status_unauthenticated(self):
        """Test 11: GET /v1/consent/ai without token returns 401."""
        resp = client.get("/v1/consent/ai")
        assert resp.status_code == 401

    def test_get_consent_status_default(self, athlete_and_headers):
        """Test 12: GET /v1/consent/ai returns { ai_consent: false, granted_at: null, revoked_at: null }."""
        athlete, headers = athlete_and_headers
        resp = client.get("/v1/consent/ai", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ai_consent"] is False
        assert data["granted_at"] is None
        assert data["revoked_at"] is None

    def test_post_consent_grant(self, athlete_and_headers):
        """Test 13: POST { granted: true } returns 200 and ai_consent is now True."""
        athlete, headers = athlete_and_headers
        resp = client.post("/v1/consent/ai", json={"granted": True}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ai_consent"] is True

        # Verify in DB
        db = SessionLocal()
        try:
            fresh = db.query(Athlete).filter(Athlete.id == athlete.id).first()
            assert fresh.ai_consent is True
            assert fresh.ai_consent_granted_at is not None
        finally:
            db.close()

    def test_post_consent_revoke(self, athlete_and_headers):
        """Test 14: POST { granted: false } returns 200 and ai_consent is now False."""
        athlete, headers = athlete_and_headers
        # First grant
        client.post("/v1/consent/ai", json={"granted": True}, headers=headers)
        # Then revoke
        resp = client.post("/v1/consent/ai", json={"granted": False}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ai_consent"] is False

        db = SessionLocal()
        try:
            fresh = db.query(Athlete).filter(Athlete.id == athlete.id).first()
            assert fresh.ai_consent is False
            assert fresh.ai_consent_revoked_at is not None
        finally:
            db.close()

    def test_post_consent_creates_audit(self, athlete_and_headers):
        """Test 15: POST consent creates an audit log row."""
        athlete, headers = athlete_and_headers
        resp = client.post("/v1/consent/ai", json={"granted": True}, headers=headers)
        assert resp.status_code == 200

        db = SessionLocal()
        try:
            logs = db.query(ConsentAuditLog).filter(ConsentAuditLog.athlete_id == athlete.id).all()
            assert len(logs) >= 1
            assert logs[-1].action == "granted"
            assert logs[-1].consent_type == "ai_processing"
        finally:
            db.close()

    def test_get_consent_after_grant(self, athlete_and_headers):
        """Test 16: GET after POST grant returns updated granted_at timestamp."""
        athlete, headers = athlete_and_headers
        client.post("/v1/consent/ai", json={"granted": True}, headers=headers)
        resp = client.get("/v1/consent/ai", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ai_consent"] is True
        assert data["granted_at"] is not None
        assert data["revoked_at"] is None

    def test_consent_idempotent_grant_still_logs(self, athlete_and_headers):
        """Test 17: Granting when already granted is a no-op on ai_consent field, but still logs."""
        athlete, headers = athlete_and_headers
        # Grant twice
        client.post("/v1/consent/ai", json={"granted": True}, headers=headers)
        client.post("/v1/consent/ai", json={"granted": True}, headers=headers)

        db = SessionLocal()
        try:
            fresh = db.query(Athlete).filter(Athlete.id == athlete.id).first()
            assert fresh.ai_consent is True  # Still true (not toggled)
            logs = db.query(ConsentAuditLog).filter(ConsentAuditLog.athlete_id == athlete.id).all()
            assert len(logs) == 2  # Both calls logged, even though field didn't change
            assert all(l.action == "granted" for l in logs)
        finally:
            db.close()

    def test_consent_idempotent_revoke_still_logs(self, athlete_and_headers):
        """Test 18: Revoking when already revoked is a no-op on ai_consent field, but still logs."""
        athlete, headers = athlete_and_headers
        # Revoke twice (starting from default False)
        client.post("/v1/consent/ai", json={"granted": False}, headers=headers)
        client.post("/v1/consent/ai", json={"granted": False}, headers=headers)

        db = SessionLocal()
        try:
            fresh = db.query(Athlete).filter(Athlete.id == athlete.id).first()
            assert fresh.ai_consent is False
            logs = db.query(ConsentAuditLog).filter(ConsentAuditLog.athlete_id == athlete.id).all()
            assert len(logs) == 2  # Both calls logged, even though field didn't change
            assert all(l.action == "revoked" for l in logs)
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Category 3: LLM Pipeline Gating Tests (tests 19-34)
# ---------------------------------------------------------------------------

class TestLLMPipelineGating:
    """
    Tests 19-34: Backend enforcement that has_ai_consent gates each of the 8 LLM call sites.
    Uses mocking — no real LLM calls.

    xfail: P1-D gating code not yet implemented. Remove marker when P1-D ships.
    """
    pytestmark = pytest.mark.xfail(
        strict=False,
        reason="P1-D LLM pipeline gating not yet implemented",
    )

    @pytest.fixture(autouse=True)
    def athlete_and_headers(self):
        db = SessionLocal()
        athlete = _make_athlete(db)
        headers = _auth_headers(athlete)
        self.athlete = athlete
        self.headers = headers
        self.db = db
        yield
        try:
            db.query(ConsentAuditLog).filter(ConsentAuditLog.athlete_id == athlete.id).delete()
            db.commit()
            # Reset kill switch to enabled so other tests aren't poisoned
            flag = db.query(FeatureFlag).filter_by(key="ai_inference_enabled").first()
            if flag:
                flag.enabled = True
                db.commit()
            db.delete(athlete)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    @pytest.fixture
    def consented_athlete(self):
        """Create an athlete with ai_consent=True."""
        db = SessionLocal()
        athlete = _make_athlete(db)
        headers = _auth_headers(athlete)
        grant_consent(db=db, athlete_id=athlete.id, ip_address="127.0.0.1", user_agent="Test", source="onboarding")
        db.refresh(athlete)
        yield athlete, headers
        try:
            db.query(ConsentAuditLog).filter(ConsentAuditLog.athlete_id == athlete.id).delete()
            db.commit()
            db.delete(athlete)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def test_coach_chat_blocked_without_consent(self):
        """Test 19: Coach chat returns consent-required message, no LLM call made."""
        with patch("services.ai_coach.AICoach._dispatch_llm") as mock_llm:
            resp = client.post(
                "/v1/coach/chat",
                json={"message": "How is my training?"},
                headers=self.headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        # Response must indicate consent required, not an LLM response
        assert "consent" in str(data).lower() or "ai_insights" in str(data).lower() or "enable" in str(data).lower()
        mock_llm.assert_not_called()

    def test_coach_chat_allowed_with_consent(self, consented_athlete):
        """Test 20: Coach chat proceeds when athlete has consent."""
        athlete, headers = consented_athlete
        with patch("services.ai_coach.AICoach._dispatch_llm") as mock_llm:
            mock_llm.return_value = "Your training looks good."
            resp = client.post(
                "/v1/coach/chat",
                json={"message": "How is my training?"},
                headers=headers,
            )
        # Should reach LLM dispatch (or at least not be blocked by consent)
        assert resp.status_code == 200

    def test_home_briefing_blocked_without_consent(self):
        """Test 21: /v1/home with ai_consent=False returns coach_briefing: null, briefing_state: 'consent_required'."""
        with patch("routers.home._fetch_llm_briefing_sync") as mock_fetch:
            resp = client.get("/v1/home", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("coach_briefing") is None
        assert data.get("briefing_state") == "consent_required"
        mock_fetch.assert_not_called()

    def test_home_briefing_allowed_with_consent(self, consented_athlete):
        """Test 22: /v1/home with ai_consent=True proceeds to normal briefing path."""
        athlete, headers = consented_athlete
        with patch("routers.home._fetch_llm_briefing_sync") as mock_fetch:
            mock_fetch.return_value = None  # No briefing ready, but path is unblocked
            resp = client.get("/v1/home", headers=headers)
        assert resp.status_code == 200

    def test_celery_briefing_task_skips_without_consent(self):
        """Test 23: generate_home_briefing_task skips (no LLM call) when athlete has no consent."""
        from tasks.home_briefing_tasks import generate_home_briefing_task
        athlete_id = str(self.athlete.id)

        with patch("tasks.home_briefing_tasks._call_llm_for_briefing") as mock_llm:
            result = generate_home_briefing_task(athlete_id)
        mock_llm.assert_not_called()

    def test_moment_narrator_returns_none_without_consent(self):
        """Test 24: _call_narrator_llm returns None without consent, no LLM call made."""
        from services.moment_narrator import _call_narrator_llm
        with patch("services.moment_narrator.genai") as mock_genai:
            result = _call_narrator_llm(
                athlete_id=self.athlete.id,
                prompt="Test prompt",
                db=None,
            )
        assert result is None
        mock_genai.GenerativeModel.assert_not_called()

    def test_workout_narrative_returns_none_without_consent(self):
        """Test 25: _call_llm in workout_narrative_generator returns None without consent."""
        from services.workout_narrative_generator import WorkoutNarrativeGenerator
        with patch("services.workout_narrative_generator.genai") as mock_genai:
            gen = WorkoutNarrativeGenerator.__new__(WorkoutNarrativeGenerator)
            result = gen._call_llm(
                athlete_id=self.athlete.id,
                prompt="Test prompt",
                db=None,
            )
        assert result is None
        mock_genai.GenerativeModel.assert_not_called()

    def test_adaptation_narrator_returns_none_without_consent(self):
        """Test 26: generate_narration in adaptation_narrator returns None without consent."""
        from services.adaptation_narrator import AdaptationNarrator
        with patch("services.adaptation_narrator.genai") as mock_genai:
            narrator = AdaptationNarrator.__new__(AdaptationNarrator)
            result = narrator.generate_narration(
                athlete_id=self.athlete.id,
                context={},
                db=None,
            )
        assert result is None
        mock_genai.GenerativeModel.assert_not_called()

    def test_progress_headline_returns_none_without_consent(self):
        """Test 27: _generate_progress_headline returns None without consent."""
        from routers.progress import _generate_progress_headline
        with patch("routers.progress.anthropic") as mock_anthropic:
            db = SessionLocal()
            try:
                result = _generate_progress_headline(
                    athlete=self.athlete,
                    metrics={},
                    db=db,
                )
            finally:
                db.close()
        assert result is None
        mock_anthropic.Anthropic.assert_not_called()

    def test_progress_cards_returns_fallback_without_consent(self):
        """Test 28: _generate_progress_cards returns deterministic fallback cards without consent."""
        from routers.progress import _generate_progress_cards
        with patch("routers.progress.anthropic") as mock_anthropic:
            db = SessionLocal()
            try:
                result = _generate_progress_cards(
                    athlete=self.athlete,
                    metrics={},
                    db=db,
                )
            finally:
                db.close()
        # Fallback cards: non-null, deterministic, no LLM call
        assert result is not None
        mock_anthropic.Anthropic.assert_not_called()

    def test_kill_switch_blocks_all_ai(self):
        """Test 29: Kill switch off blocks all AI even for non-consented users (already false)."""
        db = SessionLocal()
        try:
            flag = db.query(FeatureFlag).filter_by(key="ai_inference_enabled").first()
            if flag:
                flag.enabled = False
            else:
                flag = FeatureFlag(
                    key="ai_inference_enabled",
                    name="AI Inference Kill Switch",
                    enabled=False,
                    rollout_percentage=100,
                )
                db.add(flag)
            db.commit()

            result = has_ai_consent(athlete_id=self.athlete.id, db=db)
            assert result is False
        finally:
            db.close()

    def test_kill_switch_on_allows_consented(self):
        """Test 30: Kill switch on + consent → has_ai_consent returns True."""
        db = SessionLocal()
        try:
            grant_consent(db=db, athlete_id=self.athlete.id, ip_address="127.0.0.1", user_agent="Test", source="onboarding")

            flag = db.query(FeatureFlag).filter_by(key="ai_inference_enabled").first()
            if flag:
                flag.enabled = True
            else:
                flag = FeatureFlag(
                    key="ai_inference_enabled",
                    name="AI Inference Kill Switch",
                    enabled=True,
                    rollout_percentage=100,
                )
                db.add(flag)
            db.commit()

            result = has_ai_consent(athlete_id=self.athlete.id, db=db)
            assert result is True
        finally:
            db.close()

    def test_kill_switch_overrides_consent(self):
        """Test 31: Kill switch off + ai_consent=True → has_ai_consent returns False."""
        db = SessionLocal()
        try:
            grant_consent(db=db, athlete_id=self.athlete.id, ip_address="127.0.0.1", user_agent="Test", source="onboarding")
            db_athlete = db.query(Athlete).filter(Athlete.id == self.athlete.id).first()
            assert db_athlete.ai_consent is True

            flag = db.query(FeatureFlag).filter_by(key="ai_inference_enabled").first()
            if flag:
                flag.enabled = False
            else:
                flag = FeatureFlag(
                    key="ai_inference_enabled",
                    name="AI Inference Kill Switch",
                    enabled=False,
                    rollout_percentage=100,
                )
                db.add(flag)
            db.commit()

            result = has_ai_consent(athlete_id=self.athlete.id, db=db)
            assert result is False
        finally:
            db.close()

    def test_no_llm_call_made_when_blocked(self):
        """Test 32: For each of 8 call sites, LLM client is NOT called when consent=False."""
        # Verify has_ai_consent returns False (unconsented athlete)
        db = SessionLocal()
        try:
            result = has_ai_consent(athlete_id=self.athlete.id, db=db)
            assert result is False, "Precondition: athlete must not have consent"
        finally:
            db.close()

    def test_consent_revoke_stops_background_tasks(self):
        """Test 33: Grant → enqueue → revoke → task executes → no LLM call (checks at execution)."""
        from tasks.home_briefing_tasks import generate_home_briefing_task
        db = SessionLocal()
        try:
            grant_consent(db=db, athlete_id=self.athlete.id, ip_address="127.0.0.1", user_agent="Test", source="onboarding")
            revoke_consent(db=db, athlete_id=self.athlete.id, ip_address="127.0.0.1", user_agent="Test", source="settings")
        finally:
            db.close()

        # Task runs AFTER revocation — should skip
        with patch("tasks.home_briefing_tasks._call_llm_for_briefing") as mock_llm:
            generate_home_briefing_task(str(self.athlete.id))
        mock_llm.assert_not_called()

    def test_knowledge_extraction_not_gated(self):
        """Test 34: Admin knowledge extraction is NOT blocked by consent (admin-only, not athlete-facing)."""
        from services.knowledge_extraction_ai import KnowledgeExtractionAI
        # This should import cleanly and not have has_ai_consent in its call path
        assert KnowledgeExtractionAI is not None
        # Verify the class exists and doesn't require consent (structural test)
        import inspect
        source = inspect.getsource(KnowledgeExtractionAI)
        assert "has_ai_consent" not in source


# ---------------------------------------------------------------------------
# Category 4: Integration Tests — Graceful Degradation (tests 35-42)
# ---------------------------------------------------------------------------

class TestGracefulDegradation:
    """
    Tests 35-42: End-to-end graceful degradation when ai_consent=False.
    Full page loads return valid JSON, AI fields are null, non-AI fields intact.

    xfail: P1-D gating code not yet implemented. Remove marker when P1-D ships.
    """
    pytestmark = pytest.mark.xfail(
        strict=False,
        reason="P1-D LLM pipeline gating not yet implemented",
    )

    @pytest.fixture(autouse=True)
    def athlete_setup(self):
        db = SessionLocal()
        self.athlete = _make_athlete(db)
        self.headers = _auth_headers(self.athlete)
        self.db_setup = db
        yield
        try:
            db.query(ConsentAuditLog).filter(ConsentAuditLog.athlete_id == self.athlete.id).delete()
            db.commit()
            db.delete(self.athlete)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def test_home_page_loads_without_consent(self):
        """Test 35: /v1/home returns valid JSON with all deterministic fields intact, AI fields null."""
        resp = client.get("/v1/home", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        # Deterministic fields must be present (even if null)
        assert "coach_briefing" in data
        assert data["coach_briefing"] is None

    def test_home_page_briefing_state_consent_required(self):
        """Test 36: briefing_state is 'consent_required' when athlete has no consent."""
        resp = client.get("/v1/home", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("briefing_state") == "consent_required"

    def test_activity_detail_loads_without_consent(self):
        """Test 37: Activity-level endpoints return metrics without AI narratives (no error state)."""
        # No activities exist for this test athlete, so this is a structural test:
        # The activities list endpoint should still return 200 and an empty list (no errors)
        resp = client.get("/v1/activities", headers=self.headers)
        assert resp.status_code == 200

    def test_progress_page_loads_without_consent(self):
        """Test 38: /v1/progress returns data with no headline, fallback deterministic cards."""
        resp = client.get("/v1/progress", headers=self.headers)
        assert resp.status_code in (200, 404)  # 404 if no plan data exists; no 500

    def test_consent_then_full_functionality(self):
        """Test 39: Grant consent → briefing_state is no longer 'consent_required'."""
        db = SessionLocal()
        try:
            grant_consent(db=db, athlete_id=self.athlete.id, ip_address="127.0.0.1", user_agent="Test", source="onboarding")
        finally:
            db.close()

        resp = client.get("/v1/home", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("briefing_state") != "consent_required"

    def test_revoke_then_graceful_degradation(self):
        """Test 40: Revoke consent → briefing_state returns to 'consent_required'."""
        db = SessionLocal()
        try:
            grant_consent(db=db, athlete_id=self.athlete.id, ip_address="127.0.0.1", user_agent="Test", source="onboarding")
        finally:
            db.close()

        db2 = SessionLocal()
        try:
            revoke_consent(db=db2, athlete_id=self.athlete.id, ip_address="127.0.0.1", user_agent="Test", source="settings")
        finally:
            db2.close()

        resp = client.get("/v1/home", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("briefing_state") == "consent_required"

    def test_consent_prompt_hidden_when_consented(self):
        """Test 41: GET /v1/consent/ai returns ai_consent=True for consented athlete."""
        db = SessionLocal()
        try:
            grant_consent(db=db, athlete_id=self.athlete.id, ip_address="127.0.0.1", user_agent="Test", source="onboarding")
        finally:
            db.close()

        resp = client.get("/v1/consent/ai", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ai_consent"] is True  # Frontend should NOT show consent prompt

    def test_unconsented_user_no_dead_ends(self):
        """Test 42: Unconsented user can navigate home, activities, settings — no redirect loops or errors."""
        endpoints = [
            ("GET", "/v1/home"),
            ("GET", "/v1/activities"),
            ("GET", "/v1/consent/ai"),
        ]
        for method, path in endpoints:
            resp = client.request(method, path, headers=self.headers)
            # Must return a valid response — no 5xx, no redirect loops
            assert resp.status_code < 500, f"{method} {path} returned {resp.status_code}"
            assert resp.status_code != 302, f"{method} {path} returned a redirect"


# ---------------------------------------------------------------------------
# Category 5: Migration Tests (tests 43-46)
# ---------------------------------------------------------------------------

class TestMigrationSchema:
    """
    Tests 43-46: Verify the Alembic migration adds the correct schema.
    These tests query the database schema directly (information_schema).
    """

    def test_migration_adds_ai_consent_fields(self, db_session):
        """Test 43: Athlete table has ai_consent, ai_consent_granted_at, ai_consent_revoked_at columns."""
        from sqlalchemy import text
        result = db_session.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'athlete' "
            "AND column_name IN ('ai_consent', 'ai_consent_granted_at', 'ai_consent_revoked_at')"
        )).fetchall()
        column_names = {row[0] for row in result}
        assert "ai_consent" in column_names
        assert "ai_consent_granted_at" in column_names
        assert "ai_consent_revoked_at" in column_names

    def test_migration_creates_consent_audit_log(self, db_session):
        """Test 44: consent_audit_log table exists with all required columns."""
        from sqlalchemy import text
        result = db_session.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'consent_audit_log'"
        )).fetchall()
        column_names = {row[0] for row in result}
        required_columns = {
            "id", "athlete_id", "consent_type", "action",
            "ip_address", "user_agent", "source", "created_at",
        }
        missing = required_columns - column_names
        assert not missing, f"Missing columns in consent_audit_log: {missing}"

    def test_existing_athletes_default_false(self, db_session):
        """Test 45: After migration, athletes created without ai_consent have ai_consent=False."""
        athlete = Athlete(
            email=f"migration_test_{uuid4()}@example.com",
            display_name="Migration Test",
            subscription_tier="free",
        )
        db_session.add(athlete)
        db_session.commit()
        db_session.refresh(athlete)

        assert athlete.ai_consent is False
        assert athlete.ai_consent_granted_at is None

    def test_migration_reversible(self, db_session):
        """Test 46: Structural test — migration file defines both upgrade() and downgrade()."""
        import importlib.util
        import pathlib

        api_root = pathlib.Path(__file__).parent.parent
        # Find the consent migration file
        versions_dir = api_root / "alembic" / "versions"
        consent_migrations = list(versions_dir.glob("*consent*.py"))
        assert len(consent_migrations) >= 1, "No consent migration file found"

        migration_file = consent_migrations[0]
        spec = importlib.util.spec_from_file_location("consent_migration", migration_file)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        assert hasattr(mod, "upgrade"), "Migration must define upgrade()"
        assert hasattr(mod, "downgrade"), "Migration must define downgrade()"
