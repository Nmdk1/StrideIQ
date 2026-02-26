"""
Monetization Tier Mapping — Contract Tests

Maps the build plan's monetization table to the entitlement system.
These tests verify that each tier gets exactly what the build plan specifies
and that paid features are properly gated.

Build plan tier table (docs/TRAINING_PLAN_REBUILD_PLAN.md):

| Tier                         | Plan Paces | Adaptation    | Intelligence         |
|------------------------------|------------|---------------|----------------------|
| Free                         | null       | None (403)    | None (403)           |
| One-time ($5)                | Full       | None (403)    | None (403)           |
| Guided Self-Coaching ($15/mo)| Full       | Full (200)    | Intelligence (200)   |
| Premium ($25/mo)             | Full       | Full (200)    | All incl. narratives |

Group A — real tests (xfail removed).  Features fully implemented in Phase 2.
Group B — structured xfail. Features not yet built or not yet endpoint-gated.

Sources:
    docs/TRAINING_PLAN_REBUILD_PLAN.md (Monetization Mapping)
    docs/SESSION_HANDOFF_2026-02-26_MONETIZATION_PHASE2.md
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
# SHARED HELPERS  (mirrors test_monetization_phase2.py)
# =============================================================================

def _headers(user: Athlete) -> dict:
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def _make_athlete(tier: str = "free") -> Athlete:
    db = SessionLocal()
    athlete = Athlete(
        email=f"tm_{uuid4()}@test.com",
        display_name=f"TierMap-{tier}",
        role="athlete",
        subscription_tier=tier,
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    db.close()
    return athlete


def _make_plan(athlete: Athlete, workout_type: str = "threshold") -> TrainingPlan:
    """Create a plan with one quality workout containing coach_notes (pace info)."""
    db = SessionLocal()
    plan = TrainingPlan(
        athlete_id=athlete.id,
        name="Test Plan — Tier Mapping",
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
        scheduled_date=date(2026, 3, 5),
        week_number=1,
        day_of_week=2,
        workout_type=workout_type,
        phase="build",
        title="Threshold Run",
        description="Sustained threshold effort",
        coach_notes="5:45-6:00/mile threshold pace",
        target_distance_km=14.0,
    )
    db.add(workout)
    db.commit()
    db.refresh(plan)
    db.close()
    return plan


def _make_purchase(athlete: Athlete, plan: TrainingPlan) -> PlanPurchase:
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
    from sqlalchemy import text
    db = SessionLocal()
    try:
        plan_ids = [str(o.id) for o in objs if isinstance(o, TrainingPlan)]
        athlete_ids = [str(o.id) for o in objs if isinstance(o, Athlete)]
        purchase_ids = [str(o.id) for o in objs if isinstance(o, PlanPurchase)]

        for pid in purchase_ids:
            db.execute(text("DELETE FROM plan_purchases WHERE id = :id"), {"id": pid})
        for plan_id in plan_ids:
            db.execute(text("DELETE FROM plan_purchases WHERE plan_snapshot_id = :pid"), {"pid": plan_id})
            db.execute(text("DELETE FROM planned_workout WHERE plan_id = :pid::uuid"), {"pid": plan_id})
            db.execute(text("DELETE FROM training_plan WHERE id = :pid::uuid"), {"pid": plan_id})
        for aid in athlete_ids:
            db.execute(text("""
                DELETE FROM planned_workout pw
                USING training_plan tp
                WHERE pw.plan_id = tp.id AND tp.athlete_id = :aid::uuid
            """), {"aid": aid})
            db.execute(text("DELETE FROM plan_purchases WHERE athlete_id = :aid::uuid"), {"aid": aid})
            db.execute(text("DELETE FROM training_plan WHERE athlete_id = :aid::uuid"), {"aid": aid})
            db.execute(text("DELETE FROM athlete WHERE id = :aid::uuid"), {"aid": aid})
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _all_coach_notes(plan_response: dict) -> list:
    """Extract all coach_notes values from a plan response across all weeks."""
    notes = []
    for week_workouts in plan_response.get("weeks", {}).values():
        for w in week_workouts:
            notes.append(w.get("coach_notes"))
    return notes


# =============================================================================
# GROUP A — Free Tier (real tests, no xfail)
# =============================================================================

class TestFreeTier:
    """Free tier: RPI calculator + plan structure with locked paces. No adaptation."""

    def test_free_can_calculate_rpi(self):
        """RPI calculator is public — no auth required, always returns 200."""
        # 10K in 45:00 (2700s) — valid payload
        resp = client.post("/v1/public/rpi/calculate", json={
            "distance_meters": 10000,
            "time_seconds": 2700,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "rpi" in data
        assert data["rpi"] > 0

    def test_free_gets_basic_plan_outline(self):
        """Free athletes get the full plan structure (200), paces_locked=True."""
        athlete = _make_athlete("free")
        plan = _make_plan(athlete)
        try:
            resp = client.get(f"/v2/plans/{plan.id}", headers=_headers(athlete))
            assert resp.status_code == 200
            data = resp.json()
            assert data["paces_locked"] is True
            assert "weeks" in data
        finally:
            _cleanup(plan, athlete)

    def test_free_no_calculated_paces(self):
        """Free plans return coach_notes=null — paces are gated."""
        athlete = _make_athlete("free")
        plan = _make_plan(athlete)
        try:
            resp = client.get(f"/v2/plans/{plan.id}", headers=_headers(athlete))
            assert resp.status_code == 200
            notes = _all_coach_notes(resp.json())
            assert all(n is None for n in notes), (
                f"Expected all coach_notes to be null for free tier, got: {notes}"
            )
        finally:
            _cleanup(plan, athlete)

    def test_free_no_daily_adaptation(self):
        """Free athletes get 403 on intelligence/adaptation endpoints."""
        athlete = _make_athlete("free")
        try:
            resp = client.get("/v1/intelligence/today", headers=_headers(athlete))
            assert resp.status_code == 403
        finally:
            _cleanup(athlete)

    def test_free_no_coach_narratives(self):
        """Free athletes get 403 on workout-narrative endpoint (premium only)."""
        athlete = _make_athlete("free")
        try:
            resp = client.get(
                "/v1/intelligence/workout-narrative/2026-03-10",
                headers=_headers(athlete),
            )
            assert resp.status_code == 403
        finally:
            _cleanup(athlete)

    def test_free_no_intelligence_bank(self):
        """Free athletes get 403 on intelligence bank (guided+ only)."""
        athlete = _make_athlete("free")
        try:
            resp = client.get("/v1/insights/intelligence", headers=_headers(athlete))
            assert resp.status_code == 403
        finally:
            _cleanup(athlete)


# =============================================================================
# GROUP A — One-Time Purchase Tier (real tests, no xfail)
# =============================================================================

class TestOneTimeTier:
    """One-time $5 purchase: full paces unlocked per plan. No adaptation."""

    def test_one_time_gets_complete_plan(self):
        """After PlanPurchase, paces_locked=False on that plan."""
        athlete = _make_athlete("free")
        plan = _make_plan(athlete)
        purchase = _make_purchase(athlete, plan)
        try:
            resp = client.get(f"/v2/plans/{plan.id}", headers=_headers(athlete))
            assert resp.status_code == 200
            assert resp.json()["paces_locked"] is False
        finally:
            _cleanup(purchase, plan, athlete)

    def test_one_time_gets_calculated_paces(self):
        """After PlanPurchase, coach_notes are present (not null)."""
        athlete = _make_athlete("free")
        plan = _make_plan(athlete)
        purchase = _make_purchase(athlete, plan)
        try:
            resp = client.get(f"/v2/plans/{plan.id}", headers=_headers(athlete))
            assert resp.status_code == 200
            notes = _all_coach_notes(resp.json())
            non_null = [n for n in notes if n is not None]
            assert len(non_null) > 0, "Expected at least one coach_notes after purchase"
        finally:
            _cleanup(purchase, plan, athlete)

    def test_one_time_plan_is_static(self):
        """One-time purchasers are still free-tier athletes — 403 on intelligence."""
        athlete = _make_athlete("free")
        plan = _make_plan(athlete)
        purchase = _make_purchase(athlete, plan)
        try:
            resp = client.get("/v1/intelligence/today", headers=_headers(athlete))
            assert resp.status_code == 403, (
                "One-time plan purchase must NOT grant adaptation access "
                "(requires guided subscription)"
            )
        finally:
            _cleanup(purchase, plan, athlete)

    def test_one_time_no_coach_access(self):
        """One-time purchasers still get 403 on premium narrative endpoint."""
        athlete = _make_athlete("free")
        plan = _make_plan(athlete)
        purchase = _make_purchase(athlete, plan)
        try:
            resp = client.get(
                "/v1/intelligence/workout-narrative/2026-03-10",
                headers=_headers(athlete),
            )
            assert resp.status_code == 403
        finally:
            _cleanup(purchase, plan, athlete)


# =============================================================================
# GROUP A — Guided Self-Coaching Tier (real tests, no xfail)
# =============================================================================

class TestGuidedTierGroupA:
    """Guided tier: full adaptation access, no premium narratives."""

    def test_guided_gets_daily_adaptation(self):
        """Guided athletes get 200 (not 403) on daily intelligence endpoint."""
        athlete = _make_athlete("guided")
        try:
            resp = client.get("/v1/intelligence/today", headers=_headers(athlete))
            assert resp.status_code == 200, (
                f"Guided tier should access /v1/intelligence/today, got {resp.status_code}"
            )
        finally:
            _cleanup(athlete)

    def test_guided_gets_intelligence_insights(self):
        """Guided daily intelligence response contains expected schema keys."""
        athlete = _make_athlete("guided")
        try:
            resp = client.get("/v1/intelligence/today", headers=_headers(athlete))
            assert resp.status_code == 200
            data = resp.json()
            assert "insight_count" in data or "insights" in data or "status" in data, (
                f"Unexpected response shape: {list(data.keys())}"
            )
        finally:
            _cleanup(athlete)

    def test_guided_gets_intelligence_bank(self):
        """Guided athletes can access the intelligence bank endpoint."""
        athlete = _make_athlete("guided")
        try:
            resp = client.get("/v1/insights/intelligence", headers=_headers(athlete))
            assert resp.status_code == 200
        finally:
            _cleanup(athlete)

    def test_guided_no_narratives(self):
        """Guided athletes get 403 on workout-narrative — that's premium only."""
        athlete = _make_athlete("guided")
        try:
            resp = client.get(
                "/v1/intelligence/workout-narrative/2026-03-10",
                headers=_headers(athlete),
            )
            assert resp.status_code == 403, (
                f"Workout narratives must be premium-only, but guided got {resp.status_code}"
            )
        finally:
            _cleanup(athlete)


