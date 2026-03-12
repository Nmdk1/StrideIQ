"""AutoDiscovery Phase 1 — live mutation schema

Adds:
  - auto_discovery_change_log      (typed durable change ledger)
  - athlete_investigation_config   (per-athlete investigation param overrides)
  - auto_discovery_scan_coverage   (search-space coverage tracker)
  - correlation_finding stability fields (discovery_source, discovery_window_days,
      stability_class, windows_confirmed, stability_checked_at)

Revision ID: auto_discovery_phase1_001
Revises: phase3c_001
Create Date: 2026-03-12
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "auto_discovery_phase1_001"
down_revision = "phase3c_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── auto_discovery_change_log ──────────────────────────────────────────
    op.create_table(
        "auto_discovery_change_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("auto_discovery_run.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("change_type", sa.Text, nullable=False),
        sa.Column("change_key", sa.Text, nullable=False),
        sa.Column("before_state", postgresql.JSONB, nullable=True),
        sa.Column("after_state", postgresql.JSONB, nullable=True),
        sa.Column("reverted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("reverted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reverted_by", sa.Text, nullable=True),
        sa.Column("revert_reason", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # Prevent duplicate ledger entries for the same mutation in the same run
        sa.UniqueConstraint(
            "athlete_id", "change_type", "change_key", "run_id",
            name="uq_adcl_athlete_type_key_run",
        ),
    )
    op.create_index(
        "ix_auto_discovery_change_log_athlete_id",
        "auto_discovery_change_log", ["athlete_id"],
    )
    op.create_index(
        "ix_auto_discovery_change_log_run_id",
        "auto_discovery_change_log", ["run_id"],
    )
    op.create_index(
        "ix_auto_discovery_change_log_reverted",
        "auto_discovery_change_log", ["athlete_id", "reverted"],
    )

    # ── athlete_investigation_config ───────────────────────────────────────
    op.create_table(
        "athlete_investigation_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("investigation_name", sa.Text, nullable=False),
        sa.Column("param_overrides", postgresql.JSONB, nullable=False),
        sa.Column(
            "applied_from_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("auto_discovery_run.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "applied_change_log_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("auto_discovery_change_log.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reverted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("reverted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reverted_by", sa.Text, nullable=True),
        sa.Column("revert_reason", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_aic_athlete_investigation_active",
        "athlete_investigation_config",
        ["athlete_id", "investigation_name", "reverted"],
    )

    # ── auto_discovery_scan_coverage ───────────────────────────────────────
    op.create_table(
        "auto_discovery_scan_coverage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("loop_type", sa.Text, nullable=False),
        sa.Column("test_key", sa.Text, nullable=False),
        sa.Column("input_a", sa.Text, nullable=False),
        sa.Column("input_b", sa.Text, nullable=True),
        sa.Column("output_metric", sa.Text, nullable=False),
        sa.Column("window_days", sa.Integer, nullable=True),
        sa.Column("last_scanned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("result", sa.Text, nullable=False),  # signal / no_signal / error
        sa.Column("scan_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "athlete_id", "loop_type", "test_key",
            name="uq_adsc_athlete_loop_test_key",
        ),
    )
    op.create_index(
        "ix_adsc_athlete_loop",
        "auto_discovery_scan_coverage", ["athlete_id", "loop_type"],
    )
    op.create_index(
        "ix_adsc_athlete_last_scanned",
        "auto_discovery_scan_coverage", ["athlete_id", "last_scanned_at"],
    )

    # ── correlation_finding stability fields ───────────────────────────────
    op.add_column(
        "correlation_finding",
        sa.Column("discovery_source", sa.Text, nullable=True),
    )
    op.add_column(
        "correlation_finding",
        sa.Column("discovery_window_days", sa.Integer, nullable=True),
    )
    op.add_column(
        "correlation_finding",
        sa.Column("stability_class", sa.Text, nullable=True),
    )
    op.add_column(
        "correlation_finding",
        sa.Column("windows_confirmed", sa.Integer, nullable=True),
    )
    op.add_column(
        "correlation_finding",
        sa.Column("stability_checked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("correlation_finding", "stability_checked_at")
    op.drop_column("correlation_finding", "windows_confirmed")
    op.drop_column("correlation_finding", "stability_class")
    op.drop_column("correlation_finding", "discovery_window_days")
    op.drop_column("correlation_finding", "discovery_source")

    op.drop_index("ix_adsc_athlete_last_scanned", "auto_discovery_scan_coverage")
    op.drop_index("ix_adsc_athlete_loop", "auto_discovery_scan_coverage")
    op.drop_table("auto_discovery_scan_coverage")

    op.drop_index("ix_aic_athlete_investigation_active", "athlete_investigation_config")
    op.drop_table("athlete_investigation_config")

    op.drop_index("ix_auto_discovery_change_log_reverted", "auto_discovery_change_log")
    op.drop_index("ix_auto_discovery_change_log_run_id", "auto_discovery_change_log")
    op.drop_index("ix_auto_discovery_change_log_athlete_id", "auto_discovery_change_log")
    op.drop_table("auto_discovery_change_log")
