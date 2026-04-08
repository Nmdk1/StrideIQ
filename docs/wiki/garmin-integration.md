# Garmin Integration

## Current State

Garmin is the primary data provider. Three webhook types handle real-time data flow. Weather enrichment via Open-Meteo provides environmental context for every outdoor activity. The FIT file pipeline extracts strength exercise sets.

## How It Works

### OAuth

- `services/garmin_oauth.py` — OAuth flow for connecting Garmin accounts
- `core/auth.py` — token management
- `services/token_encryption.py` — tokens encrypted at rest

### Three Webhook Types

| Endpoint | Mode | What it does |
|----------|------|--------------|
| `POST /v1/garmin/webhook` | PUSH | Receives full activity data on sync |
| `POST /v1/garmin/webhook/activity-details` | PUSH | Receives activity detail updates |
| `POST /v1/garmin/webhook/activity-files` | PING | Notification that FIT files are available for download |

All webhook endpoints are in `routers/garmin_webhooks.py`. Authentication via `services/garmin_webhook_auth.py`.

### Activity Sync Pipeline

1. **Webhook receives activity** → `tasks/garmin_webhook_tasks.py`
2. **Deduplication** — `services/activity_deduplication.py` prevents duplicates
3. **Activity created** → `Activity` model in `models.py`
4. **Post-sync enrichment (ordered):**
   - Weather enrichment (must happen first)
   - Heat adjustment calculation
   - Shape extraction
   - Wellness stamping

### FIT File Pipeline (Shipped Apr 6, 2026)

For strength activities, Garmin provides exercise set data in FIT files:

1. `POST /v1/garmin/webhook/activity-files` receives PING notification
2. `process_garmin_activity_file_task` in `tasks/garmin_webhook_tasks.py` dispatches
3. Downloads FIT file from Garmin API
4. `services/fit_parser.py` — `extract_exercise_sets_from_fit()` parses FIT bytes using `fitparse` library
5. Normalizes data for `services/strength_parser.py` — `parse_exercise_sets()`
6. Saves as `StrengthExerciseSet` rows linked to the `Activity`

**Dead code removed:** `fetch_garmin_exercise_sets_task` was deleted — do NOT recreate it.

### Weather Enrichment

Dual-API strategy via Open-Meteo (no API key required):

1. **Historical Forecast API** — covers today + recent dates (from 2022). Tried first.
2. **Archive API (ERA5 reanalysis)** — fallback for older dates.

Single function `fetch_weather_for_date()` tries Historical Forecast first, falls back to archive. The caller never needs to know which API served the data.

**Fields populated:** `temperature_f`, `humidity_pct`, `dew_point_f`, `wind_speed_mph`, weather conditions.

**Filter for re-enrichment:** `WHERE dew_point_f IS NULL AND start_lat IS NOT NULL` — catches both "no weather at all" and "device sensor only" activities (device sensors set temperature but not dew point).

**Indoor detection:** Skip if `start_lat IS NULL` (no GPS = indoor).

**Backfill:** `backfill_weather_for_athlete()` processes all historical activities for an athlete. 605 activities enriched for the founder.

### Health API (Garmin Day)

`GarminDay` model stores daily Garmin health data:
- Sleep: total, deep, REM, light, score
- HRV: overnight avg, 5-min high
- Resting HR, average stress, body battery
- Steps, active time

Synced via `tasks/garmin_webhook_tasks.py`, queried by coach context and correlation engine.

### Accepted Sports

Activities are stored with a `sport` field. Accepted values:
- `run`, `walking`, `hiking`, `cycling`, `strength`, `flexibility`, `swimming`

Cross-training activities flow through the same pipeline but skip run-specific processing (shape extraction, pace analysis).

## Key Decisions

- **Weather before heat adjustment before shape:** Ordering constraint in post-sync pipeline
- **Device sensor override:** API weather replaces device sensor temperature because wrist sensors are unreliable (79°F readings when actual is 69°F)
- **Fire-and-forget weather:** Weather enrichment failures don't block activity processing
- **No treadmill weather:** Indoor activities (null GPS) are skipped

## Known Issues

- **Exercise set data empty for existing activities:** The FIT file webhook was built Apr 6, 2026. Activities synced before that date have no exercise set data. Brian Levesque's strength activities show "Exercise sets: (none)" because the webhook wasn't live during those syncs.
- **Garmin rate limits:** Not currently an issue but could become one at scale

## What's Next

- Exercise set backfill for historical strength activities (requires re-downloading FIT files)
- Swimming-specific data parsing (lap/stroke data)

## Sources

- `docs/BUILDER_INSTRUCTIONS_2026-04-06_ACTIVITY_FILES_WEBHOOK.md` — FIT pipeline spec
- `docs/BUILDER_INSTRUCTIONS_2026-04-05_CROSS_TRAINING_POLISH.md` — weather enrichment spec
- `docs/garmin-portal/` — Garmin API documentation
- `apps/api/routers/garmin_webhooks.py` — webhook endpoints
- `apps/api/tasks/garmin_webhook_tasks.py` — async processing
- `apps/api/services/fit_parser.py` — FIT file parsing
- `apps/api/services/garmin_adapter.py` — Garmin API adapter
