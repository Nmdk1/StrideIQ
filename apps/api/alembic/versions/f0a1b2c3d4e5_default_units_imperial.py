"""default preferred_units to imperial

Revision ID: f0a1b2c3d4e5
Revises: e6f7a8b9c0d1
Create Date: 2026-01-24
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f0a1b2c3d4e5"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # US-first product default: miles/imperial.
    op.alter_column("athlete", "preferred_units", server_default=sa.text("'imperial'"))

    # Early-stage product: align existing users to imperial by default.
    # Users can still switch in Settings.
    op.execute("UPDATE athlete SET preferred_units = 'imperial' WHERE preferred_units = 'metric';")


def downgrade() -> None:
    op.execute("UPDATE athlete SET preferred_units = 'metric' WHERE preferred_units = 'imperial';")
    op.alter_column("athlete", "preferred_units", server_default=sa.text("'metric'"))

