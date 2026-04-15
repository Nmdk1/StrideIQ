# Usage Telemetry

## Current State

First-party page view tracking. One database table, one frontend hook, two athlete API endpoints, one admin query endpoint. No third-party analytics. Fire-and-forget — telemetry failures never affect the athlete experience. Deployed April 10, 2026.

## Why

Zero visibility into how athletes use the product. Every product decision (including native app screen hierarchy) was based on founder intuition. After 7 days of production data, we know exactly which screens each athlete visits, how often, and how long they spend. After 4 weeks, the native app spec is evidence-based.

## Data Model

### PageView Table

| Column | Type | Purpose |
|--------|------|---------|
| `id` | UUID | Primary key |
| `athlete_id` | UUID (FK) | Who |
| `screen` | Text | Screen name (e.g., "home", "coach", "activity_detail") |
| `referrer_screen` | Text | Previous screen |
| `entered_at` | DateTime(tz) | When they arrived |
| `exited_at` | DateTime(tz) | When they left (set by exit call) |
| `duration_seconds` | Float | Computed from entered_at to exited_at |
| `event_metadata` | JSONB | Flexible (e.g., `{"activity_id": "..."}` for activity_detail) |

Index: `ix_page_view_athlete_entered` on `(athlete_id, entered_at)`.

Note: Python attribute is `event_metadata` (SQLAlchemy reserves `metadata`); DB column is `metadata`.

## Screen Name Registry

| Screen | Path | Name |
|--------|------|------|
| Home | `/home` | `home` |
| Calendar | `/calendar` | `calendar` |
| Coach | `/coach` | `coach` |
| Manual | `/manual` | `manual` |
| Progress | `/progress` | `progress` |
| Analytics | `/analytics` | `analytics` |
| Training Load | `/training-load` | `training_load` |
| Nutrition | `/nutrition` | `nutrition` |
| Reports | `/reports` | `reports` |
| Fingerprint | `/fingerprint` | `fingerprint` |
| Settings | `/settings` | `settings` |
| Activity Detail | `/activities/:id` | `activity_detail` |
| Plan Create | `/plans/create` | `plan_create` |
| Tools | `/tools/*` | `tools` |
| Activities List | `/activities` | `activities` |

Dynamic routes (e.g., `/activities/uuid`) extract metadata: `{"activity_id": "uuid"}`.

## Frontend Hook

`usePageTracking()` in `lib/hooks/usePageTracking.ts`, wired into `ClientShell.tsx` (fires for every authenticated page).

Lifecycle:
1. On route change → resolve screen name → `POST /v1/telemetry/page-view` (fire-and-forget)
2. Store returned `page_view_id`
3. On next route change → `PATCH .../exit` for previous view
4. On tab close / `visibilitychange` → `fetch` with `keepalive: true` for exit

Unauthenticated routes (login, register, about, etc.) are excluded.

## API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /v1/telemetry/page-view` | Record page entry. Returns `{id: uuid}`. |
| `PATCH /v1/telemetry/page-view/{id}/exit` | Set exit time + compute duration. |
| `POST /v1/telemetry/page-view/{id}/exit` | Same as PATCH, for `sendBeacon` compatibility. |
| `GET /v1/telemetry/admin/usage-report?days=30` | Admin-only. Per-athlete usage summary. |

### Admin Usage Report Response

Per-athlete:
- `total_sessions` — session = page views with no gap > 30 minutes
- `total_page_views`
- `most_visited` — top 10 screens with visit count and avg duration
- `entry_points` — first screen in each session
- `hourly_distribution` — page views by hour of day
- `last_active` — most recent page view timestamp

## Key Decisions

- **No third-party analytics.** No PostHog, Mixpanel, GA. Data stays in our database.
- **Fire-and-forget.** Frontend never shows errors for telemetry failures.
- **No PII beyond athlete_id.** No click positions, scroll depth, cookies.
- **`event_metadata` naming.** SQLAlchemy reserves `metadata` on declarative base; Python attribute is `event_metadata`, DB column remains `metadata`.

## Sources

- `docs/BUILDER_INSTRUCTIONS_2026-04-10_USAGE_TELEMETRY.md`
- `apps/api/routers/telemetry.py`
- `apps/api/models.py` (PageView)
- `apps/web/lib/hooks/usePageTracking.ts`
- `apps/web/app/components/ClientShell.tsx`
