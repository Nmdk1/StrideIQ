# Session Handoff — March 3, 2026 (Advisor)

**Agent role:** Advisor
**Session focus:** Correlation engine as the product's root dependency,
effort classification spec, correlation engine roadmap, product strategy

---

## What this session established

This session produced the founder's clearest articulation of what StrideIQ
is and what the correlation engine means to it. Every future agent must
understand this:

**The correlation engine is not a feature. It is the product.**

Every surface — the Progress page, the coach, the daily intelligence, the
future Pre-Race Fingerprint, the Proactive Coach, the Personal Operating
Manual — is downstream of the correlation engine producing findings that
are true, specific, and actionable about a single human. If the engine
produces bad findings or no findings, nothing else matters. If it produces
good findings, everything else flows from it.

This insight took many sessions and many agents to reach. It is now
encoded in permanent documents (see below). Do not lose it.

---

## Documents created this session

| Document | Purpose |
|----------|---------|
| `docs/specs/EFFORT_CLASSIFICATION_SPEC.md` | Architectural spec to replace all `athlete.max_hr` gates with N=1 percentile-based effort classification. **Approved by founder.** |
| `docs/BUILDER_NOTE_2026-03-03_EFFORT_CLASSIFICATION.md` | Builder note for effort classification. Ready for assignment. |
| `docs/specs/CORRELATION_ENGINE_ROADMAP.md` | 12-layer roadmap for the correlation engine, from threshold detection to cohort intelligence. Founder vision, advisor-annotated with feasibility and ordering. |
| `docs/PRODUCT_STRATEGY_2026-03-03.md` | Canonical product strategy. The compounding intelligence moat. Priority-ranked product concepts. Why the correlation engine is the root of everything. **Added to mandatory read order.** |

## Documents updated this session

| Document | Change |
|----------|--------|
| `.cursor/rules/founder-operating-contract.mdc` | Read order updated: added Product Strategy (#3) and Correlation Engine Roadmap (#4). Updated site audit reference to `SITE_AUDIT_LIVING.md`. |
| `docs/FOUNDER_OPERATING_CONTRACT.md` | Read order updated: added Product Strategy (#3) and Correlation Engine Roadmap (#4). |

---

## What shipped this session

Nothing shipped to production. This was a strategy and specification
session.

---

## What's in flight

1. **Effort Classification** — builder note written, ready for assignment.
   This is the critical path. It unblocks 6 of 9 correlation sweep metrics,
   Recovery Fingerprint, and accurate effort classification across 7
   services and 13 code paths.

2. **Progress Page Phase 2** — builder was working on this before this
   session started. May be complete or in progress. Check latest builder
   handoff.

---

## What's next (this week, per founder)

The founder said: "we will build it all this week." The sequence:

1. **Effort Classification** ships (unlocks full correlation sweep)
2. **Correlation Engine Layer 1:** Threshold Detection
3. **Correlation Engine Layer 2:** Asymmetric Response Detection
4. **Correlation Engine Layer 3:** Cascade Detection (mediation analysis —
   half-built, `compute_partial_correlation()` already exists)
5. **Correlation Engine Layer 4:** Lagged Decay Curves

Layers 1–4 are buildable with existing data and existing infrastructure.
They transform the Progress page from "here are your correlations" to
"here is how your body actually works."

---

## Key decisions made

1. **`athlete.max_hr` is banned as a gate.** It's a population metric that
   silently cripples the system. Replaced by three-tier N=1 classification:
   HR percentile (primary), HRR with earned observed peak (secondary),
   workout type + RPE (tertiary). No `220 - age`. No hardcoded guesses.

2. **RPE disagreement is a signal, not a bug.** When HR-derived
   classification and RPE disagree by more than one tier, log it. Over time
   those disagreements become correlation inputs themselves.

3. **Product strategy is now in the mandatory read order.** Every future
   agent reads `PRODUCT_STRATEGY_2026-03-03.md` before any work begins.
   This was the missing document that caused agents to build features
   without understanding why the correlation engine is the root dependency.

4. **Correlation engine roadmap has 12 layers.** Ordered by data
   requirements, implementation complexity, and product impact. Layers 1–4
   are this week's target.

---

## The insight that must survive

The founder's words: "without the correlation engine matching my vision,
nothing else is meaningful. Once it does, everything flows from it."

The correlation engine is a scientific instrument pointed at a single
human. The product is exactly as good as this instrument and not one bit
better. Every future session, every future feature decision, every future
prioritization call should be measured against this.
