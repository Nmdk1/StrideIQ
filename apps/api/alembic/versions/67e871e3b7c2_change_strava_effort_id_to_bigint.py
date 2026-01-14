"""change_strava_effort_id_to_bigint

Revision ID: 67e871e3b7c2
Revises: df6a2e9fd0ec
Create Date: 2026-01-14 21:24:08.351072

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '67e871e3b7c2'
down_revision: Union[str, None] = 'df6a2e9fd0ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Change strava_effort_id from INTEGER to BIGINT.
    
    Strava effort IDs exceed 32-bit integer max (2,147,483,647).
    Example: 71766851694 causes "integer out of range" error.
    
    This is a safe, non-destructive change - BIGINT can store all INTEGER values.
    """
    op.alter_column('best_effort', 'strava_effort_id',
               existing_type=sa.INTEGER(),
               type_=sa.BigInteger(),
               existing_nullable=True)


def downgrade() -> None:
    """
    Revert strava_effort_id from BIGINT to INTEGER.
    
    WARNING: This will fail if any strava_effort_id values exceed INTEGER max.
    """
    op.alter_column('best_effort', 'strava_effort_id',
               existing_type=sa.BigInteger(),
               type_=sa.INTEGER(),
               existing_nullable=True)




