#!/usr/bin/env python3
"""Database bootstrap: run Alembic migrations (production).

Production rule (MUST HOLD):
- Always run `alembic upgrade head` on startup.
- If migrations fail, fail fast and DO NOT attempt any "create schema from models" fallback.

Why:
- Model-based create_all + stamping can leave the DB in a partially-created state
  that then breaks future migrations (duplicate indexes, missing tables/columns, etc.).
- It hides real migration bugs instead of surfacing them.
"""

import os
import sys
import time
from dotenv import load_dotenv

load_dotenv()

def check_db_ready():
    """Check if database is ready"""
    import psycopg2
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'postgres'),
            port=os.getenv('POSTGRES_PORT', '5432'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', 'postgres'),
            database=os.getenv('POSTGRES_DB', 'running_app')
        )
        conn.close()
        return True
    except Exception:
        return False

def _get_alembic_config():
    """Load Alembic config for programmatic migrations."""
    from alembic.config import Config

    here = os.path.dirname(os.path.abspath(__file__))
    cfg = Config(os.path.join(here, "alembic.ini"))
    return cfg


def alembic_upgrade_head() -> None:
    """Apply all pending migrations (single head)."""
    from alembic import command

    command.upgrade(_get_alembic_config(), "head")


def alembic_upgrade_heads() -> None:
    """Apply all pending migrations across all branches (multiple heads).

    The project uses independent migration branches — Phase 2A, 2B, and 3A
    each have down_revision=None and use IF NOT EXISTS / column-check patterns
    for idempotent safety. This upgrades all branches to their respective heads.
    """
    from alembic import command

    command.upgrade(_get_alembic_config(), "heads")


def _cleanup_stale_version_entries() -> None:
    """Remove intermediate alembic_version entries from before phase migrations
    were chained.

    Previously readiness_score_001, self_regulation_001, and narration_001 each
    had down_revision=None (standalone roots).  They now form a single chain:
        readiness_score_001 -> self_regulation_001 -> narration_001

    A database that was migrated under the old layout has all three in
    alembic_version.  With the new chain only the head (narration_001) should
    remain; the intermediates would cause an "overlaps" error on upgrade.

    Safe on fresh databases — the DELETE is a no-op when the rows don't exist.
    """
    import psycopg2
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'postgres'),
            port=os.getenv('POSTGRES_PORT', '5432'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', 'postgres'),
            database=os.getenv('POSTGRES_DB', 'running_app')
        )
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM alembic_version "
            "WHERE version_num IN ('readiness_score_001', 'self_regulation_001')"
        )
        deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        if deleted:
            print(f"Cleaned up {deleted} stale alembic_version entries.")
    except Exception:
        # Table might not exist yet (fresh DB) — that's fine.
        pass


def alembic_stamp_head() -> None:
    """Stamp alembic_version as head (no schema changes)."""
    from alembic import command

    command.stamp(_get_alembic_config(), "head")

def main():
    print("Waiting for database to be ready...")
    max_retries = 30
    retry_count = 0
    
    while retry_count < max_retries:
        if check_db_ready():
            print("Database is ready!")
            break
        retry_count += 1
        print(f"Database is unavailable - sleeping (attempt {retry_count}/{max_retries})")
        time.sleep(1)
    else:
        print("ERROR: Database is not ready after maximum retries")
        sys.exit(1)
    
    # Clean up stale alembic_version entries from before phase migrations
    # were chained.  Previously each phase migration was standalone
    # (down_revision=None), leaving separate version-table rows.  They now
    # form a chain: readiness_score_001 -> self_regulation_001 -> narration_001.
    # Keeping the intermediate rows causes an "overlaps" error on upgrade.
    _cleanup_stale_version_entries()

    # Production rule: always apply migrations.
    # Use "heads" (plural) because the project has two branches:
    # - main chain (a1b2c3d4e5f7)
    # - phase chain (readiness_score_001 -> self_regulation_001 -> narration_001)
    try:
        alembic_upgrade_heads()
        print("Migrations completed successfully!")
        return
    except Exception as e:
        print(f"ERROR: Alembic upgrade failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
