# Builder Note — Readiness Relabel + Briefing Cooldown

**Date:** March 3, 2026
**Spec:** `docs/specs/READINESS_RELABEL_AND_BRIEFING_COOLDOWN_SPEC.md`
**Assigned to:** Full-stack Builder
**Advisor sign-off required:** No — spec approved by founder
**Urgency:** Critical — currently poisoning narration on every surface
and repeating the same finding in 4 consecutive briefings

---

## Before Your First Tool Call

Read in order:

1. `docs/FOUNDER_OPERATING_CONTRACT.md` — how you work (non-negotiable)
2. `docs/PRODUCT_MANIFESTO.md` — the soul
3. `docs/specs/READINESS_RELABEL_AND_BRIEFING_COOLDOWN_SPEC.md` — the
   full spec. Read every line.
4. This builder note

---

## Objective

Replace every occurrence of `motivation_1_5` with `readiness_1_5`
across the entire codebase — database column, API models, correlation
engine input name, coach context labels, frontend check-in UI, and
historical CorrelationFinding rows. Simultaneously, implement finding-
level cooldown at the prompt injection layer so the same correlation
finding cannot appear in consecutive briefings.

One migration. One commit. Atomic.

---

## Scope

### In scope

1. **Database migration:** Rename `daily_checkin.motivation_1_5` →
   `readiness_1_5`. Update `correlation_finding` rows where
   `input_name = 'motivation_1_5'` → `'readiness_1_5'`.

2. **Backend rename:** Every file that references `motivation_1_5` must
   use `readiness_1_5`. The spec lists every affected file. Use
   project-wide search to verify AC8: no file contains `motivation_1_5`
   after the commit (except the migration downgrade).

3. **Label map fix:** Replace all instances of the motivation map
   (`{5: 'Great', 4: 'Fine', 2: 'Tired', 1: 'Rough'}`) with:
   ```python
   readiness_map = {5: 'High', 4: 'Good', 3: 'Neutral', 2: 'Low', 1: 'Poor'}
   ```
   Note: the old map was missing value 3. The new map includes all 5.

4. **Frontend check-in UI:** In `apps/web/app/checkin/page.tsx`:
   - Change label from "Motivation?" to "Morning readiness"
   - Change scale from "Forcing it → Fired up" to "Low → High"
   - Change emojis: `😴😑😐💪🔥` (replacing 😤 at position 4 with 💪)
   - Change state variable from `motivation` to `readiness`
   - Change API field from `motivation_1_5` to `readiness_1_5`

5. **Finding-level cooldown:**
   - In `_build_rich_intelligence_context()`: before injecting each N=1
     finding, check Redis key `finding_surfaced:{athlete_id}:{input_name}:{output_metric}`.
     If key exists, skip that finding.
   - In `compute_coach_noticed()`: same check before returning a
     correlation-based insight.
   - In `generate_home_briefing_task()` (tasks/home_briefing_tasks.py):
     after briefing generation, scan the combined output text for each
     injected finding's readable name. Set cooldown key with 72h TTL
     for any that appear.
   - Remove old `coach_noticed_last:{athlete_id}` Redis key read/write.
   - Remove ROTATION CONSTRAINT prompt text from `_prepare_home_briefing()`.
   - Redis failure fails open — finding is injected, not suppressed.

6. **One-new-thing prompt rule:** Add to `_prepare_home_briefing()`,
   after coaching tone rules, before athlete brief:
   ```
   ONE-NEW-THING RULE: Your briefing should contain exactly ONE
   observation the athlete didn't know yesterday — one genuinely new
   piece of information, finding, or pattern. Not four insights. Not
   three correlation findings. Not two ways of saying the same thing.
   One true, useful, new thing — then practical guidance for today.
   If you don't have anything new, just coach today's session.
   Don't fill space.
   ```

### Out of scope

