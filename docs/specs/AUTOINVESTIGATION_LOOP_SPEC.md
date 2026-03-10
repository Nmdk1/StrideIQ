# AutoInvestigation Loop — Nightly Self-Improving Engine

**Date:** March 10, 2026
**Status:** Approved concept — build after Experience Guardrail ships
**Inspired by:** Karpathy's autoresearch pattern (baseline → modify → measure → keep/discard)
**Horizon:** 3 (Instrument Sharpens) per BUILD_ROADMAP_2026-03-09.md

---

## Core Insight

StrideIQ already has everything autoresearch needs except the agent and the nightly loop. The investigation registry is `train.py`. The athlete data corpus is the training set. Finding quality is `val_bpb`. The engine that runs investigations is the training loop.

The system gets smarter about every athlete every night without anyone touching it. That's the moat compounding while you sleep.

---

## The Parallel

```
Karpathy's loop:
  baseline train.py → agent modifies → 5-min training run → val_bpb metric → keep or discard → repeat

StrideIQ's loop:
  baseline investigation params → agent modifies → run against athlete corpus → FQS metric → keep or discard → repeat
```

---

## The Objective Metric: Finding Quality Score (FQS)

The hardest part. Without an unambiguous metric, the loop optimizes for the wrong thing.

FQS captures four dimensions:

### Confidence (weight: 0.35)

How many times confirmed vs attempted. A finding seen 47 times in 9 months is stronger than one seen 3 times.

```
confidence = confirmed_count / (confirmed_count + attempted_count)
```

### Specificity (weight: 0.30)

Does the finding say something a non-specific system couldn't say?

```
specificity = 1 - (athlete_threshold_range / population_default_range)
```

If the population sleep cliff is "somewhere between 5.5 and 7.5 hours" (range = 2.0) and the athlete's personal cliff is "6.1 to 6.4 hours" (range = 0.3), specificity = `1 - (0.3 / 2.0) = 0.85`.

Without a concrete formula like this, specificity is subjective and the whole FQS degrades.

### Actionability (weight: 0.20)

Does the finding point at something the athlete controls? Weather is not actionable. Sleep is. Volume is. The investigation registry already knows which inputs are controllable vs environmental — this is a stored property, not computed at runtime.

### Stability (weight: 0.15)

Does the finding hold over time, or does it flip? Track supersession events as negative signal.

```
stability = 1 - (reversal_count / total_confirmation_attempts)
```

A finding confirmed 12 times and reversed 3 times: `1 - (3/15) = 0.80`.
A finding confirmed 15 times without reversal: `1 - (0/15) = 1.0`.

### Combined

```
FQS = (confidence × 0.35) + (specificity × 0.30) + (actionability × 0.20) + (stability × 0.15)
```

### Cascade Bonus

Cascade findings (connected pathways, e.g., sleep → HRV → efficiency at 2-day lag) are dramatically more valuable than isolated correlations. They get a multiplier:

```
cascade_bonus = 0.15 × (chain_length - 1)
final_FQS = base_FQS + cascade_bonus
```

A 2-link chain gets +0.15. A 3-link chain gets +0.30.

### Validation Requirement

Before the agent optimizes for FQS, run it against current findings and manually verify: do the high-FQS findings feel more valuable than the low-FQS ones? If not, adjust weights. One afternoon of calibration. This is a prerequisite, not a nice-to-have.

---

## What the Agent Modifies

Each investigation in the registry has tunable elements:

| Parameter | Example | Search Type |
|-----------|---------|-------------|
| Minimum confirmation threshold | Currently hardcoded per investigation; agent tunes per-athlete based on data density | Integer in range |
| Lookback window | Sleep-efficiency looks back 48h — is 36 better? 72? | Integer in range |
| Threshold sensitivity | Inflection detector sensitivity for cliff detection — too sensitive = false findings, too loose = missed findings | Float in range |
| Signal weighting | If HRV is noisy but sleep is clean, downweight HRV, upweight sleep | Float weights |
| Investigation combinations | Cascade detection — propose new investigation pairs | Combinatorial (LLM v2 only) |

