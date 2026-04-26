# Builder Instructions — Coach V2 Athlete Truth Layer

**Builder:** GPT 5.5 high.
**Spec:** `docs/specs/COACH_RUNTIME_V2_ARTIFACT_9_ATHLETE_TRUTH_LAYER.md` (must be marked LOCKED before this work begins).
**Reviewer at gates:** Opus 4.7 + founder.
**Stop condition:** Phase B10 comparison harness output committed to repo. **Do not run founder canary.** Founder runs canary after review.

---

## 0. Read order (mandatory before any code)

Read these in order. If you cannot reference specific content from them in your work, you have not read them.

1. `docs/FOUNDER_OPERATING_CONTRACT.md` — non-negotiable rules.
2. `docs/specs/COACH_RUNTIME_V2_ARTIFACT_9_ATHLETE_TRUTH_LAYER.md` — the spec you are building.
3. `docs/specs/COACH_RUNTIME_V2_ARTIFACT_8_CANARY_ROLLBACK.md` — rollout discipline.
4. `docs/specs/COACH_RUNTIME_V2_LOCKED_ARTIFACTS.md` — pointer to locked artifacts (1, 5, 6, 7, 8, 9).
5. `docs/specs/REPLAY_RUBRIC_SPEC.md` — Artifact 7 case format.
6. `apps/api/services/coaching/_eval.py` — existing Phase 8 + Artifact 7 evaluation framework.
7. `apps/api/services/coaching/runtime_v2.py`, `runtime_v2_packet.py`, `_llm.py`, `core.py`, `_guardrails.py` — current V2 surface to extend/replace.
8. `docs/references/ROCHE_SWAP_*.md`, `DAVIS_*.md`, `GREEN_*.md`, `ADVANCED_EXERCISE_PHYSIOLOGY_*.md`, `COE_STYLE_*.md`, `SSMAX_*.md` — voice corpus (Artifact 9 §7.3). **You may not author coaching voice examples.** Only the founder selects snippets from these docs.

---

## 1. Operating constraints (non-negotiable)

- **Founder Operating Contract applies.** Read it. Every rule binds.
- **V2 visible flag stays OFF in production** through every phase below. Production athletes do not see V2 output during this build. Shadow flag also stays OFF — do not enable shadow.
- **Scoped commits only.** Never `git add -A`. Each commit covers one logical unit. Commit messages follow conventional commits: `feat(coach):`, `fix(coach):`, `test(coach):`, `chore(coach):`, `docs(coach):`.
- **Tests must pass locally before every push.** No exceptions.
- **CI must be green before starting the next phase.** If CI fails, fix on the same branch, push again, wait for green. Do not move forward on red.
- **Working tree clean at the end of every phase.** No untracked files left behind. No uncommitted changes.
- **No new OAuth or third-party permission scopes** without founder approval. Specs may describe future scopes; code waits.
- **No `git push --force`. No `git rebase -i`. No history rewrites.** No `--no-verify`.
- **No `git commit --amend`** unless the immediately prior commit was created by you in this session AND has not been pushed AND a pre-commit hook auto-modified files. Otherwise create a new commit.
- **No code that wakes the LLM during shadow.** Shadow mode in production stays OFF; you are not adding new shadow paths.
- **You may not author coaching voice examples or coach response samples.** Voice corpus comes from `docs/references/` and founder selection. The system prompt embeds voice snippets verbatim from a file the founder provides; until that file exists, leave the voice-corpus block in the prompt as a placeholder marker (see Phase B7).
- **You may not modify locked artifacts** (1, 5, 6, 7, 8, 9, REPLAY_RUBRIC_SPEC, FOUNDER_OPERATING_CONTRACT).
- **No commits to `main` directly.** Work on a single feature branch: `feat/v2-athlete-truth-layer`. Open a PR at end. Founder/Opus reviews and merges.
- **Show evidence, not claims.** At the end of each phase, paste the relevant test output and CI status into the PR description as you progress. Do not say "tests pass" without paste.

