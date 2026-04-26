"""Strength v1 schema additions (Phase A).

Revision ID: strength_v1_002
Revises: strength_v1_001
Create Date: 2026-04-19

Phase A of the Strength v1 sandbox build (see
docs/specs/STRENGTH_V1_SCOPE.md §5).

Additions are purely additive. No backfills, no destructive changes.

1. ``strength_exercise_set`` gains nine columns:
   - rpe, implement_type, set_modifier, tempo, notes, source,
     manually_augmented, superseded_by_id, superseded_at
   The supersede pair makes edits non-destructive: we never delete or
   in-place mutate a logged set; an edit inserts a new row pointing back
   at its predecessor and stamps ``superseded_at`` on the old.

2. ``athlete`` gains three columns for the lifting-baseline question:
   lifts_currently, lift_days_per_week, lift_experience_bucket. All
   nullable. Onboarding fills these; nothing else reads them yet.

3. New tables:
   - ``strength_routine``      — athlete-saved patterns (NOT system-curated)
   - ``strength_goal``         — athlete-set goals (NOT system-suggested)
   - ``body_area_symptom_log`` — niggles / aches / pains / injury, runner
                                 language, athlete-entered only

Idempotent — safe to re-run.
"""

from alembic import op


revision = "strength_v1_002"
down_revision = "strength_v1_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. strength_exercise_set additive columns.
    op.execute(
        """
        ALTER TABLE strength_exercise_set
            ADD COLUMN IF NOT EXISTS rpe DOUBLE PRECISION,
            ADD COLUMN IF NOT EXISTS implement_type TEXT,
            ADD COLUMN IF NOT EXISTS set_modifier TEXT,
            ADD COLUMN IF NOT EXISTS tempo TEXT,
            ADD COLUMN IF NOT EXISTS notes TEXT,
            ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'garmin',
            ADD COLUMN IF NOT EXISTS manually_augmented BOOLEAN NOT NULL DEFAULT false,
            ADD COLUMN IF NOT EXISTS superseded_by_id UUID,
            ADD COLUMN IF NOT EXISTS superseded_at TIMESTAMPTZ;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'strength_exercise_set_superseded_by_fk'
            ) THEN
                ALTER TABLE strength_exercise_set
                    ADD CONSTRAINT strength_exercise_set_superseded_by_fk
                    FOREIGN KEY (superseded_by_id)
                    REFERENCES strength_exercise_set(id)
                    ON DELETE SET NULL;
            END IF;
        END $$;
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_strength_set_active "
        "ON strength_exercise_set (athlete_id, activity_id) "
        "WHERE superseded_at IS NULL;"
    )

    # 2. athlete additive columns for lifting baseline.
    op.execute(
        """
        ALTER TABLE athlete
            ADD COLUMN IF NOT EXISTS lifts_currently TEXT,
            ADD COLUMN IF NOT EXISTS lift_days_per_week DOUBLE PRECISION,
            ADD COLUMN IF NOT EXISTS lift_experience_bucket TEXT;
        """
    )

    # 3. strength_routine.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS strength_routine (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            athlete_id UUID NOT NULL REFERENCES athlete(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            items JSONB NOT NULL DEFAULT '[]'::jsonb,
            last_used_at TIMESTAMPTZ,
            times_used INTEGER NOT NULL DEFAULT 0,
            is_archived BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_strength_routine_athlete "
        "ON strength_routine (athlete_id) WHERE is_archived = false;"
    )

    # 4. strength_goal.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS strength_goal (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            athlete_id UUID NOT NULL REFERENCES athlete(id) ON DELETE CASCADE,
            goal_type TEXT NOT NULL,
            exercise_name TEXT,
            target_value DOUBLE PRECISION,
            target_unit TEXT,
            target_date DATE,
            coupled_running_metric TEXT,
            notes TEXT,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_strength_goal_athlete_active "
        "ON strength_goal (athlete_id) WHERE is_active = true;"
    )

    # 5. body_area_symptom_log.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS body_area_symptom_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            athlete_id UUID NOT NULL REFERENCES athlete(id) ON DELETE CASCADE,
            body_area TEXT NOT NULL,
            severity TEXT NOT NULL,
            started_at DATE NOT NULL,
            resolved_at DATE,
            triggered_by TEXT,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_body_symptom_athlete_active "
        "ON body_area_symptom_log (athlete_id, started_at DESC) "
        "WHERE resolved_at IS NULL;"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_body_symptom_athlete_area "
        "ON body_area_symptom_log (athlete_id, body_area, started_at DESC);"
    )


def downgrade() -> None:
    # Drop new tables first (no FKs from elsewhere into them).
    op.execute("DROP TABLE IF EXISTS body_area_symptom_log;")
    op.execute("DROP TABLE IF EXISTS strength_goal;")
    op.execute("DROP TABLE IF EXISTS strength_routine;")

    # Athlete columns.
    op.execute(
        """
        ALTER TABLE athlete
            DROP COLUMN IF EXISTS lift_experience_bucket,
            DROP COLUMN IF EXISTS lift_days_per_week,
            DROP COLUMN IF EXISTS lifts_currently;
        """
    )

    # strength_exercise_set columns + constraint + partial index.
    op.execute("DROP INDEX IF EXISTS ix_strength_set_active;")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'strength_exercise_set_superseded_by_fk'
            ) THEN
                ALTER TABLE strength_exercise_set
                    DROP CONSTRAINT strength_exercise_set_superseded_by_fk;
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        ALTER TABLE strength_exercise_set
            DROP COLUMN IF EXISTS superseded_at,
            DROP COLUMN IF EXISTS superseded_by_id,
            DROP COLUMN IF EXISTS manually_augmented,
            DROP COLUMN IF EXISTS source,
            DROP COLUMN IF EXISTS notes,
            DROP COLUMN IF EXISTS tempo,
            DROP COLUMN IF EXISTS set_modifier,
            DROP COLUMN IF EXISTS implement_type,
            DROP COLUMN IF EXISTS rpe;
        """
    )
