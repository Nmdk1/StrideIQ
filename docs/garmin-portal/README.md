# Garmin Developer Portal — Official Documentation

Official API documentation captured directly from the Garmin Connect Developer Portal.
These files serve as Gate 0D verification artifacts for the Garmin integration build.

**Captured by:** Founder (mbshaf@gmail.com)
**Capture date:** February 22, 2026

## Files

| File | Status | Source URL | Unblocks |
|------|--------|-----------|----------|
| `HEALTH_API.md` | CAPTURED | `/tools/apiDocs/wellness-api` | D3, D4, D5, D7 |
| `OAUTH_CONFIG.md` | CAPTURED | Portal OAuth2 Tools (Steps 1-2, consent screen) | D2 |
| `PARTNER_API.md` | CAPTURED | `/tools/apiDocs/user-api` | D2, D2.3 |
| `ENDPOINT_CONFIGURATION.md` | CAPTURED | Portal Endpoint Configuration page | D4 |
| `PERMISSIONS_AND_SCOPES.md` | CAPTURED (in OAUTH_CONFIG + PARTNER_API) | Consent screen + permissions endpoint | D2 |
| `API_CONFIGURATION.md` | CAPTURED | Portal API Configuration page | D2, General |
| `CONNECT_STATUS.md` | CAPTURED | Portal Connect Status (system health snapshot) | Reference |
| `WEBHOOK_PAYLOAD_SAMPLES.md` | PENDING | First live webhook capture (D4.3 completion gate) | D4 |

## What This Resolved

### M2 — Running Dynamics Availability
**RESOLVED:** Running dynamics (stride length, GCT, vertical oscillation, vertical ratio)
are NOT available in the Health API JSON endpoints. They exist only in raw FIT files
(`GET /rest/activityFile`). The discovery doc's field mapping for these was incorrect.

Power (`powerInWatts`) IS available in activity detail samples.

### D2 — OAuth Flow Version
**CONFIRMED:** OAuth 2.0 with PKCE (S256). Authorization endpoint is
`https://connect.garmin.com/oauth2Confirm`. Token-exchange endpoint in Partner API
is a legacy OAuth 1.0a migration path, not the primary flow.

### D2 — User Permissions (Scopes)
**CONFIRMED:** Four user-facing toggles: Activities, Women's Health, Daily Health Stats,
Historical Data. Maps to API permissions: `ACTIVITY_EXPORT`, `MCT_EXPORT`,
`HEALTH_EXPORT`. Historical Data controls backfill access and is OFF by default.

### D2.3 — Deregistration Endpoint
**CONFIRMED:** `DELETE /rest/user/registration` returns `204 No Content`.

### D4 — Webhook Authentication
**CONFIRMED:** No HMAC/signing secret configuration exists in the portal. Garmin does
not provide webhook payload signatures. Security must use compensating controls
(garmin-client-id header, IP allowlisting, strict schema validation).

### D4 — Webhook Architecture
**CONFIRMED:** Each data type has its own URL field in the portal. We can point all to
one endpoint or use per-type paths. 22 total endpoint types. Three delivery modes:
on hold, enabled (ping), push. Activity Files and COMMON types are ping-only.

### D7 — Backfill
**CONFIRMED:** Backfill is async (returns 202). Data is pushed to webhook when ready.
Not a synchronous pull. All 16 data types have backfill endpoints.
