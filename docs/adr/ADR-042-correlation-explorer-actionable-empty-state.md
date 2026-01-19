# ADR-042: Correlation Explorer Actionable Empty State

**Status:** Accepted  
**Date:** 2026-01-18  
**Author:** Opus 4.5 (Planner Architect)

---

## Context

The Correlation Explorer on the Analytics page displays this message when insufficient data exists:

> "Not enough data yet. Log more inputs (sleep, nutrition, stress) to discover patterns."

Current problems:

1. **Dead-end message**: Users are told to log data but given no way to do so
2. **Hidden logging features**: `/checkin` and `/nutrition` pages exist but are not in the main navigation
3. **No data requirements transparency**: Users don't know how much data is needed or what specifically to log
4. **Trust erosion**: A feature that permanently says "not enough data" with no actionable path feels broken

From the N=1 manifesto:

> "The more you log, the more we show you."

But this promise is hollow if the logging path is hidden.

---

## Decision

Transform the Correlation Explorer empty state from a dead-end into an actionable onboarding path.

### Empty State Enhancements

1. **Add direct action buttons**:
   - "Log Check-in" → links to `/checkin`
   - "Log Nutrition" → links to `/nutrition`
   
2. **Show data requirements**:
   - Display minimum thresholds (e.g., "~10 entries needed to surface meaningful correlations")

3. **Explanatory copy**:
   - "Log check-ins and nutrition to discover what habits correlate with your best runs."

### Visual Design

- Use the existing Card pattern with subtle call-to-action styling
- Buttons are secondary/outline style (not overwhelming)
- Keep the empty state concise — this is Layer 3 (Research), not onboarding

---

## Considered Alternatives Rejected

**A. Add check-in/nutrition to main navigation**  
Rejected for this ADR. That's a broader navigation architecture decision. This ADR focuses on making the empty state actionable.

**B. Remove the Correlation Explorer until user has data**  
Rejected. Hiding features until unlocked creates a worse discovery experience. Showing what's possible (with a path to unlock it) is better.

**C. Auto-prompt users to log on page load**  
Rejected. Intrusive. The empty state should guide, not nag.

**D. Link to generic "help" documentation**  
Rejected. Direct action beats documentation. Users should be one click from logging, not reading about logging.

---

## Consequences

**Positive:**

- Users have a clear path from "not enough data" to "here's how to get data"
- Increases check-in and nutrition logging (features that already exist but are underused)
- Builds trust by showing transparency about data requirements
- Consistent with N=1 philosophy: more logging → more insight

**Negative:**

- Slightly more complex empty state component
- If thresholds change, empty state copy may become stale

---

## Rationale

**N=1 Philosophy alignment:**

> "Your data calls the shots."

Users can't let their data call the shots if they don't know how to provide data. The current empty state is a broken promise — it names the data types (sleep, nutrition, stress) but hides the input mechanisms.

**Architecture alignment:**

- `/checkin` page exists and works — it just needs visibility
- `/nutrition` page exists and works — it just needs visibility
- Correlation Explorer already queries `correlationsService` — the backend is ready
- This is a frontend UX fix, not a backend change

**Workflow alignment:**

- UI-only change in `apps/web/app/analytics/page.tsx`
- Does not touch correlation calculation logic
- Follows ADR-041 pattern of making Analytics page more transparent and actionable

---

## Related ADRs

- ADR-041: Analytics Page Metric Interactivity
