"""
Reset an athlete password hash (ops script).

SECURITY:
- No hardcoded emails or passwords.
- No password via CLI args (shell history). Read password from an env var.
- DRY_RUN by default; use --commit to persist.

Usage (inside api container):
  export STRIDEIQ_NEW_PASSWORD='...'
  python scripts/reset_password.py --email someone@example.com --commit
"""

from __future__ import annotations

import os
import sys

import bcrypt
from sqlalchemy import create_engine, text


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

    database_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/running_app")
    engine = create_engine(database_url)

    hashed = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt())
    hash_str = hashed.decode("utf-8")

    if not args.commit:
        print(f"DRY_RUN: would update password_hash for athlete email={args.email}")
        return 0

    with engine.connect() as conn:
        conn.execute(
            text("UPDATE athlete SET password_hash = :hash WHERE email = :email"),
            {"hash": hash_str, "email": args.email},
        )
        conn.commit()

    print(f"OK: updated password_hash for athlete email={args.email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