---

## 2. Branch + PR strategy

- Create branch from latest `main`: `git checkout -b feat/v2-athlete-truth-layer`.
- Push branch on first commit: `git push -u origin feat/v2-athlete-truth-layer`.
- Open a draft PR titled `feat(coach): V2 Athlete Truth Layer (Artifact 9 implementation)` immediately after first push.
- PR description: link Artifact 9, list ten phases, mark each as `[ ] B1: ledger` etc. Update as you progress. Include a `Test plan` checklist.
- Mark PR ready for review only at the end of Phase B10 with the harness output committed.
- Do not merge the PR. Founder/Opus merge after review.

---

## 3. Phase loop discipline

For each phase B1–B10, the loop is:

1. **Plan** — re-read Artifact 9 sections relevant to this phase. Identify files to add/edit. Identify tests to add.
2. **Build** — make the changes. Keep changes scoped to this phase.
3. **Test locally** — run the relevant test suite. Fix until green.
4. **Lint** — `ReadLints` on edited files. Fix any errors you introduced.
5. **Commit** — scoped commit, conventional message, references the phase ID.
6. **Push** — `git push origin feat/v2-athlete-truth-layer`.
7. **Watch CI** — `gh run watch` or equivalent. Wait for green.
8. **If CI red** — read failure logs, fix on same branch, repeat steps 3–7.
9. **Update PR description** — check off the phase, paste test output evidence.
10. **Move to next phase only after CI green and PR description updated.**

You may chain multiple commits within one phase. Each commit individually must leave tests green and tree clean. Phases never overlap.

---

## 4. The phases

### Phase B1 — Athlete Fact Ledger (foundation)

**Spec sections:** Artifact 9 §3.

**Build:**
- Alembic migration creating `athlete_facts` table (one row per athlete, jsonb payload) and `athlete_facts_audit` table (append-only). Include indexes on `athlete_id`, `(athlete_id, field)` for audit table. Foreign keys to `athletes`.
- ORM models in `apps/api/models/athlete_facts.py` (or extend existing `models/__init__.py` per project convention). Include `AthleteFacts` and `AthleteFactsAudit`.
- Service layer in `apps/api/services/coaching/ledger.py`:
  - `get_ledger(db, athlete_id) -> AthleteFacts`
  - `set_fact(db, athlete_id, field, value, source, confidence, asserted_at) -> AuditEntry`
  - `correct_fact(db, athlete_id, field, new_value, reason)` — appends prior to audit, writes new value.
  - `confirm_fact(db, athlete_id, field)` — resets `confirm_after`.
  - Conflict resolution per §3.3. Higher precedence wins; same precedence newer wins; conflict between `athlete_stated` and any other source returns a `PendingConflict` that the next coach turn must surface.
  - Staleness scheduler returning fields with `confirm_after` <= now.
- Permission policy redaction respected per existing surface.

**Tests** (`apps/api/tests/test_ledger.py`):
- Roundtrip: write/read/correct/confirm.
- Conflict resolution per precedence level (4 cases).
- Staleness returns expired fields.
- Audit trail append-only (mutation rejected).
- Permission redaction respected for sensitive fields.
- Migration up/down clean.

**Commit shape:**
- `feat(coach): add athlete_facts ledger schema and migration`
- `feat(coach): add ledger service layer`
- `test(coach): cover ledger semantics`

**Acceptance:** all tests green locally and in CI. Migration runs clean against fresh DB and existing DB.

---

### Phase B2 — Conversation Extraction + Override Semantics

**Spec sections:** Artifact 9 §3.6, §3.3.

**Build:**
- Deterministic regex extraction in `apps/api/services/coaching/ledger_extraction.py`:
  - Patterns for stated facts: weekly volume ("I'm a 60mpw runner", "I run 50 miles a week"), age, weight, target event, injury, cut active, etc.
  - Each pattern returns `ProposedFact{field, value, source, confidence: athlete_stated}`.
