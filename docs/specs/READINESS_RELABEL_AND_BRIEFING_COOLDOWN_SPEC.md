# Readiness Relabel + Briefing Finding Cooldown — Spec

**Date:** March 3, 2026
**Status:** Approved by founder
**Priority:** Critical — currently poisoning narration on every surface
**Scope:** One migration, one commit. Label fix + cooldown fix together
because the label changes input names which changes cooldown keys.

---

## The Problem

### 1. Wrong label

The check-in UI asks "Motivation?" on a 1–5 scale (Forcing it → Fired
up). The database stores it as `motivation_1_5`. The correlation engine
discovers it as input name `motivation_1_5`. Every downstream surface —
morning voice, coach noticed, progress page, What the Data Proved —
narrates findings about the athlete's "motivation."

For a disciplined athlete who runs through pain, exhaustion, and injury,
being told "your motivation correlates with efficiency" sounds like
"you run well when you feel like it." That's slightly insulting and
slightly wrong. What the field actually measures is morning subjective
state — how primed this body and mind is for today's training demand.
That's readiness, not motivation.

The UI question, the database column, the correlation input name, the
narration label, and the coach context all say the wrong word. The fix
must be atomic — all surfaces update together.

### 2. Finding repetition

The same correlation finding ("motivation → efficiency, 3-day lag") has
appeared in 4 consecutive briefings over 2 days. The existing rotation
constraint stores the last `coach_noticed` text in Redis and tells the
LLM "don't repeat this." This fails for three reasons:

1. The rotation only covers `coach_noticed`. The LLM surfaces the same
   finding in `morning_voice` with no constraint.
2. The `compute_coach_noticed()` function is deterministic — it always
   picks the strongest correlation. The rotation tells the LLM to say
   something different, but the same finding data is still injected into
   the prompt via `_build_rich_intelligence_context()`.
3. The rotation is text-based. The LLM can rephrase the same finding
   differently enough to pass the suppression check while saying the
   same thing.

The real fix: gate at the data injection layer. If a finding is in
cooldown, it never enters the prompt. The LLM cannot mention what it
cannot see.

### 3. Briefing philosophy

The briefing has been optimized for surfacing findings. It should be
optimized for being useful today. Each briefing should contain exactly
one thing the athlete didn't know yesterday — one genuinely new piece
of information or observation, delivered cleanly, then practical
guidance for today.

---

## Fix 1: Readiness Relabel

### What changes

| Layer | Old | New |
|-------|-----|-----|
| Check-in UI label | "Motivation?" | "Morning readiness" |
| Check-in UI scale | "Forcing it → Fired up" | "Low → High" |
| Check-in UI emojis | 😴😑😐😤🔥 | 😴😑😐💪🔥 |
| Database column | `motivation_1_5` | `readiness_1_5` |
| API request/response field | `motivation_1_5` | `readiness_1_5` |
| Correlation engine input name | `motivation_1_5` | `readiness_1_5` |
| Confounder map keys | `("motivation_1_5", ...)` | `("readiness_1_5", ...)` |
| Direction expectation keys | `("motivation_1_5", ...)` | `("readiness_1_5", ...)` |
| Coach context label | `"Feeling: Great/Fine/Tired/Rough"` | `"Readiness: High/Good/Neutral/Low/Poor"` |
| Coach tools wellness narrative | `avg_motivation` | `avg_readiness` |
| CorrelationFinding rows | `input_name = 'motivation_1_5'` | `input_name = 'readiness_1_5'` |

### Label map fix

Old (missing value 3, wrong framing):
```python
motivation_map = {5: 'Great', 4: 'Fine', 2: 'Tired', 1: 'Rough'}
```

New:
```python
readiness_map = {5: 'High', 4: 'Good', 3: 'Neutral', 2: 'Low', 1: 'Poor'}
```

### Files affected — Backend

| File | Change |
|------|--------|
| `apps/api/models.py` | Rename column `motivation_1_5` → `readiness_1_5` on `DailyCheckin` |
| `apps/api/routers/daily_checkin.py` | Rename field in request/response models |
| `apps/api/routers/home.py` | Replace `motivation_map` with `readiness_map`, rename `motivation_label` → `readiness_label` in `TodayCheckin` and `_build_checkin_data_dict()` |
| `apps/api/routers/progress.py` | Update any `motivation_1_5` references in progress knowledge endpoint |
| `apps/api/routers/athlete_profile.py` | Update field references |
| `apps/api/services/correlation_engine.py` | Rename input name in `aggregate_daily_inputs()`, update `CONFOUNDER_MAP` keys, update `DIRECTION_EXPECTATIONS` keys |
| `apps/api/services/coach_tools.py` | Rename `motivation_values` → `readiness_values`, `avg_motivation` → `avg_readiness` in wellness trends |
| `apps/api/services/ai_coach.py` | Update context building references |
| `apps/api/services/attribution_engine.py` | Update references |
| `apps/api/services/trend_attribution.py` | Update references |
| `apps/api/services/pre_race_fingerprinting.py` | Update references |

