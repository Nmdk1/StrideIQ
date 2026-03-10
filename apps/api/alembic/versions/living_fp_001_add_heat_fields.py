"""Add dew_point_f and heat_adjustment_pct to activity.

Living Fingerprint Spec — Capability 1: Weather Normalization.
"""
from alembic import op
import sqlalchemy as sa


revision = 'lfp_001_heat'
down_revision = 'phase1c_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('activity', sa.Column('dew_point_f', sa.Float(), nullable=True))
    op.add_column('activity', sa.Column('heat_adjustment_pct', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('activity', 'heat_adjustment_pct')
    op.drop_column('activity', 'dew_point_f')
