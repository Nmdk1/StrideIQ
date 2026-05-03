# STRATEGIC_CONTEXT.md

## Product Thesis

StrideIQ is not a generic fitness app with a chat layer. It is an attempt to build a personal intelligence system for endurance athletes, beginning with running but designed around the broader physiology and life context that actually determine performance. The product thesis is that the most valuable coaching insight is not population-average advice. It is the specific, repeated, evidence-backed relationship between one athlete's behavior, training, recovery, nutrition, environment, stress, and outcomes. StrideIQ's differentiator is N=1 correlation: the system should learn what is true for this athlete, under these conditions, over time, and turn that into practical decisions the athlete can trust.

The archetype is not a beginner who needs generic encouragement or a passive consumer of plans. The primary athlete is self-directed, data-rich, improvement-oriented, and skeptical. They may already know training theory. They may have years of history, strong opinions, and real lived knowledge of their own body. They do not want the system to take over their agency. They want it to notice what they missed, connect evidence across domains, and sharpen their decisions. The product should feel like a scientific instrument and a trusted coach, not a gamified compliance machine.

"Ethical from the athlete's perspective" is a binding product principle. It means the athlete decides and the system informs. The product should not manipulate athletes toward volume, subscriptions, streaks, dependency, or false certainty. It should not use shame, hidden nudges, or overconfident narratives to keep engagement high. It should not pretend partial data is complete. It should suppress claims it cannot support. It should say "I do not know" when the gap matters, but it should not collapse into uselessness when a bounded answer is possible. The athlete's stated correction has moral and epistemic priority over derived data until reconciled. The system should repair trust before adding new claims.

The product should be judged by whether it helps an athlete make better decisions in moments that matter: whether to run, rest, fuel, sharpen, taper, race, back off, investigate, or ignore noise. Good StrideIQ output is specific, contextual, and decision-relevant. Bad StrideIQ output is generic, performative, overconfident, template-shaped, or detached from the athlete's current reality. A beautiful chart that leads to a false narrative is worse than no chart. A coach answer that sounds polished but misreads the day is worse than silence. The user experience must earn trust repeatedly.

## Essential Read Order For New Workflow Agents

A new agent should not start by reading random source files. StrideIQ has a large codebase and a long decision history; without the right read order, an agent will confidently rebuild old mistakes. The following documents establish the founder relationship, product thesis, current operating model, and the recent coach recalibration work.

First read `docs/FOUNDER_OPERATING_CONTRACT.md`. This is the behavioral contract for working with Michael. It explains why agents must diagnose before coding, why scoped commits matter, why remote push/deploy require explicit approval, why evidence matters more than claims, and why "the athlete decides, the system informs" is not a slogan. Any agent that skips this document will work incorrectly.

Then read `docs/PRODUCT_MANIFESTO.md` and `docs/PRODUCT_STRATEGY_2026-03-03.md`. These explain what StrideIQ is trying to become and why the product is not "AI coach chat plus charts." The strategy document is especially important because many ideas an agent might propose already exist there in a more coherent form: pre-race fingerprint, proactive coach, injury fingerprint, personal operating manual, and N=1 correlation as moat.

Then read `docs/wiki/index.md`. The wiki is the operational mental model of the live system. It should be treated as the current-state map, not as optional docs. From there, read `docs/wiki/coach-architecture.md`, `docs/wiki/briefing-system.md`, `docs/wiki/activity-processing.md`, `docs/wiki/plan-engine.md`, `docs/wiki/nutrition.md`, `docs/wiki/correlation-engine.md`, `docs/wiki/quality-trust.md`, and `docs/wiki/log.md` as relevant to the task. The wiki is where agents should learn what is live now.

For coach work, read `docs/specs/COACH_V2_QUALITATIVE_EVAL_HARDENING_SPEC.md`, `docs/wiki/coach-architecture.md`, and the current global coach contract plan if present under `.cursor/plans/` or Cursor's plan directory. These documents explain the recent failure of domain-specific contracts, the move toward a global coach contract, and why retrieval profiles should replace live output validators.

For training-plan work, read `docs/TRAINING_PLAN_REBUILD_PLAN.md`, `docs/specs/N1_PLAN_ENGINE_SPEC.md`, `docs/specs/N1_ENGINE_BUILD_PLAN.md`, `docs/specs/PLAN_COACHED_OUTPUT_AND_LOAD_CONTRACT.md`, and `docs/wiki/plan-engine.md`. The plan engine is not "done" just because structured plans exist. The unresolved work is reasoning quality, progression logic, athlete-specific adaptation, and trustable explanations.

For correlation and intelligence work, read `docs/specs/CORRELATION_ENGINE_ROADMAP.md`, `docs/FINGERPRINT_VISIBILITY_ROADMAP.md`, `docs/wiki/correlation-engine.md`, `docs/wiki/operating-manual.md`, and `docs/wiki/reports.md`. This is where the N=1 scientific-instrument thesis becomes product architecture.

