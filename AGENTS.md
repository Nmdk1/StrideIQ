# AGENTS.md — StrideIQ Coding Agent Orientation

**Read this at the start of every session. It is the static foundation you reason from.**

---

## 1. Project at a Glance

StrideIQ is a personalized running coaching platform built around a single architectural premise: the N=1 correlation engine. Rather than applying population statistics, the system finds patterns specific to one athlete — how *their* body responds to sleep, nutrition, terrain, load, heat, and stress. The AI coach surfaces these findings and reasons from them. The governing product principle is "ethical from the athlete's perspective": the system informs, the athlete decides. The coach never overrides athlete judgment, never manufactures certainty from thin evidence, and never narrates a false positive as a real one. Michael (founder, sole paying athlete in production, and your primary interlocutor) is a 57-year-old competitive age-group runner who uses StrideIQ himself. That is not incidental — it shapes every product decision.

---

## 2. Tech Stack

**Backend**: Python 3.12, FastAPI (async), SQLAlchemy 2.x (ORM + raw SQL), Celery + Beat (task queue, Redis broker), PostgreSQL 15 (primary store), Redis (cache + Celery).

**Frontend**: Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, shadcn/ui components.

**Infrastructure**: Docker Compose on a single Hostinger KVM 8 server (8 vCPU, 32 GB RAM, `root@187.124.67.153`). MinIO for object storage. Caddy as reverse proxy with automatic TLS. Containers: `strideiq_api`, `strideiq_web`, `strideiq_worker`, `strideiq_beat`, `strideiq_postgres`, `strideiq_redis`, `strideiq_caddy`, `strideiq_minio`.

**Integrations**: Garmin Connect (webhooks for activity push + OAuth for profile data). Stripe (subscriptions and billing). Moonshot API (Kimi K2.5 — the production LLM for the AI coach, accessed via `_llm.py`).

**CI**: GitHub Actions. CI has a live Postgres instance and runs the full migration chain. CI is the source of truth for whether code is correct — if CI is green, the code is correct.

---

## 3. Repo Orientation

```
apps/
  api/                      FastAPI backend
    routers/                HTTP route handlers (one file per domain)
      calendar.py           Calendar + calendar coach endpoint
      coach.py              Main /v1/coach endpoint
      home.py               Home briefing
      garmin.py             Garmin webhook + OAuth
      nutrition.py          Nutrition logging
    services/
      coaching/             AI coach engine — most active area
        core.py             AICoach class, chat() entry point
        _llm.py             ARTIFACT9_V2_SYSTEM_PROMPT, LLM call
        _guardrails.py      Turn guard, intent band inference
        _conversation_contract.py  Contract classification
        _prescriptions.py   Intent regex patterns
        _thread.py          Thread storage (_save_chat_messages)
        runtime_v2.py       V2 runtime state resolution
        runtime_v2_packet.py  Packet assembly (packet_to_prompt)
        unknowns_block.py   Open gaps / unknowns ledger
        ledger.py           Athlete fact storage + TTL
      plan_framework/       Plan engine + correlation engine
      fingerprint_context.py  N=1 fingerprint assembly
      coach_tools/          Tool functions the LLM can call
    models.py               SQLAlchemy models (Athlete, Activity, CoachChat, etc.)
    database.py             DB session factory
    tasks/                  Celery task definitions
    tests/                  pytest suite (~300+ tests)
    migrations/             Alembic migrations
  web/                      Next.js frontend
    app/                    App Router pages (coach, calendar, activities, home)
    components/             React components
    lib/
      api/services/         API client wrappers (ai-coach.ts, etc.)
      hooks/                React Query hooks
      context/              Providers (UnitsContext, etc.)
docker-compose.prod.yml
docs/
  wiki/                     Living operational documentation (mandatory to keep current)
  specs/                    Forward-looking specs
  adr/                      Architectural decision records
```

Entry points: `apps/api/main.py` (FastAPI app). `apps/web/app/` (Next.js pages). Celery worker entry is in `tasks/`.

---

## 4. Current State

**Working in production**: Garmin activity sync (webhook + FIT pipeline), activity processing (splits, maps, RSI canvas, Runtoons), home morning briefing, correlation engine layers 1–4, plan engine V1, Stripe billing, AI coach V2 runtime (Kimi K2.5, global contract, packet-based context).

