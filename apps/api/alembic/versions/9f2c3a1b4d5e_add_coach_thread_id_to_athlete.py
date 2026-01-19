"""add_coach_thread_id_to_athlete

Revision ID: 9f2c3a1b4d5e
Revises: 67e871e3b7c2
Create Date: 2026-01-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9f2c3a1b4d5e"
down_revision: Union[str, None] = "67e871e3b7c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("athlete", sa.Column("coach_thread_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("athlete", "coach_thread_id")

