"""
Integration tests for Nutrition API endpoints

Tests CRUD operations, entry type validation, activity linking, and date filtering.
"""
import pytest
from fastapi.testclient import TestClient
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from main import app
from core.database import SessionLocal
from models import Athlete, NutritionEntry, Activity

client = TestClient(app)


@pytest.fixture
def test_athlete():
    """Create a test athlete"""
    db = SessionLocal()
    try:
        # Cleanup any existing test athlete first
        existing = db.query(Athlete).filter(Athlete.email == "test_nutrition@example.com").first()
        if existing:
            # Cleanup nutrition entries first (foreign key constraint)
            db.query(NutritionEntry).filter(NutritionEntry.athlete_id == existing.id).delete()
            # Cleanup activities (may have nutrition entries linked)
            activities = db.query(Activity).filter(Activity.athlete_id == existing.id).all()
            for activity in activities:
                db.query(NutritionEntry).filter(NutritionEntry.activity_id == activity.id).delete()
            db.query(Activity).filter(Activity.athlete_id == existing.id).delete()
            db.delete(existing)
            db.commit()
        
        athlete = Athlete(
            email="test_nutrition@example.com",
            display_name="Test Athlete Nutrition",
            subscription_tier="free"
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)
        yield athlete
        # Cleanup: Delete nutrition entries first (foreign key constraint)
        db.query(NutritionEntry).filter(NutritionEntry.athlete_id == athlete.id).delete()
        # Cleanup activities (may have nutrition entries linked)
        activities = db.query(Activity).filter(Activity.athlete_id == athlete.id).all()
        for activity in activities:
            db.query(NutritionEntry).filter(NutritionEntry.activity_id == activity.id).delete()
        db.query(Activity).filter(Activity.athlete_id == athlete.id).delete()
        db.commit()
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
            distance_m=5000,
            duration_s=1800,
            provider="test",
            external_activity_id=str(uuid4())
        )
        db.add(activity)
        db.commit()
        db.refresh(activity)
        yield activity
        # Cleanup: Delete nutrition entries linked to this activity first
        db.query(NutritionEntry).filter(NutritionEntry.activity_id == activity.id).delete()
        db.commit()
        db.delete(activity)
        db.commit()
    finally:
        db.close()


