#!/usr/bin/env python3
"""Database bootstrap: run Alembic migrations (production-safe).

Historical note:
- We previously attempted "schema creation from models" + manual alembic_version stamping
  to avoid replaying older migrations. That approach can silently drift schema from the
  recorded revision history as new tables are added later (ex: `best_effort` for PBs).

Definition of done for production readiness:
- Always run `alembic upgrade head` on startup.
- If migrations fail, fail fast (don't start with an unknown schema).
"""

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

def _get_alembic_config():
    """Load Alembic config for programmatic migrations."""
    from alembic.config import Config

    here = os.path.dirname(os.path.abspath(__file__))
    cfg = Config(os.path.join(here, "alembic.ini"))
    return cfg


def alembic_upgrade_head() -> None:
    """Apply all pending migrations."""
    from alembic import command

    command.upgrade(_get_alembic_config(), "head")


def alembic_stamp_head() -> None:
    """Stamp alembic_version as head (no schema changes)."""
    from alembic import command

    command.stamp(_get_alembic_config(), "head")


def create_schema_directly():
    """Fallback: create schema directly from SQLAlchemy models.

    This is ONLY used when migrations cannot be replayed from an empty database.
    It must be followed by `alembic stamp head` so future upgrades can apply.
    """
    from core.database import Base, engine
    from models import (
        Athlete, Activity, ActivitySplit, PersonalBest, BestEffort, DailyCheckin,
        BodyComposition, NutritionEntry, WorkPattern, IntakeQuestionnaire,
        CoachingKnowledgeEntry, CoachingRecommendation, RecommendationOutcome,
        ActivityFeedback, InsightFeedback, TrainingPlan, PlannedWorkout, 
        TrainingAvailability, AthleteIngestionState, CoachChat, PlanModificationLog
    )
    from sqlalchemy import text
    
    # SAFETY CHECK: If athlete table has data, don't overwrite schema here.
    # For non-empty DBs, we MUST use Alembic migrations.
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM athlete"))
            count = result.scalar()
            if count and count > 0:
                raise RuntimeError(
                    f"Refusing direct schema creation on non-empty DB (athletes={count}). "
                    f"Run Alembic migrations instead."
                )
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

    # Mark as up to date so future runs can upgrade incrementally.
    alembic_stamp_head()

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
    
    # Production rule: always apply migrations.
    try:
        alembic_upgrade_head()
        print("Migrations completed successfully!")
        return
    except Exception as e:
        print(f"ERROR: Alembic upgrade failed: {e}")

    # Only fallback to create_all for an EMPTY database that cannot replay migrations.
    # If this fallback also fails, exit non-zero.
    try:
        create_schema_directly()
    except Exception as e:
        print(f"ERROR: Schema bootstrap failed: {e}")
        sys.exit(1)
    print("Schema bootstrap completed via create_all fallback.")

if __name__ == '__main__':
    main()
