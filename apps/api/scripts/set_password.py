"""
Set an athlete password hash (ops script).

This script exists for legacy environments that use direct Postgres connections.
Prefer `scripts/reset_password.py` (SQLAlchemy) unless you explicitly need psycopg2.

SECURITY:
- No hardcoded emails or passwords.
- No password via CLI args (shell history). Read password from an env var.
- DRY_RUN by default; use --commit to persist.
"""

from __future__ import annotations

import os

import bcrypt
import psycopg2


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True, help="athlete email")
    parser.add_argument(
        "--password-env",
        default="STRIDEIQ_NEW_PASSWORD",
        help="env var name containing the new password (default: STRIDEIQ_NEW_PASSWORD)",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Persist the password change. Default is dry-run.",
    )
    args = parser.parse_args()

    new_password = os.getenv(args.password_env)
    if not new_password:
        print(f"ERROR: missing env var {args.password_env} (new password)")
        return 2

    # Generate hash (never print it)
    salt = bcrypt.gensalt()
    hash_bytes = bcrypt.hashpw(new_password.encode("utf-8"), salt)
    hash_str = hash_bytes.decode("utf-8")

    if not args.commit:
        print(f"DRY_RUN: would update password_hash for athlete email={args.email}")
        return 0

    # Connect and update (defaults match local docker compose)
    conn = psycopg2.connect(
        host=os.getenv("PGHOST", "running_app_postgres"),
        database=os.getenv("PGDATABASE", "running_app"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "postgres"),
    )
    try:
        cur = conn.cursor()
        cur.execute("UPDATE athlete SET password_hash = %s WHERE email = %s", (hash_str, args.email))
        conn.commit()
        print(f"OK: updated password_hash for athlete email={args.email}")
        cur.close()
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
