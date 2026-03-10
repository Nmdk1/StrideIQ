"""
No-Race-Planned Mode Tests (Phase 2E)

Tests for maintenance and base building modes.

Organization:
    1. Maintenance Mode — flat volume, 1 quality session, strides
    2. Base Building Mode — progressive volume, no hard quality
    3. Volume derivation — correct fallbacks from history
    4. Plan persistence — saves correctly to DB
    5. Rolling refresh — weekly extension works
"""

import pytest
from datetime import date, timedelta
from uuid import uuid4


# ===================================================================
# 1. MAINTENANCE MODE
# ===================================================================

class TestMaintenanceMode:
    """Test that maintenance mode produces the right structure."""

    def test_maintenance_produces_4_weeks(self, db_session):
        """Maintenance plan should be exactly 4 weeks."""
        from services.no_race_modes import NoRaceModeGenerator

        gen = NoRaceModeGenerator(db_session)
        plan = gen.generate_maintenance(
            athlete_id=uuid4(),
            start_date=date(2026, 2, 16),
            base_volume_km=60.0,
        )

        assert plan.total_weeks == 4
        assert plan.mode == "maintenance"
        assert len(plan.weekly_volumes_km) == 4

    def test_maintenance_flat_volume(self, db_session):
        """Maintenance volume should be constant across all 4 weeks."""
        from services.no_race_modes import NoRaceModeGenerator

        gen = NoRaceModeGenerator(db_session)
        plan = gen.generate_maintenance(
            athlete_id=uuid4(),
            start_date=date(2026, 2, 16),
            base_volume_km=60.0,
        )

        assert all(v == 60.0 for v in plan.weekly_volumes_km), (
            f"Expected flat 60.0 km/week, got {plan.weekly_volumes_km}"
        )

    def test_maintenance_has_one_quality_session(self, db_session):
        """Each maintenance week should have exactly 1 threshold session."""
        from services.no_race_modes import NoRaceModeGenerator

        gen = NoRaceModeGenerator(db_session)
        plan = gen.generate_maintenance(
            athlete_id=uuid4(),
            start_date=date(2026, 2, 16),
            base_volume_km=60.0,
        )

        # Group by week
        weeks = {}
        for w in plan.workouts:
            weeks.setdefault(w.week_number, []).append(w)

        for week_num, workouts in weeks.items():
            quality_count = sum(1 for w in workouts if w.workout_type == "threshold")
            assert quality_count == 1, (
                f"Week {week_num} has {quality_count} quality sessions, expected 1"
            )

    def test_maintenance_has_strides(self, db_session):
        """Each maintenance week should have strides sessions."""
        from services.no_race_modes import NoRaceModeGenerator

        gen = NoRaceModeGenerator(db_session)
        plan = gen.generate_maintenance(
            athlete_id=uuid4(),
            start_date=date(2026, 2, 16),
            base_volume_km=60.0,
        )

        weeks = {}
        for w in plan.workouts:
            weeks.setdefault(w.week_number, []).append(w)

        for week_num, workouts in weeks.items():
            stride_count = sum(1 for w in workouts if w.workout_type == "strides")
            assert stride_count >= 1, (
                f"Week {week_num} has {stride_count} stride sessions, expected at least 1"
            )

    def test_maintenance_has_long_run(self, db_session):
        """Each maintenance week should have a long run."""
        from services.no_race_modes import NoRaceModeGenerator

        gen = NoRaceModeGenerator(db_session)
        plan = gen.generate_maintenance(
            athlete_id=uuid4(),
            start_date=date(2026, 2, 16),
            base_volume_km=60.0,
        )

        weeks = {}
        for w in plan.workouts:
            weeks.setdefault(w.week_number, []).append(w)

        for week_num, workouts in weeks.items():
            long_count = sum(1 for w in workouts if w.workout_type == "long")
            assert long_count == 1, (
                f"Week {week_num} has {long_count} long runs, expected 1"
            )


# ===================================================================
# 2. BASE BUILDING MODE
# ===================================================================

