# Builder Instructions — Coach V2 Should-Address Items

**Status:** Active. Founder-approved 2026-04-26.
**Builder:** GPT 5.5 high (same builder instance that completed Artifact 9 / B1–B9).
**Branch:** create new feature branch `feat/v2-should-address` off latest `main`.
**Stop condition:** end of Phase SA5 PR merge. No further work without new instructions.

---

## Read order before starting

1. `docs/FOUNDER_OPERATING_CONTRACT.md` — non-negotiable working rules.
2. `docs/specs/COACH_RUNTIME_V2_ARTIFACT_9_ATHLETE_TRUTH_LAYER.md` — Artifact 9 (LOCKED 2026-04-26). This work is the locked-spec follow-up; nothing here contradicts Artifact 9.
3. `docs/specs/V2_VOICE_CORPUS.md` — LOCKED 2026-04-26. Not modified by this work.
4. `docs/BUILDER_INSTRUCTIONS_2026-04-26_COACH_V2_ATHLETE_TRUTH_LAYER.md` — the prior B1–B10 builder instructions. Style and discipline rules below mirror that document.

If anything in this file appears to contradict Artifact 9, Artifact 9 wins. Stop and flag the conflict.

---

## Operating constraints

Same as the Artifact 9 build:

- Scoped commits only. Never `git add -A`.
- Each phase is its own commit. PR title `feat(coach): v2 should-address — <phases>`.
- One PR for the whole batch (SA1–SA5). Merge to `main` after CI green and Opus review sign-off. No deploy without explicit founder approval.
- CI runs only on PR. Local validation is the only signal until the PR is open.
- No new OAuth or API permission scopes.
- No changes to `_llm.py::V2_SYSTEM_PROMPT`, voice enforcement blocklist, or Artifact 9 packet shape unless a phase below explicitly requires it.
- If you discover that an item is already addressed in the codebase, mark it "no-op verified" with the proof (file:line) and move on.

## Phase loop discipline

For each phase below:

1. Read the listed files end-to-end before touching anything.
2. Write the change.
3. Run focused tests for that phase locally.
4. Run the full backend regression: `pytest apps/api/tests -q`. Must pass before commit.
5. Lint: `ruff check apps/api` clean on edited files.
6. Commit with a scoped message naming the phase: `fix(coach): SA<n> <short summary>`.
7. Move to next phase.

If a phase's local tests fail after two attempts, stop and flag with the failing assertion text. Do not paper over with mocks or skips.

---

## Phase SA1 — `coach_thread_summary` cascade on athlete delete

**Problem.** `apps/api/alembic/versions/coach_v2_truth_002_thread_summaries.py` declares the `athlete_id` foreign key without `ondelete="CASCADE"`. If an athlete is deleted, their thread summaries become orphaned rows. The `athlete_facts` table (in `coach_v2_truth_001`) cascades correctly; `coach_thread_summary` should match.

**Files to read.**
- `apps/api/alembic/versions/coach_v2_truth_001_athlete_facts_ledger.py` (reference cascade pattern).
- `apps/api/alembic/versions/coach_v2_truth_002_thread_summaries.py` (file to fix).
- Any existing alembic migration that drops/recreates a foreign key for the cascade pattern.

**Change.** Author a new migration `coach_v2_truth_003_thread_summary_cascade.py`:
- `revision = "coach_v2_truth_003"`, `down_revision = "coach_v2_truth_002"`.
- `upgrade()`: drop the existing `athlete_id` foreign key constraint and recreate it with `ondelete="CASCADE"`.
- `downgrade()`: drop the cascading constraint and recreate the original non-cascading constraint.
- Use `op.drop_constraint` / `op.create_foreign_key` with explicit constraint names so the migration is deterministic across postgres versions.
- Do NOT edit `coach_v2_truth_002` — that migration is already in production. Forward-only.

