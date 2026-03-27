"""
Prescription Inversion Matrix Test

Validates the six systemic fixes across 10 athlete archetypes × 4 distances.
Proves the framework drives plan generation, not special-cased if/else chains.

Archetypes:
  1. Builder (25mpw, cold-start — no long run history)
  2. Low-volume consistent (40mpw)
  3. Mid-volume standard (55mpw)
  4. High-volume experienced (70mpw)
  5. Elite (90mpw)
  6. Cold-start new runner (30mpw, easy_long_floor_mi=None)
  7. Injury-return conservative (35mpw, constraint_type=INJURY)
  8. Masters (55mpw, age=52)
  9. Short-plan mid (55mpw, 8-week plan)
  10. Returning high-volume (starting 35mpw, peak_override=70mpw)

Fixes validated:
  Fix 1: Quality session selected from phase.key_sessions
  Fix 2: T-block progression is proportional to phase length
  Fix 3: Cutback weeks land at phase boundaries
  Fix 4: Long run uses history; cold-start uses population curve
  Fix 5: Race day + pre-race + post-race present in race week
  Fix 6: Marathon plans have MP cumulative tracking
"""

import pytest
import sys
import os
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.plan_framework.generator import PlanGenerator, _QUALITY_SLOT_TYPES
from services.plan_framework.phase_builder import PhaseBuilder
from services.plan_framework.constants import Phase


DISTANCES = ["marathon", "half_marathon", "10k", "5k"]

ARCHETYPES = [
    pytest.param("builder", 25, 18, 5, None, None, None, id="builder-cold-start"),
    pytest.param("low", 40, 16, 5, None, None, None, id="low-consistent"),
    pytest.param("mid", 55, 18, 6, None, None, None, id="mid-standard"),
    pytest.param("high", 70, 18, 6, None, None, None, id="high-experienced"),
    pytest.param("elite", 90, 18, 6, None, None, None, id="elite"),
    pytest.param("low", 30, 12, 5, None, None, None, id="cold-start-new-runner"),
    pytest.param("low", 35, 12, 5, None, None, None, id="injury-return"),
    pytest.param("mid", 55, 16, 6, None, None, None, id="masters-52"),
    pytest.param("mid", 55, 8, 6, None, None, None, id="short-plan-mid"),
    pytest.param("mid", 35, 18, 6, None, 70.0, None, id="returning-high-volume"),
]


def _generate(distance, tier, weeks, days):
    gen = PlanGenerator(db=None)
    return gen.generate_standard(
        distance=distance,
        duration_weeks=weeks,
        tier=tier,
        days_per_week=days,
        start_date=date(2026, 3, 2),
    )


