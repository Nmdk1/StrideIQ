"""Add pre-activity wellness snapshot columns to activity table.

Stamps each activity with the athlete's wellness state going into it:
sleep, resting HR, both HRV values (recovery peak + overnight avg).
Enables richer correlation research alongside HR, cadence, and pace.

Revision ID: wellness_stamp_001
Revises: cross_training_003
Create Date: 2026-04-04
"""
from alembic import op
import sqlalchemy as sa


revision = "wellness_stamp_001"
down_revision = "cross_training_003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("activity", sa.Column("pre_sleep_h", sa.Float(), nullable=True))
    op.add_column("activity", sa.Column("pre_sleep_score", sa.Integer(), nullable=True))
    op.add_column("activity", sa.Column("pre_resting_hr", sa.Integer(), nullable=True))
    op.add_column("activity", sa.Column("pre_recovery_hrv", sa.Integer(), nullable=True))
    op.add_column("activity", sa.Column("pre_overnight_hrv", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("activity", "pre_overnight_hrv")
    op.drop_column("activity", "pre_recovery_hrv")
    op.drop_column("activity", "pre_resting_hr")
    op.drop_column("activity", "pre_sleep_score")
    op.drop_column("activity", "pre_sleep_h")
