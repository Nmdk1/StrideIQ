"""Contract tests for the Strength v1 feature flag seed migration.

These tests are intentionally cheap (static text checks) so the contract
holds without requiring a database. They lock in three rollout-discipline
invariants for the ``strength.v1`` flag:

1. The seed migration exists, chains off ``fit_run_001``, and is the
   current head (``strength_v1_001``).
2. The seeded flag is disabled (``enabled = false``) with zero rollout
   and an empty allow-list, so merging Strength v1 work to ``main`` does
   not expose anything to athletes until the founder explicitly flips it.
3. The Alembic head guard in CI knows about the new head.

If anyone (a future agent, or a future me) tries to "soft-launch" by
flipping ``enabled`` or seeding an athlete into ``allowed_athlete_ids``
inside this migration, these tests fail loudly. Rollout has to happen
through ``FeatureFlagService.set_flag`` against a real database, which
is auditable.
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
    / "strength_v1_001_seed_feature_flag.py"
)
HEADS_GUARD_PATH = (
    REPO_ROOT / ".github" / "scripts" / "ci_alembic_heads_check.py"
)


def _read(path: Path) -> str:
    assert path.exists(), f"missing file: {path}"
    return path.read_text(encoding="utf-8")


def test_strength_v1_seed_migration_exists_and_chains_off_fit_run_001():
    text = _read(MIGRATION_PATH)
    assert re.search(r'^revision\s*=\s*"strength_v1_001"', text, re.M), (
        "strength_v1_001 must declare its own revision id"
    )
    assert re.search(r'^down_revision\s*=\s*"fit_run_001"', text, re.M), (
        "strength_v1_001 must chain off fit_run_001 (current head)"
    )


def test_strength_v1_seed_flag_is_disabled_with_zero_rollout():
    text = _read(MIGRATION_PATH)

    assert "'strength.v1'" in text, "flag key must be exactly 'strength.v1'"

    # Flag must be inserted disabled. We check the literal SQL the migration
    # emits rather than runtime state so the contract is independent of DB.
    insert_match = re.search(
        r"INSERT INTO feature_flag.*?VALUES\s*\((.*?)\)\s*ON CONFLICT",
        text,
        re.S,
    )
    assert insert_match, "could not locate the seed INSERT statement"
    values = insert_match.group(1)

    # Order in the migration: id, key, name, description, enabled,
    # requires_subscription, requires_tier, rollout_percentage,
    # allowed_athlete_ids
    parts = [p.strip() for p in re.split(r",(?![^()]*\))", values)]
    assert len(parts) == 9, (
        f"expected 9 VALUES columns in seed insert, got {len(parts)}: {parts}"
    )

    enabled = parts[4].lower()
    rollout = parts[7]
    allowed_ids = parts[8].lower()

    assert enabled == "false", (
        f"strength.v1 must seed enabled=false (got {enabled!r}). "
        "Rollout happens via FeatureFlagService.set_flag, not in the migration."
    )
    assert rollout == "0", (
        f"strength.v1 must seed rollout_percentage=0 (got {rollout!r})."
    )
    assert "'[]'::jsonb" in allowed_ids, (
        f"strength.v1 must seed allowed_athlete_ids as empty JSON array "
        f"(got {allowed_ids!r}). No allow-listed athletes at seed time."
    )


def test_alembic_head_guard_declares_a_head():
    """The Alembic head guard must declare at least one expected head."""
    text = _read(HEADS_GUARD_PATH)
    assert re.search(
        r'EXPECTED_HEADS\s*=\s*\{[^}]+\}', text
    ), (
        "ci_alembic_heads_check.py must declare at least one EXPECTED_HEADS entry."
    )
