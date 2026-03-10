"""Runtoon Share Flow: add share columns to Activity and RuntoonImage.

Revision ID: runtoon_002
Revises: runtoon_001
Create Date: 2026-03-01

Changes:
- Activity.share_dismissed_at (timestamp, nullable): set when athlete dismisses
  the share prompt for a specific run. Keyed by activity, not by RuntoonImage,
  because dismiss happens before any image is generated.
- RuntoonImage.shared_at (timestamp, nullable): when athlete tapped Share.
- RuntoonImage.share_format (varchar, nullable): "1:1" or "9:16".
- RuntoonImage.share_target (varchar, nullable): best-effort telemetry only.
  Web Share API does not reliably report the selected app. Defaults to
  "unknown". No logic should depend on this value.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "runtoon_002"
down_revision: Union[str, None] = "runtoon_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    from sqlalchemy import inspect
    inspector = inspect(conn)

    # ── Activity: share_dismissed_at ─────────────────────────────────────────
    if inspector.has_table("activity"):
        existing = {c["name"] for c in inspector.get_columns("activity")}
        if "share_dismissed_at" not in existing:
            op.add_column(
                "activity",
                sa.Column("share_dismissed_at", sa.DateTime(timezone=True), nullable=True),
            )

    # ── RuntoonImage: shared_at, share_format, share_target ─────────────────
    if inspector.has_table("runtoon_image"):
        existing = {c["name"] for c in inspector.get_columns("runtoon_image")}
        if "shared_at" not in existing:
            op.add_column(
                "runtoon_image",
                sa.Column("shared_at", sa.DateTime(timezone=True), nullable=True),
            )
        if "share_format" not in existing:
            op.add_column(
                "runtoon_image",
                sa.Column("share_format", sa.Text, nullable=True),
            )
        if "share_target" not in existing:
            op.add_column(
                "runtoon_image",
                sa.Column("share_target", sa.Text, nullable=True),
            )


def downgrade() -> None:
    op.drop_column("runtoon_image", "share_target")
    op.drop_column("runtoon_image", "share_format")
    op.drop_column("runtoon_image", "shared_at")
    op.drop_column("activity", "share_dismissed_at")
