# Garmin Connect Integration

## Overview

Garmin Connect integration enables the coaching engine to pull high-fidelity run data and reliable recovery metrics. This closes the data loop and sets the foundation for true adaptive coaching.

**Status:** ⚠️ **BLOCKED** - Username/password authentication blocked by Garmin (January 2026)

## Current Limitation

**Issue:** The unofficial `python-garminconnect` library fails with `AssertionError` when attempting username/password login. Garmin has implemented security measures that block automated credential-based access.

**Root Cause:** Garmin Connect now requires:
- Official OAuth 2.0 flow (requires registered application)
- Business registration and verification
- Live website with privacy policy
- API access approval process

**Workaround:** Strava integration is fully functional and serves as primary data source:
- ✅ 362 activities synced successfully
- ✅ Complete run data: distance, pace, splits, HR, power
- ✅ Sufficient for efficiency trends and adaptation rules
- ⚠️ Recovery metrics limited (sleep, HRV) until official API access

## Future Plan

**Phase:** Post-launch (after website goes live)
1. Register business and obtain official Garmin API credentials
2. Implement OAuth 2.0 flow
3. Migrate from unofficial library to official API
4. Enable recovery metrics (sleep, HRV, resting HR, overnight HR)

## Implementation Status

**Status:** ✅ Code Complete, ⚠️ Authentication Blocked

## Architecture

### Security (Phase 1) ✅
- **Token Encryption**: All OAuth tokens (Strava + Garmin) encrypted using Fernet symmetric encryption
- **Encryption Key**: Stored in `TOKEN_ENCRYPTION_KEY` environment variable
- **Migration**: Script available to migrate existing plain-text tokens (`scripts/migrate_tokens_to_encrypted.py`)

### Garmin OAuth & Initial Sync (Phase 2) ✅
- **Library**: Uses unofficial `python-garminconnect` library
- **Authentication**: Username/password flow (library handles OAuth internally)
- **Credential Storage**: Username stored plain, password encrypted
- **Initial Sync**: On first connect, backfills 30-120 days of data

### Data Pulls (Phase 3) ✅

#### Recovery Metrics (High-Reliability Signals Only)
- ✅ **Sleep Duration**: Total time asleep (NO sleep stages - unreliable)
- ✅ **HRV**: rMSSD and SDNN values (nightly)
- ✅ **Resting HR**: Daily lowest/morning value
- ✅ **Overnight Avg HR**: Mean HR during detected sleep window
- ❌ **NOT Included**: Body Battery, stress scores, sleep stages (unreliable)

#### Full Activity Data
- ✅ Distance, time (moving/elapsed)
- ✅ Pace splits
- ✅ Power, HR zones
- ✅ Avg/max HR
- ✅ Perceived effort (RPE)
- ✅ Training effect
- ✅ Calories (active/resting/total)
- ✅ Estimated sweat loss, fluid balance
- ✅ Split-level data

### Sync Logic & Source Priority (Phase 4) ✅

#### Priority Order
1. **Garmin is Primary**: Garmin data takes priority over Strava
2. **Deduplication**: Match activities by:
   - Date (within 24 hours)
   - Start time (within 1 hour)
   - Distance (within 5%)
   - Avg HR (within 5 bpm if both have HR)
3. **Fallback**: If no Garmin data for a workout, accept Strava version

#### Background Sync
- **Pattern**: Reuses existing Celery background task pattern
- **Staggering**: Syncs distributed over 24 hours (10-20 users every 5-10 minutes)
- **Script**: `scripts/schedule_staggered_garmin_syncs.py` for scheduling
- **Token Refresh**: Reuses Strava pattern with encrypted tokens

### Resilience & Monitoring (Phase 5) ✅

#### Health Checks
- **Daily Library Check**: `tasks.garmin_health_check` verifies library availability
- **Graceful Degradation**: Falls back to Strava/manual upload on failure
- **Error Handling**: Comprehensive logging and error tracking

#### Monitoring
- **Logging**: All sync operations logged with structured logging
- **Early Detection**: Health checks detect library issues early
- **Migration Path**: Documented path to official Garmin API (when business formalized)

## Database Schema

### Athlete Model (New Fields)
```python
garmin_username: str  # Plain text (username only)
garmin_password_encrypted: str  # Encrypted password
garmin_connected: bool  # Connection status
last_garmin_sync: datetime  # Last sync timestamp
garmin_sync_enabled: bool  # Enable/disable sync
```

### DailyCheckin Model (New Fields)
```python
hrv_rmssd: Numeric  # HRV rMSSD value
hrv_sdnn: Numeric  # HRV SDNN value
resting_hr: Integer  # Resting heart rate (bpm)
overnight_avg_hr: Numeric  # Overnight average HR (bpm)
```

## API Endpoints

### POST `/v1/garmin/connect`
Connect athlete's Garmin account.

**Request:**
```json
{
  "username": "user@example.com",
  "password": "password",
  "athlete_id": "optional-uuid"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Garmin account connected successfully",
  "athlete_id": "uuid",
  "initial_sync_triggered": true
}
```

### POST `/v1/garmin/disconnect`
Disconnect athlete's Garmin account.

**Request:**
```json
{
  "athlete_id": "uuid"
}
```

### POST `/v1/garmin/sync`
Manually trigger Garmin sync.

**Request:**
```json
{
  "athlete_id": "uuid"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Garmin sync triggered",
  "activity_sync_task_id": "task-id",
  "recovery_sync_task_id": "task-id"
}
```

### GET `/v1/garmin/status/{athlete_id}`
Get Garmin connection status.

