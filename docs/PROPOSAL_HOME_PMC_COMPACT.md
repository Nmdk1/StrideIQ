# Proposal — Compact PMC Chart on Home Page

**Date:** 2026-03-01  
**Author:** Advisor  
**Status:** APPROVED (2026-03-01) — Codex reviewed, founder approved. Builder note: `docs/BUILDER_NOTE_2026-03-01_HOME_PMC_COMPACT.md`  
**Scope:** Frontend only (new component + home page integration)

---

## Problem

The founder's favorite chart — the Performance Management Chart (Fitness/Fatigue/Form) — is buried behind More → Training Load. It requires 2-3 taps to reach. The founder checks it daily to read the shape of their training at a glance. High-value, low-discoverability.

## Solution

Add a compact, tappable PMC chart to the home page. Same data, smaller footprint, click-through to the full Training Load page for the deep dive. Follows the same pattern as LastRunHero (mini pace chart on home → tap → full activity detail).

---

## Design

### Visual Treatment

- **Height:** ~160-180px (roughly half the full page's 320px chart)
- **Width:** Full container width (matches other home sections)
- **Period:** Fixed 30 days — enough to show the recent trend shape without compressing detail
- **Lines:** All three — Fitness (blue), Fatigue (orange), Form (green area fill)
- **Grid:** Subtle, same as full chart (`#374151` dashed)
- **Background:** `bg-slate-800/50` with `border-slate-700/50` — matches This Week card treatment
- **X-axis:** Date ticks (M/D format, UTC-safe — use the fix from `a4a96d3`)
- **Y-axis:** Minimal — show scale but no label
- **No dots** on data points — clean lines only (same as full chart)

### What IS included:

- The three data lines + TSB area fill
- Recharts Legend with human-readable names: "Fitness (CTL)", "Fatigue (ATL)", "Form (TSB)"
- Section header: small label like "Training Load" with an activity/trending icon, consistent with "This Week" header style
- Click/tap anywhere on the component navigates to `/training-load`
- Small arrow indicator (ArrowRight icon, same as LastRunHero) to signal tappability

### What is NOT included:

- No metric cards (CTL: 42, ATL: 58, etc.) — the shape tells the story, numbers are for the deep dive
- No period selector — fixed 30 days
- No daily TSS chart — that's a deep dive concern
- No personal zones section
- No education ribbon — tooltips handle the explanation
- No zero reference line (keeps the compact version clean; full page retains it)

### Legend Tooltips (on hover/tap):

Each legend item gets a tooltip on hover (desktop) or tap (mobile):
- **Fitness (CTL):** "42-day average of training stress. Higher = more accumulated fitness."
- **Fatigue (ATL):** "7-day average of training stress. Higher = more recent fatigue."
- **Form (TSB):** "Fitness minus Fatigue. Positive = fresh. Negative = fatigued but building."

These are one-sentence distillations of the full education section. No acronym goes unexplained.

---

## Home Page Placement

Current layout:

```
1. Header (date + Coach button)
2. LastRunHero (mini pace chart — above the fold)
3. Morning Voice + Coach Noticed
4. Today's Workout
--- below the fold ---
5. Check-in
6. This Week card
7. Race Countdown
```

Proposed layout:

```
1. Header (date + Coach button)
2. LastRunHero (mini pace chart — above the fold)
3. Morning Voice + Coach Noticed
4. Today's Workout
--- below the fold ---
5. Check-in
6. This Week card
7. **Compact PMC** ← NEW
8. Race Countdown
```

**Rationale for position:** After This Week (the micro view of your current week) and before Race Countdown (the macro view of your goal). The PMC is the meso view — the shape of the last month. The hierarchy flows: today → this week → this month → the race.

**Alternative considered:** Placing it above This Week. Rejected because the founder's morning flow is: see the workout, check in, see the week. The PMC is "where am I in the build" — a reflection question that comes after the immediate context is established.

---

## Data Fetching

### Approach: Independent query, not bolted onto `/v1/home`

The home API endpoint (`/v1/home`) is already a complex aggregation (workout, week, check-in, briefing, last run) with a Celery cache layer and LLM briefing. Adding training load history would bloat it and couple chart data to the briefing cache lifecycle.

Instead, the compact PMC component fetches its own data from the existing endpoint:

```
GET /v1/training-load/history?days=30
```

This endpoint already exists, returns exactly the data needed, and is Redis-cached (5-minute TTL on the training load calculation). No backend changes required.

### TanStack Query configuration:

```tsx
useQuery({
  queryKey: ['training-load', 30],
  queryFn: () => fetch(`/v1/training-load/history?days=30`, ...),
  staleTime: 5 * 60 * 1000,  // 5 minutes (matches backend cache)
  enabled: !!token,
});
```

This means:
- If the user has already visited `/training-load` with a 30-day window, the data is already cached — zero additional fetch
- If they visit `/training-load` after seeing the home compact version, the 30-day window is pre-warmed
- The full training load page and home compact PMC share the same query key for 30 days — cache coherent

### Conditional rendering:

If the query returns no data (new user, no activities), the component renders nothing — no skeleton, no "no data" card. Same principle as LastRunHero: silent absence.

---

## Component Architecture

### New file: `apps/web/components/home/CompactPMC.tsx`

Self-contained component. Handles its own data fetch, loading state (renders nothing while loading), and click-through navigation.

```
Props: none (fetches its own data, auth from context)
```

### Modified file: `apps/web/app/home/page.tsx`

Import `CompactPMC` and place it between This Week and Race Countdown (~2 lines of JSX).

### No backend changes.

### No changes to the full Training Load page.

---

## Interaction Model

| Action | Result |
|--------|--------|
| View | Chart renders with 30-day PMC lines. Legend identifies each line. |
| Hover on legend item (desktop) | Tooltip with one-sentence explanation |
| Tap legend item (mobile) | Same tooltip behavior |
| Hover on chart data point (desktop) | Recharts tooltip: date + Fitness/Fatigue/Form values |
| Tap/click on chart body (not legend) | Navigate to `/training-load` |
| Tap "View training load →" in header | Navigate to `/training-load` |

**Note:** The entire card is NOT a single click target. The header CTA and chart body are clickable; the legend area is excluded to prevent tap conflicts with tooltips on mobile.

---

## What This Does NOT Change

- The full Training Load page stays exactly as-is (all features, period selector, zones, education)
- The home page layout above the fold is untouched
- No tab restructuring
- No Progress page changes
- No backend changes
- No new API endpoints

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Extra API call on home load | Existing endpoint, 5-min Redis cache, ~50ms response. If user visited training-load recently, data is pre-warmed. |
| Chart rendering performance on mobile | Recharts is already used on home (LastRunHero mini chart). 30 data points is trivial. |
| Click target conflicts (chart hover vs tap-to-navigate) | LastRunHero solves this same problem — the entire card is a Link wrapper, hover tooltips work within. Same pattern. |
| Cluttering the home page | The chart is below the fold, after the weekly context. It adds visual information, not text. If it feels crowded, it can be feature-flagged and A/B tested. |

---

## Acceptance Criteria

1. Compact PMC chart renders on home page below This Week, above Race Countdown
2. Shows Fitness (blue), Fatigue (orange), Form (green) lines for the last 30 days
3. Legend items show human-readable names with tooltips explaining each metric
4. Tapping the chart navigates to `/training-load`
5. Chart uses UTC-safe date formatting (same fix pattern from `a4a96d3`)
6. Component renders nothing when no training data exists (no skeleton, no empty state)
7. `npm run build` clean, `npm test` green
8. No backend changes, no new API endpoints
9. Visual evidence: screenshot of the home page with the compact PMC visible, in a US timezone browser

---

## Resolved Questions (Codex Review — 2026-03-01)

1. **Shared Recharts config: No.** Keep `CompactPMC` self-contained. Extract only tiny shared helpers (UTC date formatter + color tokens) if needed. Full config sharing over-couples compact and full charts that intentionally differ.

2. **Feature flag: No.** Ship directly. Additive, below the fold, no backend change, existing endpoint/cache. Flagging adds process overhead for low risk.

3. **Empty state (<7 days data): Don't render.** Silence. No "need more data" noise on home.

4. **Interaction tweak (Codex addition): Don't make the entire card clickable.** Legend tooltips and chart hover need their own tap targets on mobile. Instead, use a clear "View training load →" CTA link in the section header. The chart body can be clickable, but the legend area must be excluded to avoid tap conflicts.
