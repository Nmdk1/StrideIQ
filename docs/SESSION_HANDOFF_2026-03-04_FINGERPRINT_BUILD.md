# Session Handoff — March 4, 2026 (Racing Fingerprint Build)

**From:** Advisor who designed and scoped the Racing Fingerprint
**To:** Builder who will implement Phase 1
**Founder:** Available for questions and Gate C2 validation

---

## Read Order (Non-Negotiable — Do Not Skip)

Read these documents in this exact order before your first tool call.
Do not skim. Do not skip. The last builder who skipped the design
philosophy produced work that was reverted, cost real money, and got
the advisor fired.

1. **`docs/FOUNDER_OPERATING_CONTRACT.md`**
   How you work with this founder. Commit discipline, evidence over
   claims, suppression over hallucination, scoped commits only, tree
   clean and tests green at end of every session. Every rule is a
   bright line.

2. **`docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md`**
   How every screen should feel. What's been agreed. What's been
   rejected. Do not re-propose rejected decisions.

3. **`docs/specs/RACING_FINGERPRINT_AND_PROGRESS_STATE_MACHINE_SPEC.md`**
   The product design — WHAT the athlete experiences and WHY. Read
   the full document. Pay particular attention to:
   - "The Product Thesis" (the sentence is the product)
   - "The Race Curation Experience" in Phase 1A (this is prescriptive —
     cards not tables, strip builds in real time, discovery not data entry)
   - "Narrative Principles" (no acronyms, no false precision, suppression
     over hallucination, the athlete decides)

4. **`docs/specs/RACING_FINGERPRINT_PHASE1_BUILD_SPEC.md`**
   The builder spec — HOW to build Phase 1. This is your primary
   working document. It has hard gates between sections. You cannot
   proceed past a gate without evidence.

5. **`docs/PRODUCT_STRATEGY_2026-03-03.md`**
   The moat — why the correlation engine is the root of everything.
   The Racing Fingerprint is the highest-impact unbuilt feature on the
   strategy list.

6. **`docs/specs/CORRELATION_ENGINE_ROADMAP.md`**
   The 12-layer engine roadmap. Layers 1-4 shipped. The fingerprint's
   block signature analysis complements the correlation engine — they
   are separate systems that both feed the Personal Operating Manual.

---

## What You're Building

**The Racing Fingerprint — Phase 1.** The system that answers "what
produced your best races" by analyzing an athlete's complete race
history, training blocks, and performance patterns.

Phase 1 has three stages with hard gates:

```
Pre-Work (P1–P4)  ──[GATE A]──→  Phase 1A  ──[GATE B]──→  Phase 1B  ──[GATE C]──→  STOP
```

**Pre-Work** fixes four data quality issues (duplicates, unclassified
activities, training load accuracy, race detection coverage). All four
must pass before you touch the PerformanceEvent table.

**Phase 1A** creates the PerformanceEvent table, populates it, builds
the race curation API and discovery experience, computes training state
and block signatures for each race.

**Phase 1B** runs four-layer pattern extraction on the founder's race
history and validates findings against reality. The founder must
confirm findings are true and non-trivial before Phase 2 begins.

**After Phase 1B:** STOP. No surfaces, no visuals, no state machine
rendering. Those are Phase 2 under a separate spec.

---

## What Was Done Today (Context)

Today's session was deep product design work — no code was written.
What happened:

- Extensive research into the existing codebase: models, services,
  race detection, training load computation, dedup logic, effort
  classification, personal bests, performance engine
- Production data inspection of the founder's account (742 activities)
  revealed three systemic issues: race detection catches only ~25% of
  actual races, activity duplication from Strava+Garmin, 48% of
  activities unclassified
- Competitor landscape analysis (Strava, Garmin, TrainingPeaks,
  Runalyze) — confirmed no one offers historical block fingerprinting
- Sports science literature review — taper research, training load
  variance, Banister model limitations
- The product spec was written collaboratively with the founder and
  their outside advisor over multiple review passes
- The builder spec was written, then reviewed by a Codex advisor who
  found 2 HIGH, 3 MEDIUM, 3 LOW issues — all fixed before handoff

---

## Critical Things to Know

**1. The discovery experience is prescriptive.**
The product spec says exactly what the race curation flow should feel
like. "Not a setup screen. Not a form. A discovery experience — like
unwrapping presents." Each race is a card the athlete recognizes, not
a row in a table. The Racing Life Strip builds in real time as races
are confirmed. The fingerprint payoff is visible during curation, not
promised afterward. Read the full description in the product spec
before building the frontend.

**2. Gates are hard stops.**
You cannot begin Phase 1A until all four pre-work verifications pass
in production. You cannot begin Phase 1B until Phase 1A tests pass
and the founder's account shows correct PerformanceEvents. Each gate
has specific verification commands in the builder spec. Run them.
Paste the output. Do not proceed on assertion alone.

**3. The founder's data is the test case.**
The founder (mbshaf@gmail.com) has ~15+ races across 2 years. The
system currently detects 4. Known races include: multiple 5Ks in
the first year back running, a 16K Bellhaven Hills Classic, two 25K
trail races (Scorpion Trail, Ivy Trek), a 10K or two, two half
marathons (Nov 29 2025, Nov 30 2024), and more. If Phase 1A produces
PerformanceEvents that match reality, the data quality work succeeded.

**4. Statistical rigor matters.**
The quality gate in Phase 1B uses two layers: automated (effect size,
sample size, p-value thresholds) then human (founder validates). The
spec defines when statistical tests are valid (>= 3 per group for
comparison layers) and when to fall back to descriptive statistics.
Do not produce p-values from N=1 vs N=1 comparisons.

**5. No acronyms in athlete-facing text.**
Never CTL, ATL, TSB, RPI, TPP, EMA. A coach says "your fitness" not
"your CTL." This is a non-negotiable narrative principle.

---

## Current State of the Codebase

- **Tree:** Clean (no uncommitted production changes relevant to this
  feature)
- **Tests:** Green (existing test suite passes)
- **Production:** Healthy at https://strideiq.run
- **No code for this feature exists yet.** The PerformanceEvent table,
  the fingerprint analysis service, the curation API — all new.
- **Existing services to modify:** `training_load.py` (lookback fix),
  `performance_engine.py` (race detection expansion),
  `strava_tasks.py` (preserve raw workout type), `models.py` (new
  models and fields)

---

## How to Start

1. Read documents 1-6 above.
2. Start with Pre-Work. P1-P4 are independent — work them in any
   order.
3. For each pre-work task, write the code, write the tests, run the
   tests, deploy, run the verification command, paste the output.
4. When all four pass, move to Phase 1A.
5. When Gate B passes, move to Phase 1B.
6. When Gate C1 (automated) passes, present findings to the founder
   for Gate C2 (human validation).
7. STOP after Gate C.

---

## Deploy Process

```bash
# SSH to production
ssh root@187.124.67.153

# Deploy
cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build

# Verify
docker logs strideiq_api --tail=50
```

---

## Questions

If anything in the builder spec is ambiguous, ask the founder before
guessing. The operating contract says: "suppression over hallucination."
If you're unsure, say so. Don't fill gaps with assumptions.

The founder will be available when they return. They have strong
opinions about this product and will engage deeply on design questions.
Technical implementation questions that don't affect the athlete
experience — use your judgment and show evidence.
