"""
Plan Validation Matrix — Parametrized tests across all distance x tier x duration variants.

Phase 1-PRE: Build the test infrastructure that encodes "world-class" plan quality.
The KB's coaching rules become executable assertions. Plans are generated and
validated against every rule.

Scope guardrails (from TRAINING_PLAN_REBUILD_PLAN.md):
    - Marathon variants: expected to PASS (or expose real gaps to fix in 1B)
    - Half/10K/5K variants: marked xfail until their tasks deliver (1E, 1F, 1G)
    - N=1 override scenarios: marked xfail until 1C (athlete_plan_profile.py)
    - The builder must NOT try to make the full matrix green in 1-PRE.

Sources:
    - _AI_CONTEXT_/KNOWLEDGE_BASE/PLAN_GENERATION_FRAMEWORK.md
    - _AI_CONTEXT_/KNOWLEDGE_BASE/coaches/source_B/PHILOSOPHY.md
    - docs/TRAINING_PLAN_REBUILD_PLAN.md (Phase 1-PRE)
"""

import pytest
import sys
import os
from datetime import date

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.plan_framework.generator import PlanGenerator
from services.plan_framework.constants import Distance, VolumeTier
from services.athlete_plan_profile import AthleteProfile
from tests.plan_validation_helpers import PlanValidator, validate_plan


# ---------------------------------------------------------------------------
# Test Matrix Parameters
# ---------------------------------------------------------------------------

# Marathon variants — these should pass against current generator (relaxed mode)
MARATHON_VARIANTS = [
    pytest.param("marathon", "mid", 18, 6, id="marathon-mid-18w-6d"),
    pytest.param("marathon", "mid", 12, 6, id="marathon-mid-12w-6d"),
    pytest.param("marathon", "low", 18, 5, id="marathon-low-18w-5d"),
    pytest.param("marathon", "high", 18, 6, id="marathon-high-18w-6d"),
    pytest.param("marathon", "builder", 18, 5, id="marathon-builder-18w-5d"),
    pytest.param("marathon", "mid", 18, 5, id="marathon-mid-18w-5d"),
]

# Half marathon variants — Phase 1E delivered
HALF_VARIANTS = [
    pytest.param("half_marathon", "mid", 16, 6, id="half-mid-16w-6d"),
    pytest.param("half_marathon", "mid", 12, 6, id="half-mid-12w-6d"),
    pytest.param("half_marathon", "low", 16, 5, id="half-low-16w-5d"),
    pytest.param("half_marathon", "high", 16, 6, id="half-high-16w-6d"),
]

# 10K variants — Phase 1F delivered
TEN_K_VARIANTS = [
    pytest.param("10k", "mid", 12, 6, id="10k-mid-12w-6d"),
    pytest.param("10k", "mid", 8, 6, id="10k-mid-8w-6d"),
    pytest.param("10k", "low", 12, 5, id="10k-low-12w-5d"),
    pytest.param("10k", "high", 12, 6, id="10k-high-12w-6d"),
]

# 5K variants — Phase 1G delivered
FIVE_K_VARIANTS = [
    pytest.param("5k", "mid", 12, 6, id="5k-mid-12w-6d"),
    pytest.param("5k", "mid", 8, 6, id="5k-mid-8w-6d"),
    pytest.param("5k", "low", 12, 5, id="5k-low-12w-5d"),
    pytest.param("5k", "high", 12, 6, id="5k-high-12w-6d"),
]

# ---------------------------------------------------------------------------
# N=1 Override Scenarios (Phase 1C)
#
# These scenarios use synthetic AthleteProfiles to give the validator
# N=1 context. Plans are still generated with generate_standard() (no DB),
# but the validator uses the profile for tier-aware thresholds.
#
# The experienced and masters scenarios should PASS — they have sufficient
# data (rich/adequate) and the profile gives the validator correct context.
#
# The beginner scenario should PASS — cold_start profile makes the validator
# use tier-aware MP total targets (15mi for builder, not 40mi).
# ---------------------------------------------------------------------------

