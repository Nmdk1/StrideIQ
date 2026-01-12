"""
Integration tests for Training Availability API endpoints

Tests CRUD operations, grid operations, slot counting, and bulk updates.
"""
import pytest
from fastapi.testclient import TestClient
from uuid import uuid4
from main import app
from core.database import SessionLocal
from models import Athlete, TrainingAvailability
from core.security import create_access_token

client = TestClient(app)


@pytest.fixture
def test_athlete():
    """Create a test athlete"""
    db = SessionLocal()
    try:
        athlete = Athlete(
            email=f"test_availability_{uuid4()}@example.com",
            display_name="Test Availability Athlete",
            subscription_tier="free"
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)
        yield athlete
        # Cleanup
        db.query(TrainingAvailability).filter(TrainingAvailability.athlete_id == athlete.id).delete()
        db.delete(athlete)
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


class TestGetAvailabilityGrid:
    """Test GET /v1/training-availability/grid endpoint"""
    
    def test_get_empty_grid(self, test_athlete, auth_headers):
        """Test getting grid when no slots exist (should create all as unavailable)"""
        response = client.get(
            "/v1/training-availability/grid",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["grid"]) == 21  # 7 days × 3 blocks
        assert data["summary"]["total_slots"] == 21
        assert data["summary"]["unavailable_slots"] == 21
        assert data["summary"]["available_slots"] == 0
        assert data["summary"]["preferred_slots"] == 0
    
    def test_get_grid_with_slots(self, test_athlete, auth_headers):
        """Test getting grid with existing slots"""
        # Create some slots
        slot_data = {
            "day_of_week": 1,  # Monday
            "time_block": "morning",
            "status": "preferred"
        }
        client.post("/v1/training-availability", json=slot_data, headers=auth_headers)
        
        # Get grid
        response = client.get(
            "/v1/training-availability/grid",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["grid"]) == 21
        
        # Find Monday morning slot
        monday_morning = next(
            (s for s in data["grid"] if s["day_of_week"] == 1 and s["time_block"] == "morning"),
            None
        )
        assert monday_morning is not None
        assert monday_morning["status"] == "preferred"


