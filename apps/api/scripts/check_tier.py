"""Check and update user subscription tier."""
from sqlalchemy import create_engine, text
import os
import sys

db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@postgres:5432/running_app')
engine = create_engine(db_url)

email = 'mbshaf@gmail.com'

with engine.connect() as conn:
    result = conn.execute(
        text("SELECT id, email, subscription_tier FROM athlete WHERE email = :email"),
        {'email': email}
    )
    row = result.fetchone()
    if row:
        print(f'ID: {row[0]}')
        print(f'Email: {row[1]}')
        print(f'Current Tier: {row[2]}')
        
        # Update to elite if not already
        if row[2] != 'elite':
            conn.execute(
                text("UPDATE athlete SET subscription_tier = 'elite' WHERE email = :email"),
                {'email': email}
            )
            conn.commit()
            print('>>> Updated to ELITE tier')
        else:
            print('>>> Already ELITE tier')
    else:
        print('User not found')