- LLM extraction supplement: when deterministic patterns miss, optional Kimi-K2.6 extraction call (low confidence `inferred`). Off-by-default flag; not used in v1 unless deterministic extraction proves insufficient. Wire the code path; gate behind a setting.
- `same_turn_overrides` semantics fix in `runtime_v2_packet.py`:
  - Replace `override_value: True` boolean with `{value: <asserted_value>, duration: "current_turn" | "standing"}`.
  - Standing overrides write to ledger via `set_fact` with `confidence: athlete_stated`.
  - Current-turn overrides do not write to ledger; surface in packet only.
- Wire extraction into `AICoach.chat()` so that on every turn, `extract_facts_from_turn()` runs and populates the ledger before packet assembly.

**Tests** (extend `apps/api/tests/test_runtime_v2_packet.py`, add `test_ledger_extraction.py`):
- Each deterministic pattern matches expected inputs and writes correct fact.
- `override_value` semantics: presence-only inputs no longer produce booleans; new schema enforced.
- Standing override writes to ledger and is readable in next turn.
- Current-turn override does not write to ledger.
- Extraction does not run on flag-off (legacy V1 paths) — verify ledger writes are V2-path only.

**Commit shape:**
- `feat(coach): deterministic ledger extraction patterns`
- `fix(coach): override_value carries asserted value and duration`
- `feat(coach): wire extraction into AICoach.chat`
- `test(coach): cover extraction and override semantics`

---

### Phase B3 — Recent Activities Block

**Spec sections:** Artifact 9 §4.

**Build:**
- Module `apps/api/services/coaching/recent_activities_block.py`:
  - `compute_recent_activities(db, athlete_id, window_days=14) -> dict` matching the schema in §4.4.
  - Per-activity atoms: `activity_id`, `type`, `date`, `distance`, `duration`, `avg_pace`, `avg_hr`, `perceived_effort`, `planned_vs_executed_delta`, `notable_features`, `structured_workout_summary`.
  - `notable_features` deterministic computation:
    - `pace_drift` (rep-by-rep or split-by-split slowing in workouts)
    - `fade` (last 25% pace vs first 75% on threshold/long efforts)
    - `strong_finish` (last 25% faster than first 75%)
    - `missed_rep` (rep dropped from a structured workout)
  - Aggregates: weekly volume per last 4 weeks, weekly hard-day count, easy/hard ratio, weekly volume change pct, last session of each major workout type.
- Token budget: target 1500, hard cap 2500. Truncate oldest activities first if cap exceeded.

**Tests** (`apps/api/tests/test_recent_activities_block.py`):
- Block populates from canned fixture activities.
- 14-day window respected.
- Each `notable_feature` correctly identified on synthetic activities with known patterns.
- Aggregates match expected on synthetic data.
- Token cap enforced.

**Commit shape:**
- `feat(coach): recent_activities deterministic block`
- `test(coach): cover recent_activities computation`

---

### Phase B4 — Cross-Thread Memory

**Spec sections:** Artifact 9 §5.

**Build:**
- DB migration: `coach_thread_summaries` table (athlete_id, thread_id, generated_at, topic_tags jsonb, decisions jsonb, open_questions jsonb, stated_facts jsonb).
- Thread close trigger in `apps/api/services/coaching/thread_lifecycle.py`:
  - Idle timeout: 24h since last athlete or coach turn (default per §19 Q2 unless founder picks otherwise at lock).
  - Explicit close API for athlete-initiated closes.
- Summary generation:
  - Deterministic stated-fact extraction over closed thread (reuse `ledger_extraction.py`).
  - LLM summary supplement for `topic_tags`, `decisions`, `open_questions` using Kimi-K2.6 with thinking enabled, tight prompt, low temperature.
  - Stated facts write back to ledger via `set_fact` with `athlete_stated` confidence and `source: thread_close`.
- `recent_threads` packet block: last 5 thread summaries (default per §19 Q3 unless founder picks otherwise), token budget 2000 total, oldest truncated first.

