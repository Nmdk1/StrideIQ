# ADR-007: Full Workout Control for Paid Tier Athletes

**Status:** Implemented  
**Date:** 2026-01-11  
**Decision Makers:** Product, Engineering  

---

## Context

Athletes need flexibility to adapt training plans to life demands. The previous system offered only two adjustments:
1. Swap two workouts within a week
2. Adjust overall weekly load (reduce/increase)

This was insufficient. Athletes requested:
- Moving a single workout to any date
- Changing workout type mid-plan
- Adding workouts on rest days
- Removing workouts entirely

These capabilities must be gated to paid tier to preserve value differentiation.

---

## Decision

Implement **Full Workout Control** with the following capabilities:

| Capability | Endpoint | Method | Tier |
|------------|----------|--------|------|
| Move workout to new date | `/v2/plans/{plan_id}/workouts/{workout_id}/move` | POST | Paid |
| Edit workout details | `/v2/plans/{plan_id}/workouts/{workout_id}` | PUT | Paid |
| Remove/skip workout | `/v2/plans/{plan_id}/workouts/{workout_id}` | DELETE | Paid |
| Add new workout | `/v2/plans/{plan_id}/workouts` | POST | Paid |
| Get workout types | `/v2/plans/{plan_id}/workout-types` | GET | All |

### Tier Gating Logic

```python
def _check_paid_tier(athlete, db) -> bool:
    # Check subscription tier
    if athlete.subscription_tier in ("pro", "elite", "premium", "guided", "subscription"):
        return True
    # Check if they have any paid plans
    paid_plan = db.query(TrainingPlan).filter(
        TrainingPlan.athlete_id == athlete.id,
        TrainingPlan.generation_method.in_(["semi_custom", "custom", "framework_v2"]),
    ).first()
    return paid_plan is not None
```

---

## Constraints

1. **Cannot modify completed workouts** - Historical integrity
2. **Cannot modify paused/cancelled plans** - Only active plans
3. **Date bounds enforced** - Cannot move outside plan start/end dates
4. **Week number auto-recalculates** - When moving across weeks
5. **Phase inheritance** - New workouts inherit phase from nearest existing workout

---

## Security Considerations

1. **Ownership validation** - All endpoints verify `athlete_id` matches authenticated user ✅
2. **Plan ownership** - Verify plan belongs to athlete before any modification ✅
3. **Input validation** - Pydantic models enforce types and constraints ✅
4. **Audit logging** - All modifications logged with before/after state ✅
5. **IDOR Protection** - Workout queries filter by both `plan_id` AND `athlete_id` ✅
6. **Completed workout protection** - Cannot modify completed workouts ✅
7. **Inactive plan protection** - Cannot modify paused/cancelled/completed plans ✅

### Rate Limiting (TODO)

Recommend implementing rate limits in future:
- Move: 10/hour per athlete
- Edit: 20/hour per athlete
- Add: 5/hour per athlete
- Delete: 5/hour per athlete

### Input Sanitization

String fields (title, description, coach_notes) are stored as-is. Consider:
- Max length enforcement (title: 200 chars, description: 2000 chars)
- XSS prevention (frontend renders safely via React)

---

## Audit Trail

All modifications are logged to `plan_modification_log` with:
- `athlete_id`
- `plan_id`
- `workout_id`
- `action` (move, edit, delete, add)
- `before_state` (JSON)
- `after_state` (JSON)
- `timestamp`
- `reason` (optional)

---

## Rollback Strategy

1. **Soft delete** - Workouts marked `skipped=True`, not hard deleted
2. **Audit log** - Full before/after state enables manual restoration
3. **Feature flag** - Can disable full control without code deploy

---

## Testing Requirements

### Unit Tests
- [ ] Move workout - valid date
- [ ] Move workout - outside bounds (expect 400)
- [ ] Move workout - completed workout (expect 400)
- [ ] Edit workout - change type
- [ ] Edit workout - change distance
- [ ] Delete workout - marks as skipped
- [ ] Add workout - creates with correct week number
- [ ] Tier gating - free user blocked (expect 403)

### Integration Tests
- [ ] Frontend move flow end-to-end
- [ ] Frontend edit flow end-to-end
- [ ] Frontend add flow end-to-end
- [ ] Calendar updates after modification

---

## Alternatives Considered

### 1. Coach-Mediated Changes
Rejected: Adds friction, doesn't scale, contradicts "guided self-coaching" philosophy.

### 2. Weekly Edit Windows
Rejected: Arbitrary restriction that frustrates athletes who need flexibility.

### 3. Unlimited Free Modifications
Rejected: Removes value differentiation for paid tier.

---

## Consequences

### Positive
- Athletes have maximum control over their training
- Reduces support requests for plan modifications
- Clear paid tier value proposition
- Audit trail enables analysis of modification patterns

### Negative
- Athletes can create suboptimal plans through excessive modification
- More complex codebase
- Requires careful UX to prevent accidental changes

### Mitigations
- Coach Chat can analyze modification patterns and provide guidance
- UI requires confirmation for destructive actions
- Undo capability through audit log (future)

---

## Implementation Checklist

- [x] API endpoints implemented
- [x] Tier gating implemented
- [x] Frontend UI implemented
- [x] Audit logging implemented (PlanModificationLog model + service)
- [x] Unit tests written (tests/test_workout_control.py)
- [x] Integration tests written (in test_workout_control.py)
- [x] Input validation with max lengths
- [x] IDOR protection verified
- [x] Documentation updated (this ADR)
- [x] Database migration run (add_plan_mod_log) ✅ 2026-01-11
- [ ] Rate limiting (TODO: future enhancement)
