"""
Pytest configuration and fixtures
"""
import pytest
import sys
import os

# Add the parent directory to the path so we can import from services
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@pytest.fixture
def sample_vdot():
    """Sample VDOT value for testing"""
    return 50.0

@pytest.fixture
def sample_race_times():
    """Sample race times for testing"""
    return {
        "5k_20min": (20 * 60, 5000),
        "marathon_3hr": (3 * 3600, 42195),
        "half_marathon_90min": (90 * 60, 21097.5),
        "one_mile_533": (5 * 60 + 33, 1609.34),
    }

