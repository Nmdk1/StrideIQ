# Temporal Fact Lifecycle Spec

**Date:** March 11, 2026  
**Priority:** P1 — fix the stale fact regression, then enable longitudinal learning  
**Trigger:** Morning voice surfaced "left shin tightness" two weeks after resolution. Deactivated manually on prod. This spec prevents recurrence and turns temporal facts into correlation engine inputs.

---

## Principle

Facts have lifespans. Some are permanent (age, bone density, PRs). Some are temporal (injuries, current symptoms, shoe changes, race goals with deadlines, taper state, strength maxes in flux). The lifecycle system must be **fact-type-agnostic** — injuries are the first use case, but the columns, states, and engine wiring apply to any temporal fact.

---

## 1. Schema Changes

### `athlete_fact` table — new columns

| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `temporal` | Boolean | `false` | Marks fact as having a lifespan |
| `ttl_days` | Integer (nullable) | `null` | Days until soft-expiry. `null` = permanent |
| `resolved_at` | DateTime(tz) (nullable) | `null` | When the fact was explicitly resolved |
| `soft_expired_at` | DateTime(tz) (nullable) | `null` | When TTL elapsed without re-mention or resolution |
| `deadline_date` | Date (nullable) | `null` | For time-bounded facts (race goals, rehab targets) |

**Fact states (derived, not stored):**

| State | Condition | Surfaced in voice? | Engine signal? |
|-------|-----------|--------------------|--------------------|
| **active** | `is_active=True`, not expired, not resolved | Yes | Full strength |
| **soft-expired** | `is_active=True`, `soft_expired_at` is set | No | Decaying signal |
| **resolved** | `resolved_at` is set | No | Historical event |
| **inactive** | `is_active=False` | No | No |

The key distinction: **soft-expired is NOT resolved.** Soft-expired means "the athlete stopped mentioning it but never said it's fixed." The engine signal degrades gradually (see section 4) instead of going binary 0 overnight.

### Migration

```
alembic revision --autogenerate -m "add temporal lifecycle columns to athlete_fact"
```

Five nullable columns. Backfill: set `temporal=True` and `ttl_days=14` for existing facts where `fact_type IN ('injury_history', 'current_symptoms')`. Set `temporal=False` for all others.

---

## 2. TTL Categories (extraction prompt responsibility)

The extraction prompt classifies each fact. This is the **only** injury/category-specific part of the system.

| `fact_type` | `temporal` | `ttl_days` | Examples |
|-------------|-----------|-----------|----------|
| `injury_history` | `true` | 14 | shin soreness, knee pain, plantar fasciitis |
| `current_symptoms` | `true` | 14 | tightness, fatigue pattern, sleep disruption |
| `training_phase` | `true` | 21 | taper, base building, recovery block |
| `equipment` | `true` | 90 | new shoes, insole change |
| `race_goal` | `true` | `null` (uses `deadline_date`) | BQ attempt March 15, 20-miler race |
| `strength_metric` | `true` | 30 | deadlift 315, squat 275 |
| `life_context` | `false` | `null` | age, occupation, family |
| `health` | `false` | `null` | bone density, DEXA results |
| `race_history` | `false` | `null` | PRs, past race results |
| `preference` | `false` | `null` | taper style, race day meal |

Builder implements the mapping as a dictionary — new fact types added without code changes.

---

## 3. Soft-Expiry Sweep (daily Celery task)

Runs daily. Piggyback on existing beat schedule.

```
For each athlete_fact WHERE:
  - is_active = True
  - temporal = True
  - resolved_at IS NULL
  - soft_expired_at IS NULL
  - extracted_at + ttl_days < now()

SET soft_expired_at = now()
```

**Does NOT set `is_active = False`.** The fact remains queryable. It just enters the soft-expired state.

For `deadline_date` facts (race goals): soft-expire when `deadline_date < today` (the race happened).

---

## 4. Engine Signal Injection

### Approach: aggregator queries `athlete_fact` directly

The `aggregate_daily_inputs()` function in `correlation_engine.py` already queries `DailyCheckin`, `GarminDay`, `WorkPattern`, etc. Add a new query block that reads active and soft-expired temporal facts from `athlete_fact`.