class TestBaseBuildingMode:
    """Test that base building mode has correct progression."""

    def test_base_building_produces_4_weeks(self, db_session):
        """Base building plan should be exactly 4 weeks."""
        from services.no_race_modes import NoRaceModeGenerator

        gen = NoRaceModeGenerator(db_session)
        plan = gen.generate_base_building(
            athlete_id=uuid4(),
            start_date=date(2026, 2, 16),
            current_volume_km=50.0,
        )

        assert plan.total_weeks == 4
        assert plan.mode == "base_building"

    def test_base_building_progressive_volume(self, db_session):
        """Volume should increase for 3 weeks then cut back on week 4."""
        from services.no_race_modes import NoRaceModeGenerator

        gen = NoRaceModeGenerator(db_session)
        plan = gen.generate_base_building(
            athlete_id=uuid4(),
            start_date=date(2026, 2, 16),
            current_volume_km=50.0,
        )

        vols = plan.weekly_volumes_km
        # Week 1: 50, Week 2: 52.5, Week 3: 55, Week 4: 42.5
        assert vols[0] == 50.0
        assert vols[1] > vols[0], "Week 2 should be higher than week 1"
        assert vols[2] > vols[1], "Week 3 should be higher than week 2"
        assert vols[3] < vols[0], "Week 4 (cutback) should be lower than week 1"

    def test_base_building_no_threshold(self, db_session):
        """Base building should have NO threshold/interval sessions."""
        from services.no_race_modes import NoRaceModeGenerator

        gen = NoRaceModeGenerator(db_session)
        plan = gen.generate_base_building(
            athlete_id=uuid4(),
            start_date=date(2026, 2, 16),
            current_volume_km=50.0,
        )

        quality_types = {"threshold", "intervals", "interval", "tempo"}
        for workout in plan.workouts:
            assert workout.workout_type not in quality_types, (
                f"Base building should not have {workout.workout_type} sessions. "
                f"Found: {workout.title} on {workout.date}"
            )

    def test_base_building_has_hills(self, db_session):
        """Base building should include hill sprints for neuromuscular work."""
        from services.no_race_modes import NoRaceModeGenerator

        gen = NoRaceModeGenerator(db_session)
        plan = gen.generate_base_building(
            athlete_id=uuid4(),
            start_date=date(2026, 2, 16),
            current_volume_km=50.0,
        )

        hill_count = sum(1 for w in plan.workouts if w.workout_type == "hills")
        assert hill_count >= 4, (
            f"Expected at least 4 hill sessions (1/week for 4 weeks), got {hill_count}"
        )

    def test_base_building_has_strides(self, db_session):
        """Base building should include strides for leg speed."""
        from services.no_race_modes import NoRaceModeGenerator

        gen = NoRaceModeGenerator(db_session)
        plan = gen.generate_base_building(
            athlete_id=uuid4(),
            start_date=date(2026, 2, 16),
            current_volume_km=50.0,
        )

        stride_count = sum(1 for w in plan.workouts if w.workout_type == "strides")
        assert stride_count >= 4, (
            f"Expected at least 4 stride sessions, got {stride_count}"
        )


# ===================================================================
# 3. VOLUME DERIVATION
# ===================================================================

class TestVolumeDerivation:
    """Test volume derivation from athlete history."""

    def test_maintenance_volume_from_last_plan(self, db_session):
        """Maintenance volume should be 80% of last plan's baseline volume."""
        from models import Athlete, TrainingPlan
        from services.no_race_modes import NoRaceModeGenerator

        athlete = Athlete(
            email="vol_test@test.com", display_name="Volume Test",
            subscription_tier="guided", birthdate=date(1990, 1, 1), sex="M",
        )
        db_session.add(athlete)
        db_session.flush()

        # Create a completed plan with 80 km/week baseline
        plan = TrainingPlan(
            athlete_id=athlete.id, name="Past Plan", status="completed",
            goal_race_date=date(2026, 1, 15), goal_race_distance_m=42195,
            plan_start_date=date(2025, 9, 1), plan_end_date=date(2026, 1, 15),
            total_weeks=18, plan_type="marathon", generation_method="framework_v2",
            baseline_weekly_volume_km=80.0,
        )
        db_session.add(plan)
        db_session.flush()

        gen = NoRaceModeGenerator(db_session)
        result = gen.generate_maintenance(
            athlete_id=athlete.id,
            start_date=date(2026, 2, 16),
        )

        # 80% of 80 = 64 km/week
        assert result.base_volume_km == 64.0

    def test_volume_fallback_to_recent_activity(self, db_session):
        """When no plan exists, volume should derive from recent activities."""
        from models import Athlete, Activity
        from services.no_race_modes import NoRaceModeGenerator
        from datetime import datetime

        athlete = Athlete(
            email="fallback@test.com", display_name="Fallback Test",
            subscription_tier="guided", birthdate=date(1990, 1, 1), sex="M",
        )
        db_session.add(athlete)
        db_session.flush()

        # Add activities: 80 km over 14 days = 40 km/week average
        for i in range(10):
            act = Activity(
                athlete_id=athlete.id, name=f"Run {i}",
                start_time=datetime(2026, 2, 1 + i, 7, 0),
                sport="Run", source="strava",
                distance_m=8000, duration_s=2400,
                provider="strava",
                external_activity_id=f"fallback_{uuid4().hex[:8]}",
            )
            db_session.add(act)
        db_session.flush()

        gen = NoRaceModeGenerator(db_session)
        result = gen.generate_base_building(
            athlete_id=athlete.id,
            start_date=date(2026, 2, 16),
        )

        # 80 km / 2 weeks = 40 km/week
        assert result.base_volume_km >= 20.0  # At minimum floor

    def test_volume_minimum_floor(self, db_session):
        """Volume should never go below 20 km/week."""
        from models import Athlete
        from services.no_race_modes import NoRaceModeGenerator

        athlete = Athlete(
            email="floor@test.com", display_name="Floor Test",
            subscription_tier="guided", birthdate=date(1990, 1, 1), sex="M",
        )
        db_session.add(athlete)
        db_session.flush()

        gen = NoRaceModeGenerator(db_session)
        # No plan, no activities → should use minimum floor
        result = gen.generate_base_building(
            athlete_id=athlete.id,
            start_date=date(2026, 2, 16),
        )

        assert result.base_volume_km >= 20.0


