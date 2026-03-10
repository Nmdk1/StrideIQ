# Athlete Fact Extraction — Coach Memory Layer 1 (v2)

**Date:** March 10, 2026
**Status:** Approved — hardened after external advisor review
**Horizon:** 2 (Proof of Moat) — early, right after guardrail confirmed stable
**Estimated effort:** 3-4 days + 1 day backfill
**Dependency:** Experience Guardrail (2g) — shipped March 10, 2026
**Supersedes:** `ATHLETE_FACT_EXTRACTION_SPEC.md` (v1)

---

# Fact Extraction Layer 1 — v2 Decisions (Locked)

## Gating fixes before builder implementation

1. **Concurrency safety (P0):**
   - Add partial unique index:
     - `UNIQUE (athlete_id, fact_key) WHERE is_active = true`
   - Upsert handles `IntegrityError` by re-querying active row and skipping duplicate inserts.

2. **Extraction contract clarity (P0):**
   - Layer 1 is **athlete-stated only**.
   - Remove `coach_inferred` from prompt outputs and runtime handling.
   - `confidence` stored as a single value: `athlete_stated`.

3. **Taxonomy catch-all (P0):**
   - Add `other` to extraction prompt enum.
   - Keep DB `fact_type` as free text (`Text`) for forward compatibility.

4. **Incremental extraction only (P1):**
   - Add `last_extracted_msg_count` to `CoachChat`.
   - On trigger, process only user messages after this index.
   - After successful commit, update `last_extracted_msg_count`.

## Additional v1 constraints

5. **Prompt injection cap (P1):**
   - Max 15 active facts injected.
   - Priority: `confirmed_by_athlete DESC`, then `extracted_at DESC`.

6. **Confirmation flow simplification (P1):**
   - No automatic confirmation-detection heuristics in v1.
   - `confirmed_by_athlete` only updated on explicit athlete confirmation flow.
   - Facts remain usable even when unconfirmed.

7. **Backfill safety (P1):**
   - No `.all()` full-load scans.
   - Use chunking (`yield_per` or pagination) + `--resume-from-chat-id`.
   - Idempotent reruns required.

8. **Guardrail assertion precision (P2 hardening):**
   - Superseded-value leak check must be key-scoped, not raw global substring match.
   - Flag only when stale value appears in proximity to fact key/friendly key context.

9. **Governance note (P2):**
   - Add explicit beta note for medical-adjacent facts retention/deletion policy before public launch.

---

## Context

StrideIQ is an N=1 running intelligence platform. Athletes connect Garmin/Strava, the system runs a correlation engine against their data, and surfaces personalized findings. There's an AI coach chat feature where athletes have conversations about their training.

The system has a `CoachChat` table that stores all conversation messages as a JSONB array. The coach uses these messages during that conversation — but after the session ends, the data is forgotten. No other system reads it.

A beta tester recently told the coach his DEXA scan results (bone density T-score +3.2), his deadlift (315 lbs), his squat (275 lbs). The coach gave a deeply personalized analysis connecting his bone density to his lift history, explaining a 7-pound scale discrepancy, and assessing stress fracture risk. Then the system forgot all of it.

This spec adds permanent memory.

---

## Problem

Athletes tell the coach meaningful things — DEXA results, strength PRs, injury history, personal preferences, life context. The coach uses these facts in that conversation. Then forgets them. Every future conversation, every morning voice (daily home page briefing), every finding is generated without knowledge of what the athlete voluntarily shared.

The data already exists in `CoachChat.messages` (JSONB array). It sits inert. No other system reads it.

---

## Solution

After each coach conversation, a Celery task extracts structured facts from **new** messages and stores them in an `athlete_fact` table. These facts become permanent context for all surfaces — morning voice, future coach conversations, investigations, findings.

Historical conversations are backfilled on first deploy, so nothing already shared is lost.

---

## Database

### New table: `athlete_fact`

