"""add_ingestion_contract_fields

Revision ID: c047bd6a61d4
Revises: 27ed18b0e383
Create Date: 2026-01-02 20:35:53.481126

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c047bd6a61d4'
down_revision: Union[str, None] = '27ed18b0e383'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add ingestion contract fields to activity table
    op.add_column('activity', sa.Column('provider', sa.Text(), nullable=True))
    op.add_column('activity', sa.Column('external_activity_id', sa.Text(), nullable=True))

    # Add race detection fields
    op.add_column('activity', sa.Column('is_race_candidate', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('activity', sa.Column('race_confidence', sa.Numeric(), nullable=True))
    op.add_column('activity', sa.Column('user_verified_race', sa.Boolean(), nullable=False, server_default=sa.text('false')))

    # Prevent duplicate external IDs per provider
    op.create_unique_constraint(
        'uq_activity_provider_external_id',
        'activity',
        ['provider', 'external_activity_id']
    )

    # Remove server defaults
    op.alter_column('activity', 'is_race_candidate', server_default=None)
    op.alter_column('activity', 'user_verified_race', server_default=None)


def downgrade() -> None:
    op.drop_constraint('uq_activity_provider_external_id', 'activity', type_='unique')
    op.drop_column('activity', 'user_verified_race')
    op.drop_column('activity', 'race_confidence')
    op.drop_column('activity', 'is_race_candidate')
    op.drop_column('activity', 'external_activity_id')
    op.drop_column('activity', 'provider')