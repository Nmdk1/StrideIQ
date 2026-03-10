# Session Handoff — Garmin Live Verification & Webhook Fix

**Date:** February 22, 2026 (evening session)
**Status:** Garmin health webhooks LIVE. Activity webhook pending next run. Backfill failing — fix needed.
**Branch:** `main` (commit `ae75087`)
**Prior handoff:** `docs/SESSION_HANDOFF_2026-02-22_GARMIN_BUILD.md`

---

## Read order before first tool call

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/PRODUCT_MANIFESTO.md`
3. `docs/PHASE2_GARMIN_INTEGRATION_AC.md`
4. `docs/GARMIN_CONNECT_DEVELOPER_COMPLIANCE.md`
5. `docs/garmin-portal/HEALTH_API.md` (backfill endpoint docs — critical for the open fix)
6. `docs/GARMIN_API_REFERENCE.md` (section 5: Backfill — note the 30-day limit for activities)
7. This document

---

## What happened this session

### 1. Portal webhook URLs registered (founder action)

Founder registered all 9 Tier 1 webhook URLs in the Garmin Developer Portal Endpoint Configuration:

| Endpoint | URL | Mode |
|---|---|---|
| Activities | `https://strideiq.run/v1/garmin/webhook/activities` | enabled (push) |
| Activity Details | `https://strideiq.run/v1/garmin/webhook/activity-details` | enabled (push) |
| Sleeps | `https://strideiq.run/v1/garmin/webhook/sleeps` | enabled (push) |
| HRV Summary | `https://strideiq.run/v1/garmin/webhook/hrv` | enabled (push) |
| Stress | `https://strideiq.run/v1/garmin/webhook/stress` | enabled (push) |
| Dailies | `https://strideiq.run/v1/garmin/webhook/dailies` | enabled (push) |
| User Metrics | `https://strideiq.run/v1/garmin/webhook/user-metrics` | enabled (push) |
| Deregistrations | `https://strideiq.run/v1/garmin/webhook/deregistrations` | enabled (ping) |
| User Permissions | `https://strideiq.run/v1/garmin/webhook/permissions` | enabled (ping) |

All other endpoints left on hold with placeholder URLs.

### 2. Webhook parser fix (commit `ae75087`)

**Bug:** Garmin push payloads use an array envelope format:
```json
{"stressDetails": [{"userId": "...", "calendarDate": "...", ...}]}
```

Our parser expected `userId` at the top level of a flat dict. Every webhook was rejected with HTTP 400, triggering Garmin's 7-day retry queue.

**Fix in `apps/api/routers/garmin_webhooks.py`:**
- `_parse_and_validate_push_payload` now accepts a `data_key` parameter and unwraps the array envelope
- Route-to-key mapping: activities→`activities`, activity-details→`activityDetails`, sleeps→`sleeps`, hrv→`hrv`, stress→`stressDetails`, dailies→`dailies`, user-metrics→`userMetrics`
- Each route handler iterates over the record array, resolving athlete and dispatching per-record
- Unrecognized payloads return 200 (not 400) to prevent retry storms
- Flat dict fallback preserved for safety
- INFO-level logging of raw envelope keys for D4.3 documentation

**Tests updated in `apps/api/tests/test_garmin_d4_webhooks.py`:**
- All payloads now use array envelope format
- New tests: `test_multiple_records_dispatch_multiple_tasks`, `test_flat_payload_fallback_still_works`, `test_missing_data_key_returns_200`
- 24 tests, all passing

### 3. Live webhook verification — D4.3 COMPLETE

**Evidence (API logs, 20:34-20:35 UTC):**
```
POST /v1/garmin/webhook/stress → 200 OK (334ms, 13ms, 13ms)
POST /v1/garmin/webhook/dailies → 200 OK (483ms, 72ms)
```

**Evidence (worker logs, 20:34-20:35 UTC):**
```
process_garmin_health_task: athlete=4368ec7f data_type=stress processed=1 skipped=0 (succeeded in 0.15s)
process_garmin_health_task: athlete=4368ec7f data_type=stress processed=1 skipped=0 (succeeded in 0.01s)
process_garmin_health_task: athlete=4368ec7f data_type=dailies processed=1 skipped=0 (succeeded in 0.009s)
process_garmin_health_task: athlete=4368ec7f data_type=dailies processed=1 skipped=0 (succeeded in 0.008s)
process_garmin_health_task: athlete=4368ec7f data_type=stress processed=1 skipped=0 (succeeded in 0.01s)
process_garmin_health_task: athlete=4368ec7f data_type=dailies processed=1 skipped=0 (succeeded in 0.007s)
```