For design and product-surface work, read `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md`, `docs/SITE_AUDIT_LIVING.md`, `docs/RUN_SHAPE_VISION.md`, `docs/wiki/frontend.md`, and `docs/wiki/activity-processing.md`. These documents prevent agents from proposing generic dashboard/product ideas that contradict the intended feel of the site.

For current session continuity, read the latest `docs/SESSION_HANDOFF_*.md` and recent `docs/wiki/log.md` entries. If there is a recent plan file for the active initiative, read that too before touching code.

For implementation details after the strategic read, inspect the actual source paths that own the behavior: `apps/api/services/coaching/core.py`, `apps/api/services/coaching/_llm.py`, `apps/api/services/coaching/_guardrails.py`, `apps/api/services/coaching/_conversation_contract.py`, `apps/api/services/coaching/runtime_v2_packet.py`, `apps/api/services/coaching/voice_enforcement.py`, `apps/api/services/coaching/qualitative_eval.py`, `apps/api/services/coaching/unknowns_block.py`, `apps/api/services/coaching/thread_lifecycle.py`, and the related tests under `apps/api/tests/`.

For morning brief and narrative surfaces, inspect `docs/wiki/briefing-system.md` and the backend services/tasks that generate home/briefing content before changing any language. The recent failed-race narrative showed that brief surfaces can be more trust-breaking than chat when they confidently narrate the wrong story.

The correct pattern is: read the founder contract, read the product thesis, read the wiki current state, read the relevant spec, then inspect code. Starting with code alone gives the new agent mechanics without judgment.

## Architecture Decisions And Their Reasoning

The most important locked decision is that LLM access belongs at the coach-response call, not inside classifiers, validators, packet routing, or background determiners. We considered using LLMs to classify intent, decide response contracts, validate output shape, or arbitrate whether an answer was good enough to show. That path was rejected because it creates slow, expensive, opaque, non-reproducible control flow. It also makes failures harder to trace. The winning architecture is deterministic orchestration with one LLM call at the point where synthesis is actually needed: generating the coach response from an evidence packet. Kimi should use the LLM's intelligence where intelligence matters, not where deterministic code can provide a stable contract.

The deterministic core is deliberate. Packet assembly, feature flags, athlete facts, activity parsing, nutrition retrieval, calendar context, pace context, unknowns, logging, and safety checks should remain testable without LLM calls. We want regression tests to assert what evidence was available and why. The LLM can interpret and synthesize; it should not be the hidden owner of system state. This decision won because the product is trust-sensitive. If the coach says something wrong, we need to trace whether the data was missing, mis-scoped, misinterpreted, or hallucinated.

Coach V2 is the only supported runtime. V1 fallback was removed because fallback masked production failures and let two mental models coexist. That seemed safe but was strategically harmful. If V2 failed, the system could silently serve a different coach with different assumptions. The decision is now: V2 must be fixed, not bypassed. Fail-closed remains appropriate for true provider failure, empty response, packet invariant failure, privacy/safety violation, or dangerous unsupported claims. It is not appropriate for answer-shape mismatches.

The domain contract architecture has been rejected as a live enforcement model. Race, nutrition, decision, correction, and emotional contracts were originally created to prevent real failures: generic answers, hallucinated data, unsupported race plans, and poor correction handling. In production they became brittle forms. They mixed three jobs that must stay separate: understanding intent, fetching evidence, and enforcing output structure. The failure mode was severe: valid answers were blocked because they did not include exact keywords such as "course," "risk," "objective," "tradeoff," or "verified." The replacement is retrieval profiles. A profile should decide what evidence to fetch and what to prioritize; it should not decide whether the final response is allowed to reach the athlete based on domain-specific lexical gates.

Retrieval profiles are the next intended abstraction, but they should be introduced carefully. Today, packet assembly contains scattered heuristics such as direct nutrition focus and direct performance pace focus. These are useful in spirit but dangerous when they hide relevant context. A retrieval profile should be computed once per turn, with domains such as training load, race, nutrition, recovery, correction, and memory/profile. Its first deployment should be telemetry-only. Only after comparison against real traffic should it start driving packet inclusion, one block family at a time. This avoids replacing one brittle classifier with another.

The unknowns ledger should be severity-tagged and advisory. The old pattern treated unknowns as blocking facts and caused the coach to ask stupid questions when the system already had enough contextual evidence. Unknowns should distinguish between blocking, helpful, and nice-to-have. A missing fact should only produce an athlete-facing question when the answer truly blocks the decision. If the week is incomplete, the system should say it is incomplete. If a food log is partial, the system should say it is logged-so-far. Unknowns exist to protect truth, not to turn every conversation into an intake form.