```python
class AthleteFact(Base):
    __tablename__ = "athlete_fact"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)

    # What
    fact_type = Column(Text, nullable=False)      # Free text for forward compat; extraction prompt suggests categories
    fact_key = Column(Text, nullable=False)        # snake_case identifier, e.g. "deadlift_1rm_lbs"
    fact_value = Column(Text, nullable=False)      # String value, e.g. "315"
    numeric_value = Column(Float, nullable=True)   # Queryable numeric form when applicable

    # Provenance
    confidence = Column(Text, nullable=False, server_default="athlete_stated")  # v1: always "athlete_stated"
    source_chat_id = Column(UUID(as_uuid=True), ForeignKey("coach_chat.id"), nullable=False)
    source_excerpt = Column(Text, nullable=False)  # Exact athlete quote

    # Confirmation
    confirmed_by_athlete = Column(Boolean, nullable=False, default=False)

    # Lifecycle
    extracted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    superseded_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("ix_athlete_fact_athlete_active", "athlete_id", "is_active"),
        Index("ix_athlete_fact_key_lookup", "athlete_id", "fact_key"),
        # P0 concurrency safety: exactly one active fact per athlete+key
        Index(
            "uq_athlete_fact_active_key",
            "athlete_id", "fact_key",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )
```

**Governance note:** Medical-adjacent facts (`blood_pressure`, `medications`, `cholesterol`) are acceptable during founder-only beta. Before public launch, add explicit retention policy (max age, athlete-triggered deletion endpoint, and access audit logging). This is tracked debt, not blocking for v1.

### Schema change to `CoachChat`

Add incremental extraction tracking:

```python
# In CoachChat model (existing table)
last_extracted_msg_count = Column(Integer, nullable=True, default=0)
```

This tracks how many messages have already been processed for fact extraction. On each trigger, only messages after this index are sent to the extraction prompt.

**Migration:** Add column with `server_default=0`, nullable, no data backfill needed (null = never extracted = process all).

### Fact types (prompt guidance, not DB constraint)

| `fact_type` | Examples |
|-------------|----------|
| `body_composition` | `dexa_bone_density_t_score`, `dexa_body_fat_pct`, `weight_lbs`, `height_in` |
| `strength_pr` | `deadlift_1rm_lbs`, `squat_1rm_lbs`, `bench_1rm_lbs` |
| `injury_history` | `left_knee_issue`, `plantar_fasciitis_history`, `stress_fracture_history` |
| `preference` | `preferred_run_time`, `preferred_long_run_day`, `caffeine_before_runs` |
| `life_context` | `occupation`, `age`, `years_running`, `cross_training_type` |
| `race_history` | `marathon_pr`, `half_marathon_pr`, `5k_pr` |
| `health` | `resting_hr_manual`, `blood_pressure`, `cholesterol` |
| `other` | Anything that doesn't fit the above categories |

The database stores `fact_type` as free text. The extraction prompt suggests these categories but allows `other` as a catch-all. No validation on insert — forward-compatible with new categories.

---

## Extraction Logic

### Post-conversation extraction task

**File:** `apps/api/tasks/fact_extraction_task.py`

```python
from sqlalchemy.exc import IntegrityError

@celery_app.task(name="tasks.extract_athlete_facts", bind=True, max_retries=2)
def extract_athlete_facts(self, athlete_id: str, chat_id: str):
    """Extract structured facts from NEW messages in a coach conversation."""
    db = SessionLocal()
    try:
        chat = db.query(CoachChat).filter(CoachChat.id == UUID(chat_id)).first()
        if not chat or not chat.messages:
            return

        # Incremental: only process messages after last extraction point
        last_idx = chat.last_extracted_msg_count or 0
        all_messages = chat.messages or []

        if last_idx >= len(all_messages):
            return  # Nothing new

        new_messages = all_messages[last_idx:]
        user_messages = [m for m in new_messages if m.get("role") == "user"]

        if not user_messages:
            # Update index even if no user messages (assistant-only additions)
            chat.last_extracted_msg_count = len(all_messages)
            db.commit()
            return

        user_text = "\n".join(m["content"] for m in user_messages)
        extracted = _run_extraction(user_text)

        for fact in extracted:
            _upsert_fact(db, UUID(athlete_id), UUID(chat_id), fact)

        # Update extraction checkpoint
        chat.last_extracted_msg_count = len(all_messages)
        db.commit()

    except Exception as e:
        db.rollback()
        logger.error("Fact extraction failed for chat %s: %s", chat_id, e)
        raise self.retry(exc=e)
    finally:
        db.close()
```

