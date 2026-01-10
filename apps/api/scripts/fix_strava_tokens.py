"""
Fix unencrypted Strava tokens in the database.

The token encryption was added after some tokens were already stored.
This script encrypts any unencrypted tokens.
"""

import os
import sys
sys.path.insert(0, '/app')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Athlete
from services.token_encryption import encrypt_token, decrypt_token

# Database connection
DATABASE_URL = "postgresql://postgres:postgres@postgres/running_app"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def is_encrypted_token(token: str) -> bool:
    """Check if a token appears to be Fernet-encrypted."""
    if not token:
        return False
    
    # Fernet tokens are base64 encoded and start with 'gAAAAA'
    # Raw Strava tokens are 40-char hex strings
    if len(token) == 40 and all(c in '0123456789abcdef' for c in token.lower()):
        return False  # Looks like raw Strava token
    
    if token.startswith('gAAAAA'):
        return True  # Looks like Fernet encrypted
    
    return len(token) > 100  # Encrypted tokens are much longer


def fix_tokens():
    """Find and encrypt any unencrypted Strava tokens."""
    session = Session()
    
    try:
        athletes = session.query(Athlete).filter(
            Athlete.strava_access_token.isnot(None)
        ).all()
        
        print(f"Found {len(athletes)} athletes with Strava tokens")
        
        fixed_count = 0
        for athlete in athletes:
            needs_fix = False
            
            # Check access token
            if athlete.strava_access_token:
                if not is_encrypted_token(athlete.strava_access_token):
                    print(f"\nAthlete {athlete.email}:")
                    print(f"  Access token length: {len(athlete.strava_access_token)}")
                    print(f"  Token preview: {athlete.strava_access_token[:10]}...")
                    print("  -> Encrypting access token")
                    athlete.strava_access_token = encrypt_token(athlete.strava_access_token)
                    needs_fix = True
                else:
                    # Verify it can be decrypted
                    decrypted = decrypt_token(athlete.strava_access_token)
                    if decrypted:
                        print(f"\nAthlete {athlete.email}: Access token OK (encrypted, decrypts)")
                    else:
                        print(f"\nAthlete {athlete.email}: Access token PROBLEM (encrypted but can't decrypt)")
            
            # Check refresh token
            if athlete.strava_refresh_token:
                if not is_encrypted_token(athlete.strava_refresh_token):
                    print(f"  -> Encrypting refresh token")
                    athlete.strava_refresh_token = encrypt_token(athlete.strava_refresh_token)
                    needs_fix = True
            
            if needs_fix:
                fixed_count += 1
        
        if fixed_count > 0:
            session.commit()
            print(f"\n✅ Fixed {fixed_count} athletes' tokens")
        else:
            print("\n✅ All tokens already properly encrypted")
        
    finally:
        session.close()


if __name__ == "__main__":
    fix_tokens()
