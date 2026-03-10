"""add athlete_title to activity

Revision ID: activity_identity_001
"""
from alembic import op
import sqlalchemy as sa


revision = 'activity_identity_001'
down_revision = 'lfp_005_sentence'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('activity', sa.Column('athlete_title', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('activity', 'athlete_title')