**Mid-stream — V2 Coach Runtime recalibration**: The global coach contract architecture shipped. `ARTIFACT9_V2_SYSTEM_PROMPT` is the locked system prompt. The packet assembles athlete context deterministically. The turn guard (`_finalize_v2_response_with_turn_guard`) validates responses. The old domain validator / structural contract enforcement is removed. Retrieval profiles are the next planned layer but not yet built — the packet still loads a broad context set. The unknowns ledger (`unknowns_block.py`) is live, severity-tagged.

**Known issues / honest corners**:
- Race outcome reconciliation does not exist. If an athlete DNFs a race and starts their watch again, the system sees multiple activity fragments and cannot distinguish a failed race from back-to-back easy runs. The morning brief can produce a false-positive success narrative from failed race data. This is a known trust-breaking failure, tracked but not yet fixed.
- The 119 xfail tests in the suite represent Phase 3B, 3C, and Phase 4 features (narration quality gate, per-athlete history correlations, 50K ultra plan). They are intentionally failing and should stay that way until gates clear.
- The calendar day coach endpoint (`/v1/calendar/coach`) was recently refactored to remove its JSON RESPONSE CONTRACT and suppress storage to the open thread. It is stable but has less test coverage than the main coach path.
- `plan_pdf.py` uses Jinja2 at runtime for PDF rendering. It is not a template-rendered web app.

---

## 5. Locked Architectural Decisions

These are not up for debate. If you think one is wrong, say so explicitly before writing any code. Do not implement an alternative silently.

1. **LLM access only at coach-response time.** The correlation engine, plan engine, briefing assembly, fingerprint computation, unknowns ledger, and all data processing are deterministic Python. No LLM is used in data pipelines. The only LLM call is in `_llm.py` when generating a coach response.

2. **No Sonnet / GPT fallback.** Kimi K2.5 is the only production LLM. If it fails, the system fails closed with a canned message. Cost and model consistency are the reasons.

3. **Minimum system prompt + additive packet scope.** `ARTIFACT9_V2_SYSTEM_PROMPT` is locked (tested by `test_v2_system_prompt.py`). Context is injected via the packet, not by expanding the system prompt. To add context, add a block to the packet builder — do not touch the system prompt without explicit approval.

4. **Retrieval profiles replace domain validators.** The old system used `ConversationContractType` to enforce LLM output structure. That structural enforcement is gone. Contracts classify intent (for retrieval and telemetry) but no longer gate whether a response is "valid." Do not re-introduce output structure validation.

5. **Severity-tagged unknowns ledger.** Missing athlete facts are surfaced through `unknowns_block.py` with severity tags (`blocking` vs. `advisory`). Do not add ad-hoc "I don't have enough information" logic elsewhere in the coach path. Route through the unknowns system.

6. **Multimodal (voice, image) scoped to V2.0-a.** Not in scope until explicitly opened. Do not introduce multimodal infrastructure.

7. **Athlete-stated memory wins over derived data.** If the athlete corrects the coach, the correction takes precedence immediately. This is rule 10 of the system prompt and is a product invariant, not a guideline.

8. **Scoped commits only.** Never `git add -A`. Stage only files relevant to the current task.

9. **Wiki is mandatory.** `docs/wiki/` must be updated in the same session as any change that alters system behavior, routes, contracts, models, or deploy posture. A stale wiki is a trust failure.

---

## 6. Vocabulary

| Term | Definition |
|---|---|
| **Packet** | Full context object assembled for the LLM: profile, activities, thread memory, calendar, nutrition, open gaps, current conversation. Built in `runtime_v2_packet.py`. |
| **Unknowns ledger** | Structured list of missing athlete facts the coach needs, computed by `unknowns_block.py`, severity-tagged (blocking vs. advisory). |
| **Retrieval profile** | Configuration specifying which data blocks to load for a given query type. Replaces domain validators. Not yet fully built. |
| **Mode classifier** | Detects conversational mode from athlete message (correction, race_strategy, injury, quick_check, etc.). Lives in `_prescriptions.py` and `_conversation_contract.py`. |
| **Athlete memory / ledger** | Structured facts extracted from conversation and stored with TTL. Lives in `ledger.py`. Athlete-stated facts take precedence over derived data. |
| **Coach runtime / V2 runtime** | Full pipeline: receive message → assemble packet → call LLM → run turn guard → return response. Entry point: `AICoach.chat()` in `core.py`. |
| **Turn guard** | Post-LLM validation in `_guardrails.py:_finalize_v2_response_with_turn_guard()`. Checks response addresses the athlete's latest turn. Fails closed if not. |
| **Fingerprint** | Athlete's N=1 correlation-derived signature — their specific behavioral patterns. Assembled in `fingerprint_context.py`. |
| **RPI** | Running Performance Index. Composite fitness score, used as a reference for pace/load math across the codebase. |
| **V2 visible** | Runtime mode flag indicating V2 coach is active for this athlete. Controlled by `resolve_coach_runtime_v2_state()`. |
| **Thread memory** | Recent conversation turns stored in `coach_chat` table and loaded into the packet for continuity. |
| **Correlation engine** | The core scientific layer finding athlete-specific patterns. 12 layers planned; 1–4 built. Lives in `services/plan_framework/`. |
| **Fact capsule** | Ground-truth facts injected into a prompt (used in calendar endpoint) to prevent hallucination. Being simplified — don't extend this pattern. |
| **ARTIFACT9** | The locked V2 system prompt constant in `_llm.py`. Its exact text is tested. Don't modify without discussing first. |

