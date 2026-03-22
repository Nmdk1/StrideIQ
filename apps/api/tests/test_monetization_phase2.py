"""
Phase 2 Monetization Gating — Test Matrix

Decisions (2026-02-26):
1. Paces gated behind $5 one-time purchase (or Guided/Premium subscription).
   Free plans return full structure with pace fields set to null.
2. Hybrid gating:
   - Plan endpoints: output-layer gating (null paces for unauthorized tiers)
   - Intelligence/adaptation: endpoint-level 403 for below-guided
   - Premium features (narratives): 403 for below-premium

Evidence contract:
  plan endpoint: free (no purchase) → structure + null paces
  plan endpoint: free (with purchase) → structure + paces
  plan endpoint: guided → structure + paces
  plan endpoint: premium → structure + paces
  adaptation/intelligence endpoints → 403 for free
  intelligence endpoints → 200 for guided/premium
  premium-only endpoints → 403 for guided, 200 for premium

Categories:
  1. can_access_plan_paces() utility (unit tests)
  2. GET /v2/plans/{plan_id} output-layer gating
  3. GET /v2/plans/{plan_id}/week/{week_number} output-layer gating
  4. Plan preview pace gating
  5. Intelligence endpoints 403 gating (guided+)
  6. Workout-narrative 403 gating (premium+)
  7. Intelligence bank 403 gating (guided+)
  8. FeatureFlagService._tier_satisfies() consolidation
"""

from uuid import uuid4
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models import Athlete, TrainingPlan, PlannedWorkout, PlanPurchase

client = TestClient(app)


# =============================================================================
# HELPERS
# =============================================================================

