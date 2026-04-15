# Builder Instructions: Usage Telemetry

**Date:** April 10, 2026
**Status:** APPROVED — build as soon as possible
**Depends on:** Nothing
**Estimated effort:** 0.5 session (small, self-contained)
**Priority:** High — blocks native app spec finalization and informs every product decision

---

## Read Order (mandatory)

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. This file
3. `apps/web/app/components/Navigation.tsx` — nav structure (what screens exist)
4. `apps/api/models.py` — for the new table placement

---

## What This Is

We have zero visibility into how athletes use the product. We don't know
which pages they visit, how often they open the app, what they tap first,
or how long they spend on any screen. Every product decision is based on
founder intuition and two anecdotal data points.

This feature adds a lightweight event tracking system: one frontend hook,
one API endpoint, one database table. Within one week of deployment, we
will know exactly how Mark, Jim, Larry, Adam, Josh, and the founder
actually use StrideIQ.

This is NOT a third-party analytics platform. No PostHog, no Mixpanel,
no Google Analytics. It is a first-party, privacy-respecting event log
that stays in our database and is queryable by the founder and advisor.

---

## What to Build

### 1. Database Table

New model in `apps/api/models.py`:

```python
class PageView(Base):
    __tablename__ = "page_view"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)
    screen = Column(Text, nullable=False)          # e.g., "home", "calendar", "activity_detail", "manual"
    referrer_screen = Column(Text, nullable=True)   # what screen they came from
    entered_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    exited_at = Column(DateTime(timezone=True), nullable=True)  # set when they navigate away
    duration_seconds = Column(Float, nullable=True) # computed from entered_at to exited_at
    metadata = Column(JSONB, nullable=True)          # flexible: activity_id, plan_id, etc.

    __table_args__ = (
        Index("ix_page_view_athlete_entered", "athlete_id", "entered_at"),
    )
```

Alembic migration. Chain to latest head.

### 2. API Endpoint

**`POST /v1/telemetry/page-view`**

```python
class PageViewEvent(BaseModel):
    screen: str                         # required
    referrer_screen: Optional[str]      # optional
    metadata: Optional[Dict[str, Any]]  # optional — e.g., {"activity_id": "..."}

class PageExitEvent(BaseModel):
    page_view_id: str                   # the ID returned from the enter call
```

Two endpoints:
- `POST /v1/telemetry/page-view` — logs entry, returns `{id: uuid}`. Authenticated.
- `PATCH /v1/telemetry/page-view/{id}/exit` — sets `exited_at` and computes `duration_seconds`. Authenticated. Fire-and-forget (if it fails, the entry still exists without exit time).

Both are fire-and-forget from the frontend perspective — errors do not
affect the user experience. Never show errors to the athlete for telemetry
failures.

Access control: authenticated athlete only. The athlete_id comes from
the JWT, not the request body (prevent spoofing).

### 3. Frontend Hook

**New file: `apps/web/lib/hooks/usePageTracking.ts`**

A React hook that fires on every route change:

```typescript
import { useEffect, useRef } from 'react';
import { usePathname } from 'next/navigation';

const SCREEN_MAP: Record<string, string> = {
  '/home': 'home',
  '/calendar': 'calendar',
  '/manual': 'manual',
  '/coach': 'coach',
  '/progress': 'progress',
  '/analytics': 'analytics',
  '/training-load': 'training_load',
  '/nutrition': 'nutrition',
  '/settings': 'settings',
  '/fingerprint': 'fingerprint',
  '/trends': 'trends',
};

function resolveScreen(pathname: string): string {
  // Exact matches first
  if (SCREEN_MAP[pathname]) return SCREEN_MAP[pathname];
  // Dynamic routes
  if (pathname.startsWith('/activities/')) return 'activity_detail';
  if (pathname.startsWith('/plans/')) return 'plan_detail';
  if (pathname.startsWith('/tools/')) return 'tools';
  return pathname.replace(/^\//, '').replace(/\//g, '_') || 'home';
}
```

The hook:
1. On route change: resolve screen name from pathname
2. Call `POST /v1/telemetry/page-view` with screen + previous screen as referrer
3. Store the returned `page_view_id`
4. On next route change (or page unload): call `PATCH .../exit` for the previous view
5. Use `navigator.sendBeacon` for the exit call on page unload (reliable even when tab closes)

