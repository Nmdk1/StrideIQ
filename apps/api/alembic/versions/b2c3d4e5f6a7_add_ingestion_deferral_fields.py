"""add_ingestion_deferral_fields

Revision ID: b2c3d4e5f6a7
Revises: a7b8c9d0e1f2
Create Date: 2026-01-24

Adds Phase 5 "viral-safe" deferral fields to athlete_ingestion_state:
- deferred_until
- deferred_reason
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("athlete_ingestion_state", sa.Column("deferred_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("athlete_ingestion_state", sa.Column("deferred_reason", sa.Text(), nullable=True))
    op.create_index("ix_athlete_ingestion_state_deferred_until", "athlete_ingestion_state", ["deferred_until"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_athlete_ingestion_state_deferred_until", table_name="athlete_ingestion_state")
    op.drop_column("athlete_ingestion_state", "deferred_reason")
    op.drop_column("athlete_ingestion_state", "deferred_until")