### Extraction prompt

```
You are extracting structured facts from an athlete's messages to their running coach.

Extract any concrete, specific factual claims the athlete made about:
- Their body (weight, height, body composition, bone density, body fat %)
- Their strength (lift PRs, max weights, rep schemes)
- Their injury history (past injuries, current pain, recovery status)
- Their preferences (when they like to run, what they eat before runs, etc.)
- Their life context (age, occupation, years running, other sports)
- Their race history (PRs, recent race results, upcoming goals)
- Their health (resting heart rate, blood pressure, medications, etc.)
- Anything else specific and factual that would be useful coaching context

For each fact, return:
- fact_type: one of [body_composition, strength_pr, injury_history, preference, life_context, race_history, health, other]
- fact_key: a snake_case identifier (e.g., "dexa_bone_density_t_score", "deadlift_1rm_lbs")
- fact_value: the value as a string (e.g., "3.2", "315", "before 8am")
- numeric_value: the numeric value if applicable, else null
- source_excerpt: the exact quote from the athlete that contains this fact

Rules:
- Only extract facts the ATHLETE explicitly stated. Do not infer or deduce facts.
- Only extract concrete, specific facts. Do not extract opinions, feelings, or vague statements.
- If the athlete says "I deadlift around 300-315", use the higher value (315) and note the range in source_excerpt.
- Use consistent fact_key naming: lowercase snake_case, include units where relevant (e.g., _lbs, _in, _pct).
- If the same fact appears multiple times with different values, extract only the most recent/specific version.

Return as a JSON array. If no facts found, return [].
```

Note: No `confidence` field in the extraction output. Layer 1 is athlete-stated only. The `confidence` column is always set to `"athlete_stated"` at insert time.

### Upsert with Concurrency Safety (Savepoint-safe)

```python
def _upsert_fact(db, athlete_id: UUID, chat_id: UUID, extracted: dict):
    """
    Insert a new fact, superseding any existing fact with the same key.
    
    Handles concurrent inserts via the partial unique index
    (uq_athlete_fact_active_key) without rolling back the parent transaction.
    Uses a nested transaction (savepoint) for each candidate insert.
    """
    existing = (
        db.query(AthleteFact)
        .filter(
            AthleteFact.athlete_id == athlete_id,
            AthleteFact.fact_key == extracted["fact_key"],
            AthleteFact.is_active == True,
        )
        .first()
    )

    if existing:
        if existing.fact_value == extracted["fact_value"]:
            return  # Same value, skip

        # Different value: supersede old, insert new
        existing.superseded_at = func.now()
        existing.is_active = False
        logger.info(
            "Superseding athlete fact %s: %s -> %s",
            extracted["fact_key"], existing.fact_value, extracted["fact_value"],
        )

    new_fact = AthleteFact(
        athlete_id=athlete_id,
        fact_type=extracted["fact_type"],
        fact_key=extracted["fact_key"],
        fact_value=extracted["fact_value"],
        numeric_value=extracted.get("numeric_value"),
        confidence="athlete_stated",
        source_chat_id=chat_id,
        source_excerpt=extracted["source_excerpt"],
    )

    # Savepoint scope prevents rollback of prior successful upserts in this chat.
    with db.begin_nested():
        try:
            db.add(new_fact)
            db.flush()
        except IntegrityError:
            # Savepoint rollback only; parent transaction remains intact.
            # Race condition: another task inserted first. Re-query winner.
            winner = (
                db.query(AthleteFact)
                .filter(
                    AthleteFact.athlete_id == athlete_id,
                    AthleteFact.fact_key == extracted["fact_key"],
                    AthleteFact.is_active == True,
                )
                .first()
            )
            if winner and winner.fact_value == extracted["fact_value"]:
                logger.debug("Concurrent insert resolved: same value, skipping %s", extracted["fact_key"])
            elif winner:
                logger.warning(
                    "Concurrent insert conflict for %s: winner=%s, ours=%s — keeping winner",
                    extracted["fact_key"], winner.fact_value, extracted["fact_value"],
                )
            # In both cases: do nothing. The winner's value stands.
```