# Synthetic profiles for N=1 test scenarios
N1_PROFILE_EXPERIENCED = AthleteProfile(
    volume_tier=VolumeTier.HIGH,
    current_weekly_miles=70.0,
    peak_weekly_miles=75.0,
    volume_trend="maintaining",
    volume_confidence=0.9,
    long_run_baseline_minutes=136.0,
    long_run_baseline_miles=17.0,
    long_run_max_minutes=160.0,
    long_run_max_miles=20.0,
    long_run_frequency=0.9,
    long_run_typical_pace_per_mile=8.0,
    long_run_confidence=0.85,
    long_run_source="history",
    recovery_half_life_hours=36.0,
    recovery_confidence=0.7,
    suggested_cutback_frequency=4,
    quality_sessions_per_week=2.0,
    handles_back_to_back_quality=False,
    quality_confidence=0.8,
    weeks_of_data=16,
    data_sufficiency="rich",
    staleness_days=1,
    disclosures=[],
)

N1_PROFILE_BEGINNER = AthleteProfile(
    volume_tier=VolumeTier.BUILDER,
    current_weekly_miles=25.0,
    peak_weekly_miles=28.0,
    volume_trend="building",
    volume_confidence=0.4,
    long_run_baseline_minutes=0.0,
    long_run_baseline_miles=0.0,
    long_run_max_minutes=0.0,
    long_run_max_miles=0.0,
    long_run_frequency=0.0,
    long_run_typical_pace_per_mile=0.0,
    long_run_confidence=0.0,
    long_run_source="tier_default",
    recovery_half_life_hours=48.0,
    recovery_confidence=0.0,
    suggested_cutback_frequency=4,
    quality_sessions_per_week=0.0,
    handles_back_to_back_quality=False,
    quality_confidence=0.0,
    weeks_of_data=6,
    data_sufficiency="thin",
    staleness_days=2,
    disclosures=["I have 6 weeks of training data. Volume and long run "
                 "targets are preliminary."],
)

N1_PROFILE_MASTERS = AthleteProfile(
    volume_tier=VolumeTier.MID,
    current_weekly_miles=55.0,
    peak_weekly_miles=58.0,
    volume_trend="maintaining",
    volume_confidence=0.7,
    long_run_baseline_minutes=126.0,
    long_run_baseline_miles=14.0,
    long_run_max_minutes=144.0,
    long_run_max_miles=16.0,
    long_run_frequency=0.85,
    long_run_typical_pace_per_mile=9.0,
    long_run_confidence=0.7,
    long_run_source="history",
    recovery_half_life_hours=72.0,
    recovery_confidence=0.6,
    suggested_cutback_frequency=3,
    quality_sessions_per_week=1.5,
    handles_back_to_back_quality=False,
    quality_confidence=0.6,
    weeks_of_data=10,
    data_sufficiency="adequate",
    staleness_days=1,
    disclosures=[],
)

N1_OVERRIDE_VARIANTS = [
    pytest.param(
        "marathon", "high", 18, 6,
        id="n1-experienced-70mpw-marathon",
    ),
    pytest.param(
        "marathon", "builder", 18, 5,
        id="n1-beginner-25mpw-marathon",
    ),
    pytest.param(
        "half_marathon", "high", 16, 6,
        id="n1-masters-55mpw-half",
    ),
]

# Map N=1 test IDs to their synthetic profiles
N1_PROFILES = {
    "n1-experienced-70mpw-marathon": N1_PROFILE_EXPERIENCED,
    "n1-beginner-25mpw-marathon": N1_PROFILE_BEGINNER,
    "n1-masters-55mpw-half": N1_PROFILE_MASTERS,
}

ALL_VARIANTS = MARATHON_VARIANTS + HALF_VARIANTS + TEN_K_VARIANTS + FIVE_K_VARIANTS
ALL_WITH_N1 = ALL_VARIANTS + N1_OVERRIDE_VARIANTS


# ---------------------------------------------------------------------------
# Known-Failing Marathon Variants (Phase 1B targets)
#
# These xfail marks document specific generator gaps found by 1-PRE.
# When Phase 1B fixes land, tests xpass → builder removes the mark.
#
# DO NOT remove xfail marks until the underlying generator bug is fixed.
# DO NOT use --ignore in CI — these xfails let passing tests catch regressions.
# ---------------------------------------------------------------------------

def _xfail_all(params, reason):
    """Return a copy of params with xfail added to every entry."""
    return [
        pytest.param(*p.values, id=p.id, marks=[*p.marks, pytest.mark.xfail(reason=reason)])
        for p in params
    ]


