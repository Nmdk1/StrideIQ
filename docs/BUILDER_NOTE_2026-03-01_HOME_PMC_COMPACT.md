# Builder Note — Compact PMC Chart on Home Page

**Date:** 2026-03-01  
**Assigned to:** Frontend Builder  
**Advisor sign-off required:** Yes  
**Urgency:** Medium (UX improvement, not blocking)

---

## Before Your First Tool Call

Read in order:
1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/PROPOSAL_HOME_PMC_COMPACT.md` — the full design proposal with rationale
3. This builder note

---

## Objective

The founder's favorite chart (Performance Management Chart — Fitness/Fatigue/Form) is buried behind More → Training Load. Add a compact, tappable version to the home page so the shape of the last 30 days of training is visible daily without extra navigation.

---

## Scope

### New file: `apps/web/components/home/CompactPMC.tsx`

Self-contained component. Fetches its own data, handles loading/empty states, renders the chart.

**Data fetch:**
```tsx
GET /v1/training-load/history?days=30
```
This endpoint already exists. No backend changes. Use TanStack Query:
```tsx
useQuery({
  queryKey: ['training-load', 30],
  queryFn: ...,
  staleTime: 5 * 60 * 1000,
  enabled: !!token,
});
```
Cache key matches the full Training Load page when set to 30 days — cache coherent.

**Rendering rules:**
- If query is loading: render nothing (no skeleton, no spinner)
- If no data or empty history: render nothing (silence > noise)
- If data exists: render the chart

**Chart specs:**
- Height: ~160-180px
- Width: full container
- Period: fixed 30 days (no selector)
- Lines: Fitness (CTL) `#3B82F6`, Fatigue (ATL) `#F97316`, Form (TSB) `#10B981`
- TSB area fill: `#10B981` at 0.2 opacity
- Grid: `#374151` dashed (same as full chart)
- Background: `bg-slate-800/50` with `border-slate-700/50`
- X-axis: date ticks in M/D format, **must use UTC methods** (`getUTCMonth()`, `getUTCDate()`) — same fix pattern from commit `a4a96d3`
- Y-axis: show scale, no label
- No dots on data points
- No zero reference line (keep compact version clean)
- `ComposedChart` from Recharts (same as full page)

**Legend:**
- Recharts Legend with human-readable names: "Fitness (CTL)", "Fatigue (ATL)", "Form (TSB)"
- Each legend item has a tooltip on hover/tap:
  - Fitness: "42-day average of training stress. Higher = more accumulated fitness."
  - Fatigue: "7-day average of training stress. Higher = more recent fatigue."
  - Form: "Fitness minus Fatigue. Positive = fresh. Negative = fatigued but building."
- Use the existing `Tooltip`/`TooltipTrigger`/`TooltipContent` components from `@/components/ui/tooltip` for legend tooltips (wrap each legend entry)

**Section header:**
- Small label: icon + "Training Load" (same style as "This Week" header in the home page)
- Right side: "View training load →" link navigating to `/training-load`
- Use `TrendingUp` or `Activity` icon from lucide-react

**Click/tap behavior (critical — Codex review item):**
- The header CTA ("View training load →") navigates to `/training-load`
- The chart body (the Recharts area) is wrapped in a clickable element that navigates to `/training-load`
- The legend area is **excluded** from the click target — legend tooltips must work independently on mobile without triggering navigation
- Do NOT wrap the entire card in a single `<Link>`. Separate the click targets.

### Modified file: `apps/web/app/home/page.tsx`

Import `CompactPMC` and place it between This Week and Race Countdown.

Current layout (lines ~555-686):
```
This Week card (line 556-673)
Race Countdown (line 675-686)
```

Insert between them:
```tsx
{/* Training Load — compact PMC */}
<CompactPMC />

{/* Race Countdown */}
```

This is ~2 lines of JSX in the home page file.

---

## Out of Scope

- No backend changes
- No new API endpoints
- No changes to the full Training Load page (`/training-load`)
- No shared Recharts config extraction (keep CompactPMC self-contained)
- No feature flag (ship directly — additive, below fold, low risk)
- No metric cards (CTL: 42, etc.) on the compact version
- No period selector on the compact version
- No daily TSS chart on the compact version
- No personal zones section on the compact version
- No education ribbon on the compact version

---

## What NOT To Do

- Do NOT modify the full Training Load page
- Do NOT add training load data to the `/v1/home` API endpoint
- Do NOT make the entire card a single click target (mobile tap conflicts with legend tooltips)
- Do NOT show a skeleton/spinner/empty state — if no data, render nothing
- Do NOT use local-time date methods — all date formatting must use UTC (see commit `a4a96d3`)
- Do NOT introduce new dependencies

---

## Tests Required

### Manual verification (required):

1. Home page loads with the compact PMC visible below This Week
2. Chart shows three lines (blue Fitness, orange Fatigue, green Form area) for 30 days
3. Legend items display with human-readable names
4. Hovering/tapping a legend item shows the tooltip explanation
5. Hovering over a chart data point shows date + values tooltip
6. Tapping "View training load →" navigates to `/training-load`
7. Tapping the chart body navigates to `/training-load`
8. Tapping a legend item does NOT trigger navigation
9. New user with no data: compact PMC does not render (no empty state noise)
10. Date labels use correct calendar dates (UTC-safe — no off-by-one in US timezones)

### Build verification:
- `npm run build` must complete with zero errors
- `npm test` must pass (all existing tests green)

Paste command output in handoff.

---

## Evidence Required in Handoff

1. Scoped file list changed (should be 2 files: new `CompactPMC.tsx` + modified `home/page.tsx`)
2. `npm run build` output (zero errors)
3. `npm test` output (all passing)
4. **Screenshot of the home page** with the compact PMC visible, captured in a US timezone browser. Must show:
   - The three chart lines with correct colors
   - Legend with "Fitness (CTL)", "Fatigue (ATL)", "Form (TSB)"
   - "View training load →" CTA in the header
   - Correct date on the rightmost x-axis label (today's date, not yesterday)
5. **Screenshot showing legend tooltip** — hover/tap on a legend item showing the explanation text
6. Advisor will not sign off without screenshot evidence for items 4 and 5.

---

## Acceptance Criteria

- Compact PMC chart renders on home page below This Week, above Race Countdown
- Shows Fitness (blue), Fatigue (orange), Form (green) lines for the last 30 days
- Legend items show human-readable names with tooltips explaining each metric
- Header CTA "View training load →" navigates to `/training-load`
- Chart body tap navigates to `/training-load`
- Legend taps do NOT trigger navigation (tooltips work independently)
- Component renders nothing when no training data exists
- Chart uses UTC-safe date formatting
- No new dependencies, no backend changes
- `npm run build` clean, `npm test` green

---

## Mandatory: Site Audit Update

`docs/SITE_AUDIT_LIVING.md` must be updated in the same session:

1. Update Home page description in Section 6 (Frontend Architecture) to note compact PMC presence
2. Add to Section 0 (Delta): "Compact PMC chart added to home page — 30-day training load visible without navigating to Training Load page"

No task is complete until this is done.