**Acceptance.**
- `pytest apps/api/tests -q -k thread_summary` passes (existing tests must still pass with cascade).
- New behavioral test in `apps/api/tests/test_thread_lifecycle.py`: create athlete → create chat → close thread to generate summary → delete athlete → assert `CoachThreadSummary` row count for that athlete is zero.
- `alembic upgrade head` and `alembic downgrade -1` both run cleanly against the test database.

**Stop-and-flag if.** The constraint name in production differs from the alembic-default-generated name and the migration cannot reliably target the existing constraint without a hardcoded name. Surface to founder/Opus before writing fragile name-detection logic.

---

## Phase SA2 — Surface `PendingConflict` in the V2 packet

**Problem.** `services/coaching/ledger.py::set_fact` returns a `PendingConflict` instance when an `athlete_stated` fact would be overwritten by a lower-confidence value. `services/coaching/ledger_extraction.py::persist_proposed_facts` collects these into its return list. `services/coaching/core.py::AICoach.chat` calls `persist_proposed_facts` (~line 1169) and discards the return value entirely. The conflict never reaches the coach. Spec requires the coach to ask the athlete which value is current.

**Files to read.**
- `apps/api/services/coaching/ledger.py` — `PendingConflict` dataclass and `set_fact` semantics.
- `apps/api/services/coaching/ledger_extraction.py` — `persist_proposed_facts` return contract.
- `apps/api/services/coaching/core.py` — V2 visible-mode chat path around line 1160–1200.
- `apps/api/services/coaching/runtime_v2_packet.py` — `assemble_v2_packet` and where it accepts pre-resolved state (the conflict needs to be threaded through here).
- `apps/api/services/coaching/unknowns_block.py` — for adjacency; conflicts are NOT unknowns and should be a separate field.
- `docs/specs/COACH_RUNTIME_V2_ARTIFACT_9_ATHLETE_TRUTH_LAYER.md` §4 (Athlete Fact Ledger) and §6 (Unknowns Block) — confirm conflicts are conceptually distinct from unknowns.

**Change.**
1. In `core.py`, capture the result of `persist_proposed_facts` into a `pending_conflicts: list[PendingConflict]` local. Filter the list down to instances of `PendingConflict` only (the return type is `list[Any]`; `AthleteFactsAudit` rows are not conflicts).
2. Pass `pending_conflicts` into `assemble_v2_packet` as a new keyword-only argument with default `None` (default `None` keeps existing test fixtures working).
3. In `runtime_v2_packet.py::assemble_v2_packet`, add a top-level packet field `pending_conflicts` shaped as a list of dicts:
   ```
   {
     "field": <ledger field name>,
     "existing_value": <existing entry value>,
     "existing_confidence": <existing confidence>,
     "existing_asserted_at": <iso8601>,
     "proposed_value": <proposed entry value>,
     "proposed_confidence": <proposed confidence>,
     "proposed_source": <proposed source>,
     "suggested_question": <prompt for the coach to ask the athlete>
   }
   ```
4. The `suggested_question` is a deterministic per-field string. Reuse the `SUGGESTED_QUESTIONS` map in `unknowns_block.py` as the source of truth for question text per field; if a field has no entry, fall back to `"Earlier you said {existing_value} for {field}; I just heard {proposed_value}. Which is current?"`.
5. Pending conflicts are sensitive to the same redaction rules as the ledger itself. Apply `redact_ledger_payload` semantics (see `ledger.py::SENSITIVE_FACT_FIELDS`) so a sensitive-field conflict never leaks raw values into the packet — for sensitive fields, replace `existing_value` and `proposed_value` with the string `"[redacted]"` and keep the `field` and `suggested_question` so the coach can still ask.
6. Update the V2 system prompt's packet description in `_llm.py::ARTIFACT9_V2_SYSTEM_PROMPT` to reference `pending_conflicts` alongside `unknowns` (one short sentence — see Artifact 9 §8 for tone). Conflicts are higher priority than unknowns: if a conflict exists for a field, the coach must resolve it before answering substantive questions about that field.

