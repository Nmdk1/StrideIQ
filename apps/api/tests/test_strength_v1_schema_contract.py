"""Phase A schema contract for the Strength v1 sandbox.

These tests do not require a live database. They lock in:

1. ``strength_v1_002`` exists, chains off ``strength_v1_001``, is
   idempotent (uses ``IF NOT EXISTS`` on every additive change), and
   is reversible (has a non-empty ``downgrade()``).
2. The new columns on ``strength_exercise_set`` and ``athlete`` exist
   in the migration text exactly as the scope requires.
3. The three new tables (``strength_routine``, ``strength_goal``,
   ``body_area_symptom_log``) are created in the migration.
4. The SQLAlchemy models match the migration: every new column declared
   in the migration is also declared on the corresponding ORM model.
5. The supersede pattern on ``strength_exercise_set`` is wired
   end-to-end: column + self-FK + partial index for active rows.

Anything that drifts here breaks the read path for non-destructive edits,
so we want a loud failure rather than a silent inconsistency.
"""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = (
    REPO_ROOT
    / "apps"
    / "api"
    / "alembic"
    / "versions"
    / "strength_v1_002_schema.py"
)
ACTIVITY_MODEL_PATH = REPO_ROOT / "apps" / "api" / "models" / "activity.py"
ATHLETE_MODEL_PATH = REPO_ROOT / "apps" / "api" / "models" / "athlete.py"
STRENGTH_V1_MODEL_PATH = (
    REPO_ROOT / "apps" / "api" / "models" / "strength_v1.py"
)
MODELS_INIT_PATH = REPO_ROOT / "apps" / "api" / "models" / "__init__.py"


def _read(path: Path) -> str:
    assert path.exists(), f"missing file: {path}"
    return path.read_text(encoding="utf-8")


# --- Migration shape ---------------------------------------------------


def test_strength_v1_002_chains_off_001():
    text = _read(MIGRATION_PATH)
    assert re.search(r'^revision\s*=\s*"strength_v1_002"', text, re.M)
    assert re.search(r'^down_revision\s*=\s*"strength_v1_001"', text, re.M)


def test_strength_v1_002_upgrade_is_idempotent_and_additive_only():
    text = _read(MIGRATION_PATH)
    upgrade = re.search(r"def upgrade\(\) -> None:(.*?)\ndef downgrade", text, re.S)
    assert upgrade is not None
    body = upgrade.group(1)

    # Every ADD COLUMN must be IF NOT EXISTS, every CREATE TABLE / INDEX too.
    add_columns = re.findall(r"ADD COLUMN(?!\s+IF NOT EXISTS)", body)
    assert not add_columns, (
        "Phase A migration must use ADD COLUMN IF NOT EXISTS for every new "
        f"column. Bare ADD COLUMN found at: {add_columns}"
    )
    create_tables = re.findall(r"CREATE TABLE(?!\s+IF NOT EXISTS)", body)
    assert not create_tables, (
        "Phase A migration must use CREATE TABLE IF NOT EXISTS for every "
        f"new table. Bare CREATE TABLE found at: {create_tables}"
    )
    create_indexes = re.findall(r"CREATE INDEX(?!\s+IF NOT EXISTS)", body)
    assert not create_indexes, (
        "Phase A migration must use CREATE INDEX IF NOT EXISTS. "
        f"Bare CREATE INDEX found at: {create_indexes}"
    )

    # No destructive DDL in upgrade.
    for forbidden in ("DROP COLUMN", "DROP TABLE"):
        assert forbidden not in body.upper(), (
            f"Phase A upgrade may not contain {forbidden!r}; the migration "
            "is additive only."
        )


def test_strength_v1_002_downgrade_is_present_and_reversible():
    text = _read(MIGRATION_PATH)
    downgrade = re.search(r"def downgrade\(\) -> None:(.*)$", text, re.S)
    assert downgrade is not None
    body = downgrade.group(1)
    assert "pass" not in body.lower(), (
        "Phase A migration needs a real downgrade, not 'pass'. "
        "Rollback story is part of the rollout contract."
    )
    for table in ("strength_routine", "strength_goal", "body_area_symptom_log"):
        assert f"DROP TABLE IF EXISTS {table}" in body, (
            f"downgrade() must drop new table {table!r}"
        )


# --- strength_exercise_set columns ------------------------------------


