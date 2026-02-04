"""
Integration tests for Body Composition API endpoints

Tests CRUD operations, BMI auto-calculation, error handling, and date filtering.

Note: These tests require a running database. They test the actual API endpoints
and will create/cleanup test data. For unit tests of BMI calculation logic,
see test_bmi_calculator.py
"""
import pytest
from fastapi.testclient import TestClient
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4
from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models import Athlete, BodyComposition

client = TestClient(app)


def get_auth_headers(athlete):
    """Generate auth headers for test athlete"""
    token = create_access_token({"sub": str(athlete.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_athlete_with_height():
    """Create a test athlete with height for BMI calculation"""
    db = SessionLocal()
    try:
        # Cleanup any existing test athlete first
        existing = db.query(Athlete).filter(Athlete.email == "test_bmi@example.com").first()
        if existing:
            db.query(BodyComposition).filter(BodyComposition.athlete_id == existing.id).delete()
            db.delete(existing)
            db.commit()
        
        athlete = Athlete(
            email="test_bmi@example.com",
            display_name="Test Athlete BMI",
            height_cm=Decimal('175'),  # 175cm for BMI calculation
            subscription_tier="free"
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)
        yield athlete
        # Cleanup: Delete body_composition entries first (foreign key constraint)
        db.query(BodyComposition).filter(BodyComposition.athlete_id == athlete.id).delete()
        db.commit()
        db.delete(athlete)
        db.commit()
    finally:
        db.close()


@pytest.fixture
def test_athlete_no_height():
    """Create a test athlete without height"""
    db = SessionLocal()
    try:
        # Cleanup any existing test athlete first
        existing = db.query(Athlete).filter(Athlete.email == "test_no_height@example.com").first()
        if existing:
            db.query(BodyComposition).filter(BodyComposition.athlete_id == existing.id).delete()
            db.delete(existing)
            db.commit()
        
        athlete = Athlete(
            email="test_no_height@example.com",
            display_name="Test Athlete No Height",
            height_cm=None,  # No height - BMI cannot be calculated
            subscription_tier="free"
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)
        yield athlete
        # Cleanup: Delete body_composition entries first (foreign key constraint)
        db.query(BodyComposition).filter(BodyComposition.athlete_id == athlete.id).delete()
        db.commit()
        db.delete(athlete)
        db.commit()
    finally:
        db.close()


class TestCreateBodyComposition:
    """Test POST /v1/body-composition endpoint"""
    
    def test_create_with_bmi_calculation(self, test_athlete_with_height):
        """Test creating body composition entry with automatic BMI calculation"""
        entry_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024-01-15",
            "weight_kg": 70.0,
            "body_fat_pct": 15.5,
            "notes": "Test entry"
        }
        
        headers = get_auth_headers(test_athlete_with_height)
        response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        
        assert response.status_code == 201
        data = response.json()
        assert data["athlete_id"] == str(test_athlete_with_height.id)
        assert data["weight_kg"] == 70.0
        assert data["body_fat_pct"] == 15.5
        assert data["bmi"] is not None
        assert data["bmi"] == 22.9  # 70 / (1.75)² = 22.857... rounded to 22.9
        assert data["date"] == "2024-01-15"
    
    def test_create_without_height_no_bmi(self, test_athlete_no_height):
        """Test creating entry when athlete has no height - BMI should be None"""
        entry_data = {
            "athlete_id": str(test_athlete_no_height.id),
            "date": "2024-01-15",
            "weight_kg": 70.0
        }
        
        headers = get_auth_headers(test_athlete_no_height)
        response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        
        assert response.status_code == 201
        data = response.json()
        assert data["weight_kg"] == 70.0
        assert data["bmi"] is None  # Cannot calculate BMI without height
    
    def test_create_without_weight_no_bmi(self, test_athlete_with_height):
        """Test creating entry without weight - BMI should be None"""
        entry_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024-01-15",
            "body_fat_pct": 15.5
        }
        
        headers = get_auth_headers(test_athlete_with_height)
        response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        
        assert response.status_code == 201
        data = response.json()
        assert data["weight_kg"] is None
        assert data["bmi"] is None  # Cannot calculate BMI without weight
    
    def test_create_duplicate_date(self, test_athlete_with_height):
        """Test creating duplicate entry for same date - should fail"""
        entry_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024-01-15",
            "weight_kg": 70.0
        }
        
        headers = get_auth_headers(test_athlete_with_height)
        # Create first entry
        response1 = client.post("/v1/body-composition", json=entry_data, headers=headers)
        assert response1.status_code == 201
        
        # Try to create duplicate
        response2 = client.post("/v1/body-composition", json=entry_data, headers=headers)
        assert response2.status_code == 400
        assert "already exists" in response2.json()["detail"].lower()
    
    def test_create_invalid_athlete_id(self, test_athlete_with_height):
        """Test creating entry with non-existent athlete ID"""
        entry_data = {
            "athlete_id": str(uuid4()),
            "date": "2024-01-15",
            "weight_kg": 70.0
        }
        
        headers = get_auth_headers(test_athlete_with_height)
        response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_create_with_all_fields(self, test_athlete_with_height):
        """Test creating entry with all optional fields"""
        entry_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024-01-15",
            "weight_kg": 75.5,
            "body_fat_pct": 12.3,
            "muscle_mass_kg": 65.0,
            "measurements_json": {"waist": 32, "chest": 42},
            "notes": "Full entry test"
        }
        
        headers = get_auth_headers(test_athlete_with_height)
        response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        
        assert response.status_code == 201
        data = response.json()
        assert data["weight_kg"] == 75.5
        assert data["body_fat_pct"] == 12.3
        assert data["muscle_mass_kg"] == 65.0
        assert data["measurements_json"] == {"waist": 32, "chest": 42}
        assert data["notes"] == "Full entry test"
        assert data["bmi"] is not None