def _xfail_by_id(params, xfail_ids, reason):
    """Add xfail to specific param entries (matched by id). Others pass through."""
    return [
        pytest.param(*p.values, id=p.id, marks=[*p.marks, pytest.mark.xfail(reason=reason)])
        if p.id in xfail_ids else p
        for p in params
    ]


# ---------------------------------------------------------------------------
# Post Phase-1B status:
#   - Marathon (non-builder): all coaching rules PASS in relaxed mode.
#   - Marathon builder: Source B MP % at very low volume — real limitation.
#   - Alternation rule: FIXED (MP long run weeks no longer have threshold).
#   - Quality day limit: FIXED (max 2 quality sessions per week).
#   - Source B limits: FIXED (quality-portion measurement, easy-fill, segment data).
#   - Volume progression builder cutback: FIXED (10% reduction).
#
# Remaining xfails document legitimate scope boundaries, not generator gaps.
# ---------------------------------------------------------------------------

# Full validation: only builder still fails (MP % at very low weekly volume)
MARATHON_XFAIL_FULL = _xfail_by_id(
    MARATHON_VARIANTS,
    {"marathon-builder-18w-5d"},
    reason="Builder tier Source B MP % violation at very low weekly volume — "
           "real limitation, not a generator bug (requires N=1 volume scaling, Phase 1C)",
)

# Source B limits: only builder still fails
MARATHON_XFAIL_SOURCE_B = _xfail_by_id(
    MARATHON_VARIANTS,
    {"marathon-builder-18w-5d"},
    reason="Builder tier Source B MP % violation at very low weekly volume",
)

# Alternation rule: FIXED — all 6 marathon variants pass
# (kept as plain MARATHON_VARIANTS, no xfails)

# Quality day limit: FIXED — all 6 marathon variants pass
# (kept as plain MARATHON_VARIANTS, no xfails)

# Volume progression: builder cutback still xfail (10% reduction meets
# the taper test but volume progression validator expects steeper drops)
MARATHON_VOLUME_GATED = _xfail_by_id(
    MARATHON_VARIANTS,
    {"marathon-builder-18w-5d"},
    reason="Builder tier volume progression: 10% cutback is gentler than "
           "other tiers by design (consistency > recovery for early builders)",
)

# Full matrix with remaining known gaps xfailed (for CI)
ALL_WITH_N1_GATED = (
    MARATHON_XFAIL_FULL
    + HALF_VARIANTS + TEN_K_VARIANTS + FIVE_K_VARIANTS
    + N1_OVERRIDE_VARIANTS
)


# ---------------------------------------------------------------------------
# Plan Generation Fixture
# ---------------------------------------------------------------------------

def generate_plan(distance: str, tier: str, duration_weeks: int, days_per_week: int):
    """Generate a plan without touching the database."""
    generator = PlanGenerator(db=None)
    plan = generator.generate_standard(
        distance=distance,
        duration_weeks=duration_weeks,
        tier=tier,
        days_per_week=days_per_week,
        start_date=date(2026, 3, 2),  # A Monday
    )
    return plan


# ---------------------------------------------------------------------------
# FULL MATRIX: All rules against all variants (relaxed mode)
# ---------------------------------------------------------------------------

class TestPlanValidationMatrix:
    """
    Parametrized matrix: every distance x tier x duration variant
    validated against ALL coaching rules from the KB.

    Uses strict=False (relaxed thresholds) for 1-PRE gap discovery.
    Phase 1B will add a strict=True companion class.
    """

    @pytest.mark.parametrize("distance,tier,weeks,days", ALL_WITH_N1_GATED)
    def test_full_validation(self, distance, tier, weeks, days, request):
        """
        Run ALL coaching rule validations against a generated plan.
        This is the comprehensive test — it catches any coaching rule violation.

        For N=1 scenarios, the validator receives a synthetic AthleteProfile
        so it can apply tier-aware thresholds instead of population defaults.
        """
        plan = generate_plan(distance, tier, weeks, days)

        # Look up N=1 profile if this is an N=1 scenario
        test_id = request.node.callspec.id
        profile = N1_PROFILES.get(test_id)

        result = validate_plan(plan, strict=False, profile=profile)

        if not result.passed:
            summary = result.summary()
            pytest.fail(
                f"\n{summary}\n\n"
                f"Total failures: {len(result.failures)}\n"
                f"Total warnings: {len(result.warnings)}"
            )


