"""
Output Validation Tests

Tests that generated plans make physiological sense.
These tests validate the QUALITY of output, not just correctness.

Each test checks a specific aspect of training plan quality.
"""

import pytest
from datetime import date, timedelta

from services.plan_framework import (
    PlanGenerator,
    VolumeTierClassifier,
    PhaseBuilder,
    WorkoutScaler,
    PlanTier,
    VolumeTier,
    Distance,
)


class TestVolumeProgression:
    """Test that volume builds safely and progressively."""
    
    def test_volume_never_increases_more_than_10_percent(self):
        """Volume should never increase more than 10% week-over-week."""
        generator = PlanGenerator()
        plan = generator.generate_standard(
            distance="marathon",
            duration_weeks=18,
            tier="mid",
            days_per_week=6,
        )
        
        volumes = plan.weekly_volumes
        
        for i in range(1, len(volumes)):
            prev = volumes[i - 1]
            curr = volumes[i]
            
            # Skip if it's a decrease (cutback)
            if curr < prev:
                continue
            
            increase_pct = (curr - prev) / prev if prev > 0 else 0
            
            # Allow up to 15% for early weeks when starting low
            max_increase = 0.15 if i <= 3 else 0.10
            
            assert increase_pct <= max_increase, (
                f"Week {i + 1}: Volume increased {increase_pct:.1%} "
                f"(from {prev:.1f} to {curr:.1f}), exceeds {max_increase:.0%} limit"
            )
    
    def test_volume_has_cutback_weeks(self):
        """There should be at least one cutback week in an 18-week plan."""
        generator = PlanGenerator()
        plan = generator.generate_standard(
            distance="marathon",
            duration_weeks=18,
            tier="mid",
            days_per_week=6,
        )
        
        volumes = plan.weekly_volumes
        cutback_count = 0
        
        for i in range(1, len(volumes) - 2):  # Exclude taper
            if volumes[i] < volumes[i - 1] * 0.85:  # 15%+ reduction
                cutback_count += 1
        
        assert cutback_count >= 2, (
            f"Only {cutback_count} cutback weeks found. "
            f"Expected at least 2 in 18-week plan."
        )
    
    def test_taper_reduces_volume(self):
        """Final 2 weeks should have reduced volume."""
        generator = PlanGenerator()
        plan = generator.generate_standard(
            distance="marathon",
            duration_weeks=18,
            tier="mid",
            days_per_week=6,
        )
        
        volumes = plan.weekly_volumes
        peak = max(volumes[:-2])  # Exclude last 2 weeks
        
        # Last 2 weeks should be significantly less than peak
        assert volumes[-1] < peak * 0.6, (
            f"Race week volume ({volumes[-1]:.1f}) should be < 60% of peak ({peak:.1f})"
        )
        assert volumes[-2] < peak * 0.8, (
            f"Taper week volume ({volumes[-2]:.1f}) should be < 80% of peak ({peak:.1f})"
        )


class TestPeriodization:
    """Test that phases are structured correctly."""
    
    def test_phases_cover_all_weeks(self):
        """Every week should be in exactly one phase."""
        builder = PhaseBuilder()
        phases = builder.build_phases(
            distance="marathon",
            duration_weeks=18,
            tier="mid"
        )
        
        covered_weeks = []
        for phase in phases:
            covered_weeks.extend(phase.weeks)
        
        # Check all weeks are covered
        for week in range(1, 19):
            assert week in covered_weeks, f"Week {week} not covered by any phase"
        
        # Check no duplicates
        assert len(covered_weeks) == len(set(covered_weeks)), "Some weeks are in multiple phases"
    
    def test_phases_in_logical_order(self):
        """Phases should progress logically: base → build → specific → taper."""
        builder = PhaseBuilder()
        phases = builder.build_phases(
            distance="marathon",
            duration_weeks=18,
            tier="mid"
        )
        
        # First phase should be base-related
        assert "base" in phases[0].phase_type.value.lower(), (
            f"First phase should be base, got {phases[0].name}"
        )
        
        # Last phase should be race week
        assert "race" in phases[-1].phase_type.value.lower(), (
            f"Last phase should be race, got {phases[-1].name}"
        )
        
        # Second to last should be taper
        assert "taper" in phases[-2].phase_type.value.lower(), (
            f"Second to last phase should be taper, got {phases[-2].name}"
        )
    
    def test_marathon_has_mp_phase(self):
        """Marathon plans should have a marathon-specific phase."""
        builder = PhaseBuilder()
        phases = builder.build_phases(
            distance="marathon",
            duration_weeks=18,
            tier="mid"
        )
        
        mp_phases = [p for p in phases if "marathon" in p.phase_type.value.lower()]
        
        assert len(mp_phases) >= 1, "Marathon plan should have at least one MP phase"


