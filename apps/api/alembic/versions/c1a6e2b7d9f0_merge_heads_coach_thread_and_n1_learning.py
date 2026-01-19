"""merge_heads_coach_thread_and_n1_learning

Revision ID: c1a6e2b7d9f0
Revises: 9f2c3a1b4d5e, n1_learning_001
Create Date: 2026-01-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c1a6e2b7d9f0"
down_revision: Union[str, None] = ("9f2c3a1b4d5e", "n1_learning_001")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

