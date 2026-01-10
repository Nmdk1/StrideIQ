"""
Legacy database module - DEPRECATED.

This file is kept for backward compatibility during migration.
New code should use `core.database` instead.

Migration path:
- Old: `from database import get_db`
- New: `from core.database import get_db`
"""
import warnings
from core.database import (
    engine,
    SessionLocal,
    Base,
    get_db,
    get_db_sync,
    check_db_connection,
)

warnings.warn(
    "Importing from 'database' is deprecated. Use 'core.database' instead.",
    DeprecationWarning,
    stacklevel=2
)



