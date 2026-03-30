# StrideIQ Limiter Engine — Architectural Brief

**Date:** 2026-03-29
**Author:** Founder (Michael Shaffer)
**Status:** Design directive — governs implementation of limiter lifecycle system
**Supersedes:** Static limiter model in original `LIMITER_TAXONOMY.md` draft

---

## The Core Insight

The limiter taxonomy was drafted assuming limiters are stable physiological traits — things the correlation engine identifies once and the plan engine addresses continuously. That model is wrong.

Limiters are temporary. An athlete's job is to identify the current system constraining their performance, eliminate it, and find the next one. StrideIQ's job is to see what the athlete cannot see about themselves — which system is currently the frontier — and help them attack it in the right sequence.

The founder's own training history is the proof of concept. His correlation data shows `long_run_ratio → threshold_pace` at r=0.75. A static model reads that as "this athlete is volume-constrained — prescribe long run emphasis." That prescription is wrong. What actually happened: long runs were his weakness. He ran 40 of them. The weakness closed. Threshold improved as a result. Then threshold became the weakness. He fixed that. The correlation captured the history of solved problems, not a structural trait.

**A strong historical correlation is evidence of a solved problem, not an active limiter.**

This is the entire premise of StrideIQ N=1: identify the systems that need improvement, fix them, identify the next ones. The question the engine must answer is not "what has driven this athlete's performance historically" — it is "what physiological adaptation does this athlete most need right now to reach their goal."

---

## What the Correlation Engine Actually Produces

Correlation data contains four fundamentally different signals. The engine currently treats them all the same. They are not the same.

**Signal Type 1: Strong historical, fading recently**
The correlation was real. The athlete fixed it. It is no longer the frontier.
Example: Founder's long_run_ratio → threshold correlation. Strong in the build log. Not the current limiter.
Action: Record as closed. Do not prescribe.

**Signal Type 2: Weak historical, strengthening in last 90 days**
A new limiter is emerging. The athlete's training is shifting toward it or away from it and performance is responding.
Action: Flag as emerging frontier. Surface to coach layer for confirmation. Do not prescribe yet — confirm first.

**Signal Type 3: Strong, stable across time, not shifting**
This is a structural physiological trait, not a solvable limiter.
Example: Brian's recovery half-life at 51.3h. That is his physiology. The plan accommodates it — wider spacing, conservative dosing. It does not target it as a training problem to solve.
Action: Classify as structural trait. Modify plan delivery parameters. Do not treat as a limiter to eliminate.

**Signal Type 4: Correlation shifts after a training intervention**
The athlete attacked a limiter. The correlation weakened. The intervention worked.
Action: Mark limiter as closed. Begin scanning for the next emerging signal.

---

## The Limiter Lifecycle

Replace static limiter assignment with a lifecycle state for each identified limiter. Every limiter finding in the fingerprint carries one of five states:

**`emerging`**
Correlation strengthening in recent data (L90 weighted). Not yet dominant in full history. Has not been the subject of a deliberate training intervention yet. This is a candidate for the current frontier — surface to coach layer for athlete confirmation before acting on it.

**`active`**
The current frontier. Strongest recent signal. Confirmed as the target by recent training pattern or explicit coach/athlete confirmation. This is what the plan engine reads and addresses.

**`resolving`**
A training intervention is underway. The correlation is weakening. The limiter is closing. The plan continues addressing it but at reduced emphasis. The engine begins scanning for what comes next.

**`closed`**
Historical signal. The limiter was real. The athlete solved it. It no longer constrains performance. Preserved in fingerprint history as a record of the athlete's development arc. Not used for plan prescription.

**`structural`**
Not a limiter to solve — a physiological trait to accommodate. Recovery half-life, injury history, body composition constraints. The plan modifies delivery parameters to work with it. The coach layer does not frame it as a problem to fix.

---

## How Each System Reads the Lifecycle

**Correlation engine:**
Computes correlations as it does today. Adds temporal weighting — L90 data weighted 3x relative to full history. Classifies each correlation pattern against the four signal types above. Assigns initial lifecycle state based on pattern type and recency.

**Fingerprint bridge:**
Reads lifecycle states, not raw correlations. Passes `active` limiters to the plan engine. Passes `emerging` limiters to the coach layer as candidate frontiers. Ignores `closed` limiters for prescription purposes. Passes `structural` traits as delivery modifiers only.

**Plan engine:**
Reads `active` limiters only. Uses the limiter to adjust session type weighting and volume balance within the distance-specific floor (distance rules still set the minimum session types — limiter adjusts the ratio). Does not read `emerging`, `resolving`, `closed`, or `structural` for prescription decisions.

**Coach layer:**
Surfaces `emerging` limiters as questions or observations to the athlete. "Your data is showing X pattern emerging — is this something you're feeling in training?" Athlete confirms or corrects. Confirmation moves the limiter from `emerging` to `active`. Correction keeps it as `emerging` and prevents the plan engine from acting on it. This is the human-in-the-loop gate before fingerprint data drives a real plan change.

---

## The Temporal Weighting Requirement