- Renaming `enjoyment_1_5` or `confidence_1_5` (separate decision)
- Changes to correlation engine logic (Pearson, confounder control)
- Briefing LLM model changes

---

## Implementation Notes

### Key contracts

1. **Atomic rename.** After this commit, `motivation_1_5` must not
   appear anywhere in the codebase except the migration downgrade and
   git history. Grep the entire repo as a final check.

2. **Migration is non-destructive.** Column rename is metadata-only in
   PostgreSQL. The UPDATE on correlation_finding is small (handful of
   rows per athlete). Both operations are reversible.

3. **Cooldown fails open.** If Redis is unavailable, the cooldown check
   returns False (not in cooldown) and the finding is injected. This
   matches the current behavior where Redis failure doesn't break the
   briefing.

4. **One-new-thing is a prompt constraint, not a code constraint.** The
   LLM is instructed. The cooldown mechanism is the hard gate. The
   prompt rule is the soft guidance.

### Build sequence

1. Run the migration first.
2. Rename all backend references.
3. Fix the label map (all 5 values).
4. Implement cooldown (check + set + removal of old rotation).
5. Add one-new-thing prompt rule.
6. Update frontend check-in page.
7. Update all tests.
8. Final grep: verify zero occurrences of `motivation_1_5`.

---

## Tests Required

### Rename tests
- Existing tests for daily checkin, correlation quality, progress
  knowledge, coach tools, sleep prompt grounding, and training
  scenarios must pass with the renamed field.
- Add one assertion: `assert 'motivation_1_5' not in` the correlation
  engine's aggregated input names.

### Cooldown tests
- Finding in cooldown → not injected into rich intelligence context
- Finding not in cooldown → injected normally
- After briefing generation → cooldown key set for surfaced findings
- Redis unavailable → finding injected (fail open)
- Old `coach_noticed_last` key no longer read or written

### Production smoke checks

```bash
# Verify column renamed
docker exec strideiq_api python -c "
from models import DailyCheckin
cols = [c.name for c in DailyCheckin.__table__.columns]
assert 'readiness_1_5' in cols, f'readiness_1_5 not found: {cols}'
assert 'motivation_1_5' not in cols, 'motivation_1_5 still exists!'
print('Column rename verified:', cols)
"

# Verify correlation findings updated
docker exec strideiq_api python -c "
from database import SessionLocal
from models import CorrelationFinding
db = SessionLocal()
old = db.query(CorrelationFinding).filter(
    CorrelationFinding.input_name == 'motivation_1_5'
).count()
new = db.query(CorrelationFinding).filter(
    CorrelationFinding.input_name == 'readiness_1_5'
).count()
print(f'Old motivation_1_5 findings: {old} (should be 0)')
print(f'New readiness_1_5 findings: {new}')
db.close()
"

# Verify no motivation_1_5 in codebase
docker exec strideiq_api grep -r 'motivation_1_5' /app/ --include='*.py' -l || echo 'Clean — no occurrences'
```

---

## Evidence Required in Handoff

1. Scoped file list changed (no `git add -A`)
2. Test output — verbatim paste of all tests passing
3. Migration output — applied cleanly
4. Grep output showing zero occurrences of `motivation_1_5` in codebase
5. Production smoke check output

---

## Acceptance Criteria

See spec for the full list (AC1–AC20). Summary:

- AC8 is the critical gate: no file contains `motivation_1_5` after commit
- AC5 is the label fix: readiness map has all 5 values
- AC10–AC15 are the cooldown fix: finding-level gating at injection layer
- AC16–AC17 are the briefing constraint: one-new-thing rule in prompt

---

## Mandatory: Site Audit Update

`docs/SITE_AUDIT_LIVING.md` must be updated in the same session.

Required update block in the delivery pack:

1. Exact section(s) updated in `docs/SITE_AUDIT_LIVING.md`
2. What changed in product truth (not plan text)
3. Any inventory count/surface/tool updates

No task is complete until this is done.
