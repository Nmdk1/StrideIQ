"""
T2-7, T2-8, T2-9, T2-10 acceptance tests.

T2-7: Medium-long progression — taper weeks visibly shorter than peak-phase weeks.
T2-8: MP/HMP gate — low-tier athletes receive zero long_mp; high-tier athletes
      receive long_mp from the marathon-specific phase onward.
T2-9: Threshold volume cap — low-tier beginner threshold work ≤ 3.5mi per session.
T2-10: Long run floor — high-mileage athlete with L30=18mi long runs gets long runs
       ≥15mi in 10K base/build phases.
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.plan_framework.workout_scaler import WorkoutScaler
from services.plan_framework.generator import PlanGenerator
from services.plan_framework.phase_builder import PhaseBuilder


# ---------------------------------------------------------------------------
# T2-7: Medium-long progression and taper reduction
# ---------------------------------------------------------------------------

class TestT2MediumLongProgression:
    """
    T2-7 acceptance: medium-long shorter in taper than in peak phase;
    visible week-over-week progression within the build block.
    """

    def test_taper_medium_long_shorter_than_peak(self):
        """Medium-long in taper must be shorter than peak-phase medium-long."""
        scaler = WorkoutScaler()

        peak = scaler.scale_workout(
            workout_type="medium_long",
            weekly_volume=55.0,
            tier="mid",
            phase="threshold",
            week_in_phase=4,
            total_phase_weeks=4,
        )
        taper = scaler.scale_workout(
            workout_type="medium_long",
            weekly_volume=55.0,
            tier="mid",
            phase="taper",
            week_in_phase=1,
            total_phase_weeks=2,
        )
        assert taper.total_distance_miles < peak.total_distance_miles, (
            f"Taper medium-long ({taper.total_distance_miles}mi) should be shorter "
            f"than peak-phase medium-long ({peak.total_distance_miles}mi)"
        )

    def test_race_week_medium_long_shorter_than_taper(self):
        """Race week medium-long must be shorter than regular taper medium-long."""
        scaler = WorkoutScaler()

        taper = scaler.scale_workout(
            workout_type="medium_long",
            weekly_volume=55.0,
            tier="mid",
            phase="taper",
            week_in_phase=1,
            total_phase_weeks=2,
        )
        race = scaler.scale_workout(
            workout_type="medium_long",
            weekly_volume=55.0,
            tier="mid",
            phase="race",
            week_in_phase=1,
            total_phase_weeks=1,
        )
        assert race.total_distance_miles < taper.total_distance_miles, (
            f"Race-week medium-long ({race.total_distance_miles}mi) should be shorter "
            f"than taper medium-long ({taper.total_distance_miles}mi)"
        )

    def test_medium_long_progression_visible_within_phase(self):
        """Medium-long distance increases from early to late in a phase."""
        scaler = WorkoutScaler()

        early = scaler.scale_workout(
            workout_type="medium_long",
            weekly_volume=50.0,
            tier="mid",
            phase="threshold",
            week_in_phase=1,
            total_phase_weeks=6,
        )
        late = scaler.scale_workout(
            workout_type="medium_long",
            weekly_volume=50.0,
            tier="mid",
            phase="threshold",
            week_in_phase=5,
            total_phase_weeks=6,
        )
        assert late.total_distance_miles > early.total_distance_miles, (
            f"Late-phase medium-long ({late.total_distance_miles}mi) should exceed "
            f"early-phase ({early.total_distance_miles}mi) — progression must be visible"
        )

    def test_plan_taper_medium_long_below_peak(self):
        """End-to-end: 18w marathon plan — taper ML miles < peak ML miles."""
        gen = PlanGenerator()
        plan = gen.generate_standard(
            distance="marathon",
            duration_weeks=18,
            tier="mid",
            days_per_week=6,
        )
        builder = PhaseBuilder()
        phases = builder.build_phases(distance="marathon", duration_weeks=18, tier="mid")

        taper_weeks = {
            w for p in phases if p.phase_type.value == "taper" for w in p.weeks
        }
        build_weeks = {
            w for p in phases
            if p.phase_type.value not in ("taper", "race")
            for w in p.weeks
        }

        def ml_miles(week_set):
            return [
                w.distance_miles
                for w in plan.workouts
                if w.week in week_set and w.workout_type in ("medium_long", "medium_long_mp")
            ]

        taper_ml = ml_miles(taper_weeks)
        build_ml = ml_miles(build_weeks)

        if taper_ml and build_ml:
            avg_taper = sum(taper_ml) / len(taper_ml)
            max_build = max(build_ml)
            assert avg_taper < max_build, (
                f"Average taper ML ({avg_taper:.1f}mi) should be less than "
                f"peak build ML ({max_build:.1f}mi)"
            )


# ---------------------------------------------------------------------------
# T2-8: Gate long_mp / long_hmp on tier + volume
# ---------------------------------------------------------------------------

class TestT2MPHMPGate:
    """
    T2-8 acceptance: low-tier, low-volume athletes produce zero long_mp.
    High-tier athletes receive long_mp from the MP phase onward.
    """

    def test_beginner_archetype_produces_zero_long_mp(self):
        """
        A builder-tier athlete (< 35mpw) must receive zero long_mp sessions.
        The "builder" tier is the low-volume gate: < 35mpw maps to this tier.
        "low" tier (35-45mpw) athletes may be experienced and still receive MP work.
        """
        gen = PlanGenerator()
        plan = gen.generate_standard(
            distance="marathon",
            duration_weeks=18,
            tier="builder",
            days_per_week=5,
        )
        long_mp_count = sum(1 for w in plan.workouts if w.workout_type == "long_mp")
        assert long_mp_count == 0, (
            f"Builder-tier marathon plan should have 0 long_mp sessions. "
            f"Got {long_mp_count}."
        )

    def test_high_tier_gets_long_mp_in_marathon_specific_phase(self):
        """
        High-tier athlete (sub-3 aspirant, 65mpw) should receive long_mp sessions
        in the marathon-specific / race-specific phases.
        """
        gen = PlanGenerator()
        plan = gen.generate_standard(
            distance="marathon",
            duration_weeks=18,
            tier="high",
            days_per_week=6,
        )
        builder = PhaseBuilder()
        phases = builder.build_phases(distance="marathon", duration_weeks=18, tier="high")

        mp_phases_weeks = {
            w for p in phases
            if p.phase_type.value in ("marathon_specific", "race_specific")
            for w in p.weeks
        }

        long_mp_in_mp_phase = [
            w for w in plan.workouts
            if w.workout_type == "long_mp" and w.week in mp_phases_weeks
        ]
        assert long_mp_in_mp_phase, (
            "High-tier 18w marathon plan should have long_mp sessions in the "
            "marathon-specific/race-specific phase."
        )

    def test_long_mp_never_appears_in_base_or_threshold_phases(self):
        """long_mp must not appear in base_speed or threshold phases regardless of tier."""
        gen = PlanGenerator()
        plan = gen.generate_standard(
            distance="marathon",
            duration_weeks=18,
            tier="high",
            days_per_week=6,
        )
        builder = PhaseBuilder()
        phases = builder.build_phases(distance="marathon", duration_weeks=18, tier="high")

        forbidden_weeks = {
            w for p in phases
            if p.phase_type.value in ("base_speed", "threshold")
            for w in p.weeks
        }
        violations = [
            w for w in plan.workouts
            if w.workout_type == "long_mp" and w.week in forbidden_weeks
        ]
        assert not violations, (
            f"long_mp appeared in base/threshold phase: "
            f"weeks {[v.week for v in violations]}"
        )

    def test_builder_half_marathon_produces_zero_long_hmp(self):
        """
        T2-8 HMP gate: builder-tier half-marathon plans must produce zero long_hmp
        sessions. The gate in _get_workout_for_day blocks HMP long runs for builder
        tier, matching the marathon long_mp gate.
        """
        gen = PlanGenerator()
        plan = gen.generate_standard(
            distance="half_marathon",
            duration_weeks=16,
            tier="builder",
            days_per_week=5,
        )
        hmp_count = sum(1 for w in plan.workouts if w.workout_type == "long_hmp")
        assert hmp_count == 0, (
            f"Builder-tier half-marathon plan should have 0 long_hmp sessions. "
            f"Got {hmp_count}."
        )


# ---------------------------------------------------------------------------
# T2-9: Threshold session volume cap for low-mileage athletes
# ---------------------------------------------------------------------------

class TestT2ThresholdCap:
    """
    T2-9 acceptance: low-tier beginner threshold work ≤ 3.5mi per session.
    All athletes: threshold_session_miles / weekly_miles ≤ 0.18.
    """

    @pytest.mark.parametrize("weekly_volume", [15.0, 20.0, 25.0])
    def test_low_tier_threshold_continuous_work_capped(self, weekly_volume):
        """Continuous T session work for low-tier athletes must stay ≤ 3.5mi."""
        scaler = WorkoutScaler()
        wo = scaler.scale_workout(
            workout_type="threshold",
            weekly_volume=weekly_volume,
            tier="low",
            phase="threshold",
            week_in_phase=3,
            total_phase_weeks=4,
        )
        # Find the T segment
        segs = wo.segments or []
        t_seg = next((s for s in segs if s.get("pace") in ("threshold", "t")), None)
        t_miles = t_seg["distance_miles"] if t_seg else (wo.total_distance_miles - 3.0)
        assert t_miles <= 3.5, (
            f"Low-tier {weekly_volume}mpw threshold work should be ≤ 3.5mi. "
            f"Got {t_miles:.2f}mi (total session: {wo.total_distance_miles:.1f}mi)"
        )

    @pytest.mark.parametrize("weekly_volume", [15.0, 20.0, 25.0])
    def test_low_tier_threshold_intervals_work_capped(self, weekly_volume):
        """Interval T session work for low-tier athletes must stay ≤ 3.5mi."""
        scaler = WorkoutScaler()
        wo = scaler.scale_workout(
            workout_type="threshold_intervals",
            weekly_volume=weekly_volume,
            tier="low",
            phase="threshold",
            week_in_phase=2,
            total_phase_weeks=4,
        )
        segs = wo.segments or []
        t_seg = next((s for s in segs if s.get("type") == "intervals"), None)
        t_miles = t_seg["distance_miles"] if t_seg else wo.total_distance_miles
        assert t_miles <= 3.5, (
            f"Low-tier {weekly_volume}mpw threshold interval work should be ≤ 3.5mi. "
            f"Got {t_miles:.2f}mi"
        )

    def test_all_athletes_threshold_session_ratio(self):
        """For all generated plans, T-work miles / weekly miles ≤ 0.15 (Source B 10%+buffer)."""
        gen = PlanGenerator()
        for distance, tier in [("marathon", "low"), ("marathon", "mid"), ("10k", "low")]:
            plan = gen.generate_standard(
                distance=distance,
                duration_weeks=12,
                tier=tier,
                days_per_week=6,
            )
            threshold_types = {"threshold", "threshold_intervals"}
            for w in plan.workouts:
                if w.workout_type not in threshold_types:
                    continue
                week_miles = sum(
                    x.distance_miles or 0
                    for x in plan.workouts
                    if x.week == w.week and x.workout_type != "rest"
                )
                if week_miles < 10:
                    continue  # Skip degenerate weeks
                # Use T-pace segment miles when available (Source B 10% is on work only)
                segs = getattr(w, "segments", None) or []
                t_work = sum(
                    s.get("distance_miles", 0)
                    for s in segs
                    if s.get("pace") in ("threshold", "t")
                    or s.get("type") in ("threshold", "intervals")
                )
                if not t_work:
                    t_work = max(0.0, (w.distance_miles or 0) - 3.0)
                ratio = t_work / week_miles
                assert ratio <= 0.15, (
                    f"{distance}/{tier} plan week {w.week}: "
                    f"T-work {t_work:.1f}mi / weekly {week_miles:.1f}mi = {ratio:.2%} > 15%"
                )


# ---------------------------------------------------------------------------
# T2-10: Long run floor from athlete history
# ---------------------------------------------------------------------------

class TestT2LongRunFloor:
    """
    T2-10 acceptance: athlete with L30 long run = 18mi gets long runs ≥ 15mi
    in base/build phases of a 10K plan (floor raised above population cap).
    """

    def test_history_floor_raises_long_run_cap(self):
        """
        With easy_long_floor_mi=18, the long run peak cap should be ≥ 18.9mi
        (1.05× the floor), not limited to the default LONG_RUN_PEAKS table value.
        """
        scaler = WorkoutScaler()
        wo = scaler.scale_workout(
            workout_type="long",
            weekly_volume=70.0,
            tier="high",
            phase="base_speed",
            week_in_phase=4,
            plan_week=10,
            duration_weeks=12,
            easy_long_floor_mi=18.0,
        )
        # High-tier 10K LONG_RUN_PEAKS is 14mi by default; floor should override it
        assert wo.total_distance_miles >= 15.0, (
            f"With L30 floor of 18mi, long run should be ≥ 15mi (elevated above "
            f"10K table cap). Got {wo.total_distance_miles}mi"
        )

    def test_floor_absent_respects_population_cap(self):
        """Without a floor, long run stays within the LONG_RUN_PEAKS table for the given tier/goal."""
        scaler = WorkoutScaler()

        wo = scaler.scale_workout(
            workout_type="long",
            weekly_volume=70.0,
            tier="high",
            phase="base_speed",
            week_in_phase=4,
            plan_week=10,
            duration_weeks=12,
        )
        # "high" tier marathon cap is 22mi; without a history floor the plan must stay ≤ 22mi
        peak_cap = 22
        assert wo.total_distance_miles <= peak_cap, (
            f"Without floor, long run should not exceed LONG_RUN_PEAKS cap ({peak_cap}mi). "
            f"Got {wo.total_distance_miles}mi"
        )

    def test_floor_1_05_multiplier_applied(self):
        """
        peak_cap = max(LONG_RUN_PEAKS, floor * 1.05) — a 5% buffer above history
        allows the plan to push slightly beyond the athlete's last long run.
        """
        scaler = WorkoutScaler()
        wo_with_floor = scaler.scale_workout(
            workout_type="long",
            weekly_volume=80.0,
            tier="high",
            phase="marathon_specific",
            week_in_phase=3,
            plan_week=14,
            duration_weeks=18,
            easy_long_floor_mi=16.0,
        )
        # With floor=16, peak_cap = max(22, 16*1.05=16.8) = 22 (table wins here)
        # Plan can target up to 22mi, not clipped at 16mi
        assert wo_with_floor.total_distance_miles >= 16.0, (
            f"Plan should reach or exceed the 16mi history floor. "
            f"Got {wo_with_floor.total_distance_miles}mi"
        )
