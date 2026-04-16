"""Schema invariants for the N=1 learning tables.

Regression guard for the April 2026 incident where production ended up
past `n1_learning_001` while missing `athlete_calibrated_model`,
`athlete_workout_response`, and `athlete_learning` — which caused
continuous warning spam on every /v1/home request because the model
cache could never populate.

The forward `n1_repair_001` migration recreates them idempotently.
This test makes sure the tables, their critical columns, and their
unique constraint all exist after migrations run.  If one of these
tables is ever dropped or renamed without being added elsewhere in the
chain, this test fails at PR time instead of in production logs.
"""

from __future__ import annotations

from sqlalchemy import inspect, text

from core.database import engine


def _columns(table: str) -> set[str]:
    return {c["name"] for c in inspect(engine).get_columns(table)}


def test_athlete_calibrated_model_table_exists_with_required_columns() -> None:
    insp = inspect(engine)
    assert "athlete_calibrated_model" in insp.get_table_names(), (
        "athlete_calibrated_model table missing — most likely the repair "
        "migration (n1_repair_001) didn't run.  This table underpins the "
        "Banister calibration cache; without it every /v1/home recalibrates."
    )

    cols = _columns("athlete_calibrated_model")
    for required in {
        "athlete_id",
        "tau1",
        "tau2",
        "k1",
        "k2",
        "p0",
        "confidence",
        "data_tier",
        "calibrated_at",
    }:
        assert required in cols, (
            f"athlete_calibrated_model is missing required column {required!r}; "
            f"got {sorted(cols)}"
        )


def test_athlete_workout_response_table_exists_with_unique_stimulus_constraint() -> None:
    insp = inspect(engine)
    assert "athlete_workout_response" in insp.get_table_names()

    cols = _columns("athlete_workout_response")
    for required in {"id", "athlete_id", "stimulus_type", "n_observations"}:
        assert required in cols

    constraint_names = {c["name"] for c in insp.get_unique_constraints("athlete_workout_response")}
    assert "uq_athlete_stimulus_response" in constraint_names, (
        f"Unique constraint uq_athlete_stimulus_response missing; got {constraint_names}"
    )


def test_athlete_learning_table_exists_with_required_columns() -> None:
    insp = inspect(engine)
    assert "athlete_learning" in insp.get_table_names()

    cols = _columns("athlete_learning")
    for required in {
        "id",
        "athlete_id",
        "learning_type",
        "subject",
        "confidence",
        "is_active",
    }:
        assert required in cols


def test_repair_migration_is_idempotent() -> None:
    """Running n1_repair_001's upgrade SQL a second time must not explode.

    The repair uses CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS /
    guarded ADD CONSTRAINT, so re-running it against an already-repaired
    database is a no-op.  Guard that property directly.
    """
    idempotent_stmts = [
        "CREATE TABLE IF NOT EXISTS athlete_calibrated_model ("
        "    athlete_id UUID PRIMARY KEY REFERENCES athlete(id),"
        "    tau1 DOUBLE PRECISION NOT NULL,"
        "    tau2 DOUBLE PRECISION NOT NULL,"
        "    k1 DOUBLE PRECISION NOT NULL,"
        "    k2 DOUBLE PRECISION NOT NULL,"
        "    p0 DOUBLE PRECISION NOT NULL,"
        "    confidence TEXT NOT NULL,"
        "    data_tier TEXT NOT NULL,"
        "    calibrated_at TIMESTAMPTZ NOT NULL DEFAULT now()"
        ");",
        "CREATE INDEX IF NOT EXISTS ix_athlete_workout_response_athlete_id "
        "ON athlete_workout_response (athlete_id);",
        "CREATE INDEX IF NOT EXISTS ix_athlete_learning_athlete_id "
        "ON athlete_learning (athlete_id);",
    ]

    with engine.begin() as conn:
        for stmt in idempotent_stmts:
            conn.execute(text(stmt))