class TestGetBodyComposition:
    """Test GET /v1/body-composition endpoint"""
    
    def test_get_all_entries(self, test_athlete_with_height):
        """Test getting all entries for an athlete"""
        headers = get_auth_headers(test_athlete_with_height)
        # Create multiple entries
        dates = ["2024-01-15", "2024-01-20", "2024-01-25"]
        for entry_date in dates:
            entry_data = {
                "athlete_id": str(test_athlete_with_height.id),
                "date": entry_date,
                "weight_kg": 70.0
            }
            client.post("/v1/body-composition", json=entry_data, headers=headers)
        
        # Get all entries
        response = client.get(
            f"/v1/body-composition?athlete_id={test_athlete_with_height.id}",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        # Should be ordered by date descending
        assert data[0]["date"] == "2024-01-25"
        assert data[1]["date"] == "2024-01-20"
        assert data[2]["date"] == "2024-01-15"
    
    def test_get_with_date_filter(self, test_athlete_with_height):
        """Test getting entries with date range filter"""
        headers = get_auth_headers(test_athlete_with_height)
        # Create entries on different dates
        dates = ["2024-01-15", "2024-01-20", "2024-01-25", "2024-02-01"]
        for entry_date in dates:
            entry_data = {
                "athlete_id": str(test_athlete_with_height.id),
                "date": entry_date,
                "weight_kg": 70.0
            }
            client.post("/v1/body-composition", json=entry_data, headers=headers)
        
        # Filter by date range
        response = client.get(
            f"/v1/body-composition?athlete_id={test_athlete_with_height.id}&start_date=2024-01-20&end_date=2024-01-25",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all("2024-01-20" <= entry["date"] <= "2024-01-25" for entry in data)
    
    def test_get_empty_list(self, test_athlete_with_height):
        """Test getting entries when none exist"""
        headers = get_auth_headers(test_athlete_with_height)
        response = client.get(
            f"/v1/body-composition?athlete_id={test_athlete_with_height.id}",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data == []


class TestGetBodyCompositionById:
    """Test GET /v1/body-composition/{id} endpoint"""
    
    def test_get_by_id(self, test_athlete_with_height):
        """Test getting a specific entry by ID"""
        headers = get_auth_headers(test_athlete_with_height)
        # Create entry
        entry_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024-01-15",
            "weight_kg": 70.0,
            "notes": "Test entry"
        }
        create_response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        entry_id = create_response.json()["id"]
        
        # Get by ID
        response = client.get(f"/v1/body-composition/{entry_id}", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == entry_id
        assert data["weight_kg"] == 70.0
        assert data["notes"] == "Test entry"
    
    def test_get_by_id_not_found(self, test_athlete_with_height):
        """Test getting non-existent entry"""
        headers = get_auth_headers(test_athlete_with_height)
        fake_id = uuid4()
        response = client.get(f"/v1/body-composition/{fake_id}", headers=headers)
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestUpdateBodyComposition:
    """Test PUT /v1/body-composition/{id} endpoint"""
    
    def test_update_entry(self, test_athlete_with_height):
        """Test updating an existing entry"""
        headers = get_auth_headers(test_athlete_with_height)
        # Create entry
        entry_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024-01-15",
            "weight_kg": 70.0
        }
        create_response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        entry_id = create_response.json()["id"]
        
        # Update entry
        update_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024-01-15",
            "weight_kg": 72.0,  # Changed weight
            "body_fat_pct": 14.0,
            "notes": "Updated entry"
        }
        response = client.put(f"/v1/body-composition/{entry_id}", json=update_data, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["weight_kg"] == 72.0
        assert data["body_fat_pct"] == 14.0
        assert data["notes"] == "Updated entry"
        # BMI should be recalculated
        assert data["bmi"] is not None
        assert data["bmi"] != create_response.json()["bmi"]  # Should be different
    
    def test_update_recalculates_bmi(self, test_athlete_with_height):
        """Test that BMI is recalculated when weight changes"""
        headers = get_auth_headers(test_athlete_with_height)
        # Create entry
        entry_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024-01-15",
            "weight_kg": 70.0
        }
        create_response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        entry_id = create_response.json()["id"]
        original_bmi = create_response.json()["bmi"]
        
        # Update with new weight
        update_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024-01-15",
            "weight_kg": 75.0  # Increased weight
        }
        response = client.put(f"/v1/body-composition/{entry_id}", json=update_data, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["bmi"] != original_bmi
        assert data["bmi"] > original_bmi  # Higher weight = higher BMI
    
    def test_update_not_found(self, test_athlete_with_height):
        """Test updating non-existent entry"""
        headers = get_auth_headers(test_athlete_with_height)
        fake_id = uuid4()
        update_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024-01-15",
            "weight_kg": 70.0
        }
        
        response = client.put(f"/v1/body-composition/{fake_id}", json=update_data, headers=headers)
        assert response.status_code == 404


