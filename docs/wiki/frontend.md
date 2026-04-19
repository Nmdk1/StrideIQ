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

Sport-specific components: `CyclingDetail`, `StrengthDetail`, `HikingDetail`, `FlexibilityDetail`.

**Run activity page (rebuilt April 2026):**

- **Hero:** `components/canvas-v2/CanvasV2.tsx` rendered with `chromeless`
  prop. Real Mapbox GL 3D terrain (`TerrainMap3D.tsx`), three-layer route
  (white casing + emerald glow + deep emerald line), navigation controls,
  fullscreen toggle, distance hover card. Stacked 2D charts (HR / pace /
  elevation) under the map share a `StreamHoverContext` so hovering a chart
  drives the map dot, the moment-readout cards, and the elevation
  highlight in lockstep. Pace chart uses **Tukey's fence (IQR, k=3.0)** for
  outlier clipping (`robustDomain` in `StreamsStack.tsx`) — replaces the
  earlier percentile clip that flattened pace.
- **Three tabs (down from six):**
  - `Splits` — splits/laps table only, no map (the hero already has it).
  - `Coach` — absorbs `RunIntelligence`, `FindingsCards`, `WhyThisRun`,
    `GoingInCard`, `AnalysisTabPanel`, and `activity.narrative`. The
    Compare tab remains visible as an "urgent reminder to get it done"
    flagged for redesign behind the canvas vocabulary (see
    `docs/specs/COMPARE_REDESIGN.md`).
  - `Compare` — placeholder; redesign sequenced behind the canvas.
- **Page chrome pills (right of title, run-only):**
  - `ReflectPill` (`components/activities/feedback/`) — opens the
    `FeedbackModal`. Pill state reflects completion of reflection / RPE /
    workout-type confirmation, sourced from `useFeedbackCompletion`.
  - `ShareButton` (`components/activities/share/`) — opens the
    `ShareDrawer`, which hosts the `RuntoonCard` plus a roadmap placeholder
    for future share styles (photo overlays, customizable stats, modern
    backgrounds, flyovers). The runtoon is no longer rendered at page
    bottom; sharing is now a pull action.
- **`FeedbackModal`** is **unskippable** (no X, Cancel, Skip, or backdrop
  dismiss) and auto-opens on first visit to a recent, incomplete run via
  `useFeedbackTrigger` (gated on a `localStorage` flag so it only auto-opens
  once per activity). Edits remain available via the `ReflectPill` after
  the first save. Auto-classified workout types require explicit "Looks
  right" confirmation before Save & Close enables — `workoutTypeAcked` is
  only pre-true when `existingWorkoutType.is_user_override` is true.

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
| `components/activities/` | Activity cards, splits, sport-specific detail panels, narrative; `feedback/` (FeedbackModal, ReflectPill, useFeedbackCompletion, useFeedbackTrigger), `share/` (ShareButton, ShareDrawer) |
| `components/canvas-v2/` | CanvasV2 (hero), TerrainMap3D (Mapbox GL), StreamsStack (HR/pace/elevation, Tukey fence outlier clip), CanvasHelpButton, distance hover card |
| `components/calendar/` | Day cells, week rows, `DayDetailPanel.tsx` (edit + swap) |
| `components/progress/` | Hero, sparklines, correlation web, recovery fingerprint |
| `components/coach/` | `ProposalCard.tsx` |
| `components/runtoon/` | Runtoon card view (rendered inside ShareDrawer). `RuntoonSharePrompt.tsx` is preserved on disk but **no longer mounted in `app/layout.tsx`** — sharing is a pull action via the activity-page Share button. |
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

- **`StreamHoverContext`:** Links CanvasV2's TerrainMap3D, StreamsStack charts (HR / pace / elevation), and the moment-readout cards through hover. When you hover any chart or scrub the map, the dot moves on the terrain, the elevation highlight updates, and the readout cards (including the distance hover card) recompute in lockstep.
- **`useUnits()` hook:** Metric/imperial unit conversion throughout the app
- **i18n:** `lib/i18n/` with `en.ts`, `es.ts`, `ja.ts` translations
- **`DayDetailPanel.tsx`:** Unified save action — swap + edit consolidated into single button (fixed Apr 7, 2026)
- **`usePageTracking()` hook:** Wired in `ClientShell.tsx`, fires on every authenticated route change. Posts page entry, patches exit on navigation or tab close via `sendBeacon`/`fetch` with `keepalive`. See [telemetry.md](./telemetry.md).
- **Caddy CSP for Mapbox:** Mapbox tile/style/sprite domains are allowed in `connect-src` and `worker-src`/`child-src` (`blob:`) in the production `Caddyfile`. CSP changes require a Caddy container restart, not just `caddy reload`, due to a Docker bind-mount caching artefact on Linux.

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
