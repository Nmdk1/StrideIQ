# ADR 14: Landing Experience Architecture

**Status:** In Progress (Phases 1-3 Complete)  
**Date:** 2026-01-12  
**Author:** AI Architect  
**Stakeholder:** Founder

---

## Context

StrideIQ aims to be a world-leading running intelligence platform that athletes, coaches, and scientists can't put down. The current landing experience (login → activity list) fails to deliver on this vision. The dashboard shows technical analytics without context. The calendar is a separate page.

**The manifesto states:** "The calendar is home. Everything flows through it."

But the current implementation doesn't embody this. Athletes land on a list. The intelligence is buried.

---

## Decision

Create a **layered intelligence architecture** that serves three user types with appropriate depth:

### The Three Layers

| Layer | Time | User Intent | What They See |
|-------|------|-------------|---------------|
| **Glance** | 2 sec | "What now?" | Today's workout + one insight |
| **Explore** | 30 sec | "How am I doing?" | Week view, trends, comparisons |
| **Research** | 5+ min | "Why did this happen?" | Correlations, attribution, queries |

---

## Layer 1: The Glance (Home View)

When an athlete logs in, they see:

### Section A: Today (Hero)
```
┌─────────────────────────────────────────────────────────────┐
│  TODAY: THURSDAY, JAN 12                                    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  THRESHOLD INTERVALS                                 │   │
│  │  7 mi total · 4×1mi @ 6:15/mi w/ 2min jog           │   │
│  │                                                      │   │
│  │  WHY THIS WORKOUT:                                   │   │
│  │  "You're in week 3 of threshold focus. This builds  │   │
│  │   on last week's 3×1mi. Your efficiency at LT pace  │   │
│  │   improved 4% last session — keep pushing."         │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  [Mark Complete]  [Adjust]  [Skip]                          │
└─────────────────────────────────────────────────────────────┘
```

### Section B: Yesterday's Insight
```
┌─────────────────────────────────────────────────────────────┐
│  YESTERDAY: 6mi Easy                                        │
│                                                             │
│  "Your efficiency was 3% better than similar easy runs.    │
│   HR stayed low (138 avg) despite 8:24/mi pace.            │
│   Aerobic base is solid."                                   │
│                                                             │
│  [See Full Analysis →]                                      │
└─────────────────────────────────────────────────────────────┘
```

### Section C: This Week Progress
```
┌─────────────────────────────────────────────────────────────┐
│  WEEK 3 OF 8 · THRESHOLD FOCUS                              │
│                                                             │
│  Mon   Tue   Wed   Thu   Fri   Sat   Sun    │  Progress    │
│  ✓6mi  ✓8mi  ✓Rest  •7mi  6mi   14mi  Rest   │  24/47 mi   │
│                                              │  ████░░░░   │
│                                                             │
│  On Track: Volume and quality hitting targets               │
└─────────────────────────────────────────────────────────────┘
```

---

## Layer 2: The Exploration (Calendar + Insights)

The calendar becomes a **story**, not just dates:

### Every Day Shows:
- **Planned vs Actual** — visual comparison
- **One Key Metric** — efficiency, cardiac drift, or pace consistency
- **Status Indicator** — completed, adjusted, missed

### Tap Any Day → Day Detail:
- Full workout data
- Comparison to similar runs ("ghost average")
- Notes and context
- Coach chat for questions

### Week Summary:
- Volume vs target
- Quality sessions completed
- Key insight for the week
- Trend direction (improving, stable, fatiguing)

---

## Layer 3: The Research (Analytics + Attribution)

For coaches and scientists who want depth:

### The Dashboard (Renamed: Analytics)
- Efficiency trends over time
- Load-response curves
- Age-graded trajectory
- Stability metrics

### The Attribution Engine
- **"What drives my performance?"**
  - Correlations with sleep, nutrition, volume, intensity
  - Lagged effects (e.g., "threshold work 2 weeks ago correlates with today's efficiency")
  - Confidence levels for each factor

### The Query Engine (Future)
- Natural language queries: "Show me runs where I negative split after sleeping 7+ hours"
- Visual correlation explorer
- Export for external analysis

---

## Implementation Plan

### Phase 1: Home Experience (This Sprint)
1. Change login redirect to new `/home` route
2. Build Home page with Today's Workout (hero), Yesterday's Insight, Week Progress
3. Add "Why This Workout" context generation
4. Add "Yesterday's Insight" auto-generation

### Phase 2: Calendar Enhancement
1. Add inline insights to day cells
2. Add week summary cards
3. Make calendar the exploration layer

### Phase 3: Analytics Restructure
1. Rename Dashboard → Analytics
2. Move to `/analytics` route
3. Add correlation explorer
4. Add attribution engine output

### Phase 4: Research Tools
1. Query engine (natural language)
2. Multi-athlete view (for coaches)
3. Data export with context

---

## Navigation Restructure

### Current Navigation (Too Many Items)
- Dashboard, Calendar, Training Plan, Insights, Compare, Coach, Activities, Tools, Settings

### Proposed Navigation (Focused)
```
Primary:
  Home        — The glance (today + yesterday + week)
  Calendar    — The exploration (past/present/future)
  Analytics   — The research (trends, correlations, attribution)
  Coach       — Ask questions, get answers

Secondary (Settings menu):
  Activities, Personal Bests, Profile, Settings, Tools
```

---

## Success Criteria

- [ ] Athlete knows what to do today within 2 seconds of logging in
- [ ] Athlete understands "why" for today's workout
- [ ] Yesterday's run provides one actionable insight
- [ ] Week progress is visible at a glance
- [ ] Exploration is one tap away
- [ ] Research is available for power users without cluttering athlete view

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| "Why This Workout" requires AI generation | Start with template-based, add GPT later |
| "Yesterday's Insight" needs data | Graceful fallback: show key metrics if no insight |
| Too much on Home page | Progressive disclosure — show essentials, hide depth |

---

## Approval

Awaiting founder review before implementation.

---
