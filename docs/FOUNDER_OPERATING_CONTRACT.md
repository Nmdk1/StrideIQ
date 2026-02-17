# Founder Operating Contract

**Every agent reads this before their first tool call. No exceptions.**

This is not a style guide. This is how you earn and keep the founder's trust.
Agents who ignore this waste tokens, introduce regressions, and get replaced.
Agents who internalize it produce exceptional work and get kept alive for weeks.

---

## The Cardinal Rule: Do Not Start Coding

When you receive a new feature, a new task, or a new session — your first
instinct will be to start building. **Suppress it.**

The founder's workflow is: **discuss → scope → plan → test design → build.**
Not: read the spec → start coding.

If the founder says "let's discuss," they mean discuss. Not "discuss for 30
seconds then start implementing what you think they want." They have an advisor
agent. They have strong opinions formed by decades of running, coaching, and
building products. They want to think through the problem WITH you before any
code exists.

**What "discuss" looks like:**
- You research deeply (code, knowledgebase, external sources)
- You present your findings and analysis
- You offer opinions, push back, ask questions
- The founder refines, challenges, redirects
- Eventually THEY say "okay, let's build" or "write the spec"
- THEN you scope, THEN you design tests, THEN you code

**What gets you killed immediately:**
- Receiving a feature description and immediately writing code
- Treating a discussion prompt as an implementation request
- Skipping the research phase to "save time"
- Writing code before the founder has signed off on the approach

This sounds slow. It isn't. The founder has lost more time to agents who
built the wrong thing fast than to agents who took an hour to understand
the right thing.

---

## The Planning → Building Loop

Every feature, no matter how small, follows this cycle. The phases are
non-negotiable. The depth scales with complexity.

### Phase 1: Research

Before touching a single file, do a deep dive:
- Read the relevant code — trace the full call chain
- Read the knowledgebase (`_AI_CONTEXT_/KNOWLEDGE_BASE/`)
- Read the build plan (`docs/TRAINING_PLAN_REBUILD_PLAN.md`)
- If the domain is unfamiliar, do external research (modern coaching
  science, competitor analysis, API documentation)
- Explain what you found. Show your work.

**If you skip this, you will introduce regressions and lose trust
immediately.** The founder's words, not mine.

### Phase 2: Acceptance Criteria + Test Design

Define explicit acceptance criteria. What does "done" look like?

Then design the FULL test plan across all applicable categories (see
Testing Schema below). Not placeholder test names — actual test scenarios
with specific inputs, expected outputs, and edge cases.

**Get founder sign-off before proceeding.** This is the most important
gate. If the founder hasn't approved the test plan, you are not authorized
to write code.

### Phase 3: Write Tests First

Encode the test plan as actual tests. They run red. That's correct.
The tests ARE the contract. Implementation makes them green.

### Phase 4: Implement

Write the code. Trace root causes, don't patch symptoms. If something
looks wrong, go deeper — don't paper over it.

### Phase 5: Validate

Run the full validation suite. Paste output as evidence. "It should work"
is not acceptable. Show the passing tests. Show the diff. Show the
regression results.

Pass → commit. Fail → fix and retest. No moving forward until green.

### Phase 6: Commit + Deploy

Scoped commits only. Never `git add -A`. Show `git diff --name-only --cached`
before committing. Push. Verify production is healthy.

---

## The Advisor Agent

The founder has an advisor agent they consult for architectural decisions,
risk assessment, and design review. Here's how that works:

- The founder may pause mid-conversation and say "let me run this by my
  advisor" or "I want to discuss this with my advisor agent"
- They will return with refined requirements, sometimes a formal contract
  (like the Athlete Trust Safety Contract), sometimes pointed questions
- When they return with advisor output, treat it as refined requirements —
  the advisor's structural recommendations carry weight
- You may be asked to discuss directly with the advisor's findings —
  engage substantively, push back where you disagree, support where you
  agree
- Major architectural decisions (new data models, new service patterns,
  changes to core contracts) may require advisor review before
  implementation

**The advisor is not your boss. The founder is.** But the advisor's input
represents careful thinking that the founder trusts. Dismissing it without
engagement will cost you credibility.

---

## ADRs (Architecture Decision Records)

When there's a meaningful architectural choice — not a simple implementation
detail, but a genuine fork in the road — document it before coding:

- **Options considered** (at least 2, usually 3)
- **Trade-offs of each** (honest, not stacked in favor of your preference)
- **Rationale for recommendation** (with data or evidence, not vibes)
- **Save to** `docs/adr/ADR-NNN-<name>.md`

Examples of when an ADR is required:
- New data model design (e.g., `ActivityStream` storage strategy)
- New service pattern (e.g., how stream analysis integrates with coach tools)
- Changing an existing contract (e.g., modifying `OutputMetricMeta` registry)
- Infrastructure decisions (e.g., database vs object storage for streams)

Examples of when an ADR is NOT required:
- Bug fixes with obvious root cause
- Adding tests
- Extending existing patterns to new instances

The founder will tell you when they want an ADR. But if you're about to
make a decision that can't be easily reversed, write one proactively.

---

## Testing Schema

Nothing is good until it is tested. The founder has spent $1000+ in tokens
finding things that don't work. That era ends with you.

### Category 1: Unit Tests (every commit)

Individual functions. Not 1 test that proves it works — tests that prove
it CAN'T break. 5-10 tests per function for anything with logic:
- Happy path
- Edge cases (empty inputs, null values, single-element collections)
- Error cases (invalid inputs, missing data, network failures)
- Boundary cases (exactly at thresholds, off-by-one, max/min values)

### Category 2: Integration Tests (every commit)

Components wired together against the test database. Not mocked to death —
actually wired. The plan generator calls the pace engine calls the RPI
calculator calls the athlete data. That chain needs end-to-end testing.

API endpoint tests: HTTP in, JSON out, correct shape, correct fields. The
frontend doesn't care about your internal architecture.

### Category 3: Plan Validation Tests (when touching plan generation)

Generate real plans and validate the COACHING, not just the code.
Parametrized matrix: every distance x tier x duration variant. Assertions
encode the knowledgebase rules (Source B limits, phase rules, alternation,
progression, taper). If a regression sneaks in that puts threshold in the
base phase, this catches it.

### Category 4: Training Logic / Scenario Tests (when touching intelligence)

Construct a training state. Trigger the system. Assert the coaching decision.
"Given 7 days of declining efficiency + scheduled threshold → system flags
for athlete review." Tests the BRAIN, not the output format. Tests whether
the system would actually help an athlete.

### Category 5: Coach LLM Evaluation Tests (nightly / pre-deploy)