# =============================================================================
# GROUP A — Premium Tier (real tests, no xfail)
# =============================================================================

class TestPremiumTierGroupA:
    """Premium tier: everything guided has plus contextual narratives."""

    def test_premium_gets_all_guided_features(self):
        """Premium includes guided-level access to daily intelligence."""
        athlete = _make_athlete("premium")
        try:
            resp = client.get("/v1/intelligence/today", headers=_headers(athlete))
            assert resp.status_code == 200, (
                f"Premium must have guided-level access to intelligence, got {resp.status_code}"
            )
        finally:
            _cleanup(athlete)

    def test_premium_gets_adaptation_narration(self):
        """Premium can hit all intelligence endpoints including intelligence bank."""
        athlete = _make_athlete("premium")
        try:
            resp = client.get("/v1/insights/intelligence", headers=_headers(athlete))
            assert resp.status_code == 200
        finally:
            _cleanup(athlete)

    def test_premium_gets_contextual_narratives(self):
        """Premium athletes can access the workout-narrative endpoint (200, not 403)."""
        athlete = _make_athlete("premium")
        try:
            resp = client.get(
                "/v1/intelligence/workout-narrative/2026-03-10",
                headers=_headers(athlete),
            )
            # 200 or 404 (no workout that day) — either is fine; 403 is not
            assert resp.status_code != 403, (
                f"Premium must not be blocked on workout-narrative, got 403"
            )
        finally:
            _cleanup(athlete)


