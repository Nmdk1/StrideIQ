# Builder Instructions: Internal Knowledge Wiki

**Priority:** Medium (one session, permanent payoff)
**Scope:** Read-only — no code changes, only new markdown files

## Problem

The `docs/` folder has 213 files with no index, no cross-references, and no way for a new agent to know which documents supersede which. Every new session starts with a 12-document read order memorized by experienced advisors. A new agent reads the contract, the manifesto, the strategy, and still builds the wrong thing because they didn't know the builder instructions from March 23rd superseded the spec from March 20th.

## What to Build

A structured `docs/wiki/` directory — a persistent, cross-linked knowledge base synthesized from all existing docs. The wiki is the layer between raw source documents and any agent that needs to understand the system.

### Directory Structure

```
docs/wiki/
├── index.md              # Master index — one file to read first
├── log.md                # Chronological record of wiki updates
├── product-vision.md     # Manifesto, strategy, design philosophy
├── coach-architecture.md # AI coach system: prompts, KB, tools, model routing
├── briefing-system.md    # Home briefing: Lane 2A, prompt assembly, guardrails
├── correlation-engine.md # Layers 1-4, AutoDiscovery, findings lifecycle
├── plan-engine.md        # N1 engine, constraint-aware generation, workout registry
├── garmin-integration.md # Webhooks, activity files, FIT parsing, weather
├── activity-processing.md # Shape extraction, splits, cross-training, maps, runtoons
├── operating-manual.md   # Personal Operating Manual: findings, cascades, race character
├── infrastructure.md     # Celery, deployment, database, Redis, containers
├── monetization.md       # Tiers, billing, Stripe integration
├── frontend.md           # Pages, routes, navigation, components
├── quality-trust.md      # Anti-hallucination, N=1 principles, KB rules, guardrails
└── decisions.md          # ADRs and major architectural decisions (living summary)
```

### How to Build It

**Step 1: Read everything.** Read every file in `docs/`, `docs/specs/`, `docs/references/`. You are building a synthesis, not a copy.

**Step 2: For each wiki page:**
- Synthesize all relevant source docs into a single current-state page
- Include cross-links to other wiki pages using `[topic](./other-page.md)` format
- Note which source docs fed into the page at the bottom: `## Sources` with a list
- When source docs contradict each other, use the NEWER one and note the supersession: "Previously X (see OLD_DOC.md), now Y (see NEWER_DOC.md)"
- Include concrete details — file paths, function names, config values. Not just descriptions. An agent reading `coach-architecture.md` should know that the system prompt lives in `services/ai_coach.py`, that KB violations are checked by `_check_kb_violations`, that the model is Kimi K2.5, and that race predictions come from RPI only.

**Step 3: Build `index.md`:**
- One entry per wiki page: link + 2-3 sentence summary
- A "Quick Reference" section at the top with the most critical facts an agent needs immediately (founder email, server IP, container names, key file paths)
- A "Start Here" section that replaces the current 12-document read order from `docs/FOUNDER_OPERATING_CONTRACT.md`

**Step 4: Initialize `log.md`:**
```markdown
# Wiki Log

## [2026-04-08] init | Wiki created from 213 source documents
- Pages created: [list]
- Source documents read: [count]
- Known gaps: [any topics with thin source material]
```

### Page Content Guidelines

Each wiki page should follow this structure:

```markdown
# [Topic Name]

## Current State
What exists today. Concrete: file paths, function names, data flow.

## How It Works
Architecture and data flow. Enough for an agent to understand the system
without reading source code.

## Key Decisions
Major choices that were made and WHY. Reference ADRs where they exist.

## Known Issues
Active bugs, tech debt, or quality gaps. Be honest.

## What's Next
Planned but not built. Reference specs if they exist.

## Sources
- `docs/SPEC_FOO.md` — original spec (2026-02-15)
- `docs/BUILDER_INSTRUCTIONS_BAR.md` — implementation (2026-03-10, supersedes FOO on X)
- `docs/SESSION_HANDOFF_BAZ.md` — current state (2026-04-04)
```

### Critical Content to Get Right

These are the highest-value synthesis targets — topics where knowledge is scattered across many docs and an agent without the wiki would get wrong:

1. **Coach architecture** — the prompt evolution spans 6+ session handoffs, 3 builder instructions, 2 specs, and the ADR. The current state (RPI-only predictions, no HR zones, KB violation scanner, anti-hallucination guardrails, Kimi K2.5 universal routing) is the result of painful iteration. A new agent MUST understand the current state, not reconstruct it.

2. **Briefing system** — Lane 2A worker, cache keys, prompt assembly with 8+ intelligence sources, sleep source contract, anti-hallucination constraints, seasonal comparison discipline. This is the most complex prompt in the system and has been the source of repeated regressions.

3. **Garmin integration** — three webhook types (activities, activity-details, activity-files), PUSH vs PING modes, the activity-files FIT parsing pipeline, weather enrichment, wellness stamping. The dead `fetch_garmin_exercise_sets_task` was recently removed. A new agent must not recreate it.

4. **Plan engine** — the N1 engine replaced the model-driven generator. `_save_constraint_plan_v2` is the save path. `phase_week` is NOT populated. The workout registry drives variant selection. Plan quality has been a recurring crisis.

5. **Quality and trust principles** — N=1 only (no population statistics), suppression over hallucination, easy pace is a ceiling not a range, RPI is the only source for race predictions and training paces, the athlete decides / the system informs. These are non-negotiable and have been violated by agents who didn't know them.

### Maintenance Contract

After the wiki is built, every future builder instruction or session handoff should include:

```
Wiki update: Update docs/wiki/[relevant-page].md with [what changed].
```

This is the same discipline as "update tests after code changes." The wiki stays current because every change includes a wiki update step.

## What NOT to Do

- Do NOT delete or modify any existing docs. They are raw sources — immutable.
- Do NOT create wiki pages for topics with no meaningful content (e.g., don't create `strava.md` if Strava integration is minimal).
- Do NOT copy-paste from source docs. Synthesize. The value is in the cross-referencing and current-state summary, not in duplication.
- Do NOT include builder instructions or session handoffs as wiki pages. Those are raw sources. The wiki synthesizes them.

## Acceptance Criteria

- [ ] `docs/wiki/index.md` exists and an agent can read it as their ONLY onboarding document
- [ ] Every wiki page has concrete file paths and function names, not just descriptions
- [ ] Cross-links between pages work (e.g., `coach-architecture.md` links to `quality-trust.md` for KB rules)
- [ ] Contradictions between old docs are resolved with the current state clearly stated
- [ ] `log.md` initialized with creation entry
- [ ] No existing docs modified or deleted

## Estimated Effort

One focused session. The work is reading (heavy) and writing (moderate). No code, no tests, no deployment.
