"""
Integration tests for Activity Feedback API endpoints

Tests CRUD operations, validation, perception prompts, and integration with activity analysis.
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from main import app
from core.database import SessionLocal
from models import Athlete, Activity, ActivityFeedback
from core.auth import create_access_token

client = TestClient(app)


@pytest.fixture
def test_athlete():
    """Create a test athlete"""
    db = SessionLocal()
    try:
        athlete = Athlete(
            email=f"test_feedback_{uuid4()}@example.com",
            display_name="Test Feedback Athlete",
            subscription_tier="free"
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)
        yield athlete
        # Cleanup
        db.query(ActivityFeedback).filter(ActivityFeedback.athlete_id == athlete.id).delete()
        db.query(Activity).filter(Activity.athlete_id == athlete.id).delete()
        db.delete(athlete)
        db.commit()
    finally:
        db.close()


@pytest.fixture
def test_activity(test_athlete):
    """Create a test activity"""
    db = SessionLocal()
    try:
        activity = Activity(
            athlete_id=test_athlete.id,
            start_time=datetime.now(),
            sport="run",
            source="manual",
            duration_s=1800,
            distance_m=5000,
            avg_hr=150,
            average_speed=Decimal('2.78')
        )
        db.add(activity)
        db.commit()
        db.refresh(activity)
        yield activity
        db.delete(activity)
        db.commit()
    finally:
        db.close()


@pytest.fixture
def auth_token(test_athlete):
    """Create auth token for test athlete"""
    return create_access_token({"sub": str(test_athlete.id)})


@pytest.fixture
def auth_headers(auth_token):
    """Get auth headers"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestCreateActivityFeedback:
    """Test POST /v1/activity-feedback endpoint"""
    
    def test_create_feedback_success(self, test_athlete, test_activity, auth_headers):
        """Test creating feedback successfully"""
        feedback_data = {
            "activity_id": str(test_activity.id),
            "perceived_effort": 7,
            "leg_feel": "tired",
            "mood_pre": "energetic",
            "mood_post": "satisfied",
            "energy_pre": 8,
            "energy_post": 6,
            "notes": "Felt strong throughout"
        }
        
        response = client.post(
            "/v1/activity-feedback",
            json=feedback_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["perceived_effort"] == 7
        assert data["leg_feel"] == "tired"
        assert data["mood_pre"] == "energetic"
        assert data["mood_post"] == "satisfied"
        assert data["energy_pre"] == 8
        assert data["energy_post"] == 6
        assert data["notes"] == "Felt strong throughout"
        assert data["activity_id"] == str(test_activity.id)
        assert data["athlete_id"] == str(test_athlete.id)
    
    def test_create_feedback_minimal(self, test_athlete, test_activity, auth_headers):
        """Test creating feedback with minimal required fields"""
        feedback_data = {
            "activity_id": str(test_activity.id),
            "perceived_effort": 5
        }
        
        response = client.post(
            "/v1/activity-feedback",
            json=feedback_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["perceived_effort"] == 5
    
    def test_create_feedback_invalid_activity(self, test_athlete, auth_headers):
        """Test creating feedback for non-existent activity"""
        feedback_data = {
            "activity_id": str(uuid4()),
            "perceived_effort": 5
        }
        
        response = client.post(
            "/v1/activity-feedback",
            json=feedback_data,
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    def test_create_feedback_duplicate(self, test_athlete, test_activity, auth_headers):
        """Test creating duplicate feedback (should fail)"""
        feedback_data = {
            "activity_id": str(test_activity.id),
            "perceived_effort": 5
        }
        
        # Create first feedback
        response1 = client.post(
            "/v1/activity-feedback",
            json=feedback_data,
            headers=auth_headers
        )
        assert response1.status_code == 201
        
        # Try to create duplicate
        response2 = client.post(
            "/v1/activity-feedback",
            json=feedback_data,
            headers=auth_headers
        )
        assert response2.status_code == 409
    
    def test_create_feedback_invalid_rpe(self, test_athlete, test_activity, auth_headers):
        """Test creating feedback with invalid RPE (outside 1-10)"""
        feedback_data = {
            "activity_id": str(test_activity.id),
            "perceived_effort": 11  # Invalid
        }
        
        response = client.post(
            "/v1/activity-feedback",
            json=feedback_data,
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "1 and 10" in response.json()["detail"]
    
    def test_create_feedback_invalid_leg_feel(self, test_athlete, test_activity, auth_headers):
        """Test creating feedback with invalid leg_feel category"""
        feedback_data = {
            "activity_id": str(test_activity.id),
            "leg_feel": "invalid_category"
        }
        
        response = client.post(
            "/v1/activity-feedback",
            json=feedback_data,
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "leg_feel must be one of" in response.json()["detail"]
    
    def test_create_feedback_invalid_energy(self, test_athlete, test_activity, auth_headers):
        """Test creating feedback with invalid energy scale"""
        feedback_data = {
            "activity_id": str(test_activity.id),
            "energy_pre": 15  # Invalid
        }
        
        response = client.post(
            "/v1/activity-feedback",
            json=feedback_data,
            headers=auth_headers
        )
        
        assert response.status_code == 400


class TestGetActivityFeedback:
    """Test GET /v1/activity-feedback/activity/{activity_id} endpoint"""
    
    def test_get_feedback_success(self, test_athlete, test_activity, auth_headers):
        """Test getting feedback successfully"""
        # Create feedback first
        feedback_data = {
            "activity_id": str(test_activity.id),
            "perceived_effort": 7,
            "leg_feel": "tired"
        }
        client.post("/v1/activity-feedback", json=feedback_data, headers=auth_headers)
        
        # Get feedback
        response = client.get(
            f"/v1/activity-feedback/activity/{test_activity.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["perceived_effort"] == 7
        assert data["leg_feel"] == "tired"
    
    def test_get_feedback_not_found(self, test_athlete, test_activity, auth_headers):
        """Test getting feedback that doesn't exist"""
        response = client.get(
            f"/v1/activity-feedback/activity/{test_activity.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 404


class TestUpdateActivityFeedback:
    """Test PUT /v1/activity-feedback/{feedback_id} endpoint"""
    
    def test_update_feedback_success(self, test_athlete, test_activity, auth_headers):
        """Test updating feedback successfully"""
        # Create feedback
        feedback_data = {
            "activity_id": str(test_activity.id),
            "perceived_effort": 5,
            "leg_feel": "normal"
        }
        create_response = client.post(
            "/v1/activity-feedback",
            json=feedback_data,
            headers=auth_headers
        )
        feedback_id = create_response.json()["id"]
        
        # Update feedback
        update_data = {
            "perceived_effort": 8,
            "leg_feel": "tired",
            "notes": "Updated notes"
        }
        response = client.put(
            f"/v1/activity-feedback/{feedback_id}",
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["perceived_effort"] == 8
        assert data["leg_feel"] == "tired"
        assert data["notes"] == "Updated notes"
    
    def test_update_feedback_partial(self, test_athlete, test_activity, auth_headers):
        """Test partial update (only some fields)"""
        # Create feedback
        feedback_data = {
            "activity_id": str(test_activity.id),
            "perceived_effort": 5,
            "leg_feel": "normal",
            "notes": "Original notes"
        }
        create_response = client.post(
            "/v1/activity-feedback",
            json=feedback_data,
            headers=auth_headers
        )
        feedback_id = create_response.json()["id"]
        
        # Update only perceived_effort
        update_data = {"perceived_effort": 7}
        response = client.put(
            f"/v1/activity-feedback/{feedback_id}",
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["perceived_effort"] == 7
        assert data["leg_feel"] == "normal"  # Unchanged
        assert data["notes"] == "Original notes"  # Unchanged


class TestDeleteActivityFeedback:
    """Test DELETE /v1/activity-feedback/{feedback_id} endpoint"""
    
    def test_delete_feedback_success(self, test_athlete, test_activity, auth_headers):
        """Test deleting feedback successfully"""
        # Create feedback
        feedback_data = {
            "activity_id": str(test_activity.id),
            "perceived_effort": 5
        }
        create_response = client.post(
            "/v1/activity-feedback",
            json=feedback_data,
            headers=auth_headers
        )
        feedback_id = create_response.json()["id"]
        
        # Delete feedback
        response = client.delete(
            f"/v1/activity-feedback/{feedback_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 204
        
        # Verify deleted
        get_response = client.get(
            f"/v1/activity-feedback/activity/{test_activity.id}",
            headers=auth_headers
        )
        assert get_response.status_code == 404


class TestPendingPrompts:
    """Test GET /v1/activity-feedback/pending endpoint"""
    
    def test_get_pending_prompts(self, test_athlete, auth_headers):
        """Test getting pending feedback prompts"""
        db = SessionLocal()
        try:
            # Create recent activity (race-like)
            activity = Activity(
                athlete_id=test_athlete.id,
                start_time=datetime.now() - timedelta(hours=1),
                sport="run",
                source="manual",
                distance_m=5000,
                avg_hr=170,
                average_speed=Decimal('3.33'),
                is_race_candidate=True
            )
            db.add(activity)
            db.commit()
            
            # Get pending prompts
            response = client.get(
                "/v1/activity-feedback/pending",
                headers=auth_headers
            )
            
            assert response.status_code == 200
            prompts = response.json()
            assert isinstance(prompts, list)
            # Should have at least one prompt for the race activity
            assert len(prompts) >= 1
            
            db.delete(activity)
            db.commit()
        finally:
            db.close()


class TestActivityAnalysisIntegration:
    """Test integration with activity analysis"""
    
    def test_analysis_includes_perception_prompt(self, test_athlete, test_activity, auth_headers):
        """Test that activity analysis includes perception prompt info"""
        response = client.get(
            f"/v1/activities/{test_activity.id}/analysis",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "perception_prompt" in data
        assert "should_prompt" in data["perception_prompt"]
        assert "prompt_text" in data["perception_prompt"]
        assert "required_fields" in data["perception_prompt"]
        assert "optional_fields" in data["perception_prompt"]
        assert "has_feedback" in data["perception_prompt"]