For each day in the analysis window, synthesize these signals:

| Signal | Type | Source |
|--------|------|--------|
| `temporal_fact_active_{fact_type}` | Float 0.0-1.0 | 1.0 if active, decaying if soft-expired, 0.0 if resolved/inactive |
| `days_since_fact_onset_{fact_type}` | Integer | Days since `extracted_at` for the most recent fact of that type |
| `days_until_fact_deadline` | Integer (nullable) | Days until `deadline_date` for the nearest time-bounded fact |

**Decay function for soft-expired facts:**

```python
if soft_expired_at:
    days_past_expiry = (current_date - soft_expired_at).days
    signal = max(0.0, 1.0 - (days_past_expiry / 14))  # linear decay over 14 days post-expiry
else:
    signal = 1.0  # fully active
```

This gives the engine a 14-day gradient after soft-expiry instead of a binary cliff. An athlete who's still limping on day 15 but hasn't mentioned it produces a 0.93 signal, not 0.0. By day 28 post-expiry it reaches 0.0.

### What NOT to do

- No `DIRECTION_EXPECTATIONS` for temporal fact signals. The engine discovers relationships — we don't prescribe them.
- No `CONFOUNDER_MAP` entries. Let the engine sort it out.
- DO add `FRIENDLY_NAMES`:
  - `temporal_fact_active_injury_history` → `injury status`
  - `days_since_fact_onset_injury_history` → `days since injury reported`
  - `days_until_fact_deadline` → `days until target race`
  - (Pattern: `temporal_fact_active_{type}` → human-readable name per type)

---

## 5. Extraction Prompt — Lifecycle Awareness

The fact extraction prompt (in `ai_coach.py` or wherever `extract_athlete_facts` lives) needs three new pattern recognitions:

### 5a. Onset detection (existing, works today)
"My shin has been sore" → creates fact with `fact_key=current_injury_symptoms`, `temporal=True`, `ttl_days=14`.

### 5b. Update/re-mention detection (new)
"Shin is still bugging me" → find active fact with matching key, reset `extracted_at = now()`. This extends the TTL window. If the fact was soft-expired, clear `soft_expired_at` (re-activates it).

### 5c. Resolution detection (new)
"Shin feels fine now" / "back to 100%" / "cleared by PT" / "no more pain"

**Trigger:** Every coach message is already processed by fact extraction. Add resolution patterns to the extraction prompt:

```
If the athlete indicates a previously reported condition has RESOLVED
(e.g., "feels better", "back to normal", "no more X", "cleared by doctor"),
output:
{
  "action": "resolve",
  "fact_key": "<matching key>",
  "resolution_note": "<what they said>"
}
```

**Confidence:** No confirmation prompt for v1. If the LLM detects resolution language with a matching active temporal fact, it resolves automatically. Rationale: false resolution is recoverable (athlete re-mentions it, fact re-activates), false persistence is the current bug we're fixing.

**What triggers extraction:** Every coach message (existing behavior). No change needed — the extraction task already runs on every `_save_chat_messages`. The resolution patterns are additions to the existing extraction prompt, not a new trigger.

---

## 6. Morning Voice Injection Rules

Update the fact injection block in `home.py` (lines 1510-1539):

```python
# Only inject ACTIVE, non-soft-expired temporal facts
# and ALL active permanent facts
active_facts = (
    db.query(_AF)
    .filter(
        _AF.athlete_id == athlete_id,
        _AF.is_active == True,
        # Exclude soft-expired temporal facts from voice
        or_(
            _AF.temporal == False,
            and_(_AF.temporal == True, _AF.soft_expired_at.is_(None)),
        ),
    )
    ...
)
```

Add to the injection rules text:
```
- Temporal facts (injuries, symptoms) older than 10 days: treat as
  possibly outdated. Do NOT present as current state unless corroborated
  by today's check-in or recent activity data.
```

---

## 7. Re-Confirmation Prompt (v2, not v1)

For v1: soft-expiry + decay signal handles the gap.

For v2 (future): when a temporal fact is within 2 days of TTL expiry, the coach proactively asks: "Last time we talked, you mentioned [fact]. How's that going?" This captures re-confirmation or resolution naturally within conversation. Not in scope for this build.

