"""Add activity_stream table and stream fetch lifecycle fields (ADR-063)

Revision ID: activity_stream_001
Revises: narration_001
Create Date: 2026-02-14

Run Shape Intelligence — Phase 1: Stream Data Foundation
- New table: activity_stream (per-second resolution stream data)
- New columns on activity: stream_fetch_status, stream_fetch_attempted_at,
  stream_fetch_error, stream_fetch_retry_count, stream_fetch_deferred_until
- Check constraint on stream_fetch_status (6-state lifecycle)
- Partial index for backfill eligibility query
- Data migration: mark activities without external_activity_id as 'unavailable'
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = 'activity_stream_001'
down_revision = 'narration_001'
branch_labels = None
depends_on = None


def upgrade():
    # -------------------------------------------------------------------
    # 1. Create activity_stream table
    # -------------------------------------------------------------------
    op.create_table(
        'activity_stream',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('activity_id', UUID(as_uuid=True), sa.ForeignKey('activity.id'), nullable=False),
        sa.Column('stream_data', JSONB, nullable=False),
        sa.Column('channels_available', JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('point_count', sa.Integer, nullable=False),
        sa.Column('source', sa.Text, nullable=False, server_default='strava'),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('activity_id', name='uq_activity_stream_activity_id'),
        sa.Index('ix_activity_stream_activity_id', 'activity_id'),
    )

    # -------------------------------------------------------------------
    # 2. Add stream fetch lifecycle columns to activity (ADR-063)
    # -------------------------------------------------------------------
    conn = op.get_bind()
    from sqlalchemy import inspect
    inspector = inspect(conn)
    existing_columns = {col['name'] for col in inspector.get_columns('activity')}

    if 'stream_fetch_status' not in existing_columns:
        op.add_column('activity', sa.Column(
            'stream_fetch_status', sa.Text, nullable=False, server_default='pending',
        ))

    if 'stream_fetch_attempted_at' not in existing_columns:
        op.add_column('activity', sa.Column(
            'stream_fetch_attempted_at', sa.DateTime(timezone=True), nullable=True,
        ))

    if 'stream_fetch_error' not in existing_columns:
        op.add_column('activity', sa.Column(
            'stream_fetch_error', sa.Text, nullable=True,
        ))

    if 'stream_fetch_retry_count' not in existing_columns:
        op.add_column('activity', sa.Column(
            'stream_fetch_retry_count', sa.Integer, nullable=False, server_default='0',
        ))

    if 'stream_fetch_deferred_until' not in existing_columns:
        op.add_column('activity', sa.Column(
            'stream_fetch_deferred_until', sa.DateTime(timezone=True), nullable=True,
        ))

    # -------------------------------------------------------------------
    # 3. Check constraint on stream_fetch_status (6-state lifecycle)
    # -------------------------------------------------------------------
    op.create_check_constraint(
        'ck_activity_stream_fetch_status',
        'activity',
        "stream_fetch_status IN ('pending', 'fetching', 'success', 'failed', 'deferred', 'unavailable')",
    )

    # -------------------------------------------------------------------
    # 4. Partial index for backfill eligibility query (ADR-063 Decision 5)
    # -------------------------------------------------------------------
    op.create_index(
        'ix_activity_stream_backfill_eligible',
        'activity',
        ['start_time'],
        postgresql_where=sa.text(
            "stream_fetch_status IN ('pending', 'failed', 'deferred') "
            "AND external_activity_id IS NOT NULL"
        ),
    )

    # -------------------------------------------------------------------
    # 5. Data migration: mark activities without external_activity_id
    #    as 'unavailable' (they can never have streams)
    # -------------------------------------------------------------------
    op.execute(
        "UPDATE activity SET stream_fetch_status = 'unavailable' "
        "WHERE external_activity_id IS NULL"
    )


def downgrade():
    # Remove partial index
    op.drop_index('ix_activity_stream_backfill_eligible', table_name='activity')

    # Remove check constraint
    op.drop_constraint('ck_activity_stream_fetch_status', 'activity', type_='check')

    # Remove stream fetch columns from activity
    op.drop_column('activity', 'stream_fetch_deferred_until')
    op.drop_column('activity', 'stream_fetch_retry_count')
    op.drop_column('activity', 'stream_fetch_error')
    op.drop_column('activity', 'stream_fetch_attempted_at')
    op.drop_column('activity', 'stream_fetch_status')

    # Drop activity_stream table
    op.drop_table('activity_stream')