---

## Trigger Point

**File:** `apps/api/services/ai_coach.py`, in `_save_chat_messages` (line ~1734)

After saving user message + assistant response to `CoachChat`, enqueue the extraction task:

```python
def _save_chat_messages(self, athlete_id: UUID, user_message: str, assistant_response: str) -> None:
    # ... existing save logic ...

    # Trigger fact extraction (fire-and-forget, async)
    from tasks.fact_extraction_task import extract_athlete_facts
    extract_athlete_facts.delay(str(athlete_id), str(chat.id))
```

The extraction runs asynchronously. The coach response is not delayed.

---

## Backfill Historical Conversations

**Script:** `scripts/backfill_athlete_facts.py`

```python
"""
One-time backfill: extract facts from all historical CoachChat conversations.

Usage:
    python scripts/backfill_athlete_facts.py
    python scripts/backfill_athlete_facts.py --resume-from-chat-id <uuid>

Idempotent: safe to re-run. The upsert logic skips existing facts with
matching values. Processes chats in chronological order so supersession
is correct (later values override earlier ones).
"""

import argparse
from uuid import UUID

BATCH_SIZE = 50

def backfill(resume_from: str = None):
    db = SessionLocal()
    try:
        query = (
            db.query(CoachChat)
            .filter(CoachChat.messages.isnot(None))
            .order_by(CoachChat.created_at.asc(), CoachChat.id.asc())
        )

        if resume_from:
            resume_chat = db.query(CoachChat).filter(CoachChat.id == UUID(resume_from)).first()
            if resume_chat:
                # Deterministic resume: strictly after (created_at, id) tuple.
                # Avoids timestamp-collision reprocessing ambiguity.
                query = query.filter(
                    (CoachChat.created_at > resume_chat.created_at) |
                    (
                        (CoachChat.created_at == resume_chat.created_at) &
                        (CoachChat.id > resume_chat.id)
                    )
                )

        processed = 0
        skipped = 0
        facts_found = 0

        for chat in query.yield_per(BATCH_SIZE):
            user_messages = [m for m in chat.messages if m.get("role") == "user"]
            if not user_messages:
                skipped += 1
                continue

            user_text = "\n".join(m["content"] for m in user_messages)
            extracted = _run_extraction(user_text)

            for fact in extracted:
                _upsert_fact(db, chat.athlete_id, chat.id, fact)
                facts_found += 1

            # Mark as fully extracted
            chat.last_extracted_msg_count = len(chat.messages)
            processed += 1

            # Checkpoint every batch
            if processed % BATCH_SIZE == 0:
                db.commit()
                logger.info(
                    "Backfill checkpoint: %d chats processed, %d facts found, last chat_id=%s",
                    processed, facts_found, chat.id,
                )

        db.commit()
        logger.info(
            "Backfill complete: %d chats processed, %d skipped, %d facts extracted",
            processed, skipped, facts_found,
        )

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume-from-chat-id", type=str, default=None)
    args = parser.parse_args()
    backfill(resume_from=args.resume_from_chat_id)
```

**Key properties:**
- Chronological order (`created_at ASC`) so supersession is correct
- `yield_per(50)` — no full table load
- Checkpoints every 50 chats (commit + log with last `chat_id`)
- `--resume-from-chat-id` for crash recovery (strict tuple resume, no timestamp ambiguity)
- Idempotent: upsert skips matching values, sets `last_extracted_msg_count`
- Run once after deploy

---

