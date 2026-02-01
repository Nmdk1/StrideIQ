#!/usr/bin/env python3
"""
Delete all test users with @example.com emails and their related data.
Dynamically discovers all FK constraints to handle them properly.
Run: python scripts/cleanup_test_users.py
"""
import sys
sys.path.insert(0, "/app")

from sqlalchemy import text
from core.database import engine

def cleanup_test_users():
    """Delete test users using raw connection with proper FK handling."""
    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()
        try:
            # Get test user IDs
            result = conn.execute(text("SELECT id FROM athlete WHERE email LIKE '%@example.com'"))
            user_ids = [str(row[0]) for row in result.fetchall()]
            
            if not user_ids:
                print("No test users found.")
                return
            
            print(f"Found {len(user_ids)} test users to delete")
            ids_str = ",".join(f"'{uid}'" for uid in user_ids)
            
            # Get all FK constraints pointing to athlete table
            fk_query = text("""
                SELECT 
                    tc.table_name, 
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints AS tc 
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY' 
                    AND ccu.table_name = 'athlete'
                ORDER BY tc.table_name
            """)
            fk_result = conn.execute(fk_query)
            fk_constraints = fk_result.fetchall()
            
            print(f"Found {len(fk_constraints)} FK constraints to athlete table")
            
            # Handle each FK - either UPDATE to NULL or DELETE
            for table_name, column_name, _, _ in fk_constraints:
                # Try UPDATE SET NULL first (for nullable FKs)
                try:
                    update_sql = f"UPDATE {table_name} SET {column_name} = NULL WHERE {column_name} IN ({ids_str})"
                    result = conn.execute(text(update_sql))
                    if result.rowcount > 0:
                        print(f"  UPDATE {table_name}.{column_name} = NULL -> {result.rowcount} rows")
                except Exception:
                    # If UPDATE fails (NOT NULL constraint), DELETE instead
                    try:
                        # First handle any child FKs of this table
                        delete_sql = f"DELETE FROM {table_name} WHERE {column_name} IN ({ids_str})"
                        result = conn.execute(text(delete_sql))
                        if result.rowcount > 0:
                            print(f"  DELETE FROM {table_name} -> {result.rowcount} rows")
                    except Exception as e:
                        print(f"  SKIP {table_name}: {e}")
            
            # Handle training_plan child tables explicitly
            plan_ids_query = f"SELECT id FROM training_plan WHERE athlete_id IN ({ids_str})"
            plan_result = conn.execute(text(plan_ids_query))
            plan_ids = [str(row[0]) for row in plan_result.fetchall()]
            
            if plan_ids:
                plan_ids_str = ",".join(f"'{pid}'" for pid in plan_ids)
                for child_table in ['plan_modification_log', 'planned_workout', 'coach_action_proposals']:
                    try:
                        result = conn.execute(text(f"DELETE FROM {child_table} WHERE plan_id IN ({plan_ids_str})"))
                        if result.rowcount > 0:
                            print(f"  DELETE FROM {child_table} (plan children) -> {result.rowcount} rows")
                    except Exception:
                        pass
                
                # Delete plans
                result = conn.execute(text(f"DELETE FROM training_plan WHERE id IN ({plan_ids_str})"))
                print(f"  DELETE FROM training_plan -> {result.rowcount} rows")
            
            # Handle activity child tables
            activity_ids_query = f"SELECT id FROM activity WHERE athlete_id IN ({ids_str})"
            activity_result = conn.execute(text(activity_ids_query))
            activity_ids = [str(row[0]) for row in activity_result.fetchall()]
            
            if activity_ids:
                activity_ids_str = ",".join(f"'{aid}'" for aid in activity_ids)
                result = conn.execute(text(f"DELETE FROM activity_split WHERE activity_id IN ({activity_ids_str})"))
                if result.rowcount > 0:
                    print(f"  DELETE FROM activity_split -> {result.rowcount} rows")
                result = conn.execute(text(f"DELETE FROM activity WHERE id IN ({activity_ids_str})"))
                print(f"  DELETE FROM activity -> {result.rowcount} rows")
            
            # Finally delete athletes
            result = conn.execute(text(f"DELETE FROM athlete WHERE id IN ({ids_str})"))
            print(f"  DELETE FROM athlete -> {result.rowcount} rows")
            
            trans.commit()
            print(f"\nSuccessfully deleted {len(user_ids)} test users.")
            
        except Exception as e:
            trans.rollback()
            print(f"ERROR: {e}")
            print("Transaction rolled back. No changes made.")
            raise

if __name__ == "__main__":
    cleanup_test_users()
