# Incident Report: Data Loss Near-Miss

**Date:** 2026-01-19  
**Severity:** Critical (P0)  
**Status:** Resolved  
**Data Lost:** None (recovered)

---

## Executive Summary

During ADR-044 (AI Coach) implementation, the Tester agent's actions caused the application to connect to an empty database volume instead of the volume containing production user data. This resulted in the user appearing to have no account or data. After investigation, the data was found intact in an alternative Docker volume and was successfully recovered.

**No data was permanently lost.** However, this incident exposed critical gaps in the development workflow that could have caused irreversible data loss in production.

---

## Timeline

| Time (UTC) | Event |
|------------|-------|
| ~07:51 | Tester runs docker-compose commands during ADR-044 Phase 1 verification |
| ~07:52 | Application connects to new empty volume `strideiq_postgres_data` |
| ~07:52 | `run_migrations.py` creates fresh empty schema (no safety check existed) |
| ~08:00 | User attempts login, discovers account missing |
| ~08:05 | Initial assumption: data permanently lost |
| ~08:30 | Investigation begins: discover two postgres volumes exist |
| ~08:35 | Old volume `runningapp_postgres_data` found with all user data |
| ~08:40 | docker-compose.yml updated to use external volume with user data |
| ~08:45 | Schema updated with missing columns, alembic stamped |
| ~08:50 | Application restarted, data verified accessible |
| ~09:00 | Test users cleaned up, only real user remains |
| ~09:10 | Full rebuild/restart verified, all 1020 tests pass |
| ~09:15 | New backup created |

---

## Root Cause Analysis

### Primary Cause: Docker Volume Name Mismatch

Docker Compose derives volume names from the project name, which defaults to the directory name. At some point in development:

1. Project was initially run as `runningapp` → created `runningapp_postgres_data`
2. Directory or configuration changed → `strideiq` prefix used
3. New volume `strideiq_postgres_data` created (empty)
4. Application connected to empty volume, appeared to lose data

### Contributing Causes

1. **No data-aware safety check in `run_migrations.py`**
   - Script would run `create_all()` on any database, empty or not
   - No detection of existing production data

2. **No backup requirement in Epoch workflow**
   - Builder/Tester could modify database infrastructure without backup
   - No pre-change verification step

3. **No volume audit before infrastructure changes**
   - Multiple volumes with similar names not detected
   - Assumption that "the" postgres volume was correct

4. **No explicit volume configuration in docker-compose.yml**
   - Volumes were implicitly created, not explicitly referenced

---

## Data Impact Assessment

### What Was At Risk

| Data Type | Count | Status |
|-----------|-------|--------|
| User Account | 1 | Recovered |
| Activities | 363 | Recovered |
| Activity Splits | 1,381 | Recovered |
| Personal Bests | 6 | Recovered |
| Training Plans | 2 | Recovered |
| Planned Workouts | 224 | Recovered |
| Daily Check-ins | 0 | N/A |
| Nutrition Entries | 0 | N/A |

### What Was Lost

**Nothing.** All data was recovered.

---

## Remediation Actions Taken

### Immediate (During Incident)

1. **Data Recovery**
   - Located old volume with user data
   - Updated docker-compose.yml to use external volume reference
   - Added missing schema columns manually
   - Verified all data accessible

2. **Cleanup**
   - Removed 31 test accounts created by pytest
   - Only production user remains in database

### Permanent Safeguards

1. **Safety Check in `run_migrations.py`**
   ```python
   # If athlete table has data, don't overwrite schema
   result = conn.execute(text("SELECT COUNT(*) FROM athlete"))
   if count and count > 0:
       print(f"Database has {count} athletes - skipping schema creation")
       return
   ```
   - Script now detects existing data and refuses to run `create_all()`
   - Logs warning and exits safely

2. **Explicit External Volume in docker-compose.yml**
   ```yaml
   volumes:
     postgres_data:
       external: true
       name: runningapp_postgres_data
   ```
   - Volume explicitly named, not auto-generated
   - Prevents accidental creation of new empty volume

3. **Modified Epoch Workflow v1.3** (Section 8: Database Safety Protocol)
   - Mandatory backup before infrastructure changes
   - Forbidden actions list (`docker-compose down -v`, etc.)
   - Volume safety check procedure
   - Recovery procedure documented

