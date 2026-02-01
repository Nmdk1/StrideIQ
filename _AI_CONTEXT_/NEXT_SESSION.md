# Next Session Instructions

**Last Updated:** 2026-02-01
**Previous Session:** Test User Cleanup (SUCCESS)

---

## Current State

### Branch
`phase8-s2-hardening`

### Docker Status
All containers healthy. Production running.

### All Tests Passing
- 1326 passed, 3 skipped

### Database (Production)
- 9 real athletes
- 0 test users (cleanup complete on 2026-02-01)

---

## Completed This Session

### Test User Cleanup (SUCCESS - PRODUCTION)
Deleted 393 fake users with `@example.com` emails from **production**.

**Approach that worked:**
1. Queried actual FK constraints from production (not models.py)
2. Discovered 34 FK relationships to `athlete` table
3. Found nested FKs: `athlete_training_pace_profile` → `athlete_race_result_anchor`, `invite_audit_event` → `invite_allowlist`
4. Tested on single user first
5. Bulk deleted remaining 392 users

**Production result:** 0 test users, 9 real athletes remain.

---

## Previously Completed

### RPI Terminology Fix (Phase 11)
- Coach AI uses "RPI" instead of "VDOT"
- `TrainingPaceCalculator.tsx` renamed from `VDOTCalculator.tsx`
- All tests pass

---

## Priority List

1. **Verify RPI fix works** - clear coach_thread_id, test Coach
2. **Pending integrations:**
   - Garmin API (awaiting approval)
   - COROS API (application prepared at `docs/COROS_API_APPLICATION.md`)

---

## Key Files

| File | Purpose |
|------|---------|
| `apps/api/services/ai_coach.py` | Coach system prompts with RPI terminology |
| `apps/api/services/coach_tools.py` | Tool responses with dual rpi/vdot keys |
| `_AI_CONTEXT_/SESSION_SUMMARY_2026_02_01_CLEANUP.md` | Test user cleanup details |

---

## Commands

```bash
# Verify RPI fix
UPDATE athlete SET coach_thread_id = NULL WHERE email = 'your-email';
# Then test Coach with "what is my threshold pace?"

# Check athlete count
docker exec running_app_postgres psql -U postgres -d running_app -c "SELECT COUNT(*) FROM athlete;"
```

---

*Session ended: 2026-02-01*