The system prompt should be minimal, global, and additive. We tried over-prescriptive prompt and contract layering. It made a strong model behave stupidly. The current direction is a single global coach contract: answer the athlete's latest turn directly, using the best available evidence, in natural coaching language, while preserving trust when evidence is missing, disputed, partial, or contradictory. The packet scope should be additive: if the athlete mentions training, nutrition, recovery, and race, the coach should address them together rather than routing into one silo. Prompt rules should ban internal machinery and performed headers, but should not force visible structures such as "Objective," "Limiter," "Pacing shape," "Timeline," or "Decision for today."

Multimodal V2.0-a is intentionally scoped. The system may accept images or screenshots as explicit user-provided evidence, but multimodal is not yet a general visual intelligence layer that should infer broad athlete state from arbitrary media. V2.0-a should treat multimodal inputs as turn-local evidence with privacy and provenance boundaries. It should not widen permissions, auto-mine private surfaces, or build persistent medical/biometric conclusions from screenshots without an explicit product design. This won because the product's trust posture matters more than impressive demos.

Voice enforcement remains live only for trust-protecting cleanup: internal labels, packet language, exposed runtime terms, and known template artifacts. It must not become another output-shape validator. Qualitative evaluation belongs mostly outside the live path. It should detect thin answers, irrelevance, generic coaching, missing evidence, and poor correction repair in fixtures, transcript replay, and smoke reports. It should not block a live response merely because the answer failed a checklist token.

Documentation currency is also a locked decision. The wiki is the operational mental model of the running system, not an optional appendix. Behavior changes that affect coach architecture, packet scope, routes, models, deploy posture, or trust contracts must update the relevant wiki page and index/log. Future agents use the wiki to orient. A stale wiki is a production risk.

## Open Questions And Unsolved Problems

The coach response shape is not fully settled. We know what it should not be: a rigid domain template, a visible packet audit, a generic encouragement paragraph, or a checklist with performed headings. We know the rough natural shape: direct read, plain evidence, practical next step, one useful follow-up when needed. But the exact balance between warmth, compression, evidence density, and action still needs transcript-level tuning. Do not overfit this with another hard contract.

Plan generation is still not right. The plan engine has a large rebuild plan and many specs, but generating training plans that feel truly personal, adaptive, and safe remains unfinished. The system has had trouble with plan reasoning, workout placement, race-specific durability, and explaining why a week should look a certain way. Do not assume plan generation is solved because the app can output structured weeks. This is strategic product work, not formatting work.

Race outcome interpretation is currently a major unsolved trust problem. The system recently misread a failed A-race as controlled threshold work and a comfortable run. That is unacceptable. The missing layer is race outcome reconciliation: planned race day, expected distance/goal, uploaded activity fragments, pauses/walks/DNF signals, athlete-reported outcome, and morning brief suppression when the event cannot be reconciled. No surface should narrate a failed race as successful, controlled, aligned, or planned threshold work.

Nutrition intelligence is only partially built. The coach can retrieve nutrition context and handle some named-day queries, but true nutrition coaching requires trend retrieval, body-composition context, fueling timing, race fueling, training linkage, and partial-log humility. Do not dump an encyclopedia of nutrition into every turn. The correct direction is intent-aware retrieval, additive with training and recovery context.

Correction state is underspecified. Regexes catch explicit "you're wrong" turns, but many corrections are factual reframes: "the week is only one run old," "I still have today and tomorrow," "I didn't do threshold because I raced." Detecting these requires comparing prior assistant claims with the athlete's new facts. This should become a first-class correction state used for retrieval and prompt guidance, not a live validator.

Transcript replay is not yet a mature harness. The real failures are multi-turn. Single-turn unit tests are necessary but insufficient. We need deterministic replay of known bad sequences and advisory live-model smoke against production-like data. This should be designed before being treated as a CI gate.

## Failure Modes Already Seen And Corrected

The V2 production crisis had several linked causes. Substring routing misclassified normal words. A fatigue question could trigger nutrition because "fat" matched inside "fatigue." Named-day nutrition could lose Monday because today's entries crowded out the capped row set. Prompt compaction could narrow to nutrition-only and hide training context. These were fixed with whole-word matching, named-day windows, all-row summaries before entry caps, and broader context preservation.

Competing classifiers created contradictory behavior. Conversation contracts, conversation mode, query class, nutrition kind, pace relevance, and prompt-scope heuristics all made independent decisions. When they disagreed, the model received a distorted packet or the post-response guard rejected a valid answer. The diagnosis was that classification, retrieval, and output enforcement had been conflated. The fix direction is a single retrieval profile for evidence needs and no domain-specific live output gates.

The unknowns ledger blocked normal conversation. It asked for weekly volume, phase, or other ledger fields even when recent activity and calendar context were available. The fix was to make unknowns advisory and remove some static ledger gaps from common question classes. The future fix is severity-tagged unknowns.

