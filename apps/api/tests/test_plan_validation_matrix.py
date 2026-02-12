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

# Half marathon variants — xfail until 1E delivers
HALF_VARIANTS = [
    pytest.param(
        "half_marathon", "mid", 16, 6,
        id="half-mid-16w-6d",
        marks=pytest.mark.xfail(reason="Half marathon generator not yet rebuilt (Phase 1E)")
    ),
    pytest.param(
        "half_marathon", "mid", 12, 6,
        id="half-mid-12w-6d",
        marks=pytest.mark.xfail(reason="Half marathon generator not yet rebuilt (Phase 1E)")
    ),
    pytest.param(
        "half_marathon", "low", 16, 5,
        id="half-low-16w-5d",
        marks=pytest.mark.xfail(reason="Half marathon generator not yet rebuilt (Phase 1E)")
    ),
    pytest.param(
        "half_marathon", "high", 16, 6,
        id="half-high-16w-6d",
        marks=pytest.mark.xfail(reason="Half marathon generator not yet rebuilt (Phase 1E)")
    ),
]

# 10K variants — xfail until 1F delivers
TEN_K_VARIANTS = [
    pytest.param(
        "10k", "mid", 12, 6,
        id="10k-mid-12w-6d",
        marks=pytest.mark.xfail(reason="10K generator not yet rebuilt (Phase 1F)")
    ),
    pytest.param(
        "10k", "mid", 8, 6,
        id="10k-mid-8w-6d",
        marks=pytest.mark.xfail(reason="10K generator not yet rebuilt (Phase 1F)")
    ),
    pytest.param(
        "10k", "low", 12, 5,
        id="10k-low-12w-5d",
        marks=pytest.mark.xfail(reason="10K generator not yet rebuilt (Phase 1F)")
    ),
    pytest.param(
        "10k", "high", 12, 6,
        id="10k-high-12w-6d",
        marks=pytest.mark.xfail(reason="10K generator not yet rebuilt (Phase 1F)")
    ),
]

# 5K variants — xfail until 1G delivers
FIVE_K_VARIANTS = [
    pytest.param(
        "5k", "mid", 12, 6,
        id="5k-mid-12w-6d",
        marks=pytest.mark.xfail(reason="5K generator not yet rebuilt (Phase 1G)")
    ),
    pytest.param(
        "5k", "mid", 8, 6,
        id="5k-mid-8w-6d",
        marks=pytest.mark.xfail(reason="5K generator not yet rebuilt (Phase 1G)")
    ),
    pytest.param(
        "5k", "low", 12, 5,
        id="5k-low-12w-5d",
        marks=pytest.mark.xfail(reason="5K generator not yet rebuilt (Phase 1G)")
    ),
    pytest.param(
        "5k", "high", 12, 6,
        id="5k-high-12w-6d",
        marks=pytest.mark.xfail(reason="5K generator not yet rebuilt (Phase 1G)")
    ),
]

# N=1 override scenarios — xfail until 1C (athlete_plan_profile.py) delivers.
# These exercise personalization paths that require the N=1 override service.
# generate_standard() with db=None can't exercise these paths, but the
# scenarios document the contract and will be wired up in 1C.
N1_OVERRIDE_VARIANTS = [
    pytest.param(
        "marathon", "high", 18, 6,
        id="n1-experienced-70mpw-marathon",
        marks=pytest.mark.xfail(
            reason="N=1 override requires athlete_plan_profile.py (Phase 1C). "
                   "Scenario: experienced 70mpw athlete, proven 22mi long runs, "
                   "should get longer long runs and VO2 touches in base."
        )
    ),
    pytest.param(
        "marathon", "builder", 18, 5,
        id="n1-beginner-25mpw-marathon",
        marks=pytest.mark.xfail(
            reason="N=1 override requires athlete_plan_profile.py (Phase 1C). "
                   "Scenario: beginner at 25mpw, no race history, should get "
                   "conservative long run caps and extended base phase."
        )
    ),
    pytest.param(
        "half_marathon", "high", 16, 6,
        id="n1-masters-55mpw-half",
        marks=pytest.mark.xfail(
            reason="N=1 override requires athlete_plan_profile.py (Phase 1C). "
                   "Scenario: masters 55+ athlete, proven HM history, should get "
                   "every-3rd-week cutbacks and extra strides/hills."
        )
    ),
]

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


# Full validation: all 6 marathon variants fail (multiple rule violations)
MARATHON_XFAIL_FULL = _xfail_all(
    MARATHON_VARIANTS,
    reason="Multiple coaching rule violations in relaxed mode: "
           "Source B limits, alternation rule, quality day limit (Phase 1B)",
)

# Source B limits: all 6 fail — T at 14-16% (limit 10%), MP exceeds volume %, easy too low
MARATHON_XFAIL_SOURCE_B = _xfail_all(
    MARATHON_VARIANTS,
    reason="Source B volume limits: T sessions at 14-16% (limit 10%), "
           "MP exceeds volume %, easy distribution too low (Phase 1B)",
)

# Alternation rule: all 6 fail — MP long run weeks still contain threshold sessions
MARATHON_XFAIL_ALTERNATION = _xfail_all(
    MARATHON_VARIANTS,
    reason="Alternation rule: MP long run weeks still contain threshold sessions (Phase 1B)",
)

# Quality day limit: 3 of 6 fail (6-day variants where secondary quality creates 3 quality days)
MARATHON_QUALITY_GATED = _xfail_by_id(
    MARATHON_VARIANTS,
    {"marathon-mid-18w-6d", "marathon-mid-12w-6d", "marathon-high-18w-6d"},
    reason="3 quality sessions in 6-day week — secondary quality converts "
           "medium_long to threshold (Phase 1B)",
)

# Volume progression: 1 of 6 fails (builder tier cutback timing)
MARATHON_VOLUME_GATED = _xfail_by_id(
    MARATHON_VARIANTS,
    {"marathon-builder-18w-5d"},
    reason="Builder tier cutback pattern timing gap (Phase 1B)",
)

# Full matrix with all known gaps xfailed (for CI)
ALL_WITH_N1_GATED = (
    MARATHON_XFAIL_FULL + HALF_VARIANTS + TEN_K_VARIANTS
    + FIVE_K_VARIANTS + N1_OVERRIDE_VARIANTS
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
    def test_full_validation(self, distance, tier, weeks, days):
        """
        Run ALL coaching rule validations against a generated plan.
        This is the comprehensive test — it catches any coaching rule violation.
        """
        plan = generate_plan(distance, tier, weeks, days)
        result = validate_plan(plan, strict=False)

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
    """Never 3 quality days in a week."""

    @pytest.mark.parametrize("distance,tier,weeks,days", MARATHON_QUALITY_GATED)
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
    """MP long + no T same week. This is a RULE, not a suggestion."""

    @pytest.mark.parametrize("distance,tier,weeks,days", MARATHON_XFAIL_ALTERNATION)
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