**Response:**
```json
{
  "connected": true,
  "sync_enabled": true,
  "last_sync": "2026-01-05T07:00:00Z",
  "username": "user@example.com"
}
```

## Celery Tasks

### `tasks.sync_garmin_activities`
Syncs Garmin activities for an athlete.

**Args:**
- `athlete_id`: UUID string

**Returns:**
```json
{
  "status": "success",
  "synced_new": 10,
  "updated_existing": 5
}
```

### `tasks.sync_garmin_recovery_metrics`
Syncs recovery metrics for an athlete.

**Args:**
- `athlete_id`: UUID string
- `days_back`: Number of days to sync (default: 30)

**Returns:**
```json
{
  "status": "success",
  "days_synced": 30
}
```

### `tasks.garmin_health_check`
Daily health check for Garmin library.

**Returns:**
```json
{
  "status": "healthy",
  "library_available": true,
  "timestamp": "2026-01-05T07:00:00Z"
}
```

## Setup Instructions

### 1. Generate Encryption Key
```bash
docker compose exec api python scripts/generate_encryption_key.py
```

Add output to `.env`:
```
TOKEN_ENCRYPTION_KEY=your-generated-key-here
```

### 2. Migrate Existing Tokens
```bash
docker compose exec api python scripts/migrate_tokens_to_encrypted.py
```

### 3. Install Dependencies
Dependencies are already in `requirements.txt`:
- `cryptography==41.0.7`
- `garminconnect==0.2.19`

### 4. Run Migrations
```bash
docker compose exec api alembic upgrade head
```

### 5. Schedule Staggered Syncs (Optional)
Add to cron or scheduled task:
```bash
# Daily at midnight
0 0 * * * docker compose exec api python scripts/schedule_staggered_garmin_syncs.py
```

## Usage

### Connect Garmin Account
```python
import requests

response = requests.post(
    "http://localhost:8000/v1/garmin/connect",
    json={
        "username": "user@example.com",
        "password": "password",
        "athlete_id": "athlete-uuid"  # Optional
    }
)
```

### Check Status
```python
response = requests.get(
    "http://localhost:8000/v1/garmin/status/{athlete_id}"
)
```

### Manual Sync
```python
response = requests.post(
    "http://localhost:8000/v1/garmin/sync",
    json={"athlete_id": "athlete-uuid"}
)
```

## Risk Mitigation

### Unofficial Library Risk
- **Mitigation**: Health checks detect library issues early
- **Fallback**: Strava integration remains available
- **Migration Path**: Documented path to official API

### Detection Risk
- **Mitigation**: Staggered syncs mimic natural user behavior
- **Conservative Polling**: 10-20 users every 5-10 minutes
- **Rate Limiting**: Built-in delays and retry logic

### Token Security
- **Encryption**: All tokens encrypted at rest
- **No Plain Storage**: Never store plain credentials
- **Key Management**: Encryption key in environment variable

## Scale Considerations

### Target: 300 Concurrent Users
- **Staggering**: Syncs distributed over 24 hours
- **Batch Size**: 10-20 users per batch
- **Interval**: 5-10 minutes between batches
- **Conservative**: Well under detection thresholds

### Beta Phase: 50-100 Users
- **Monitoring**: Close monitoring during beta
- **Gradual Rollout**: Scale up based on performance
- **Error Tracking**: Comprehensive logging

## Future Enhancements

### Official API Migration
When business is formalized:
1. Apply for official Garmin API access
2. Migrate from `python-garminconnect` to official API
3. Update authentication flow (OAuth 2.0)
4. Maintain backward compatibility during transition

### Additional Metrics (Post-Launch)
- Body Battery (if reliable)
- Stress scores (if reliable)
- Sleep stages (if reliable)

## Files Created/Modified

### New Files
- `apps/api/services/token_encryption.py` - Token encryption service
- `apps/api/services/garmin_service.py` - Garmin API service
- `apps/api/services/activity_deduplication.py` - Deduplication logic
- `apps/api/tasks/garmin_tasks.py` - Celery tasks
- `apps/api/routers/garmin.py` - API endpoints
- `apps/api/scripts/migrate_tokens_to_encrypted.py` - Token migration
- `apps/api/scripts/generate_encryption_key.py` - Key generation
- `apps/api/scripts/schedule_staggered_garmin_syncs.py` - Sync scheduling

### Modified Files
- `apps/api/models.py` - Added Garmin fields and recovery metrics
- `apps/api/core/config.py` - Added encryption key config
- `apps/api/services/strava_service.py` - Updated to use encrypted tokens
- `apps/api/routers/strava.py` - Updated to encrypt tokens on save
- `apps/api/tasks/__init__.py` - Added Garmin tasks
- `apps/api/main.py` - Added Garmin router
- `apps/api/requirements.txt` - Added cryptography and garminconnect

### Migrations
- `apps/api/alembic/versions/728acc5f0965_add_garmin_fields_and_encrypt_tokens.py`

## Testing Checklist

- [ ] Generate encryption key
- [ ] Migrate existing tokens
- [ ] Connect Garmin account via API
- [ ] Verify initial sync (activities + recovery)
- [ ] Test deduplication (Garmin vs Strava)
- [ ] Test manual sync trigger
- [ ] Test health check
- [ ] Test staggered sync scheduling
- [ ] Verify token encryption/decryption
- [ ] Test error handling (invalid credentials)
- [ ] Test fallback to Strava

## Notes

- **Library**: Uses unofficial `python-garminconnect` library
- **Risk**: Library may break if Garmin changes API
- **Mitigation**: Health checks and fallback to Strava
- **Migration**: Path to official API documented
- **Scale**: Conservative polling for 300 users
- **Beta**: Start with 50-100 users, monitor closely