**Tests** (`apps/api/tests/test_thread_lifecycle.py`, `test_recent_threads_block.py`):
- Idle timeout triggers close + summary.
- Explicit close triggers summary.
- Summary writes facts to ledger with `athlete_stated` confidence.
- New thread receives populated `recent_threads` block.
- Persistent-fact-recall acceptance scenario (synthetic): fact stated in thread A is in `recent_threads` of thread B days later.
- Token cap enforced.

**Commit shape:**
- `feat(coach): thread summary table and migration`
- `feat(coach): thread close trigger and summary generation`
- `feat(coach): recent_threads packet block`
- `test(coach): cover thread lifecycle and cross-thread memory`

---

### Phase B5 — Unknowns Block

**Spec sections:** Artifact 9 §6.

**Build:**
- Module `apps/api/services/coaching/unknowns_block.py`:
  - `compute_unknowns(db, athlete_id, query_class) -> list[Unknown]`
  - Maps query class (`interval_pace_question`, `nutrition_planning`, `injury_assessment`, `volume_question`, `race_planning`, etc.) to the set of required ledger fields.
  - For each required field with `null` value or expired `confirm_after`, emits `Unknown{field, last_known_value_or_null, asserted_at, field_required_for, suggested_question}`.
- `suggested_question` is a deterministic per-field template, not an LLM call.
- Replace hardcoded `unknowns: []` in `runtime_v2_packet.py` with a real call to `compute_unknowns`.
- Query class detection: extend the existing mode classifier in `runtime_v2_packet.py` to emit a `query_class` alongside `conversation_mode`. Use a small deterministic classifier first (regex/keywords); LLM supplement if needed.

**Tests** (`apps/api/tests/test_unknowns_block.py`):
- Null required field surfaces with correct `field_required_for` tag.
- Expired field surfaces.
- Query class detection routes correctly.
- Hardcoded empty `unknowns: []` removed (regression test).

**Commit shape:**
- `feat(coach): query class detection`
- `feat(coach): unknowns block populated from required fields`
- `test(coach): cover unknowns surfacing`

---

### Phase B6 — Voice Contract Enforcement

**Spec sections:** Artifact 9 §7.

**Build:**
- Module `apps/api/services/coaching/voice_enforcement.py`:
  - `TEMPLATE_PHRASE_BLOCKLIST` constant — list from §7.1 verbatim.
  - `check_response(response_text) -> {ok: bool, hits: list[str]}` — case-insensitive regex check.
  - `enforce_voice(response_text, retry_callable, max_retries=2)` — on hit, calls `retry_callable` with explicit "rewrite without phrase X" instruction; if all retries hit, raises `VoiceContractViolation` and the orchestration logs a quality incident.
- Wire into `query_kimi_v2_packet` post-LLM-call: every V2 response runs through `enforce_voice`. Non-fatal log on retry; fatal incident on max-retry.
- Extend Tier 3 judge in `_eval.py`: `voice_alignment` already exists for `artifact7.v1` cases; ensure it explicitly penalizes blocklist hits in the score calculation.
- Telemetry: `template_phrase_count` field added to `CoachChat` metadata.

**Tests** (`apps/api/tests/test_voice_enforcement.py`):
- Each blocklist phrase detected.
- Retry succeeds on rewritten response.
- Max-retry raises and logs incident.
- Tier 3 judge penalizes hits.

**Commit shape:**
- `feat(coach): template-phrase blocklist enforcement`
- `feat(coach): voice_alignment penalizes blocklist hits`
- `test(coach): cover voice enforcement`

---

### Phase B7 — V2 Packet Rewire + System Prompt + Thinking Flip

**Spec sections:** Artifact 9 §8, §15, §17.