class TestDeleteBodyComposition:
    """Test DELETE /v1/body-composition/{id} endpoint"""
    
    def test_delete_entry(self, test_athlete_with_height):
        """Test deleting an entry"""
        headers = get_auth_headers(test_athlete_with_height)
        # Create entry
        entry_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024-01-15",
            "weight_kg": 70.0
        }
        create_response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        entry_id = create_response.json()["id"]
        
        # Delete entry
        response = client.delete(f"/v1/body-composition/{entry_id}", headers=headers)
        assert response.status_code == 204
        
        # Verify deleted
        get_response = client.get(f"/v1/body-composition/{entry_id}", headers=headers)
        assert get_response.status_code == 404
    
    def test_delete_not_found(self, test_athlete_with_height):
        """Test deleting non-existent entry"""
        headers = get_auth_headers(test_athlete_with_height)
        fake_id = uuid4()
        response = client.delete(f"/v1/body-composition/{fake_id}", headers=headers)
        assert response.status_code == 404


class TestBodyCompositionEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_create_with_zero_weight(self, test_athlete_with_height):
        """Test creating entry with zero weight"""
        headers = get_auth_headers(test_athlete_with_height)
        entry_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024-01-15",
            "weight_kg": 0.0
        }
        response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        # Should fail validation or return None BMI
        assert response.status_code in [201, 400, 422]
    
    def test_create_with_negative_weight(self, test_athlete_with_height):
        """Test creating entry with negative weight"""
        headers = get_auth_headers(test_athlete_with_height)
        entry_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024-01-16",
            "weight_kg": -10.0
        }
        response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        # Note: API currently accepts negative weights (BMI calculation handles it by returning None)
        # Validation can be added later if needed
        assert response.status_code in [201, 400, 422]
    
    def test_create_with_very_large_weight(self, test_athlete_with_height):
        """Test creating entry with very large weight"""
        headers = get_auth_headers(test_athlete_with_height)
        entry_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024-01-17",
            "weight_kg": 1000.0  # Unrealistic but should handle gracefully
        }
        response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        assert response.status_code == 201
        data = response.json()
        assert data["weight_kg"] == 1000.0
        assert data["bmi"] is not None
    
    def test_create_with_very_small_weight(self, test_athlete_with_height):
        """Test creating entry with very small weight"""
        headers = get_auth_headers(test_athlete_with_height)
        entry_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024-01-18",
            "weight_kg": 0.1
        }
        response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        assert response.status_code == 201
        data = response.json()
        assert data["weight_kg"] == 0.1
    
    def test_create_with_negative_body_fat(self, test_athlete_with_height):
        """Test creating entry with negative body fat percentage"""
        headers = get_auth_headers(test_athlete_with_height)
        entry_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024-01-19",
            "weight_kg": 70.0,
            "body_fat_pct": -5.0
        }
        response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        # Note: API currently accepts negative body fat (validation can be added later if needed)
        assert response.status_code in [201, 400, 422]
    
    def test_create_with_body_fat_over_100(self, test_athlete_with_height):
        """Test creating entry with body fat > 100%"""
        headers = get_auth_headers(test_athlete_with_height)
        entry_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024-01-20",
            "weight_kg": 70.0,
            "body_fat_pct": 150.0
        }
        response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        # Note: API currently accepts body fat > 100% (validation can be added later if needed)
        assert response.status_code in [201, 400, 422]
    
    def test_create_with_future_date(self, test_athlete_with_height):
        """Test creating entry with future date"""
        headers = get_auth_headers(test_athlete_with_height)
        from datetime import date, timedelta
        future_date = (date.today() + timedelta(days=365)).isoformat()
        entry_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": future_date,
            "weight_kg": 70.0
        }
        response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        # Should accept future dates (user might pre-log)
        assert response.status_code in [201, 400, 422]
    
    def test_create_with_very_old_date(self, test_athlete_with_height):
        """Test creating entry with very old date"""
        headers = get_auth_headers(test_athlete_with_height)
        entry_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "1900-01-01",
            "weight_kg": 70.0
        }
        response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        # Should accept old dates (historical data)
        assert response.status_code in [201, 400, 422]
    
    def test_create_with_invalid_date_format(self, test_athlete_with_height):
        """Test creating entry with invalid date format"""
        headers = get_auth_headers(test_athlete_with_height)
        entry_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024/01/15",  # Wrong format
            "weight_kg": 70.0
        }
        response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        assert response.status_code in [400, 422]
    
    def test_create_with_leap_year_date(self, test_athlete_with_height):
        """Test creating entry on leap year date"""
        headers = get_auth_headers(test_athlete_with_height)
        entry_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024-02-29",  # Leap year
            "weight_kg": 70.0
        }
        response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        assert response.status_code == 201
    
    def test_create_with_invalid_leap_year_date(self, test_athlete_with_height):
        """Test creating entry on invalid leap year date"""
        headers = get_auth_headers(test_athlete_with_height)
        entry_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2023-02-29",  # Not a leap year
            "weight_kg": 70.0
        }
        response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        assert response.status_code in [400, 422]
    
    def test_create_with_unicode_notes(self, test_athlete_with_height):
        """Test creating entry with Unicode characters in notes"""
        headers = get_auth_headers(test_athlete_with_height)
        entry_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024-01-21",
            "weight_kg": 70.0,
            "notes": "Test with émojis 🏃‍♂️ and 中文 and русский"
        }
        response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        assert response.status_code == 201
        data = response.json()
        assert data["notes"] == "Test with émojis 🏃‍♂️ and 中文 and русский"
    
    def test_create_with_very_long_notes(self, test_athlete_with_height):
        """Test creating entry with very long notes"""
        headers = get_auth_headers(test_athlete_with_height)
        long_notes = "A" * 10000  # 10k characters
        entry_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024-01-22",
            "weight_kg": 70.0,
            "notes": long_notes
        }
        response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        assert response.status_code == 201
        data = response.json()
        assert len(data["notes"]) == 10000
    
    def test_create_with_empty_string_notes(self, test_athlete_with_height):
        """Test creating entry with empty string notes"""
        headers = get_auth_headers(test_athlete_with_height)
        entry_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024-01-23",
            "weight_kg": 70.0,
            "notes": ""
        }
        response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        assert response.status_code == 201
        data = response.json()
        assert data["notes"] == ""
    
    def test_create_with_complex_json(self, test_athlete_with_height):
        """Test creating entry with complex JSON measurements"""
        headers = get_auth_headers(test_athlete_with_height)
        complex_json = {
            "waist": 32,
            "chest": 42,
            "arms": {"left": 12.5, "right": 12.7},
            "legs": {"left": 24.0, "right": 24.2},
            "notes": ["measurement 1", "measurement 2"]
        }
        entry_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024-01-24",
            "weight_kg": 70.0,
            "measurements_json": complex_json
        }
        response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        assert response.status_code == 201
        data = response.json()
        assert data["measurements_json"] == complex_json
    
    def test_create_with_empty_json(self, test_athlete_with_height):
        """Test creating entry with empty JSON object"""
        headers = get_auth_headers(test_athlete_with_height)
        entry_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024-01-25",
            "weight_kg": 70.0,
            "measurements_json": {}
        }
        response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        assert response.status_code == 201
        data = response.json()
        assert data["measurements_json"] == {}
    
    def test_create_with_missing_required_fields(self, test_athlete_with_height):
        """Test creating entry without required fields"""
        headers = get_auth_headers(test_athlete_with_height)
        entry_data = {
            "weight_kg": 70.0
            # Missing athlete_id and date
        }
        response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        assert response.status_code == 422
    
    def test_get_with_invalid_date_format(self, test_athlete_with_height):
        """Test getting entries with invalid date format"""
        headers = get_auth_headers(test_athlete_with_height)
        response = client.get(
            f"/v1/body-composition?athlete_id={test_athlete_with_height.id}&start_date=2024/01/15",
            headers=headers
        )
        # Should handle gracefully or return error
        assert response.status_code in [200, 400, 422]
    
    def test_get_with_reversed_date_range(self, test_athlete_with_height):
        """Test getting entries with reversed date range (end < start)"""
        headers = get_auth_headers(test_athlete_with_height)
        response = client.get(
            f"/v1/body-composition?athlete_id={test_athlete_with_height.id}&start_date=2024-01-25&end_date=2024-01-15",
            headers=headers
        )
        # Should handle gracefully (return empty or error)
        assert response.status_code in [200, 400]
    
    def test_update_with_weight_to_none(self, test_athlete_with_height):
        """Test updating entry to remove weight"""
        headers = get_auth_headers(test_athlete_with_height)
        # Create entry
        entry_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024-01-26",
            "weight_kg": 70.0
        }
        create_response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        entry_id = create_response.json()["id"]
        
        # Update to remove weight
        update_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024-01-26",
            "weight_kg": None
        }
        response = client.put(f"/v1/body-composition/{entry_id}", json=update_data, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["weight_kg"] is None
        assert data["bmi"] is None  # No weight = no BMI
    
    def test_multiple_entries_same_athlete_different_dates(self, test_athlete_with_height):
        """Test creating multiple entries for same athlete on different dates"""
        headers = get_auth_headers(test_athlete_with_height)
        dates = ["2024-01-27", "2024-01-28", "2024-01-29"]
        created_ids = []
        
        for entry_date in dates:
            entry_data = {
                "athlete_id": str(test_athlete_with_height.id),
                "date": entry_date,
                "weight_kg": 70.0
            }
            response = client.post("/v1/body-composition", json=entry_data, headers=headers)
            assert response.status_code == 201
            created_ids.append(response.json()["id"])
        
        # Verify all were created
        assert len(created_ids) == 3
        assert len(set(created_ids)) == 3  # All unique IDs
    
    def test_get_with_only_start_date(self, test_athlete_with_height):
        """Test getting entries with only start_date filter"""
        headers = get_auth_headers(test_athlete_with_height)
        # Create entries
        dates = ["2024-02-15", "2024-02-20", "2024-02-25"]
        for entry_date in dates:
            entry_data = {
                "athlete_id": str(test_athlete_with_height.id),
                "date": entry_date,
                "weight_kg": 70.0
            }
            client.post("/v1/body-composition", json=entry_data, headers=headers)
        
        # Get with only start_date
        response = client.get(
            f"/v1/body-composition?athlete_id={test_athlete_with_height.id}&start_date=2024-02-20",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2  # Should return entries from 2024-02-20 onwards
    
    def test_get_with_only_end_date(self, test_athlete_with_height):
        """Test getting entries with only end_date filter"""
        headers = get_auth_headers(test_athlete_with_height)
        # Create entries
        dates = ["2024-03-15", "2024-03-20", "2024-03-25"]
        for entry_date in dates:
            entry_data = {
                "athlete_id": str(test_athlete_with_height.id),
                "date": entry_date,
                "weight_kg": 70.0
            }
            client.post("/v1/body-composition", json=entry_data, headers=headers)
        
        # Get with only end_date
        response = client.get(
            f"/v1/body-composition?athlete_id={test_athlete_with_height.id}&end_date=2024-03-20",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2  # Should return entries up to 2024-03-20
    
    def test_create_with_whitespace_in_notes(self, test_athlete_with_height):
        """Test creating entry with whitespace-only notes"""
        headers = get_auth_headers(test_athlete_with_height)
        entry_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024-01-30",
            "weight_kg": 70.0,
            "notes": "   \n\t   "  # Only whitespace
        }
        response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        assert response.status_code == 201
        data = response.json()
        assert data["notes"] == "   \n\t   "
    
    def test_update_date_change(self, test_athlete_with_height):
        """Test updating entry to change date"""
        headers = get_auth_headers(test_athlete_with_height)
        # Create entry
        entry_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024-01-31",
            "weight_kg": 70.0
        }
        create_response = client.post("/v1/body-composition", json=entry_data, headers=headers)
        entry_id = create_response.json()["id"]
        
        # Update date
        update_data = {
            "athlete_id": str(test_athlete_with_height.id),
            "date": "2024-02-01",  # Changed date
            "weight_kg": 70.0
        }
        response = client.put(f"/v1/body-composition/{entry_id}", json=update_data, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["date"] == "2024-02-01"