## Consumer Integration

### Morning voice prompt (capped injection)

In `apps/api/routers/home.py`, in the prompt assembly for `generate_coach_home_briefing`:

```python
MAX_INJECTED_FACTS = 15

active_facts = (
    db.query(AthleteFact)
    .filter(
        AthleteFact.athlete_id == athlete_id,
        AthleteFact.is_active == True,
    )
    .order_by(
        AthleteFact.confirmed_by_athlete.desc(),  # Confirmed facts first
        AthleteFact.extracted_at.desc(),           # Then most recent
    )
    .limit(MAX_INJECTED_FACTS)
    .all()
)

if active_facts:
    facts_section = "=== ATHLETE-STATED FACTS (from coach conversations) ===\n"
    for f in active_facts:
        facts_section += f"- {f.fact_key}: {f.fact_value} (stated {f.extracted_at.strftime('%b %d')})\n"
    facts_section += (
        "\nRULES FOR USING THESE FACTS:\n"
        "- Use these facts to INFORM your reasoning, connections, and interpretations.\n"
        "- Do NOT recite facts back to the athlete. They already know their own weight, "
        "their own deadlift max, their own T-score. Telling them what they told you is not coaching.\n"
        "- DO use facts to CONNECT and CONTEXTUALIZE. Example: 'Your scale discrepancy is "
        "explained by your bone density' uses two facts together to produce an insight "
        "without parroting either number.\n"
        "- The athlete should feel the system THINKS with what they shared, not that it "
        "memorized and repeated it.\n"
    )
    prompt_parts.append(facts_section)
```

### Coach conversation context (capped injection)

In `apps/api/services/ai_coach.py`, in the system prompt assembly:

```python
MAX_INJECTED_FACTS = 15

active_facts = (
    self.db.query(AthleteFact)
    .filter(
        AthleteFact.athlete_id == athlete_id,
        AthleteFact.is_active == True,
    )
    .order_by(
        AthleteFact.confirmed_by_athlete.desc(),
        AthleteFact.extracted_at.desc(),
    )
    .limit(MAX_INJECTED_FACTS)
    .all()
)

if active_facts:
    facts_context = "Known athlete facts (from previous conversations):\n"
    for f in active_facts:
        facts_context += f"- {f.fact_key}: {f.fact_value}\n"
    facts_context += (
        "\nYou already know these facts. Do not ask the athlete to repeat them. "
        "Do not recite them back — the athlete knows their own body. "
        "Use them to reason, connect patterns, and provide context the athlete "
        "could not produce on their own.\n"
    )
```

### Fact confirmation (v1 — simplified)

In v1, `confirmed_by_athlete` is NOT set automatically. It is only updated through an explicit confirmation pathway (e.g., a future admin/athlete endpoint or manual DB update). No heuristic detection of confirmation in assistant responses.

Facts are usable in prompts regardless of confirmation status. Confirmation affects injection priority only (confirmed facts sort first).

---

## Experience Guardrail Integration

### Assertion #25: No stale/superseded athlete facts in coach output

- **Check:** For each `AthleteFact` where `is_active = False` (superseded), build a key-scoped regex pattern. Check whether the superseded `fact_value` appears within a proximity window of a friendly version of `fact_key` using numeric token boundaries (e.g., "deadlift" near standalone `315`, not `1315`).
- **Implementation:**

