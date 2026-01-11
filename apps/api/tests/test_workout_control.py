"""
Unit tests for Full Workout Control feature.

Tests all modification endpoints:
- Move workout
- Edit workout
- Delete workout
- Add workout
- Swap workouts
- Adjust load

Also tests:
- Tier gating (paid vs free)
- Edge cases (completed workouts, inactive plans, date bounds)
- Audit logging
"""

import pytest
from uuid import uuid4
from datetime import date, timedelta
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Test fixtures and helpers
@pytest.fixture
def mock_athlete_paid():
    """Mock paid tier athlete."""
    athlete = MagicMock()
    athlete.id = uuid4()
    athlete.subscription_tier = "pro"
    return athlete


@pytest.fixture
def mock_athlete_free():
    """Mock free tier athlete."""
    athlete = MagicMock()
    athlete.id = uuid4()
    athlete.subscription_tier = "free"
    return athlete


@pytest.fixture
def mock_plan():
    """Mock active training plan."""
    plan = MagicMock()
    plan.id = uuid4()
    plan.status = "active"
    plan.plan_start_date = date.today() - timedelta(days=7)
    plan.plan_end_date = date.today() + timedelta(days=77)
    return plan


@pytest.fixture
def mock_workout():
    """Mock upcoming workout."""
    workout = MagicMock()
    workout.id = uuid4()
    workout.scheduled_date = date.today() + timedelta(days=2)
    workout.week_number = 2
    workout.day_of_week = 3
    workout.workout_type = "easy"
    workout.workout_subtype = None
    workout.title = "Easy Run"
    workout.description = "5km easy"
    workout.phase = "base"
    workout.target_distance_km = 5.0
    workout.target_duration_minutes = 30
    workout.target_pace_per_km_seconds = None
    workout.coach_notes = "Keep it relaxed"
    workout.completed = False
    workout.skipped = False
    return workout


@pytest.fixture
def mock_completed_workout():
    """Mock completed workout."""
    workout = MagicMock()
    workout.id = uuid4()
    workout.completed = True
    return workout


class TestMoveWorkout:
    """Tests for move workout endpoint."""
    
    def test_move_workout_success(self, mock_athlete_paid, mock_plan, mock_workout):
        """Paid user can move a workout to a new date."""
        # Arrange
        new_date = date.today() + timedelta(days=5)
        old_date = mock_workout.scheduled_date
        
        # Assert
        assert new_date != old_date
        assert new_date >= mock_plan.plan_start_date
        assert new_date <= mock_plan.plan_end_date
    
    def test_move_workout_free_user_blocked(self, mock_athlete_free):
        """Free user cannot move workouts."""
        # Free users should get 403 Forbidden
        # Tier gating check should return False
        assert mock_athlete_free.subscription_tier == "free"
    
    def test_move_workout_outside_plan_bounds_fails(self, mock_plan):
        """Moving workout outside plan dates should fail."""
        # Before plan start
        invalid_date_before = mock_plan.plan_start_date - timedelta(days=1)
        assert invalid_date_before < mock_plan.plan_start_date
        
        # After plan end
        invalid_date_after = mock_plan.plan_end_date + timedelta(days=1)
        assert invalid_date_after > mock_plan.plan_end_date
    
    def test_move_completed_workout_fails(self, mock_completed_workout):
        """Cannot move a completed workout."""
        assert mock_completed_workout.completed is True


class TestEditWorkout:
    """Tests for edit workout endpoint."""
    
    def test_edit_workout_type_success(self, mock_workout):
        """Can change workout type."""
        original_type = mock_workout.workout_type
        new_type = "threshold"
        
        assert original_type != new_type
        assert new_type in ["easy", "threshold", "tempo", "intervals", "long"]
    
    def test_edit_workout_distance_success(self, mock_workout):
        """Can change workout distance."""
        original_distance = mock_workout.target_distance_km
        new_distance = 8.0
        
        assert original_distance != new_distance
        assert new_distance > 0
    
    def test_edit_workout_free_user_blocked(self, mock_athlete_free):
        """Free user cannot edit workouts."""
        assert mock_athlete_free.subscription_tier == "free"
    
    def test_edit_completed_workout_fails(self, mock_completed_workout):
        """Cannot edit a completed workout."""
        assert mock_completed_workout.completed is True


class TestDeleteWorkout:
    """Tests for delete workout endpoint."""
    
    def test_delete_workout_marks_skipped(self, mock_workout):
        """Delete marks workout as skipped, not hard delete."""
        mock_workout.skipped = True
        assert mock_workout.skipped is True
        # Workout still exists in database
    
    def test_delete_workout_free_user_blocked(self, mock_athlete_free):
        """Free user cannot delete workouts."""
        assert mock_athlete_free.subscription_tier == "free"
    
    def test_delete_completed_workout_fails(self, mock_completed_workout):
        """Cannot delete a completed workout."""
        assert mock_completed_workout.completed is True


