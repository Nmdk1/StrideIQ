"""Add activity_reflection table for Layer 2 RSI wiring

Revision ID: rsi_layer2_001
Revises: 0d82917b8305
Create Date: 2026-02-14

Simple 3-option reflection prompt: harder | expected | easier.
One reflection per activity per athlete.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'rsi_layer2_001'
down_revision: Union[str, None] = '0d82917b8305'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'activity_reflection',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('activity_id', UUID(as_uuid=True), sa.ForeignKey('activity.id'), nullable=False),
        sa.Column('athlete_id', UUID(as_uuid=True), sa.ForeignKey('athlete.id'), nullable=False),
        sa.Column('response', sa.Text(), nullable=False),  # 'harder' | 'expected' | 'easier'
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("response IN ('harder', 'expected', 'easier')", name='ck_reflection_response_enum'),
        sa.UniqueConstraint('activity_id', name='uq_activity_reflection_activity'),  # One per activity
    )
    op.create_index('ix_activity_reflection_activity_id', 'activity_reflection', ['activity_id'])
    op.create_index('ix_activity_reflection_athlete_id', 'activity_reflection', ['athlete_id'])


def downgrade() -> None:
    op.drop_index('ix_activity_reflection_athlete_id')
    op.drop_index('ix_activity_reflection_activity_id')
    op.drop_table('activity_reflection')
