"""
Fix unencrypted Strava tokens in the database.

The token encryption was added after some tokens were already stored.
This script encrypts any unencrypted tokens.
"""

import argparse
import os
import sys

sys.path.insert(0, "/app")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Athlete
from services.token_encryption import decrypt_token, encrypt_token


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


def fix_tokens(*, session: "sessionmaker", commit: bool) -> int:
    """Find and encrypt any unencrypted Strava tokens."""
    s = session()
    
    try:
        athletes = s.query(Athlete).filter(
            Athlete.strava_access_token.isnot(None)
        ).all()
        
        print(f"Found {len(athletes)} athletes with Strava tokens")
        
        fixed_count = 0
        for athlete in athletes:
            needs_fix = False
            
            # Check access token
            if athlete.strava_access_token:
                if not is_encrypted_token(athlete.strava_access_token):
                    print(f"\nAthlete {athlete.id}: needs access token encryption")
                    if commit:
                        athlete.strava_access_token = encrypt_token(athlete.strava_access_token)
                        needs_fix = True
                else:
                    # Verify it can be decrypted
                    decrypted = decrypt_token(athlete.strava_access_token)
                    if decrypted:
                        print(f"\nAthlete {athlete.id}: access token OK (encrypted, decrypts)")
                    else:
                        print(f"\nAthlete {athlete.id}: access token PROBLEM (encrypted but can't decrypt)")
            
            # Check refresh token
            if athlete.strava_refresh_token:
                if not is_encrypted_token(athlete.strava_refresh_token):
                    print("  -> needs refresh token encryption")
                    if commit:
                        athlete.strava_refresh_token = encrypt_token(athlete.strava_refresh_token)
                        needs_fix = True
            
            if needs_fix:
                fixed_count += 1
        
        if fixed_count > 0:
            if commit:
                s.commit()
                print(f"\n✅ Fixed {fixed_count} athletes' tokens")
            else:
                s.rollback()
                print(f"\nDRY_RUN: would fix {fixed_count} athletes' tokens (run with --commit)")
        else:
            print("\n✅ All tokens already properly encrypted")

        return 0
        
    finally:
        s.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres/running_app"),
        help="SQLAlchemy database URL (defaults to DATABASE_URL env var)",
    )
    parser.add_argument("--commit", action="store_true", help="Persist changes (default: dry-run)")
    args = parser.parse_args()

    engine = create_engine(args.database_url)
    Session = sessionmaker(bind=engine)
    raise SystemExit(fix_tokens(session=Session, commit=args.commit))