```python
def _assert_no_superseded_facts(self, coach_texts: list):
    superseded = (
        self.db.query(AthleteFact)
        .filter(
            AthleteFact.athlete_id == self.athlete_id,
            AthleteFact.is_active == False,
            AthleteFact.superseded_at.isnot(None),
        )
        .all()
    )

    for fact in superseded:
        # Get the current active value for this key
        current = (
            self.db.query(AthleteFact)
            .filter(
                AthleteFact.athlete_id == self.athlete_id,
                AthleteFact.fact_key == fact.fact_key,
                AthleteFact.is_active == True,
            )
            .first()
        )
        if not current or current.fact_value == fact.fact_value:
            continue  # No conflict possible

        # Build key-scoped check: look for old value near the key context.
        # Numeric values must match as standalone numeric tokens.
        key_friendly = fact.fact_key.replace("_", " ").replace("1rm", "").replace("lbs", "").strip()
        old_val = str(fact.fact_value).strip()
        cur_val = str(current.fact_value).strip()
        old_pat = re.compile(rf"(?<!\\d){re.escape(old_val)}(?!\\d)")
        cur_pat = re.compile(rf"(?<!\\d){re.escape(cur_val)}(?!\\d)")
        for text in coach_texts:
            text_lower = text.lower()
            key_pos = text_lower.find(key_friendly.lower())
            if key_pos == -1:
                continue
            # Check 50-char window around key mention for the old value
            window = text_lower[max(0, key_pos - 50):key_pos + len(key_friendly) + 50]
            if old_pat.search(window) and not cur_pat.search(window):
                self.results.append(AssertionResult(
                    id=25, name="no_superseded_facts_in_coach",
                    category="trust_integrity", passed=False, skipped=False,
                    detail=f"Superseded {fact.fact_key}={fact.fact_value} found near key mention; current is {current.fact_value}",
                    endpoint="coach_briefing", severity="high",
                ))
                return

    self.results.append(AssertionResult(
        id=25, name="no_superseded_facts_in_coach",
        category="trust_integrity", passed=True, skipped=False,
        detail="No superseded fact values found in coach output",
        endpoint="coach_briefing", severity="high",
    ))
```

- **Pass:** No superseded fact values found in key-scoped context.
- **Fail:** Old value appears near key mention without current value present.
- **Severity:** high

---

## Tests

### Extraction tests
1. `test_extraction_from_user_messages` — user says "I deadlift 315" → `AthleteFact(fact_key="deadlift_1rm_lbs", fact_value="315", confidence="athlete_stated")`
2. `test_extraction_ignores_coach_messages` — only user messages in the new message window are sent to extraction
3. `test_extraction_produces_valid_json` — extraction prompt returns parseable JSON array
4. `test_extraction_other_category` — unusual fact gets `fact_type="other"` (not forced into wrong category)

### Upsert tests
5. `test_upsert_same_value_skips` — same key, same value → no new row
6. `test_upsert_different_value_supersedes` — same key, new value → old row `is_active=False` + `superseded_at` set, new row `is_active=True`
7. `test_upsert_preserves_history` — after supersession, both rows exist (one active, one superseded)
8. `test_upsert_concurrent_insert_handled` — simulate `IntegrityError` from partial unique index → re-query and skip gracefully
9. `test_upsert_integrityerror_does_not_rollback_prior_facts` — savepoint rollback does not erase earlier successful upserts in same run

### Incremental extraction tests
10. `test_incremental_only_new_messages` — chat has 10 messages, `last_extracted_msg_count=8` → only messages 9-10 sent to extraction
11. `test_incremental_updates_checkpoint` — after extraction, `last_extracted_msg_count` equals total message count
12. `test_incremental_skips_when_no_new` — `last_extracted_msg_count == len(messages)` → task returns early

### Backfill tests
13. `test_backfill_chronological_order` — earlier value superseded by later value, not vice versa
14. `test_backfill_sets_checkpoint` — after backfill, `last_extracted_msg_count` set on each chat
15. `test_backfill_idempotent` — running backfill twice produces same result (no duplicates)
16. `test_backfill_resume_from_chat_id` — strict tuple resume skips exactly up-to resume chat
17. `test_backfill_resume_handles_same_timestamp_chats` — deterministic ordering by `(created_at, id)`

### Consumer tests
18. `test_facts_injected_into_morning_voice_prompt` — active facts appear in prompt, capped at 15
19. `test_superseded_facts_not_injected` — superseded facts excluded from prompt
20. `test_injection_priority_order` — confirmed facts sort before unconfirmed, then by recency
21. `test_injection_cap_respected` — 20 active facts → only 15 injected

