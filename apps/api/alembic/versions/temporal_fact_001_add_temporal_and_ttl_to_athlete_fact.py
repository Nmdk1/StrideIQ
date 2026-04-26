"""Add temporal and ttl_days to athlete_fact.

Revision ID: temporal_fact_001
Revises: athlete_fact_001
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa


revision = "temporal_fact_001"
down_revision = "athlete_fact_001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "athlete_fact",
        sa.Column(
            "temporal",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "athlete_fact",
        sa.Column("ttl_days", sa.Integer(), nullable=True),
    )

    # Backfill: classify existing temporal facts
    op.execute("""
        UPDATE athlete_fact
        SET
            temporal = true,
            ttl_days = CASE
                WHEN fact_type IN ('injury_history', 'current_symptoms') THEN 14
                WHEN fact_type = 'training_phase' THEN 21
                WHEN fact_type = 'equipment' THEN 90
                WHEN fact_type = 'strength_pr' THEN 30
                ELSE ttl_days
            END
        WHERE fact_type IN (
            'injury_history',
            'current_symptoms',
            'training_phase',
            'equipment',
            'strength_pr'
        )
    """)


def downgrade():
    op.drop_column("athlete_fact", "ttl_days")
    op.drop_column("athlete_fact", "temporal")