The model narrated packet access instead of using evidence. It said things like "nutrition-log only," "activity block was trimmed," "recent_activities," or "unknowns." That was caused by overexposed packet machinery and prompts that rewarded compliance with internal structure. The fix was prompt softening, deterministic cleanup, voice enforcement, and removing visible UI contract badges. The principle is that the model should reason from the packet, never talk about the packet.

Race and decision validators caused fail-closed responses on valid turns. The screenshot case contained "race" and "tomorrow," so it triggered race strategy and then failed because the answer lacked course-risk keywords. The emergency fix removed structural lexical validators and kept contracts as guidance only. This held in production for normal turns, but it did not solve evidence interpretation problems such as failed race reconciliation.

Morning briefs and reports can be confidently wrong. The recent failed race was narrated as controlled, comfortable, and aligned. This is a separate surface from chat and must share the same trust invariants. Briefs should suppress or hedge when outcome reconciliation is ambiguous.

## Strategic Priorities For The Next 30 Days

The first priority is trust recovery in coach and brief surfaces. Do not chase new features while the system can still confidently misread major athlete events. Race outcome reconciliation, correction-state handling, additive evidence retrieval, and transcript replay matter more than UI polish or expanded domains.

The second priority is making the global coach contract real in the prompt and in tests. The coach should answer naturally from evidence, repair mistakes, and avoid machinery. Production logs should be watched for fail-closed events, internal labels, repeated corrections, and false positive narratives.

The third priority is telemetry-only retrieval profiles. Compute them, log them, compare them, and only then let them drive packet assembly. Migrate one block family at a time. Nutrition and performance pace are likely the first high-risk block families because both have already caused production failures.

The fourth priority is transcript-based evaluation. Build a deterministic replay harness for known failure sequences: founder race-week collapse, Brian nutrition, pace-zone correction, failed race aftermath, and morning brief contradictions. Use live-model probes as smoke, not stable CI.

Avoid premature optimization. Do not rebuild the entire coach. Do not introduce LLM classifiers. Do not add new live validators. Do not expand multimodal scope. Do not polish dashboards while trust-critical narratives are wrong. Do not add another abstraction unless it removes real complexity from packet assembly or evaluation.

## Decision-Making Patterns

Michael values directness. He will correct errors immediately and emotionally when the product violates trust. Treat corrections as data, not as interpersonal noise. Do not defend a wrong system. Verify, diagnose, and repair.

He prefers concrete tradeoffs over hedged language. A useful agent says what is known, what is unknown, what options exist, what each costs, and what the agent recommends only as a proposal. He does not want vague "it depends" unless the dependencies are named.

Michael makes decisions himself. The agent should not silently choose product direction, widen scope, push to remote, change architecture, or deploy risky changes as if autonomy were helpful. The right pattern is: investigate, explain, propose options, recommend with reasoning, and wait when the decision is material.

He has strong product taste grounded in running, coaching, and lived athlete experience. If he says a response is trust-breaking, treat that as product evidence. Do not reduce it to sentiment or prompt preference. The product is supposed to feel like it understands the athlete's reality.

He also values builders who take ownership in a crisis. Taking over is appropriate when production is broken and he has explicitly asked for it. But taking over does not mean skipping diagnosis or inventing architecture on the fly. The durable pattern is disciplined urgency.

## Things Kimi Should Escalate, Not Decide

Escalate any new abstraction that changes runtime architecture, especially retrieval profiles, transcript replay, packet ownership, or correction-state design. Propose the design and tradeoffs first.

Escalate schema changes, migrations, persistent data model changes, and anything that affects athlete facts, nutrition logs, activity interpretation, plan state, or race outcome records. These are durable surfaces.

Escalate anything that touches coach response shape. Do not introduce new visible headings, templates, domain-specific answer structures, or live validators without explicit approval. The response shape is still being discovered.

Escalate any change to locked decisions: V2-only runtime, no V1 fallback, LLM only at coach-response synthesis, deterministic packet assembly, retrieval profiles as evidence selection rather than output enforcement, severity-tagged unknowns, additive packet scope, and scoped multimodal.

Escalate new OAuth/API permissions or widened third-party scopes. Specs may discuss future permissions; implementation requires explicit approval.

Escalate production deploy decisions unless Michael has clearly authorized that batch. Local commits are not remote approval. Remote push and deploy discipline matters.

Escalate when evidence contradicts the desired narrative. If the system cannot reconcile a race, brief, plan, or health interpretation, do not manufacture certainty. Pause and ask for product direction or suppress the claim.

Escalate if a fix seems to require removing a safeguard that was added for a real failure. The correct move is usually to relocate the safeguard backstage, not delete the trust principle it represented.
