"""Add run_shape JSONB column to activity.

Living Fingerprint Spec — Capability 2: Activity Shape Extraction.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = 'lfp_002_shape'
down_revision = 'lfp_001_heat'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('activity', sa.Column('run_shape', JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column('activity', 'run_shape')
