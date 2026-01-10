"""
Tests for API endpoints - calculator routes
"""
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


class TestVDOTEndpoint:
    """Test VDOT calculator API endpoint"""
    
    def test_vdot_calculation_endpoint(self):
        """Test VDOT calculation endpoint"""
        response = client.post(
            "/v1/vdot/calculate",
            json={
                "race_time_seconds": 20 * 60,  # 20 minutes
                "distance_meters": 5000
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "vdot" in data
        assert data["vdot"] > 0
    
    def test_vdot_training_paces_endpoint(self):
        """Test training paces endpoint"""
        response = client.post(
            "/v1/vdot/training-paces",
            json={"vdot": 50.0}
        )
        assert response.status_code == 200
        data = response.json()
        assert "easy" in data
        assert "marathon" in data
        assert "threshold" in data
        assert "interval" in data
        assert "repetition" in data
    
    def test_vdot_invalid_input(self):
        """Test invalid input handling"""
        response = client.post(
            "/v1/vdot/calculate",
            json={
                "race_time_seconds": -100,
                "distance_meters": 5000
            }
        )
        # Should return error
        assert response.status_code in [400, 422]


class TestAgeGradingEndpoint:
    """Test age-grading calculator API endpoint"""
    
    def test_age_grading_calculation(self):
        """Test age-grading calculation endpoint"""
        response = client.post(
            "/v1/public/age-grade",
            json={
                "age": 57,
                "sex": "M",
                "distance_meters": 21097.5,  # Half Marathon
                "time_seconds": 87 * 60 + 14  # 1:27:14
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "performance_percentage" in data
        assert "equivalent_time" in data
        assert data["performance_percentage"] > 0
        
        # Equivalent time should be faster (less seconds)
        equivalent_seconds = data["equivalent_time_seconds"]
        assert equivalent_seconds < (87 * 60 + 14)
    
    def test_age_grading_equivalent_faster(self):
        """Verify equivalent open time is faster than actual time"""
        response = client.post(
            "/v1/public/age-grade",
            json={
                "age": 57,
                "sex": "M",
                "distance_meters": 21097.5,
                "time_seconds": 87 * 60 + 14
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # Equivalent time should be faster
        equivalent_seconds = data["equivalent_time_seconds"]
        actual_seconds = 87 * 60 + 14
        assert equivalent_seconds < actual_seconds
    
    def test_age_grading_invalid_input(self):
        """Test invalid input handling"""
        response = client.post(
            "/v1/public/age-grade",
            json={
                "age": -10,
                "sex": "M",
                "distance_meters": 5000,
                "time_seconds": 20 * 60
            }
        )
        # Should return error
        assert response.status_code in [400, 422]


class TestInputValidation:
    """Test input validation for all endpoints"""
    
    def test_missing_fields(self):
        """Test missing required fields"""
        response = client.post(
            "/v1/vdot/calculate",
            json={"race_time_seconds": 20 * 60}
        )
        assert response.status_code == 422
    
    def test_invalid_time_format(self):
        """Test invalid time values"""
        response = client.post(
            "/v1/public/age-grade",
            json={
                "age": 50,
                "sex": "M",
                "distance_meters": 5000,
                "time_seconds": 0  # Zero time
            }
        )
        assert response.status_code in [400, 422]
    
    def test_invalid_distance(self):
        """Test invalid distance values"""
        response = client.post(
            "/v1/vdot/calculate",
            json={
                "race_time_seconds": 20 * 60,
                "distance_meters": -100
            }
        )
        assert response.status_code in [400, 422]

