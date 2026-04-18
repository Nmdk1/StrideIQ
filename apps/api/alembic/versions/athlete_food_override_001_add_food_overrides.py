"""Add athlete_food_override + nutrition_entry source ref columns

Revision ID: athlete_food_override_001
Revises: training_block_001
Create Date: 2026-04-18

Phase 2 of the nutrition product family. Stores per-athlete corrections
to scanned/branded foods so that the next time the athlete scans the
same UPC or fdc_id, we return their corrected values instead of the
generic catalog defaults.

Idempotent:
  - CREATE TABLE IF NOT EXISTS for athlete_food_override
  - ADD COLUMN IF NOT EXISTS for nutrition_entry source-ref columns
  - CREATE INDEX IF NOT EXISTS for all indexes
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "athlete_food_override_001"
down_revision = "training_block_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS athlete_food_override (
            id BIGSERIAL PRIMARY KEY,
            athlete_id UUID NOT NULL REFERENCES athlete(id) ON DELETE CASCADE,

            upc TEXT,
            fdc_id INTEGER,
            fueling_product_id INTEGER REFERENCES fueling_product(id) ON DELETE CASCADE,

            food_name TEXT,

            serving_size_g DOUBLE PRECISION,
            calories DOUBLE PRECISION,
            protein_g DOUBLE PRECISION,
            carbs_g DOUBLE PRECISION,
            fat_g DOUBLE PRECISION,
            fiber_g DOUBLE PRECISION,
            caffeine_mg DOUBLE PRECISION,
            sodium_mg DOUBLE PRECISION,

            times_applied INTEGER NOT NULL DEFAULT 0,
            last_applied_at TIMESTAMPTZ,

            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ,

            CONSTRAINT ck_athlete_food_override_one_identifier
                CHECK (
                    (CASE WHEN upc IS NOT NULL THEN 1 ELSE 0 END
                   + CASE WHEN fdc_id IS NOT NULL THEN 1 ELSE 0 END
                   + CASE WHEN fueling_product_id IS NOT NULL THEN 1 ELSE 0 END) = 1
                )
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_athlete_food_override_athlete "
        "ON athlete_food_override (athlete_id);"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_athlete_food_override_upc "
        "ON athlete_food_override (athlete_id, upc) WHERE upc IS NOT NULL;"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_athlete_food_override_fdc "
        "ON athlete_food_override (athlete_id, fdc_id) WHERE fdc_id IS NOT NULL;"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_athlete_food_override_fpid "
        "ON athlete_food_override (athlete_id, fueling_product_id) "
        "WHERE fueling_product_id IS NOT NULL;"
    )

    op.execute(
        "ALTER TABLE nutrition_entry "
        "ADD COLUMN IF NOT EXISTS source_fdc_id INTEGER;"
    )
    op.execute(
        "ALTER TABLE nutrition_entry "
        "ADD COLUMN IF NOT EXISTS source_upc TEXT;"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_nutrition_entry_source_fdc "
        "ON nutrition_entry (source_fdc_id) WHERE source_fdc_id IS NOT NULL;"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_nutrition_entry_source_upc "
        "ON nutrition_entry (source_upc) WHERE source_upc IS NOT NULL;"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_nutrition_entry_source_upc;")
    op.execute("DROP INDEX IF EXISTS ix_nutrition_entry_source_fdc;")
    op.execute("ALTER TABLE nutrition_entry DROP COLUMN IF EXISTS source_upc;")
    op.execute("ALTER TABLE nutrition_entry DROP COLUMN IF EXISTS source_fdc_id;")

    op.execute("DROP INDEX IF EXISTS uq_athlete_food_override_fpid;")
    op.execute("DROP INDEX IF EXISTS uq_athlete_food_override_fdc;")
    op.execute("DROP INDEX IF EXISTS uq_athlete_food_override_upc;")
    op.execute("DROP INDEX IF EXISTS ix_athlete_food_override_athlete;")
    op.execute("DROP TABLE IF EXISTS athlete_food_override;")
