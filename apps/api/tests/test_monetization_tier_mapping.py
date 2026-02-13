"""
Monetization Tier Mapping — Contract Tests

Maps the build plan's monetization table to the entitlement system.
These tests verify that each tier gets exactly what the build plan specifies
and that paid features are properly gated.

Build plan tier table (docs/TRAINING_PLAN_REBUILD_PLAN.md):

| Tier                        | Plan Features                                    | Adaptation                        |
|-----------------------------|--------------------------------------------------|-----------------------------------|
| Free                        | RPI calculator, basic plan outline               | None                              |
| One-time ($5)               | Complete race plan, calculated paces              | None (static)                     |
| Guided Self-Coaching ($15/mo)| N=1 params, daily adaptation, readiness, intel   | Full daily adaptation             |
| Premium ($25/mo)            | All above + narratives, advisory, multi-race      | Adaptation + coach proposals      |

Current system tiers: free, pro, elite, premium, guided, subscription
Mapping needed: build plan tiers → current system tiers

Sources:
    docs/TRAINING_PLAN_REBUILD_PLAN.md (Monetization Mapping)
    services/plan_framework/entitlements.py
"""

import pytest
import sys
import os
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# xfail — tier mapping needs implementation
# ---------------------------------------------------------------------------
_XFAIL_TIERS = pytest.mark.xfail(
    reason="Monetization tier mapping not yet aligned to build plan",
    strict=True,
)


# ===========================================================================
# Free Tier
# ===========================================================================

@_XFAIL_TIERS
class TestFreeTier:
    """Free tier: RPI calculator + basic plan outline. No adaptation."""

    def test_free_can_calculate_rpi(self):
        """Free athletes can use the RPI calculator."""
        raise NotImplementedError("Tier: RPI access for free")

    def test_free_gets_basic_plan_outline(self):
        """
        Free plan = phase structure, effort descriptions, general guidance.
        No calculated paces, no N=1 parameters.
        """
        raise NotImplementedError("Tier: basic plan for free")

    def test_free_no_calculated_paces(self):
        """
        Free plans show effort descriptions ("easy effort, conversational")
        but NOT calculated pace targets.
        """
        raise NotImplementedError("Tier: pace gating")

    def test_free_no_daily_adaptation(self):
        """Free athletes do NOT get readiness scores or intelligence insights."""
        raise NotImplementedError("Tier: adaptation gating")

    def test_free_no_coach_narratives(self):
        """Free athletes do NOT get AI coach narratives on workouts."""
        raise NotImplementedError("Tier: narrative gating")

    def test_free_no_intelligence_bank(self):
        """Free athletes do NOT get N=1 personalized insights."""
        raise NotImplementedError("Tier: intelligence bank gating")


# ===========================================================================
# One-Time Purchase ($5)
# ===========================================================================

@_XFAIL_TIERS
class TestOneTimeTier:
    """One-time purchase: complete race plan with calculated paces. Static."""

    def test_one_time_gets_complete_plan(self):
        """
        One-time purchase unlocks the full plan: proper periodization,
        workout structure, calculated paces from RPI.
        """
        raise NotImplementedError("Tier: one-time plan access")

    def test_one_time_gets_calculated_paces(self):
        """Paces are included if athlete has RPI from signup or Strava."""
        raise NotImplementedError("Tier: pace access for one-time")

    def test_one_time_plan_is_static(self):
        """
        One-time plans are NOT adapted. No readiness, no intelligence,
        no weekly re-evaluation. The plan is generated once.
        """
        raise NotImplementedError("Tier: no adaptation for one-time")

    def test_one_time_no_coach_access(self):
        """One-time purchasers do NOT get conversational coach access."""
        raise NotImplementedError("Tier: coach gating for one-time")


# ===========================================================================
# Guided Self-Coaching ($15/mo)
# ===========================================================================