# ===================================================================
# 4. PLAN PERSISTENCE
# ===================================================================

class TestPlanPersistence:
    """Test that no-race plans save correctly to the database."""

    def test_save_maintenance_plan(self, db_session):
        """Maintenance plan should create TrainingPlan + PlannedWorkout records."""
        from models import Athlete, TrainingPlan, PlannedWorkout
        from services.no_race_modes import NoRaceModeGenerator, save_no_race_plan

        athlete = Athlete(
            email="save_test@test.com", display_name="Save Test",
            subscription_tier="guided", birthdate=date(1990, 1, 1), sex="M",
        )
        db_session.add(athlete)
        db_session.flush()

        gen = NoRaceModeGenerator(db_session)
        plan = gen.generate_maintenance(
            athlete_id=athlete.id,
            start_date=date(2026, 2, 16),
            base_volume_km=50.0,
        )

        plan_id = save_no_race_plan(plan, db_session)

        # Verify TrainingPlan was created
        db_plan = db_session.query(TrainingPlan).filter(TrainingPlan.id == plan_id).first()
        assert db_plan is not None
        assert db_plan.plan_type == "maintenance"
        assert db_plan.status == "active"
        assert db_plan.generation_method == "no_race_mode"

        # Verify PlannedWorkout records
        workouts = db_session.query(PlannedWorkout).filter(
            PlannedWorkout.plan_id == plan_id,
        ).all()
        assert len(workouts) == len(plan.workouts)

    def test_save_base_building_plan(self, db_session):
        """Base building plan should save with correct plan_type."""
        from models import Athlete, TrainingPlan
        from services.no_race_modes import NoRaceModeGenerator, save_no_race_plan

        athlete = Athlete(
            email="bb_save@test.com", display_name="BB Save",
            subscription_tier="guided", birthdate=date(1990, 1, 1), sex="M",
        )
        db_session.add(athlete)
        db_session.flush()

        gen = NoRaceModeGenerator(db_session)
        plan = gen.generate_base_building(
            athlete_id=athlete.id,
            start_date=date(2026, 2, 16),
            current_volume_km=50.0,
        )

        plan_id = save_no_race_plan(plan, db_session)

        db_plan = db_session.query(TrainingPlan).filter(TrainingPlan.id == plan_id).first()
        assert db_plan.plan_type == "base_building"
        assert db_plan.baseline_weekly_volume_km == 50.0


# ===================================================================
# 5. ROLLING REFRESH
# ===================================================================

class TestRollingRefresh:
    """Test the weekly plan refresh mechanism."""

    def test_refresh_extends_plan_by_one_week(self, db_session):
        """Refreshing should add one week of workouts to the plan."""
        from models import Athlete, TrainingPlan, PlannedWorkout
        from services.no_race_modes import NoRaceModeGenerator, save_no_race_plan, refresh_rolling_plan

        athlete = Athlete(
            email="refresh@test.com", display_name="Refresh Test",
            subscription_tier="guided", birthdate=date(1990, 1, 1), sex="M",
        )
        db_session.add(athlete)
        db_session.flush()

        gen = NoRaceModeGenerator(db_session)
        plan = gen.generate_maintenance(
            athlete_id=athlete.id,
            start_date=date(2026, 2, 16),
            base_volume_km=50.0,
        )
        plan_id = save_no_race_plan(plan, db_session)

        # Count initial workouts
        initial_count = db_session.query(PlannedWorkout).filter(
            PlannedWorkout.plan_id == plan_id,
        ).count()

        # Refresh
        refreshed_id = refresh_rolling_plan(athlete.id, db_session)
        assert refreshed_id == plan_id

        # Should have more workouts now
        final_count = db_session.query(PlannedWorkout).filter(
            PlannedWorkout.plan_id == plan_id,
        ).count()
        assert final_count > initial_count

        # Plan should be extended
        db_plan = db_session.query(TrainingPlan).filter(TrainingPlan.id == plan_id).first()
        assert db_plan.total_weeks == 5  # Was 4, now 5

    def test_refresh_returns_none_without_plan(self, db_session):
        """Refreshing without an active no-race plan should return None."""
        from models import Athlete
        from services.no_race_modes import refresh_rolling_plan

        athlete = Athlete(
            email="no_plan_refresh@test.com", display_name="No Plan",
            subscription_tier="guided", birthdate=date(1990, 1, 1), sex="M",
        )
        db_session.add(athlete)
        db_session.flush()

        result = refresh_rolling_plan(athlete.id, db_session)
        assert result is None
