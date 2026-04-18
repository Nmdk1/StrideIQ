"""Add user-named meal columns to meal_template

Revision ID: meal_template_named_001
Revises: athlete_food_override_001
Create Date: 2026-04-18

Phase 3 of the nutrition product family.

Adds explicit naming + provenance columns so an athlete can save a meal
("Workday Breakfast") and re-log it in one tap, while keeping backward
compatibility with implicitly learned signature templates.

  - name              user-given title; null for implicit templates
  - is_user_named     true when athlete explicitly saved/named the meal
  - name_prompted_at  when we surfaced the "name this meal" prompt so
                      we don't re-prompt forever
  - created_at        explicit creation timestamp (existing rows get NOW)

A partial index on (athlete_id) WHERE is_user_named = true keeps the
"my meals" picker fast as the implicit template count grows.

Idempotent.
"""

from alembic import op


revision = "meal_template_named_001"
down_revision = "athlete_food_override_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE meal_template "
        "ADD COLUMN IF NOT EXISTS name TEXT;"
    )
    op.execute(
        "ALTER TABLE meal_template "
        "ADD COLUMN IF NOT EXISTS is_user_named BOOLEAN NOT NULL DEFAULT FALSE;"
    )
    op.execute(
        "ALTER TABLE meal_template "
        "ADD COLUMN IF NOT EXISTS name_prompted_at TIMESTAMPTZ;"
    )
    op.execute(
        "ALTER TABLE meal_template "
        "ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_meal_template_athlete_named "
        "ON meal_template (athlete_id) WHERE is_user_named = true;"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_meal_template_athlete_named;")
    op.execute("ALTER TABLE meal_template DROP COLUMN IF EXISTS created_at;")
    op.execute("ALTER TABLE meal_template DROP COLUMN IF EXISTS name_prompted_at;")
    op.execute("ALTER TABLE meal_template DROP COLUMN IF EXISTS is_user_named;")
    op.execute("ALTER TABLE meal_template DROP COLUMN IF EXISTS name;")