class TestCreateAvailabilitySlot:
    """Test POST /v1/training-availability endpoint"""
    
    def test_create_slot_success(self, test_athlete, auth_headers):
        """Test creating availability slot successfully"""
        slot_data = {
            "day_of_week": 1,  # Monday
            "time_block": "morning",
            "status": "preferred",
            "notes": "Best time for intervals"
        }
        
        response = client.post(
            "/v1/training-availability",
            json=slot_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["day_of_week"] == 1
        assert data["time_block"] == "morning"
        assert data["status"] == "preferred"
        assert data["notes"] == "Best time for intervals"
        assert data["athlete_id"] == str(test_athlete.id)
    
    def test_create_slot_duplicate_updates(self, test_athlete, auth_headers):
        """Test that creating duplicate slot updates existing"""
        slot_data = {
            "day_of_week": 1,
            "time_block": "morning",
            "status": "available"
        }
        
        # Create first
        response1 = client.post(
            "/v1/training-availability",
            json=slot_data,
            headers=auth_headers
        )
        assert response1.status_code == 201
        
        # Create again with different status
        slot_data["status"] = "preferred"
        response2 = client.post(
            "/v1/training-availability",
            json=slot_data,
            headers=auth_headers
        )
        
        assert response2.status_code == 201
        assert response2.json()["status"] == "preferred"
        assert response2.json()["id"] == response1.json()["id"]  # Same slot
    
    def test_create_slot_invalid_day(self, test_athlete, auth_headers):
        """Test creating slot with invalid day_of_week"""
        slot_data = {
            "day_of_week": 7,  # Invalid (0-6 only)
            "time_block": "morning",
            "status": "available"
        }
        
        response = client.post(
            "/v1/training-availability",
            json=slot_data,
            headers=auth_headers
        )
        
        assert response.status_code == 400
    
    def test_create_slot_invalid_time_block(self, test_athlete, auth_headers):
        """Test creating slot with invalid time_block"""
        slot_data = {
            "day_of_week": 1,
            "time_block": "midnight",  # Invalid
            "status": "available"
        }
        
        response = client.post(
            "/v1/training-availability",
            json=slot_data,
            headers=auth_headers
        )
        
        assert response.status_code == 400
    
    def test_create_slot_invalid_status(self, test_athlete, auth_headers):
        """Test creating slot with invalid status"""
        slot_data = {
            "day_of_week": 1,
            "time_block": "morning",
            "status": "maybe"  # Invalid
        }
        
        response = client.post(
            "/v1/training-availability",
            json=slot_data,
            headers=auth_headers
        )
        
        assert response.status_code == 400


class TestUpdateAvailabilitySlot:
    """Test PUT /v1/training-availability/{slot_id} endpoint"""
    
    def test_update_slot_success(self, test_athlete, auth_headers):
        """Test updating slot successfully"""
        # Create slot
        slot_data = {
            "day_of_week": 1,
            "time_block": "morning",
            "status": "available"
        }
        create_response = client.post(
            "/v1/training-availability",
            json=slot_data,
            headers=auth_headers
        )
        slot_id = create_response.json()["id"]
        
        # Update slot
        update_data = {
            "status": "preferred",
            "notes": "Updated notes"
        }
        response = client.put(
            f"/v1/training-availability/{slot_id}",
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "preferred"
        assert data["notes"] == "Updated notes"
    
    def test_update_slot_partial(self, test_athlete, auth_headers):
        """Test partial update (only status)"""
        # Create slot
        slot_data = {
            "day_of_week": 1,
            "time_block": "morning",
            "status": "available",
            "notes": "Original notes"
        }
        create_response = client.post(
            "/v1/training-availability",
            json=slot_data,
            headers=auth_headers
        )
        slot_id = create_response.json()["id"]
        
        # Update only status
        update_data = {"status": "preferred"}
        response = client.put(
            f"/v1/training-availability/{slot_id}",
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "preferred"
        assert data["notes"] == "Original notes"  # Unchanged


class TestBulkUpdate:
    """Test PUT /v1/training-availability/bulk endpoint"""
    
    def test_bulk_update_success(self, test_athlete, auth_headers):
        """Test bulk updating multiple slots"""
        slots_data = [
            {"day_of_week": 1, "time_block": "morning", "status": "preferred"},
            {"day_of_week": 1, "time_block": "afternoon", "status": "available"},
            {"day_of_week": 2, "time_block": "evening", "status": "preferred"},
        ]
        
        response = client.put(
            "/v1/training-availability/bulk",
            json=slots_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        
        # Verify slots
        statuses = {s["status"] for s in data}
        assert "preferred" in statuses
        assert "available" in statuses


class TestDeleteAvailabilitySlot:
    """Test DELETE /v1/training-availability/{slot_id} endpoint"""
    
    def test_delete_slot_sets_unavailable(self, test_athlete, auth_headers):
        """Test that deleting sets status to unavailable (doesn't actually delete)"""
        # Create slot
        slot_data = {
            "day_of_week": 1,
            "time_block": "morning",
            "status": "preferred",
            "notes": "Test notes"
        }
        create_response = client.post(
            "/v1/training-availability",
            json=slot_data,
            headers=auth_headers
        )
        slot_id = create_response.json()["id"]
        
        # Delete (sets to unavailable)
        response = client.delete(
            f"/v1/training-availability/{slot_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 204
        
        # Verify it's now unavailable
        get_response = client.get(
            "/v1/training-availability/grid",
            headers=auth_headers
        )
        monday_morning = next(
            (s for s in get_response.json()["grid"] 
             if s["day_of_week"] == 1 and s["time_block"] == "morning"),
            None
        )
        assert monday_morning is not None
        assert monday_morning["status"] == "unavailable"
        assert monday_morning["notes"] is None


class TestAvailabilitySummary:
    """Test GET /v1/training-availability/summary endpoint"""
    
    def test_summary_empty_grid(self, test_athlete, auth_headers):
        """Test summary with empty grid"""
        response = client.get(
            "/v1/training-availability/summary",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_slots"] == 21
        assert data["unavailable_slots"] == 21
        assert data["available_slots"] == 0
        assert data["preferred_slots"] == 0
        assert data["total_available_slots"] == 0
    
    def test_summary_with_slots(self, test_athlete, auth_headers):
        """Test summary with some slots set"""
        # Create some slots
        slots = [
            {"day_of_week": 1, "time_block": "morning", "status": "preferred"},
            {"day_of_week": 1, "time_block": "afternoon", "status": "available"},
            {"day_of_week": 2, "time_block": "evening", "status": "preferred"},
        ]
        client.put("/v1/training-availability/bulk", json=slots, headers=auth_headers)
        
        # Get summary
        response = client.get(
            "/v1/training-availability/summary",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["preferred_slots"] == 2
        assert data["available_slots"] == 1
        assert data["total_available_slots"] == 3
        assert data["unavailable_slots"] == 18
        assert data["total_available_percentage"] > 0