**Tests required (new file or extend existing).**
- `apps/api/tests/test_runtime_v2_packet.py` (or new `test_pending_conflicts.py`):
  - `test_pending_conflict_surfaces_in_packet`: persist an `athlete_stated` fact, then attempt to persist a `system_inferred` fact for the same field through `persist_proposed_facts`. Confirm the chat path threads a non-empty `pending_conflicts` into the packet.
  - `test_pending_conflict_redacts_sensitive_field`: same shape but for a field in `SENSITIVE_FACT_FIELDS`. Confirm `existing_value` and `proposed_value` are `"[redacted]"`, `field` and `suggested_question` are present.
  - `test_pending_conflict_priority_over_unknowns`: when a conflict exists for the same field that would otherwise appear in `unknowns`, the field appears in `pending_conflicts` and is suppressed from `unknowns`.
- `apps/api/tests/test_v2_system_prompt.py`: extend the verbatim-prompt assertion to cover the new `pending_conflicts` line.

**Acceptance.**
- All new tests pass.
- Full backend regression green.
- No change to existing packet-shape contract beyond the additive field.

**Stop-and-flag if.** The redaction policy cannot be satisfied without changing `SENSITIVE_FACT_FIELDS` or `redact_ledger_payload`. Surface to founder/Opus.

---

## Phase SA3 — `LEDGER_COVERAGE_SHIM_THRESHOLD` configurable + warning log

**Problem.** `services/coaching/runtime_v2_packet.py:25` hardcodes `LEDGER_COVERAGE_SHIM_THRESHOLD = 0.5`. When ledger coverage is below the threshold, the runtime falls back to including the deprecated `legacy_context_bridge` shim. Today this fallback happens silently — there is no log, no telemetry, no way to detect quietly that V2 is shipping prose-bridge context to K2.6 instead of structured atoms. Operations needs visibility, and the threshold should be operator-tunable without a code change.

**Files to read.**
- `apps/api/services/coaching/runtime_v2_packet.py` — the constant and its three usages (line 25, ~1303, ~1325, ~1517).
- `apps/api/core/config.py` — settings module pattern for env-var configuration.

**Change.**
1. In `core/config.py`, add a new setting:
   ```python
   COACH_LEDGER_COVERAGE_SHIM_THRESHOLD: float = 0.5
   ```
   with the standard env-var lookup, validated to be in `[0.0, 1.0]`. Default 0.5 preserves current behavior.
2. In `runtime_v2_packet.py`, replace the module-level constant with a function `_ledger_coverage_shim_threshold() -> float` that reads from `settings.COACH_LEDGER_COVERAGE_SHIM_THRESHOLD` at call time (not import time, so test overrides via `monkeypatch.setattr(settings, ...)` work). Update the three existing usages to call the function. Keep the module-level `LEDGER_COVERAGE_SHIM_THRESHOLD` name as a re-export for backward compatibility with any test that imports it directly — set it to a `property`-style indirect or just leave the constant as a fallback alias and document in a comment that the runtime uses the function.
3. Where `legacy_context` is included (the `else` branch around line 1303–1304 — i.e., coverage < threshold AND `legacy_context` is non-empty after `quiet_legacy_context_bridge`), emit a structured log line at WARNING level:
   ```
   logger.warning(
       "coach_runtime_v2_legacy_context_shim_active",
       extra={
           "athlete_id": str(athlete_id),
           "ledger_field_coverage": ledger_field_coverage,
           "threshold": _ledger_coverage_shim_threshold(),
           "legacy_context_chars": len(legacy_context),
           "removed_temporal_lines_count": removed_temporal_lines_count,
       },
   )
   ```
   The log key `coach_runtime_v2_legacy_context_shim_active` is part of the contract and must be greppable in production logs.

