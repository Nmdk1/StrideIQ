"""CI gate: assert the Alembic migration graph has exactly the expected heads.

Prevents accidental introduction of new standalone migration roots
(down_revision = None) that cause non-deterministic ordering, FK failures,
and "overlaps" errors in CI and production.

Expected state (after Phase 2 merge):
  Single head: 0d82917b8305  (merges main chain + activity_stream branch)

If a new migration is added, it MUST chain off the existing head — not introduce
a new root.  If this check fails, the fix is to set down_revision to the
appropriate parent.

Usage:
  python .github/scripts/ci_alembic_heads_check.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Alembic needs the api directory on sys.path and the alembic.ini location.
api_root = Path(__file__).resolve().parents[2] / "apps" / "api"
sys.path.insert(0, str(api_root))

from alembic.config import Config
from alembic.script import ScriptDirectory

EXPECTED_HEADS = {"consent_001"}
MAX_ROOTS = 2  # main chain root + phase chain root (readiness_score_001)


def main() -> int:
    cfg = Config(str(api_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(api_root / "alembic"))

    script = ScriptDirectory.from_config(cfg)
    heads = set(script.get_heads())

    # --- Check 1: head count and identity ---
    if heads != EXPECTED_HEADS:
        print("MIGRATION HEAD CHECK FAILED")
        print(f"  Expected heads: {sorted(EXPECTED_HEADS)}")
        print(f"  Actual heads:   {sorted(heads)}")
        print()
        if heads - EXPECTED_HEADS:
            print("  New/unexpected heads:")
            for h in sorted(heads - EXPECTED_HEADS):
                print(f"    - {h}")
            print()
            print("  Fix: set down_revision to the appropriate parent instead of None.")
        if EXPECTED_HEADS - heads:
            print("  Missing heads:")
            for h in sorted(EXPECTED_HEADS - heads):
                print(f"    - {h}")
            print()
            print("  Fix: a migration that was a head was re-parented or removed.")
            print("  Update EXPECTED_HEADS in this script if intentional.")
        return 1

    # --- Check 2: no unexpected roots (down_revision = None) ---
    revisions = list(script.walk_revisions())
    roots = [r.revision for r in revisions if r.down_revision is None]

    if len(roots) > MAX_ROOTS:
        print("MIGRATION ROOT CHECK FAILED")
        print(f"  Expected at most {MAX_ROOTS} roots, found {len(roots)}:")
        for r in sorted(roots):
            print(f"    - {r}")
        print()
        print("  Fix: new migrations must chain off an existing head, not use down_revision = None.")
        return 1

    print(f"Migration integrity check: OK ({len(heads)} heads, {len(roots)} roots, {len(revisions)} total)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
