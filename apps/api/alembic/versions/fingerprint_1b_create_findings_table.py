"""Create fingerprint_finding table

Racing Fingerprint Phase 1B: stored pattern extraction findings.

Revision ID: fingerprint_1b_001
Revises: fingerprint_1a_001
Create Date: 2026-03-04
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = 'fingerprint_1b_001'
down_revision = 'fingerprint_1a_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'fingerprint_finding',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('athlete_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('athlete.id'), nullable=False, index=True),
        sa.Column('layer', sa.Integer(), nullable=False),
        sa.Column('finding_type', sa.Text(), nullable=False),
        sa.Column('sentence', sa.Text(), nullable=False),
        sa.Column('evidence', postgresql.JSONB(), nullable=False),
        sa.Column('statistical_confidence', sa.Float(), nullable=False),
        sa.Column('effect_size', sa.Float(), nullable=False),
        sa.Column('sample_size', sa.Integer(), nullable=False),
        sa.Column('confidence_tier', sa.Text(), nullable=False),
        sa.Column('computation_version', sa.Integer(), nullable=False,
                  server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('fingerprint_finding')