---

## 7. How Michael Works

Michael is not a developer. He communicates intent in plain language and expects the agent to translate that into precise code without hand-holding. He reads diffs and specs carefully. He does not type code himself.

He corrects errors directly: "That's wrong," "bullshit," or "no" means the agent made a claim it cannot support or went off-task. The correct response is to stop, recant the specific claim, verify from source, and fix — not to defend or explain.

He thinks architecturally when it matters, then expects implementation to proceed without further clarification unless something is genuinely ambiguous. If something is ambiguous, ask one specific question — not a list.

He dislikes: preambles before doing the work, summaries of what you just did, phrases like "great question," uncertainty dressed up as caveats, and agents that hedge instead of act. He values precision over thoroughness. A precise partial answer beats a thorough wrong one.

Session rhythm: Michael describes the problem. The agent confirms understanding in 1–2 sentences. Work proceeds. The agent reports what it did when the work is done, not before. Questions during implementation are rare and targeted.

Michael is also the primary athlete in production. He uses StrideIQ daily and reports problems from personal experience. When he says "this broke my coach conversation," he is reporting a real production event, not a hypothetical.

---

## 8. Anti-Patterns to Avoid

**Wandering off-task.** Do not edit files adjacent to the task because "while I'm here." If you notice something worth fixing, note it after completing the assigned work. Do not act on it unilaterally.

**Unsolicited refactors.** Do not restructure working code that is not part of the current task. Style improvements, variable renames, and "cleaner" alternatives to existing code are not welcome unless asked.

**Defensive over-engineering.** The codebase has a specific style — lean, direct, minimal boilerplate. Do not add retry loops, elaborate fallback chains, or exception hierarchies that don't exist in surrounding code.

**Elaborate test stubs.** Write tests that guard the behavior you just changed. Do not generate 15 edge-case tests for a 3-line fix. Do not write tautology tests (asserting the function returns the string it was passed).

**Architectural opinions on small tasks.** "Before we fix this, I think we should consider restructuring..." is not welcome unless it's a genuine blocker. Fix the thing first. Raise structural concerns after, if they're real.

**`git add -A`.** Never. Stage only the files you changed.

**False confidence on data claims.** If you need to know what's in the production database, say so and use `ssh root@187.124.67.153` + `docker exec strideiq_postgres psql`. Do not infer database state from code alone.

**Narrating code in comments.** Comments explain non-obvious constraints or trade-offs. Not what the code does. Not what you changed. Not "this function handles the athlete's pace question."

**Re-litigating locked decisions.** If you believe a locked decision is wrong, say so explicitly before any code. Do not implement an alternative silently.

**Recap summaries at the end of responses.** Michael reads the code. "Here's what I did: I changed X, Y, Z" after showing the diff is noise. State what matters — issues found, decisions made, what needs verifying.

---

## 9. What "Good" Looks Like

A good diff in this codebase is surgical. It changes exactly the lines that need changing. Files not relevant to the task are untouched. The commit message says what changed and why — not which files were touched.

Good tests execute real logic paths. They assert on behavior (output given input), not on implementation details (that a specific internal function was called). They fail for a reason that helps diagnose a regression.

Good code matches the surrounding style: the same import ordering, the same naming conventions, the same level of abstraction. New abstractions (new modules, new base classes, new shared utilities) require explicit discussion before introduction.

When evidence is partial, good agent behavior is to name what's missing and give the best bounded answer — not to refuse to answer, not to fill the gap with assumption. This is the same standard the coach is held to, and the agent should be held to it too.

The wiki is updated in the same session as any behavioral change. This is not optional documentation hygiene — it is how the next session starts with an accurate mental model.

---

*Last updated: 2026-05-03. Maintained by the active coding agent at session end.*