Wire the hook into the root layout (`apps/web/app/layout.tsx`) inside the
auth-protected wrapper so it fires on every page for logged-in athletes only.

### 4. Admin Query Endpoint

**`GET /v1/admin/telemetry/usage-report`**

Admin-only endpoint. Returns per-athlete usage summary for the last N days:

```json
{
  "athletes": [
    {
      "athlete_id": "...",
      "name": "Michael Shaffer",
      "total_sessions": 42,
      "total_page_views": 187,
      "most_visited": [
        {"screen": "home", "visits": 89, "avg_duration_s": 34},
        {"screen": "activity_detail", "visits": 52, "avg_duration_s": 48},
        {"screen": "calendar", "visits": 23, "avg_duration_s": 18}
      ],
      "entry_points": [
        {"screen": "home", "count": 38},
        {"screen": "calendar", "count": 4}
      ],
      "hourly_distribution": {
        "6": 12, "7": 18, "8": 5, "14": 3, "19": 4
      },
      "last_active": "2026-04-10T14:22:00Z"
    }
  ]
}
```

Query params: `?days=30` (default 30).

A "session" is defined as a sequence of page views with no gap > 30 minutes.
An "entry point" is the first screen in a session.

---

## Screen Name Registry

Use these exact names for consistency:

| Screen | Path | Name |
|--------|------|------|
| Home | `/home` | `home` |
| Calendar | `/calendar` | `calendar` |
| Activity Detail | `/activities/:id` | `activity_detail` |
| Coach | `/coach` | `coach` |
| Operating Manual | `/manual` | `manual` |
| Progress | `/progress` | `progress` |
| Analytics | `/analytics` | `analytics` |
| Training Load | `/training-load` | `training_load` |
| Nutrition | `/nutrition` | `nutrition` |
| Fingerprint | `/fingerprint` | `fingerprint` |
| Trends | `/trends` | `trends` |
| Settings | `/settings` | `settings` |
| Plan Create | `/plans/create` | `plan_create` |
| Tools | `/tools/*` | `tools` |
| Onboarding | `/onboarding` | `onboarding` |
| Discover | `/discover` | `discover` |

### Activity Detail metadata

When tracking `activity_detail`, include the activity_id in metadata:
```json
{"activity_id": "uuid-here"}
```

This lets us answer "which activities does the athlete actually look at?"
(e.g., do they only look at hard workouts? Do they review every run?)

---

## What This Does NOT Do

- No third-party analytics platform. No external data sharing.
- No tracking of unauthenticated users (marketing pages are excluded).
- No tracking of click positions, scroll depth, or mouse movement.
- No cookies. Authentication comes from the existing JWT.
- No impact on page load performance. The tracking call is async and
  fire-and-forget.
- No PII in the event data beyond the athlete_id (which is a UUID).

---

## Validation Criteria

- [ ] Page view events are recorded for every authenticated route change
- [ ] Exit events fire on navigation away (duration_seconds computed)
- [ ] Admin endpoint returns per-athlete usage summary
- [ ] Telemetry failures never produce visible errors for the athlete
- [ ] `sendBeacon` fires on tab close / page unload
- [ ] No telemetry fires for unauthenticated pages
- [ ] After 7 days of production data: founder can answer "which screen
      does each athlete visit most?" from the admin endpoint

---

## Why This Matters

Every screen priority in the native app spec is currently a guess. The
Operating Manual was assumed to be a daily destination — the founder
corrected this: it's periodic. The home page was assumed to be universal —
Adam uses the calendar instead. Without telemetry, we will design the
native app around assumptions and get the hierarchy wrong.

Four weeks of telemetry data from 6 active athletes will tell us:
1. Which 2-3 screens carry 80% of daily engagement
2. Whether the morning briefing drives app opens (time-of-day patterns)
3. Whether anyone uses Analytics, Training Load, or Trends regularly
4. Whether nutrition logging has adoption or is dead weight
5. What the actual daily session looks like per athlete type

This data directly informs the native app's default tab, navigation
hierarchy, pre-caching strategy, push notification content, and which
screens get the most design investment.