# =============================================================================
# GROUP B — Structured xfail: features not yet endpoint-gated or unbuilt
# =============================================================================

_XFAIL_NOT_BUILT = pytest.mark.xfail(
    reason="Feature not yet built or not yet endpoint-gated",
    strict=True,
)

_XFAIL_NO_ENDPOINT = pytest.mark.xfail(
    reason="No tier-gated endpoint exists for this feature yet",
    strict=True,
)


@_XFAIL_NOT_BUILT
class TestGuidedTierGroupB:
    """Guided features that require deeper integration not yet tested via HTTP."""

    def test_guided_gets_n1_plan_parameters(self):
        """N=1 profile (long run baseline, volume tier) adjusts plan generation.

        Gate: requires generating a full plan and verifying athlete_plan_profile
        values are applied. Needs a more sophisticated integration test with
        Strava data fixtures — not testable with a minimal DB plan.
        """
        athlete = _make_athlete("guided")
        plan = _make_plan(athlete)
        try:
            # Placeholder: generate a plan and verify N=1 profile was consulted.
            # When this gate opens, assert plan config matches athlete_plan_profile output.
            raise NotImplementedError(
                "test_guided_gets_n1_plan_parameters: needs Strava fixture + plan generation"
            )
        finally:
            _cleanup(plan, athlete)

    def test_guided_gets_readiness_score(self):
        """Readiness score is computed daily and accessible to guided athletes.

        Gate: DailyReadiness rows exist for the athlete (Celery task has run).
        The /v1/intelligence/today endpoint returns readiness_score in its payload,
        but testing a meaningful score requires pre-seeded activity data.
        """
        athlete = _make_athlete("guided")
        try:
            # When this gate opens: seed activity data, trigger compute, assert score.
            raise NotImplementedError(
                "test_guided_gets_readiness_score: needs activity data fixtures"
            )
        finally:
            _cleanup(athlete)

    def test_guided_gets_completion_tracking(self):
        """Workout completion is tracked; self-regulation is logged.

        Gate: requires completing a workout (PATCH endpoint) and verifying
        SelfRegulationLog is populated. Tests the full state-machine path.
        """
        athlete = _make_athlete("guided")
        plan = _make_plan(athlete)
        try:
            raise NotImplementedError(
                "test_guided_gets_completion_tracking: needs full workout state machine test"
            )
        finally:
            _cleanup(plan, athlete)

    def test_guided_no_advisory_mode(self):
        """Advisory mode (coach proposals) is premium only.

        Gate: /v1/coach/chat is not yet tier-gated — apply require_tier(["premium"])
        before this test can pass. When gated, guided should receive 403.
        """
        athlete = _make_athlete("guided")
        try:
            raise NotImplementedError(
                "test_guided_no_advisory_mode: /v1/coach/chat not yet tier-gated"
            )
        finally:
            _cleanup(athlete)


