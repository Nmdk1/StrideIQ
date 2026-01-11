# Plan Generation System Roadmap

**Status:** ACTIVE - Governing Document  
**Created:** January 11, 2026  
**Standard:** Production-Ready (NOT MVP)

---

## Guiding Principles

1. **Production quality from day one** — No shortcuts, no "we'll fix it later"
2. **Configuration over code** — Paywalls, features, rules in database
3. **Plugin architecture** — Workouts, phases, rules are pluggable modules
4. **Feature flags everywhere** — Any feature can be gated/ungated without deploy
5. **Async generation** — Background jobs, not blocking requests
6. **Cache aggressively** — 15,000 athletes = read-heavy workload
7. **Test output quality** — Does the generated plan make sense?
8. **Rigorous testing** — Design → Implement → Test → Debug → Test → Iterate

---

## System Integration

Plan Generation is ONE component of the StrideIQ ecosystem:

```
Training Calendar (Central Hub)
├── Plan Generation → Planned Workouts
├── Activity Sync → Actual Activities
├── Insights Engine → Performance Analysis
├── GPT Coach → Guided Training
└── Athlete Intelligence Bank → Personalization
```

**The calendar is the consumer. Everything else is a producer.**

---

## Phase A: Core Infrastructure (Weeks 1-3)

### Week 1: Foundation

| Component | Purpose | Status |
|-----------|---------|--------|
| Feature Flags | Gate any feature without deploy | ⬜ |
| Plugin Registry | Pluggable workouts/phases/rules | ⬜ |
| Entitlements Service | Clean access control | ⬜ |
| Config Loading | YAML-driven rules | ⬜ |
| Cache Layer | Redis for scale | ⬜ |
| Job Queue | Celery for async generation | ⬜ |

### Week 2: Plan Generator Core

| Component | Purpose | Status |
|-----------|---------|--------|
| Volume Tier Classifier | Categorize athlete capacity | ⬜ |
| Phase Builder | Construct phase structure | ⬜ |
| Workout Scaler | Scale workouts to athlete | ⬜ |
| Pace Engine | Integrate Training Pace Calculator | ⬜ |
| Async Generation | Background plan creation | ⬜ |
| API Endpoints | REST API for plan operations | ⬜ |

### Week 3: Calendar Integration

| Component | Purpose | Status |
|-----------|---------|--------|
| Display Planned Workouts | Show in calendar grid | ⬜ |
| Option A/B UI | Toggle between workout options | ⬜ |
| Week Summaries | Volume, phase, focus | ⬜ |
| Phase Indicators | Visual phase progression | ⬜ |
| Completion Tracking | Match actual to planned | ⬜ |

---

## Phase B: Standard Plans (Weeks 4-8)

### Deliverable: 24 Standard Plans

| Distance | Durations | Volume Tiers | Count | Status |
|----------|-----------|--------------|-------|--------|
| Marathon | 18w, 12w | Low, Mid, High | 6 | ⬜ |
| Half Marathon | 16w, 12w | Low, Mid, High | 6 | ⬜ |
| 10K | 12w, 8w | Low, Mid, High | 6 | ⬜ |
| 5K | 12w, 8w | Low, Mid, High | 6 | ⬜ |

### Workout Library Required

- ~50 workout definitions across all distances
- Option A/B pairs for key workouts
- Scaling rules for each tier
- Phase-appropriate selection logic

---

## Phase C: Personalization (Weeks 9-12)

### Semi-Custom Plans ($5)

| Feature | Purpose | Status |
|---------|---------|--------|
| Questionnaire UI | Capture athlete input | ⬜ |
| Pace Integration | Training Pace Calculator | ⬜ |
| Duration Fitting | Compress/expand to race date | ⬜ |
| Race Profile | Hilly/flat/trail adjustments | ⬜ |
| Weather Context | Season-appropriate notes | ⬜ |
| Payment Integration | $5 one-time | ⬜ |

### Custom Plans (Subscription)

| Feature | Purpose | Status |
|---------|---------|--------|
| Strava Integration | Auto-populate from data | ⬜ |
| Variable Duration | Any length (4-24 weeks) | ⬜ |
| Tune-up Blocks | Short specialty plans | ⬜ |
| Athlete Intelligence | Personalization from history | ⬜ |
| Subscription Gating | Pro/Elite tiers | ⬜ |

---

## Phase D: GPT Coach (Weeks 13-15)

### GPT Coach Capabilities

| Capability | Description | Status |
|------------|-------------|--------|
| Workout Explanation | "Why this workout today?" | ⬜ |
| Modification Suggestions | "I'm tired, what should I do?" | ⬜ |
| Day Swapping | "Can I swap Tue and Thu?" | ⬜ |
| Morning Briefing | Daily focus and context | ⬜ |
| Post-Workout Feedback | Analysis and encouragement | ⬜ |
| Weekly Preview | What's coming this week | ⬜ |
| Phase Transitions | Explain what's changing | ⬜ |

### Context Assembly

GPT Coach has access to:
- Current plan and phase
- Today's planned workout
- Recent activities (7-14 days)
- Athlete profile and preferences
- Athlete Intelligence insights
- Workout library and purposes
- Coaching principles (TRAINING_PHILOSOPHY.md)

---

## Phase E: Dynamic Adaptation (Weeks 16-18)

### Completion Tracking

