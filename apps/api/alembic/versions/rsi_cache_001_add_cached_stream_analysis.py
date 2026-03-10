"""Add cached_stream_analysis table for analysis caching

Revision ID: rsi_cache_001
Revises: rsi_layer2_001
Create Date: 2026-02-14

RSI spec decision: "Cache full StreamAnalysisResult in DB."
Stores pre-computed analysis so /v1/home and /v1/activities/{id}/stream-analysis
serve from cache instead of recomputing on every read.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision: str = 'rsi_cache_001'
down_revision: Union[str, None] = 'rsi_layer2_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'cached_stream_analysis',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('activity_id', UUID(as_uuid=True), sa.ForeignKey('activity.id'), nullable=False, unique=True),
        sa.Column('result_json', JSONB, nullable=False),
        sa.Column('analysis_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_cached_stream_analysis_activity_id', 'cached_stream_analysis', ['activity_id'])


def downgrade() -> None:
    op.drop_index('ix_cached_stream_analysis_activity_id')
    op.drop_table('cached_stream_analysis')
