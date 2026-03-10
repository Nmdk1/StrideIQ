"""Add layer column to AthleteFinding.

Living Fingerprint Spec — layer tracks finding category (A, B, C, etc.)
"""
from alembic import op
import sqlalchemy as sa


revision = 'lfp_004_layer'
down_revision = 'lfp_003_finding'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('fingerprint_finding', sa.Column(
        'layer', sa.Text(), nullable=False, server_default='B',
    ))


def downgrade() -> None:
    op.drop_column('fingerprint_finding', 'layer')
