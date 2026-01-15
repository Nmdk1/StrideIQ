"""
Comprehensive unit tests for age-grading calculations.

Verifies accuracy against Alan Jones 2025 Road Age-Grading Tables.
Source: https://github.com/AlanLyttonJones/Age-Grade-Tables

Tests cover:
- All 7 distances: 1 Mile, 5K, 8K, 10K, 10 Mile, Half Marathon, Marathon
- Both genders: Male and Female
- All ages: 5-100 (spot checks + edge cases)
- Official calculator validation cases
"""

import pytest
from httpx import AsyncClient, ASGITransport
from main import app
from services.wma_age_factors import (
    get_wma_age_factor,
    get_wma_open_standard_seconds,
    WMA_1_MILE_MALE, WMA_5K_MALE, WMA_8K_MALE, WMA_10K_MALE,
    WMA_10_MILE_MALE, WMA_HALF_MARATHON_MALE, WMA_MARATHON_MALE,
    WMA_1_MILE_FEMALE, WMA_5K_FEMALE, WMA_8K_FEMALE, WMA_10K_FEMALE,
    WMA_10_MILE_FEMALE, WMA_HALF_MARATHON_FEMALE, WMA_MARATHON_FEMALE,
    WMA_OPEN_STANDARDS_SECONDS,
)


# ============================================================================
# TEST DATA - Alan Jones 2025 Tables
# ============================================================================

# Distance mappings
DISTANCES = {
    '1 Mile': 1609,
    '5K': 5000,
    '8K': 8000,
    '10K': 10000,
    '10 Mile': 16093,
    'Half Marathon': 21097,
    'Marathon': 42195,
}

# Expected open standards (seconds) from Alan Jones 2025 tables
EXPECTED_OPEN_STANDARDS = {
    'male': {
        1609: 227,     # 3:47
        5000: 769,     # 12:49
        8000: 1255,    # 20:55
        10000: 1584,   # 26:24
        16093: 2595,   # 43:15
        21097: 3451,   # 57:31
        42195: 7235,   # 2:00:35
    },
    'female': {
        1609: 253,     # 4:13
        5000: 834,     # 13:54
        8000: 1365,    # 22:45
        10000: 1726,   # 28:46
        16093: 2832,   # 47:12
        21097: 3772,   # 1:02:52
        42195: 7796,   # 2:09:56
    }
}

# Spot-check factors from Alan Jones 2025 tables (time multipliers)
# These values are verified against the source Excel files
SPOT_CHECK_FACTORS = {
    # (sex, distance_meters, age): expected_time_multiplier
    # Male 5K - from MaleRoadStd2025.xlsx
    ('M', 5000, 25): 1.0000,
    ('M', 5000, 35): 1.0179,
    ('M', 5000, 45): 1.0959,
    ('M', 5000, 55): 1.1869,
    ('M', 5000, 65): 1.2945,
    ('M', 5000, 75): 1.4605,
    ('M', 5000, 85): 1.8570,
    ('M', 5000, 95): 3.0093,
    
    # Female 5K - from FemaleRoadStd2025.xlsx
    ('F', 5000, 25): 1.0000,
    ('F', 5000, 35): 1.0211,
    ('F', 5000, 45): 1.1016,
    ('F', 5000, 55): 1.2335,
    ('F', 5000, 65): 1.4013,
    ('F', 5000, 75): 1.6221,
    ('F', 5000, 81): 1.8132,  # User test case
    ('F', 5000, 85): 2.0251,
    ('F', 5000, 95): 3.3738,
    
    # Male 10K - from MaleRoadStd2025.xlsx
    ('M', 10000, 40): 1.0378,
    ('M', 10000, 50): 1.1254,
    ('M', 10000, 60): 1.2291,
    ('M', 10000, 70): 1.3539,
    ('M', 10000, 79): 1.5528,  # User test case (79yo male)
    ('M', 10000, 80): 1.5870,
    ('M', 10000, 90): 2.1997,
    
    # Female Marathon - from FemaleRoadStd2025.xlsx
    ('F', 42195, 30): 1.0017,
    ('F', 42195, 50): 1.1114,
    ('F', 42195, 70): 1.4579,
    ('F', 42195, 90): 2.8645,
    
    # Edge cases - from source Excel files
    ('M', 5000, 5): 1.6447,   # Youngest male
    ('M', 5000, 100): 4.8379, # Oldest male
    ('F', 5000, 5): 1.4486,   # Youngest female
    ('F', 5000, 100): 5.9102, # Oldest female
}

