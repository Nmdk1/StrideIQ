"""
Tests for API endpoints - calculator routes
"""
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


class TestRPIEndpoint:
    """Test RPI calculator API endpoint"""
    
    def test_rpi_calculation_endpoint(self):
        """Test RPI calculation endpoint"""
        response = client.post(
            "/v1/rpi/calculate",
            json={
                "race_time_seconds": 20 * 60,  # 20 minutes
                "distance_meters": 5000
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "rpi" in data
        assert data["rpi"] > 0
    
    def test_rpi_training_paces_endpoint(self):
        """Test training paces endpoint"""
        response = client.post(
            "/v1/rpi/training-paces",
            json={"rpi": 50.0}
        )
        assert response.status_code == 200
        data = response.json()
        assert "easy" in data
        assert "marathon" in data
        assert "threshold" in data
        assert "interval" in data
        assert "repetition" in data
    
    def test_rpi_invalid_input(self):
        """Test invalid input handling"""
        response = client.post(
            "/v1/rpi/calculate",
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
    
    def test_age_grading_enhanced_response(self):
        """Test enhanced age-grading response includes all new fields"""
        response = client.post(
            "/v1/public/age-grade",
            json={
                "age": 55,
                "sex": "M",
                "distance_meters": 5000,  # 5K
                "time_seconds": 18 * 60 + 53  # 18:53
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # Core fields (backwards compatible)
        assert "performance_percentage" in data
        assert "equivalent_time" in data
        assert "equivalent_time_seconds" in data
        
        # Enhanced fields (new in v2)
        assert "open_class_standard_seconds" in data
        assert "open_class_standard_formatted" in data
        assert "age_standard_seconds" in data
        assert "age_standard_formatted" in data
        assert "age_factor" in data
        assert "age_graded_time_seconds" in data
        assert "age_graded_time_formatted" in data
        assert "classification" in data
        assert "equivalent_performances" in data
        assert "close_performances" in data
        
        # Validate classification structure
        classification = data["classification"]
        assert "level" in classification
        assert "label" in classification
        assert "color" in classification
        
        # Validate equivalent performances
        equiv = data["equivalent_performances"]
        assert len(equiv) > 0
        assert "distance" in equiv[0]
        assert "time_formatted" in equiv[0]
        
        # Validate close performances
        close = data["close_performances"]
        assert len(close) > 0
        assert "percentage" in close[0]
        assert "time_formatted" in close[0]
    
    def test_age_grading_age_factor_increases_with_age(self):
        """Test that age factor increases with age"""
        response_55 = client.post(
            "/v1/public/age-grade",
            json={"age": 55, "sex": "M", "distance_meters": 5000, "time_seconds": 1200}
        )
        response_65 = client.post(
            "/v1/public/age-grade",
            json={"age": 65, "sex": "M", "distance_meters": 5000, "time_seconds": 1200}
        )
        
        assert response_55.status_code == 200
        assert response_65.status_code == 200
        
        # Older age should have higher age factor
        assert response_65.json()["age_factor"] > response_55.json()["age_factor"]
    
    def test_age_grading_classification_levels(self):
        """Test classification levels based on percentage"""
        # Fast time should be higher classification
        response = client.post(
            "/v1/public/age-grade",
            json={"age": 30, "sex": "M", "distance_meters": 5000, "time_seconds": 15 * 60}  # 15:00 5K
        )
        assert response.status_code == 200
        data = response.json()
        
        # 15:00 5K for 30yo male should be quite good (regional+ class)
        assert data["performance_percentage"] >= 70
        assert data["classification"]["level"] in ["world_class", "national_class", "regional_class"]


class TestInputValidation:
    """Test input validation for all endpoints"""
    
    def test_missing_fields(self):
        """Test missing required fields"""
        response = client.post(
            "/v1/rpi/calculate",
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
            "/v1/rpi/calculate",
            json={
                "race_time_seconds": 20 * 60,
                "distance_meters": -100
            }
        )
        assert response.status_code in [400, 422]

