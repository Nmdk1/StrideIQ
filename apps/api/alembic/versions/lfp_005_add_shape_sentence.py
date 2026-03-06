"""Add shape_sentence column to Activity.

Natural language description of the run shape, generated from RunShape data.
Replaces generic titles like "Morning Run" with "7 miles easy" or
"10 miles with a 20-min tempo at 6:03".
"""
from alembic import op
import sqlalchemy as sa


revision = 'lfp_005_sentence'
down_revision = 'lfp_004_layer'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('activity', sa.Column('shape_sentence', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('activity', 'shape_sentence')
