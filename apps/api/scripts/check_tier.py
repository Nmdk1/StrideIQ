"""Check (and optionally update) an athlete subscription tier (ops script)."""

from __future__ import annotations

import os

from sqlalchemy import create_engine, text


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default=os.getenv("STRIDEIQ_EMAIL"), help="athlete email (default: STRIDEIQ_EMAIL)")
    parser.add_argument("--target-tier", default="elite", help="tier to set if updating (default: elite)")
    parser.add_argument("--commit", action="store_true", help="Persist tier update (default: dry-run)")
    args = parser.parse_args()

    if not args.email:
        print("ERROR: missing STRIDEIQ_EMAIL (or pass --email)")
        return 2

    db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/running_app")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT id, email, subscription_tier FROM athlete WHERE email = :email"),
            {"email": args.email},
        )
        row = result.fetchone()
        if not row:
            print("User not found")
            return 1

        athlete_id, email, tier = row[0], row[1], row[2]
        print(f"ID: {athlete_id}")
        print(f"Email: {email}")
        print(f"Current Tier: {tier}")

        if tier == args.target_tier:
            print(f">>> Already {args.target_tier.upper()} tier")
            return 0

        if not args.commit:
            print(f"DRY_RUN: would update tier to {args.target_tier!r}")
            return 0

        conn.execute(
            text("UPDATE athlete SET subscription_tier = :tier WHERE email = :email"),
            {"tier": args.target_tier, "email": args.email},
        )
        conn.commit()
        print(f">>> Updated to {args.target_tier.upper()} tier")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
