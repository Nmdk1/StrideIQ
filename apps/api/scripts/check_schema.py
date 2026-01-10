from sqlalchemy import create_engine, text
import os

user = os.environ.get('POSTGRES_USER', 'postgres')
password = os.environ.get('POSTGRES_PASSWORD', 'postgres')
host = os.environ.get('POSTGRES_HOST', 'postgres')
db = os.environ.get('POSTGRES_DB', 'running_app')
db_url = f'postgresql://{user}:{password}@{host}:5432/{db}'

engine = create_engine(db_url)
with engine.connect() as conn:
    result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'activity' ORDER BY ordinal_position"))
    print("Activity table columns:")
    for row in result:
        print(f"  {row[0]}")