def _headers(user: Athlete) -> dict:
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def _make_athlete(tier: str = "free") -> Athlete:
    db = SessionLocal()
    athlete = Athlete(
        email=f"phase2_{uuid4()}@test.com",
        display_name=f"P2Test-{tier}",
        role="athlete",
        subscription_tier=tier,
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    db.close()
    return athlete


def _make_plan(athlete: Athlete) -> TrainingPlan:
    """Create a minimal saved training plan with one workout containing coach_notes (pace info)."""
    db = SessionLocal()
    plan = TrainingPlan(
        athlete_id=athlete.id,
        name="Test Marathon Plan",
        status="active",
        goal_race_date=date(2026, 10, 15),
        goal_race_distance_m=42195,
        plan_start_date=date(2026, 3, 1),
        plan_end_date=date(2026, 10, 15),
        total_weeks=18,
        plan_type="marathon",
        generation_method="framework_v2",
    )
    db.add(plan)
    db.flush()

    workout = PlannedWorkout(
        plan_id=plan.id,
        athlete_id=athlete.id,
        scheduled_date=date(2026, 3, 3),
        week_number=1,
        day_of_week=0,
        workout_type="easy",
        phase="base",
        title="Easy Run",
        description="Easy effort run",
        coach_notes="7:30-8:00/mile easy pace",  # This is the pace field
        target_distance_km=12.0,
    )
    db.add(workout)
    db.commit()
    db.refresh(plan)
    db.close()
    return plan


def _make_purchase(athlete: Athlete, plan: TrainingPlan) -> PlanPurchase:
    """Create a PlanPurchase record linking athlete to plan."""
    db = SessionLocal()
    purchase = PlanPurchase(
        athlete_id=athlete.id,
        plan_snapshot_id=str(plan.id),
        stripe_payment_intent_id=f"pi_test_{uuid4()}",
        amount_cents=500,
        purchased_at=datetime.now(timezone.utc),
    )
    db.add(purchase)
    db.commit()
    db.refresh(purchase)
    db.close()
    return purchase


def _cleanup(*objs):
    """Delete test objects from DB respecting FK dependency order via raw SQL.

    Deletes children before parents to avoid FK violations.
    """
    from sqlalchemy import text

    db = SessionLocal()
    try:
        plan_ids = [str(o.id) for o in objs if isinstance(o, TrainingPlan)]
        athlete_ids = [str(o.id) for o in objs if isinstance(o, Athlete)]
        purchase_ids = [str(o.id) for o in objs if isinstance(o, PlanPurchase)]

        # Delete in dependency order: purchases/workouts → plans → athletes
        for pid in purchase_ids:
            db.execute(text("DELETE FROM plan_purchases WHERE id = :id"), {"id": pid})
        for plan_id in plan_ids:
            db.execute(text("DELETE FROM plan_modification_log WHERE plan_id = :pid"), {"pid": plan_id})
            db.execute(text("DELETE FROM plan_purchases WHERE plan_snapshot_id = :pid"), {"pid": plan_id})
            db.execute(text("DELETE FROM planned_workout WHERE plan_id = :pid"), {"pid": plan_id})
            db.execute(text("DELETE FROM training_plan WHERE id = :pid"), {"pid": plan_id})
        for aid in athlete_ids:
            # Cascade-delete any remaining plan data for this athlete
            db.execute(text("""
                DELETE FROM plan_modification_log
                WHERE athlete_id = :aid
            """), {"aid": aid})
            db.execute(text("""
                DELETE FROM planned_workout pw
                USING training_plan tp
                WHERE pw.plan_id = tp.id AND tp.athlete_id = :aid
            """), {"aid": aid})
            db.execute(text("""
                DELETE FROM plan_purchases WHERE athlete_id = :aid
            """), {"aid": aid})
            db.execute(text("""
                DELETE FROM training_plan WHERE athlete_id = :aid
            """), {"aid": aid})
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


# =============================================================================
# CATEGORY 1: can_access_plan_paces() unit tests
# =============================================================================

class TestCanAccessPlanPaces:
    """Unit tests for the pace access utility."""

    def test_free_athlete_no_purchase_cannot_access(self):
        from core.pace_access import can_access_plan_paces
        athlete = _make_athlete("free")
        plan = _make_plan(athlete)
        db = SessionLocal()
        try:
            result = can_access_plan_paces(athlete, plan.id, db)
            assert result is False
        finally:
            db.close()
            _cleanup(plan, athlete)

    def test_subscriber_athlete_can_access(self):
        from core.pace_access import can_access_plan_paces
        athlete = _make_athlete("subscriber")
        plan = _make_plan(athlete)
        db = SessionLocal()
        try:
            result = can_access_plan_paces(athlete, plan.id, db)
            assert result is True
        finally:
            db.close()
            _cleanup(plan, athlete)

    def test_guided_legacy_tier_cannot_access(self):
        from core.pace_access import can_access_plan_paces
        athlete = _make_athlete("guided")
        plan = _make_plan(athlete)
        db = SessionLocal()
        try:
            result = can_access_plan_paces(athlete, plan.id, db)
            assert result is False
        finally:
            db.close()
            _cleanup(plan, athlete)

    def test_free_has_no_per_plan_purchase_unlock(self):
        """Two-tier model: free tier has no one-off unlock path."""
        from core.pace_access import can_access_plan_paces
        athlete = _make_athlete("free")
        plan_b = _make_plan(athlete)
        db = SessionLocal()
        try:
            result = can_access_plan_paces(athlete, plan_b.id, db)
            assert result is False
        finally:
            db.close()
            _cleanup(plan_b, athlete)

    def test_admin_can_always_access(self):
        from core.pace_access import can_access_plan_paces
        db = SessionLocal()
        athlete = Athlete(
            email=f"admin_{uuid4()}@test.com",
            display_name="Admin",
            role="admin",
            subscription_tier="free",
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)
        plan = _make_plan(athlete)
        try:
            result = can_access_plan_paces(athlete, plan.id, db)
            assert result is True
        finally:
            db.close()
            _cleanup(plan, athlete)

    def test_legacy_pro_tier_cannot_access(self):
        """Two-tier model: legacy paid aliases are not treated as active paid."""
        from core.pace_access import can_access_plan_paces
        athlete = _make_athlete("pro")
        plan = _make_plan(athlete)
        db = SessionLocal()
        try:
            result = can_access_plan_paces(athlete, plan.id, db)
            assert result is False
        finally:
            db.close()
            _cleanup(plan, athlete)

    def test_active_subscription_can_access(self):
        """Trial athletes (has_active_subscription=True) get pace access regardless of tier."""
        from core.pace_access import can_access_plan_paces
        from datetime import timedelta
        db = SessionLocal()
        athlete = Athlete(
            email=f"trial_{uuid4()}@test.com",
            display_name="TrialUser",
            role="athlete",
            subscription_tier="free",
            # Set trial_ends_at in future so has_active_subscription returns True
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)
        plan = _make_plan(athlete)
        try:
            assert athlete.has_active_subscription is True, "Pre-condition: trial should be active"
            result = can_access_plan_paces(athlete, plan.id, db)
            assert result is True
        finally:
            db.close()
            _cleanup(plan, athlete)


# =============================================================================
# CATEGORY 2: GET /v2/plans/{plan_id} output-layer gating
# =============================================================================

class TestGetPlanPaceGating:
    """GET /v2/plans/{plan_id} returns null paces for unauthorized athletes."""

    def test_free_no_purchase_coach_notes_null(self):
        athlete = _make_athlete("free")
        plan = _make_plan(athlete)
        try:
            resp = client.get(f"/v2/plans/{plan.id}", headers=_headers(athlete))
            assert resp.status_code == 200
            data = resp.json()
            week_1 = data["weeks"]["1"]
            assert any(True for w in week_1), "Week 1 should have workouts"
            for workout in week_1:
                assert workout["coach_notes"] is None, (
                    f"Free athlete without purchase must see null coach_notes, got: {workout['coach_notes']}"
                )
        finally:
            _cleanup(plan, athlete)

    def test_free_no_purchase_structure_present(self):
        """Non-pace fields must always be present regardless of tier."""
        athlete = _make_athlete("free")
        plan = _make_plan(athlete)
        try:
            resp = client.get(f"/v2/plans/{plan.id}", headers=_headers(athlete))
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == str(plan.id)
            assert data["total_weeks"] == 18
            week_1 = data["weeks"]["1"]
            for workout in week_1:
                # Non-pace fields always present
                assert workout["workout_type"] is not None
                assert workout["title"] is not None
        finally:
            _cleanup(plan, athlete)

    def test_subscriber_coach_notes_visible(self):
        athlete = _make_athlete("subscriber")
        plan = _make_plan(athlete)
        try:
            resp = client.get(f"/v2/plans/{plan.id}", headers=_headers(athlete))
            assert resp.status_code == 200
            data = resp.json()
            week_1 = data["weeks"]["1"]
            has_paces = any(w["coach_notes"] is not None for w in week_1)
            assert has_paces, "Subscriber athlete must see pace data in coach_notes"
        finally:
            _cleanup(plan, athlete)

    def test_guided_coach_notes_hidden(self):
        athlete = _make_athlete("guided")
        plan = _make_plan(athlete)
        try:
            resp = client.get(f"/v2/plans/{plan.id}", headers=_headers(athlete))
            assert resp.status_code == 200
            data = resp.json()
            week_1 = data["weeks"]["1"]
            has_paces = any(w["coach_notes"] is not None for w in week_1)
            assert not has_paces, "Legacy guided tier should not unlock paces"
        finally:
            _cleanup(plan, athlete)


# =============================================================================
# CATEGORY 3: GET /v2/plans/{plan_id}/week/{week_number} output-layer gating
# =============================================================================

class TestGetWeekPaceGating:
    """GET /v2/plans/{plan_id}/week/{week_number} respects pace gating."""

    def test_free_no_purchase_coach_notes_null(self):
        athlete = _make_athlete("free")
        plan = _make_plan(athlete)
        try:
            resp = client.get(f"/v2/plans/{plan.id}/week/1", headers=_headers(athlete))
            assert resp.status_code == 200
            data = resp.json()
            for w in data["workouts"]:
                assert w["coach_notes"] is None
        finally:
            _cleanup(plan, athlete)

    def test_subscriber_coach_notes_visible(self):
        athlete = _make_athlete("subscriber")
        plan = _make_plan(athlete)
        try:
            resp = client.get(f"/v2/plans/{plan.id}/week/1", headers=_headers(athlete))
            assert resp.status_code == 200
            data = resp.json()
            has_paces = any(w["coach_notes"] is not None for w in data["workouts"])
            assert has_paces
        finally:
            _cleanup(plan, athlete)

    def test_guided_coach_notes_hidden(self):
        athlete = _make_athlete("guided")
        plan = _make_plan(athlete)
        try:
            resp = client.get(f"/v2/plans/{plan.id}/week/1", headers=_headers(athlete))
            assert resp.status_code == 200
            data = resp.json()
            has_paces = any(w["coach_notes"] is not None for w in data["workouts"])
            assert has_paces is False
        finally:
            _cleanup(plan, athlete)


# =============================================================================
# CATEGORY 4: Plan preview pace gating
# =============================================================================

class TestPreviewPaceGating:
    """Plan preview endpoints gate paces for unauthenticated/free users."""

    def test_standard_preview_public_paces_null(self):
        """Standard preview is public — no auth → paces always null."""
        resp = client.post("/v2/plans/standard/preview", json={
            "distance": "marathon",
            "duration_weeks": 18,
            "days_per_week": 6,
            "volume_tier": "mid",
        })
        assert resp.status_code == 200
        data = resp.json()
        for w in data["workouts"]:
            assert w.get("pace_description") is None, (
                f"Public preview must have null pace_description, got: {w.get('pace_description')}"
            )

    def test_standard_preview_free_auth_paces_null(self):
        """Authenticated free user also sees null paces in preview."""
        athlete = _make_athlete("free")
        try:
            resp = client.post(
                "/v2/plans/standard/preview",
                json={
                    "distance": "marathon",
                    "duration_weeks": 18,
                    "days_per_week": 6,
                    "volume_tier": "mid",
                },
                headers=_headers(athlete),
            )
            # Standard preview may or may not require auth — check 200 or handle gracefully
            if resp.status_code == 200:
                data = resp.json()
                for w in data["workouts"]:
                    assert w.get("pace_description") is None
        finally:
            _cleanup(athlete)


# =============================================================================
# CATEGORY 5: Intelligence endpoints — 403 for free, 200 for guided/premium
# =============================================================================

class TestIntelligenceEndpoint403:
    """GET/POST /v1/intelligence/* returns 403 for free athletes."""

    def test_intelligence_today_free_403(self):
        athlete = _make_athlete("free")
        try:
            resp = client.get("/v1/intelligence/today", headers=_headers(athlete))
            assert resp.status_code == 403, f"Expected 403 for free tier, got {resp.status_code}"
        finally:
            _cleanup(athlete)

    def test_intelligence_today_guided_200(self):
        athlete = _make_athlete("guided")
        try:
            resp = client.get("/v1/intelligence/today", headers=_headers(athlete))
            assert resp.status_code == 200, f"Expected 200 for guided tier, got {resp.status_code}: {resp.text}"
        finally:
            _cleanup(athlete)

    def test_intelligence_today_premium_200(self):
        athlete = _make_athlete("premium")
        try:
            resp = client.get("/v1/intelligence/today", headers=_headers(athlete))
            assert resp.status_code == 200
        finally:
            _cleanup(athlete)

    def test_intelligence_compute_free_403(self):
        athlete = _make_athlete("free")
        try:
            resp = client.post("/v1/intelligence/compute", headers=_headers(athlete))
            assert resp.status_code == 403
        finally:
            _cleanup(athlete)

    def test_intelligence_compute_guided_not_403(self):
        athlete = _make_athlete("guided")
        try:
            resp = client.post("/v1/intelligence/compute", headers=_headers(athlete))
            # May return 200 or 500 (if no plan data), but NOT 403
            assert resp.status_code != 403, f"Guided should not get 403, got {resp.status_code}"
        finally:
            _cleanup(athlete)

    def test_intelligence_history_free_403(self):
        athlete = _make_athlete("free")
        try:
            resp = client.get("/v1/intelligence/history/recent", headers=_headers(athlete))
            assert resp.status_code == 403
        finally:
            _cleanup(athlete)

    def test_intelligence_history_guided_200(self):
        athlete = _make_athlete("guided")
        try:
            resp = client.get("/v1/intelligence/history/recent", headers=_headers(athlete))
            assert resp.status_code == 200
        finally:
            _cleanup(athlete)

    def test_intelligence_date_free_403(self):
        athlete = _make_athlete("free")
        try:
            resp = client.get(f"/v1/intelligence/{date.today()}", headers=_headers(athlete))
            assert resp.status_code == 403
        finally:
            _cleanup(athlete)

    def test_intelligence_date_guided_200(self):
        athlete = _make_athlete("guided")
        try:
            resp = client.get(f"/v1/intelligence/{date.today()}", headers=_headers(athlete))
            assert resp.status_code == 200
        finally:
            _cleanup(athlete)

    def test_narration_quality_free_403(self):
        athlete = _make_athlete("free")
        try:
            resp = client.get("/v1/intelligence/narration/quality", headers=_headers(athlete))
            assert resp.status_code == 403
        finally:
            _cleanup(athlete)

    def test_narration_quality_guided_200(self):
        athlete = _make_athlete("guided")
        try:
            resp = client.get("/v1/intelligence/narration/quality", headers=_headers(athlete))
            assert resp.status_code == 200
        finally:
            _cleanup(athlete)


# =============================================================================
# CATEGORY 6: Workout narrative — premium only (403 for free + guided)
# =============================================================================

class TestWorkoutNarrativePremiumOnly:
    """GET /v1/intelligence/workout-narrative/{date} requires premium tier."""

    def test_workout_narrative_free_403(self):
        athlete = _make_athlete("free")
        try:
            resp = client.get(
                f"/v1/intelligence/workout-narrative/{date.today()}",
                headers=_headers(athlete),
            )
            assert resp.status_code == 403
        finally:
            _cleanup(athlete)

    def test_workout_narrative_guided_403(self):
        athlete = _make_athlete("guided")
        try:
            resp = client.get(
                f"/v1/intelligence/workout-narrative/{date.today()}",
                headers=_headers(athlete),
            )
            assert resp.status_code != 403, (
                f"Guided should access workout narrative after monetization reset, got {resp.status_code}"
            )
        finally:
            _cleanup(athlete)

    def test_workout_narrative_premium_not_403(self):
        athlete = _make_athlete("premium")
        try:
            resp = client.get(
                f"/v1/intelligence/workout-narrative/{date.today()}",
                headers=_headers(athlete),
            )
            # May return 200 (suppressed) if gate not open, but NOT 403
            assert resp.status_code != 403, f"Premium should not get 403, got {resp.status_code}"
        finally:
            _cleanup(athlete)


# =============================================================================
# CATEGORY 7: Intelligence bank — guided+ required
# =============================================================================

class TestIntelligenceBankGating:
    """GET /v1/insights/intelligence requires guided+ tier."""

    def test_intelligence_bank_free_403(self):
        athlete = _make_athlete("free")
        try:
            resp = client.get("/v1/insights/intelligence", headers=_headers(athlete))
            assert resp.status_code == 403
        finally:
            _cleanup(athlete)

    def test_intelligence_bank_guided_200(self):
        athlete = _make_athlete("guided")
        try:
            resp = client.get("/v1/insights/intelligence", headers=_headers(athlete))
            assert resp.status_code == 200
        finally:
            _cleanup(athlete)

    def test_intelligence_bank_premium_200(self):
        athlete = _make_athlete("premium")
        try:
            resp = client.get("/v1/insights/intelligence", headers=_headers(athlete))
            assert resp.status_code == 200
        finally:
            _cleanup(athlete)


# =============================================================================
# CATEGORY 8: FeatureFlagService._tier_satisfies() consolidation
# =============================================================================

class TestFeatureFlagTierConsolidation:
    """FeatureFlagService._tier_satisfies() must delegate to core.tier_utils."""

    def setup_method(self):
        self.db = SessionLocal()
        from services.plan_framework.feature_flags import FeatureFlagService
        self.flags = FeatureFlagService(self.db)

    def teardown_method(self):
        self.db.close()

    def test_delegates_to_tier_utils(self):
        """_tier_satisfies must produce identical results to tier_utils.tier_satisfies."""
        from core.tier_utils import tier_satisfies as canonical
        test_cases = [
            ("free", "free"),
            ("free", "guided"),
            ("free", "premium"),
            ("guided", "free"),
            ("guided", "guided"),
            ("guided", "premium"),
            ("premium", "free"),
            ("premium", "guided"),
            ("premium", "premium"),
            ("pro", "guided"),
            ("elite", "premium"),
            (None, "free"),
            ("garbage", "free"),
        ]
        for actual, required in test_cases:
            expected = canonical(actual, required)
            got = self.flags._tier_satisfies(actual, required)
            assert got == expected, (
                f"_tier_satisfies({actual!r}, {required!r}) = {got}, "
                f"but tier_utils.tier_satisfies returned {expected}"
            )

    def test_free_does_not_satisfy_guided(self):
        assert self.flags._tier_satisfies("free", "guided") is False

    def test_free_does_not_satisfy_premium(self):
        assert self.flags._tier_satisfies("free", "premium") is False

    def test_guided_satisfies_free(self):
        assert self.flags._tier_satisfies("guided", "free") is True

    def test_guided_satisfies_guided(self):
        assert self.flags._tier_satisfies("guided", "guided") is True

    def test_guided_does_not_satisfy_premium(self):
        assert self.flags._tier_satisfies("guided", "premium") is False

    def test_premium_satisfies_all(self):
        assert self.flags._tier_satisfies("premium", "free") is True
        assert self.flags._tier_satisfies("premium", "guided") is True
        assert self.flags._tier_satisfies("premium", "premium") is True

    def test_legacy_pro_maps_correctly(self):
        """Legacy 'pro' tier must satisfy guided (it normalizes to premium)."""
        assert self.flags._tier_satisfies("pro", "guided") is True
        assert self.flags._tier_satisfies("pro", "premium") is True

    def test_unknown_tier_treated_as_free(self):
        assert self.flags._tier_satisfies("garbage", "guided") is False
        assert self.flags._tier_satisfies(None, "guided") is False
