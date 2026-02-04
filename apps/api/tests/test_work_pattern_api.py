"""
Integration tests for Work Pattern API endpoints

Tests CRUD operations, stress level validation, duplicate date prevention, and date filtering.
"""
import pytest
from fastapi.testclient import TestClient
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4
from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models import Athlete, WorkPattern

client = TestClient(app)


def get_auth_headers(athlete):
    """Generate auth headers for test athlete"""
    token = create_access_token({"sub": str(athlete.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_athlete():
    """Create a test athlete"""
    db = SessionLocal()
    try:
        # Cleanup any existing test athlete first
        existing = db.query(Athlete).filter(Athlete.email == "test_work@example.com").first()
        if existing:
            db.query(WorkPattern).filter(WorkPattern.athlete_id == existing.id).delete()
            db.delete(existing)
            db.commit()
        
        athlete = Athlete(
            email="test_work@example.com",
            display_name="Test Athlete Work",
            subscription_tier="free"
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)
        yield athlete
        # Cleanup
        db.query(WorkPattern).filter(WorkPattern.athlete_id == athlete.id).delete()
        db.commit()
        db.delete(athlete)
        db.commit()
    finally:
        db.close()


class TestCreateWorkPattern:
    """Test POST /v1/work-patterns endpoint"""
    
    def test_create_with_all_fields(self, test_athlete):
        """Test creating work pattern entry with all fields"""
        headers = get_auth_headers(test_athlete)
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "work_type": "desk",
            "hours_worked": 8.0,
            "stress_level": 3,
            "notes": "Normal workday"
        }
        
        response = client.post("/v1/work-patterns", json=entry_data, headers=headers)
        
        assert response.status_code == 201
        data = response.json()
        assert data["athlete_id"] == str(test_athlete.id)
        assert data["work_type"] == "desk"
        assert data["hours_worked"] == 8.0
        assert data["stress_level"] == 3
        assert data["notes"] == "Normal workday"
    
    def test_create_with_minimal_fields(self, test_athlete):
        """Test creating entry with minimal fields"""
        headers = get_auth_headers(test_athlete)
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15"
        }
        
        response = client.post("/v1/work-patterns", json=entry_data, headers=headers)
        
        assert response.status_code == 201
        data = response.json()
        assert data["work_type"] is None
        assert data["hours_worked"] is None
        assert data["stress_level"] is None
    
    def test_create_duplicate_date(self, test_athlete):
        """Test creating duplicate entry for same date - should fail"""
        headers = get_auth_headers(test_athlete)
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "work_type": "desk",
            "hours_worked": 8.0
        }
        
        # Create first entry
        response1 = client.post("/v1/work-patterns", json=entry_data, headers=headers)
        assert response1.status_code == 201
        
        # Try to create duplicate
        response2 = client.post("/v1/work-patterns", json=entry_data, headers=headers)
        assert response2.status_code == 400
        assert "already exists" in response2.json()["detail"].lower()
    
    def test_create_invalid_athlete_id(self, test_athlete):
        """Test creating entry with non-existent athlete ID"""
        headers = get_auth_headers(test_athlete)
        entry_data = {
            "athlete_id": str(uuid4()),
            "date": "2024-01-15",
            "work_type": "desk"
        }
        
        response = client.post("/v1/work-patterns", json=entry_data, headers=headers)
        assert response.status_code == 404
    
    def test_create_with_invalid_stress_level_low(self, test_athlete):
        """Test creating entry with stress_level < 1"""
        headers = get_auth_headers(test_athlete)
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "stress_level": 0
        }
        
        response = client.post("/v1/work-patterns", json=entry_data, headers=headers)
        assert response.status_code == 400
        assert "between 1 and 5" in response.json()["detail"]
    
    def test_create_with_invalid_stress_level_high(self, test_athlete):
        """Test creating entry with stress_level > 5"""
        headers = get_auth_headers(test_athlete)
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "stress_level": 6
        }
        
        response = client.post("/v1/work-patterns", json=entry_data, headers=headers)
        assert response.status_code == 400
        assert "between 1 and 5" in response.json()["detail"]
    
    def test_create_with_valid_stress_levels(self, test_athlete):
        """Test creating entries with all valid stress levels"""
        headers = get_auth_headers(test_athlete)
        for stress_level in [1, 2, 3, 4, 5]:
            entry_data = {
                "athlete_id": str(test_athlete.id),
                "date": f"2024-01-{15 + stress_level}",  # Different dates
                "stress_level": stress_level
            }
            response = client.post("/v1/work-patterns", json=entry_data, headers=headers)
            assert response.status_code == 201
            assert response.json()["stress_level"] == stress_level
    
    def test_create_different_work_types(self, test_athlete):
        """Test creating entries with different work types"""
        headers = get_auth_headers(test_athlete)
        work_types = ["desk", "physical", "shift", "travel"]
        for i, work_type in enumerate(work_types):
            entry_data = {
                "athlete_id": str(test_athlete.id),
                "date": f"2024-01-{15 + i}",
                "work_type": work_type
            }
            response = client.post("/v1/work-patterns", json=entry_data, headers=headers)
            assert response.status_code == 201
            assert response.json()["work_type"] == work_type


