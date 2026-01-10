# Race Selection and Splits Backfill - January 4, 2026

## Issues Identified

### 1. Race Detection Missing Some Races ✅ FIXED
**Problem:** Automatic race detection missed some races that should be marked.

**Solution:** Added manual race selection API endpoint:
- `POST /v1/activities/{activity_id}/mark-race?is_race=true` - Mark activity as race
- `POST /v1/activities/{activity_id}/mark-race?is_race=false` - Unmark activity as race

**Implementation:**
- Updates `user_verified_race` flag (overrides automatic detection)
- Updates `is_race_candidate` flag
- Sets `race_confidence` to 1.0 when user marks as race

### 2. Missing Splits for Older Activities ✅ FIXED
**Problem:** 187 activities are missing splits, particularly older activities (before March 2025).

**Root Cause:** 
- Splits were only fetched for activities synced after the splits feature was implemented
- Older activities synced before splits feature don't have lap data

**Solution:** 
1. Added API endpoint to backfill splits for individual activities:
   - `POST /v1/activities/{activity_id}/backfill-splits`
   
2. Created script to backfill all missing splits:
   - `scripts/backfill_all_missing_splits.py`

**Statistics:**
- Total activities > 1 mile: 341
- Activities missing splits: 187
- Most missing splits are from July-September 2025 and earlier

## API Endpoints Added

### Mark Activity as Race
```http
POST /v1/activities/{activity_id}/mark-race?is_race=true
```

**Response:**
```json
{
  "status": "success",
  "activity_id": "uuid",
  "is_race": true,
  "message": "Activity marked as race"
}
```

### Backfill Splits for Activity
```http
POST /v1/activities/{activity_id}/backfill-splits
```

**Response:**
```json
{
  "status": "success",
  "activity_id": "uuid",
  "splits_created": 6,
  "message": "Successfully backfilled 6 splits"
}
```

## Scripts Created

### Check Missing Splits
```bash
docker compose exec api python scripts/check_missing_splits.py
```

Shows:
- Total activities missing splits
- List of activities missing splits
- Breakdown by date range

### Backfill All Missing Splits
```bash
docker compose exec api python scripts/backfill_all_missing_splits.py
```

**Features:**
- Processes all activities missing splits
- Fetches lap data from Strava API
- Creates split records with HR and cadence data
- Includes rate limiting (2s delay between requests)
- Progress reporting

**Note:** This will take time due to rate limiting. For 187 activities, expect ~6-7 minutes.

## Usage Instructions

### To Mark a Race Manually:
1. Find the activity ID from the frontend or API
2. Call: `POST /v1/activities/{activity_id}/mark-race?is_race=true`
3. The activity will be marked as a race with confidence 1.0

### To Backfill Splits:
**Option 1: Backfill all missing splits (recommended)**
```bash
docker compose exec api python scripts/backfill_all_missing_splits.py
```

**Option 2: Backfill individual activity**
```bash
# Get activity ID first, then:
curl -X POST "http://localhost:8000/v1/activities/{activity_id}/backfill-splits"
```

## Files Modified

- `apps/api/routers/v1.py` - Added race marking and splits backfill endpoints
- `apps/api/scripts/check_missing_splits.py` - Script to check for missing splits
- `apps/api/scripts/backfill_all_missing_splits.py` - Script to backfill all missing splits

## Next Steps

1. **Run backfill script** to populate splits for older activities:
   ```bash
   docker compose exec api python scripts/backfill_all_missing_splits.py
   ```

2. **Manually mark missed races** using the API endpoint or frontend (when UI is built)

3. **Frontend Integration** (future):
   - Add "Mark as Race" button on activity details page
   - Add "Backfill Splits" button for activities missing splits
   - Show visual indicator when splits are missing

## Notes

- The backfill script respects Strava rate limits (2s delay between requests)
- If an activity already has splits, the backfill endpoint will skip it
- User-verified race flag takes precedence over automatic detection
- Splits backfill requires Strava access token and external activity ID


