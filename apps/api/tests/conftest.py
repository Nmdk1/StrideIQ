"""
Pytest configuration and fixtures

IMPORTANT: All tests use transactional rollback isolation.
Nothing created during tests persists to the database.
This prevents test data pollution completely.
"""
import pytest
import sys
import os
from uuid import uuid4
from datetime import datetime, date

# Add the parent directory to the path so we can import from services
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import event
from sqlalchemy.orm import Session
from core.database import SessionLocal, engine
from models import Athlete, Activity, PersonalBest, BestEffort


@pytest.fixture(scope="function")
def db_session():
    """
    Create a database session with transactional rollback.
    
    All changes made during the test are rolled back after the test completes.
    This guarantees zero test data pollution - nothing persists.
    """
    connection = engine.connect()
    transaction = connection.begin()
    
    # Bind session to this connection
    session = Session(bind=connection)
    
    # Begin a nested transaction (savepoint)
    nested = connection.begin_nested()
    
    # If the application code calls session.commit(), restart the savepoint
    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, transaction):
        nonlocal nested
        if transaction.nested and not transaction._parent.nested:
            nested = connection.begin_nested()
    
    yield session
    
    # Rollback everything - nothing persists
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def test_athlete(db_session):
    """
    Create a test athlete.
    
    No cleanup needed - transactional rollback handles it automatically.
    """
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
    
    return athlete  # No cleanup needed - transaction rollback handles it


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