@_XFAIL_NOT_BUILT
class TestPremiumTierGroupB:
    """Premium features that require unbuilt infrastructure."""

    def test_premium_gets_coach_advisory_mode(self):
        """Coach proposes adjustments; athlete approves/rejects.

        Gate: /v1/coach/chat must be tier-gated to premium AND advisory
        proposal format must exist in the response schema.
        """
        athlete = _make_athlete("premium")
        try:
            raise NotImplementedError(
                "test_premium_gets_coach_advisory_mode: advisory mode not yet built"
            )
        finally:
            _cleanup(athlete)

    def test_premium_gets_multi_race_planning(self):
        """Multiple concurrent plans with tune-up race integration.

        Gate: Phase 4 infrastructure (multi-race scheduling, tune-up race
        endpoint) must be built before this test can pass.
        """
        athlete = _make_athlete("premium")
        try:
            raise NotImplementedError(
                "test_premium_gets_multi_race_planning: Phase 4 not yet built"
            )
        finally:
            _cleanup(athlete)

    def test_premium_gets_intelligence_bank_dashboard(self):
        """Full intelligence bank dashboard with visualisation.

        Gate: dashboard endpoint (distinct from /v1/insights/intelligence list)
        does not yet exist. Frontend-driven feature.
        """
        athlete = _make_athlete("premium")
        try:
            raise NotImplementedError(
                "test_premium_gets_intelligence_bank_dashboard: dashboard endpoint not built"
            )
        finally:
            _cleanup(athlete)

    def test_premium_gets_conversational_coach(self):
        """Full conversational AI coach access.

        Gate: /v1/coach/chat is not yet tier-gated (Phase 3B/3C dependency).
        When gated, guided should receive 403 and premium should receive 200.
        """
        athlete = _make_athlete("premium")
        try:
            raise NotImplementedError(
                "test_premium_gets_conversational_coach: coach endpoint not yet tier-gated"
            )
        finally:
            _cleanup(athlete)


@_XFAIL_NOT_BUILT
class TestTierTransitions:
    """Upgrading/downgrading tiers handles entitlements correctly.

    All four tests require a production-like event sequence:
    Stripe webhook fires → tier updates → access changes.
    Unit-testing this end-to-end requires webhook simulation fixtures
    that are beyond the current test infrastructure.
    """

    def test_free_to_guided_activates_adaptation(self):
        """When free athlete subscribes to guided: adaptation pipeline activates.

        Gate: requires simulating a Stripe subscription.created webhook,
        verifying subscription_tier updated, then confirming intelligence
        endpoint flips from 403 → 200.
        """
        raise NotImplementedError(
            "test_free_to_guided_activates_adaptation: needs Stripe webhook simulation"
        )

    def test_guided_to_premium_activates_narratives(self):
        """When guided upgrades to premium: workout-narrative endpoint unlocks.

        Gate: same Stripe webhook simulation requirement.
        """
        raise NotImplementedError(
            "test_guided_to_premium_activates_narratives: needs Stripe webhook simulation"
        )

    def test_premium_to_free_preserves_plan(self):
        """When premium downgrades to free: plan persists, adaptation stops.

        Gate: requires subscription cancellation webhook simulation and
        verifying plan is still accessible but intelligence returns 403.
        """
        raise NotImplementedError(
            "test_premium_to_free_preserves_plan: needs Stripe webhook simulation"
        )

    def test_one_time_to_guided_preserves_plan(self):
        """When one-time purchaser subscribes to guided: plan gains adaptation.

        Gate: one-time purchaser starts with PlanPurchase; subscription webhook
        updates subscription_tier to guided; plan should still unlock paces
        AND intelligence endpoints should now return 200.
        """
        raise NotImplementedError(
            "test_one_time_to_guided_preserves_plan: needs Stripe webhook simulation"
        )