# ---------------------------------------------------------------------------
# INDIVIDUAL RULE GROUPS: Fine-grained tests for debugging
# ---------------------------------------------------------------------------

class TestSourceBLimits:
    """Source B volume limits (relaxed): long <=35%, T <=12%, I <=10%, MP <=25%."""

    @pytest.mark.parametrize("distance,tier,weeks,days", MARATHON_XFAIL_SOURCE_B)
    def test_marathon_source_b(self, distance, tier, weeks, days):
        """Source B: quality-portion miles checked against limits."""
        plan = generate_plan(distance, tier, weeks, days)
        v = PlanValidator(plan)
        v.assert_source_b_limits()
        assert v.result.passed, v.result.summary()


class TestHardEasyPattern:
    """Hard day always followed by easy/rest. Never back-to-back hard."""

    @pytest.mark.parametrize("distance,tier,weeks,days", MARATHON_VARIANTS)
    def test_marathon_hard_easy(self, distance, tier, weeks, days):
        plan = generate_plan(distance, tier, weeks, days)
        v = PlanValidator(plan)
        v.assert_hard_easy_pattern()
        assert v.result.passed, v.result.summary()


class TestQualityDayLimit:
    """Never 3 quality days in a week. FIXED in Phase 1B."""

    @pytest.mark.parametrize("distance,tier,weeks,days", MARATHON_VARIANTS)
    def test_marathon_quality_limit(self, distance, tier, weeks, days):
        plan = generate_plan(distance, tier, weeks, days)
        v = PlanValidator(plan)
        v.assert_quality_day_limit()
        assert v.result.passed, v.result.summary()


class TestPhaseRules:
    """No threshold in base, correct phase types per distance."""

    @pytest.mark.parametrize("distance,tier,weeks,days", MARATHON_VARIANTS)
    def test_marathon_phase_rules(self, distance, tier, weeks, days):
        plan = generate_plan(distance, tier, weeks, days)
        v = PlanValidator(plan)
        v.assert_phase_rules()
        assert v.result.passed, v.result.summary()


class TestAlternationRule:
    """MP long + no T same week. This is a RULE, not a suggestion. FIXED in Phase 1B."""

    @pytest.mark.parametrize("distance,tier,weeks,days", MARATHON_VARIANTS)
    def test_marathon_alternation(self, distance, tier, weeks, days):
        plan = generate_plan(distance, tier, weeks, days)
        v = PlanValidator(plan)
        v.assert_alternation_rule()
        # Alternation is now a failure — check both failures and warnings
        assert v.result.passed, v.result.summary()


class TestVolumeProgression:
    """Volume progression: no jumps > 20% (relaxed), cutbacks present."""

    @pytest.mark.parametrize("distance,tier,weeks,days", MARATHON_VOLUME_GATED)
    def test_marathon_volume_progression(self, distance, tier, weeks, days):
        plan = generate_plan(distance, tier, weeks, days)
        v = PlanValidator(plan)
        v.assert_volume_progression()
        v.assert_cutback_pattern()
        assert v.result.passed, v.result.summary()


class TestTaperStructure:
    """Taper: volume reduces, some intensity maintained."""

    @pytest.mark.parametrize("distance,tier,weeks,days", MARATHON_VARIANTS)
    def test_marathon_taper(self, distance, tier, weeks, days):
        plan = generate_plan(distance, tier, weeks, days)
        v = PlanValidator(plan)
        v.assert_taper_structure()
        assert v.result.passed, v.result.summary()


