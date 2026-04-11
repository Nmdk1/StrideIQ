# Frontend

## Current State

Next.js 14 App Router. React 18. TanStack Query for data fetching. Tailwind CSS. Deployed behind Caddy reverse proxy.

## Key Routes

### Primary Navigation

| Route | Page | Status |
|-------|------|--------|
| `/home` | Home — morning briefing, PMC, wellness, recent activity | Primary |
| `/manual` | Personal Operating Manual V2 | Primary |
| `/calendar` | Training calendar with plan, variant dropdown | Primary |
| `/coach` | AI coach chat | Primary |
| `/activities` | Activity list (all sports, chronological) | Primary |
| `/analytics` | Analytics (absorbed trends) | Primary |
| `/training-load` | PMC chart, TSS breakdown | Primary |
| `/progress` | Progress page — correlation web, hero | Primary |
| `/settings` | Settings (absorbed profile) | Primary |

### Activity Detail

| Route | Purpose |
|-------|---------|
| `/activities/[id]` | Activity detail — branches on `sport` field |

Sport-specific components: `CyclingDetail`, `StrengthDetail`, `HikingDetail`, `FlexibilityDetail`. Run uses existing RunShapeCanvas.

### Other Active Routes

| Route | Purpose |
|-------|---------|
| `/nutrition` | Nutrition tracking — Log (input + edit + delete), History, Insights tabs |
| `/reports` | Unified reports — health, activities, nutrition, body comp in configurable date ranges |
| `/checkin` | Daily check-in (redirects to `/home` after) |
| `/plans/create` | Plan wizard (absorbed availability). Constraint-aware endpoint accepts `engine=v2` query param (admin/owner only) to use V2 plan engine. |
| `/plans/[id]` | Plan detail |
| `/plans/preview` | Plan preview before purchase |
| `/plans/checkout` | Stripe checkout |
| `/compare/context/[activityId]` | Contextual comparison hub |
| `/personal-bests` | Personal bests |
| `/onboarding` | New athlete onboarding flow |
| `/admin` | Admin panel |
| `/tools/*` | Public SEO tools (age grading, race equivalency, etc.) |

### Deprecated/Deleted Routes

| Route | Status |
|-------|--------|
| `/dashboard` | Deleted |
| `/home-preview` | Deleted |
| `/spike/rsi-rendering` | Deleted |
| `/diagnostic` | Deleted (admin-only diagnostic remains) |
| `/insights` | Redirects to `/manual` |
| `/discovery` | Redirects to `/manual` |
| `/trends` | Absorbed into `/analytics` |
| `/profile` | Absorbed into `/settings` |
| `/availability` | Absorbed into `/plans/create` |

## Component Architecture

### Key Directories

| Directory | Contents |
|-----------|----------|
| `components/home/` | Hero, PMC compact, signals, banners |
| `components/activities/` | Activity cards, maps, RSI canvas, splits, cross-training detail |
| `components/calendar/` | Day cells, week rows, `DayDetailPanel.tsx` (edit + swap) |
| `components/progress/` | Hero, sparklines, correlation web, recovery fingerprint |
| `components/coach/` | `ProposalCard.tsx` |
| `components/runtoon/` | Share prompt and view |
| `components/ui/` | Shared primitives (button, dialog, card, badge, spinner) |
| `components/nutrition/` | Barcode scanner, fueling shelf, NL input, nutrition goal setup |

### Data Layer

| Layer | Location |
|-------|----------|
| **API client** | `lib/api/client.ts` — HTTP client with auth |
| **Service modules** | `lib/api/services/*.ts` — typed API calls per domain (nutrition, reports, etc.) |
| **React Query hooks** | `lib/hooks/queries/*.ts` — TanStack Query hooks per domain |
| **Standalone hooks** | `lib/hooks/usePageTracking.ts` — usage telemetry (fires on every route change) |
| **Contexts** | `lib/context/` — `AuthContext`, `StreamHoverContext`, `UnitsContext`, `CompareContext`, `ConsentContext` |
| **Feature flags** | `lib/featureFlags.ts` |

### Key Patterns

- **`StreamHoverContext`:** Links RunShapeCanvas, elevation profile, and map through hover. When you hover on the canvas, the dot moves on the map and the elevation profile highlights.
- **`useUnits()` hook:** Metric/imperial unit conversion throughout the app
- **i18n:** `lib/i18n/` with `en.ts`, `es.ts`, `ja.ts` translations
- **`DayDetailPanel.tsx`:** Unified save action — swap + edit consolidated into single button (fixed Apr 7, 2026)
- **`usePageTracking()` hook:** Wired in `ClientShell.tsx`, fires on every authenticated route change. Posts page entry, patches exit on navigation or tab close via `sendBeacon`/`fetch` with `keepalive`. See [telemetry.md](./telemetry.md).

## Key Decisions

- **App Router:** Next.js 14 file-based routing
- **TanStack Query:** All API data fetched via React Query hooks, not manual fetch
- **Tailwind:** Utility-first CSS, no CSS modules
- **No separate mobile app:** Mobile-responsive web app only (native app spec in progress)
- **Inline entry editing:** Nutrition log entries support tap-to-edit and delete directly in the Log tab

## Known Issues

- **Mobile experience:** Athletes at the founder's 10K race will open on phones. Mobile responsiveness is critical and needs a polish pass.
- **Empty states:** New athletes with no data may see empty cards/sections. Onboarding flow exists but cold-start UX needs attention.

## Sources

- `apps/web/app/` — all route pages
- `apps/web/components/` — UI components
- `apps/web/lib/` — data layer, hooks, utils
- `apps/web/package.json` — dependencies
- `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` — page-level design guidance
- `docs/SITE_AUDIT_LIVING.md` §6 — route inventory