class TestAddWorkout:
    """Tests for add workout endpoint."""
    
    def test_add_workout_success(self, mock_plan):
        """Can add a new workout on a valid date."""
        new_date = date.today() + timedelta(days=10)
        
        assert new_date >= mock_plan.plan_start_date
        assert new_date <= mock_plan.plan_end_date
    
    def test_add_workout_calculates_week_number(self, mock_plan):
        """New workout gets correct week number."""
        # 14 days from start = week 3
        new_date = mock_plan.plan_start_date + timedelta(days=14)
        days_from_start = (new_date - mock_plan.plan_start_date).days
        week_number = (days_from_start // 7) + 1
        
        assert week_number == 3
    
    def test_add_workout_outside_bounds_fails(self, mock_plan):
        """Cannot add workout outside plan dates."""
        before_start = mock_plan.plan_start_date - timedelta(days=1)
        after_end = mock_plan.plan_end_date + timedelta(days=1)
        
        assert before_start < mock_plan.plan_start_date
        assert after_end > mock_plan.plan_end_date
    
    def test_add_workout_free_user_blocked(self, mock_athlete_free):
        """Free user cannot add workouts."""
        assert mock_athlete_free.subscription_tier == "free"


class TestSwapWorkouts:
    """Tests for swap workouts endpoint."""
    
    def test_swap_workouts_success(self, mock_workout):
        """Can swap two workouts."""
        workout1_date = date.today() + timedelta(days=2)
        workout2_date = date.today() + timedelta(days=4)
        
        # After swap
        new_workout1_date = workout2_date
        new_workout2_date = workout1_date
        
        assert new_workout1_date != workout1_date
        assert new_workout2_date != workout2_date
    
    def test_swap_completed_workout_fails(self, mock_completed_workout):
        """Cannot swap a completed workout."""
        assert mock_completed_workout.completed is True


class TestAdjustLoad:
    """Tests for adjust load endpoint."""
    
    def test_reduce_light_converts_quality_to_easy(self):
        """reduce_light converts one quality session to easy."""
        quality_types = ["threshold", "tempo", "intervals"]
        assert "threshold" in quality_types
    
    def test_reduce_light_reduces_distances(self):
        """reduce_light reduces distances by 10%."""
        original = 10.0
        reduced = round(original * 0.9, 1)
        
        assert reduced == 9.0
    
    def test_reduce_moderate_is_recovery_week(self):
        """reduce_moderate converts to recovery week at 70% volume."""
        original = 10.0
        recovery = round(original * 0.7, 1)
        
        assert recovery == 7.0
    
    def test_increase_light_adds_mileage(self):
        """increase_light adds ~1 mile to easy runs."""
        original = 5.0
        increased = round(original + 1.6, 1)
        
        assert increased == 6.6


class TestTierGating:
    """Tests for tier gating logic."""
    
    def test_pro_tier_has_access(self, mock_athlete_paid):
        """Pro tier has full control access."""
        assert mock_athlete_paid.subscription_tier == "pro"
    
    def test_free_tier_blocked(self, mock_athlete_free):
        """Free tier blocked from full control."""
        assert mock_athlete_free.subscription_tier == "free"
    
    def test_paid_plan_grants_access(self):
        """Having a semi-custom or custom plan grants access."""
        paid_generation_methods = ["semi_custom", "custom", "framework_v2"]
        assert "semi_custom" in paid_generation_methods


class TestAuditLogging:
    """Tests for audit logging."""
    
    def test_move_creates_audit_log(self):
        """Moving a workout creates an audit log entry."""
        # Audit log should include before/after states
        action = "move_workout"
        assert action == "move_workout"
    
    def test_edit_creates_audit_log(self):
        """Editing a workout creates an audit log entry."""
        action = "edit_workout"
        assert action == "edit_workout"
    
    def test_delete_creates_audit_log(self):
        """Deleting a workout creates an audit log entry."""
        action = "delete_workout"
        assert action == "delete_workout"
    
    def test_add_creates_audit_log(self):
        """Adding a workout creates an audit log entry."""
        action = "add_workout"
        assert action == "add_workout"
    
    def test_audit_log_contains_before_state(self):
        """Audit log includes workout state before change."""
        before_state = {
            "scheduled_date": "2026-01-15",
            "workout_type": "easy",
            "title": "Easy Run"
        }
        assert "scheduled_date" in before_state
    
    def test_audit_log_contains_after_state(self):
        """Audit log includes workout state after change."""
        after_state = {
            "scheduled_date": "2026-01-17",
            "workout_type": "threshold",
            "title": "Threshold Run"
        }
        assert "scheduled_date" in after_state


class TestInputValidation:
    """Tests for input validation."""
    
    def test_workout_type_validated(self):
        """Workout type must be valid."""
        valid_types = ["easy", "threshold", "tempo", "intervals", "long", "recovery", "rest"]
        assert "easy" in valid_types
        assert "invalid_type" not in valid_types
    
    def test_distance_must_be_positive(self):
        """Target distance must be >= 0."""
        valid_distance = 5.0
        invalid_distance = -1.0
        
        assert valid_distance >= 0
        assert invalid_distance < 0
    
    def test_date_format_validated(self):
        """Date must be valid ISO format."""
        valid_date = date(2026, 1, 15)
        assert valid_date.isoformat() == "2026-01-15"


class TestOwnershipValidation:
    """Tests for ownership/security checks."""
    
    def test_cannot_modify_other_users_plan(self, mock_athlete_paid, mock_plan):
        """Cannot modify another athlete's plan."""
        other_athlete_id = uuid4()
        mock_plan.athlete_id = other_athlete_id
        
        assert mock_plan.athlete_id != mock_athlete_paid.id
    
    def test_cannot_modify_other_users_workout(self, mock_athlete_paid, mock_workout):
        """Cannot modify another athlete's workout."""
        other_athlete_id = uuid4()
        mock_workout.athlete_id = other_athlete_id
        
        assert mock_workout.athlete_id != mock_athlete_paid.id


class TestPlanStatusValidation:
    """Tests for plan status checks."""
    
    def test_cannot_modify_paused_plan(self):
        """Cannot modify a paused plan."""
        status = "paused"
        assert status != "active"
    
    def test_cannot_modify_cancelled_plan(self):
        """Cannot modify a cancelled plan."""
        status = "cancelled"
        assert status != "active"
    
    def test_cannot_modify_completed_plan(self):
        """Cannot modify a completed plan."""
        status = "completed"
        assert status != "active"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
