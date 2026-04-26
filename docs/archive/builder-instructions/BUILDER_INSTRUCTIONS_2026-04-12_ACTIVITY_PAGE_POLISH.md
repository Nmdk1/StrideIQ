# Builder Instructions — Activity Page & Daily Surfaces Polish

**Date:** April 12, 2026
**Priority:** URGENT — these are the surfaces every user sees every day
**Commissioned by:** Founder, via advisor

---

## Context

The founder and all active users interact with these surfaces daily:
1. Activity detail page (after every run)
2. Morning briefing / home page
3. Calendar

They do NOT use: Manual, Progress, Analytics, Training Load, Coachable Moments.

The founder already screenshots and shares the run shape canvas, splits, and morning briefing manually. The "what app is that?" moment from those screenshots is the real acquisition channel — not share cards, not Runtoon.

**The goal of this work is to make the daily surfaces look and work well enough that organic screenshots become the growth engine.**

---

## Mandatory Read Order

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` — Part 1 (the design principle)
3. `docs/RUN_SHAPE_VISION.md`
4. This document

---

## Workstream 1: Run Shape Canvas — Fix Sizing and Padding

**File:** `apps/web/components/activities/rsi/RunShapeCanvas.tsx`
**Current problem:** The canvas is 256px tall (`CHART_HEIGHT = 256`). The founder asked for the aspect ratio to be adjusted — instead of reducing the height of the square to make it more compact, a previous agent made it a wide rectangle with wrong padding. The result takes up too much vertical space on mobile while not using horizontal space well.

### What to fix

1. **Chart height on mobile vs desktop.** The canvas should fill the viewport width and use a height that creates a roughly 16:9 aspect ratio on mobile (not a square, not a tall rectangle). On desktop/tablet, it can be taller. Use a responsive approach:
   - Mobile (<768px): height ~200px for a wide, cinematic feel
   - Desktop (>=768px): height ~280px

2. **Padding/margins around the canvas.** Look at the container div with `className="relative overflow-hidden"` and `style={{ height: CHART_HEIGHT }}` at ~line 1227. There should be zero wasted space between the edge of the screen and the chart on mobile. The gradient effort line should go edge to edge.

3. **The chart must be the hero of the activity page.** It appears at position 4 in the page layout (after header, Garmin badge, map). On mobile, the runner should see the run shape within the first scroll. If the map pushes it below the fold, the map should be more compact or collapsible.

### What NOT to change

- Do not change the gradient effort coloring logic
- Do not change the LTTB downsampling
- Do not change the hover/crosshair interaction
- Do not change the segment overlay logic
- Do not break the splits/laps tab integration

### Evidence required

- Screenshots of the activity page on a 390px-wide viewport (iPhone 14 size) showing the run shape canvas above the fold or within first scroll
- Screenshots on 1440px desktop showing proper proportions
- `npx tsc --noEmit` exit 0

---

## Workstream 2: Fix the Map

**Files:** `apps/web/components/activities/map/RouteContext.tsx`, `apps/web/components/activities/map/ActivityMapInner.tsx`
**Current problem:** The map is "off" — it consistently doesn't render correctly. The founder says it's broken on most activities.

### What to investigate and fix

1. **Open the activity page on production** (`https://strideiq.run/activities/<id>`) for several activities. Document what "off" looks like — is the map blank? Wrong zoom? Wrong position? Tiles not loading? GPS track not rendering?

2. **Check the GPS track data.** The `gps_track` field is `[number, number][]`. Verify the coordinate order (lat/lng vs lng/lat) matches what Leaflet expects. A coordinate swap is the most common cause of maps being "off."

3. **Check the map container sizing.** On mobile, the map should be compact — wide and short (roughly 200px tall). It should NOT take up half the screen and push the run shape below the fold.

4. **If the map cannot be reliably fixed in this session,** make it collapsible (collapsed by default on mobile, with a "Show map" tap to expand). A broken map is worse than no map.