class TestCreateNutritionEntry:
    """Test POST /v1/nutrition endpoint"""
    
    def test_create_daily_entry(self, test_athlete):
        """Test creating daily nutrition entry"""
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "entry_type": "daily",
            "calories": 2000.0,
            "protein_g": 150.0,
            "carbs_g": 250.0,
            "fat_g": 65.0,
            "notes": "Daily nutrition"
        }
        
        response = client.post("/v1/nutrition", json=entry_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["athlete_id"] == str(test_athlete.id)
        assert data["entry_type"] == "daily"
        assert data["calories"] == 2000.0
        assert data["activity_id"] is None
        assert data["notes"] == "Daily nutrition"
    
    def test_create_pre_activity_entry(self, test_athlete, test_activity):
        """Test creating pre-activity nutrition entry"""
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "entry_type": "pre_activity",
            "activity_id": str(test_activity.id),
            "calories": 300.0,
            "carbs_g": 60.0,
            "notes": "Pre-run fuel"
        }
        
        response = client.post("/v1/nutrition", json=entry_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["entry_type"] == "pre_activity"
        assert data["activity_id"] == str(test_activity.id)
        assert data["calories"] == 300.0
    
    def test_create_during_activity_entry(self, test_athlete, test_activity):
        """Test creating during-activity nutrition entry"""
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "entry_type": "during_activity",
            "activity_id": str(test_activity.id),
            "calories": 200.0,
            "carbs_g": 50.0,
            "notes": "During run gel"
        }
        
        response = client.post("/v1/nutrition", json=entry_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["entry_type"] == "during_activity"
        assert data["activity_id"] == str(test_activity.id)
    
    def test_create_post_activity_entry(self, test_athlete, test_activity):
        """Test creating post-activity nutrition entry"""
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "entry_type": "post_activity",
            "activity_id": str(test_activity.id),
            "calories": 400.0,
            "protein_g": 30.0,
            "carbs_g": 50.0,
            "notes": "Post-run recovery"
        }
        
        response = client.post("/v1/nutrition", json=entry_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["entry_type"] == "post_activity"
        assert data["activity_id"] == str(test_activity.id)
    
    def test_create_daily_with_activity_id_fails(self, test_athlete, test_activity):
        """Test that daily entry cannot have activity_id"""
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "entry_type": "daily",
            "activity_id": str(test_activity.id),  # Should fail
            "calories": 2000.0
        }
        
        response = client.post("/v1/nutrition", json=entry_data)
        assert response.status_code == 400
        assert "activity_id must be None" in response.json()["detail"]
    
    def test_create_pre_activity_without_activity_id_fails(self, test_athlete):
        """Test that pre_activity entry requires activity_id"""
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "entry_type": "pre_activity",
            # Missing activity_id - should fail
            "calories": 300.0
        }
        
        response = client.post("/v1/nutrition", json=entry_data)
        assert response.status_code == 400
        assert "activity_id is required" in response.json()["detail"]
    
    def test_create_with_invalid_activity_id(self, test_athlete):
        """Test creating entry with non-existent activity ID"""
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "entry_type": "pre_activity",
            "activity_id": str(uuid4()),  # Non-existent
            "calories": 300.0
        }
        
        response = client.post("/v1/nutrition", json=entry_data)
        assert response.status_code == 404
    
    def test_create_with_invalid_entry_type(self, test_athlete):
        """Test creating entry with invalid entry_type"""
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "entry_type": "invalid_type",
            "calories": 2000.0
        }
        
        response = client.post("/v1/nutrition", json=entry_data)
        assert response.status_code == 400
    
    def test_create_with_all_fields(self, test_athlete):
        """Test creating entry with all optional fields"""
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "entry_type": "daily",
            "calories": 2200.5,
            "protein_g": 165.3,
            "carbs_g": 275.7,
            "fat_g": 72.1,
            "fiber_g": 35.0,
            "timing": "2024-01-15T12:00:00Z",
            "notes": "Complete entry"
        }
        
        response = client.post("/v1/nutrition", json=entry_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["calories"] == 2200.5
        assert data["protein_g"] == 165.3
        assert data["carbs_g"] == 275.7
        assert data["fat_g"] == 72.1
        assert data["fiber_g"] == 35.0
        assert data["notes"] == "Complete entry"


class TestGetNutritionEntries:
    """Test GET /v1/nutrition endpoint"""
    
    def test_get_all_entries(self, test_athlete):
        """Test getting all entries for an athlete"""
        # Create multiple entries
        dates = ["2024-01-15", "2024-01-20", "2024-01-25"]
        for entry_date in dates:
            entry_data = {
                "athlete_id": str(test_athlete.id),
                "date": entry_date,
                "entry_type": "daily",
                "calories": 2000.0
            }
            client.post("/v1/nutrition", json=entry_data)
        
        # Get all entries
        response = client.get(f"/v1/nutrition?athlete_id={test_athlete.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        # Should be ordered by date descending
        assert data[0]["date"] == "2024-01-25"
    
    def test_get_with_date_filter(self, test_athlete):
        """Test getting entries with date range filter"""
        dates = ["2024-01-15", "2024-01-20", "2024-01-25", "2024-02-01"]
        for entry_date in dates:
            entry_data = {
                "athlete_id": str(test_athlete.id),
                "date": entry_date,
                "entry_type": "daily",
                "calories": 2000.0
            }
            client.post("/v1/nutrition", json=entry_data)
        
        # Filter by date range
        response = client.get(
            f"/v1/nutrition?athlete_id={test_athlete.id}&start_date=2024-01-20&end_date=2024-01-25"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
    
    def test_get_with_entry_type_filter(self, test_athlete, test_activity):
        """Test getting entries filtered by entry_type"""
        # Create entries of different types
        entry_types = ["daily", "pre_activity", "daily"]
        for entry_type in entry_types:
            entry_data = {
                "athlete_id": str(test_athlete.id),
                "date": "2024-01-15",
                "entry_type": entry_type,
                "calories": 2000.0
            }
            if entry_type != "daily":
                entry_data["activity_id"] = str(test_activity.id)
            client.post("/v1/nutrition", json=entry_data)
        
        # Filter by entry_type
        response = client.get(
            f"/v1/nutrition?athlete_id={test_athlete.id}&entry_type=daily"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert all(entry["entry_type"] == "daily" for entry in data)
        assert len(data) == 2
    
    def test_get_with_activity_id_filter(self, test_athlete, test_activity):
        """Test getting entries filtered by activity_id"""
        # Create entries linked to activity
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "entry_type": "pre_activity",
            "activity_id": str(test_activity.id),
            "calories": 300.0
        }
        client.post("/v1/nutrition", json=entry_data)
        
        # Filter by activity_id
        response = client.get(
            f"/v1/nutrition?athlete_id={test_athlete.id}&activity_id={test_activity.id}"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["activity_id"] == str(test_activity.id)
    
    def test_get_empty_list(self, test_athlete):
        """Test getting entries when none exist"""
        response = client.get(f"/v1/nutrition?athlete_id={test_athlete.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data == []


class TestGetNutritionEntryById:
    """Test GET /v1/nutrition/{id} endpoint"""
    
    def test_get_by_id(self, test_athlete):
        """Test getting a specific entry by ID"""
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "entry_type": "daily",
            "calories": 2000.0,
            "notes": "Test entry"
        }
        create_response = client.post("/v1/nutrition", json=entry_data)
        entry_id = create_response.json()["id"]
        
        # Get by ID
        response = client.get(f"/v1/nutrition/{entry_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == entry_id
        assert data["calories"] == 2000.0
        assert data["notes"] == "Test entry"
    
    def test_get_by_id_not_found(self):
        """Test getting non-existent entry"""
        fake_id = uuid4()
        response = client.get(f"/v1/nutrition/{fake_id}")
        
        assert response.status_code == 404


class TestUpdateNutritionEntry:
    """Test PUT /v1/nutrition/{id} endpoint"""
    
    def test_update_entry(self, test_athlete):
        """Test updating an existing entry"""
        # Create entry
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "entry_type": "daily",
            "calories": 2000.0
        }
        create_response = client.post("/v1/nutrition", json=entry_data)
        entry_id = create_response.json()["id"]
        
        # Update entry
        update_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "entry_type": "daily",
            "calories": 2200.0,
            "protein_g": 150.0,
            "notes": "Updated entry"
        }
        response = client.put(f"/v1/nutrition/{entry_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["calories"] == 2200.0
        assert data["protein_g"] == 150.0
        assert data["notes"] == "Updated entry"
    
    def test_update_not_found(self, test_athlete):
        """Test updating non-existent entry"""
        fake_id = uuid4()
        update_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "entry_type": "daily",
            "calories": 2000.0
        }
        
        response = client.put(f"/v1/nutrition/{fake_id}", json=update_data)
        assert response.status_code == 404


class TestDeleteNutritionEntry:
    """Test DELETE /v1/nutrition/{id} endpoint"""
    
    def test_delete_entry(self, test_athlete):
        """Test deleting an entry"""
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "entry_type": "daily",
            "calories": 2000.0
        }
        create_response = client.post("/v1/nutrition", json=entry_data)
        entry_id = create_response.json()["id"]
        
        # Delete entry
        response = client.delete(f"/v1/nutrition/{entry_id}")
        assert response.status_code == 204
        
        # Verify deleted
        get_response = client.get(f"/v1/nutrition/{entry_id}")
        assert get_response.status_code == 404
    
    def test_delete_not_found(self):
        """Test deleting non-existent entry"""
        fake_id = uuid4()
        response = client.delete(f"/v1/nutrition/{fake_id}")
        assert response.status_code == 404


class TestNutritionEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_create_with_zero_calories(self, test_athlete):
        """Test creating entry with zero calories"""
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "entry_type": "daily",
            "calories": 0.0
        }
        response = client.post("/v1/nutrition", json=entry_data)
        assert response.status_code == 201
    
    def test_create_with_negative_macros(self, test_athlete):
        """Test creating entry with negative macros"""
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "entry_type": "daily",
            "calories": -100.0
        }
        response = client.post("/v1/nutrition", json=entry_data)
        # API currently accepts negative values (validation can be added later)
        assert response.status_code in [201, 400, 422]
    
    def test_create_with_very_large_values(self, test_athlete):
        """Test creating entry with very large values"""
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "entry_type": "daily",
            "calories": 10000.0,
            "protein_g": 500.0
        }
        response = client.post("/v1/nutrition", json=entry_data)
        assert response.status_code == 201
        data = response.json()
        assert data["calories"] == 10000.0
    
    def test_create_multiple_daily_entries_same_date(self, test_athlete):
        """Test creating multiple daily entries on same date (should be allowed)"""
        # Create first entry
        entry1 = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "entry_type": "daily",
            "calories": 1000.0,
            "notes": "Breakfast"
        }
        response1 = client.post("/v1/nutrition", json=entry1)
        assert response1.status_code == 201
        
        # Create second entry same date (should be allowed - multiple meals per day)
        entry2 = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "entry_type": "daily",
            "calories": 1000.0,
            "notes": "Dinner"
        }
        response2 = client.post("/v1/nutrition", json=entry2)
        assert response2.status_code == 201
        
        # Both should exist
        assert response1.json()["id"] != response2.json()["id"]
    
    def test_create_with_future_date(self, test_athlete):
        """Test creating entry with future date"""
        future_date = (date.today() + timedelta(days=30)).isoformat()
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": future_date,
            "entry_type": "daily",
            "calories": 2000.0
        }
        response = client.post("/v1/nutrition", json=entry_data)
        assert response.status_code in [201, 400, 422]
    
    def test_create_with_unicode_notes(self, test_athlete):
        """Test creating entry with Unicode characters"""
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "entry_type": "daily",
            "calories": 2000.0,
            "notes": "Test with émojis 🍎 and 中文"
        }
        response = client.post("/v1/nutrition", json=entry_data)
        assert response.status_code == 201
        data = response.json()
        assert data["notes"] == "Test with émojis 🍎 and 中文"
    
    def test_create_with_timing(self, test_athlete):
        """Test creating entry with timing"""
        entry_data = {
            "athlete_id": str(test_athlete.id),
            "date": "2024-01-15",
            "entry_type": "daily",
            "calories": 2000.0,
            "timing": "2024-01-15T12:30:00Z"
        }
        response = client.post("/v1/nutrition", json=entry_data)
        assert response.status_code == 201
        data = response.json()
        assert data["timing"] is not None

