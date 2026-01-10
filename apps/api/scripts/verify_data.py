import sys
import os
from sqlalchemy import func

# Force Python to look in the parent directory (/app) for database.py
# When running from /app/scripts/verify_data.py, parent is /app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import ActivitySplit

def run_check():
    print("--- VERIFYING DATA ---")
    db = SessionLocal()
    try:
        # Count rows
        total_splits = db.query(func.count(ActivitySplit.id)).scalar()
        
        print(f"Total Splits in DB: {total_splits}")

        if total_splits > 0:
            print("SUCCESS: Database is healthy.")
        else:
            print("WARNING: Database is empty.")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    run_check()