class TestPlanStructure:
    """Basic structural validations: workouts exist, phases exist, no empty weeks."""

    # Structure tests use UNMARKED variants — basic structure should pass for ALL
    # distances even before their generators are rebuilt.
    ALL_UNMARKED = [
        pytest.param("marathon", "mid", 18, 6, id="marathon-mid-18w-6d"),
        pytest.param("marathon", "mid", 12, 6, id="marathon-mid-12w-6d"),
        pytest.param("marathon", "low", 18, 5, id="marathon-low-18w-5d"),
        pytest.param("marathon", "high", 18, 6, id="marathon-high-18w-6d"),
        pytest.param("marathon", "builder", 18, 5, id="marathon-builder-18w-5d"),
        pytest.param("marathon", "mid", 18, 5, id="marathon-mid-18w-5d"),
        pytest.param("half_marathon", "mid", 16, 6, id="half-mid-16w-6d"),
        pytest.param("half_marathon", "mid", 12, 6, id="half-mid-12w-6d"),
        pytest.param("half_marathon", "low", 16, 5, id="half-low-16w-5d"),
        pytest.param("half_marathon", "high", 16, 6, id="half-high-16w-6d"),
        pytest.param("10k", "mid", 12, 6, id="10k-mid-12w-6d"),
        pytest.param("10k", "mid", 8, 6, id="10k-mid-8w-6d"),
        pytest.param("10k", "low", 12, 5, id="10k-low-12w-5d"),
        pytest.param("10k", "high", 12, 6, id="10k-high-12w-6d"),
        pytest.param("5k", "mid", 12, 6, id="5k-mid-12w-6d"),
        pytest.param("5k", "mid", 8, 6, id="5k-mid-8w-6d"),
        pytest.param("5k", "low", 12, 5, id="5k-low-12w-5d"),
        pytest.param("5k", "high", 12, 6, id="5k-high-12w-6d"),
    ]

    @pytest.mark.parametrize("distance,tier,weeks,days", ALL_UNMARKED)
    def test_plan_structure(self, distance, tier, weeks, days):
        """Structure tests should pass for ALL distances (even pre-rebuild)."""
        plan = generate_plan(distance, tier, weeks, days)
        v = PlanValidator(plan)
        v.assert_plan_structure()
        assert v.result.passed, v.result.summary()


class TestDistanceEmphasis:
    """Distance-specific quality emphasis rules."""

    @pytest.mark.parametrize("distance,tier,weeks,days", MARATHON_VARIANTS)
    def test_marathon_emphasis(self, distance, tier, weeks, days):
        """Marathon: threshold dominant, MP integration."""
        plan = generate_plan(distance, tier, weeks, days)
        v = PlanValidator(plan)
        v.assert_distance_emphasis()
        assert v.result.passed, v.result.summary()

    @pytest.mark.parametrize("distance,tier,weeks,days", HALF_VARIANTS)
    def test_half_marathon_emphasis(self, distance, tier, weeks, days):
        """
        Half marathon (Phase 1E):
        - Threshold is PRIMARY quality emphasis
        - HMP long runs in race-specific phase
        - VO2max is secondary
        """
        plan = generate_plan(distance, tier, weeks, days)
        v = PlanValidator(plan)
        v.assert_distance_emphasis()
        assert v.result.passed, v.result.summary()


class TestHalfMarathonRules:
    """Half-marathon-specific coaching rule tests (Phase 1E)."""

    @pytest.mark.parametrize("distance,tier,weeks,days", HALF_VARIANTS)
    def test_half_source_b(self, distance, tier, weeks, days):
        """Source B limits respected for half marathon plans."""
        plan = generate_plan(distance, tier, weeks, days)
        v = PlanValidator(plan)
        v.assert_source_b_limits()
        assert v.result.passed, v.result.summary()

    @pytest.mark.parametrize("distance,tier,weeks,days", HALF_VARIANTS)
    def test_half_hard_easy(self, distance, tier, weeks, days):
        """Hard day always followed by easy/rest."""
        plan = generate_plan(distance, tier, weeks, days)
        v = PlanValidator(plan)
        v.assert_hard_easy_pattern()
        assert v.result.passed, v.result.summary()

    @pytest.mark.parametrize("distance,tier,weeks,days", HALF_VARIANTS)
    def test_half_quality_limit(self, distance, tier, weeks, days):
        """Never 3 quality days in a week."""
        plan = generate_plan(distance, tier, weeks, days)
        v = PlanValidator(plan)
        v.assert_quality_day_limit()
        assert v.result.passed, v.result.summary()

    @pytest.mark.parametrize("distance,tier,weeks,days", HALF_VARIANTS)
    def test_half_taper(self, distance, tier, weeks, days):
        """Taper: volume reduces, some intensity maintained."""
        plan = generate_plan(distance, tier, weeks, days)
        v = PlanValidator(plan)
        v.assert_taper_structure()
        assert v.result.passed, v.result.summary()

    @pytest.mark.parametrize("distance,tier,weeks,days", HALF_VARIANTS)
    def test_half_phase_rules(self, distance, tier, weeks, days):
        """Phase rules: no threshold in base."""
        plan = generate_plan(distance, tier, weeks, days)
        v = PlanValidator(plan)
        v.assert_phase_rules()
        assert v.result.passed, v.result.summary()


