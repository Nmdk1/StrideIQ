# ADR-041: Analytics Page Metric Interactivity

**Status:** Accepted  
**Date:** 2026-01-18  
**Author:** Opus 4.5 (Planner Architect)

---

## Context

The Analytics page displays two groups of advanced metrics without explanation or interactivity:

- **Efficiency Factor (EF)** summary cards: Current EF, 180d Avg, Best, Trend
- **Stability Metrics** section: Consistency Score, Easy Runs, Moderate Runs, Hard Runs

Current behavior:

- Cards are static — no hover state, no tooltip, no click action
- Users expect interaction when they see clickable-looking cards
- Most athletes don’t know what “Efficiency Factor” or “Consistency Score” measure
- These are StrideIQ-specific or advanced metrics not found in mainstream running apps

This creates a trust gap: the numbers appear authoritative but users can’t verify what they mean or how they’re calculated. Unlike standard metrics (pace, distance, heart rate), EF and Consistency Score require explanation.

From the N=1 manifesto:

> “No motivational fluff.”

But unexplained metrics aren’t the opposite of fluff — they’re noise. Data without context is not insight.

---

## Decision

Add interactive education to all Analytics page metric cards.

### EF Summary Cards (Current, Avg, Best, Trend)

- **Hover**: Show a tooltip explaining what EF measures (pace:HR ratio, higher = fitter).
- **Include brief context**: e.g., “Your EF of 15.17 means you’re running X:XX/mi at Y bpm average.”

### Stability Metrics Section

- **Hover on Consistency Score**: Explain calculation (training regularity, intensity distribution).
- **Hover on Easy/Moderate/Hard counts**: Explain the classification criteria.
- **Add section-level “What is this?” help icon** with fuller explanation (so users can learn without hovering every item).

### Visual affordance

- Add a subtle hover state to indicate interactivity.
- Use the consistent tooltip pattern established in ADR-039 (Training Load page).

---

## Considered Alternatives Rejected

**A. Add a separate “Glossary” or “Help” page**  
Rejected. Forces users to leave context. Inline explanation at point of confusion is better UX.

**B. Remove these metrics for non-power-users**  
Rejected. The metrics are valuable — the problem is presentation, not existence.

**C. Add permanent explanatory text below each metric**  
Rejected. Creates visual clutter. Tooltips provide explanation on-demand without cluttering the default view.

**D. Do nothing (assume users will learn)**  
Rejected. Unexplained metrics erode trust. Users assume broken or meaningless rather than investigating.

---

## Consequences

**Positive:**

- Users understand what they’re looking at
- Builds trust in StrideIQ’s intelligence layer
- Consistent interaction pattern across app (aligns with ADR-039)
- Reduces support questions about metric meanings

**Negative:**

- Requires tooltip content writing (educational copy)
- Slightly more complex card components
- Need to ensure tooltips don’t block other content on mobile

---

## Rationale

**N=1 Philosophy alignment:**

> “Your data calls the shots.”

For data to “call the shots,” athletes must understand it. An EF of 15.17 means nothing without context. Explaining that this is a pace:HR efficiency ratio — and that higher is better — transforms a number into actionable insight.

**Architecture alignment:**

- Analytics page is “Layer 3: Research Layer” per existing documentation
- Research layer serves “power users, coaches, and scientists” who expect metric transparency
- Tooltip pattern already established in Training Load page (ADR-039)

**Workflow alignment:**

- UI-only change (single page file)
- Follows ADR-039 pattern — similar scope and approach
- Does not touch core calculation logic

---

## Implementation Notes

**Scope:** UI-only. No changes to EF / stability metric calculations.

**Tooltip requirements:**

- **Consistency**: Reuse the tooltip UI pattern from the Training Load page (ADR-039).
- **Mobile**: Ensure content remains accessible on touch devices (e.g., tap-to-open popover, or help icon opens a bottom sheet).
- **Copy**: Prefer concrete, athlete-readable language (include units and an example interpretation) and avoid motivational language.

---

## Related ADRs

- ADR-039: Training Load Page Enhancement

