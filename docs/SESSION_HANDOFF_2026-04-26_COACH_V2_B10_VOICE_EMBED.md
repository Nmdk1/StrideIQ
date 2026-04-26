# Coach V2 — B10 Voice Embed & Path to Canary — April 26, 2026

**For:** Founder, and any agent picking up this thread
**From:** Opus 4.7 (review + B10 voice corpus embed)
**Production:** https://strideiq.run | Server: root@187.124.67.153

---

## What state we're in

1. **PR #6 merged.** Artifact 9 (Athlete Truth Layer) foundation: athlete fact ledger, recent activities block, thread summaries, unknowns, conflict typing, deterministic mode, V2 system prompt anchored on the packet. Comparison harness scaffolding shipped.
2. **PR #7 merged.** SA1–SA5 hardening: thread summary cascade, `PendingConflict` surfaced in packet, `LEDGER_COVERAGE_SHIM_THRESHOLD` configurable with warning log, V2 deterministic turn guard, Dockerfile revision labels.
3. **PR #B10 open** (this PR) — embeds the locked voice corpus into `V2_SYSTEM_PROMPT`.
4. **V2 visible flag is off in production.** It stays off until the canary gate clears.
5. **Production is on `main` at the post-PR #7 SHA, but has NOT yet been redeployed since the PR #7 merge.** Deploy is the next founder action (see commands below).

---

## What this PR does