**Tests required.**
- `apps/api/tests/test_runtime_v2_packet.py`:
  - `test_legacy_shim_threshold_respects_env_override`: monkeypatch the setting to 0.9; confirm legacy context is included for an athlete with 0.6 coverage that would have been suppressed under the default 0.5.
  - `test_legacy_shim_active_emits_warning_log`: assemble a packet with low ledger coverage and non-empty legacy context; assert the warning log fires with the expected `extra` payload (use `caplog`).
  - `test_legacy_shim_silent_when_coverage_high`: high coverage path emits no warning and the legacy context is empty in the packet.

**Acceptance.**
- All new tests pass.
- Full backend regression green.
- Production deploy verifies the env var with `docker exec strideiq_api python -c "from core.config import settings; print(settings.COACH_LEDGER_COVERAGE_SHIM_THRESHOLD)"` returning `0.5` (or whatever the operator sets).

**Stop-and-flag if.** The settings module enforces immutability or validation in a way that prevents test monkeypatching. Document the workaround in the test file rather than weakening the validator.

---

## Phase SA4 — V2 turn-guard parity audit and decision

**Problem.** In `services/coaching/core.py` around line 1264:

```python
if served_by_v2:
    guarded_response = result.get("response", "")
else:
    guarded_response = await self._finalize_response_with_turn_guard(...)
```

V2 runs voice enforcement (template phrase blocklist) but bypasses `_finalize_response_with_turn_guard` entirely. The turn guard does broader checks than voice enforcement — extreme length, leakage of other athletes' identifying details, unsafe medical/clinical advice patterns, repetition guards, etc. (See `apps/api/services/coaching/_guardrails.py` for the full set.) This is a regression risk: V1 had this safety net; V2 does not.

This phase is a **decision-and-document phase, not a feature phase**. The output is a parity matrix, a code change to either port the relevant checks or call the turn guard, and a test that proves V2 has the same safety floor V1 has.

**Files to read.**
- `apps/api/services/coaching/_guardrails.py` — read the entire `_finalize_response_with_turn_guard` and every helper it calls. List each individual check (e.g., "max length", "athlete-name leakage", "medical-claim filter", "repetition guard", etc.).
- `apps/api/services/coaching/voice_enforcement.py` — full file. List every check.
- `apps/api/services/coaching/core.py` — the V2 path lines 1160–1310 to understand where the response is finalized.
- Artifact 9 §7 (voice contract enforcement) and §8 (system prompt) for the spec posture.

**Step 1 — produce a parity matrix.**
Write a markdown file `apps/api/services/coaching/V2_TURN_GUARD_PARITY.md` (committed; this is durable documentation) with one row per V1 turn-guard check:

| Check | V1 behavior | V2 current state | Decision |
|------|------------|------------------|----------|
| <name> | <what V1 does> | covered by voice enforcement / not covered / partially covered | port / skip-with-reason / route-through-guard |

**Step 2 — port the gaps.**
For each row marked `port`, implement the check inside `services/coaching/voice_enforcement.py` (or a new sibling module if voice_enforcement is the wrong home — for example, length and leakage checks may belong in a `_v2_safety.py` module called from the voice-enforcement retry loop). The V2 finalize path must run all `port` checks before returning.

For each row marked `skip-with-reason`, the parity matrix must state the reason. Acceptable reasons: "the check exists to handle a V1-specific failure mode that V2 architecturally cannot produce because <Artifact 9 mechanism>". Unacceptable reason: "out of scope."

For each row marked `route-through-guard`, refactor the V2 path to call a stripped-down version of `_finalize_response_with_turn_guard` that runs only the relevant checks. The default should be `port`; `route-through-guard` is allowed when the V1 implementation is the most reliable path and porting would duplicate substantial logic.

**Step 3 — tests.**
For every check ported or routed:
- Behavioral test in `apps/api/tests/test_v2_safety.py` (new file) that exercises the V2 path and asserts the check fires correctly for a violating response and passes a clean response.

**Acceptance.**
- `V2_TURN_GUARD_PARITY.md` is committed and complete (one row per V1 check, every row has a decision).
- Every `port` and `route-through-guard` row has at least one corresponding behavioral test.
- Full backend regression green.

