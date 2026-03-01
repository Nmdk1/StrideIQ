"""Runtoon MVP: athlete_photo and runtoon_image tables.

Revision ID: runtoon_001
Revises: monetization_001
Create Date: 2026-03-01

Creates:
- athlete_photo: stores R2 object keys for athlete reference photos used in
  Runtoon generation. Includes consent tracking (consent_at, consent_version).
- runtoon_image: stores R2 object keys for generated Runtoon images, with
  idempotency enforced by UniqueConstraint(activity_id, attempt_number).
  Includes caption_text + stats_text for 9:16 Pillow recompose at download time.

All storage_key columns are R2 object keys — never public URLs.
All access is via signed URLs generated server-side (15-min TTL).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "runtoon_001"
down_revision: Union[str, None] = "monetization_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # athlete_photo
    # ------------------------------------------------------------------
    op.create_table(
        "athlete_photo",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "athlete_id",
            UUID(as_uuid=True),
            sa.ForeignKey("athlete.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("storage_key", sa.Text, nullable=False),
        sa.Column("photo_type", sa.Text, nullable=False),
        sa.Column("mime_type", sa.Text, nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consent_version", sa.Text, nullable=False, server_default="1.0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_athlete_photo_athlete_id", "athlete_photo", ["athlete_id"])

    # ------------------------------------------------------------------
    # runtoon_image
    # ------------------------------------------------------------------
    op.create_table(
        "runtoon_image",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "athlete_id",
            UUID(as_uuid=True),
            sa.ForeignKey("athlete.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "activity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("activity.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("storage_key", sa.Text, nullable=False),
        sa.Column("prompt_hash", sa.Text, nullable=True),
        sa.Column("generation_time_ms", sa.Integer, nullable=True),
        sa.Column("cost_usd", sa.Numeric(6, 4), nullable=True),
        sa.Column(
            "model_version",
            sa.Text,
            nullable=False,
            server_default="gemini-3.1-flash-image-preview",
        ),
        sa.Column("attempt_number", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_visible", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("caption_text", sa.Text, nullable=True),
        sa.Column("stats_text", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_unique_constraint(
        "uq_runtoon_activity_attempt",
        "runtoon_image",
        ["activity_id", "attempt_number"],
    )
    op.create_index("ix_runtoon_image_athlete_id", "runtoon_image", ["athlete_id"])
    op.create_index("ix_runtoon_image_activity_id", "runtoon_image", ["activity_id"])


def downgrade() -> None:
    op.drop_table("runtoon_image")
    op.drop_table("athlete_photo")
