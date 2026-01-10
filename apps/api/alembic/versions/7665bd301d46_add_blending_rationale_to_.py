"""add_blending_rationale_to_recommendations

Revision ID: 7665bd301d46
Revises: add_tags_kb
Create Date: 2026-01-04 23:10:12.416864

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '7665bd301d46'
down_revision: Union[str, None] = 'add_tags_kb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add blending_rationale JSONB column to coaching_recommendation table
    op.add_column(
        'coaching_recommendation',
        sa.Column('blending_rationale', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('coaching_recommendation', 'blending_rationale')