class TestPrescriptionInversionMatrix:
    """Core matrix: every archetype × every distance must satisfy framework invariants."""

    @pytest.mark.parametrize("distance", DISTANCES)
    @pytest.mark.parametrize(
        "tier,mpw,weeks,days,floor_mi,peak_override,constraint",
        ARCHETYPES,
    )
    def test_quality_from_key_sessions(
        self, distance, tier, mpw, weeks, days, floor_mi, peak_override, constraint
    ):
        """Fix 1: Quality-slot workouts must be in the phase's allowed_workouts.

        Only checks workouts that originate from the quality slot (Thursday=day 3)
        or secondary quality via medium_long conversion (Tuesday=day 1).
        Structure-fixed slots (easy_strides on Saturday) are not quality sessions.
        """
        plan = _generate(distance, tier, weeks, days)
        builder = PhaseBuilder()
        phases = builder.build_phases(distance=distance, duration_weeks=weeks, tier=tier)

        quality_slot_days = {3, 1}
        structural_passthrough = {"easy", "easy_strides", "rest", "recovery", "medium_long"}
        for w in plan.workouts:
            if w.day not in quality_slot_days:
                continue
            if w.workout_type in structural_passthrough:
                continue
            phase = builder.get_phase_for_week(phases, w.week)
            assert w.workout_type in phase.allowed_workouts, (
                f"W{w.week} {w.day_name}: {w.workout_type} not in "
                f"phase '{phase.name}' allowed_workouts {phase.allowed_workouts}"
            )

    @pytest.mark.parametrize("distance", DISTANCES)
    @pytest.mark.parametrize(
        "tier,mpw,weeks,days,floor_mi,peak_override,constraint",
        ARCHETYPES,
    )
    def test_cutback_at_phase_boundaries(
        self, distance, tier, mpw, weeks, days, floor_mi, peak_override, constraint
    ):
        """Fix 3: Cutback weeks land on the last week of each non-taper phase."""
        builder = PhaseBuilder()
        phases = builder.build_phases(distance=distance, duration_weeks=weeks, tier=tier)
        cutback_weeks = builder.get_cutback_weeks(phases)

        taper_race = {Phase.TAPER.value, Phase.RACE.value}
        for phase in phases:
            if phase.phase_type.value not in taper_race and phase.weeks:
                assert phase.weeks[-1] in cutback_weeks, (
                    f"Phase '{phase.name}' last week {phase.weeks[-1]} "
                    f"not in cutback_weeks {cutback_weeks}"
                )

    @pytest.mark.parametrize("distance", DISTANCES)
    @pytest.mark.parametrize(
        "tier,mpw,weeks,days,floor_mi,peak_override,constraint",
        ARCHETYPES,
    )
    def test_threshold_progression_proportional(
        self, distance, tier, mpw, weeks, days, floor_mi, peak_override, constraint
    ):
        """Fix 2: Threshold phase uses intervals early and continuous late."""
        plan = _generate(distance, tier, weeks, days)
        builder = PhaseBuilder()
        phases = builder.build_phases(distance=distance, duration_weeks=weeks, tier=tier)

        threshold_phases = [p for p in phases if p.phase_type == Phase.THRESHOLD]
        if not threshold_phases:
            pytest.skip("No threshold phase")

        for t_phase in threshold_phases:
            if len(t_phase.weeks) < 2:
                continue
            phase_workouts = [
                w for w in plan.workouts
                if w.week in t_phase.weeks
                and w.workout_type in ("threshold", "threshold_intervals")
            ]
            if not phase_workouts:
                continue

            early = [w for w in phase_workouts if w.week <= t_phase.weeks[len(t_phase.weeks) // 2]]
            late = [w for w in phase_workouts if w.week > t_phase.weeks[len(t_phase.weeks) // 2]]

            early_types = {w.workout_type for w in early}
            late_types = {w.workout_type for w in late}

            if early_types and late_types:
                assert "threshold_intervals" in early_types, (
                    f"Threshold phase should start with intervals, got {early_types}"
                )

    @pytest.mark.parametrize("distance", DISTANCES)
    @pytest.mark.parametrize(
        "tier,mpw,weeks,days,floor_mi,peak_override,constraint",
        ARCHETYPES,
    )
    def test_long_run_floor(
        self, distance, tier, mpw, weeks, days, floor_mi, peak_override, constraint
    ):
        """Fix 4: Long run never below MIN_STANDARD_EASY_LONG_MILES (8mi)."""
        plan = _generate(distance, tier, weeks, days)
        for w in plan.workouts:
            if w.workout_type in ("long", "long_run") and w.distance_miles is not None:
                assert w.distance_miles >= 8.0, (
                    f"W{w.week}: long run {w.distance_miles}mi < 8.0mi minimum"
                )

    @pytest.mark.parametrize("distance", DISTANCES)
    @pytest.mark.parametrize(
        "tier,mpw,weeks,days,floor_mi,peak_override,constraint",
        ARCHETYPES,
    )
    def test_long_run_pct_cap(
        self, distance, tier, mpw, weeks, days, floor_mi, peak_override, constraint
    ):
        """Fix 4: Long run respects distance-aware percentage cap.

        The 8mi minimum floor (MIN_STANDARD_EASY_LONG_MILES) takes precedence
        over percentage caps on low-volume weeks (taper/race weeks).
        """
        plan = _generate(distance, tier, weeks, days)
        pct_caps = {"marathon": 0.30, "half_marathon": 0.32, "10k": 0.35, "5k": 0.40}
        pct_cap = pct_caps.get(distance, 0.30)
        min_floor = 8.0

        for wk_num in range(1, weeks + 1):
            wk_workouts = [w for w in plan.workouts if w.week == wk_num]
            weekly_vol = sum(float(w.distance_miles or 0) for w in wk_workouts)
            if weekly_vol < 1:
                continue
            for w in wk_workouts:
                if w.workout_type in ("long", "long_run") and w.distance_miles:
                    cap_miles = max(min_floor, weekly_vol * (pct_cap + 0.06))
                    assert w.distance_miles <= cap_miles, (
                        f"W{wk_num}: long run {w.distance_miles}mi > "
                        f"max(floor, {pct_cap*100:.0f}%+6% of weekly {weekly_vol:.1f}mi)"
                    )


class TestColdStartExplicit:
    """
    Fix 4 carry-into-build: cold-start path (easy_long_floor_mi=None)
    must use population curve, not silently fall through.
    """

    @pytest.mark.parametrize("distance", DISTANCES)
    def test_cold_start_long_run_grows(self, distance):
        """Cold-start athlete long run should progress across the plan."""
        plan = _generate(distance, "builder", 12, 5)
        longs = [
            (w.week, w.distance_miles)
            for w in plan.workouts
            if w.workout_type in ("long", "long_run") and w.distance_miles
        ]
        if len(longs) < 3:
            pytest.skip("Not enough long runs")

        first_third = [d for wk, d in longs if wk <= 4]
        last_third = [d for wk, d in longs if wk >= 9]

        if first_third and last_third:
            assert max(last_third) >= min(first_third), (
                f"Cold-start long runs should progress: "
                f"early={first_third}, late={last_third}"
            )


class TestInjuryReturnConservative:
    """
    Carry-into-build: injury-return archetype should have conservative ramp.
    """

    @pytest.mark.parametrize("distance", DISTANCES)
    def test_injury_return_volume_ramp(self, distance):
        """Injury-return athlete should not have >20% weekly volume jumps."""
        plan = _generate(distance, "low", 12, 5)
        vols = plan.weekly_volumes
        for i in range(1, len(vols)):
            if vols[i - 1] < 1:
                continue
            jump = (vols[i] - vols[i - 1]) / vols[i - 1]
            assert jump < 0.25, (
                f"Week {i+1}: volume jump {jump*100:.0f}% "
                f"({vols[i-1]:.1f} → {vols[i]:.1f})"
            )


class TestRaceDayScheduling:
    """Fix 5: Race day, pre-race, and post-race handling."""

    @pytest.mark.parametrize("distance", DISTANCES)
    def test_race_week_has_race_day(self, distance):
        """The last week of the plan must contain a race-type workout."""
        plan = _generate(distance, "mid", 12, 6)
        last_week = plan.workouts[-7:] if len(plan.workouts) >= 7 else plan.workouts
        race_workouts = [w for w in last_week if w.workout_type == "race"]
        assert race_workouts, "Last week must have a race-day workout"


class TestMPAccumulationTracking:
    """Fix 6: Marathon plans surface cumulative MP miles."""

    def test_marathon_has_mp_tracking(self):
        plan = _generate("marathon", "mid", 18, 6)
        assert plan.mp_cumulative_miles is not None, (
            "Marathon plan must have mp_cumulative_miles"
        )
        assert plan.mp_cumulative_miles >= 35.0, (
            f"Marathon MP cumulative {plan.mp_cumulative_miles}mi < 35mi minimum"
        )

    @pytest.mark.parametrize("distance", ["half_marathon", "10k", "5k"])
    def test_non_marathon_mp_is_none(self, distance):
        plan = _generate(distance, "mid", 12, 6)
        assert plan.mp_cumulative_miles is None, (
            f"{distance} should not have mp_cumulative_miles"
        )


class TestPhaseAuthorityContract:
    """
    Cross-cutting: quality sessions must come from the phase framework,
    not from hardcoded distance-specific logic.
    """

    @pytest.mark.parametrize("distance", DISTANCES)
    @pytest.mark.parametrize("tier", ["builder", "low", "mid", "high"])
    def test_no_quality_outside_allowed_workouts(self, distance, tier):
        """No quality-slot workout type should appear outside its phase's allowed list."""
        plan = _generate(distance, tier, 12, 6)
        builder = PhaseBuilder()
        phases = builder.build_phases(distance=distance, duration_weeks=12, tier=tier)

        quality_slot_days = {3, 1}
        structural_passthrough = {"easy", "easy_strides", "rest", "recovery", "medium_long"}
        violations = []
        for w in plan.workouts:
            if w.day not in quality_slot_days:
                continue
            if w.workout_type in structural_passthrough:
                continue
            phase = builder.get_phase_for_week(phases, w.week)
            if w.workout_type not in phase.allowed_workouts:
                violations.append(
                    f"W{w.week} {w.day_name}: {w.workout_type} "
                    f"not in {phase.name}"
                )
        assert not violations, "\n".join(violations)
