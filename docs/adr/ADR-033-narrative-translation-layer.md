# ADR-033: Narrative Translation Layer

**Status:** Proposed  
**Date:** 2026-01-15  
**Author:** Engineering Team  
**Depends On:** ADR-030 (Fitness Bank Framework)

## Context

StrideIQ's backend computes accurate, personalized signals:
- τ1 = 25 days (fast adapter)
- Efficiency up 4.2%
- TSB = -13 (coiled)
- Injury rebound: 70% of peak in 3 weeks

These are technically correct but emotionally flat. When a runner opens the app at 5:47am, they need to *feel* known in under 3 seconds.

**Current state:**
- Insights display raw metrics: "τ1=25d indicates faster adaptation"
- Workout notes show structure only: "2x3mi @ 6:25"
- Predictions show ranges without explanation: "3:01 ±5-8min"

**Desired state:**
- "You bounced back from the Dec 15 strain faster than the April one."
- "This is the session you crushed before Philly. Trust the legs."
- "The range is wide because of the leg. If it holds, you're sub-3."

## Decision

Implement a **Narrative Translation Layer** that converts computed signals into human-first sentences with dynamic, history-specific anchors.

### Key Principles

1. **No LLM at runtime** — Templates with dynamic slots, not generated text
2. **Specificity over variety** — Same skeleton, different anchors make it fresh
3. **History as content** — Reference specific dates, workouts, races
4. **Memory prevents repetition** — Track shown narratives, avoid recent repeats
5. **Emotional fidelity** — Connect data to lived experience

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Signal Sources                               │
│   FitnessBank, LoadSummary, EfficiencyTrending, PlannedWorkout  │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     AnchorFinder                                 │
│   find_previous_rebound(), find_similar_workout(),              │
│   find_efficiency_outlier(), find_comparable_load_state()       │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                  NarrativeTranslator                             │
│   narrate_load_state(), narrate_workout_context(),              │
│   narrate_injury_rebound(), narrate_efficiency(),               │
│   narrate_uncertainty(), narrate_milestone()                    │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                  NarrativeMemory                                 │
│   record_shown(), recently_shown(), get_stale_patterns()        │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     UI Surfaces                                  │
│   Home hero, Workout notes, Plan preview, Diagnostic summary    │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. AnchorFinder (`services/anchor_finder.py`)

Queries athlete history for specific, comparable events:

| Method | Purpose |
|--------|---------|
| `find_previous_injury_rebound()` | Find prior injury → recovery pattern |
| `find_similar_workout()` | Find workout with same structure |
| `find_efficiency_outlier()` | Best/worst efficiency in N days |
| `find_comparable_load_state()` | Prior day with similar TSB |
| `find_prior_race_at_load()` | Race performed at similar CTL/TSB |
| `find_same_route_run()` | Prior run on same GPS route |

### 2. NarrativeTranslator (`services/narrative_translator.py`)

Renders signals into sentences:

| Signal Type | Example Output |
|-------------|----------------|
| `load_state_coiled` | "You're coiled like {date}. That day you felt light — expect the same today." |
| `load_state_fresh` | "TSB is as high as before {race}. The hay is in the barn." |
| `workout_context` | "This is the session you averaged {pace} before {race}. Legs remember." |
| `injury_rebound` | "{weeks} weeks ago you couldn't run. Now at {pct}% — faster than the {prior_date} rebuild." |
| `efficiency_gain` | "Tuesday's {workout} was {delta}% more efficient than the same route in {month}." |
| `uncertainty_source` | "Range is wide because of {source}. If {source} holds, you're at the low end." |
| `milestone` | "You hit {volume} miles. That's where you were Week {week} before {race}." |

### 3. NarrativeMemory (`services/narrative_memory.py`)

Prevents repetition:

| Method | Purpose |
|--------|---------|
| `record_shown(narrative_hash)` | Store hash + timestamp |
| `recently_shown(hash, days=14)` | Check if shown recently |
| `get_stale_patterns()` | Find overused pattern IDs |
| `clear_old(days=60)` | Prune old records |

## Alternatives Considered

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| **LLM at runtime** | Natural language, handles edge cases | Latency (1-3s), cost, unpredictable voice, dependency | Rejected |
| **Static templates** | Fast, controlled | Stale by month 2, no personalization | Rejected |
| **Dynamic anchors (chosen)** | Fast, controlled, infinite variety from history | More upfront query work | **Accepted** |

## Integration Points

| Surface | Integration |
|---------|-------------|
| **Home page** | Hero sentence via `get_hero_narrative()` |
| **Workout detail** | Notes via `narrate_workout_context()` |
| **Plan preview** | Insights via `get_plan_narratives()` |
| **Diagnostic report** | Summary section |

## Performance

- All queries use existing indexed fields (athlete_id, start_time, workout_type)
- Anchor finding: <50ms (single query per anchor type)
- Template rendering: <1ms
- Total latency: <100ms for full narrative set

## Security

- No new data exposure — uses existing activity/bank data
- Narrative memory keyed by athlete_id (no cross-user access)
- Feature flag gated: `narrative.translation_enabled`

## Testing

### Unit Tests
- Anchor finder returns correct events
- Translator formats correctly with various inputs
- Memory deduplication works
- Edge cases: no history, no comparable anchor

### Integration Tests
- Full flow: signal → anchor → narrative → memory → display
- Home page renders hero without error
- Workout notes populate correctly

## Rollout

1. **Phase 1:** Workout detail notes only (lowest risk, highest impact)
2. **Phase 2:** Home hero sentence
3. **Phase 3:** Plan preview insights
4. **Phase 4:** Diagnostic report summary

## Success Metrics

| Metric | Target |
|--------|--------|
| Narrative uniqueness | <5% repeat rate over 30 days |
| Load time impact | <100ms added latency |
| User engagement | Increased home page opens |
| Qualitative | "This thing knows me" feedback |

## Files

| File | Purpose |
|------|---------|
| `services/anchor_finder.py` | Historical anchor queries |
| `services/narrative_translator.py` | Signal → sentence rendering |
| `services/narrative_memory.py` | Deduplication tracking |
| `tests/test_narrative_layer.py` | Unit + integration tests |

## References

- ADR-030: Fitness Bank Framework
- ADR-031: Constraint-Aware Planning
- Executive Report: "Gap between data truth and felt truth"
