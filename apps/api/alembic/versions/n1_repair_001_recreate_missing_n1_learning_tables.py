"""Recreate missing N=1 learning tables (prod repair)

Revision ID: n1_repair_001
Revises: briefing_persist_001
Create Date: 2026-04-16

Context
-------
The original `n1_learning_001` migration (`add_n1_learning_tables.py`) is
in the alembic chain and its downgrade/upgrade pair is healthy, but at
some point before this commit landed the production database ended up
past that revision while lacking three of the four tables it creates:

  - athlete_calibrated_model
  - athlete_workout_response
  - athlete_learning

(`feature_flag` survived because it was written with `CREATE TABLE IF
NOT EXISTS`.)  The symptom was continuous warning spam from
`services.individual_performance_model.get_or_calibrate_model` on every
/v1/home request:

    Model cache lookup unavailable; falling back to live calibration:
    (psycopg2.errors.UndefinedTable) relation
    "athlete_calibrated_model" does not exist

The runtime already falls back gracefully (the warning itself says
"non-critical"), but the model cache can never populate, so the Banister
calibration is rerun on every request for every athlete.  Fixing the
prod schema restores that cache path and silences the log spam.

Approach
--------
Forward-only repair migration using `CREATE TABLE IF NOT EXISTS` so it
is a no-op in any environment where the tables already exist (e.g. the
test DB, local dev created from scratch) and creates them cleanly
everywhere they are missing (prod).  All indexes / constraints are
likewise created with `IF NOT EXISTS`.

Schema is copied verbatim from the original `n1_learning_001`
migration and matches the SQLAlchemy models in `models/athlete.py`.
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "n1_repair_001"
down_revision = "briefing_persist_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS athlete_calibrated_model (
            athlete_id UUID PRIMARY KEY REFERENCES athlete(id),
            tau1 DOUBLE PRECISION NOT NULL,
            tau2 DOUBLE PRECISION NOT NULL,
            k1 DOUBLE PRECISION NOT NULL,
            k2 DOUBLE PRECISION NOT NULL,
            p0 DOUBLE PRECISION NOT NULL,
            r_squared DOUBLE PRECISION,
            fit_error DOUBLE PRECISION,
            n_performance_markers INTEGER,
            n_training_days INTEGER,
            confidence TEXT NOT NULL,
            data_tier TEXT NOT NULL,
            confidence_notes JSONB,
            calibrated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            valid_until DATE
        );
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS athlete_workout_response (
            id UUID PRIMARY KEY,
            athlete_id UUID NOT NULL REFERENCES athlete(id),
            stimulus_type TEXT NOT NULL,
            avg_rpe_gap DOUBLE PRECISION,
            rpe_gap_stddev DOUBLE PRECISION,
            completion_rate DOUBLE PRECISION,
            adaptation_signal DOUBLE PRECISION,
            n_observations INTEGER NOT NULL DEFAULT 0,
            first_observation TIMESTAMPTZ,
            last_updated TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_athlete_workout_response_athlete_id "
        "ON athlete_workout_response (athlete_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_athlete_workout_response_stimulus "
        "ON athlete_workout_response (stimulus_type);"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_athlete_stimulus_response'
            ) THEN
                ALTER TABLE athlete_workout_response
                    ADD CONSTRAINT uq_athlete_stimulus_response
                    UNIQUE (athlete_id, stimulus_type);
            END IF;
        END$$;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS athlete_learning (
            id UUID PRIMARY KEY,
            athlete_id UUID NOT NULL REFERENCES athlete(id),
            learning_type TEXT NOT NULL,
            subject TEXT NOT NULL,
            evidence JSONB,
            confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
            discovered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            source TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT true,
            superseded_by UUID REFERENCES athlete_learning(id)
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_athlete_learning_athlete_id "
        "ON athlete_learning (athlete_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_athlete_learning_type "
        "ON athlete_learning (learning_type);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_athlete_learning_subject "
        "ON athlete_learning (subject);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_athlete_learning_active "
        "ON athlete_learning (is_active);"
    )


def downgrade() -> None:
    # Intentional no-op: this is a forward-only repair.  Dropping these
    # tables on downgrade would hide the original problem and could lose
    # data.  The original `n1_learning_001` downgrade still handles table
    # removal for a clean rollback of that ADR.
    pass
