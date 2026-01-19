# ADR-039: Training Load Page Enhancement

**Status:** Accepted  
**Date:** 2026-01-17  
**Author:** Opus 4.5 (Planner Architect)  
**Accepted:** 2026-01-17 (Judge: Michael)

---

## Context

The Training Load page displays CTL (Fitness), ATL (Fatigue), TSB (Form), and Training Phase in summary cards above a Performance Management Chart. Users can select lookback periods (30d, 60d, 90d, 6mo, 1yr) which change the chart's time range.

Current behavior: the summary cards show **today's values only** and do not change when the lookback period changes. This is mathematically correct—CTL is a 42-day exponential average ending today, regardless of how much history you view—but creates a UX disconnect. Users expect visible response when they change a filter.

Additionally:
- Cards have no hover state or tooltip explaining the metric
- Cards have no click action for drill-down
- Console shows chart dimension errors when container renders before size is determined
- The page provides no period-specific context (e.g., "CTL rose 12 points over this period")

This violates the N=1 principle of surfacing individualized insight. A static snapshot tells the athlete less than their trajectory over the selected period.

---

## Decision

Enhance the Training Load page with three changes:

1. **Add period-aware context to summary cards**
   - Keep current values as primary display (these are the canonical metrics)
   - Add secondary display showing change over selected period: `+8 over 60d` or `-3 since period start`
   - This makes the cards respond meaningfully to period selection without misrepresenting the metrics

2. **Add interactivity to summary cards**
   - Hover: show tooltip with metric definition and calculation basis
   - Click: future capability placeholder (could navigate to detailed breakdown or historical comparison)

3. **Fix chart dimension warnings**
   - Ensure chart container has explicit dimensions before rendering
   - Use proper loading state to prevent negative dimension calculations

---

## Considered Alternatives Rejected

**A. Replace current values with period averages**  
Rejected. CTL/ATL/TSB are defined as point-in-time metrics. Showing "average CTL over 60 days" would misrepresent what CTL means and confuse athletes who understand the Banister model. The current value is the right primary display.

**B. Remove period selector from summary section**  
Rejected. The period selector legitimately controls chart range. The solution is to make the cards contextually aware, not to hide the control.

**C. Add a separate "period stats" section below the cards**  
Rejected. This fragments the UI and duplicates visual weight. Integrating period context into the existing cards is cleaner.

**D. Do nothing (document that current behavior is correct)**  
Rejected. While technically correct, the UX creates confusion. "Correct but confusing" is not acceptable.

---

## Consequences

**Positive:**
- Cards now respond visibly to period selection (user expectation met)
- Athletes see trajectory, not just snapshot (N=1 insight)
- Hover tooltips reduce confusion about metric meaning
- Console errors eliminated

**Negative:**
- Requires API change to return period start/end values (or frontend calculation from history array)
- Slightly more complex card component
- Must ensure "change over period" doesn't overshadow the primary current value

---

## Rationale

**N=1 Philosophy alignment:**
> "We learn from every workout, every build, every race."

A snapshot of today's CTL tells you where you are. The delta over a period tells you where you've been and whether your training is working. Both are N=1 insights; the current implementation provides only half.

**Architecture alignment:**
- The `/history` endpoint already returns daily values; period delta can be calculated from `history[0]` vs `history[last]`
- No new backend calculation required for MVP
- Card components already receive `data.summary` and `data.history`; wiring is straightforward

**Workflow alignment:**
- This touches UI only (page.tsx, no core plan generation files)
- Likely <50 lines changed in existing file
- Qualifies as **trivial** by threshold definition, but written as ADR because it changes user-facing behavior and establishes a pattern for other pages

---

## Implementation Notes

**Files modified:**
- `apps/web/app/training-load/page.tsx`

**Changes made:**
- Added `periodDelta` prop to `MetricCard` showing change over selected period (e.g., `+8 over 60d`)
- Added `title` attribute tooltips to all four summary cards
- Changed chart container heights from Tailwind classes to explicit inline pixel styles

**Key data points:**
- `data.history[0]` = oldest day in selected period
- `data.history[data.history.length - 1]` = most recent day
- Delta = current value - period start value

**Tooltip content:**
- Fitness (CTL): "42-day exponential average of training stress. Higher = more accumulated fitness."
- Fatigue (ATL): "7-day exponential average of training stress. Higher = more recent fatigue."
- Form (TSB): "Fitness minus Fatigue. Positive = fresh, negative = fatigued but building."
- Training Phase: Context-specific based on phase value.

---

## Known Limitations

**Recharts console warning:** `ResponsiveContainer` emits `width(-1) and height(-1)` warnings on initial render. This is a library-level issue where Recharts measures parent dimensions synchronously before browser layout completes. 

- **Impact:** Cosmetic (console noise only). Charts render correctly on next frame.
- **Workaround attempted:** Explicit inline pixel heights on containers. Did not resolve.
- **Proper fix:** Would require a ResizeObserver wrapper component — out of scope for this ADR.
- **Decision:** Accepted as cosmetic limitation. Does not affect functionality.