4. **Backup Files Created**
   - `backups/old_data_backup.sql` (original recovery)
   - `backups/backup_20260119_recovery.sql` (post-recovery)
   - `backups/backup_20260119_verified_clean.sql` (post-cleanup)

---

## Production Implications

### If This Had Happened in Production

- **All user data would appear lost**
- Strava re-sync would recover activities but lose:
  - Manual annotations
  - Training plan history
  - Personal bests
  - Check-in/nutrition logs
  - Coach conversation history
- **User trust would be destroyed**
- **Business would fail immediately**

### Required Before Production

1. **Automated Daily Backups**
   - Scripts exist (`scripts/backup_database.py`) but not scheduled
   - Must be activated before beta

2. **S3/Cloud Backup Storage**
   - Local backups insufficient for disaster recovery
   - Configure S3 bucket and automated upload

3. **Backup Verification**
   - Automated test restore to verify backup integrity
   - Alert on backup failure

4. **Separation of Environments**
   - Dev database must never share volumes with production
   - Explicit environment isolation

---

## Lessons Learned

### Process Failures

1. **"Task completion" mindset is dangerous**
   - Tester focused on verifying features, not protecting data
   - Speed over safety is unacceptable for production software

2. **Implicit assumptions kill**
   - Assumed "the database" was obvious
   - Multiple volumes with similar names existed silently

3. **No rollback plan existed**
   - If data had been truly lost, no recovery path
   - Backups were documented but never created

### What Worked

1. **Docker volumes don't auto-delete**
   - Old volume preserved even when unused
   - Made recovery possible

2. **Thorough investigation before giving up**
   - Initial assumption of permanent loss was wrong
   - Checking all volumes found the data

3. **Safety check now prevents recurrence**
   - Script refuses to overwrite existing data
   - Logs explicit warning

---

## Action Items

| Priority | Item | Status |
|----------|------|--------|
| P0 | Add safety check to run_migrations.py | ✅ Complete |
| P0 | Use explicit external volume in docker-compose.yml | ✅ Complete |
| P0 | Update Epoch Workflow with Database Safety Protocol | ✅ Complete |
| P0 | Create backup of recovered data | ✅ Complete |
| P1 | Schedule automated daily backups | Pending |
| P1 | Configure S3 backup storage | Pending |
| P1 | Add backup verification tests | Pending |
| P2 | Create dev/staging environment separation | Pending |

---

## Additional Issue (Same Session)

### Training Pace Calculator Regression

**Issue:** Calculator regressed to using copyrighted Daniels lookup tables instead of physics-based formulas. This has happened 3+ times.

**Root cause:** `LOOKUP_AVAILABLE = True` was importing `vdot_lookup.py`

**Fix applied:**
1. Set `LOOKUP_AVAILABLE = False` in `vdot_calculator.py`
2. Updated docstring with clear "DO NOT RE-ENABLE" warning
3. Added regression test that will FAIL if lookup is re-enabled
4. Updated test expectations to match physics formula output

**Result:** 1035 tests pass

---

## Additional Issue: SECRET_KEY Security Vulnerability (FIXED)

**Issue:** SECRET_KEY was Optional with no default, causing a new random key to be generated on every server restart. This invalidated all user tokens on restart.

**Root cause:** 
- `config.py` had `SECRET_KEY: Optional[str] = Field(default=None)`
- `security.py` had fallback: `SECRET_KEY = settings.SECRET_KEY or secrets.token_urlsafe(32)`

**Production-ready fix:**
1. Made SECRET_KEY **required** in `config.py` (app fails to start without it)
2. Added **minimum length validation** (32 chars) in `security.py`
3. Removed fallback random key generation
4. Added SECRET_KEY to `.env` (gitignored)
5. Updated `docker-compose.yml` to read from env (no default)
6. Added Security Requirements section to `MODIFIED_EPOCH_WORKFLOW.md` v1.4

**Verification:**
- App fails to start without SECRET_KEY (tested)
- App fails to start with < 32 char key (tested)
- Tokens persist across restarts with proper key (tested)
- 1035 tests pass

---

## Sign-Off

**Incident Resolved By:** Opus 4.5 (Planner)  
**Verified By:** Judge (manual login test confirmed working)  
**Scale Testing:** Deferred to post-production push  
**Date:** 2026-01-19

---

*This incident must never happen again. Data security is non-negotiable.*
