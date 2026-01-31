"""add_grant_tier_to_invite_allowlist

Revision ID: a1b2c3d4e5f6
Revises: 9033f613c815
Create Date: 2026-01-31

Adds grant_tier column to invite_allowlist table.
When set (e.g., "pro"), user automatically gets that subscription tier on signup.
Used for beta testers who should get free pro access.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '9033f613c815'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add grant_tier column to invite_allowlist
    # Nullable - only set for invites that should grant a specific tier
    op.add_column(
        'invite_allowlist',
        sa.Column('grant_tier', sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('invite_allowlist', 'grant_tier')