**Stop-and-flag if.** The parity matrix surfaces a check that requires architectural change beyond this phase (e.g., a check that depends on multi-turn history that V2 doesn't currently retrieve). Document the gap in the matrix as `defer-with-spec-followup` and stop. Do not silently expand scope.

---

## Phase SA5 — Dockerfile revision label

**Problem.** During the B9 production deploy, the API image revealed that `apps/api/Dockerfile` does not bake the `.git` directory and does not set `org.opencontainers.image.revision`. There is no reliable way to confirm at runtime which commit SHA produced the running image. We worked around it via the alembic head, but that is indirect and fails for any build-only change that does not touch migrations.

**Files to read.**
- `apps/api/Dockerfile` — the file to change.
- `apps/web/Dockerfile` if present (apply the same change for symmetry).
- `.github/workflows/*.yml` — find the build/push job and confirm `${GITHUB_SHA}` is available; also look for `docker-compose.prod.yml` or any local build script that builds the image without going through CI.
- `docker-compose.prod.yml` (likely at repo root) — the production compose file that the deploy command rebuilds.

**Change.**
1. In `apps/api/Dockerfile`:
   ```Dockerfile
   ARG GIT_SHA=unknown
   LABEL org.opencontainers.image.revision=$GIT_SHA
   LABEL org.opencontainers.image.source="https://github.com/Nmdk1/StrideIQ"
   ```
   Place near the top of the final stage.
2. Apply the same change to `apps/web/Dockerfile` if it exists.
3. In `docker-compose.prod.yml`, add `args: GIT_SHA: ${GIT_SHA:-unknown}` to the `build` block of the api (and web, if applicable) service. The compose file should propagate the SHA from an env var that the deploy command sets.
4. Update the production deploy command documentation in `.cursor/rules/production-deployment.mdc` to set `GIT_SHA=$(git rev-parse HEAD)` before `docker compose up -d --build`. The full updated deploy line:
   ```bash
   cd /opt/strideiq/repo && git pull origin main && GIT_SHA=$(git rev-parse HEAD) docker compose -f docker-compose.prod.yml up -d --build
   ```
5. If CI builds and pushes the image, ensure the GitHub Actions build step passes `--build-arg GIT_SHA=${{ github.sha }}`.

**Verification (run locally before commit, also after deploy).**
- Local: `docker build --build-arg GIT_SHA=test123 -t strideiq-api-test apps/api && docker inspect strideiq-api-test --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}'` returns `test123`.
- Production verification (post-deploy step, document in PR description): `docker inspect strideiq_api --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}'` returns the actual deployed commit SHA.

**Acceptance.**
- Local docker build smoke verified.
- No backend test regression (this change has no Python test surface; full regression must still pass).
- PR description includes the local verification output.

**Stop-and-flag if.** The web Dockerfile uses a build system (Next.js standalone, etc.) that does not propagate `LABEL` reliably — document the limitation and apply the change to api only. The api label is the higher priority.

---

## Final delivery

After all five phases are committed and locally green:

1. Push `feat/v2-should-address` to origin.
2. Open PR titled `feat(coach): v2 should-address — SA1–SA5 (cascade, conflicts, threshold config, turn-guard parity, image revision)`.
3. PR description must include:
   - One bullet per phase summarizing the change.
   - Phase SA4 parity matrix link.
   - Phase SA5 local verification output.
   - Test counts per phase (`pytest ... -k <phase>` results).
   - Note: `No deploy without founder approval. No flag flips.`
4. Wait for CI green and Opus review sign-off before requesting merge approval.

**Hard stop after PR is opened.** No deploy, no flag flips, no Phase SA6+ work, no founder canary. Founder and Opus review the PR, decide on merge, and decide on deploy timing separately.

If any phase blocks on a founder dependency (like B8 blocked on Acceptance Set fixtures), state the blocker explicitly and stop. Do not invent the input.
