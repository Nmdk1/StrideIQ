# ADR-028: Model-Driven Plan UI Integration

**Status:** ACCEPTED  
**Date:** 2026-01-15  
**Author:** AI Assistant  
**Reviewers:** Michael Shaffer

---

## Context

Model-driven plans (ADR-022) are deployed at `/v2/plans/model-driven` but have no frontend. Cannot test without UI. Plans must:

1. Be creatable from the Plans page
2. Show personal insights (τ values, predictions, counter-conventional notes)
3. Apply to calendar with workouts

## Decision

**Enhance existing `/plans` page and creation flow.** Do not create separate page (increases friction).

### Chosen Approach

| Component | Implementation |
|-----------|----------------|
| Plans list | Add "Model-Driven" badge to plan cards with insight pills |
| Plan creation | Add radio toggle: "Template" vs "Model-Driven" in existing flow |
| Creation form | race_date, race_distance, optional goal_time |
| Preview | Show predicted time, τ values, counter-conventional notes |
| Apply to calendar | Button on plan card → create calendar workouts |

### Alternatives Rejected

| Alternative | Rejected Because |
|-------------|------------------|
| Separate `/plans/model-driven` page | Increases friction, fragments UX |
| New modal from scratch | Duplicates existing plan creation logic |
| AI chat interface | Violates "no GPT dependency" constraint |

## UI Design

### Plan Card (Model-Driven)

```
┌──────────────────────────────────────────────────┐
│  🧠 Model-Driven Plan                    [Apply] │
│  ─────────────────────────────────────────────── │
│  Boston Marathon • May 1, 2026                   │
│                                                  │
│  Pred: 3:28:xx ±3min (moderate)                 │
│  τ1=38d • τ2=7d • 14-day taper                  │
│                                                  │
│  "You adapt faster than average."               │
│  ─────────────────────────────────────────────── │
│  12 weeks • 847 mi total                        │
└──────────────────────────────────────────────────┘
```

### Creation Form (Model-Driven selected)

```
┌──────────────────────────────────────────────────┐
│  Create Training Plan                            │
│                                                  │
│  ○ Template (standard, free)                    │
│  ● Model-Driven (uses your data)                │
│                                                  │
│  Race Date:     [May 1, 2026      ▼]            │
│  Distance:      [Marathon         ▼]            │
│  Goal Time:     [3:30:00          ] (optional)  │
│                                                  │
│           [Generate Plan]                        │
└──────────────────────────────────────────────────┘
```

### Preview After Generation

```
┌──────────────────────────────────────────────────┐
│  Your Plan is Ready                              │
│                                                  │
│  Predicted Finish: 3:28:14 ±3 minutes           │
│  Confidence: moderate (based on 4 races)        │
│                                                  │
│  Your Model:                                     │
│  • τ1 = 38 days (you adapt faster than avg)     │
│  • τ2 = 7 days (typical recovery rate)          │
│  • Optimal taper: 14 days                        │
│                                                  │
│  From Your Data:                                 │
│  "Your best races followed 2 rest days, not 3." │
│                                                  │
│      [Save & Apply to Calendar]    [Discard]    │
└──────────────────────────────────────────────────┘
```

## Tone

Sparse, irreverent, value-first:
- "τ1=38d • faster adapter" not "Your fitness time constant is 38 days which is..."
- "Pred: 3:28 ±3min" not "We predict you will finish in approximately..."
- Counter-conventional notes verbatim from fingerprint

## Feature Gate

```typescript
// Check before showing Model-Driven option
const canUseModelDriven = 
  featureFlags.plan_model_driven_generation && 
  user.subscription_tier === 'elite';
```

If not elite: show disabled state with "Upgrade to Elite" link.

## Data Flow

```
1. User selects "Model-Driven" in creation form
2. Submits: POST /v2/plans/model-driven
3. Backend: calibrate model → calculate trajectory → predict → generate
4. Response: plan with prediction, model params, weeks
5. Frontend: show preview with insights
6. User clicks "Save & Apply"
7. Frontend: POST to save plan, then create calendar workouts
8. Redirect to /plans with success toast
```

## Calendar Integration

Reuse existing `PlannedWorkout` creation:
- Each plan week → 7 days
- Each day → workout entry if not rest
- Include: type, target pace, personalization notes
- Avoid overlap with existing workouts (warn or shift)

## Security

- Frontend: optimistic tier check (hide if not elite)
- Backend: enforces tier + rate limit (already done)
- No PII in model params (just numbers)

## Test Plan

### Unit Tests
- Plan card renders model badge
- Toggle state (template vs model-driven)
- Form validation

### Integration Tests
- API mock → form submit → plan saved
- Calendar events created

### Manual Verification
1. Log in as elite user
2. Go to /plans
3. Click "Create Plan"
4. Select "Model-Driven"
5. Fill form, submit
6. See preview with τ values
7. Apply to calendar
8. Verify workouts on calendar page

---

*ADR-028: Model-Driven Plan UI Integration*