---

## Agent Architecture

### v1: Structured Optimizer (not LLM)

The search space is structured and bounded. Lookback windows are integers in a range, thresholds are floats, confirmation counts are integers. This is a Bayesian optimization problem, not a creative generation problem.

An LLM agent would cost ~8,400 calls/athlete/year and be harder to debug. A structured optimizer is cheaper, more reproducible, and produces mechanically explainable experiment logs.

### v2: LLM Agent (for novel investigation combinations only)

Save the LLM for proposing *novel investigation combinations* — that's where generative reasoning is genuinely needed. Parameter tuning within a known investigation is a search problem, not a creativity problem.

---

## The Modification Strategy

The agent receives:
```
Current investigation registry state for athlete X:
- 15 investigations, current FQS per investigation
- Last 30 days of finding confirmation/rejection events
- Athlete data coverage (which signals are dense, which are sparse)
- Previous modification attempts and their outcomes
```

It proposes one modification per cycle:
```
"Increase lookback window for sleep-efficiency investigation from 48h to 60h.
Rationale: athlete has irregular sleep patterns; 48h may miss the delayed response.
Expected outcome: confirmation rate improves without stability drop.
Rollback if: FQS drops more than 0.05 or stability drops more than 0.10."
```

The modification is applied to a **shadow copy** — never the production registry. The investigation runs against the full athlete corpus. FQS is computed before and after. Improved → shadow becomes baseline. Not improved → discarded.

---

## Safety Architecture

### Shadow Parameter System

The agent NEVER modifies the production investigation registry directly. Every experiment runs against a shadow copy. Only after FQS improvement exceeds the threshold does the shadow commit to production.

### Rollback Conditions

Every proposal includes a rollback condition. If FQS drops more than 0.05 OR stability drops more than 0.10, the modification is automatically discarded.

### Experience Guardrail Integration

The Daily Experience Guardrail (see `DAILY_EXPERIENCE_GUARDRAIL_SPEC.md`) runs at 06:15 UTC. If the agent committed a parameter change overnight that produces a banned term, wrong date, or data integrity break in the morning voice, the guardrail catches it and the parameters can be rolled back.

The guardrail is the safety net for the auto-tuning loop.

---

## Data Density Activation Threshold

The loop is NOT activated for athletes with insufficient data.

**Minimum:** 90 days of synced data OR 60 activities — whichever comes first.

Below that threshold: investigations run with population defaults.
Above that threshold: the overnight loop activates.

This creates a natural product moment: "You now have enough history for personalized tuning."

---

## The "Learned Something New" Rarity Gate

The morning voice can reference overnight learning: "The system learned something new about you overnight." This is the single best product moment — the reason someone opens the app.

**But it must be rare.** If it fires every morning, it's noise. If it fires twice a month, it's a genuine event the athlete remembers.

**Gate conditions (ALL must be true):**
- Aggregate FQS improved by more than 0.05
- A new finding crossed the surfacing threshold for the first time
- The finding is genuinely novel (not a parameter tweak to an existing finding)

Otherwise: the loop ran, improved parameters silently, and the athlete notices their findings getting sharper over time without being told.

---

## Overnight Loop Architecture

