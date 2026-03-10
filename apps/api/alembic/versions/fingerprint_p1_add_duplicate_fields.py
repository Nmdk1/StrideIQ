"""Add is_duplicate and duplicate_of_id to Activity

Racing Fingerprint Pre-Work P1: retroactive duplicate detection.

Revision ID: fingerprint_p1_001
Revises: readiness_relabel_001
Create Date: 2026-03-04
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = 'fingerprint_p1_001'
down_revision = 'readiness_relabel_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('activity', sa.Column(
        'is_duplicate', sa.Boolean(), nullable=False, server_default='false',
    ))
    op.add_column('activity', sa.Column(
        'duplicate_of_id', postgresql.UUID(as_uuid=True), nullable=True,
    ))
    op.create_index('ix_activity_is_duplicate', 'activity', ['is_duplicate'])
    op.create_foreign_key(
        'fk_activity_duplicate_of', 'activity', 'activity',
        ['duplicate_of_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_activity_duplicate_of', 'activity', type_='foreignkey')
    op.drop_index('ix_activity_is_duplicate', table_name='activity')
    op.drop_column('activity', 'duplicate_of_id')
    op.drop_column('activity', 'is_duplicate')