The correlation engine needs L90 weighting before limiter lifecycle classification is meaningful. Without it, a strong 12-month-old correlation will always dominate a weak 30-day-old emerging signal — and the engine will perpetually prescribe for solved problems.

Proposed weighting:
- L30 data: 4x weight
- L31-90 data: 2x weight
- L91-180 data: 1x weight
- Beyond 180 days: 0.5x weight

This means a correlation that was r=0.75 twelve months ago but is r=0.20 in the last 90 days will not drive a limiter assignment. A correlation that was r=0.15 historically but is r=0.45 in the last 90 days will flag as emerging.

The exact weights are adjustable. The principle is not — recency must dominate for the lifecycle model to work.

---

## Implementation Sequence

Do not rebuild everything at once. The static taxonomy has real value for data-sparse athletes and as a starting state before lifecycle classification has enough data to operate. Build in layers:

**Phase 1 — Already built:**
Static limiter taxonomy, fingerprint bridge, recovery half-life → plan parameters, confidence gates. This works for Brian (structural L-REC is correctly identified and stable). It is wrong for Michael (historical L-VOL should be closed). Ship it, it is better than no fingerprint at all.

**Phase 2 — Temporal weighting:**
Add L90 weighting to correlation engine. This is a single parameter change in how correlation_engine.py aggregates observations. Test against all three athletes — Michael's L-VOL signal should weaken, Brian's L-REC should remain strong (it is recent and stable), Larry's L-CON should remain suggested (small sample).

**Phase 3 — Lifecycle states:**
Add `lifecycle_state` field to `CorrelationFinding`. Write the classifier that assigns states based on temporal pattern and signal type. Add intervention tracking — when the plan engine prescribes against a limiter, record the intervention start date so the engine can watch for the correlation to weaken.

**Phase 4 — Coach layer integration:**
Wire `emerging` limiters into the coach layer as surfaceable observations. Build the confirmation flow — athlete confirms or corrects, state updates accordingly. This is where the N=1 engine becomes genuinely conversational rather than purely algorithmic.

**Phase 5 — Limiter transition detection:**
When a limiter moves from `active` to `resolving` to `closed`, trigger a scan for the next `emerging` signal. Surface it to the coach layer. The engine begins watching for the next frontier before the athlete consciously identifies it. This is the capability that makes StrideIQ genuinely different from every other platform — it sees the development arc as it is happening.

---

## What This Means for the Three Current Athletes

**Michael (founder):**
Current L-VOL assignment is historically accurate and currently wrong. With temporal weighting, the long_run_ratio → threshold correlation will correctly weaken (it is 8+ months old and the training pattern has shifted to threshold and interval work). The emerging signal is threshold and ceiling work — consistent with his current crash block training for the 10K. His active limiter right now is race-specific sharpening, not volume. The plan engine should not be adding long run emphasis to his current build. It should be supporting exactly what he is already doing — intervals, threshold, quality long runs, supercompensation taper.

**Larry (79, state record holder):**
L-CON signal (days_since_rest → PBs) remains at suggested confidence (n=11, selection bias caveat). With temporal weighting this signal may strengthen or clarify as more data accumulates. The cadence finding is correctly suppressed by the elevation confounder. His structural trait is his 46.4h recovery half-life — the plan accommodates it with every 3rd week cutbacks and 48h quality spacing. No active limiter is currently confirmed. He gets distance-default prescription with structural delivery modifications.

**Brian (data-sparse):**
L-REC is correctly identified as structural — his TSB sensitivity and daily session stress patterns are stable, not historical artifacts. Multiple confirming signals (CS-8, CS-9, TSB positive). This is genuinely his physiology. The temporal weighting will not change his classification because the signal is recent and consistent. His plan correctly uses 72h spacing, 2 quality sessions max, cutback every 3rd week. As he accumulates more data, the engine will begin to see whether any other limiters are emerging or whether L-REC is the primary constraint on his development.

---

## The Question the Engine Must Always Be Answering

Not: what has driven this athlete's performance historically.

Not: what does the population of athletes like this athlete typically need.

This: **what physiological adaptation does this athlete most need right now to reach their goal?**

The correlation engine provides evidence. The lifecycle classifier interprets it temporally. The coach layer confirms it with the athlete. The plan engine addresses it. When it closes, the engine finds the next one.

That is the N=1 engine. That is what makes StrideIQ different.

---

## Files to Touch in Phase 2 and 3

```
services/correlation_engine.py                 — add L90 temporal weighting
models.py (CorrelationFinding)                 — add lifecycle_state field + migration
services/plan_framework/fingerprint_bridge.py  — read lifecycle states, not raw correlations
services/plan_framework/limiter_classifier.py  — new: temporal pattern → lifecycle state
docs/specs/LIMITER_TAXONOMY.md                 — update with lifecycle layer (after annotation)
```

Do not touch the plan engine or coach layer until Phase 3 lifecycle states are validated against the three athlete profiles.

---

*This brief reflects a conversation between the founder and the builder on 2026-03-29. The limiter lifecycle model supersedes the static limiter taxonomy at the architectural level. The taxonomy annotation continues — the correlation signatures and session type mappings remain valid. What changes is how they are applied: temporally, with lifecycle states, not as static profile assignments.*
