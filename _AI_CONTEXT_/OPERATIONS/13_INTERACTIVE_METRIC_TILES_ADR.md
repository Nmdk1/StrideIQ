# ADR 13: Interactive Metric Tiles

**Status:** Proposed  
**Date:** 2026-01-11  
**Decision:** Make metric tiles on contextual comparison page interactive with drill-down

---

## Context

The contextual comparison page displays performance metrics in card/tile format:
- Running Efficiency
- Cardiac Drift
- Aerobic Decoupling
- Pace Consistency

**Problem:** Users expect tiles to be interactive (clickable/expandable) based on visual affordance, but nothing happens on click. This creates a subconscious UX disappointment.

---

## Decision

Make each metric tile interactive. On click, expand to show:

| Metric | Expanded Content |
|--------|------------------|
| **Running Efficiency** | Trend chart (last 30 similar runs), personal best, average |
| **Cardiac Drift** | Comparison to similar efforts, what causes high/low drift |
| **Aerobic Decoupling** | Historical trend, threshold for "ready to race" |
| **Pace Consistency** | Which splits hurt consistency, comparison to ghost |

---

## Design

### Interaction Pattern
- Click tile → Expands inline (accordion style)
- Click again → Collapses
- Only one tile expanded at a time (optional)

### Expanded Content Structure
```
┌─────────────────────────────────────────────┐
│ Running Efficiency                    -2.6% │
├─────────────────────────────────────────────┤
│ [Trend Chart: Last 20 Similar Runs]         │
│                                             │
│  Your Average: +0.5%    Today: -2.6%        │
│  Best Ever: +8.2% (Oct 15, 2025)            │
│                                             │
│  💡 Today was harder than usual. Could be   │
│     heat, fatigue, or accumulated load.     │
└─────────────────────────────────────────────┘
```

### Data Requirements

Backend must provide for each metric:
1. Current value (already exists)
2. Historical values for similar runs (new endpoint needed)
3. Personal best (calculate from history)
4. Average (calculate from history)

---

## Implementation Plan

### Phase 1: Backend
1. Create endpoint: `GET /v1/activities/{id}/metric-history`
2. Returns historical data for all four metrics from similar runs
3. Reuse existing `SimilarityScorer` logic

### Phase 2: Frontend
1. Add expandable state to each tile
2. Fetch metric history on first tile click (lazy load)
3. Render trend chart using existing chart component
4. Add insight text based on comparison

### Phase 3: Polish
1. Loading state while fetching
2. Smooth expand/collapse animation
3. Empty state if insufficient history

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Performance on click | Lazy load, cache response |
| No historical data for new users | Show "Need more runs to show trends" |
| Chart rendering issues | Use same Recharts already in codebase |

---

## Success Criteria

- [ ] All four tiles are clickable
- [ ] Expansion shows meaningful historical context
- [ ] No performance degradation
- [ ] Works on mobile (touch expand)

---

## Rollback Plan

Feature flag: `FEATURE_INTERACTIVE_TILES`
- If issues arise, disable via config
- Tiles revert to static display

---

**Approved By:** Founder (2026-01-11)
**Status:** Implemented
