"""enforce_ingestion_contract

Revision ID: 27ed18b0e383
Revises: e661e5c152c7
Create Date: 2026-01-02 19:27:36.147955

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '27ed18b0e383'
down_revision: Union[str, None] = 'e661e5c152c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add Sync Cursor to ConnectedAccount
    op.add_column('connected_accounts', sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True))
    
    # 2. Add Provider and Race Detection to Activity
    op.add_column('activities', sa.Column('provider', sa.String(), nullable=True))
    op.add_column('activities', sa.Column('external_activity_id', sa.String(), nullable=True))
    op.add_column('activities', sa.Column('is_race_candidate', sa.Boolean(), server_default='false'))
    op.add_column('activities', sa.Column('race_confidence', sa.Float(), nullable=True))
    op.add_column('activities', sa.Column('user_verified_race', sa.Boolean(), nullable=True))
    
    # 3. Enforce the "No Duplicates" rule
    op.create_unique_constraint('uq_provider_external_id', 'activities', ['provider', 'external_activity_id'])


def downgrade() -> None:
    pass