@_XFAIL_TIERS
class TestGuidedTier:
    """
    Guided Self-Coaching: the subscription moat.
    N=1 plan parameters, daily adaptation, readiness score,
    completion tracking, intelligence bank.
    """

    def test_guided_gets_n1_plan_parameters(self):
        """N=1 profile adjusts plan generation (duration-gated long runs, etc.)."""
        raise NotImplementedError("Tier: N=1 plan params for guided")

    def test_guided_gets_daily_adaptation(self):
        """Full daily adaptation: readiness → intelligence → insights."""
        raise NotImplementedError("Tier: daily adaptation for guided")

    def test_guided_gets_readiness_score(self):
        """Readiness score computed daily at 5 AM."""
        raise NotImplementedError("Tier: readiness for guided")

    def test_guided_gets_intelligence_insights(self):
        """All 7 intelligence rules surface insights for guided athletes."""
        raise NotImplementedError("Tier: intelligence for guided")

    def test_guided_gets_completion_tracking(self):
        """Workout completion tracked, self-regulation logged."""
        raise NotImplementedError("Tier: completion tracking for guided")

    def test_guided_gets_intelligence_bank(self):
        """N=1 insights from correlation engine (when gate met)."""
        raise NotImplementedError("Tier: intelligence bank for guided")

    def test_guided_no_narratives(self):
        """
        Guided tier does NOT get contextual workout narratives.
        Narratives are a premium differentiator.
        """
        raise NotImplementedError("Tier: narrative gating for guided")

    def test_guided_no_advisory_mode(self):
        """Coach advisory mode (proposes adjustments) is premium only."""
        raise NotImplementedError("Tier: advisory gating for guided")


# ===========================================================================
# Premium ($25/mo)
# ===========================================================================

@_XFAIL_TIERS
class TestPremiumTier:
    """Premium: everything + narratives, advisory, multi-race, recovery."""

    def test_premium_gets_all_guided_features(self):
        """Premium includes everything in guided tier."""
        raise NotImplementedError("Tier: premium superset of guided")

    def test_premium_gets_contextual_narratives(self):
        """Workout narratives from Phase 3B (when gate met)."""
        raise NotImplementedError("Tier: narratives for premium")

    def test_premium_gets_adaptation_narration(self):
        """Intelligence insight narrations from Phase 3A."""
        raise NotImplementedError("Tier: adaptation narration for premium")

    def test_premium_gets_coach_advisory_mode(self):
        """
        Coach proposes adjustments, athlete approves/rejects.
        Acceptance rate tracked for autonomy gate.
        """
        raise NotImplementedError("Tier: advisory mode for premium")

    def test_premium_gets_multi_race_planning(self):
        """Multiple concurrent plans with tune-up race integration."""
        raise NotImplementedError("Tier: multi-race for premium")

    def test_premium_gets_intelligence_bank_dashboard(self):
        """Full intelligence bank dashboard with visualization."""
        raise NotImplementedError("Tier: intelligence dashboard for premium")

    def test_premium_gets_conversational_coach(self):
        """Full conversational AI coach access."""
        raise NotImplementedError("Tier: conversational coach for premium")


# ===========================================================================
# Tier Transitions
# ===========================================================================

@_XFAIL_TIERS
class TestTierTransitions:
    """Upgrading/downgrading tiers handles entitlements correctly."""

    def test_free_to_guided_activates_adaptation(self):
        """
        When free athlete subscribes to guided:
        - Readiness computation starts
        - Intelligence pipeline runs at next 5 AM
        - Historical data is backfilled for N=1 profile
        """
        raise NotImplementedError("Tier: upgrade activation")

    def test_guided_to_premium_activates_narratives(self):
        """
        When guided upgrades to premium:
        - Coach narratives appear on insights
        - Workout narratives appear (if 3B gate met)
        - Advisory mode becomes available
        """
        raise NotImplementedError("Tier: premium upgrade")

    def test_premium_to_free_preserves_plan(self):
        """
        When premium downgrades to free:
        - Active plan remains but becomes static (no adaptation)
        - Historical data is preserved (re-activatable)
        - Narratives and insights stop appearing
        """
        raise NotImplementedError("Tier: downgrade graceful degradation")

    def test_one_time_to_guided_preserves_plan(self):
        """
        When one-time purchaser subscribes to guided:
        - Existing plan gains adaptation
        - Readiness starts computing
        - Self-regulation detection activates
        """
        raise NotImplementedError("Tier: one-time to subscription")
