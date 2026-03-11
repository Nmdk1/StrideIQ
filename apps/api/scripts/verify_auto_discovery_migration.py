import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import engine
from sqlalchemy import inspect, text

insp = inspect(engine)
all_tables = insp.get_table_names()
ad_tables = [t for t in all_tables if "auto_discovery" in t]
print("AutoDiscovery tables:", ad_tables)

# Check alembic version
with engine.connect() as conn:
    result = conn.execute(text("SELECT version_num FROM alembic_version"))
    versions = [r[0] for r in result]
    print("Alembic versions:", versions)

# Check indexes
for table in ad_tables:
    indexes = insp.get_indexes(table)
    print(f"\nIndexes for {table}:")
    for idx in indexes:
        print(f"  {idx['name']}: {idx['column_names']}")
