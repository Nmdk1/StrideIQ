"""
Seed feature flags for plan generation.

Creates the feature_flag table if needed and populates required flags.
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
import os
import uuid

db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@postgres:5432/running_app')
engine = create_engine(db_url)

# Required feature flags for plan generation
REQUIRED_FLAGS = [
    {
        "key": "plan.standard",
        "name": "Standard Plans",
        "description": "Free standard training plans",
        "enabled": True,
        "requires_subscription": False,
        "requires_tier": None,
        "requires_payment": None,
        "rollout_percentage": 100,
    },
    {
        "key": "plan.standard.marathon",
        "name": "Marathon Standard Plans",
        "description": "Free marathon training plans",
        "enabled": True,
        "requires_subscription": False,
        "requires_tier": None,
        "requires_payment": None,
        "rollout_percentage": 100,
    },
    {
        "key": "plan.standard.half_marathon",
        "name": "Half Marathon Standard Plans",
        "description": "Free half marathon training plans",
        "enabled": True,
        "requires_subscription": False,
        "requires_tier": None,
        "requires_payment": None,
        "rollout_percentage": 100,
    },
    {
        "key": "plan.standard.10k",
        "name": "10K Standard Plans",
        "description": "Free 10K training plans",
        "enabled": True,
        "requires_subscription": False,
        "requires_tier": None,
        "requires_payment": None,
        "rollout_percentage": 100,
    },
    {
        "key": "plan.standard.5k",
        "name": "5K Standard Plans",
        "description": "Free 5K training plans",
        "enabled": True,
        "requires_subscription": False,
        "requires_tier": None,
        "requires_payment": None,
        "rollout_percentage": 100,
    },
    {
        "key": "plan.semi_custom",
        "name": "Semi-Custom Plans",
        "description": "Personalized plans with pace calculation",
        "enabled": True,
        "requires_subscription": False,
        "requires_tier": None,
        "requires_payment": 5.0,  # $5 one-time
        "rollout_percentage": 100,
    },
    {
        "key": "plan.custom",
        "name": "Custom Plans",
        "description": "Fully custom plans with Strava integration",
        "enabled": True,
        "requires_subscription": False,  # We check subscription_tier instead
        "requires_tier": "elite",
        "requires_payment": None,
        "rollout_percentage": 100,
    },
]

with engine.connect() as conn:
    # Check if table exists
    result = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'feature_flag'
        )
    """))
    table_exists = result.scalar()
    
    if not table_exists:
        print("Creating feature_flag table...")
        conn.execute(text("""
            CREATE TABLE feature_flag (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                key TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                enabled BOOLEAN NOT NULL DEFAULT FALSE,
                requires_subscription BOOLEAN NOT NULL DEFAULT FALSE,
                requires_tier TEXT,
                requires_payment NUMERIC,
                rollout_percentage INTEGER DEFAULT 100,
                allowed_athlete_ids JSONB DEFAULT '[]',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))
        conn.execute(text("CREATE INDEX ix_feature_flag_key ON feature_flag(key)"))
        conn.commit()
        print("Table created!")
    else:
        print("feature_flag table already exists")
    
    # Seed flags
    for flag in REQUIRED_FLAGS:
        # Check if exists
        existing = conn.execute(
            text("SELECT id FROM feature_flag WHERE key = :key"),
            {"key": flag["key"]}
        ).fetchone()
        
        if existing:
            print(f"  Flag '{flag['key']}' already exists, updating...")
            conn.execute(text("""
                UPDATE feature_flag SET
                    name = :name,
                    description = :description,
                    enabled = :enabled,
                    requires_subscription = :requires_subscription,
                    requires_tier = :requires_tier,
                    requires_payment = :requires_payment,
                    rollout_percentage = :rollout_percentage,
                    updated_at = NOW()
                WHERE key = :key
            """), flag)
        else:
            print(f"  Creating flag '{flag['key']}'...")
            conn.execute(text("""
                INSERT INTO feature_flag (key, name, description, enabled, 
                    requires_subscription, requires_tier, requires_payment, rollout_percentage)
                VALUES (:key, :name, :description, :enabled,
                    :requires_subscription, :requires_tier, :requires_payment, :rollout_percentage)
            """), flag)
    
    conn.commit()
    
    # Verify
    print("\nFeature flags in database:")
    flags = conn.execute(text("SELECT key, enabled, requires_tier FROM feature_flag ORDER BY key"))
    for row in flags:
        print(f"  {row[0]}: enabled={row[1]}, requires_tier={row[2]}")

print("\nDone!")
