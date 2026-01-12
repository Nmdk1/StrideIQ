"""
Pytest configuration and fixtures
"""
import pytest
import sys
import os
from uuid import uuid4
from datetime import datetime, date

# Add the parent directory to the path so we can import from services
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SessionLocal, engine
from models import Athlete, Activity, PersonalBest, BestEffort


@pytest.fixture
def db_session():
    """Create a database session for testing."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_athlete(db_session):
    """Create a test athlete and clean up after test."""
    athlete = Athlete(
        email=f"test_{uuid4()}@example.com",
        display_name="Test Athlete",
        subscription_tier="free",
        birthdate=date(1990, 1, 1),
        sex="M"
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)
    
    yield athlete
    
    # Cleanup - delete in proper order to respect foreign keys
    try:
        # Delete PersonalBest records first (they reference Activity)
        db_session.query(PersonalBest).filter(
            PersonalBest.athlete_id == athlete.id
        ).delete()
        
        # Delete BestEffort records 
        db_session.query(BestEffort).filter(
            BestEffort.athlete_id == athlete.id
        ).delete()
        
        # Delete Activity records
        db_session.query(Activity).filter(
            Activity.athlete_id == athlete.id
        ).delete()
        
        # Delete the athlete
        db_session.delete(athlete)
        db_session.commit()
    except Exception:
        db_session.rollback()


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