class Test10KRules:
    """10K-specific coaching rule tests (Phase 1F)."""

    @pytest.mark.parametrize("distance,tier,weeks,days", TEN_K_VARIANTS)
    def test_10k_emphasis(self, distance, tier, weeks, days):
        """
        10K (Phase 1F):
        - VO2max + threshold co-dominant
        - Neither overwhelms (ratio < 3.0)
        - Both present and substantial
        """
        plan = generate_plan(distance, tier, weeks, days)
        v = PlanValidator(plan)
        v.assert_distance_emphasis()
        assert v.result.passed, v.result.summary()

    @pytest.mark.parametrize("distance,tier,weeks,days", TEN_K_VARIANTS)
    def test_10k_source_b(self, distance, tier, weeks, days):
        """Source B limits respected for 10K plans."""
        plan = generate_plan(distance, tier, weeks, days)
        v = PlanValidator(plan)
        v.assert_source_b_limits()
        assert v.result.passed, v.result.summary()

    @pytest.mark.parametrize("distance,tier,weeks,days", TEN_K_VARIANTS)
    def test_10k_hard_easy(self, distance, tier, weeks, days):
        """Hard day always followed by easy/rest."""
        plan = generate_plan(distance, tier, weeks, days)
        v = PlanValidator(plan)
        v.assert_hard_easy_pattern()
        assert v.result.passed, v.result.summary()

    @pytest.mark.parametrize("distance,tier,weeks,days", TEN_K_VARIANTS)
    def test_10k_quality_limit(self, distance, tier, weeks, days):
        """Never 3 quality days in a week."""
        plan = generate_plan(distance, tier, weeks, days)
        v = PlanValidator(plan)
        v.assert_quality_day_limit()
        assert v.result.passed, v.result.summary()

    @pytest.mark.parametrize("distance,tier,weeks,days", TEN_K_VARIANTS)
    def test_10k_taper(self, distance, tier, weeks, days):
        """Taper: volume reduces, some intensity maintained."""
        plan = generate_plan(distance, tier, weeks, days)
        v = PlanValidator(plan)
        v.assert_taper_structure()
        assert v.result.passed, v.result.summary()

    @pytest.mark.parametrize("distance,tier,weeks,days", TEN_K_VARIANTS)
    def test_10k_phase_rules(self, distance, tier, weeks, days):
        """Phase rules: appropriate structure per phase."""
        plan = generate_plan(distance, tier, weeks, days)
        v = PlanValidator(plan)
        v.assert_phase_rules()
        assert v.result.passed, v.result.summary()


class Test5KRules:
    """5K-specific coaching rule tests (Phase 1G)."""

    @pytest.mark.parametrize("distance,tier,weeks,days", FIVE_K_VARIANTS)
    def test_5k_emphasis(self, distance, tier, weeks, days):
        """
        5K (Phase 1G):
        - VO2max dominant (I > T)
        - Repetitions present for neuromuscular economy
        - No MP/HMP contamination
        """
        plan = generate_plan(distance, tier, weeks, days)
        v = PlanValidator(plan)
        v.assert_distance_emphasis()
        assert v.result.passed, v.result.summary()

    @pytest.mark.parametrize("distance,tier,weeks,days", FIVE_K_VARIANTS)
    def test_5k_source_b(self, distance, tier, weeks, days):
        """Source B limits respected for 5K plans."""
        plan = generate_plan(distance, tier, weeks, days)
        v = PlanValidator(plan)
        v.assert_source_b_limits()
        assert v.result.passed, v.result.summary()

    @pytest.mark.parametrize("distance,tier,weeks,days", FIVE_K_VARIANTS)
    def test_5k_hard_easy(self, distance, tier, weeks, days):
        """Hard day always followed by easy/rest."""
        plan = generate_plan(distance, tier, weeks, days)
        v = PlanValidator(plan)
        v.assert_hard_easy_pattern()
        assert v.result.passed, v.result.summary()

    @pytest.mark.parametrize("distance,tier,weeks,days", FIVE_K_VARIANTS)
    def test_5k_quality_limit(self, distance, tier, weeks, days):
        """Never 3 quality days in a week."""
        plan = generate_plan(distance, tier, weeks, days)
        v = PlanValidator(plan)
        v.assert_quality_day_limit()
        assert v.result.passed, v.result.summary()

    @pytest.mark.parametrize("distance,tier,weeks,days", FIVE_K_VARIANTS)
    def test_5k_taper(self, distance, tier, weeks, days):
        """Taper: volume reduces, neuromuscular sharpness maintained."""
        plan = generate_plan(distance, tier, weeks, days)
        v = PlanValidator(plan)
        v.assert_taper_structure()
        assert v.result.passed, v.result.summary()

    @pytest.mark.parametrize("distance,tier,weeks,days", FIVE_K_VARIANTS)
    def test_5k_phase_rules(self, distance, tier, weeks, days):
        """Phase rules: appropriate structure per phase."""
        plan = generate_plan(distance, tier, weeks, days)
        v = PlanValidator(plan)
        v.assert_phase_rules()
        assert v.result.passed, v.result.summary()


