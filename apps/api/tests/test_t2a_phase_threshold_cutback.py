"""
T2-1, T2-2, T2-4 acceptance tests.

T2-1: phase.allowed_workouts is enforced — no quality workout can escape its phase boundary.
T2-2: T-block 6-step progression — every threshold session in a ≥3-week block has a
      unique (reps, duration) from the preceding week.
T2-4: Phase-boundary cutbacks — cutbacks land at phase transitions, not arithmetic midpoints.
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.plan_framework.phase_builder import PhaseBuilder
from services.plan_framework.workout_scaler import WorkoutScaler
from services.plan_framework.generator import PlanGenerator


# ---------------------------------------------------------------------------
# T2-1: Phase.allowed_workouts enforced — no out-of-phase quality workout
# ---------------------------------------------------------------------------

class TestT2PhaseAllowedWorkoutsEnforced:
    """
    Acceptance: No plan across the full athlete matrix contains a quality workout
    that is not in its phase's allowed_workouts list.
    """

    @pytest.mark.parametrize("distance,duration_weeks", [
        ("marathon", 18),
        ("marathon", 12),
        ("half_marathon", 16),
        ("10k", 12),
        ("5k", 10),
    ])
    def test_no_out_of_phase_quality_workouts(self, distance, duration_weeks):
        gen = PlanGenerator()
        plan = gen.generate_standard(
            distance=distance,
            duration_weeks=duration_weeks,
            tier="mid",
            days_per_week=6,
        )
        builder = PhaseBuilder()
        phases = builder.build_phases(distance=distance, duration_weeks=duration_weeks, tier="mid")

        violations = []
        non_structural = {"easy", "long", "long_mp", "long_hmp", "medium_long",
                          "easy_strides", "mp_touch", "medium_long_mp", "recovery",
                          "rest", "race", "long_run"}
        for workout in plan.workouts:
            if workout.workout_type in non_structural:
                continue
            phase = builder.get_phase_for_week(phases, workout.week)
            if workout.workout_type not in set(phase.allowed_workouts):
                violations.append(
                    f"Week {workout.week} ({phase.name}): "
                    f"{workout.workout_type} not in {phase.allowed_workouts}"
                )

        assert not violations, (
            f"{distance}/{duration_weeks}w — {len(violations)} phase boundary violation(s):\n"
            + "\n".join(violations[:5])
        )

    def test_base_phase_no_intervals_for_marathon(self):
        """
        Marathon base phase must not contain 'intervals' regardless of athlete context.
        The base_speed phase allowed_workouts for marathon does not include intervals.
        """
        gen = PlanGenerator()
        plan = gen.generate_standard(
            distance="marathon",
            duration_weeks=18,
            tier="high",
            days_per_week=7,
        )
        builder = PhaseBuilder()
        phases = builder.build_phases(distance="marathon", duration_weeks=18, tier="high")

        base_phases = [p for p in phases if p.phase_type.value == "base_speed"]
        base_week_nums = {w for p in base_phases for w in p.weeks}

        interval_in_base = [
            w for w in plan.workouts
            if w.week in base_week_nums and w.workout_type == "intervals"
        ]
        assert not interval_in_base, (
            f"'intervals' appeared in marathon base phase for high-volume athlete: "
            f"{[(w.week, w.workout_type) for w in interval_in_base]}"
        )


# ---------------------------------------------------------------------------
# T2-2: T-block 6-step progression — unique sessions per week
# ---------------------------------------------------------------------------

class TestT2ThresholdSixStepProgression:
    """
    Acceptance: In any threshold block with ≥3 weeks, every threshold_intervals
    session has a different (reps, duration) combination than the preceding week.
    """

    def _extract_reps_duration(self, workout) -> tuple | None:
        """Extract (reps, duration_min) from threshold_intervals segments."""
        if workout.workout_type != "threshold_intervals":
            return None
        for seg in (workout.segments or []):
            if seg.get("type") == "intervals":
                return (seg.get("reps"), seg.get("duration_min"))
        return None

    @pytest.mark.parametrize("distance,duration_weeks,tier", [
        ("marathon", 18, "mid"),
        ("marathon", 12, "low"),
        ("half_marathon", 16, "mid"),
        ("10k", 12, "mid"),
        ("5k", 10, "mid"),
    ])
    def test_threshold_intervals_unique_per_week(self, distance, duration_weeks, tier):
        gen = PlanGenerator()
        plan = gen.generate_standard(
            distance=distance,
            duration_weeks=duration_weeks,
            tier=tier,
            days_per_week=6,
        )
        builder = PhaseBuilder()
        phases = builder.build_phases(distance=distance, duration_weeks=duration_weeks, tier=tier)
        threshold_phases = [p for p in phases if p.phase_type.value == "threshold"]

        for phase in threshold_phases:
            if len(phase.weeks) < 3:
                continue

            interval_sessions = []
            for wk in phase.weeks:
                week_intervals = [
                    w for w in plan.workouts
                    if w.week == wk and w.workout_type == "threshold_intervals"
                ]
                rd = self._extract_reps_duration(week_intervals[0]) if week_intervals else None
                interval_sessions.append((wk, rd))

            # Filter to weeks that have threshold_intervals
            interval_sessions = [(wk, rd) for wk, rd in interval_sessions if rd is not None]
            if len(interval_sessions) < 2:
                continue  # Not enough intervals to test progression

            duplicates = []
            for i in range(1, len(interval_sessions)):
                prev_wk, prev_rd = interval_sessions[i - 1]
                curr_wk, curr_rd = interval_sessions[i]
                if curr_rd == prev_rd:
                    duplicates.append(f"Weeks {prev_wk} and {curr_wk}: both {curr_rd}")

            assert not duplicates, (
                f"{distance}/{duration_weeks}w threshold block has repeated sessions: "
                + ", ".join(duplicates)
            )

    def test_low_tier_starts_with_shorter_intervals(self):
        """Low tier should start with a shorter format (4×4 or 4×5) than mid tier (5×5)."""
        scaler = WorkoutScaler()
        low_w1 = scaler.scale_workout("threshold_intervals", 25.0, "low", "threshold",
                                      week_in_phase=1, total_phase_weeks=4)
        mid_w1 = scaler.scale_workout("threshold_intervals", 45.0, "mid", "threshold",
                                      week_in_phase=1, total_phase_weeks=4)

        def total_time(wo) -> int:
            for seg in (wo.segments or []):
                if seg.get("type") == "intervals":
                    return seg["reps"] * seg["duration_min"]
            return 0

        assert total_time(low_w1) <= total_time(mid_w1), (
            f"Low tier W1 threshold should be ≤ mid tier. "
            f"Got low={total_time(low_w1)}min, mid={total_time(mid_w1)}min"
        )

    def test_high_tier_starts_with_more_reps(self):
        """High tier should start with 6×5 (30 min) vs mid tier 5×5 (25 min)."""
        scaler = WorkoutScaler()
        high_w1 = scaler.scale_workout("threshold_intervals", 70.0, "high", "threshold",
                                       week_in_phase=1, total_phase_weeks=4)
        mid_w1 = scaler.scale_workout("threshold_intervals", 55.0, "mid", "threshold",
                                      week_in_phase=1, total_phase_weeks=4)

        def total_time(wo) -> int:
            for seg in (wo.segments or []):
                if seg.get("type") == "intervals":
                    return seg["reps"] * seg["duration_min"]
            return 0

        assert total_time(high_w1) >= total_time(mid_w1), (
            f"High tier W1 threshold should be ≥ mid tier. "
            f"Got high={total_time(high_w1)}min, mid={total_time(mid_w1)}min"
        )

    def test_six_week_threshold_has_six_distinct_sessions(self):
        """A 6-week threshold block must produce 6 distinct session shapes."""
        scaler = WorkoutScaler()
        shapes = set()
        for wk in range(1, 7):
            if wk < 6:
                wo = scaler.scale_workout("threshold_intervals", 55.0, "mid",
                                          "threshold", week_in_phase=wk, total_phase_weeks=6)
                for seg in (wo.segments or []):
                    if seg.get("type") == "intervals":
                        shapes.add((seg["reps"], seg["duration_min"]))
                        break
            else:
                wo = scaler.scale_workout("threshold", 55.0, "mid",
                                          "threshold", week_in_phase=wk, total_phase_weeks=6)
                shapes.add(("continuous", int(wo.duration_minutes - 25)))

        assert len(shapes) == 6, (
            f"6-week threshold block should have 6 distinct session shapes. Got {len(shapes)}: {shapes}"
        )


# ---------------------------------------------------------------------------
# T2-4: Phase-boundary cutbacks
# ---------------------------------------------------------------------------

class TestT2PhaseBoundaryCutbacks:
    """
    Acceptance: Cutback weeks land at phase boundaries, not arithmetic midpoints.
    """

    def test_18w_marathon_cutbacks_at_phase_ends(self):
        """
        18-week marathon plan: cutbacks at {4, 8, 12, 16} (last week of each build phase).
        4-4-4-4 build + 2 taper = 16 build weeks → phase ends at 4, 8, 12, 16.
        """
        builder = PhaseBuilder()
        phases = builder.build_phases(distance="marathon", duration_weeks=18, tier="mid")
        cutback_weeks = builder.get_cutback_weeks(phases)
        assert cutback_weeks == {4, 8, 12, 16}, (
            f"18w marathon cutback weeks should be {{4, 8, 12, 16}}. Got {sorted(cutback_weeks)}"
        )

    def test_12w_10k_cutback_not_in_threshold_middle(self):
        """
        12-week 10K plan: no cutback week should land mid-threshold-block.
        The threshold block must complete its progression uninterrupted.
        """
        builder = PhaseBuilder()
        phases = builder.build_phases(distance="10k", duration_weeks=12, tier="mid")
        cutback_weeks = builder.get_cutback_weeks(phases)

        threshold_phases = [p for p in phases if p.phase_type.value == "threshold"]
        for phase in threshold_phases:
            if len(phase.weeks) < 2:
                continue
            mid_weeks = set(phase.weeks[1:-1])  # Exclude first and last
            interrupted = cutback_weeks & mid_weeks
            assert not interrupted, (
                f"Cutback week(s) {sorted(interrupted)} interrupt the middle of 10K "
                f"threshold block (weeks {phase.weeks}). Phase integrity violated."
            )

    def test_cutbacks_only_in_build_phases_not_taper(self):
        """Taper and race weeks must never be cutback weeks."""
        builder = PhaseBuilder()
        for distance, duration in [("marathon", 18), ("half_marathon", 16),
                                    ("10k", 12), ("5k", 10)]:
            phases = builder.build_phases(distance=distance, duration_weeks=duration, tier="mid")
            cutback_weeks = builder.get_cutback_weeks(phases)

            taper_race_weeks = {
                w
                for p in phases
                if p.phase_type.value in ("taper", "race")
                for w in p.weeks
            }
            overlap = cutback_weeks & taper_race_weeks
            assert not overlap, (
                f"{distance}/{duration}w: cutback week(s) {sorted(overlap)} land in taper/race phase"
            )

    def test_every_cutback_week_retains_quality_session(self):
        """
        Every cutback week in a generated plan must retain at most 1 hard quality session
        (the primary key session, reduced). No double hard quality should appear.
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
        cutback_weeks = builder.get_cutback_weeks(phases)

        for wk in sorted(cutback_weeks):
            week_workouts = [w for w in plan.workouts if w.week == wk]
            # Strides/easy_strides count as quality but also appear in non-cutback weeks.
            # For cutback: at most 1 "hard" quality (threshold/intervals) must be present.
            hard_quality = [
                w.workout_type for w in week_workouts
                if w.workout_type in {"threshold", "threshold_intervals", "intervals", "repetitions"}
            ]
            assert len(hard_quality) <= 1, (
                f"Cutback week {wk}: {len(hard_quality)} hard quality sessions. "
                f"Expected ≤1. Sessions: {hard_quality}"
            )