class TestWorkoutScaling:
    """Test that workouts are scaled appropriately."""
    
    def test_threshold_respects_10_percent_rule(self):
        """Threshold work should not exceed 10% of weekly volume."""
        scaler = WorkoutScaler()
        
        for volume in [40, 55, 70]:
            workout = scaler.scale_workout(
                workout_type="threshold_intervals",
                weekly_volume=volume,
                tier="mid",
                phase="threshold",
                week_in_phase=4,  # Peak T-block
            )
            
            if workout.segments:
                # Calculate threshold miles
                t_miles = 0
                for seg in workout.segments:
                    if seg.get("pace") == "threshold":
                        # Estimate distance from duration
                        duration = seg.get("duration_min", 0)
                        t_miles += duration * 0.17  # ~6 min/mile at T
                
                max_allowed = volume * 0.12  # Slight buffer
                
                assert t_miles <= max_allowed, (
                    f"At {volume}mpw, threshold work is {t_miles:.1f}mi, "
                    f"exceeds {max_allowed:.1f}mi (10% limit)"
                )
    
    def test_long_run_respects_cap(self):
        """Long run should not exceed tier-appropriate cap."""
        scaler = WorkoutScaler()
        
        workout = scaler.scale_workout(
            workout_type="long",
            weekly_volume=55,
            tier="mid",
            phase="race_specific",
            distance="marathon"
        )
        
        assert workout.total_distance_miles <= 22, (
            f"Mid-volume long run ({workout.total_distance_miles}mi) "
            f"should not exceed 22mi"
        )
    
    def test_mp_work_respects_18_mile_cap(self):
        """Continuous MP should not exceed 18 miles."""
        scaler = WorkoutScaler()
        
        workout = scaler.scale_workout(
            workout_type="long_mp",
            weekly_volume=70,
            tier="high",
            phase="race_specific",
            week_in_phase=5,  # Late in phase
            distance="marathon"
        )
        
        # Find MP segment
        if workout.segments:
            for seg in workout.segments:
                if seg.get("pace") == "MP":
                    mp_miles = seg.get("distance_miles", 0)
                    assert mp_miles <= 18, (
                        f"MP segment ({mp_miles}mi) exceeds 18mi cap"
                    )


class TestWeeklyStructure:
    """Test that weekly structure makes sense."""
    
    def test_rest_days_present(self):
        """Each week should have at least 1 rest day for 6-day plans."""
        generator = PlanGenerator()
        plan = generator.generate_standard(
            distance="marathon",
            duration_weeks=18,
            tier="mid",
            days_per_week=6,
        )
        
        for week in range(1, 19):
            week_workouts = plan.get_week(week)
            rest_days = [w for w in week_workouts if w.workout_type == "rest"]
            
            assert len(rest_days) >= 1, (
                f"Week {week} has no rest days"
            )
    
    def test_long_run_on_sunday(self):
        """Long runs should be on Sunday (day 6)."""
        generator = PlanGenerator()
        plan = generator.generate_standard(
            distance="marathon",
            duration_weeks=18,
            tier="mid",
            days_per_week=6,
        )
        
        for week in range(1, 17):  # Exclude taper/race
            week_workouts = plan.get_week(week)
            long_runs = [w for w in week_workouts if "long" in w.workout_type]
            
            if long_runs:
                for lr in long_runs:
                    assert lr.day == 6, (  # Sunday
                        f"Week {week}: Long run on {lr.day_name}, should be Sunday"
                    )
    
    def test_quality_not_on_consecutive_days(self):
        """Quality sessions should have at least 1 easy day between."""
        generator = PlanGenerator()
        plan = generator.generate_standard(
            distance="marathon",
            duration_weeks=18,
            tier="mid",
            days_per_week=6,
        )
        
        quality_types = ["threshold", "tempo", "intervals", "long_mp", "hills"]
        
        for week in range(1, 17):
            week_workouts = sorted(plan.get_week(week), key=lambda w: w.day)
            
            prev_quality_day = -3  # Initialize far away
            
            for workout in week_workouts:
                is_quality = any(q in workout.workout_type for q in quality_types)
                
                if is_quality:
                    gap = workout.day - prev_quality_day
                    
                    # Should have at least 1 day between (gap >= 2)
                    assert gap >= 2 or prev_quality_day == -3, (
                        f"Week {week}: Quality sessions on days "
                        f"{prev_quality_day} and {workout.day} (need 1 day between)"
                    )
                    
                    prev_quality_day = workout.day


