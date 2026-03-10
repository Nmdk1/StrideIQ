# Purge Test Athletes from Production DB

**Use when:** Test fixtures (example.com emails) have leaked into the production database after running pytest against live containers.

**Safe:** Only deletes rows where `email LIKE '%example.com'`. Real athletes are never touched.

## The Command

```bash
docker exec strideiq_postgres psql -U postgres -d running_app -c "
SET session_replication_role = replica;
DELETE FROM athlete WHERE email LIKE '%example.com';
SET session_replication_role = DEFAULT;
"
```

`session_replication_role = replica` disables FK constraint enforcement for the session, allowing a single DELETE to cascade through all 40+ dependent tables without manually ordering them. It is reset immediately after.

## Verify Before Running

```bash
docker exec strideiq_postgres psql -U postgres -d running_app -c "
SELECT COUNT(*), MIN(created_at), MAX(created_at)
FROM athlete
WHERE email LIKE '%example.com';
"
```

## Verify After Running

```bash
docker exec strideiq_postgres psql -U postgres -d running_app -c "
SELECT COUNT(*) FROM athlete WHERE email LIKE '%example.com';
"
```

Expected: `0`

## Why This Happens

The test suite creates real `Athlete` rows using `SessionLocal()` which connects to the production Postgres database, not an isolated test DB. Tests run via `docker exec strideiq_api python -m pytest` write to production.

## Permanent Fix (not yet implemented)

Add teardown to tests that create athletes:

```python
@pytest.fixture
def test_athlete(db):
    user = Athlete(email=f"test_{uuid4()}@example.com", ...)
    db.add(user)
    db.commit()
    yield user
    db.delete(user)
    db.commit()
```

Or add a guard at the top of test files that create DB rows:

```python
import os
assert "test" in os.getenv("DATABASE_URL", ""), "Refusing to run against production DB"
```

## History

- First occurrence: Feb 20, 2026 — 93 test rows created during CI runs on droplet
