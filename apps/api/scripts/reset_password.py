"""Reset password for a user."""
from sqlalchemy import create_engine, text
import bcrypt
import os

database_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@postgres:5432/running_app')
engine = create_engine(database_url)

email = 'mbshaf@gmail.com'
password = 'StrideIQ2026!'
hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
hash_str = hashed.decode('utf-8')

with engine.connect() as conn:
    result = conn.execute(
        text("UPDATE athlete SET password_hash = :hash WHERE email = :email"),
        {'hash': hash_str, 'email': email}
    )
    conn.commit()
    print(f'Updated password for {email}')
    print(f'New hash: {hash_str}')
