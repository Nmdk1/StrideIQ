"""Create PerformanceEvent table

Racing Fingerprint Phase 1A: curated race events with training context.

Revision ID: fingerprint_1a_001
Revises: fingerprint_p4_001
Create Date: 2026-03-04
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = 'fingerprint_1a_001'
down_revision = 'fingerprint_p4_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'performance_event',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('athlete_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('athlete.id'), nullable=False, index=True),
        sa.Column('activity_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('activity.id'), nullable=False, index=True),

        sa.Column('distance_category', sa.Text(), nullable=False),
        sa.Column('event_date', sa.Date(), nullable=False, index=True),
        sa.Column('event_type', sa.Text(), nullable=False),

        sa.Column('time_seconds', sa.Integer(), nullable=False),
        sa.Column('pace_per_mile', sa.Float(), nullable=True),
        sa.Column('rpi_at_event', sa.Float(), nullable=True),
        sa.Column('performance_percentage', sa.Float(), nullable=True),
        sa.Column('is_personal_best', sa.Boolean(), server_default='false'),

        sa.Column('ctl_at_event', sa.Float(), nullable=True),
        sa.Column('atl_at_event', sa.Float(), nullable=True),
        sa.Column('tsb_at_event', sa.Float(), nullable=True),
        sa.Column('fitness_relative_performance', sa.Float(), nullable=True),

        sa.Column('block_signature', postgresql.JSONB(), nullable=True),
        sa.Column('pre_event_wellness', postgresql.JSONB(), nullable=True),

        sa.Column('race_role', sa.Text(), nullable=True),
        sa.Column('user_classified_role', sa.Text(), nullable=True),
        sa.Column('cycle_id', postgresql.UUID(as_uuid=True), nullable=True),

        sa.Column('detection_source', sa.Text(), nullable=False,
                  server_default='algorithm'),
        sa.Column('detection_confidence', sa.Float(), nullable=True),
        sa.Column('user_confirmed', sa.Boolean(), nullable=True),

        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column('computation_version', sa.Integer(), nullable=False,
                  server_default='1'),

        sa.UniqueConstraint('athlete_id', 'activity_id',
                            name='uq_performance_event_athlete_activity'),
    )

    op.create_index('ix_performance_event_athlete_date',
                    'performance_event', ['athlete_id', 'event_date'])


def downgrade() -> None:
    op.drop_index('ix_performance_event_athlete_date',
                  table_name='performance_event')
    op.drop_table('performance_event')
