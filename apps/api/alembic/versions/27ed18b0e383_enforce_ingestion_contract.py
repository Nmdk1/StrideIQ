"""enforce_ingestion_contract

Revision ID: 27ed18b0e383
Revises: e661e5c152c7
Create Date: 2026-01-02 19:27:36.147955

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '27ed18b0e383'
down_revision: Union[str, None] = 'e661e5c152c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Enforce ingestion contract.

    Notes:
    - `connected_accounts` may not exist in all schemas; apply that change only if present.
    - Activity ingestion fields are added in the follow-up migration
      `c047bd6a61d4_add_ingestion_contract_fields` and should NOT be duplicated here.
    """
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    # 1) Add sync cursor to ConnectedAccount (optional table)
    if "connected_accounts" in tables:
        existing_cols = {col["name"] for col in inspector.get_columns("connected_accounts")}
        if "last_sync_at" not in existing_cols:
            op.add_column(
                "connected_accounts",
                sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "connected_accounts" in tables:
        cols = {col["name"] for col in inspector.get_columns("connected_accounts")}
        if "last_sync_at" in cols:
            op.drop_column("connected_accounts", "last_sync_at")