### Files affected — Frontend

| File | Change |
|------|--------|
| `apps/web/app/checkin/page.tsx` | Rename state variable, update label/scale/emojis, change API field name |
| `apps/web/app/home/page.tsx` | Update any `motivation_label` references |
| `apps/web/lib/hooks/queries/home.ts` | Update type field name |

### Files affected — Tests

| File | Change |
|------|--------|
| `apps/api/tests/test_correlation_quality.py` | Update input name references |
| `apps/api/tests/test_progress_knowledge.py` | Update input name references |
| `apps/api/tests/test_coach_tools_phase3.py` | Update field references |
| `apps/api/tests/test_daily_checkin_briefing_refresh.py` | Update field references |
| `apps/api/tests/test_sleep_prompt_grounding.py` | Update field references |
| `apps/api/tests/test_training_logic_scenarios.py` | Update field references |
| `apps/api/tests/training_scenario_helpers.py` | Update field references |

### Migration

```python
# Rename column
op.alter_column('daily_checkin', 'motivation_1_5',
                new_column_name='readiness_1_5')

# Update existing CorrelationFinding rows
op.execute("""
    UPDATE correlation_finding
    SET input_name = 'readiness_1_5'
    WHERE input_name = 'motivation_1_5'
""")
```

The column rename is a metadata-only operation in PostgreSQL (no table
rewrite). The `UPDATE` on `correlation_finding` fixes historical input
names so downstream consumers never see the old label.

### What the athlete sees after the fix

Old: "Motivation 1 5 positively correlates with your efficiency"
New: "Your morning readiness score predicts your running efficiency
2 days later."

Old progress page: "High Motivation improves Efficiency within 2 days"
New: "High Morning Readiness improves Efficiency within 2 days"

---

## Fix 2: Finding-Level Briefing Cooldown

### Mechanism

**Cooldown key:** `finding_surfaced:{athlete_id}:{input_name}:{output_metric}`
**TTL:** 72 hours (3 days)
**Gate location:** `_build_rich_intelligence_context()` and
`compute_coach_noticed()` — before findings enter the prompt

### How it works

1. **On briefing generation** (`generate_home_briefing_task`): after the
   LLM produces the briefing, scan the output for which correlation
   findings were referenced. For each finding that appears in the
   output, set the cooldown key in Redis with 72h TTL.

2. **On next briefing build** (`_build_rich_intelligence_context`):
   before injecting N=1 insights into the prompt, check each finding's
   cooldown key. If the key exists, skip that finding. The LLM never
   sees it.

3. **On `compute_coach_noticed()`**: before returning a correlation-
   based coach noticed, check the cooldown key. If in cooldown, skip
   to the next waterfall step.

### Implementation detail: knowing which findings were surfaced

The simplest approach: after the LLM returns the briefing JSON, scan
the combined text of all fields for each input name that was injected
into the prompt. If `readiness_1_5` appears anywhere in the output,
set its cooldown key. This is conservative — it might cooldown a
finding that was mentioned tangentially — but that's fine. Better to
rotate too aggressively than too passively.

```python
def _set_finding_cooldowns(
    athlete_id: str,
    briefing_text: str,
    injected_findings: List[Dict],
    redis_client,
):
    """
    After briefing generation, set cooldown keys for any findings
    that appear in the output text.
    """
    combined_text = briefing_text.lower()
    for finding in injected_findings:
        input_name = finding.get("input_name", "")
        output_metric = finding.get("output_metric", "")
        # Check if the input's human-readable name appears in output
        readable_name = input_name.replace("_1_5", "").replace("_", " ")
        if readable_name in combined_text:
            key = f"finding_surfaced:{athlete_id}:{input_name}:{output_metric}"
            redis_client.setex(key, 72 * 3600, "1")


def _is_finding_in_cooldown(
    athlete_id: str,
    input_name: str,
    output_metric: str,
    redis_client,
) -> bool:
    key = f"finding_surfaced:{athlete_id}:{input_name}:{output_metric}"
    return redis_client.get(key) is not None
```

### What replaces the old rotation constraint

The existing `coach_noticed_last:{athlete_id}` Redis key and the
text-based ROTATION CONSTRAINT prompt injection are removed. They are
superseded by the finding-level cooldown which operates upstream of
the LLM.

### Files affected

| File | Change |
|------|--------|
| `apps/api/routers/home.py` | Add `_is_finding_in_cooldown()` check in `_build_rich_intelligence_context()`, add `_is_finding_in_cooldown()` check in `compute_coach_noticed()`, remove old `coach_noticed_last` read + ROTATION CONSTRAINT prompt injection |
| `apps/api/tasks/home_briefing_tasks.py` | After briefing generation, call `_set_finding_cooldowns()`. Remove old `coach_noticed_last` write. |
| `apps/api/tests/test_coach_quality.py` | Update rotation tests to test finding-level cooldown instead of text-based rotation |