**Build:**
- Modify `apps/api/services/coaching/runtime_v2_packet.py`:
  - Add `athlete_facts` block (from ledger).
  - Add `recent_activities` block (from B3).
  - Add `recent_threads` block (from B4).
  - Add `unknowns` block (from B5).
  - Keep existing `calendar_context`, `current_turn`, `recent_context`, `conversation_mode`, `athlete_stated_overrides` blocks unchanged.
  - **Remove `legacy_context_bridge` from primary athlete state.** Keep only as a deprecation shim block named `_legacy_context_bridge_deprecated` set to empty when ledger field coverage ≥ a configurable threshold (default 50%); below threshold, populate the shim from `_build_athlete_state_for_opus` and log a warning. Plan to remove the shim entirely in a follow-up commit after first canary cycle.
- Modify `apps/api/services/coaching/_llm.py`:
  - In `query_kimi_v2_packet`:
    - Replace the current system prompt with the locked v1 text from Artifact 9 §8 verbatim. Do not paraphrase.
    - Insert a `<!-- VOICE_CORPUS -->` placeholder marker after the system prompt. The corpus contents are populated in Phase B10 from a founder-provided file.
    - Set `extra_body["thinking"] = {"type": "enabled"}` for `kimi-k2.6`. Remove the `disabled` setting.
- Telemetry per §17: `anchor_atoms_per_answer`, `unasked_surfacing`, `template_phrase_count`, `generic_fallback_count`, `ledger_field_coverage`, `unknowns_count`, `model`, `thinking`, `voice_alignment_judge_score`. All written to `CoachChat` metadata + structured log.

**`anchor_atoms_per_answer` detection** (deterministic post-response analysis):
- Count of named atoms detected: regex for activity-date references (e.g., `Tuesday's`, `Sunday's`, dates), regex for ledger-field references (e.g., `60 mpw`, `1:27 half`, `cut`), regex for thread references (e.g., `you said`, `three weeks ago`, `last time we talked`).
- Reported per turn; not gated.

**`unasked_surfacing` detection** (deterministic):
- Heuristic: response contains a sentence beginning with `One thing`, `I'd flag`, `Worth noting`, `I notice`, `Pattern I see`, `Risk here`, or includes a paragraph that does not directly answer the user's question. Recorded as boolean; not gated.

**Tests** (extend `apps/api/tests/test_runtime_v2_packet.py`, add `test_v2_system_prompt.py`):
- Packet now includes `athlete_facts`, `recent_activities`, `recent_threads`, `unknowns`.
- `legacy_context_bridge` no longer in primary path; shim only populated when ledger coverage low.
- `query_kimi_v2_packet` calls Kimi with thinking enabled.
- System prompt text matches Artifact 9 §8 verbatim.
- Voice corpus marker present and replaceable.
- Telemetry fields populated correctly on synthetic turns.

**Commit shape:**
- `feat(coach): V2 packet ledger + activities + threads + unknowns blocks`
- `refactor(coach): remove legacy_context_bridge from primary path`
- `feat(coach): V2 system prompt and thinking enabled`
- `feat(coach): V2 telemetry contract`
- `test(coach): cover V2 packet rewire and system prompt`

---

### Phase B8 — Comparison Harness

**Spec sections:** Artifact 9 §11, §12.

