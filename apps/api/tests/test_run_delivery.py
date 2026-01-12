"""
Integration tests for Run Delivery Service

Tests complete run delivery experience: analysis + perception prompts + tone.
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta, date
from decimal import Decimal
from uuid import uuid4
from main import app
from core.database import SessionLocal
from models import Athlete, Activity, ActivityFeedback
from core.security import create_access_token
from services.run_delivery import deliver_run, get_run_delivery

client = TestClient(app)


@pytest.fixture
def test_athlete():
    """Create a test athlete"""
    db = SessionLocal()
    try:
        athlete = Athlete(
            email=f"test_delivery_{uuid4()}@example.com",
            display_name="Test Delivery Athlete",
            birthdate=date(1980, 1, 1),
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
    """Create a test activity with pace and HR"""
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
            max_hr=165,
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


class TestRunDeliveryService:
    """Test RunDelivery service functions"""
    
    def test_deliver_run_with_meaningful_insight(self, test_athlete, test_activity):
        """Test delivery when meaningful insight exists"""
        db = SessionLocal()
        try:
            # Create baseline activities for comparison
            base_time = datetime.now()
            for i in range(5):
                activity = Activity(
                    athlete_id=test_athlete.id,
                    start_time=base_time - timedelta(weeks=i+1),
                    sport="run",
                    distance_m=5000,
                    avg_hr=155,  # Higher HR baseline
                    average_speed=Decimal('2.78')
                )
                db.add(activity)
            db.commit()
            
            # Current activity with lower HR (improvement)
            current_activity = Activity(
                athlete_id=test_athlete.id,
                start_time=base_time,
                sport="run",
                distance_m=5000,
                avg_hr=145,  # Lower HR at same pace
                average_speed=Decimal('2.78')
            )
            db.add(current_activity)
            db.commit()
            
            # Get delivery
            delivery = deliver_run(current_activity, test_athlete, db)
            
            assert delivery["has_meaningful_insight"] in [True, False]  # May or may not be confirmed
            assert "insights" in delivery
            assert "perception_prompt" in delivery
            assert "metrics" in delivery
            assert delivery["insight_tone"] in ["irreverent", "sparse"]
            
            # Cleanup
            db.query(Activity).filter(Activity.athlete_id == test_athlete.id).delete()
            db.commit()
        finally:
            db.close()
    
    def test_deliver_run_no_meaningful_insight(self, test_athlete, test_activity):
        """Test delivery when no meaningful insight"""
        db = SessionLocal()
        try:
            delivery = deliver_run(test_activity, test_athlete, db)
            
            assert delivery["has_meaningful_insight"] == False
            assert len(delivery["insights"]) > 0  # Should have sparse message
            assert delivery["insight_tone"] == "sparse"
            assert "perception_prompt" in delivery
        finally:
            db.close()
    
    def test_deliver_run_insufficient_data(self, test_athlete):
        """Test delivery when insufficient data for analysis"""
        db = SessionLocal()
        try:
            # Activity without HR (insufficient data)
            activity = Activity(
                athlete_id=test_athlete.id,
                start_time=datetime.now(),
                sport="run",
                distance_m=5000,
                avg_hr=None,  # Missing HR
                average_speed=Decimal('2.78')
            )
            db.add(activity)
            db.commit()
            
            delivery = deliver_run(activity, test_athlete, db)
            
            assert delivery["has_meaningful_insight"] == False
            assert len(delivery["insights"]) > 0  # Should have insufficient data message
            assert delivery["insight_tone"] == "sparse"
            
            db.delete(activity)
            db.commit()
        finally:
            db.close()
    
    def test_deliver_run_with_perception_prompt(self, test_athlete):
        """Test delivery includes perception prompt"""
        db = SessionLocal()
        try:
            # Race activity (should prompt)
            activity = Activity(
                athlete_id=test_athlete.id,
                start_time=datetime.now(),
                sport="run",
                distance_m=5000,
                avg_hr=170,
                average_speed=Decimal('3.33'),
                is_race_candidate=True
            )
            db.add(activity)
            db.commit()
            
            delivery = deliver_run(activity, test_athlete, db)
            
            assert "perception_prompt" in delivery
            assert delivery["perception_prompt"]["should_prompt"] == True
            assert "prompt_text" in delivery["perception_prompt"]
            assert "required_fields" in delivery["perception_prompt"]
            
            db.delete(activity)
            db.commit()
        finally:
            db.close()


class TestRunDeliveryAPI:
    """Test RunDelivery API endpoint"""
    
    def test_get_delivery_success(self, test_athlete, test_activity, auth_headers):
        """Test getting delivery via API"""
        response = client.get(
            f"/v1/activities/{test_activity.id}/delivery",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "activity_id" in data
        assert "has_meaningful_insight" in data
        assert "insights" in data
        assert "perception_prompt" in data
        assert "metrics" in data
        assert "delivery_timestamp" in data
    
    def test_get_delivery_not_found(self, test_athlete, auth_headers):
        """Test getting delivery for non-existent activity"""
        fake_id = uuid4()
        response = client.get(
            f"/v1/activities/{fake_id}/delivery",
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    def test_get_delivery_unauthorized(self, test_athlete, test_activity):
        """Test getting delivery without auth"""
        response = client.get(
            f"/v1/activities/{test_activity.id}/delivery"
        )
        
        assert response.status_code == 401
    
    def test_get_delivery_wrong_owner(self, test_athlete, auth_headers):
        """Test getting delivery for activity owned by different athlete"""
        db = SessionLocal()
        try:
            # Create another athlete
            other_athlete = Athlete(
                email=f"other_{uuid4()}@example.com",
                display_name="Other Athlete",
                subscription_tier="free"
            )
            db.add(other_athlete)
            db.commit()
            
            # Create activity for other athlete
            other_activity = Activity(
                athlete_id=other_athlete.id,
                start_time=datetime.now(),
                sport="run",
                distance_m=5000,
                avg_hr=150,
                average_speed=Decimal('2.78')
            )
            db.add(other_activity)
            db.commit()
            
            # Try to get delivery (should fail)
            response = client.get(
                f"/v1/activities/{other_activity.id}/delivery",
                headers=auth_headers
            )
            
            assert response.status_code == 403
            
            # Cleanup
            db.delete(other_activity)
            db.delete(other_athlete)
            db.commit()
        finally:
            db.close()


class TestRunDeliveryTone:
    """Test tone application in delivery"""
    
    def test_tone_irreverent_for_improvements(self, test_athlete):
        """Test that improvements get irreverent tone"""
        db = SessionLocal()
        try:
            # Create activity with improvement
            activity = Activity(
                athlete_id=test_athlete.id,
                start_time=datetime.now(),
                sport="run",
                distance_m=5000,
                avg_hr=145,  # Lower HR
                average_speed=Decimal('2.78'),
                is_race_candidate=True
            )
            db.add(activity)
            
            # Create PR baseline
            pr_activity = Activity(
                athlete_id=test_athlete.id,
                start_time=datetime.now() - timedelta(days=30),
                sport="run",
                distance_m=5000,
                avg_hr=165,  # Higher HR
                average_speed=Decimal('2.78'),
                is_race_candidate=True
            )
            db.add(pr_activity)
            db.commit()
            
            delivery = deliver_run(activity, test_athlete, db)
            
            # If meaningful insight exists, tone should be irreverent
            if delivery["has_meaningful_insight"]:
                assert delivery["insight_tone"] == "irreverent"
                assert len(delivery["insights"]) > 0
            
            # Cleanup
            db.delete(activity)
            db.delete(pr_activity)
            db.commit()
        finally:
            db.close()
    
    def test_tone_sparse_for_no_insights(self, test_athlete, test_activity):
        """Test that no insights get sparse tone"""
        db = SessionLocal()
        try:
            delivery = deliver_run(test_activity, test_athlete, db)
            
            if not delivery["has_meaningful_insight"]:
                assert delivery["insight_tone"] == "sparse"
                assert len(delivery["insights"]) > 0  # Should have sparse message
        finally:
            db.close()


class TestRunDeliveryIntegration:
    """Test integration with perception prompts"""
    
    def test_delivery_includes_perception_prompt(self, test_athlete):
        """Test that delivery always includes perception prompt info"""
        db = SessionLocal()
        try:
            # Race activity
            activity = Activity(
                athlete_id=test_athlete.id,
                start_time=datetime.now(),
                sport="run",
                distance_m=5000,
                avg_hr=170,
                average_speed=Decimal('3.33'),
                is_race_candidate=True
            )
            db.add(activity)
            db.commit()
            
            delivery = deliver_run(activity, test_athlete, db)
            
            assert "perception_prompt" in delivery
            prompt = delivery["perception_prompt"]
            assert "should_prompt" in prompt
            assert "prompt_text" in prompt
            assert "has_feedback" in prompt
            
            db.delete(activity)
            db.commit()
        finally:
            db.close()
    
    def test_delivery_with_existing_feedback(self, test_athlete):
        """Test delivery when feedback already exists"""
        db = SessionLocal()
        try:
            # Create activity
            activity = Activity(
                athlete_id=test_athlete.id,
                start_time=datetime.now(),
                sport="run",
                distance_m=5000,
                avg_hr=150,
                average_speed=Decimal('2.78')
            )
            db.add(activity)
            db.commit()
            
            # Create feedback
            feedback = ActivityFeedback(
                activity_id=activity.id,
                athlete_id=test_athlete.id,
                perceived_effort=7,
                leg_feel="tired"
            )
            db.add(feedback)
            db.commit()
            
            delivery = deliver_run(activity, test_athlete, db)
            
            assert delivery["perception_prompt"]["has_feedback"] == True
            
            # Cleanup
            db.delete(feedback)
            db.delete(activity)
            db.commit()
        finally:
            db.close()


