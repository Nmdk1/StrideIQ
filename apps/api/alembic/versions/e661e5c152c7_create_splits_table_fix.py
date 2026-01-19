"""create_splits_table_fix

Revision ID: e661e5c152c7
Revises: 8ca181dbd12e
Create Date: 2026-01-02 07:45:37.154813

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e661e5c152c7'
down_revision: Union[str, None] = '8ca181dbd12e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Historical fix migration.

    Some environments may already have `activity_split` created by an earlier revision.
    Make this migration idempotent so fresh installs and upgraded installs both work.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "activity_split" not in inspector.get_table_names():
        op.create_table(
            "activity_split",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("activity_id", sa.UUID(), nullable=False),
            sa.Column("split_number", sa.Integer(), nullable=False),
            sa.Column("distance", sa.Numeric(), nullable=True),
            sa.Column("elapsed_time", sa.Integer(), nullable=True),
            sa.Column("moving_time", sa.Integer(), nullable=True),
            sa.Column("average_heartrate", sa.Integer(), nullable=True),
            sa.Column("max_heartrate", sa.Integer(), nullable=True),
            sa.Column("average_cadence", sa.Numeric(), nullable=True),
            sa.ForeignKeyConstraint(["activity_id"], ["activity.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    existing_indexes = {ix["name"] for ix in inspector.get_indexes("activity_split")}
    if "ix_activity_split_activity_id" not in existing_indexes:
        op.create_index("ix_activity_split_activity_id", "activity_split", ["activity_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "activity_split" not in inspector.get_table_names():
        return

    existing_indexes = {ix["name"] for ix in inspector.get_indexes("activity_split")}
    if "ix_activity_split_activity_id" in existing_indexes:
        op.drop_index("ix_activity_split_activity_id", table_name="activity_split")

    op.drop_table("activity_split")



