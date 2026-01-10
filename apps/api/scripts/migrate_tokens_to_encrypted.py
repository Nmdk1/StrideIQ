#!/usr/bin/env python3
"""
Migrate existing plain-text tokens to encrypted format.

This script should be run once after deploying token encryption.
It encrypts all existing Strava tokens in the database.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db_sync
from models import Athlete
from services.token_encryption import encrypt_token, get_token_encryption

def migrate_tokens():
    """Migrate all plain-text tokens to encrypted format."""
    db = get_db_sync()
    encryption = get_token_encryption()
    
    try:
        athletes = db.query(Athlete).all()
        migrated_count = 0
        
        print(f"Found {len(athletes)} athletes")
        print("=" * 70)
        
        for athlete in athletes:
            updated = False
            
            # Check and encrypt Strava access token
            if athlete.strava_access_token:
                if not encryption.is_encrypted(athlete.strava_access_token):
                    encrypted = encrypt_token(athlete.strava_access_token)
                    if encrypted:
                        athlete.strava_access_token = encrypted
                        updated = True
                        print(f"✅ Encrypted Strava access token for athlete {athlete.id}")
            
            # Check and encrypt Strava refresh token
            if athlete.strava_refresh_token:
                if not encryption.is_encrypted(athlete.strava_refresh_token):
                    encrypted = encrypt_token(athlete.strava_refresh_token)
                    if encrypted:
                        athlete.strava_refresh_token = encrypted
                        updated = True
                        print(f"✅ Encrypted Strava refresh token for athlete {athlete.id}")
            
            if updated:
                migrated_count += 1
        
        if migrated_count > 0:
            db.commit()
            print(f"\n✅ Migrated {migrated_count} athletes' tokens")
        else:
            print("\n✅ No tokens needed migration (all already encrypted or empty)")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    migrate_tokens()