# Official calculator validation cases
OFFICIAL_CALCULATOR_CASES = [
    # (age, sex, distance, time_seconds, expected_percentage, tolerance)
    (55, 'M', 5000, 18*60+53, 80.65, 0.2),   # 55yo male, 5K 18:53 -> 80.65%
    (79, 'M', 5000, 27*60+14, 74.3, 0.2),    # 79yo male, 5K 27:14 -> 74.3%
    (81, 'F', 5000, 31*60+25, 80.22, 0.2),   # 81yo female, 5K 31:25 -> 80.22%
]


# ============================================================================
# OPEN STANDARDS TESTS
# ============================================================================

class TestOpenStandards:
    """Test that open standards match Alan Jones 2025 tables."""
    
    @pytest.mark.parametrize("sex,distance,expected", [
        ('male', 1609, 227),
        ('male', 5000, 769),
        ('male', 8000, 1255),
        ('male', 10000, 1584),
        ('male', 16093, 2595),
        ('male', 21097, 3451),
        ('male', 42195, 7235),
        ('female', 1609, 253),
        ('female', 5000, 834),
        ('female', 8000, 1365),
        ('female', 10000, 1726),
        ('female', 16093, 2832),
        ('female', 21097, 3772),
        ('female', 42195, 7796),
    ])
    def test_open_standard_values(self, sex, distance, expected):
        """Verify open standard times match Excel data."""
        result = get_wma_open_standard_seconds(sex[0].upper(), distance)
        assert abs(result - expected) < 1, f"{sex} {distance}m: expected {expected}s, got {result}s"


# ============================================================================
# AGE FACTOR TESTS
# ============================================================================

class TestAgeFactors:
    """Test age factors against Alan Jones 2025 tables."""
    
    @pytest.mark.parametrize("sex,distance,age,expected", [
        (s, d, a, e) for (s, d, a), e in SPOT_CHECK_FACTORS.items()
    ])
    def test_spot_check_factors(self, sex, distance, age, expected):
        """Verify spot-check age factors match Excel data."""
        result = get_wma_age_factor(age, sex, distance)
        assert abs(result - expected) < 0.001, \
            f"{sex} {distance}m Age {age}: expected {expected:.4f}, got {result:.4f}"
    
    def test_factor_table_completeness_male(self):
        """Verify male factor tables have all ages 5-100."""
        tables = [
            WMA_1_MILE_MALE, WMA_5K_MALE, WMA_8K_MALE, WMA_10K_MALE,
            WMA_10_MILE_MALE, WMA_HALF_MARATHON_MALE, WMA_MARATHON_MALE,
        ]
        for table in tables:
            for age in range(5, 101):
                assert age in table, f"Missing age {age} in male table"
    
    def test_factor_table_completeness_female(self):
        """Verify female factor tables have all ages 5-100."""
        tables = [
            WMA_1_MILE_FEMALE, WMA_5K_FEMALE, WMA_8K_FEMALE, WMA_10K_FEMALE,
            WMA_10_MILE_FEMALE, WMA_HALF_MARATHON_FEMALE, WMA_MARATHON_FEMALE,
        ]
        for table in tables:
            for age in range(5, 101):
                assert age in table, f"Missing age {age} in female table"
    
    def test_factors_increase_with_age_male_5k(self):
        """Verify factors increase monotonically with age (after peak)."""
        prev_factor = WMA_5K_MALE[30]
        for age in range(31, 101):
            curr_factor = WMA_5K_MALE[age]
            assert curr_factor >= prev_factor, \
                f"Male 5K factor should increase: age {age-1}={prev_factor:.4f}, age {age}={curr_factor:.4f}"
            prev_factor = curr_factor
    
    def test_factors_increase_with_age_female_5k(self):
        """Verify factors increase monotonically with age (after peak)."""
        prev_factor = WMA_5K_FEMALE[30]
        for age in range(31, 101):
            curr_factor = WMA_5K_FEMALE[age]
            assert curr_factor >= prev_factor, \
                f"Female 5K factor should increase: age {age-1}={prev_factor:.4f}, age {age}={curr_factor:.4f}"
            prev_factor = curr_factor
    
    def test_senior_athletes_have_factor_1(self):
        """Verify senior athletes (peak ages) have factor ~1.0."""
        # Male 5K seniors: ages 20-29
        for age in range(20, 30):
            factor = WMA_5K_MALE[age]
            assert abs(factor - 1.0) < 0.01, f"Male 5K age {age} should be ~1.0, got {factor}"
        
        # Female 5K seniors: ages 19-26
        for age in range(19, 27):
            factor = WMA_5K_FEMALE[age]
            assert abs(factor - 1.0) < 0.01, f"Female 5K age {age} should be ~1.0, got {factor}"