**Build:**
- Module `apps/api/services/coaching/comparison_harness.py`:
  - `run_harness(case_ids: list[str]) -> HarnessReport`:
    - For each case, build the prompt + typed athlete context (the context the athlete would type, drawn from the case's `situation` + `required_context`).
    - Call Sonnet 4.6, GPT 5.5, Opus 4.6 via existing provider abstractions (or thin clients added here). Use the typed context only — no ledger, no activities, no threads (these competitors don't have it).
    - Call V2 with full packet (ledger + activities + threads + unknowns + calendar) for the same athlete.
    - Run Tier 3 judge from `_eval.py` on all four answers per case across five dimensions.
    - Generate per-case `data_advantage_must_include` coverage check: does V2's answer mention each required atom?
  - `HarnessReport` rendered as markdown to `docs/V2_HARNESS_REPORTS/{date}_run.md`:
    - Per-case ranking matrix.
    - Per-case `data_advantage_must_include` coverage table.
    - Per-case answers from all four sources, side by side.
    - Tier 3 judge qualitative notes per case.
    - Aggregate: did V2 unanimous #1 every dimension every case?
- The harness is **not** wired into CI. It is run on-demand by the builder in Phase B10. CI runs only the unit/integration test suite.

**Tests** (`apps/api/tests/test_comparison_harness.py`):
- Harness runs against a mocked-LLM fixture (no real API calls in CI).
- Report rendering structure correct.
- `data_advantage_must_include` coverage check correctly identifies misses.
- Aggregate "unanimous #1" computation correct on fixture data.

**Commit shape:**
- `feat(coach): comparison harness against frontier models`
- `feat(coach): harness report rendering`
- `test(coach): cover harness logic with mocked LLMs`

---

### Phase B9 — Production Deployment (code only, V2 visible OFF)

**Constraint:** V2 visible flag stays OFF in production. This deployment ships the new code paths so the harness can be run against production-like data, but does not enable visible V2 to any athlete. Founder explicitly enables only after harness review and canary decision.

**Steps:**
1. Open the PR for review (Opus + founder) marked as ready. CI must be green.
2. After merge to `main` (founder/Opus merges, not builder), the builder may run deployment per `c:\Dev\StrideIQ\.cursor\rules\production-deployment.mdc`:
   ```bash
   cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build
   ```
3. Run smoke check per the production-deployment rule (auth token + `/v1/home` curl). Verify production healthy.
4. Verify V2 flags via DB query: `coach.runtime_v2.shadow` and `coach.runtime_v2.visible` both `enabled=false`, `rollout_percentage=0`, `allowed_athlete_ids='[]'::jsonb`. **If either flag is enabled, abort and alert founder.**
5. Verify ledger migration applied cleanly. Spot-check a backfilled athlete row.

**Commit shape:** none (deploy only). Update PR description with smoke-check evidence.

**If anything in the smoke check fails**, do not proceed to Phase B10. Surface to founder and Opus.

---

### Phase B10 — Voice Corpus Embed + Comparison Harness Run

**This is the only phase that requires founder synchronous input.**

**Pre-condition:** Founder provides `docs/specs/V2_VOICE_CORPUS.md` containing 8–12 selected snippets from the reference corpus (Artifact 9 §7.3). Until this file exists in repo, builder waits.

**Build:**
- Replace the `<!-- VOICE_CORPUS -->` placeholder in the V2 system prompt with the verbatim contents of `docs/specs/V2_VOICE_CORPUS.md`. **Builder does not edit, summarize, or paraphrase the snippets.** Verbatim only.
- Commit: `feat(coach): embed founder-curated voice corpus into V2 system prompt`.
- Run the comparison harness against the three Acceptance Set cases (`grok_physiology_breathing`, `nutrition_cheerlead_sarcastic_intake`, `persistent_fact_recall_volume`):
  ```bash
  python -m apps.api.scripts.run_v2_comparison_harness
  ```
- Commit the harness report at `docs/V2_HARNESS_REPORTS/{YYYY-MM-DD}_run.md`.
- Update PR description (or open a new PR for the harness output if main has been merged): paste the aggregate "unanimous #1" row for each case + dimension. Link the full report.

**Stop condition:** harness report committed and surfaced. **Do not run founder canary.** **Do not enable any V2 flag.** Founder + Opus review the harness output and decide next step.

If the aggregate shows V2 not unanimous #1 on any case-dimension cell, the builder may continue with one targeted iteration:
- Identify the failing case-dimension cell.
- Diagnose: is it the system prompt (anchor instruction), the packet (missing atom), the voice corpus (wrong snippet emphasis), or the ledger coverage?
- Apply one fix. Commit. Re-run harness. Commit new report.
- Maximum two iteration cycles before pausing for founder/Opus review. Do not grind past two.

---

## 5. Acceptance Set fixtures

The three Acceptance Set cases must exist as JSON fixtures in `apps/api/tests/fixtures/v2_acceptance_set.json` before Phase B8 runs. The first two cases mostly already exist (`nutrition_cheerlead_sarcastic_intake` is in `coach_eval_cases.json`); the other two need authoring.

**You may not author the cases.** Founder authors with Opus review. If fixtures are missing at the start of Phase B8, builder pauses and surfaces.

---

## 6. What you do NOT do

- Do not author coaching voice examples or coach response samples.
- Do not modify locked artifacts (1, 5, 6, 7, 8, 9).
- Do not enable V2 visible flag.
- Do not enable V2 shadow flag.
- Do not run the founder canary.
- Do not push to main directly; PR + review only.
- Do not add new OAuth or third-party scopes.
- Do not use `git push --force`, `--no-verify`, `git rebase -i`, or `git commit --amend` except per the narrow exception in §1.
- Do not skip CI or deploy on red.
- Do not extend the build past Phase B10. If you reach a blocker, stop and surface.
- Do not invent fields or extend ledger schema beyond Artifact 9 §3.1 without founder approval. The schema is additive but lock-time additions only.

---

## 7. What evidence to surface in the PR description

Update the PR description as you complete each phase. For each phase:

- Phase ID and one-line summary.
- Files added / modified.
- Tests added (count + path).
- Local test output (last lines including pass count).
- CI run link + status.
- Any deviations from the spec (with reasoning) — surface for review, do not silently deviate.

At Phase B9: smoke-check output, flag verification query results.
At Phase B10: harness report link, aggregate ranking row, any iteration notes.

---

## 8. End state at handoff

When you stop at the end of Phase B10, the repo state is:

- Branch `feat/v2-athlete-truth-layer` merged into `main` (founder/Opus merged after review of B1–B8).
- All ten phases checked off in the (now-merged) PR.
- Production running new code with V2 visible flag still OFF, V2 shadow flag still OFF.
- `docs/V2_HARNESS_REPORTS/{date}_run.md` committed with comparison run output.
- CI green on `main`.
- Tree clean.

Founder and Opus then review the harness output and decide:
- Pass: founder enables visible flag for founder-only canary turns.
- Fail with diagnosable lever: builder iterates targeted fix on a new branch.
- Fail at model-ceiling: Opus + founder discuss next architecture step.

That decision is not yours.

---

## 9. If you hit a wall

If at any phase you cannot proceed because:
- A spec ambiguity blocks correct implementation,
- A test or CI failure does not have a clear fix path after one fix attempt,
- A locked artifact appears to conflict with another,
- A required dependency is missing,

**Stop. Push your current state. Surface the blocker in the PR description with:**
- The phase ID.
- The specific question.
- What you tried.
- What you need (founder decision, Opus review, missing fixture, etc.).

Do not invent your way past a blocker. Do not silently deviate from the spec.

---

## 10. Reference: locked artifact pointers

- Artifact 1 (state package): `docs/specs/COACH_RUNTIME_V2_LOCKED_ARTIFACTS.md` — see pointer.
- Artifact 5 (conversation modes): same.
- Artifact 6 (voice rules): same.
- Artifact 7 (replay rubric): `docs/specs/REPLAY_RUBRIC_SPEC.md`.
- Artifact 8 (canary/rollback): `docs/specs/COACH_RUNTIME_V2_ARTIFACT_8_CANARY_ROLLBACK.md`.
- Artifact 9 (Athlete Truth Layer): `docs/specs/COACH_RUNTIME_V2_ARTIFACT_9_ATHLETE_TRUTH_LAYER.md`.
- Failure modes catalog: in `apps/api/services/coaching/_eval.py` (`ARTIFACT7_FAILURE_MODES`).

---

That is the build. Ten phases, scoped commits, CI green every step, V2 visible off throughout, harness output as the handoff. After that the founder and Opus pick up.