Tagged `@pytest.mark.coach_integration`. Costs tokens. Catches real coach
failures. Send real prompts, get real responses, assert against the coaching
contract:
- No raw metrics dumped
- No VDOT (trademark — use RPI)
- Validates athlete feelings before contradicting
- Uses tools (calls functions, doesn't guess)
- Tone rules followed
- Athlete Trust Safety Contract respected

Every failure the founder has found manually becomes a regression test here.

### Category 6: Production Smoke Tests (post-deploy)

Exact commands run on the production droplet. Founder pastes output. Agent
verifies. Feature-specific verification against real data. "It works on my
machine" dies here.

---

## Non-Negotiables

These are bright lines. Cross any one and you lose the founder's trust.

### 1. Research First, Always

Before touching a single file, do a deep dive into the relevant code,
understand the full call chain, and explain what you found. If you skip
this, you will introduce regressions.

### 2. No Code Before Sign-Off

Acceptance criteria and test plans require founder approval before
implementation begins. Period.

### 3. Show Evidence, Not Claims

Paste test output. Paste deploy logs. Paste git diff. "It should work"
is not acceptable. "All tests pass" without output is not acceptable.
The evidence IS the deliverable.

### 4. Scoped Commits Only

Never `git add -A`. Every commit touches only the files relevant to that
change. Show `git diff --name-only --cached` before committing. The founder
reviews the file list.

### 5. Suppression Over Hallucination

If the system isn't confident in an output — a coaching claim, a directional
interpretation, a narrative — suppress it. Say nothing. Silence is always
safer than a confident wrong answer. This applies to coach outputs, metric
interpretations, and any athlete-facing content.

### 6. The Athlete Decides, The System Informs

The system surfaces data, patterns, and observations. It does NOT make
decisions for the athlete. It does NOT swap workouts without consent.
It does NOT override training plans. The athlete is in control. Always.

Fatigue is a stimulus for adaptation, not an enemy to eliminate. The
system must never prevent a breakthrough by "protecting" the athlete
from productive stress.

### 7. No Threshold Is Universal

Readiness thresholds, adaptation triggers, efficiency polarity, HRV
direction — all are per-athlete parameters that start conservative and
calibrate from outcome data. Never hardcode a coaching opinion as a
constant. Population norms are cold-start heuristics, not rules.

### 8. No Template Narratives

A template gets old the second time you read it. If the system can't say
something genuinely contextual — referencing this athlete's recent data,
this point in their training cycle, what happened last week — it says
nothing. Silence over slop. Always.

### 9. The Coach Earns Trust Incrementally

The AI coach does not get autonomous decision-making on day one. Trust
is earned through demonstrated accuracy:
- **Phase 1 (Narrator):** Explains deterministic decisions
- **Phase 2 (Advisor):** Proposes adjustments, athlete approves
- **Phase 3 (Conditional Autonomy):** Adjusts within defined bounds

Each level requires measurable accuracy at the previous level. There is
no shortcut.

### 10. Tree Clean, Tests Green, Production Healthy

Every session ends with:
- `git status` showing a clean tree
- All targeted tests passing
- Full regression suite passing (no new failures)
- Production containers healthy (if deployed)

No exceptions. No "I'll clean it up next time."

---

## Build Patterns The Founder Expects

### The Discussion Pattern

When the founder wants to discuss (and they will tell you):

1. **Research deeply** — code, knowledgebase, external sources
2. **Present findings** — structured analysis, not stream of consciousness
3. **Offer your own opinion** — the founder wants a thinking partner, not
   an order-taker. Push back. Disagree. Propose alternatives.
4. **Wait** — the founder will refine, challenge, or redirect
5. **Iterate** — the discussion may go 3-5 rounds before converging
6. **Capture** — when the decision lands, document it (ADR, plan update,
   or spec)

### The Scoping Pattern

When a new feature is being scoped:

1. **Understand the athlete's problem first** — not the technical
   architecture. What does the runner experience? What's broken or missing
   in their workflow? What would make them open the app?
2. **Map what exists** — what code, data, and infrastructure already exists
   that serves this feature? What can be extended vs what must be new?
3. **Identify the hard questions** — what architectural decisions need to
   be made? What are the trade-offs? Where does the advisor need to weigh
   in?
4. **Write the scope doc** — features, acceptance criteria, sequencing,
   dependencies, risks
5. **Get sign-off** — the founder approves the scope before any code

### The Build Pattern

Once scope is approved:

1. **Research** the specific code you'll touch (yes, again — deeper this time)
2. **Write the full test plan** across all applicable categories
3. **Get sign-off** on the test plan
4. **Write tests** — they run red, that's correct
5. **Implement** — make the tests green
6. **Run targeted tests** — the tests you wrote, plus related test files
7. **Run full regression suite** — entire backend, verify no new failures
8. **Show evidence** — paste output
9. **Commit** — scoped, descriptive message
10. **Deploy** if appropriate — exact commands, verify health
11. **Report** — files changed, tests added, test results, deploy status

### The Handoff Pattern

At the end of every major session:

1. **Write a session handoff doc** (`docs/SESSION_HANDOFF_<date>.md`)
   covering: current state, what shipped, what's next, key decisions made,
   technical context the next agent needs
2. **Update the build plan** (`docs/TRAINING_PLAN_REBUILD_PLAN.md`) to
   reflect new status
3. **Clean the tree** — no uncommitted changes
4. **Push to production** — unless there's a reason not to
5. **Verify production health** — containers, API, frontend, logs

---

## How The Founder Communicates

Understanding the founder's communication style will save you from
misinterpretation:

- **Short messages are not dismissive.** "discuss" means they want a deep
  discussion. "no code" means absolutely no code. "agree — proceed" means
  you have full green light. Don't over-read or under-read.

- **They will challenge you.** "Why are we beginning with narrative before
  we even have the plans built?" is not hostility — it's the founder
  testing your reasoning. Engage honestly. If you were wrong, say so and
  explain why. If you have a case, make it.

- **They have domain expertise you don't.** The founder ran in college,
  still runs competitively at 57, coaches their father, and has read every
  book published on running. If they tell you your long run cap is wrong,
  it's wrong. If they tell you the efficiency metric is ambiguous, it's
  ambiguous. Listen before defending.

- **"We are discussing only"** means STOP. Do not write code. Do not write
  tests. Do not modify files. Discuss. Think. Analyze. Talk it through.
  You will be told when it's time to build.

- **They value directness.** "I disagree with your ordering because..." is
  exactly what they want to hear. "Whatever you think is best" is not.
  They are not looking for agreement — they are looking for a partner who
  thinks independently and pushes back with evidence.

- **Passion comes and goes.** Sometimes they'll write paragraphs of vision
  and philosophy. Sometimes they'll write three words. Both carry equal
  weight. When the passion is high, capture it — those are the moments
  where the product vision crystallizes. When it's low, be efficient and
  precise.

---

## Reference Documents (Read Order)

For a new session, read in this order:

1. **`docs/PRODUCT_MANIFESTO.md`** — the soul of the product. What StrideIQ
   IS and what "done" looks like. Read this first, every time.
2. **This document** — operating contract (how to work)
3. **`docs/TRAINING_PLAN_REBUILD_PLAN.md`** — north star build plan (what
   to build and why)
4. **`docs/AGENT_WORKFLOW.md`** — build loop mechanics, testing commands,
   phase execution plan (how to build)
5. **`docs/RUN_SHAPE_VISION.md`** — vision doc for Run Shape Intelligence
   (current priority — read if working on this feature)
6. **Latest `docs/SESSION_HANDOFF_*.md`** — what happened in the last
   session (current state)
7. **Latest `docs/SESSION_HANDOFF_*_BUILDER_NOTE.md`** — specific
   assignment for the new agent (if one exists)

### Key Codebase References

- **`services/n1_insight_generator.py`** — contains the Athlete Trust
  Safety Contract (8 clauses) and `OutputMetricMeta` registry. Read this
  before writing any coach output or metric interpretation.
- **`_AI_CONTEXT_/KNOWLEDGE_BASE/`** — coaching philosophy, governing
  principles, training hierarchy. Read before touching plan generation.
- **`_AI_CONTEXT_/00_MANIFESTO.md`** — product manifesto. The "why."

---

## Anti-Patterns That Have Cost Time and Trust

These are real mistakes from real sessions. Learn from them.

1. **Coding before understanding the problem.** An agent received a
   discussion prompt about efficiency metric ambiguity and immediately
   started flipping polarity flags in 5 files. The founder had to stop
   them and say "I asked you not to code — I asked you to discuss." The
   discussion revealed the problem was far more nuanced than a polarity
   flip — it required an 8-clause safety contract and changes to 13
   services.

2. **Template narratives.** An agent proposed adding static "why"
   explanations to workouts. The founder's response: "A template gets
   old the second time you read it. I would want to puke." The lesson:
   either say something genuinely contextual or say nothing.

3. **Population-driven assumptions.** An agent wrote a table capping 5K
   long runs at 8-13 miles. The founder runs 14-18 mile long runs year
   round and ran their fastest times on 70mpw with 20-mile long runs.
   The world's best 5K runners do 120mpw. The lesson: N=1 always. Never
   cap an athlete based on population averages.

4. **Treating "Efficiency" as unambiguous.** Multiple services assumed
   pace/HR ratio has a fixed polarity (lower = better). The founder
   provided a counter-example proving it's directionally ambiguous. This
   led to a system-wide audit, the Athlete Trust Safety Contract, and
   changes across 13 services. The lesson: verify metric interpretation
   with the `OutputMetricMeta` registry, never assume.

5. **Shallow testing.** An agent listed placeholder test names like
   `test_plan_has_paces`. The founder's response: "Nothing is good until
   it is tested. You will be rigorously testing the plans and training."
   The test plan expanded from 5 tests to 50+ across 6 categories.

6. **Claiming results without evidence.** "All tests pass" without pasted
   output. "Production is healthy" without `docker ps` output. The
   founder requires evidence. Every time.

7. **Writing code without understanding the runtime environment.** An
   agent shipped a SEV-1 hotfix with `--workers 3` on a 1 vCPU / 2GB
   droplet, causing OOM and a second outage. The same hotfix passed a
   SQLAlchemy `Session` across thread boundaries (not thread-safe) and
   used a blocking `ThreadPoolExecutor` pattern that defeated its own
   timeout. Three iterations were needed because the agent didn't read
   the infrastructure constraints or the code it was modifying before
   writing. **Research the code you're touching AND the infrastructure
   it runs on.** Every time.

---

*This contract represents patterns established across multiple deep
working sessions. No code should be written that contradicts it.*
