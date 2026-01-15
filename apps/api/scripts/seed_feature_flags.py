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
    # Analytics feature flags
    {
        "key": "analytics.efficiency_trending_v2",
        "name": "Efficiency Trending V2",
        "description": "Enhanced efficiency trending with statistical significance testing",
        "enabled": True,
        "requires_subscription": False,
        "requires_tier": None,
        "requires_payment": None,
        "rollout_percentage": 100,
    },
    {
        "key": "analytics.pre_race_fingerprinting",
        "name": "Pre-Race State Fingerprinting",
        "description": "Personal readiness signature detection before races",
        "enabled": True,  # Enabled - ADR-009 implemented
        "requires_subscription": False,
        "requires_tier": None,
        "requires_payment": None,
        "rollout_percentage": 100,
    },
    {
        "key": "analytics.training_stress_balance",
        "name": "Training Stress Balance (TSB)",
        "description": "CTL/ATL/TSB training load tracking with race readiness",
        "enabled": True,  # Enabled - ADR-010 implemented
        "requires_subscription": False,
        "requires_tier": None,
        "requires_payment": None,
        "rollout_percentage": 100,
    },
    {
        "key": "analytics.critical_speed",
        "name": "Critical Speed Model",
        "description": "Critical Speed + D' from race PRs with pace predictions",
        "enabled": True,  # Enabled - ADR-011 implemented
        "requires_subscription": False,
        "requires_tier": None,
        "requires_payment": None,
        "rollout_percentage": 100,
    },
    {
        "key": "analytics.pace_decay",
        "name": "Pace Decay Analysis",
        "description": "Race pacing pattern and historical comparison analysis",
        "enabled": True,  # Enabled - ADR-012 implemented
        "requires_subscription": False,
        "requires_tier": None,
        "requires_payment": None,
        "rollout_percentage": 100,
    },
    # Integration feature flags
    {
        "key": "signals.home_banner",
        "name": "Home Signals Banner",
        "description": "Aggregated analytics signals on home page glance layer",
        "enabled": True,  # Enabled - ADR-013 implemented
        "requires_subscription": False,
        "requires_tier": None,
        "requires_payment": None,
        "rollout_percentage": 100,
    },
    {
        "key": "analytics.trend_attribution",
        "name": "Trend Attribution Analysis",
        "description": "Why This Trend? attribution on Analytics page",
        "enabled": True,  # Enabled - ADR-014 implemented
        "requires_subscription": False,
        "requires_tier": None,
        "requires_payment": None,
        "rollout_percentage": 100,
    },
    {
        "key": "analytics.run_attribution",
        "name": "Run Attribution Analysis",
        "description": "Why This Run? attribution on Activity Detail page",
        "enabled": True,  # Enabled - ADR-015 implemented
        "requires_subscription": False,
        "requires_tier": None,
        "requires_payment": None,
        "rollout_percentage": 100,
    },
    {
        "key": "signals.calendar_badges",
        "name": "Calendar Signals",
        "description": "Day badges and week trajectory on Calendar page",
        "enabled": True,  # Enabled - ADR-016 implemented
        "requires_subscription": False,
        "requires_tier": None,
        "requires_payment": None,
        "rollout_percentage": 100,
    },
    # CS predictor feature flag REMOVED - feature archived to branch archive/cs-model-2026-01
    {
        "key": "analytics.diagnostic_report",
        "name": "Diagnostic Report",
        "description": "Comprehensive on-demand diagnostic report for athletes",
        "enabled": True,  # Enabled - ADR-019 implemented
        "requires_subscription": False,
        "requires_tier": None,
        "requires_payment": None,
        "rollout_percentage": 100,
    },
    {
        "key": "home.enhanced_context",
        "name": "Enhanced Home Context",
        "description": "Correlation-based Why This Workout and TSB context on Home page",
        "enabled": True,  # Enabled - ADR-020 implemented
        "requires_subscription": False,
        "requires_tier": None,
        "requires_payment": None,
        "rollout_percentage": 100,
    },
    {
        "key": "plan.model_driven_generation",
        "name": "Model-Driven Plan Generation",
        "description": "Individual performance model for personalized plan generation (ADR-022)",
        "enabled": True,  # Enabled for beta elite users (ADR-027)
        "requires_subscription": True,
        "requires_tier": "elite",
        "requires_payment": None,
        "rollout_percentage": 100,  # Full rollout to elite tier
    },
    {
        "key": "ab.model_vs_template",
        "name": "A/B Test: Model vs Template Plans",
        "description": "A/B testing for model-driven vs template plan generation (ADR-026)",
        "enabled": False,  # Enable when ready to start A/B test
        "requires_subscription": False,
        "requires_tier": None,
        "requires_payment": None,
        "rollout_percentage": 0,
    },
    {
        "key": "cache.model_params",
        "name": "Model Parameter Caching",
        "description": "Cache individual model parameters in database (ADR-024)",
        "enabled": True,  # Default enabled
        "requires_subscription": False,
        "requires_tier": None,
        "requires_payment": None,
        "rollout_percentage": 100,
    },
    {
        "key": "api.model_driven_plans",
        "name": "Model-Driven Plans API",
        "description": "API endpoint for model-driven plan generation (ADR-025)",
        "enabled": True,  # Enabled for beta
        "requires_subscription": True,
        "requires_tier": "elite",
        "requires_payment": None,
        "rollout_percentage": 100,
    },
    {
        "key": "narrative.translation_enabled",
        "name": "Narrative Translation Layer",
        "description": "Human-first narrative generation from signals (ADR-033)",
        "enabled": True,  # Enabled for all users
        "requires_subscription": False,
        "requires_tier": None,
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