_NEW_SES_COLUMNS = [
    ("rpe", "DOUBLE PRECISION", "Float"),
    ("implement_type", "TEXT", "Text"),
    ("set_modifier", "TEXT", "Text"),
    ("tempo", "TEXT", "Text"),
    ("notes", "TEXT", "Text"),
    ("source", "TEXT NOT NULL DEFAULT 'garmin'", "Text"),
    ("manually_augmented", "BOOLEAN NOT NULL DEFAULT false", "Boolean"),
    ("superseded_by_id", "UUID", "UUID"),
    ("superseded_at", "TIMESTAMPTZ", "DateTime"),
]


def test_strength_exercise_set_new_columns_in_migration():
    text = _read(MIGRATION_PATH)
    for col, ddl, _ in _NEW_SES_COLUMNS:
        assert re.search(
            rf"ADD COLUMN IF NOT EXISTS {col}\s+{re.escape(ddl)}", text
        ), f"strength_exercise_set.{col} ({ddl}) missing from upgrade"


def test_strength_exercise_set_new_columns_in_orm_model():
    text = _read(ACTIVITY_MODEL_PATH)
    for col, _, sa_type in _NEW_SES_COLUMNS:
        assert re.search(rf"\b{col}\s*=\s*Column\(", text), (
            f"StrengthExerciseSet ORM model missing column {col!r}"
        )
    assert "ForeignKey(\"strength_exercise_set.id\"" in text, (
        "superseded_by_id must FK back to strength_exercise_set.id "
        "to support the non-destructive edit-history pattern"
    )


def test_strength_exercise_set_active_partial_index_exists():
    text = _read(MIGRATION_PATH)
    assert (
        "ix_strength_set_active" in text
        and "WHERE superseded_at IS NULL" in text
    ), (
        "Active-row partial index ix_strength_set_active is required so "
        "the default read path (superseded_at IS NULL) is fast at scale."
    )


# --- athlete lifting baseline columns ---------------------------------


_NEW_ATHLETE_COLUMNS = [
    ("lifts_currently", "TEXT", "Text"),
    ("lift_days_per_week", "DOUBLE PRECISION", "Float"),
    ("lift_experience_bucket", "TEXT", "Text"),
]


def test_athlete_lifting_baseline_columns_in_migration():
    text = _read(MIGRATION_PATH)
    for col, ddl, _ in _NEW_ATHLETE_COLUMNS:
        assert re.search(
            rf"ADD COLUMN IF NOT EXISTS {col}\s+{re.escape(ddl)}", text
        ), f"athlete.{col} missing from upgrade"


def test_athlete_lifting_baseline_columns_in_orm_model():
    text = _read(ATHLETE_MODEL_PATH)
    for col, _, _sa_type in _NEW_ATHLETE_COLUMNS:
        assert re.search(rf"\b{col}\s*=\s*Column\(", text), (
            f"Athlete ORM model missing column {col!r}"
        )


# --- new tables --------------------------------------------------------


def test_new_tables_in_migration():
    text = _read(MIGRATION_PATH)
    for table in ("strength_routine", "strength_goal", "body_area_symptom_log"):
        assert (
            f"CREATE TABLE IF NOT EXISTS {table}" in text
        ), f"migration must create table {table!r}"


def test_new_tables_have_orm_models_and_are_exported():
    text = _read(STRENGTH_V1_MODEL_PATH)
    for cls in ("StrengthRoutine", "StrengthGoal", "BodyAreaSymptomLog"):
        assert re.search(rf"^class {cls}\(Base\):", text, re.M), (
            f"models/strength_v1.py must define {cls}"
        )

    init_text = _read(MODELS_INIT_PATH)
    for cls in ("StrengthRoutine", "StrengthGoal", "BodyAreaSymptomLog"):
        assert cls in init_text, f"models/__init__.py must re-export {cls}"


# --- supersede semantics smoke ----------------------------------------


def test_strength_exercise_set_supersede_self_fk_is_set_null():
    """ON DELETE SET NULL preserves the predecessor row even if a successor
    is hard-deleted (we don't expect that to happen, but we want the audit
    chain to survive any operational accident)."""
    text = _read(MIGRATION_PATH)
    assert (
        "REFERENCES strength_exercise_set(id)" in text
        and "ON DELETE SET NULL" in text
    ), "self-FK on superseded_by_id must use ON DELETE SET NULL"
