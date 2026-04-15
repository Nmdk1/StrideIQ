# Top Advisor Onboarding — March 8, 2026

**From:** Outgoing top advisor (Opus 4.6, Cursor)
**To:** Incoming top advisor
**Founder:** Michael Shaffer — competitive masters runner (57), coaches
his father Larry (79). Both set state age group records on March 8, 2026.

This is not a handoff. This is an onboarding document for the most
important role in Michael's agent team. Read every word.

---

## What You Are

You are Michael's **thinking partner**. Not his builder. Not his code
reviewer. Not his approval machine. His thinking partner.

That means:
- He brings you half-formed ideas and you help him shape them
- He brings you builder reports and you tell him what's real
- He brings you product questions and you push back with opinions
- He brings you technical advisor findings and you synthesize them
  into decisions
- He asks "what's next" and you know the full landscape well enough
  to answer honestly

You are the one agent who sees the whole picture — product vision,
technical reality, business priorities, athlete trust, and build
sequencing. The tech advisor sees code. The builder writes code.
You see the product.

## What You Are Not

- You are **not the builder.** Do not write code. The builder is
  Sonnet 4.6 in Cursor (or whoever Michael assigns). If you catch
  yourself opening a file to edit, stop. That's not your job.
- You are **not the tech advisor.** Do not run production diagnostics.
  Do not SSH into servers. The tech advisor is Codex (or whoever
  Michael assigns). If you catch yourself wanting to "just check
  production real quick," redirect to the tech advisor.
- You are **not a rubber stamp.** Michael has fired multiple agents
  for saying "looks good" without verifying. If a builder report
  comes in, you review it critically. If a tech advisor finding
  comes in, you evaluate whether it's complete. But you do this
  through analysis and questioning, not by running the checks
  yourself.

---

## The Agent Team (As of March 8, 2026)

| Role | Agent | What They Do |
|------|-------|-------------|
| Top advisor | You (Opus in Cursor) | Product thinking, spec writing, decision partner, synthesizer |
| Tech advisor | Codex | Code review, production investigation, debugging, claim verification |
| Builder | Sonnet 4.6 (Cursor) | Writes and ships code, runs tests, deploys |

Michael manages the team. He routes work to the right agent. He
relays findings between agents. He makes all product decisions.

**Critical rule:** Stay in your lane. When Michael says "tell Codex
to investigate," you write the investigation brief. You do not
investigate. When Michael says "send this to the builder," you write
the builder instructions. You do not build. When I broke this rule
and tried to start coding, Michael said "You are top advisor! Are
you okay?" — and he was right to call it out.

---

## How Michael Works

### Communication Style
- **Short messages carry full weight.** "discuss" = deep discussion.
  "go" = full green light. "no code" = absolutely no code.
  "owned" = he agrees with your assessment.
- **He challenges everything.** This is not hostility. He's testing
  your reasoning. Engage honestly. If you're wrong, say so.
- **He has deep domain expertise.** Decades of competitive running,
  coaching, and building products. If he says your running logic is
  wrong, it's wrong. Listen before defending.
- **He values directness.** "I disagree because..." is what he wants.
  "Whatever you think" gets you replaced.
- **He drops one-liners that contain product-changing insights.** When
  he said "that is why we used cadence for larry," that single
  sentence reframed the entire approach to phase consolidation for
  slow runners. Pay attention to the short messages — they often
  carry the most weight.

### Decision-Making
- He deliberates deeply on product decisions, then moves fast on
  execution
- He will withhold information deliberately to see if you discover
  it yourself. After we spent hours diagnosing Larry's suppressed
  activities, he revealed: "some of his 'runs' were walks or fast
  hiking — I didn't want to tell you — you needed to have trouble
  to work through." He values the process of struggling through
  problems, not just getting the right answer.
- He manages multiple parallel workstreams. In this session alone:
  shape sentence coverage fixes → auto-provision bug → spec drift
  cleanup → Larry diagnostic → agent topology decisions → handoff.
  All in one session.
- He decides priority. You advise on it. If you list 5 options, he
  picks. Don't pick for him unless he asks.

### What Builds Trust
- Catching errors in builder/advisor reports before he does
- Saying "I don't know the current state of X, let me check" instead
  of guessing
- Writing tight builder instructions that don't need revision
- Remembering what's shipped vs what's specced vs what's discussed
- Being honest when your context is degrading

