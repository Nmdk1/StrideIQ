#!/usr/bin/env python3
"""Script to run Alembic migrations"""
import os
import sys
import time
import subprocess
from dotenv import load_dotenv

load_dotenv()

def check_db_ready():
    """Check if database is ready"""
    import psycopg2
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'postgres'),
            port=os.getenv('POSTGRES_PORT', '5432'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', 'postgres'),
            database=os.getenv('POSTGRES_DB', 'running_app')
        )
        conn.close()
        return True
    except Exception:
        return False

def main():
    print("Waiting for database to be ready...")
    max_retries = 30
    retry_count = 0
    
    while retry_count < max_retries:
        if check_db_ready():
            print("Database is ready!")
            break
        retry_count += 1
        print(f"Database is unavailable - sleeping (attempt {retry_count}/{max_retries})")
        time.sleep(1)
    else:
        print("ERROR: Database is not ready after maximum retries")
        sys.exit(1)
    
    print("Running migrations...")
    result = subprocess.run(['alembic', 'upgrade', 'head'], cwd='/app')
    
    if result.returncode == 0:
        print("Migrations completed successfully!")
    else:
        print("ERROR: Migrations failed")
        sys.exit(1)

if __name__ == '__main__':
    main()




