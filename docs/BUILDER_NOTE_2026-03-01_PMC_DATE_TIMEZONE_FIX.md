# Builder Note — PMC Chart Date Axis Timezone Fix

**Date:** 2026-03-01  
**Assigned to:** Frontend Builder  
**Advisor sign-off required:** Yes  
**Urgency:** Medium (visible to founder daily, not blocking)

---

## Before Your First Tool Call

Read in order:
1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. This builder note

---

## Objective

All date labels on charts must display the correct calendar date. Currently, every chart that parses an ISO date string (`"2026-02-28"`) through JavaScript's `new Date()` and renders it with local-time methods shows dates shifted back by one day for US timezone users.

---

## Root Cause

The backend sends dates as ISO strings: `"2026-02-28"` (from Python `date.isoformat()`).

JavaScript's `new Date("2026-02-28")` creates a Date object at **midnight UTC** — `2026-02-28T00:00:00Z`.

But `.getMonth()`, `.getDate()`, and `.toLocaleDateString()` without an explicit `timeZone` option all return values in the **browser's local timezone**. For a user in US Eastern (UTC-5):

- Midnight UTC Feb 28 = 7:00 PM EST **Feb 27**
- `.getDate()` returns **27**, not 28
- `.toLocaleDateString()` returns **"Feb 27"**, not "Feb 28"

The graph curves are visually correct because Recharts plots data points in array order — only the labels are wrong.

---

## Scope — All Affected Files

### Primary target (founder's favorite chart):

**`apps/web/app/training-load/page.tsx`** — 4 locations:

1. **Line 216–219** — PMC chart x-axis `tickFormatter`:
   ```tsx
   tickFormatter={(value) => {
       const d = new Date(value);
       return `${d.getMonth() + 1}/${d.getDate()}`;
   }}
   ```
   Fix: use `d.getUTCMonth()` and `d.getUTCDate()`.

2. **Line 228–235** — PMC chart tooltip `labelFormatter`:
   ```tsx
   labelFormatter={(label) => {
       const d = new Date(label);
       return d.toLocaleDateString('en-US', {
           month: 'short',
           day: 'numeric',
           year: 'numeric'
       });
   }}
   ```
   Fix: add `timeZone: 'UTC'` to the options object.

3. **Line 303–306** — Daily TSS chart x-axis `tickFormatter`:
   Same pattern as #1. Same fix.

4. **Line 315–320** — Daily TSS chart tooltip `labelFormatter`:
   Same pattern as #2. Same fix.

### Secondary targets (same bug, same fix pattern):

5. **`apps/web/components/dashboard/LoadResponseChart.tsx`**
   - Line 51: `new Date(week.week_start).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })`
   - Line 164: same pattern with `year: 'numeric'`
   - Line 264: same pattern with `year: 'numeric'`
   - Fix: add `timeZone: 'UTC'` to all three.

6. **`apps/web/components/dashboard/AgeGradedChart.tsx`**
   - Line 33: `new Date(point.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })`
   - Fix: add `timeZone: 'UTC'`.

7. **`apps/web/components/dashboard/EfficiencyChart.tsx`**
   - Line 37: `new Date(point.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })`
   - Fix: add `timeZone: 'UTC'`.

### NOT affected (verified, no action needed):

- `RunShapeCanvas.tsx` — x-axis is elapsed time in seconds, not dates
- `SplitsChart.tsx` — x-axis is split number/pace, not dates
- `compare/` pages — x-axis is pace/distance, not dates
- `spike/rsi-rendering/` — x-axis is elapsed time, not dates

---

## Out of Scope

- Backend changes — the backend is correct (`date.isoformat()` returns the right date string)
- Calendar page — uses its own date handling (not Recharts `tickFormatter`)
- Creating a shared date utility — this is a 7-location fix, not a pattern that needs abstraction yet. If the codebase grows more date-axis charts, a utility can be extracted later.

---

## Implementation Notes

### The fix pattern is one of two forms:

**Form A** — for `tickFormatter` using `.getMonth()` / `.getDate()`:
```tsx
// Before (broken):
const d = new Date(value);
return `${d.getMonth() + 1}/${d.getDate()}`;

// After (fixed):
const d = new Date(value);
return `${d.getUTCMonth() + 1}/${d.getUTCDate()}`;
```

**Form B** — for `toLocaleDateString()`:
```tsx
// Before (broken):
new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })

// After (fixed):
new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })
```

### Guardrails:
- Do NOT change the backend date format
- Do NOT introduce moment.js, date-fns, or any new dependency for this
- Do NOT refactor the chart components beyond the date fix
- Verify the fix with the browser set to a US timezone (the bug is invisible in UTC+0 and east-of-UTC timezones)

---

## Tests Required

### Unit tests:
No new unit tests needed — this is a display formatting fix with no logic changes.

### Manual verification (required):
For each of the 4 charts (PMC, Daily TSS, Efficiency, Age-Graded, Load-Response):
1. Set browser timezone to US Eastern (or verify on founder's machine)
2. Load the chart
3. Confirm the rightmost date label matches today's actual date
4. Hover over the last data point — tooltip date must match today's actual date

### Regression check:
- `npm run build` must complete with zero errors
- Existing frontend tests must pass: `npm test`

Paste command output in handoff.

---

## Evidence Required in Handoff

1. Scoped file list changed (should be exactly 4 files, ~10 lines changed total).
2. `npm run build` output (zero errors).
3. `npm test` output (all passing).
4. **Before/after screenshots of the PMC chart** — same data, browser in US/Eastern. The rightmost x-axis date must shift forward by one day after the fix. This is the primary acceptance evidence.
5. **Before/after screenshot of one additional chart** (Efficiency or Load-Response) — same timezone check. Confirms the fix is systematic, not just the PMC.
6. Advisor will not sign off without screenshot evidence for items 4 and 5.

---

## Acceptance Criteria

- The PMC chart x-axis shows today's correct date as the rightmost label (not yesterday)
- The PMC chart tooltip shows the correct date when hovering over any data point
- The Daily TSS chart x-axis and tooltip show correct dates
- The Efficiency chart, Age-Graded chart, and Load-Response chart all show correct dates
- **Timezone parity check:** With browser set to `US/Eastern`, then switched to `UTC`, the same data point renders the same calendar date on all 4 charts. This is the definitive proof the fix works — if the date shifts between timezones, the bug is not fixed.
- No new dependencies introduced
- `npm run build` clean, `npm test` green

---

## Mandatory: Site Audit Update

`docs/SITE_AUDIT_LIVING.md` must be updated in the same session:

1. Move to Resolved Issues: "Chart date labels shifted by one day in US timezones"
2. Note: "All Recharts date axes now use UTC methods to prevent local-timezone date shift"

No task is complete until this is done.
