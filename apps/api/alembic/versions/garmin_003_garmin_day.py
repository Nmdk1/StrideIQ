"""garmin_003: Create garmin_day table

Revision ID: garmin_003
Revises: garmin_002
Create Date: 2026-02-22

Phase 2 / D1.3 — unified daily wellness table. One row per
(athlete_id, calendar_date). Replaces any GarminSleep / GarminHRV
split-table designs from earlier discovery documents. Architecture
decision 3D: single GarminDay model.

calendar_date is the wakeup day (morning), not the night before.
When joining sleep to activity: garmin_day.calendar_date = activity.start_time::date
(L1 rule — enforced by test).

See docs/PHASE2_GARMIN_INTEGRATION_AC.md §D1.3
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision: str = "garmin_003"
down_revision: Union[str, None] = "garmin_002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "garmin_day",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "athlete_id",
            UUID(as_uuid=True),
            sa.ForeignKey("athlete.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("calendar_date", sa.Date(), nullable=False),

        # --- Daily Summary ---
        sa.Column("resting_hr", sa.Integer(), nullable=True),
        sa.Column("avg_stress", sa.Integer(), nullable=True),   # -1 = insufficient data
        sa.Column("max_stress", sa.Integer(), nullable=True),
        sa.Column("stress_qualifier", sa.Text(), nullable=True),  # calm/balanced/stressful/very_stressful
        sa.Column("steps", sa.Integer(), nullable=True),
        sa.Column("active_time_s", sa.Integer(), nullable=True),
        sa.Column("active_kcal", sa.Integer(), nullable=True),
        sa.Column("moderate_intensity_s", sa.Integer(), nullable=True),
        sa.Column("vigorous_intensity_s", sa.Integer(), nullable=True),
        sa.Column("min_hr", sa.Integer(), nullable=True),
        sa.Column("max_hr", sa.Integer(), nullable=True),

        # --- Sleep Summary ---
        sa.Column("sleep_total_s", sa.Integer(), nullable=True),
        sa.Column("sleep_deep_s", sa.Integer(), nullable=True),
        sa.Column("sleep_light_s", sa.Integer(), nullable=True),
        sa.Column("sleep_rem_s", sa.Integer(), nullable=True),
        sa.Column("sleep_awake_s", sa.Integer(), nullable=True),
        sa.Column("sleep_score", sa.Integer(), nullable=True),          # 0–100
        sa.Column("sleep_score_qualifier", sa.Text(), nullable=True),   # EXCELLENT/GOOD/FAIR/POOR
        sa.Column("sleep_validation", sa.Text(), nullable=True),

        # --- HRV Summary ---
        sa.Column("hrv_overnight_avg", sa.Integer(), nullable=True),    # ms
        sa.Column("hrv_5min_high", sa.Integer(), nullable=True),        # ms

        # --- User Metrics ---
        sa.Column("vo2max", sa.Float(), nullable=True),                 # updates infrequently

        # --- Body Battery (from Stress Detail) ---
        sa.Column("body_battery_end", sa.Integer(), nullable=True),     # end-of-day value

        # --- Raw JSONB (Tier 2 computed fields deferred) ---
        sa.Column("stress_samples", JSONB(), nullable=True),            # TimeOffsetStressLevelValues
        sa.Column("body_battery_samples", JSONB(), nullable=True),      # TimeOffsetBodyBatteryValues

        # --- Deduplication ---
        sa.Column("garmin_daily_summary_id", sa.Text(), nullable=True),
        sa.Column("garmin_sleep_summary_id", sa.Text(), nullable=True),
        sa.Column("garmin_hrv_summary_id", sa.Text(), nullable=True),

        # --- Audit ---
        sa.Column(
            "inserted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Unique constraint: one row per athlete per day
    op.create_unique_constraint(
        "uq_garmin_day_athlete_date",
        "garmin_day",
        ["athlete_id", "calendar_date"],
    )

    op.create_index(
        "ix_garmin_day_athlete_id",
        "garmin_day",
        ["athlete_id"],
    )
    op.create_index(
        "ix_garmin_day_calendar_date",
        "garmin_day",
        ["calendar_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_garmin_day_calendar_date", table_name="garmin_day")
    op.drop_index("ix_garmin_day_athlete_id", table_name="garmin_day")
    op.drop_constraint("uq_garmin_day_athlete_date", "garmin_day", type_="unique")
    op.drop_table("garmin_day")