### Evidence required

- Screenshots showing the map rendering correctly on at least 3 different activities
- If collapsible: screenshot of collapsed and expanded states

---

## ~~Workstream 3: REVERTED — Runtoon stays live~~

**The Runtoon prompt stays enabled.** The original instruction to disable it was wrong.
Runtoon needs a creative quality upgrade (better prompts, better visual concepts), not suppression.
That work is out of scope for this doc. Do NOT touch Runtoon code.

---

## Workstream 4: Coach Intelligence Gap — Interval Session Detection

**Context:** The founder ran a 7.6-mile session that was a "busted 1200 interval session." The splits/laps data picked up the intervals perfectly. The coach (AI coach on the activity page and in the briefing) said nothing about it. This is an intelligence gap — the system has the data but the coach doesn't use it.

**This is a DISCUSSION item, not a build item.** The founder's operating contract says: discuss → scope → plan → test design → build. Do NOT start coding.

### What to investigate (research only)

1. **How does the coach get activity data?** Trace the flow from activity ingestion through to coach narration. Check `apps/api/services/ai_coach.py`, `apps/api/services/moment_narrator.py`, `apps/api/services/run_analysis_engine.py`.

2. **Does the interval detection feed into coach context?** The `interval_detector.py` or splits data clearly detected the intervals. Does that detection result get passed to the coach's prompt? Or is the coach generating commentary without knowing what kind of session it was?

3. **What did the coach actually receive as context for this activity?** If you can identify the activity in question (7.6mi, 8:21 pace, 129bpm, April 12, 2026, founder's account), check what the coach's prompt looked like.

4. **Report findings.** Do not build a fix. Report what you found: where the gap is, what data the coach is missing, and what would need to change. The founder will decide whether and how to fix it.

### Evidence required

- The call chain from activity → coach context, documented
- What data the coach received vs what it should have received
- A clear statement of the gap

---

## Workstream 5: Remove Phase 2 Share Cards from Manual

**Files:** `apps/web/app/manual/page.tsx`, `apps/web/components/manual/FindingShareModal.tsx`, `apps/web/components/manual/findingShareCanvas.ts`

The share cards shipped in Phase 2 are not meeting quality standards. The founder rejected them.

### What to do

1. **Remove all share buttons from the Manual page.** Remove the `Share2` icon imports, the `onShareClick` handlers, the `canShare*` functions, the `FindingShareModal` rendering, and the `shareTarget` state from `apps/web/app/manual/page.tsx`.

2. **Do NOT delete the component files** (`FindingShareModal.tsx`, `findingShareCanvas.ts`). They may be repurposed later. Just disconnect them from the Manual page.

3. **Remove `finding_share_initiated` and `finding_share_completed`** from the telemetry event type enum in `apps/web/lib/hooks/useToolTelemetry.ts` and the API validation in `apps/api/routers/telemetry.py`. Clean up the test file if those event types are tested.

### Evidence required

- The Manual page renders without share buttons
- TypeScript compiles clean
- No references to `FindingShareModal` remain in `page.tsx`

---

## Priority Order

1. ~~**Workstream 3** — REVERTED. Runtoon stays live.~~
2. **Workstream 5** (remove manual share buttons) — 15 minutes, remove rejected feature
3. **Workstream 1** (run shape canvas sizing) — the core visual fix
4. **Workstream 2** (map fix) — parallel with or after workstream 1
5. **Workstream 4** (coach gap investigation) — research only, report back

---

## Rules

- Scoped commits only. Never `git add -A`.
- Show evidence — screenshots, TypeScript compilation, git diff.
- Do NOT push until the founder says "push."
- CI must be green before reporting done.
- Do NOT touch plan generation, correlation engine, intelligence services, or any backend beyond the telemetry cleanup in workstream 5.
- When in doubt about visual decisions, take a screenshot and ask. Do not guess.
