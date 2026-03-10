"""garmin_002: Add Garmin-specific activity columns

Revision ID: garmin_002
Revises: garmin_001
Create Date: 2026-02-22

Phase 2 / D1.2 — running dynamics, power, and other Garmin-only
fields on the Activity model. All columns nullable so existing
Strava activities are unaffected and require no backfill.

See docs/PHASE2_GARMIN_INTEGRATION_AC.md §D1.2
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "garmin_002"
down_revision: Union[str, None] = "garmin_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Running dynamics ---
    op.add_column("activity", sa.Column("avg_cadence", sa.Integer(), nullable=True))
    op.add_column("activity", sa.Column("max_cadence", sa.Integer(), nullable=True))
    op.add_column("activity", sa.Column("avg_stride_length_m", sa.Float(), nullable=True))
    op.add_column("activity", sa.Column("avg_ground_contact_ms", sa.Float(), nullable=True))
    op.add_column("activity", sa.Column("avg_ground_contact_balance_pct", sa.Float(), nullable=True))
    op.add_column("activity", sa.Column("avg_vertical_oscillation_cm", sa.Float(), nullable=True))
    op.add_column("activity", sa.Column("avg_vertical_ratio_pct", sa.Float(), nullable=True))

    # --- Power ---
    op.add_column("activity", sa.Column("avg_power_w", sa.Integer(), nullable=True))
    op.add_column("activity", sa.Column("max_power_w", sa.Integer(), nullable=True))

    # --- Effort / grade ---
    op.add_column("activity", sa.Column("avg_gap_min_per_mile", sa.Float(), nullable=True))
    op.add_column("activity", sa.Column("total_descent_m", sa.Float(), nullable=True))

    # --- Garmin Training Effect (informational only — see annotations in model) ---
    op.add_column("activity", sa.Column("garmin_aerobic_te", sa.Float(), nullable=True))
    op.add_column("activity", sa.Column("garmin_anaerobic_te", sa.Float(), nullable=True))
    op.add_column("activity", sa.Column("garmin_te_label", sa.Text(), nullable=True))

    # --- Athlete self-evaluation (low-fidelity — see annotations in model) ---
    op.add_column("activity", sa.Column("garmin_feel", sa.Text(), nullable=True))
    op.add_column("activity", sa.Column("garmin_perceived_effort", sa.Integer(), nullable=True))

    # --- Wellness crossover ---
    op.add_column("activity", sa.Column("garmin_body_battery_impact", sa.Integer(), nullable=True))

    # --- Timing / kilojoules ---
    op.add_column("activity", sa.Column("moving_time_s", sa.Integer(), nullable=True))
    op.add_column("activity", sa.Column("max_speed", sa.Float(), nullable=True))
    op.add_column("activity", sa.Column("active_kcal", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("activity", "active_kcal")
    op.drop_column("activity", "max_speed")
    op.drop_column("activity", "moving_time_s")
    op.drop_column("activity", "garmin_body_battery_impact")
    op.drop_column("activity", "garmin_perceived_effort")
    op.drop_column("activity", "garmin_feel")
    op.drop_column("activity", "garmin_te_label")
    op.drop_column("activity", "garmin_anaerobic_te")
    op.drop_column("activity", "garmin_aerobic_te")
    op.drop_column("activity", "total_descent_m")
    op.drop_column("activity", "avg_gap_min_per_mile")
    op.drop_column("activity", "max_power_w")
    op.drop_column("activity", "avg_power_w")
    op.drop_column("activity", "avg_vertical_ratio_pct")
    op.drop_column("activity", "avg_vertical_oscillation_cm")
    op.drop_column("activity", "avg_ground_contact_balance_pct")
    op.drop_column("activity", "avg_ground_contact_ms")
    op.drop_column("activity", "avg_stride_length_m")
    op.drop_column("activity", "max_cadence")
    op.drop_column("activity", "avg_cadence")
