# Next Session Instructions

**Last Updated:** 2026-01-31 Morning
**Previous Session:** RPI Terminology Fix + Failed Test User Cleanup

---

## CRITICAL: Read First

The previous session degraded. The assistant made multiple failed attempts to delete test users from production without first querying the actual database schema. **All attempts rolled back - no data was damaged**, but the task is incomplete.

**User expectations going forward:**
1. Query actual production schema before writing any SQL
2. Test on a single record before bulk operations
3. No trial and error on production
4. Get explicit approval before making changes

---

## Current State

### Branch
`phase8-s2-hardening`

### Docker Status
All containers healthy. Production running.

### All Tests Passing
- 1326 passed, 3 skipped

---

## Completed This Session

### 1. RPI Terminology Fix (Phase 11 - COMPLETE)
Replaced trademarked "VDOT" with "RPI" throughout Coach AI:
- `ai_coach.py`: 3 system prompt locations with "NEVER say VDOT" instructions
- `coach_tools.py`: Dual keys (`rpi` + `vdot`) for backward compatibility
- Frontend component renamed: `VDOTCalculator.tsx` → `TrainingPaceCalculator.tsx`

**To verify in production:** Clear `coach_thread_id` for your account, then test Coach.

### 2. Test Fixes
- Model tiering tests: expect `gpt-4o-mini` default
- Coach routing tests: expect plain English ("fatigue level")
- Stripe tests: skip without env vars

### 3. Phase 11 Documentation
Updated `docs/PHASED_WORK_PLAN.md` - Phase 11 marked complete.

---

## Incomplete Task

### Test User Cleanup
**Goal:** Delete 393 users with `@example.com` emails

**Status:** FAILED - multiple FK constraint errors

**Why:** Production schema differs from `models.py`. Tables like `purchase` don't exist. Column `invite_audit_event.athlete_id` doesn't exist.

**No damage:** All transactions rolled back.

**To fix properly:**
1. Query actual FK constraints from production:
```sql
SELECT tc.table_name, kcu.column_name 
FROM information_schema.table_constraints AS tc 
JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY' AND ccu.table_name = 'athlete';
```
2. Build delete script from actual results
3. Test on ONE user first
4. Then run bulk delete

---

## Priority List

1. **Verify RPI fix works** - clear coach_thread_id, test Coach
2. **Clean up test users** - do it RIGHT this time (query schema first)
3. **Pending integrations:**
   - Garmin API (awaiting approval)
   - COROS API (application prepared)

---

## Key Files

| File | Purpose |
|------|---------|
| `apps/api/services/ai_coach.py` | Coach system prompts with RPI terminology |
| `apps/api/services/coach_tools.py` | Tool responses with dual rpi/vdot keys |
| `apps/api/scripts/cleanup_test_users.py` | BROKEN - do not use without rewrite |
| `_AI_CONTEXT_/SESSION_SUMMARY_2026_01_31_MORNING.md` | Detailed session summary |

---

## Commands

```bash
# Verify RPI fix
UPDATE athlete SET coach_thread_id = NULL WHERE email = 'your-email';
# Then test Coach with "what is my threshold pace?"

# Check test user count
docker exec strideiq_postgres psql -U postgres -d running_app -c "SELECT COUNT(*) FROM athlete WHERE email LIKE '%@example.com';"

# Query actual FK constraints before any cleanup
docker exec strideiq_postgres psql -U postgres -d running_app -c "SELECT tc.table_name, kcu.column_name FROM information_schema.table_constraints AS tc JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name JOIN information_schema.constraint_column_usage AS ccu ON ccu.constraint_name = tc.constraint_name WHERE tc.constraint_type = 'FOREIGN KEY' AND ccu.table_name = 'athlete';"
```

---

*Session ended: 2026-01-31 Morning*
