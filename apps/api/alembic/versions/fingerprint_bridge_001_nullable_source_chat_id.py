"""Make athlete_fact.source_chat_id nullable for admin-injected context.

Admin-injected training context facts (e.g. route elevation profiles,
confounding variable annotations) bypass coach chat extraction.
These facts have no source_chat_id.

Revision ID: fingerprint_bridge_001
Revises: temporal_fact_001
Create Date: 2026-03-28
"""
from alembic import op


revision = "fingerprint_bridge_001"
down_revision = "race_anchor_001"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "athlete_fact",
        "source_chat_id",
        nullable=True,
    )


def downgrade():
    op.alter_column(
        "athlete_fact",
        "source_chat_id",
        nullable=False,
    )
