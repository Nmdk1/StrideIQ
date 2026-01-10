"""Set password for user."""
import bcrypt
import psycopg2

# Generate hash
password = 'StrideIQ2026!'
salt = bcrypt.gensalt()
hash_bytes = bcrypt.hashpw(password.encode('utf-8'), salt)
hash_str = hash_bytes.decode('utf-8')
print(f'Generated hash: {hash_str}')

# Connect and update
conn = psycopg2.connect(
    host='running_app_postgres',
    database='running_app',
    user='postgres',
    password='postgres'
)
cur = conn.cursor()
cur.execute(
    "UPDATE athlete SET password_hash = %s WHERE email = %s",
    (hash_str, 'mbshaf@gmail.com')
)
conn.commit()
print('Password updated successfully')
cur.close()
conn.close()