6 health records processed successfully. Zero failures. D4.3 gate is cleared.

### 4. Strava sync confirmed working

Founder's "Afternoon Run" (5 miles, Strava ID 17487837574) synced at 20:39:42 with 2440 stream data points. Displayed on home page after brief cache delay.

---

## Deliverable status (updated)

| Deliverable | Status | Notes |
|---|---|---|
| D0 — Dedup refactor | COMPLETE | |
| D1 — Data models | COMPLETE | |
| D2 — OAuth PKCE | COMPLETE | Founder connected live on production |
| D3 — Adapter layer | COMPLETE | |
| D4 — Webhook endpoints | **COMPLETE (D4.3 cleared)** | Live webhook captured, parsed, processed |
| D5 — Activity sync | COMPLETE (code) | Awaiting first Garmin activity webhook (next run) |
| D6 — Health/wellness sync | **LIVE** | Stress + dailies processing in production |
| D7 — Backfill | **FAILING — needs fix** | See below |
| D8 — Frontend/attribution | COMPLETE | Feature-flagged, founder + father only |

---

## OPEN ISSUE: Backfill failures

`request_garmin_backfill_task` fails for all 7 endpoints. Two runs produced identical results:

| Endpoint | Status | Notes |
|---|---|---|
| `/rest/backfill/activities` | 400 | Was 403 on first attempt, now 400 |
| `/rest/backfill/activityDetails` | 429 | Rate limited |
| `/rest/backfill/sleeps` | 429 | Rate limited |
| `/rest/backfill/hrv` | 400 | |
| `/rest/backfill/stressDetails` | 429 | Rate limited |
| `/rest/backfill/dailies` | 429 | Rate limited |
| `/rest/backfill/userMetrics` | 400 | |

### Suspected causes

1. **No response body logging.** The backfill service (`apps/api/services/garmin_backfill.py` line 148-152) logs the status code but not `resp.text`. We're debugging blind.

2. **Activities max range is 30 days, not 90.** Per `docs/GARMIN_API_REFERENCE.md` section 5, activities and activityDetails backfill max is 30 days. We send `_BACKFILL_DEPTH_DAYS = 90` for all endpoints. This likely causes the 400 for activities.

3. **Rate limiting cascade.** The 429s may be from repeated failed attempts (3 total backfill triggers this session). Garmin rate limits are per-key and per-evaluation-tier.

4. **HRV and userMetrics 400s.** Unknown cause — could be time range, could be parameter format, could be permissions. Response body logging will tell us.

### Required fix

In `apps/api/services/garmin_backfill.py`:

1. Add `resp.text` to the warning log for non-202 responses (line 150)
2. Use 30-day range for activities/activityDetails, 90 days for health endpoints
3. Add retry logic for 429s (retry same endpoint after backoff, max 2 retries)
4. Deploy, trigger backfill, verify

### File reference

- `apps/api/services/garmin_backfill.py` — all changes needed here
- `apps/api/tasks/garmin_webhook_tasks.py` — `request_garmin_backfill_task` calls `request_garmin_backfill()`

---

## Production state

- **Droplet:** `main` at `ae75087`
- **Containers:** api + worker rebuilt at 20:33 UTC
- **Feature flag:** `garmin_connect_enabled` = True, rollout 0%, allowlist = founder (`4368ec7f`) + father (`d0065617`)
- **Founder Garmin account:** Connected, `garmin_user_id` set, live webhooks flowing
- **Father:** Not connected to Garmin (Strava only)

---

## What NOT to touch

- Do not modify any non-Garmin code
- Do not change the feature flag or allowlist
- Do not touch Strava sync, home briefing, or AI coach code
- Do not re-propose anything in `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` rejected decisions
- Scoped commits only — never `git add -A`

---

## Remaining compliance items (not blocking backfill fix)

1. **30-day display notice:** Take screenshots of Garmin attribution in production, email to Garmin
2. **ToS review:** Quick scan for Garmin-protective liability limitations
3. **Document breach notification procedure**