```python
class AutoInvestigationLoop:
    """
    Runs nightly after daily fingerprint refresh (06:00 UTC).
    Target: 06:30-09:00 UTC — 2.5 hour budget.
    """

    NIGHTLY_BUDGET_S = 9000        # 2.5 hours
    IMPROVEMENT_THRESHOLD = 0.005  # Minimum FQS delta to keep
    MIN_ACTIVITIES = 60            # Data density gate
    MIN_DAYS = 90                  # Data density gate

    def run(self, athlete_id: str):
        if not self._meets_density_threshold(athlete_id):
            return

        baseline = self.load_investigation_baseline(athlete_id)
        baseline_fqs = self.score_all_investigations(athlete_id, baseline)
        original_fqs = baseline_fqs

        experiment_log = []
        budget_remaining = self.NIGHTLY_BUDGET_S

        while budget_remaining > 0:
            proposal = self.optimizer.propose_modification(
                baseline=baseline,
                current_fqs=baseline_fqs,
                experiment_history=experiment_log,
                athlete_coverage=self.get_signal_coverage(athlete_id),
            )

            candidate_params = self.apply_modification(baseline, proposal)
            candidate_fqs = self.score_all_investigations(athlete_id, candidate_params)

            delta = candidate_fqs - baseline_fqs
            if delta > self.IMPROVEMENT_THRESHOLD:
                baseline = candidate_params
                baseline_fqs = candidate_fqs
                outcome = "KEPT"
            else:
                outcome = "DISCARDED"

            experiment_log.append({
                "proposal": proposal,
                "delta_fqs": delta,
                "outcome": outcome,
                "timestamp": now(),
            })

            budget_remaining -= proposal.estimated_runtime

        if baseline_fqs > original_fqs:
            self.commit_to_registry(athlete_id, baseline)

        self.write_session_report(athlete_id, experiment_log, original_fqs, baseline_fqs)
```

---

## Session Report

Written to `experience_audit_log` (same table, tier = `auto_investigation`).

Example output:
```
AutoInvestigation run for Michael Shaffer — March 10, 2026
Experiments attempted: 23
Experiments kept: 4
Aggregate FQS: 0.71 → 0.79 (+11.3%)

Changes committed:
1. Sleep-efficiency lookback: 48h → 58h (+0.04 FQS)
   Rationale: Delayed cortisol response pattern detected in historical data

2. Volume cliff threshold: 55mi/wk → 61mi/wk (+0.03 FQS)
   Rationale: Athlete's adaptation curve suggests higher tolerance than population default

3. New finding surfaced: Afternoon run timing correlates with next-day efficiency
   Confidence: 0.71, seen 6 times, watching

4. Cascade: Sleep cliff → HRV drop → efficiency delay confirmed at 2-day lag
   Previously detected independently, now confirmed as connected pathway
```

---

## Why This Is the Moat

Every platform has activity data. Nobody else runs an automated optimization loop against individual physiology overnight. The moment this loop is live, every night that passes makes the product harder to replicate — not because of code, but because of accumulated knowledge per athlete.

A competitor would need to run the same loop for the same duration against the same athlete to catch up. That's a time-locked moat.

### Multi-Athlete Expansion (Horizon 4)

When multiple athletes have tuned parameters, findings that improve FQS for athletes with similar profiles become shareable priors. "Athletes with your running volume and sleep patterns tend to have a 58h sleep-efficiency lag, not 48h." That's cohort intelligence feeding individual tuning — the moat becomes permanent.

---

## Build Order

| Step | What | Dependency | Horizon |
|------|------|------------|---------|
| 1 | Experience Guardrail | None — **shipping now** | 2 |
| 2 | FQS metric implementation + validation | Guardrail live | 3 |
| 3 | Shadow investigation runner | FQS validated | 3 |
| 4 | Structured optimizer (Bayesian, not LLM) | Shadow runner | 3 |
| 5 | Cascade detection scoring | Optimizer live | 3 |
| 6 | LLM agent for novel investigation proposals | Steps 2-5 stable | 4 |
| 7 | Multi-athlete parameter sharing (cohort priors) | Step 6 + athlete base | 4 |

Steps 1-4 are buildable this month. Step 5 is a sprint. Steps 6-7 are Horizon 4.

---

## What This Does NOT Do

- Does not replace human judgment about which investigations to build
- Does not modify investigation *logic* — only parameters within existing investigations
- Does not run without the Experience Guardrail as safety net
- Does not activate for athletes below the data density threshold
- Does not surface "learned something new" without passing the rarity gate
- Does not use LLM agents in v1 — structured optimization only
