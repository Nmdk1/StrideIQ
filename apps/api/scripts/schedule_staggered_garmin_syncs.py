#!/usr/bin/env python3
"""
Schedule staggered Garmin syncs for all connected athletes.

This script distributes sync tasks across 24 hours to mimic natural user behavior.
Run this via cron or scheduled task (e.g., daily at midnight).
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
import random

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db_sync
from models import Athlete
from tasks.garmin_tasks import sync_garmin_activities_task, sync_garmin_recovery_metrics_task
from celery import current_app

def schedule_staggered_syncs():
    """
    Schedule Garmin syncs for all connected athletes, staggered over 24 hours.
    
    Distributes syncs across the day:
    - 10-20 users every 5-10 minutes
    - Random delay within each batch
    """
    db = get_db_sync()
    
    try:
        # Get all athletes with Garmin connected and sync enabled
        athletes = db.query(Athlete).filter(
            Athlete.garmin_connected == True,
            Athlete.garmin_sync_enabled == True
        ).all()
        
        print(f"Found {len(athletes)} athletes with Garmin connected")
        
        if not athletes:
            print("No athletes to sync")
            return
        
        # Calculate stagger parameters
        total_minutes = 24 * 60  # 24 hours in minutes
        batch_size = min(15, len(athletes) // 10)  # 10-20 users per batch
        batch_interval = 7  # 5-10 minutes between batches
        
        scheduled = 0
        
        for i, athlete in enumerate(athletes):
            # Calculate delay for this athlete
            batch_num = i // batch_size
            base_delay = batch_num * batch_interval * 60  # Convert to seconds
            random_delay = random.randint(0, 300)  # 0-5 minutes random
            total_delay = base_delay + random_delay
            
            # Schedule activity sync
            sync_garmin_activities_task.apply_async(
                args=[str(athlete.id)],
                countdown=total_delay
            )
            
            # Schedule recovery metrics sync (slightly later)
            sync_garmin_recovery_metrics_task.apply_async(
                args=[str(athlete.id), 30],
                countdown=total_delay + 60  # 1 minute after activity sync
            )
            
            scheduled += 1
            
            if (i + 1) % batch_size == 0:
                print(f"Scheduled batch {batch_num + 1}: {batch_size} athletes")
        
        print(f"\n✅ Scheduled {scheduled} athletes for staggered sync")
        print(f"   Syncs distributed over ~{len(athletes) * batch_interval // 60} hours")
        
    except Exception as e:
        print(f"❌ Error scheduling syncs: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    schedule_staggered_syncs()