class TestPhysiologicalSense:
    """High-level tests that plans make physiological sense."""
    
    def test_mp_work_comes_after_base(self):
        """Marathon pace work should not appear in base phase."""
        generator = PlanGenerator()
        plan = generator.generate_standard(
            distance="marathon",
            duration_weeks=18,
            tier="mid",
            days_per_week=6,
        )
        
        base_phases = [p for p in plan.phases if "base" in p.phase_type.value.lower()]
        
        if base_phases:
            base_weeks = []
            for p in base_phases:
                base_weeks.extend(p.weeks)
            
            for workout in plan.workouts:
                if workout.week in base_weeks:
                    assert "mp" not in workout.workout_type.lower(), (
                        f"Week {workout.week}: MP work in base phase"
                    )
    
    def test_total_volume_is_reasonable(self):
        """Total plan volume should be in reasonable range."""
        generator = PlanGenerator()
        plan = generator.generate_standard(
            distance="marathon",
            duration_weeks=18,
            tier="mid",
            days_per_week=6,
        )
        
        total = plan.total_miles
        
        # 18-week mid-volume should be roughly 700-1000 miles
        assert 600 <= total <= 1100, (
            f"Total volume ({total:.0f}mi) outside expected range (600-1100)"
        )
    
    def test_easy_running_dominates(self):
        """Most running should be easy (80/20 principle)."""
        generator = PlanGenerator()
        plan = generator.generate_standard(
            distance="marathon",
            duration_weeks=18,
            tier="mid",
            days_per_week=6,
        )
        
        easy_types = ["easy", "recovery", "long", "medium_long"]
        hard_types = ["threshold", "tempo", "intervals", "long_mp"]
        
        easy_miles = sum(
            w.distance_miles or 0
            for w in plan.workouts
            if any(e in w.workout_type for e in easy_types)
            and not any(h in w.workout_type for h in hard_types)
        )
        
        total_miles = plan.total_miles
        
        easy_pct = easy_miles / total_miles if total_miles > 0 else 0
        
        # At least 70% should be easy (some MP long runs count as mixed)
        assert easy_pct >= 0.70, (
            f"Easy running is only {easy_pct:.0%}, should be at least 70%"
        )


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_short_plan_still_structured(self):
        """Even 8-week plans should have proper structure."""
        generator = PlanGenerator()
        plan = generator.generate_standard(
            distance="10k",
            duration_weeks=8,
            tier="mid",
            days_per_week=6,
        )
        
        # Should still have multiple phases
        assert len(plan.phases) >= 3, (
            f"8-week plan should have at least 3 phases, got {len(plan.phases)}"
        )
        
        # Should have taper
        assert any("taper" in p.phase_type.value.lower() for p in plan.phases), (
            "8-week plan should have taper phase"
        )
    
    def test_builder_tier_handles_low_volume(self):
        """Builder tier should handle low starting volume safely."""
        generator = PlanGenerator()
        plan = generator.generate_standard(
            distance="marathon",
            duration_weeks=18,
            tier="builder",
            days_per_week=6,
        )
        
        # Should start low and build up
        assert plan.weekly_volumes[0] <= 35, (
            f"Builder tier starts at {plan.weekly_volumes[0]:.1f}mpw, too high"
        )
        
        # Should still reach reasonable peak
        assert plan.peak_volume >= 45, (
            f"Builder tier peaks at {plan.peak_volume:.1f}mpw, too low"
        )
    
    def test_5_day_plan_valid(self):
        """5-day plans should have appropriate structure."""
        generator = PlanGenerator()
        plan = generator.generate_standard(
            distance="marathon",
            duration_weeks=18,
            tier="mid",
            days_per_week=5,
        )
        
        for week in range(1, 19):
            week_workouts = plan.get_week(week)
            running_days = [w for w in week_workouts if w.workout_type != "rest"]
            
            assert len(running_days) <= 5, (
                f"Week {week}: 5-day plan has {len(running_days)} running days"
            )


# Run tests directly for development
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