| Feature | Purpose | Status |
|---------|---------|--------|
| Activity Matching | Link actual to planned | ⬜ |
| Quality Assessment | Nailed/close/missed | ⬜ |
| Completion Rate | Track plan adherence | ⬜ |
| Missed Workout Handling | What happens when they skip | ⬜ |

### Adaptation Engine

| Feature | Purpose | Status |
|---------|---------|--------|
| Overperformance Detection | Crushing workouts → accelerate | ⬜ |
| Underperformance Detection | Struggling → adjust | ⬜ |
| Fatigue Detection | Insert recovery when needed | ⬜ |
| Phase Extension | Not ready → hold | ⬜ |
| Pace Updates | Breakthrough → new targets | ⬜ |

### Closed-Loop Integration

| Loop | Automation | Status |
|------|------------|--------|
| Daily | Compare actual vs planned | ⬜ |
| Weekly | Summary + adjustments | ⬜ |
| Build | Phase review + adaptation | ⬜ |
| Season | Race analysis + next cycle | ⬜ |

---

## Phase F: Polish & Scale (Weeks 19-20)

### Performance

| Target | Requirement |
|--------|-------------|
| Plan Generation | < 5 seconds |
| Calendar Load | < 500ms |
| Concurrent Users | 15,000+ |
| Cache Hit Rate | > 90% |

### Quality

| Requirement | Approach |
|-------------|----------|
| Test Coverage | 80%+ on generator logic |
| Output Validation | Plans reviewed for sensibility |
| Edge Cases | All handled gracefully |
| Error Handling | Clear messages, no crashes |

---

## Testing Strategy

### Unit Tests
- Volume tier classification
- Workout scaling
- Phase building
- Duration fitting
- Pace calculations

### Integration Tests
- API endpoint responses
- Database operations
- Cache behavior
- Job queue processing

### Output Validation Tests
- Generated plan makes physiological sense
- Workouts are appropriate for phase
- Volume builds safely
- Long run progression is correct
- T-block progression is logical
- MP work appears at right time
- Taper is appropriate length
- Option A/B pairs are equivalent stimuli

### Load Tests
- 15,000 concurrent plan views
- 1,000 simultaneous generations
- Cache performance under load

---

## Success Criteria

### Phase A Complete When:
- [ ] Feature flags work and gate features correctly
- [ ] Plugins can be added without code changes
- [ ] Entitlements correctly determine access
- [ ] Config drives behavior, not hardcoded values
- [ ] Cache reduces database load
- [ ] Async generation completes reliably

### Phase B Complete When:
- [ ] All 24 standard plans generate correctly
- [ ] Plans display in calendar
- [ ] Option A/B selection works
- [ ] Output makes physiological sense (manual review)
- [ ] All tests pass

### Phase C Complete When:
- [ ] Questionnaire captures all needed input
- [ ] Paces populate correctly
- [ ] Duration fitting works (±6 weeks from standard)
- [ ] Environmental adjustments apply
- [ ] Payment flow works
- [ ] Custom plans use Strava data

### Phase D Complete When:
- [ ] GPT Coach explains workouts accurately
- [ ] Modifications are sensible
- [ ] Day swaps respect constraints
- [ ] Briefings are helpful and personalized
- [ ] Responses use athlete's data

### Phase E Complete When:
- [ ] Plans adapt to missed workouts
- [ ] Over/underperformance triggers changes
- [ ] Fatigue detection works
- [ ] Pace targets update on breakthroughs
- [ ] All loops function automatically

### Phase F Complete When:
- [ ] Performance targets met
- [ ] No critical bugs
- [ ] Documentation complete
- [ ] Admin tools functional
- [ ] Monitoring in place
- [ ] Ready for 15,000 athletes

---

## File Structure

```
apps/api/services/plan_framework/
├── __init__.py
├── constants.py              # Volume tiers, limits, ratios
├── config.py                 # YAML config loading
├── feature_flags.py          # Feature flag service
├── entitlements.py           # Access control
├── cache.py                  # Caching layer
├── registry.py               # Plugin registry
├── volume_tiers.py           # Tier classification
├── phase_builder.py          # Phase construction
├── workout_scaler.py         # Workout scaling
├── pace_engine.py            # Pace calculation
├── duration_fitter.py        # Compress/expand plans
├── generator.py              # Main orchestrator
├── validators.py             # Plan validation
├── adapters/                 # Distance-specific logic
│   ├── marathon.py
│   ├── half_marathon.py
│   ├── ten_k.py
│   └── five_k.py
├── plugins/                  # Pluggable components
│   ├── workouts/
│   ├── phases/
│   └── rules/
└── tests/
    ├── test_volume_tiers.py
    ├── test_workout_scaling.py
    ├── test_phase_building.py
    ├── test_plan_generation.py
    └── test_output_validation.py
```

---

## Database Tables

```sql
-- Core tables
feature_flags
plan_templates
workout_definitions
phase_definitions
scaling_rules

-- Athlete tables
athlete_goals
athlete_questionnaires

-- Plan tables
training_plans
planned_workouts
workout_completions

-- Tracking tables
plan_adaptations
generation_logs
```

---

## Configuration Files

```
config/
├── plan_rules.yaml           # Volume tiers, phases, limits
├── workout_library.yaml      # Workout definitions
├── feature_flags.yaml        # Initial flag values
└── paywall_config.yaml       # Pricing and gating
```

---

## Revision History

| Date | Change | By |
|------|--------|-----|
| 2026-01-11 | Initial roadmap created | AI |

---

*This document governs all plan generation development.*
*Production quality. Not MVP. Test everything.*
