"""Add Phase 3A narration tables and columns

Revision ID: narration_001
Revises: self_regulation_001 (narration_log has FK to insight_log.id)
Create Date: 2026-02-13

Phase 3A: Adaptation Narration
- New columns on insight_log: narrative, narrative_score, narrative_contradicts
- New table: narration_log
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = 'narration_001'
down_revision = 'self_regulation_001'
branch_labels = None
depends_on = None


def upgrade():
    # ---------------------------------------------------------------
    # New columns on insight_log
    # ---------------------------------------------------------------
    conn = op.get_bind()

    # Check existing columns to avoid duplicate adds
    from sqlalchemy import inspect
    inspector = inspect(conn)

    if inspector.has_table("insight_log"):
        existing_columns = {c["name"] for c in inspector.get_columns("insight_log")}

        if "narrative" not in existing_columns:
            op.add_column("insight_log", sa.Column("narrative", sa.Text, nullable=True))
        if "narrative_score" not in existing_columns:
            op.add_column("insight_log", sa.Column("narrative_score", sa.Float, nullable=True))
        if "narrative_contradicts" not in existing_columns:
            op.add_column("insight_log", sa.Column("narrative_contradicts", sa.Boolean, nullable=True))

    # ---------------------------------------------------------------
    # New table: narration_log
    # ---------------------------------------------------------------
    if not inspector.has_table("narration_log"):
        op.create_table(
            "narration_log",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("athlete_id", UUID(as_uuid=True), sa.ForeignKey("athlete.id"), nullable=False, index=True),
            sa.Column("insight_log_id", UUID(as_uuid=True), sa.ForeignKey("insight_log.id"), nullable=True),

            sa.Column("trigger_date", sa.Date, nullable=False),
            sa.Column("rule_id", sa.Text, nullable=False),
            sa.Column("narration_text", sa.Text, nullable=True),
            sa.Column("prompt_used", sa.Text, nullable=True),

            sa.Column("ground_truth", JSONB, nullable=True),

            sa.Column("factually_correct", sa.Boolean, nullable=True),
            sa.Column("no_raw_metrics", sa.Boolean, nullable=True),
            sa.Column("actionable_language", sa.Boolean, nullable=True),
            sa.Column("criteria_passed", sa.Integer, nullable=True),
            sa.Column("score", sa.Float, nullable=True),

            sa.Column("contradicts_engine", sa.Boolean, nullable=False, server_default="false"),
            sa.Column("contradiction_detail", sa.Text, nullable=True),

            sa.Column("suppressed", sa.Boolean, nullable=False, server_default="false"),
            sa.Column("suppression_reason", sa.Text, nullable=True),

            sa.Column("model_used", sa.Text, nullable=True),
            sa.Column("input_tokens", sa.Integer, nullable=True),
            sa.Column("output_tokens", sa.Integer, nullable=True),
            sa.Column("latency_ms", sa.Integer, nullable=True),

            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

        # Indexes
        op.create_index("ix_narration_log_athlete_date", "narration_log", ["athlete_id", "trigger_date"])
        op.create_index("ix_narration_log_score", "narration_log", ["score"])


def downgrade():
    op.drop_table("narration_log")
    op.drop_column("insight_log", "narrative")
    op.drop_column("insight_log", "narrative_score")
    op.drop_column("insight_log", "narrative_contradicts")