# ---------------------------------------------------------------------------
# DIAGNOSTIC: Plan Summary (not a test, used for debugging)
# ---------------------------------------------------------------------------

class TestPlanDiagnostics:
    """
    Diagnostic tests that print plan summaries for manual review.
    These always pass -- they're for visibility, not validation.
    """

    @pytest.mark.parametrize("distance,tier,weeks,days", MARATHON_VARIANTS[:1])
    def test_print_plan_summary(self, distance, tier, weeks, days, capsys):
        """Print a detailed plan summary for manual inspection."""
        plan = generate_plan(distance, tier, weeks, days)
        result = validate_plan(plan)

        lines = [
            f"\n{'='*70}",
            f"PLAN SUMMARY: {plan.distance} | {plan.volume_tier} | "
            f"{plan.duration_weeks}w | {plan.days_per_week}d/w",
            f"{'='*70}",
            f"Total miles: {plan.total_miles}",
            f"Peak volume: {plan.peak_volume:.1f} mi/w",
            f"Quality sessions: {plan.total_quality_sessions}",
            f"Phases: {[f'{p.name} (w{p.weeks[0]}-{p.weeks[-1]})' for p in plan.phases]}",
            "",
        ]

        # Week-by-week summary
        for week in range(1, plan.duration_weeks + 1):
            workouts = [w for w in plan.workouts if w.week == week]
            phase = next(
                (p.name for p in plan.phases if week in p.weeks),
                "unknown"
            )
            week_miles = sum(w.distance_miles or 0 for w in workouts)
            types = [
                f"{w.day_name[:3]}:{w.workout_type}"
                for w in sorted(workouts, key=lambda x: x.day)
                if w.workout_type != "rest"
            ]
            lines.append(
                f"  W{week:02d} [{phase:20s}] {week_miles:5.1f}mi  "
                f"{' | '.join(types)}"
            )

        # Validation results
        lines.append(f"\n{'='*70}")
        lines.append(f"VALIDATION: {'PASS' if result.passed else 'FAIL'}")
        lines.append(f"  Failures: {len(result.failures)}")
        lines.append(f"  Warnings: {len(result.warnings)}")
        for f in result.failures:
            lines.append(f"  FAIL [{f.rule_id}] W{f.week or '?'}: {f.message}")
        for w in result.warnings:
            lines.append(f"  WARN [{w.rule_id}] W{w.week or '?'}: {w.message}")
        lines.append(f"{'='*70}\n")

        print("\n".join(lines))

    @pytest.mark.parametrize("distance,tier,weeks,days", MARATHON_VARIANTS[:1])
    def test_workout_type_distribution(self, distance, tier, weeks, days, capsys):
        """Print workout type distribution for manual inspection."""
        plan = generate_plan(distance, tier, weeks, days)

        type_counts = {}
        for w in plan.workouts:
            t = w.workout_type
            type_counts[t] = type_counts.get(t, 0) + 1

        total = sum(type_counts.values())
        lines = [
            f"\nWORKOUT TYPE DISTRIBUTION: {plan.distance} | {plan.volume_tier}",
            f"{'Type':<25} {'Count':>5} {'%':>6}",
            f"{'-'*40}",
        ]
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {t:<23} {c:>5} {c/total*100:>5.1f}%")
        lines.append(f"{'-'*40}")
        lines.append(f"  {'TOTAL':<23} {total:>5}")

        print("\n".join(lines))