### Integration tests
22. `test_extraction_task_fires_after_chat_save` — `_save_chat_messages` enqueues `extract_athlete_facts`
23. `test_no_extraction_on_empty_user_messages` — chat with only assistant messages → no extraction, checkpoint still updated
24. `test_guardrail_assertion_25_catches_superseded` — mock superseded fact with old value near key mention → assertion fails
25. `test_guardrail_assertion_25_ignores_unrelated_numbers` — "315" in a pace context does not trigger false positive
26. `test_guardrail_assertion_25_numeric_boundary` — `315` does not match `1315`

---

## Acceptance Criteria

- [ ] `athlete_fact` table created via Alembic migration with partial unique index `uq_athlete_fact_active_key`
- [ ] `last_extracted_msg_count` column added to `coach_chat` table via migration
- [ ] Extraction task fires after every coach conversation save (async, non-blocking)
- [ ] Extraction processes only new messages (incremental, not full-chat rerun)
- [ ] Extraction prompt includes `other` as catch-all category
- [ ] No `coach_inferred` logic — all facts stored as `athlete_stated`
- [ ] Upsert correctly supersedes: same key + different value → old row deactivated, new row inserted
- [ ] Upsert skips duplicates: same key + same value → no new row
- [ ] Upsert handles `IntegrityError` from concurrent inserts gracefully
- [ ] Backfill script processes historical conversations chronologically with `yield_per` chunking
- [ ] Backfill supports `--resume-from-chat-id` for crash recovery
- [ ] Backfill is idempotent (safe to re-run)
- [ ] Active facts injected into morning voice prompt (max 15, priority: confirmed then recent)
- [ ] Active facts injected into coach system prompt (max 15, same priority)
- [ ] Superseded facts excluded from both prompts
- [ ] Experience Guardrail assertion #25 added with key-scoped matching (not raw substring)
- [ ] Savepoint-safe upsert: `IntegrityError` does not rollback prior successful inserts in same extraction run
- [ ] Backfill resume uses deterministic tuple boundary `(created_at, id)` (strictly after resume point)
- [ ] Guardrail #25 uses numeric token boundaries (no `315` vs `1315` false positives)
- [ ] All 26 tests pass
- [ ] Governance comment in model for medical-adjacent facts retention policy

---

## File Layout

```
apps/api/
├── alembic/versions/
│   └── add_athlete_fact_table.py              # Migration: athlete_fact + coach_chat column
├── models.py                                   # AthleteFact model + CoachChat column addition
├── tasks/
│   └── fact_extraction_task.py                 # Celery task: extract_athlete_facts
├── services/
│   └── ai_coach.py                            # Modified: trigger extraction after save
├── routers/
│   └── home.py                                # Modified: inject facts into morning voice prompt
├── services/
│   └── experience_guardrail.py                # Modified: add assertion #25
├── tests/
│   └── test_fact_extraction.py                # 26 tests
scripts/
└── backfill_athlete_facts.py                  # One-time backfill with resume support
```

---

## What This Does NOT Do

- Does not extract facts from coach responses (only athlete statements)
- Does not replace the coach's in-session memory (that uses `CoachChat.messages` directly)
- Does not feed the investigation engine yet (Layer 3 — future)
- Does not use embeddings/RAG (Layer 2 — future)
- Does not modify the coach's behavior during conversation (only post-conversation extraction)
- Does not automatically detect confirmation in assistant responses (v1 — simplified)
- Does not store `coach_inferred` facts (Layer 1 is athlete-stated only)

---

## Future Layers (not in this build)

**Layer 2: RAG for Narrative Context** — Store conversation chunks with embeddings (pgvector). Retrieve relevant past conversations when generating briefings. Captures qualitative observations that don't fit a key-value schema ("my left knee always hurts after hill repeats over 6% grade").

**Layer 3: Investigation Integration** — Numeric facts from Layer 1 become signals in the correlation engine. Brian's T-score becomes a variable that can be correlated against recovery patterns. The nightly AutoInvestigation loop can include athlete-stated facts as inputs.
