from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete AdminAuditEvent rows older than N days (with dry-run).")
    parser.add_argument("--days", type=int, default=90, help="Delete events older than this many days (default: 90)")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be deleted, without deleting")
    parser.add_argument("--sample", type=int, default=5, help="Show up to N sample rows (default: 5)")
    args = parser.parse_args()

    if args.days < 1:
        raise SystemExit("--days must be >= 1")

    cutoff = datetime.now(timezone.utc) - timedelta(days=int(args.days))

    # NOTE: This script is intended to be run inside the API container/runtime where
    # the app modules (`core`, `models`) are available on PYTHONPATH.
    from core.database import get_db_sync
    from models import AdminAuditEvent

    db = get_db_sync()
    try:
        q = db.query(AdminAuditEvent).filter(AdminAuditEvent.created_at < cutoff)
        count = int(q.count() or 0)

        print(f"AdminAuditEvent retention cleanup")
        print(f"- cutoff: {cutoff.isoformat()}")
        print(f"- days: {int(args.days)}")
        print(f"- matches: {count}")

        sample_n = max(0, int(args.sample or 0))
        if sample_n:
            rows = q.order_by(AdminAuditEvent.created_at.asc()).limit(sample_n).all()
            for ev in rows:
                created = ev.created_at.isoformat() if getattr(ev, "created_at", None) else None
                print(f"  - {created} action={ev.action} actor={ev.actor_athlete_id} target={ev.target_athlete_id}")

        if args.dry_run:
            print("Dry run: no deletions performed.")
            return 0

        deleted = int(q.delete(synchronize_session=False) or 0)
        db.commit()
        print(f"Deleted {deleted} admin audit event(s).")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