---

## 8. Tests

### Unit tests

1. `test_temporal_fact_created_with_ttl` — injury fact gets `temporal=True`, `ttl_days=14`
2. `test_permanent_fact_no_ttl` — age fact gets `temporal=False`, `ttl_days=None`
3. `test_soft_expiry_sweep` — fact past TTL gets `soft_expired_at` set, `is_active` unchanged
4. `test_soft_expiry_not_resolved` — soft-expired fact has no `resolved_at`
5. `test_resolution_sets_resolved_at` — explicit resolution sets timestamp
6. `test_re_mention_resets_extracted_at` — re-mention refreshes TTL window
7. `test_re_mention_clears_soft_expiry` — re-mention of soft-expired fact re-activates
8. `test_deadline_fact_expires_after_date` — race goal soft-expires after race date
9. `test_decay_signal_calculation` — soft-expired 7 days ago produces 0.5 signal
10. `test_decay_signal_floors_at_zero` — 14+ days past soft-expiry produces 0.0
11. `test_engine_sees_active_fact_signal` — active injury fact produces 1.0 in input matrix
12. `test_engine_sees_decaying_signal` — soft-expired fact produces fractional signal
13. `test_engine_no_signal_for_resolved` — resolved fact produces 0.0
14. `test_voice_excludes_soft_expired` — morning voice doesn't inject soft-expired facts
15. `test_voice_includes_active_temporal` — morning voice does inject active temporal facts
16. `test_days_until_deadline_signal` — race goal 5 days out produces signal value 5

### Manual integration test (builder runs once)

17. Insert synthetic injury fact for founder backdated 10 days:
    ```sql
    INSERT INTO athlete_fact (athlete_id, fact_type, fact_key, fact_value,
      temporal, ttl_days, extracted_at, is_active)
    VALUES (<founder_id>, 'injury_history', 'test_injury', 'synthetic test injury',
      true, 14, now() - interval '10 days', true);
    ```
18. Run one correlation sweep for founder. Verify `temporal_fact_active_injury_history` = 1.0 and `days_since_fact_onset_injury_history` = 10 appear in the input matrix.
19. Set `soft_expired_at = now() - interval '7 days'` on the fact. Re-run sweep. Verify signal = 0.5.
20. Delete the synthetic fact.

---

## 9. What This Enables (without prescribing findings)

The engine gets new input signals. What it discovers is up to the data. Possible examples (we don't know and don't hardcode):

- Conditions and training patterns that precede injury onset
- Conditions that correlate with faster or slower resolution
- Whether approaching a race deadline correlates with efficiency changes
- Whether shoe age (equipment fact) correlates with biomechanical shifts
- Whether strength metric changes precede performance changes

We surface whatever it finds through the existing fingerprint and morning voice paths. No special UI. No prescribed narratives.

---

## 10. Build Phases

| Phase | What | Files |
|-------|------|-------|
| 1 | Migration + schema | `models.py`, new alembic migration |
| 2 | Backfill existing facts with `temporal` flag | Migration data step |
| 3 | Soft-expiry sweep task | `tasks/`, `celerybeat_schedule.py` |
| 4 | Extraction prompt — update/resolution detection | `services/fact_extraction.py` or wherever extraction lives |
| 5 | Engine signal injection | `services/correlation_engine.py` `aggregate_daily_inputs()` |
| 6 | `FRIENDLY_NAMES` for new signals | `services/n1_insight_generator.py` |
| 7 | Morning voice injection filter | `routers/home.py` |
| 8 | Tests (16 automated + 4 manual) | `tests/test_temporal_fact_lifecycle.py` |

---

## Acceptance Criteria

1. No temporal fact surfaces in morning voice after its TTL expires
2. Soft-expired facts produce a decaying (not binary) signal to the engine
3. Resolved facts produce 0.0 signal and never appear in voice
4. Re-mentioning a fact resets its TTL window, even if soft-expired
5. Resolution detection works without athlete confirmation prompt
6. `days_until_fact_deadline` signal exists for time-bounded facts
7. No `DIRECTION_EXPECTATIONS` hardcoded for any temporal fact signal
8. Manual integration test passes with synthetic data
9. 16 automated tests pass
