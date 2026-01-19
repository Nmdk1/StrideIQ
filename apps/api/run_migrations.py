#!/usr/bin/env python3
"""Script to run Alembic migrations or create schema directly"""
import os
import sys
import time
from dotenv import load_dotenv

load_dotenv()

def check_db_ready():
    """Check if database is ready"""
    import psycopg2
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'postgres'),
            port=os.getenv('POSTGRES_PORT', '5432'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', 'postgres'),
            database=os.getenv('POSTGRES_DB', 'running_app')
        )
        conn.close()
        return True
    except Exception:
        return False

def create_schema_directly():
    """Create schema directly from SQLAlchemy models - more reliable than migrations"""
    from core.database import Base, engine
    from models import (
        Athlete, Activity, ActivitySplit, PersonalBest, DailyCheckin,
        BodyComposition, NutritionEntry, WorkPattern, IntakeQuestionnaire,
        CoachingKnowledgeEntry, CoachingRecommendation, RecommendationOutcome,
        ActivityFeedback, InsightFeedback, TrainingPlan, PlannedWorkout, 
        TrainingAvailability
    )
    from sqlalchemy import text
    
    # SAFETY CHECK: If athlete table has data, don't overwrite schema
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM athlete"))
            count = result.scalar()
            if count and count > 0:
                print(f"Database has {count} athletes - skipping schema creation to preserve data")
                print("Run 'alembic upgrade head' manually if schema updates are needed")
                return
    except Exception as e:
        print(f"Could not check athlete table (may not exist yet): {e}")
        # Continue with schema creation if table doesn't exist
    
    print("Creating schema directly from models...")
    
    # Create TimescaleDB extension first
    with engine.connect() as conn:
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE'))
        conn.commit()
    
    # Create all tables
    Base.metadata.create_all(engine, checkfirst=True)
    
    # Create alembic_version table and stamp as current head.
    #
    # Note: this environment prefers schema creation from models (create_all)
    # rather than relying on historical Alembic migrations, which may not be
    # consistently replayable from an empty database.
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS alembic_version (
                version_num VARCHAR(32) NOT NULL PRIMARY KEY
            )
        """))
        conn.execute(text("DELETE FROM alembic_version"))
        conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('c1a6e2b7d9f0')"))
        conn.commit()
    
    print("Schema created successfully!")

def main():
    print("Waiting for database to be ready...")
    max_retries = 30
    retry_count = 0
    
    while retry_count < max_retries:
        if check_db_ready():
            print("Database is ready!")
            break
        retry_count += 1
        print(f"Database is unavailable - sleeping (attempt {retry_count}/{max_retries})")
        time.sleep(1)
    else:
        print("ERROR: Database is not ready after maximum retries")
        sys.exit(1)
    
    # Try direct schema creation (more reliable with inconsistent migrations)
    try:
        create_schema_directly()
    except Exception as e:
        print(f"Warning: Schema creation had issues: {e}")
        print("Continuing anyway - tables may already exist")

if __name__ == '__main__':
    main()