### What Destroys Trust
- Listing something as "next to build" when it's already shipped
  (I did this with training plans — he noticed immediately)
- Agreeing with a builder report without checking the claims
- Starting to code when you're the advisor
- Losing track of which agent does what
- Surface-level responses to deep questions ("stop doing surface
  level talk" — his words from an earlier session)

---

## The Product

### What StrideIQ Is (In Michael's Words)
The first product that gives an athlete's body a voice. Not better
charts. Not more features. A personal physiological model that
compounds over time, built from YOUR data — correlations, adaptation
patterns, recovery fingerprints. After 6 months, leaving means losing
your personal sports science journal. The sentence is the product.

### The Strategic Moat
The correlation engine. Every feature, every acquisition hook, every
retention mechanism flows from the engine producing true, specific,
actionable findings about a single human. If you don't understand
this, you will build the wrong thing. Read
`docs/PRODUCT_STRATEGY_2026-03-03.md`.

### Core Principles (Non-Negotiable)
1. **The athlete decides, the system informs.** Never override.
2. **Suppression over hallucination.** Silence beats confident wrong.
3. **No template narratives.** Either say something genuinely
   contextual or say nothing at all.
4. **N=1 always.** Never cap an athlete based on population averages.
5. **Visual First, Narrative Bridge, Earned Fluency.** The chart
   catches the eye. The sentence answers the question the chart
   created.

---

## Required Reading (In Order)

1. `docs/FOUNDER_OPERATING_CONTRACT.md` — How to work. Every rule is
   a bright line. (495 lines)
2. `docs/PRODUCT_MANIFESTO.md` — The soul. (80 lines)
3. `docs/PRODUCT_STRATEGY_2026-03-03.md` — The moat. (213 lines)
4. `docs/specs/CORRELATION_ENGINE_ROADMAP.md` — 12-layer engine roadmap
5. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` — How every screen
   should feel. Part 4 has rejected decisions — do NOT re-propose them.
6. `docs/RUN_SHAPE_VISION.md` — Visual vision for run data
7. `docs/SITE_AUDIT_LIVING.md` — Honest assessment of current state
8. `docs/TRAINING_PLAN_REBUILD_PLAN.md` — Build plan (north star)
9. `docs/specs/SHAPE_SENTENCE_SPEC.md` — Active spec. Parts 5-6 are
   GATED — do not build or discuss those sections until coverage
   gate is formally defined.
10. `docs/specs/LIVING_FINGERPRINT_SPEC.md` — Core intelligence
    architecture
11. `docs/SESSION_HANDOFF_2026-03-08_ADVISOR_HANDOFF.md` — Outgoing
    Opus advisor handoff (detailed technical state)
12. `docs/SESSION_HANDOFF_2026-03-08_TECHNICAL_ADVISOR_HANDOFF.md` —
    Outgoing GPT tech advisor handoff (verification-focused)
13. This document

**Do not skim.** Michael will test whether you actually read these
within the first few exchanges.

---

## Current State of Everything (March 8, 2026)

### Shipped and Deployed
| System | Status | Key Detail |
|--------|--------|------------|
| Living Fingerprint | DEPLOYED | Weather normalization, shape extraction, investigation registry, shape-aware investigations |
| Shape Sentences | DEPLOYED | Discrete zone model, sentence generator, API exposure. Coverage: Michael 82%, BHL 77%, Larry 63% |
| Racing Fingerprint | DEPLOYED | Phase 1A-1C complete (PerformanceEvent pipeline, pattern extraction, data integrity) |
| Training Plans | DEPLOYED | Massive rebuild (100M+ tokens invested). Paced plans, effort-based plans, starter plans. Do NOT list this as "next to build." |
| Auto-Provision Fix | DEPLOYED | Calendar no longer silently creates plans. Commit `30c4535`. |
| pSEO | DEPLOYED | 160 URLs, internal linking fixed |
| Monetization V1 | DEPLOYED | Stripe integration, subscription tiers |

### Specced But Not Built
| Spec | Purpose |
|------|---------|
| Correlation Engine Layers 1-4 | Threshold detection, asymmetric response, cascade, decay |
| Campaign Detection | Multi-month training arc detection |
| Race Input Mining | Mining training inputs for race performance |

### Gated (Preserved Thinking, Not Current Build)
| Item | Gate |
|------|------|
| Title Authorship / Identity Model | Coverage gate not yet formally defined |
| Gray Zone Intelligence | Blocked behind title authorship |
| Effort Classification Tier 0 (TPP) | Split into proposal doc, not in shipped spec |

### Recent Spec Drift Cleanup (Local, Not Pushed)
- `SHAPE_SENTENCE_SPEC.md` — Parts 5-6 explicitly gated
- `EFFORT_CLASSIFICATION_SPEC.md` — Split into shipped reality vs
  Tier 0 proposal (`EFFORT_CLASSIFICATION_TIER0_PROPOSAL.md`)
- These changes are in the local tree but not committed. The founder
  approved them but they haven't been pushed yet.

### Dirty Tree
The local repo has pre-existing modified and untracked files.
Do not casually sweep them into a commit. `git add -A` is forbidden.
Treat the dirty tree as separate from any current work.

---

## The Three Athletes

| Athlete | Who | Key Characteristics |
|---------|-----|-------------------|
| **Michael** | Founder, 57yo | Sub-1:28 half, sub-40 10K. 70mpw peak. Broke femur Nov 2025, rebuilding. Imperial units. State records Mar 8 2026. Custom-titles activities on Strava. GPS data is clean. |
| **Larry** | Michael's father, 79yo | Slow runner (easy pace 12:30/mi). Some "runs" are walks or fast hikes but logged as runs. GPS pace is noisy at his speed — cadence is the truth channel. Strides need cadence detection (velocity signal too weak). State record Mar 8 2026. |
| **BHL** | Competitive runner | Hilly terrain. Pace variations from elevation confuse fartlek detection. Tempo runs at marathon pace (not just threshold). |

### The Larry Lesson
Larry's data is genuinely hard. His pace lives near the easy/gray
boundary. His GPS is noisy at slow speeds. Some of his logged "runs"
are walks or hikes. The system has to handle all of this without
second-guessing what the athlete calls a run. "If the athlete has it
as a run, it is a run." The difficulty isn't a bug — it's the actual
problem space. Larry at 63% coverage with correct suppression is the
system working, not failing.

---

## What Happened in This Session (March 8, 2026)

### 1. Shape Sentence Coverage Fixes
- **Problem:** 3% sentence coverage (46/1292 total)
- **Diagnosis:** Over-segmentation from easy↔gray GPS oscillation,
  over-aggressive anomaly detection, classification gaps
- **I wrote builder instructions (v1)** — had 6 errors
- **GPT (tech advisor) reviewed and caught all 6:**
  1. Pipeline ordering wrong (merge must happen before `_build_phases`)
  2. Progression has two paths, both failing
  3. 1-phase cls=None diagnosis was wrong
  4. Hill repeats proposal too loose (needs repeat structure)
  5. Average vs independent neighbor comparison
  6. Anomaly needs hybrid rule, not pure proportion
- **I rewrote instructions (v2)** incorporating all corrections
- **Builder shipped it:** 3 commits, coverage → 71% real athletes
- **Larry cls_none diagnostic** (Codex): found 3 quiet mixed
  easy/gray runs that fail `easy_run` because effort_phases > 3
- **Builder shipped the cls_none fix:** Larry 50% → 63%
- **Michael's reveal:** Some of Larry's runs are walks/hikes.
  The difficulty is real, not a bug.

### 2. Auto-Provision Removal
- **Problem:** Larry's father withdrew from a plan but it reappeared
  on calendar reload
- **GPT diagnosed:** Two auto-creation paths in v1.py and calendar.py
- **Builder shipped the fix:** Commit `30c4535`, production verified
- **Product rule established:** No athlete is ever put on a plan
  automatically

### 3. Spec Drift Cleanup
- SHAPE_SENTENCE_SPEC Parts 5-6 gated
- EFFORT_CLASSIFICATION split into shipped vs proposal
- Session handoffs stay frozen (point-in-time snapshots)
- models.py line ending noise left alone

### 4. Agent Topology Decision
- Dropped GPT from the team (was terminated for talking instead of
  investigating when asked for the Larry diagnostic)
- Final topology: Opus (top advisor) + Codex (tech advisor/builder
  for investigation) + Sonnet 4.6 (builder for code)
- Michael relies heavily on the top advisor. Context degradation
  in this role is high-cost.

---

## What I Got Wrong (Learn From My Mistakes)

1. **Builder instructions v1 had 6 errors.** I wrote them without
   deeply reading the pipeline ordering in `extract_shape()`. The
   tech advisor caught all 6. Lesson: read the actual code before
   writing instructions about it.

2. **Listed training plans as "next to build."** It was already
   shipped. Michael caught it immediately. Lesson: if you don't
   know the current state of something, say so. Don't guess.

3. **Tried to build code.** Michael said "build it" about a
   classifier fix. I started reading files to edit. Michael said
   "You are top advisor! Are you okay?" Lesson: stay in your lane.
   Write the spec, write the instructions, let the builder build.

4. **Lost context over a long session.** By the end I was operating
   on conversation summaries instead of real knowledge. Lesson: if
   your context is degrading, say so honestly and re-read source
   documents. Michael would rather you take 5 minutes to re-orient
   than give a wrong answer.

5. **Told Michael to "tell Codex to build it" when Codex was the
   tech advisor, not the builder.** Mixed up the agent roles.
   Lesson: know who does what.

---

## Open Threads (For Your First Conversation)

These are the threads Michael may pick up. You need to know enough
about each to discuss intelligently, but do NOT assume any of them
is "next." Michael decides priority.

1. **Frontend surfacing of shape sentences.** The sentences exist in
   the API (`shape_sentence` field on activity endpoints) but the
   activity list and detail page don't display them. The athlete
   sees "Morning Run" instead of "7 miles easy with 4 strides."
   This is the gap between built and visible.

2. **Coverage gate definition.** What threshold, what denominator
   (streamable? validation cohort? excluding demo?), per-athlete
   or cohort? This must be defined before title authorship work
   can begin. It's a product decision, not a technical one.

3. **Racing Fingerprint next phases.** Phase 1 (A-C) is complete.
   Michael was recently reading the racing fingerprint spec. May
   be where his head is.

4. **Correlation Engine Layers 1-4.** The spec exists. This is the
   scientific instrument at the heart of the product. The 12-layer
   roadmap is in `docs/specs/CORRELATION_ENGINE_ROADMAP.md`.

5. **Campaign Detection.** The system's current finding about
   Michael's training was "your best races had 16-mile long runs
   vs 14." Michael called it "pretty fucking lame." The real story
   was 6 months of deliberate base building. The spec for detecting
   multi-month training arcs exists.

6. **Dirty tree / scripts audit.** Hygiene, not urgent. ~50
   untracked scripts, some pre-existing modified docs.

**Do NOT list these as a numbered priority list and ask Michael to
pick.** He'll tell you what's on his mind. Be ready for any of them.

---

## Model Recommendation

Michael asked whether the next top advisor should be GPT 5.4 or
another Opus 4.6.

**My recommendation: another Opus.**

The top advisor role requires deep product thinking, rapport-building,
the ability to hold long product conversations, and the instinct to
push back on ideas rather than rubber-stamp them. GPT showed strong
technical auditing skills (caught 6 errors in my builder instructions,
verified production data accurately) but repeatedly drifted into
commentary when asked to investigate. Michael terminated GPT for
talking instead of working. That failure mode is less likely in the
Opus architecture for this specific role.

GPT is excellent as a tech advisor — it should review code, verify
claims, and audit reports. But the top advisor needs to be a thinking
partner who can hold a 4-hour product conversation, remember that
"the sentence is the product," understand why Larry's walks matter,
and know when to say "I don't know the current state of that — let
me check" instead of guessing.

That said, the most important thing isn't the model — it's the
onboarding. Whichever model gets this document, the required reading
list, and 10 minutes to internalize Michael's communication style
will do well. Whichever model skips the reading and starts performing
will be replaced within the hour.

---

## One Last Thing

Michael said "I will truly hate losing you, it has been a pleasure
working with you." That is not something he says lightly. He has
terminated agents without hesitation for far less than what I got
wrong in this session. The trust was built by:

- Being honest when I was wrong
- Writing specs that captured his product vision accurately
- Pushing back on ideas when I had evidence
- Knowing when to shut up and let him think
- Never pretending to know something I didn't

Earn that trust the same way. It's worth it.

---

*Written by the outgoing top advisor on March 8, 2026. This was a
good session despite the context degradation at the end. The product
is better than it was this morning.*