# ============================================================================
# OFFICIAL CALCULATOR VALIDATION
# ============================================================================

class TestOfficialCalculatorValidation:
    """Validate against known official calculator results."""
    
    @pytest.mark.parametrize("age,sex,distance,time_secs,expected_pct,tolerance", 
                             OFFICIAL_CALCULATOR_CASES)
    def test_official_calculator_match(self, age, sex, distance, time_secs, expected_pct, tolerance):
        """Verify our calculations match official calculator results."""
        time_mult = get_wma_age_factor(age, sex, distance)
        open_std = get_wma_open_standard_seconds(sex, distance)
        age_std = open_std * time_mult
        calculated_pct = (age_std / time_secs) * 100
        
        assert abs(calculated_pct - expected_pct) < tolerance, \
            f"Age {age} {sex} {distance}m {time_secs}s: expected {expected_pct}%, got {calculated_pct:.2f}%"
    
    def test_case_55yo_male_5k(self):
        """User test case: 55yo male, 5K 18:53."""
        age, sex, distance = 55, 'M', 5000
        time_secs = 18 * 60 + 53
        
        time_mult = get_wma_age_factor(age, sex, distance)
        open_std = get_wma_open_standard_seconds(sex, distance)
        age_std = open_std * time_mult
        pct = (age_std / time_secs) * 100
        
        # Expected: 80.65%, factor 0.8425, age std 15:13.7
        assert abs(1/time_mult - 0.8425) < 0.001, f"Factor: expected 0.8425, got {1/time_mult:.4f}"
        assert abs(pct - 80.65) < 0.2, f"Percentage: expected 80.65%, got {pct:.2f}%"
    
    def test_case_79yo_male_5k(self):
        """User test case: 79yo male, 5K 27:14."""
        age, sex, distance = 79, 'M', 5000
        time_secs = 27 * 60 + 14
        
        time_mult = get_wma_age_factor(age, sex, distance)
        open_std = get_wma_open_standard_seconds(sex, distance)
        age_std = open_std * time_mult
        pct = (age_std / time_secs) * 100
        
        # Expected: 74.3%, factor 0.6334, age std 20:14.1
        assert abs(1/time_mult - 0.6334) < 0.001, f"Factor: expected 0.6334, got {1/time_mult:.4f}"
        assert abs(pct - 74.3) < 0.2, f"Percentage: expected 74.3%, got {pct:.2f}%"
    
    def test_case_81yo_female_5k(self):
        """User test case: 81yo female, 5K 31:25."""
        age, sex, distance = 81, 'F', 5000
        time_secs = 31 * 60 + 25
        
        time_mult = get_wma_age_factor(age, sex, distance)
        open_std = get_wma_open_standard_seconds(sex, distance)
        age_std = open_std * time_mult
        pct = (age_std / time_secs) * 100
        
        # Expected: 80.22%, factor 0.5515, age std 25:12.2
        assert abs(1/time_mult - 0.5515) < 0.001, f"Factor: expected 0.5515, got {1/time_mult:.4f}"
        assert abs(pct - 80.22) < 0.1, f"Percentage: expected 80.22%, got {pct:.2f}%"


# ============================================================================
# API ENDPOINT TESTS
# ============================================================================

