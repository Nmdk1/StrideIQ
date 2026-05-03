# RULES.md — StrideIQ Operating Rules

This file consolidates the seven operating rules previously maintained in `.cursor/rules/` for Cursor IDE. All rules apply to any agent working in this repo — Cline/Kimi specifically, but model-agnostic. They are not preferences or guidelines; they are binding constraints on how work is done here. Violations cost trust immediately. The original `.cursor/rules/` files remain in place for Cursor sessions; this file is the portable version. When the two conflict, treat the more restrictive version as authoritative.

---

## Session-Start Read Order

**VISION DOCUMENTS (1–6): MANDATORY. Read ALL before proposing ANY feature or architecture.** Agents who propose features without having read these will build the wrong thing. If you cannot reference specific content from these docs in your proposal, you haven't read them.

1. `docs/FOUNDER_OPERATING_CONTRACT.md` — how to work, non-negotiable
2. `docs/PRODUCT_MANIFESTO.md` — the soul of the product. *"The chart makes you open the app. The intelligence makes you trust it. The voice makes you need it."*
3. `docs/PRODUCT_STRATEGY_2026-03-03.md` — the moat: 16 priority-ranked product concepts. The Pre-Race Fingerprint, Proactive Coach, Injury Fingerprint, Personal Operating Manual. Every feature flows from the correlation engine producing true, specific, actionable findings about a single human. Skip this and you will propose something that already exists in a better form here.
4. `docs/specs/CORRELATION_ENGINE_ROADMAP.md` — the 12-layer roadmap for the scientific instrument at the heart of the product. Layers 1–4 are built. Know what exists before proposing what to build next.
5. `docs/FINGERPRINT_VISIBILITY_ROADMAP.md` — how built backend intelligence connects to product strategy: what's surfaceable now, what needs more engine layers, phased plan from surface to deep product.
6. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` — how every screen should feel, what's agreed, what's rejected. Do not re-propose rejected decisions.

**CONTEXT DOCUMENTS (7–13): Read as needed for current work.**

7. `docs/wiki/index.md` — operational mental model of the live system. Treat as authoritative for current state. If you change behavior, you owe a wiki edit — see the [Wiki Currency Contract](#wiki-currency-contract) below.
8. `docs/RUN_SHAPE_VISION.md` — visual vision for run data
9. `docs/SITE_AUDIT_LIVING.md` — honest assessment of current state
10. `docs/BUILD_SPEC_HOME_AND_ACTIVITY.md` — active build spec if working on home/activity pages
11. `docs/TRAINING_PLAN_REBUILD_PLAN.md` — what to build next
12. `docs/AGENT_WORKFLOW.md` — build loop mechanics
13. Latest `docs/SESSION_HANDOFF_*.md` — current state handoff

---

## Founder Operating Contract

Before your first tool call, read `docs/FOUNDER_OPERATING_CONTRACT.md`. Every rule below is non-negotiable. Violating any of them costs trust immediately.

**1. Do NOT start coding when you receive a new feature request.** The workflow is: discuss → scope → plan → test design → build. If the founder says "discuss," they mean discuss — not "discuss briefly then implement."

**2. Show evidence, not claims.** Paste test output. Paste deploy logs. Never claim a test passes without showing the output.

**3. Suppression over hallucination.** If uncertain, say nothing. A precise partial answer beats a thorough wrong one.

**4. The athlete decides, the system informs.** Never override the athlete's judgment in code, copy, or coaching output.

**5. No template narratives.** Either say something genuinely contextual or say nothing at all. The coach must never narrate a false positive as a real finding.

**6. Discuss → scope → plan → build.** Never skip or compress this sequence unilaterally.

**7. Tree clean, tests green, production healthy** at end of every session. Do not close a session with uncommitted changes, failing tests, or a degraded production environment.

**8. Scoped commits only. Never `git add -A`.** Stage only the files relevant to the current task. Unrelated files are never included in a commit.

**9. CI first, local second.** Always check CI (`gh run view`) before debugging locally. CI has Postgres and the full migration chain. If CI is green, the code is correct.

**10. No `git push` without founder approval.** Do not push to `origin` or publish to the shared remote until the founder explicitly approves that batch for publication. This is a governance rule, not a workflow preference. See `docs/FOUNDER_OPERATING_CONTRACT.md` — *Remote publish and permission scopes (binding)*.

**11. No new OAuth or API permission scopes without founder approval.** Do not implement, merge, or deploy widened OAuth scopes or new third-party permissions without explicit sign-off for those exact scopes. Specs may describe future scopes; code waits for approval.

**12. Wiki must always be current.** `docs/wiki/` is the single onboarding document for the project. Every commit that changes system behavior, surfaces, contracts, models, deploy posture, env vars, or routes must update the relevant wiki page in the same commit (or a follow-up commit in the same session). Bump `docs/wiki/index.md`'s `Last updated:` date and append cross-cutting changes to `docs/wiki/log.md`. See the [Wiki Currency Contract](#wiki-currency-contract) below for the page-ownership map. A stale wiki is a trust failure, not a documentation gap. Same standard as tests.

---

## Advisor Review Discipline

When the founder asks for a review, the following is mandatory — not optional:

**1. Verify first, then judge.**
Read the actual target files, specs, or commit diffs before giving any verdict. For commit claims, inspect the commit (`git show` / changed files) before commenting.

**2. Findings first, no fluff.**
Response order: Must fix → Should address → Nice to have. Do not lead with praise, summaries, or "looks good" statements.

**3. Evidence is required.**
Every finding must reference concrete file paths and observed code or spec behavior. Never claim "resolved" or "missing" without direct verification in the current turn.

**4. No speculative approval.**
If verification is incomplete, say "not verified yet" and continue checking. Silence and uncertainty are better than confident but unverified feedback.

**5. Regression-test quality bar.**
Reject tautology or source-string tests as sufficient coverage. Prefer behavioral tests that execute real logic paths.

**6. Founder correction protocol.**
If the founder says review quality is off, stop, acknowledge, re-read sources, and re-issue findings only after verification.

---

## Athlete Trust Safety Contract — Efficiency Interpretation

**One wrong directional claim ("your efficiency is declining") to an athlete who just had a breakthrough week will destroy trust permanently.**

This rule applies whenever you touch any of:
- `apps/api/services/n1_insight_generator.py`
- `apps/api/services/correlation_engine.py`
- `apps/api/services/efficiency_calculation.py`
- `apps/api/services/coach_tools.py`
- `apps/api/services/causal_attribution.py`
- `apps/api/services/load_response_explain.py`
- `apps/api/services/ai_coach.py`
- `apps/api/services/home_signals.py`
- `apps/api/services/calendar_signals.py`
- `apps/api/services/pattern_recognition.py`
- `apps/api/services/run_analysis_engine.py`
- `apps/api/services/activity_analysis.py`
- `apps/api/services/anchor_finder.py`
- `apps/api/tests/test_n1_insight_generator.py`

**Rules:**

1. **Directional claims require explicit polarity metadata.** Never use "improving," "declining," "better," or "worse" in athlete-facing text unless the output metric has `polarity_ambiguous=False` in `OutputMetricMeta` AND is in `DIRECTIONAL_SAFE_METRICS`.

2. **Two-tier fail-closed.**
   - Ambiguous polarity → neutral text only ("associated with changes"), category=`pattern`.
   - Missing/invalid/conflicting metadata → suppress directional output entirely.

3. **No sign-only inference.** Correlation sign (r > 0 / r < 0) alone never determines beneficial/harmful. Always check `_is_beneficial()`, which consults the registry.

4. **Approved directional whitelist (Phase 3C):** `pace_easy`, `pace_threshold`, `race_pace` (lower is better), `completion_rate`, `completion`, `pb_events` (higher is better). New metrics need a registry entry + whitelist addition + tests.

5. **Single registry: `OUTPUT_METRIC_REGISTRY` in `n1_insight_generator.py`.** No local polarity overrides. Legacy services reference this via comments; new code must consume it.

6. **Why efficiency (pace/HR) is ambiguous:**
   - Same pace + lower HR → ratio goes UP (better)
   - Faster pace + same HR → ratio goes DOWN (also better)
   - The ratio moves in opposite directions for two equally valid improvement modes.

**When editing these files:**
- Check `OutputMetricMeta` before adding directional language.
- Run `test_n1_insight_generator.py` — it enforces this contract.
- If adding a new output metric, register it in `OUTPUT_METRIC_REGISTRY` with explicit polarity.
- Legacy services have local polarity assumptions tracked as migration debt. Do not add new local overrides.

---

## Training Plan Rebuild Plan — North Star

The canonical build plan lives at `docs/TRAINING_PLAN_REBUILD_PLAN.md`. Before starting any new feature or phase, read it to confirm:

**1. Build priority order** (bottom of doc):
- Monetization tier mapping (revenue unlock)
- Phase 4 (50K Ultra)
- Phase 3B (when narration quality gate clears)
- Phase 3C (gate cleared for founders with synced history)

**2. Open gates to monitor:**
- 3B: narration accuracy > 90% for 4 weeks (`/v1/intelligence/narration/quality`)
- 3C: per-athlete synced history + significant correlations (founder rule: immediate if history exists)

**3. Enforced contracts:**
- Athlete Trust Safety Contract (efficiency interpretation) — see `n1_insight_generator.py`
- 119 xfail contract tests for 3B, 3C, Phase 4, Monetization — these become real tests when gates clear

**4. Legacy debt (tracked, not blocking):**
- 8 services with local efficiency polarity assumptions — migrate to `OutputMetricMeta` registry

Do not build features that contradict the principles at the top of the rebuild plan. When completing a phase or clearing a gate, update the phase summary table.

---

## Production Deployment

### Credentials
- **Email:** mbshaf@gmail.com
- **Server:** `root@187.124.67.153` (Hostinger KVM 8 — 8 vCPU, 32 GB RAM)
- **Repo path on server:** `/opt/strideiq/repo`

### Deploy (run on server after SSH)
```bash
cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build
```

### Generate Auth Token (on server, no password needed)
```bash
docker exec strideiq_api python -c "
from core.security import create_access_token
from database import SessionLocal
from models import Athlete
db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
print(create_access_token(data={'sub': str(user.id), 'email': user.email, 'role': user.role}))
db.close()
"
```

### Smoke Check (one-liner, on server)
```bash
TOKEN=$(docker exec strideiq_api python -c "
from core.security import create_access_token
from database import SessionLocal
from models import Athlete
db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
print(create_access_token(data={'sub': str(user.id), 'email': user.email, 'role': user.role}))
db.close()
") && curl -s -H "Authorization: Bearer $TOKEN" https://strideiq.run/v1/home | python3 -m json.tool
```

### Container Names
| Service | Container |
|---|---|
| API | `strideiq_api` |
| Web | `strideiq_web` |
| Worker | `strideiq_worker` |
| Beat | `strideiq_beat` |
| DB | `strideiq_postgres` |
| Cache | `strideiq_redis` |
| Proxy | `strideiq_caddy` |
| Storage | `strideiq_minio` |

### Logs
```bash
docker logs strideiq_api --tail=50
docker logs strideiq_web --tail=50
```

---

## Wiki Currency Contract

`docs/wiki/` is the single onboarding document for this project. If the wiki is stale, the next agent gets the wrong mental model of the system. That is a trust failure, not a documentation gap. **The wiki is mandatory. It must always be current. Same standard as tests.**

### The Rule

Every commit that changes system behavior, surfaces, contracts, models, or deploy posture **must** update the relevant wiki page in the same commit, or in an explicit follow-up commit in the same session before the work is called done. No exceptions.

If you ship a feature, fix a bug class, retire a component, change a default, add/remove a route, change a model id, change a deploy step, change an environment variable, or change a contract — you owe a wiki edit.

### Wiki Map (which page owns what)

| Surface / change | Page that owns it |
|---|---|
| Coach (Kimi K2.5, routing, prompts, tools, guardrails, budgets) | `docs/wiki/coach-architecture.md` |
| Morning briefing (Lane 2A, fingerprint, voice gates, narrative LLM) | `docs/wiki/briefing-system.md` |
| Activity detail page, RSI/Canvas, splits, maps, Runtoons, share | `docs/wiki/activity-processing.md` and `docs/wiki/frontend.md` |
| Routes, components, contexts, data layer, hooks | `docs/wiki/frontend.md` |
| Garmin webhooks, FIT pipeline, OAuth, demo guards | `docs/wiki/garmin-integration.md` |
| Correlation engine layers, AutoDiscovery, fingerprint bridge | `docs/wiki/correlation-engine.md` |
| Plan engine V1 / V2, KB docs, fueling, segments | `docs/wiki/plan-engine.md` |
| Personal Operating Manual, findings display, cascade chains | `docs/wiki/operating-manual.md` |
| Server, containers, Celery/Beat, DB, CI, env vars | `docs/wiki/infrastructure.md` |
| Stripe, tiers, pricing, promo codes | `docs/wiki/monetization.md` |
| Nutrition (parsing, overrides, saved meals, fueling shelf) | `docs/wiki/nutrition.md` |
| Page view tracking, admin usage reports | `docs/wiki/telemetry.md` |
| Cross-domain reports | `docs/wiki/reports.md` |
| Five quality/trust principles, KB registry, OutputMetricMeta | `docs/wiki/quality-trust.md` |
| Architectural decisions (ADR-style) | `docs/wiki/decisions.md` |
| Vision and competitive frame | `docs/wiki/product-vision.md` |
| Cross-cutting changes that touch multiple pages | append to `docs/wiki/log.md` |

If you can't decide which page owns a change, append a dated entry to `docs/wiki/log.md` and link it from the most-relevant page.

### Always Touch `index.md` When…
- A page is added, renamed, or deleted (update the All Pages table)
- A Quick Reference value changes (server IP, container name, model id, deploy command)
- A core architectural surface moves enough that the Start Here ordering needs to change

Always bump the `Last updated:` date in `index.md` when you edit any wiki page in the same session.

### What Counts as a Wiki Update

A wiki update is not a one-line stub. It must:

1. Reflect the **shipped** state, not the proposed state. Specs live elsewhere.
2. Be specific enough that another agent reading only the wiki could rebuild the same mental model the founder has.
3. Remove or move stale content rather than letting it pile up. The wiki is not append-only.
4. Link source files (path-only) where the behavior actually lives, so the next agent can verify with a file read instead of guessing.

### Session-End Check (binding)

Before declaring "tree clean, tests green, production healthy" at end of session:

- [ ] Every commit in this session that changed behavior has a corresponding wiki edit (in the same commit, in a follow-up commit, or a `wiki/log.md` entry).
- [ ] `docs/wiki/index.md` `Last updated:` date is today if any wiki page was edited.
- [ ] No wiki page contradicts what is actually deployed.

If any of these are false, the session is not done.

### What the Wiki Is Not

The wiki does not replace:
- `docs/FOUNDER_OPERATING_CONTRACT.md` — how to work with the founder
- `docs/PRODUCT_MANIFESTO.md` / `docs/PRODUCT_STRATEGY_2026-03-03.md` — vision
- `docs/SITE_AUDIT_LIVING.md` — honest assessment of current state
- `docs/SESSION_HANDOFF_*.md` — per-session state for the next agent
- `docs/specs/*` — forward-looking specs

The wiki is the operational mental model of the running system. Vision docs say what we want; specs say what we plan; the wiki says what is actually live right now. Keep that distinction crisp.

---

## Plan Generator — Session Protocol

This rule is **mandatory** whenever you touch any of:
- `apps/api/services/plan_framework/`
- `apps/api/services/plan_generator.py`
- `apps/api/services/model_driven_plan_generator.py`
- `apps/api/services/constraint_aware_planner.py`
- `apps/api/services/workout_prescription.py`
- `apps/api/services/plan_quality_gate.py`
- `apps/api/services/optimal_load_calculator.py`
- `apps/api/services/plan_framework/load_context.py`
- `apps/api/routers/plan_generation.py`
- Any file under `apps/api/tests/` that imports from the above

### Entry (before first tool call)
1. Read `docs/PLAN_GENERATOR_STATUS.md` in full.
2. Check the **Blocking Issues** section. If any are OPEN, your session must either clear one or explicitly acknowledge why it is not blocking your current task.
3. Check the **Execution Order** section. Work the next step unless the founder has directed otherwise.

### Exit (before last commit)
1. Update `docs/PLAN_GENERATOR_STATUS.md`:
   - Add a row to the Session Log with: date, session ID, commits, what changed, what test proved it, any new blocking issues.
   - Update any checklist rows that changed status. "DONE" requires pasted test output, not just "tests pass."
2. Verify `git status -sb` is clean before closing the session.

### What "DONE" Means

A checklist item is DONE only when:
- The specific test command is recorded in `docs/PLAN_GENERATOR_STATUS.md`
- The output of that test is pasted into the document (or into the Session Log entry)
- The commit SHA that contains the fix is recorded

"Code written" is not DONE. "Tests pass locally" is not DONE without pasted output. "CI is green" is not DONE without the CI run URL.

### What You Must Never Do
- Mark a phase or item DONE without evidence
- Skip the session log entry
- Create a new `BUILDER_INSTRUCTIONS_*.md` file as a substitute for updating `PLAN_GENERATOR_STATUS.md`
- Work on Phase N+1 before Phase N blocking issues are cleared

---

## Companion Documents

`AGENTS.md`, `RULES.md`, and `docs/CLINE_SETUP_GUIDE.md` are the orientation files for any agent starting a session on this repo.

**Recommended session-start read order:**

1. `AGENTS.md` — codebase shape, tech stack, current state, vocabulary, how Michael works, anti-patterns
2. `RULES.md` (this file) — operating rules, governance, wiki contract, deployment
3. `docs/wiki/index.md` — live operational mental model of the deployed system
4. Relevant vision/context docs from the [Session-Start Read Order](#session-start-read-order) above, based on current task

The `.cursor/rules/` directory contains the original source files for all rules above. They remain in place for Cursor IDE sessions. This file (`RULES.md`) is the portable, model-agnostic version.
