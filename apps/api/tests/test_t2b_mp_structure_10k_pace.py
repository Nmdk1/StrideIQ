"""
T2-3, T2-5, T2-6 acceptance tests.

T2-3: MP in medium-long — MPProgressionPlanner builds correct alternating sequence;
      ≥ 35 total MP miles before taper; ≥ 2 medium_long_mp weeks in 18-week marathon plan.
T2-5: Phase-aware structure variants — Structure B weeks (MP long) have easy medium-long,
      not medium-long; secondary quality gate lowered for race-specific phases.
T2-6: 10K race-specific intervals use 5K_pace, not 10K_pace.
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.plan_framework.mp_progression import MPProgressionPlanner
from services.plan_framework.phase_builder import PhaseBuilder
from services.plan_framework.generator import PlanGenerator


# ---------------------------------------------------------------------------
# T2-3: MPProgressionPlanner — sequence structure and MP mile tracking
# ---------------------------------------------------------------------------

class TestT2MPProgressionPlanner:
    """
    Acceptance: MPProgressionPlanner produces correct alternating structure;
    18-week marathon plan has ≥35 total MP miles before taper;
    ≥ 2 weeks have medium_long_mp (MP in medium-long).
    """

    def test_planner_alternates_structure_a_and_b(self):
        """Odd weeks are Structure A (easy long); even weeks are Structure B (long_mp).
        Per PLAN_GENERATION_FRAMEWORK.md: first MP week introduces threshold quality
        with an easy long (Structure A), second week puts MP in the long run (Structure B).
        """
        planner = MPProgressionPlanner()
        seq = planner.build_sequence("mid", 8)
        for mw in seq:
            if mw.week_in_phase % 2 == 1:
                assert mw.long_type == "long", (
                    f"Week_in_phase {mw.week_in_phase} (odd) should be Structure A (easy long). "
                    f"Got {mw.long_type}"
                )
            else:
                assert mw.long_type == "long_mp", (
                    f"Week_in_phase {mw.week_in_phase} (even) should be Structure B (long_mp). "
                    f"Got {mw.long_type}"
                )

    def test_structure_b_has_easy_medium_long(self):
        """On Structure B (MP long) weeks, medium-long slot must be 'easy' (recovery)."""
        planner = MPProgressionPlanner()
        seq = planner.build_sequence("mid", 8)
        for mw in seq:
            if mw.long_type == "long_mp":
                assert mw.medium_long_type == "easy", (
                    f"Structure B week {mw.week_in_phase}: medium_long_type should be 'easy' "
                    f"(recovery from MP long). Got '{mw.medium_long_type}'"
                )

    def test_second_half_structure_a_weeks_get_mp_medium_long(self):
        """Structure A weeks in the second half of the block should have medium_long_mp."""
        planner = MPProgressionPlanner()
        seq = planner.build_sequence("mid", 8)
        # Second half starts at week 4 (ml_mp_start = max(2, 8//2) = 4)
        ml_mp_weeks = [mw for mw in seq if mw.medium_long_type == "medium_long_mp"]
        assert len(ml_mp_weeks) >= 2, (
            f"Expected ≥2 medium_long_mp weeks in an 8-week MP block. "
            f"Got {len(ml_mp_weeks)}: {[mw.week_in_phase for mw in ml_mp_weeks]}"
        )

    def test_cumulative_mp_miles_at_least_35_for_mid_tier(self):
        """Mid-tier 8-week MP sequence should produce ≥35 total MP miles."""
        planner = MPProgressionPlanner()
        seq = planner.build_sequence("mid", 8)
        total = planner.cumulative_mp_miles(seq)
        assert total >= 35, (
            f"Mid-tier 8-week MP block should produce ≥35 total MP miles. Got {total:.1f}"
        )

    @pytest.mark.parametrize("tier", ["low", "mid", "high", "elite"])
    def test_all_tiers_produce_positive_mp_miles(self, tier):
        """Every tier should produce at least some MP miles in a 6-week block."""
        planner = MPProgressionPlanner()
        seq = planner.build_sequence(tier, 6)
        total = planner.cumulative_mp_miles(seq)
        assert total > 0, f"Tier '{tier}' produced 0 MP miles in a 6-week block"

    def test_18w_marathon_plan_has_at_least_two_medium_long_mp_weeks(self):
        """18-week mid-tier marathon plan: ≥ 2 weeks with medium_long_mp (MP in medium-long)."""
        gen = PlanGenerator()
        plan = gen.generate_standard(
            distance="marathon",
            duration_weeks=18,
            tier="mid",
            days_per_week=6,
        )
        ml_mp_weeks = [
            w.week for w in plan.workouts if w.workout_type == "medium_long_mp"
        ]
        unique_weeks = set(ml_mp_weeks)
        assert len(unique_weeks) >= 2, (
            f"18w marathon plan should have ≥2 weeks with medium_long_mp. "
            f"Got {len(unique_weeks)} (weeks: {sorted(unique_weeks)})"
        )

    def test_plan_level_cumulative_mp_miles_before_taper(self):
        """
        Should-Address 1: Plan-level (not planner-estimate) cumulative MP-mile check.
        Sum total_distance_miles for all long_mp + medium_long_mp workouts that fall
        before the taper phase in an 18w mid-tier marathon plan. Must be ≥35 miles.
        """
        gen = PlanGenerator()
        plan = gen.generate_standard(
            distance="marathon",
            duration_weeks=18,
            tier="mid",
            days_per_week=6,
        )
        builder = PhaseBuilder()
        phases = builder.build_phases(distance="marathon", duration_weeks=18, tier="mid")

        taper_start = min(
            (w for p in phases if p.phase_type.value == "taper" for w in p.weeks),
            default=19,
        )

        mp_types = {"long_mp", "medium_long_mp", "mp_touch"}
        total_mp_miles = sum(
            w.distance_miles or 0
            for w in plan.workouts
            if w.workout_type in mp_types and w.week < taper_start
        )
        assert total_mp_miles >= 35, (
            f"18w mid-tier marathon plan: cumulative MP workout miles before taper "
            f"should be ≥35. Got {total_mp_miles:.1f}mi "
            f"(taper starts week {taper_start})"
        )

    def test_no_mp_work_in_base_or_threshold_phases(self):
        """MP workout types must not appear in base_speed or threshold phases."""
        gen = PlanGenerator()
        plan = gen.generate_standard(
            distance="marathon",
            duration_weeks=18,
            tier="mid",
            days_per_week=6,
        )
        builder = PhaseBuilder()
        phases = builder.build_phases(distance="marathon", duration_weeks=18, tier="mid")

        mp_types = {"long_mp", "medium_long_mp", "mp_touch"}
        bad_phases = {"base_speed", "threshold"}

        violations = []
        for w in plan.workouts:
            if w.workout_type not in mp_types:
                continue
            phase = builder.get_phase_for_week(phases, w.week)
            if phase.phase_type.value in bad_phases:
                violations.append(
                    f"Week {w.week} ({phase.name}): {w.workout_type} in {phase.phase_type.value}"
                )

        assert not violations, (
            "MP workout(s) appeared in base/threshold phase:\n" + "\n".join(violations)
        )


# ---------------------------------------------------------------------------
# T2-5: Structure B medium-long → easy; lower secondary quality gate
# ---------------------------------------------------------------------------

class TestT2StructureVariantsAndQualityGate:
    """
    Acceptance: On MP-long (Structure B) weeks, medium-long slot is 'easy', not 'medium_long'.
    45mpw 10K athlete in race-specific phase receives 2 quality sessions.
    """

    def test_mp_long_week_has_easy_not_medium_long(self):
        """
        On every week with a long_mp, the medium_long slot must be 'easy' (T2-5 Structure B).
        """
        gen = PlanGenerator()
        plan = gen.generate_standard(
            distance="marathon",
            duration_weeks=18,
            tier="mid",
            days_per_week=6,
        )
        violations = []
        for week_num in range(1, 19):
            week_workouts = [w for w in plan.workouts if w.week == week_num]
            has_mp_long = any(w.workout_type == "long_mp" for w in week_workouts)
            has_medium_long = any(w.workout_type == "medium_long" for w in week_workouts)
            if has_mp_long and has_medium_long:
                violations.append(
                    f"Week {week_num}: has long_mp (Structure B) but also has medium_long. "
                    f"Medium-long slot should be 'easy' on MP-long weeks."
                )

        assert not violations, "\n".join(violations)

    def test_45mpw_10k_race_specific_gets_two_quality_sessions(self):
        """
        T2-5: 10K athlete in race-specific phase must receive 2 hard quality sessions
        per non-cutback week (secondary quality gate lowered to 25mpw for 5K/10K race-specific).
        Pre-T2-5 gate was 55mpw — a 45mpw athlete would have been blocked to only 1.
        """
        gen = PlanGenerator()
        plan = gen.generate_standard(
            distance="10k",
            duration_weeks=12,
            tier="mid",
            days_per_week=6,
        )
        builder = PhaseBuilder()
        phases = builder.build_phases(distance="10k", duration_weeks=12, tier="mid")
        race_specific_phases = [p for p in phases if p.phase_type.value == "race_specific"]

        hard_quality = {"threshold", "threshold_intervals", "intervals", "repetitions"}

        for phase in race_specific_phases:
            non_cutback_weeks = phase.weeks[:-1]  # last week is cutback
            for wk in non_cutback_weeks:
                week_workouts = [w for w in plan.workouts if w.week == wk]
                quality_count = sum(1 for w in week_workouts if w.workout_type in hard_quality)
                assert quality_count >= 2, (
                    f"Week {wk} (10K race_specific): expected ≥2 hard quality sessions "
                    f"(T2-5b lowered gate to 25mpw). "
                    f"Got {quality_count}. Sessions: "
                    f"{[w.workout_type for w in week_workouts]}"
                )


# ---------------------------------------------------------------------------
# T2-6: 10K race-specific intervals use 5K_pace
# ---------------------------------------------------------------------------

class TestT2TenKIntervalPace:
    """
    Acceptance: Race-specific 10K plan intervals are described as '5K effort' / '5K_pace',
    not '10K race pace' / '10K_pace'.
    """

    def test_10k_race_specific_intervals_use_5k_pace_label(self):
        """
        In the race_specific phase of a 10K plan, interval segments must have
        pace_label = '5K_pace', not '10K_pace'.
        """
        from services.plan_framework.workout_scaler import WorkoutScaler
        scaler = WorkoutScaler()

        wo = scaler.scale_workout(
            workout_type="intervals",
            weekly_volume=45.0,
            tier="mid",
            phase="race_specific",
            week_in_phase=1,
            plan_week=11,
            distance="10k",
        )
        # Find the intervals segment and check pace label
        interval_seg = next(
            (s for s in (wo.segments or []) if s.get("type") == "intervals"),
            None,
        )
        assert interval_seg is not None, "No intervals segment found in race_specific 10K workout"
        pace = interval_seg.get("pace", "")
        assert "5k" in pace.lower() or "5K" in pace, (
            f"10K race-specific interval pace should be '5K_pace'. Got '{pace}'"
        )
        assert "10k" not in pace.lower() and "10K" not in pace, (
            f"10K race-specific interval must NOT use 10K pace. Got '{pace}'"
        )

    def test_10k_race_specific_description_mentions_5k_effort(self):
        """Pace description must say '5K effort', not '10K race pace'."""
        from services.plan_framework.workout_scaler import WorkoutScaler
        scaler = WorkoutScaler()

        wo = scaler.scale_workout(
            workout_type="intervals",
            weekly_volume=50.0,
            tier="mid",
            phase="race_specific",
            week_in_phase=1,
            plan_week=11,
            distance="10k",
        )
        assert "5K" in wo.pace_description or "5k" in wo.pace_description, (
            f"Pace description should mention 5K effort. Got: '{wo.pace_description}'"
        )

    def test_10k_early_build_intervals_retain_generic_pace(self):
        """Early 10K build intervals (before race_specific) should NOT be 5K pace."""
        from services.plan_framework.workout_scaler import WorkoutScaler
        scaler = WorkoutScaler()

        wo = scaler.scale_workout(
            workout_type="intervals",
            weekly_volume=40.0,
            tier="mid",
            phase="threshold",
            week_in_phase=1,
            plan_week=3,
            distance="10k",
        )
        interval_seg = next(
            (s for s in (wo.segments or []) if s.get("type") == "intervals"),
            None,
        )
        if interval_seg:
            pace = interval_seg.get("pace", "")
            # Early build intervals should NOT carry 5K_pace label
            assert "5K_pace" not in pace, (
                f"Early 10K build intervals should not use 5K_pace. Got '{pace}'"
            )

    def test_full_10k_plan_race_specific_intervals_have_correct_pace(self):
        """End-to-end: race_specific 10K plan workouts must have '5K' in their description."""
        gen = PlanGenerator()
        plan = gen.generate_standard(
            distance="10k",
            duration_weeks=12,
            tier="mid",
            days_per_week=6,
        )
        builder = PhaseBuilder()
        phases = builder.build_phases(distance="10k", duration_weeks=12, tier="mid")

        race_weeks = {
            w
            for p in phases if p.phase_type.value == "race_specific"
            for w in p.weeks
        }

        interval_workouts_in_race = [
            w for w in plan.workouts
            if w.week in race_weeks and w.workout_type == "intervals"
        ]
        assert interval_workouts_in_race, (
            "No interval workouts found in 10K race_specific phase"
        )

        for w in interval_workouts_in_race:
            segs = w.segments or []
            interval_seg = next((s for s in segs if s.get("type") == "intervals"), None)
            if interval_seg:
                pace = interval_seg.get("pace", "")
                assert "5k_pace" in pace.lower() or "5K_pace" in pace, (
                    f"Week {w.week} interval segment pace should be 5K_pace. Got '{pace}'"
                )
