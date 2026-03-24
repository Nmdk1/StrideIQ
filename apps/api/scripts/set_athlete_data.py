#!/usr/bin/env python3
"""
Set athlete birthdate and sex for age-grading calculations.
"""
import sys
import os
import argparse
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SessionLocal
from models import Athlete
from datetime import date

def set_athlete_data():
    """Set optional athlete demographics without overwriting explicit values."""
    parser = argparse.ArgumentParser(
        description="Set optional athlete demographics for local testing.",
    )
    parser.add_argument("--athlete-id", help="Specific athlete UUID to update")
    parser.add_argument("--email", help="Specific athlete email to update")
    parser.add_argument("--birthdate", help="Birthdate YYYY-MM-DD (only applied if missing unless --force-birthdate)")
    parser.add_argument("--sex", choices=["M", "F"], help="Sex code to set")
    parser.add_argument(
        "--force-birthdate",
        action="store_true",
        help="Allow overwriting existing birthdate (manual opt-in only).",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("SETTING ATHLETE DATA")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        from models import Activity
        athlete = None
        if args.athlete_id:
            athlete = db.query(Athlete).filter(Athlete.id == args.athlete_id).first()
        elif args.email:
            athlete = db.query(Athlete).filter(Athlete.email == args.email).first()
        else:
            athlete = db.query(Athlete).join(Activity).first()
        if not athlete:
            athlete = db.query(Athlete).first()

        if not athlete:
            print("❌ No athlete found")
            return False

        print(f"\n✓ Found athlete: {athlete.id}")
        print(f"  Email: {athlete.email}")
        print(f"  Current birthdate: {athlete.birthdate}")
        print(f"  Current sex: {athlete.sex}")

        if args.birthdate:
            requested_birthdate = date.fromisoformat(args.birthdate)
            if athlete.birthdate and not args.force_birthdate:
                print("  Skipping birthdate update (already set). Use --force-birthdate to overwrite.")
            else:
                athlete.birthdate = requested_birthdate
        if args.sex:
            athlete.sex = args.sex

        db.commit()

        print("\n✅ Updated athlete:")
        print(f"  Birthdate: {athlete.birthdate}")
        print(f"  Sex: {athlete.sex}")

        return True

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = set_athlete_data()
    sys.exit(0 if success else 1)

