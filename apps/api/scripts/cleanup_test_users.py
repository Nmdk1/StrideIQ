#!/usr/bin/env python3
"""
Delete all test users with @example.com emails and their related data.
Run: python scripts/cleanup_test_users.py
"""
import sys
sys.path.insert(0, "/app")

from sqlalchemy import text
from core.database import SessionLocal

def cleanup_test_users():
    db = SessionLocal()
    try:
        # Get all test user IDs first
        result = db.execute(text("SELECT id, email FROM athlete WHERE email LIKE '%@example.com'"))
        users = result.fetchall()
        print(f"Found {len(users)} test users to delete")
        
        if not users:
            print("No test users found.")
            return
        
        user_ids = [str(u[0]) for u in users]
        ids_str = ",".join(f"'{uid}'" for uid in user_ids)
        
        # Delete in correct order (children first)
        tables_to_clean = [
            f"DELETE FROM athlete_training_pace_profile WHERE athlete_id IN ({ids_str})",
            f"DELETE FROM athlete_race_result_anchor WHERE athlete_id IN ({ids_str})",
            f"DELETE FROM coach_chat WHERE athlete_id IN ({ids_str})",
            f"DELETE FROM coach_action_proposals WHERE athlete_id IN ({ids_str})",
            f"DELETE FROM coach_intent_snapshot WHERE athlete_id IN ({ids_str})",
            f"DELETE FROM coach_usage WHERE athlete_id IN ({ids_str})",
            f"DELETE FROM activity_feedback WHERE athlete_id IN ({ids_str})",
            f"DELETE FROM insight_feedback WHERE athlete_id IN ({ids_str})",
            f"DELETE FROM activity_split WHERE activity_id IN (SELECT id FROM activity WHERE athlete_id IN ({ids_str}))",
            f"DELETE FROM activity WHERE athlete_id IN ({ids_str})",
            f"DELETE FROM personal_best WHERE athlete_id IN ({ids_str})",
            f"DELETE FROM best_effort WHERE athlete_id IN ({ids_str})",
            f"DELETE FROM daily_checkin WHERE athlete_id IN ({ids_str})",
            f"DELETE FROM body_composition WHERE athlete_id IN ({ids_str})",
            f"DELETE FROM nutrition_entry WHERE athlete_id IN ({ids_str})",
            f"DELETE FROM work_pattern WHERE athlete_id IN ({ids_str})",
            f"DELETE FROM intake_questionnaire WHERE athlete_id IN ({ids_str})",
            f"DELETE FROM subscriptions WHERE athlete_id IN ({ids_str})",
            f"DELETE FROM athlete_ingestion_state WHERE athlete_id IN ({ids_str})",
            f"DELETE FROM athlete_data_import_job WHERE athlete_id IN ({ids_str})",
            f"DELETE FROM training_availability WHERE athlete_id IN ({ids_str})",
            f"DELETE FROM calendar_note WHERE athlete_id IN ({ids_str})",
            f"DELETE FROM calendar_insight WHERE athlete_id IN ({ids_str})",
            f"DELETE FROM plan_modification_log WHERE plan_id IN (SELECT id FROM training_plan WHERE athlete_id IN ({ids_str}))",
            f"DELETE FROM planned_workout WHERE plan_id IN (SELECT id FROM training_plan WHERE athlete_id IN ({ids_str}))",
            f"DELETE FROM training_plan WHERE athlete_id IN ({ids_str})",
            f"DELETE FROM athlete WHERE id IN ({ids_str})",
        ]
        
        for sql in tables_to_clean:
            try:
                result = db.execute(text(sql))
                print(f"  {sql[:60]}... -> {result.rowcount} rows")
            except Exception as e:
                if "does not exist" in str(e):
                    print(f"  (skipped - table doesn't exist)")
                else:
                    print(f"  ERROR: {e}")
        
        db.commit()
        print(f"\nDeleted {len(users)} test users successfully.")
        
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_test_users()