---

## Fix 3: One-New-Thing Briefing Constraint

### The constraint

Add to the briefing prompt, in the coaching rules section:

```
ONE-NEW-THING RULE: Your briefing should contain exactly ONE observation
the athlete didn't know yesterday — one genuinely new piece of
information, finding, or pattern. Not four insights. Not three
correlation findings. Not two ways of saying the same thing. One true,
useful, new thing — then practical guidance for today. If you don't
have anything new, just coach today's session. Don't fill space.
```

### Where it goes

In `_prepare_home_briefing()` in `routers/home.py`, add to the
`parts` list after the existing coaching tone rules and before the
athlete brief injection.

### What it replaces

This is additive — it doesn't replace anything. But it makes the
finding-level cooldown more effective: even if multiple findings
survive the cooldown filter, the LLM is instructed to pick one and
move on.

---

## Migration

Single Alembic migration covering both fixes:

```python
"""rename motivation to readiness"""

def upgrade():
    # 1. Rename column on daily_checkin
    op.alter_column('daily_checkin', 'motivation_1_5',
                    new_column_name='readiness_1_5')

    # 2. Update historical correlation findings
    op.execute("""
        UPDATE correlation_finding
        SET input_name = 'readiness_1_5'
        WHERE input_name = 'motivation_1_5'
    """)


def downgrade():
    op.alter_column('daily_checkin', 'readiness_1_5',
                    new_column_name='motivation_1_5')
    op.execute("""
        UPDATE correlation_finding
        SET input_name = 'motivation_1_5'
        WHERE input_name = 'readiness_1_5'
    """)
```

---

## Acceptance Criteria

### Label fix
- [ ] AC1: Database column is `readiness_1_5`, not `motivation_1_5`
- [ ] AC2: Check-in UI asks "Morning readiness" with "Low → High" scale
- [ ] AC3: Correlation engine input name is `readiness_1_5`
- [ ] AC4: Confounder map and direction expectations use `readiness_1_5`
- [ ] AC5: Coach context says "Readiness: High/Good/Neutral/Low/Poor"
  (all 5 values mapped, including 3)
- [ ] AC6: Existing `CorrelationFinding` rows with `input_name =
  'motivation_1_5'` are migrated to `readiness_1_5`
- [ ] AC7: Progress page / What the Data Proved shows "Morning
  Readiness" not "Motivation 1 5"
- [ ] AC8: No file in the codebase contains the string `motivation_1_5`
  after the commit (except the downgrade migration and git history)
- [ ] AC9: API request/response models use `readiness_1_5`

### Cooldown fix
- [ ] AC10: `_build_rich_intelligence_context()` skips findings whose
  cooldown key exists in Redis
- [ ] AC11: `compute_coach_noticed()` skips correlation findings whose
  cooldown key exists in Redis
- [ ] AC12: After briefing generation, cooldown keys are set for all
  findings that appear in the output text
- [ ] AC13: Cooldown TTL is 72 hours
- [ ] AC14: Old `coach_noticed_last:{athlete_id}` key and ROTATION
  CONSTRAINT prompt text are removed
- [ ] AC15: If Redis is unavailable, cooldown check fails open (finding
  is injected, not suppressed — same as current behavior)

### Briefing constraint
- [ ] AC16: Briefing prompt contains ONE-NEW-THING rule
- [ ] AC17: Rule is positioned before the athlete brief, after coaching
  tone rules

### Integration
- [ ] AC18: All existing tests pass (with field name updates)
- [ ] AC19: Migration applies and rolls back cleanly
- [ ] AC20: Founder's next morning briefing does not mention motivation

---

## Build Order

One commit. Everything updates atomically:

1. Migration (column rename + finding data fix)
2. Model + router + service renames (all `motivation_1_5` → `readiness_1_5`)
3. Label map fix (`readiness_map` with all 5 values)
4. Cooldown implementation (Redis key check + set)
5. Old rotation removal
6. One-new-thing prompt addition
7. Frontend check-in UI update
8. Test updates

---

## Why This Matters

The label fix is not cosmetic. "Morning readiness predicts running
efficiency 2 days later" is a finding about physiological
self-knowledge — the athlete's subjective assessment of their state
is a genuine leading indicator of performance. That's remarkable and
actionable. "Motivation predicts efficiency" sounds like the athlete
is lazy on bad days. Same data, completely different message. The
wrong word poisons the trust relationship between the athlete and
the system.

The cooldown fix is not just about repetition. The briefing exists to
help the athlete train better today. A finding they've internalized is
no longer useful — it's noise. The system should say one true useful
thing and stop. Every additional repeated finding erodes the signal and
teaches the athlete to ignore the briefing.
