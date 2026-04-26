"""Merge heads before adaptive replan migration.

Revision ID: adaptive_replan_000
Revises: athlete_override_001, wellness_stamp_001
Create Date: 2026-04-04
"""
from typing import Sequence, Union

revision: str = "adaptive_replan_000"
down_revision: Union[str, None] = ("athlete_override_001", "wellness_stamp_001")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