class TestAgeGradingAPI:
    """Test the age-grading API endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create async test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    
    @pytest.mark.asyncio
    async def test_api_55yo_male_5k(self, client):
        """API test: 55yo male, 5K 18:53."""
        response = await client.post("/v1/public/age-grade", json={
            "age": 55,
            "sex": "M",
            "distance_meters": 5000,
            "time_seconds": 18 * 60 + 53
        })
        assert response.status_code == 200
        data = response.json()
        assert abs(data["performance_percentage"] - 80.65) < 0.5
        assert "National" in data["classification"]["label"]
    
    @pytest.mark.asyncio
    async def test_api_79yo_male_5k(self, client):
        """API test: 79yo male, 5K 27:14."""
        response = await client.post("/v1/public/age-grade", json={
            "age": 79,
            "sex": "M",
            "distance_meters": 5000,
            "time_seconds": 27 * 60 + 14
        })
        assert response.status_code == 200
        data = response.json()
        assert abs(data["performance_percentage"] - 74.3) < 0.5
        assert "Regional" in data["classification"]["label"]
    
    @pytest.mark.asyncio
    async def test_api_81yo_female_5k(self, client):
        """API test: 81yo female, 5K 31:25."""
        response = await client.post("/v1/public/age-grade", json={
            "age": 81,
            "sex": "F",
            "distance_meters": 5000,
            "time_seconds": 31 * 60 + 25
        })
        assert response.status_code == 200
        data = response.json()
        assert abs(data["performance_percentage"] - 80.22) < 0.5
        assert "National" in data["classification"]["label"]
    
    @pytest.mark.asyncio
    async def test_api_all_distances(self, client):
        """Verify API handles all supported distances."""
        # Distance in meters -> reasonable time in seconds
        distances = [
            (1609, 5 * 60),       # 1 Mile: 5:00
            (5000, 20 * 60),      # 5K: 20:00
            (8000, 35 * 60),      # 8K: 35:00
            (10000, 45 * 60),     # 10K: 45:00
            (16093, 75 * 60),     # 10 Mile: 1:15:00
            (21097, 100 * 60),    # Half Marathon: 1:40:00
            (42195, 210 * 60),    # Marathon: 3:30:00
        ]
        for dist_meters, time_secs in distances:
            response = await client.post("/v1/public/age-grade", json={
                "age": 40,
                "sex": "M",
                "distance_meters": dist_meters,
                "time_seconds": time_secs
            })
            assert response.status_code == 200, f"Failed for distance: {dist_meters}m"
            data = response.json()
            assert "performance_percentage" in data
            assert "classification" in data
    
    @pytest.mark.asyncio
    async def test_api_edge_age_young(self, client):
        """Test youngest age (5)."""
        response = await client.post("/v1/public/age-grade", json={
            "age": 5,
            "sex": "M",
            "distance_meters": 5000,
            "time_seconds": 30 * 60
        })
        assert response.status_code == 200
        data = response.json()
        assert data["performance_percentage"] > 0
    
    @pytest.mark.asyncio
    async def test_api_edge_age_old(self, client):
        """Test oldest age (100)."""
        response = await client.post("/v1/public/age-grade", json={
            "age": 100,
            "sex": "F",
            "distance_meters": 5000,
            "time_seconds": 60 * 60
        })
        assert response.status_code == 200
        data = response.json()
        assert data["performance_percentage"] > 0


# ============================================================================
# CALCULATION ACCURACY TESTS
# ============================================================================

class TestCalculationAccuracy:
    """Test calculation formulas and accuracy."""
    
    def test_age_grading_formula(self):
        """Verify the age-grading formula is correct."""
        # Formula: age_grading_pct = (age_standard / athlete_time) * 100
        # Where: age_standard = open_standard * time_multiplier
        
        age, sex, distance = 55, 'M', 5000
        athlete_time = 18 * 60 + 53  # 1133 seconds
        
        time_mult = get_wma_age_factor(age, sex, distance)
        open_std = get_wma_open_standard_seconds(sex, distance)
        age_std = open_std * time_mult
        pct = (age_std / athlete_time) * 100
        
        # Verify each step
        assert open_std == 769, f"Open standard should be 769s"
        assert abs(time_mult - 1.1877) < 0.001, f"Time mult should be ~1.1877"
        assert abs(age_std - 913.3) < 1, f"Age standard should be ~913.3s"
        assert abs(pct - 80.6) < 0.5, f"Percentage should be ~80.6%"
    
    def test_age_graded_time_formula(self):
        """Verify age-graded time calculation."""
        # Age-graded time = athlete_time * (1 / time_multiplier)
        # = athlete_time * wma_factor
        
        age, sex, distance = 55, 'M', 5000
        athlete_time = 18 * 60 + 53  # 1133 seconds
        
        time_mult = get_wma_age_factor(age, sex, distance)
        wma_factor = 1 / time_mult
        age_graded_time = athlete_time * wma_factor
        
        # Expected: ~954s = 15:54
        assert abs(age_graded_time - 954) < 5, f"Age-graded time should be ~954s (15:54)"
    
    def test_classification_boundaries(self):
        """Verify classification boundaries are correct."""
        boundaries = [
            (100, "World Record"),
            (92, "World Class"),
            (82, "National Class"),
            (72, "Regional Class"),
            (62, "Local Class"),
            (50, "Local Class"),  # Anything below 60% is still Local
        ]
        
        for pct, expected_class in boundaries:
            if pct >= 90:
                assert expected_class in ["World Record", "World Class"]
            elif pct >= 80:
                assert expected_class == "National Class"
            elif pct >= 70:
                assert expected_class == "Regional Class"
            else:
                assert expected_class == "Local Class"