Embeds the founder-locked voice corpus (`docs/specs/V2_VOICE_CORPUS.md`) directly into `V2_SYSTEM_PROMPT` in `apps/api/services/coaching/_llm.py`. The previous `<!-- VOICE_CORPUS -->` marker was a placeholder; this PR makes it real — Kimi K2.6 now sees all twelve snippets (Roche/Green reference passages + register exemplars including push-forward after diagnostic work, suppression-as-default trend surfacing, and racing-prep judgment anchored in the athlete's own race history) plus the use-note that defines how the corpus is to be applied.

Files changed:

- `apps/api/services/coaching/_llm.py` — new `V2_VOICE_CORPUS` constant; `V2_SYSTEM_PROMPT = f"{ARTIFACT9_V2_SYSTEM_PROMPT}\n\n{V2_VOICE_CORPUS}"`
- `apps/api/tests/test_v2_system_prompt.py` — locked-prompt verbatim test stays; added presence checks for all 12 snippets, founder-anchor phrases, and exclusion of human-only metadata sections
- `docs/specs/V2_VOICE_CORPUS.md` — adds the locked corpus to the repo as the canonical source for the embed
- `docs/BUILDER_INSTRUCTIONS_2026-04-26_COACH_V2_SHOULD_ADDRESS.md` — adds the SA1–SA5 builder instructions to the repo (already executed via PR #7; preserved for history)
- This handoff

---

## Local validation

V2 + harness regression sample, run from `apps/api`:

```
python -m pytest tests/test_v2_system_prompt.py tests/test_pending_conflicts.py \
  tests/test_runtime_v2_packet_shim.py tests/test_v2_turn_guard_parity.py \
  tests/test_coach_runtime_v2_shell.py tests/test_thread_lifecycle.py \
  tests/test_comparison_harness.py -q
```

Result: `55 passed, 3 skipped` (skips are DB-backed thread lifecycle tests that need Postgres). No regressions.

Pre-existing baseline failures from the PR #7 full-regression run (4 failed, 4669 passed) carry forward — `test_zero_hallucination_rule_in_gemini_prompt` and 3 Garmin D5 sport-skip tests. Tracked separately, not blocking.

---

## CI

This PR will trigger the same active checks the prior two ran: Backend Lint, Backend Smoke, Migration Integrity, Docker Build, Frontend Build, Frontend Tests, Security Scan, P0 plan registry gate. Backend Tests + Nightly Report skip per workflow rules.

The system prompt change is logic-equivalent at the runtime layer (still gated behind `coach.runtime_v2.visible`, which is off), so smoke and migration paths are unaffected.

---

## Deploy command (founder action, on droplet)

After CI on this PR is green and you've merged it:

```bash
ssh root@187.124.67.153
cd /opt/strideiq/repo && git pull origin main && GIT_SHA=$(git rev-parse HEAD) docker compose -f docker-compose.prod.yml up -d --build
```

The `GIT_SHA=` prefix is required for the OCI revision label that SA5 introduced. Without it the label bakes as `unknown`.

---

## Post-deploy verification

### Revision label

```bash
docker inspect strideiq_api --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}'
docker inspect strideiq_web --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}'
```

Both should print the post-merge `main` SHA.

### Migrations

```bash
docker exec strideiq_api alembic current
```

Should report `coach_v2_truth_003` as head.

### Flags stay off

```bash
docker exec strideiq_api python -c "
from database import SessionLocal
from models import FeatureFlag
db = SessionLocal()
for key in ['coach.runtime_v2.shadow', 'coach.runtime_v2.visible']:
    f = db.query(FeatureFlag).filter_by(key=key).first()
    print(key, '->', 'enabled=', getattr(f, 'enabled', None),
          'rollout=', getattr(f, 'rollout_percentage', None),
          'allowed=', getattr(f, 'allowed_athlete_ids', None))
db.close()
"
```

Both should be `enabled=False`, `rollout=0`, `allowed=[]`. Do not flip either flag from this handoff.

### No V2 packet activity

After a smoke chat call, API logs should contain `coach_runtime_v2_flag_decision` with `enabled: false` for both flags and **no** `coach_runtime_v2_request` events. If `coach_runtime_v2_request` appears, an allowlist or rollout snuck back in — stop and re-check the flag rows.

---

## The canary gate

V2 visible turns on **only after** the comparison harness produces a passing report against the locked acceptance set. The full gate criteria, scoring, and ranking math live in `docs/specs/COACH_RUNTIME_V2_ARTIFACT_9_ATHLETE_TRUTH_LAYER.md` §2 and the comparison harness in `apps/api/services/coaching/comparison_harness.py`.

### Acceptance set

`apps/api/tests/fixtures/v2_acceptance_set.json` — three founder-curated cases:

- `grok_physiology_breathing` — checks anchored physiology reasoning
- `nutrition_cheerlead_sarcastic_intake` — checks suppression and direct voice over generic cheerleading
- `persistent_fact_recall_volume` — checks the ledger actually persists athlete-stated facts across turns

### Harness baselines

V2 (Kimi K2.6 + full Artifact 9 packet) is ranked against:

- Sonnet 4.6 with typed-context-only prompt (no ledger atoms)
- GPT 5.5 with typed-context-only prompt
- Opus 4.6 with typed-context-only prompt
- "Stranger baseline" — same Kimi K2.6 with no packet and no athlete history

The bar: V2 must be ranked unanimous #1 by the LLM-as-judge across all three cases for `voice_alignment`, `unique_observation`, `data_anchoring`, and `decision_specificity`. Ties or losses fail the gate.

### Running the harness

The harness needs API keys for all four model families. The cleanest place to run it is the droplet, after deploy, with the production secrets already in env. Exact entry point and CLI flags are documented in the `comparison_harness.py` module docstring.

The harness writes the report to a JSON artifact. Founder + advisor jointly review the artifact; founder makes the canary call.

### If it passes

Canary plan: founder-only allowlist on `coach.runtime_v2.visible`, no rollout %, founder runs three to five real conversations, both of us read the trace logs and the resulting `CoachUsage` rows, founder either keeps it on or kills it. No shadow production. No long iteration.

### If it fails

Read the harness report, find the specific scoring dimension that failed, decide what packet field, prompt rule, or voice exemplar isn't doing its job, fix that thing, re-run the harness. No flag flip until pass.

---

## Read order for the next agent picking this up

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/specs/COACH_RUNTIME_V2_ARTIFACT_9_ATHLETE_TRUTH_LAYER.md`
3. `docs/specs/V2_VOICE_CORPUS.md`
4. `apps/api/services/coaching/_llm.py` (system prompt + voice corpus embed)
5. `apps/api/services/coaching/comparison_harness.py`
6. `apps/api/services/coaching/V2_TURN_GUARD_PARITY.md`
7. This handoff

---

## Tracked debt (none of this blocks the canary)

- The 4 pre-existing pytest failures from the PR #7 baseline.
- Scope creep on `apps/api/scripts/clone_athlete_to_demo.py` (logged in PR #7).
- The harness has no founder-facing CLI yet beyond the module docstring instructions; running it currently requires a Python invocation. If we end up running it more than twice, build the CLI.