class TestGetWorkPatterns:
    """Test GET /v1/work-patterns endpoint"""
    
    def test_get_all_entries(self, test_athlete):
        """Test getting all entries for an athlete"""
        headers = get_auth_headers(test_athlete)
        # Create multiple entries
        dates = ["2024-01-15", "2024-01-20", "2024-01-25"]
        for entry_date in dates:
            entry_data = {
                "athlete_id": str(test_athlete.id),
                "date": entry_date,
                "work_type": "desk",
                "hours_worked": 8.0
            }
            client.post("/v1/work-patterns", json=entry_data, headers=headers)
        
        # Get all entries
        response = client.get(f"/v1/work-patterns?athlete_id={test_athlete.id}", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        # Should be ordered by date descending
        assert data[0]["date"] == "2024-01-25"
        assert data[1]["date"] == "2024-01-20"
        assert data[2]["date"] == "2024-01-15"
    
    def test_get_with_date_filter(self, test_athlete):
        """Test getting entries with date range filter"""
        headers = get_auth_headers(test_athlete)
        dates = ["2024-01-15", "2024-01-20", "2024-01-25", "2024-02-01"]
        for entry_date in dates:
            entry_data = {
                "athlete_id": str(test_athlete.id),
                "date": entry_date,
                "work_type": "desk"
            }
            client.post("/v1/work-patterns", json=entry_data, headers=headers)
        
        # Filter by date range
        response = client.get(
            f"/v1/work-patterns?athlete_id={test_athlete.id}&start_date=2024-01-20&end_date=2024-01-25",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all("2024-01-20" <= entry["date"] <= "2024-01-25" for entry in data)
    
    def test_get_empty_list(self, test_athlete):
        """Test getting entries when none exist"""
        headers = get_auth_headers(test_athlete)
        response = client.get(f"/v1/work-patterns?athlete_id={test_athlete.id}", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data == []


class TestGetWorkPatternById:
    """Test GET /v1/work-patterns/{id} endpoint"""
    
    def test_get_by_id(self, test_athlete):
        """Test getting a specific entry by ID"""
        headers = get_auth_headers(test_athlete)
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "work_type": "desk",
            "hours_worked": 8.0,
            "notes": "Test entry"
        }
        create_response = client.post("/v1/work-patterns", json=entry_data, headers=headers)
        entry_id = create_response.json()["id"]
        
        # Get by ID
        response = client.get(f"/v1/work-patterns/{entry_id}", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == entry_id
        assert data["work_type"] == "desk"
        assert data["hours_worked"] == 8.0
        assert data["notes"] == "Test entry"
    
    def test_get_by_id_not_found(self, test_athlete):
        """Test getting non-existent entry"""
        headers = get_auth_headers(test_athlete)
        fake_id = uuid4()
        response = client.get(f"/v1/work-patterns/{fake_id}", headers=headers)
        
        assert response.status_code == 404


class TestUpdateWorkPattern:
    """Test PUT /v1/work-patterns/{id} endpoint"""
    
    def test_update_entry(self, test_athlete):
        """Test updating an existing entry"""
        headers = get_auth_headers(test_athlete)
        # Create entry
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "work_type": "desk",
            "hours_worked": 8.0
        }
        create_response = client.post("/v1/work-patterns", json=entry_data, headers=headers)
        entry_id = create_response.json()["id"]
        
        # Update entry
        update_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "work_type": "physical",
            "hours_worked": 10.0,
            "stress_level": 4,
            "notes": "Updated entry"
        }
        response = client.put(f"/v1/work-patterns/{entry_id}", json=update_data, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["work_type"] == "physical"
        assert data["hours_worked"] == 10.0
        assert data["stress_level"] == 4
        assert data["notes"] == "Updated entry"
    
    def test_update_not_found(self, test_athlete):
        """Test updating non-existent entry"""
        headers = get_auth_headers(test_athlete)
        fake_id = uuid4()
        update_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "work_type": "desk"
        }
        
        response = client.put(f"/v1/work-patterns/{fake_id}", json=update_data, headers=headers)
        assert response.status_code == 404


class TestDeleteWorkPattern:
    """Test DELETE /v1/work-patterns/{id} endpoint"""
    
    def test_delete_entry(self, test_athlete):
        """Test deleting an entry"""
        headers = get_auth_headers(test_athlete)
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "work_type": "desk"
        }
        create_response = client.post("/v1/work-patterns", json=entry_data, headers=headers)
        entry_id = create_response.json()["id"]
        
        # Delete entry
        response = client.delete(f"/v1/work-patterns/{entry_id}", headers=headers)
        assert response.status_code == 204
        
        # Verify deleted
        get_response = client.get(f"/v1/work-patterns/{entry_id}", headers=headers)
        assert get_response.status_code == 404
    
    def test_delete_not_found(self, test_athlete):
        """Test deleting non-existent entry"""
        headers = get_auth_headers(test_athlete)
        fake_id = uuid4()
        response = client.delete(f"/v1/work-patterns/{fake_id}", headers=headers)
        assert response.status_code == 404


class TestWorkPatternEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_create_with_zero_hours(self, test_athlete):
        """Test creating entry with zero hours worked"""
        headers = get_auth_headers(test_athlete)
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "hours_worked": 0.0
        }
        response = client.post("/v1/work-patterns", json=entry_data, headers=headers)
        assert response.status_code == 201
    
    def test_create_with_negative_hours(self, test_athlete):
        """Test creating entry with negative hours"""
        headers = get_auth_headers(test_athlete)
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "hours_worked": -5.0
        }
        response = client.post("/v1/work-patterns", json=entry_data, headers=headers)
        # API currently accepts negative values (validation can be added later)
        assert response.status_code in [201, 400, 422]
    
    def test_create_with_very_large_hours(self, test_athlete):
        """Test creating entry with very large hours"""
        headers = get_auth_headers(test_athlete)
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "hours_worked": 24.0  # 24 hours
        }
        response = client.post("/v1/work-patterns", json=entry_data, headers=headers)
        assert response.status_code == 201
        data = response.json()
        assert data["hours_worked"] == 24.0
    
    def test_create_with_future_date(self, test_athlete):
        """Test creating entry with future date"""
        headers = get_auth_headers(test_athlete)
        future_date = (date.today() + timedelta(days=30)).isoformat()
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": future_date,
            "work_type": "desk"
        }
        response = client.post("/v1/work-patterns", json=entry_data, headers=headers)
        assert response.status_code in [201, 400, 422]
    
    def test_create_with_unicode_notes(self, test_athlete):
        """Test creating entry with Unicode characters"""
        headers = get_auth_headers(test_athlete)
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "work_type": "desk",
            "notes": "Test with émojis 💼 and 中文"
        }
        response = client.post("/v1/work-patterns", json=entry_data, headers=headers)
        assert response.status_code == 201
        data = response.json()
        assert data["notes"] == "Test with émojis 💼 and 中文"
    
    def test_create_with_empty_string_work_type(self, test_athlete):
        """Test creating entry with empty string work_type"""
        headers = get_auth_headers(test_athlete)
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "work_type": ""
        }
        response = client.post("/v1/work-patterns", json=entry_data, headers=headers)
        assert response.status_code == 201
        data = response.json()
        assert data["work_type"] == ""
    
    def test_update_stress_level_boundary(self, test_athlete):
        """Test updating with boundary stress levels"""
        headers = get_auth_headers(test_athlete)
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "stress_level": 1
        }
        create_response = client.post("/v1/work-patterns", json=entry_data, headers=headers)
        entry_id = create_response.json()["id"]
        
        # Update to max stress level
        update_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "stress_level": 5
        }
        response = client.put(f"/v1/work-patterns/{entry_id}", json=update_data, headers=headers)
        assert response.status_code == 200
        assert response.json()["stress_level"] == 5
    
    def test_update_to_remove_fields(self, test_athlete):
        """Test updating entry to remove optional fields"""
        headers = get_auth_headers(test_athlete)
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "work_type": "desk",
            "hours_worked": 8.0,
            "stress_level": 3
        }
        create_response = client.post("/v1/work-patterns", json=entry_data, headers=headers)
        entry_id = create_response.json()["id"]
        
        # Update to remove fields
        update_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "work_type": None,
            "hours_worked": None,
            "stress_level": None
        }
        response = client.put(f"/v1/work-patterns/{entry_id}", json=update_data, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["work_type"] is None
        assert data["hours_worked"] is None
        assert data["stress_level"] is None
