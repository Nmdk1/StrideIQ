# LIMITER → SESSION TAXONOMY — Annotation-Ready Draft

**Date:** 2026-03-29
**Status:** DRAFT — incorporates founder lifecycle directive. Awaiting annotation on mappings.
**Supersedes:** Static limiter model. Read `LIMITER_ENGINE_BRIEF.md` first.
**Depends on:** `KB_RULE_REGISTRY_ANNOTATED.md`, `03_WORKOUT_TYPES.md`, `fingerprint_bridge.py`

**Process:** Same as KB Rule Registry. I draft from the KB, correlation engine, and three athlete profiles. You annotate. Annotated version becomes the spec. I code from the annotated spec.

**Architectural context:** Limiters are temporary. A strong historical correlation is evidence of a solved problem, not an active limiter. Every limiter carries a lifecycle state (`emerging`, `active`, `resolving`, `closed`, `structural`). The correlation signatures below identify WHAT is correlated. The lifecycle classifier (Phase 3) determines WHETHER it is currently actionable. The mappings in Layers 1-2 remain valid — what changes is that they apply only to `active` and `structural` limiters, not to the entire historical dataset.

**Notation key:**
- `[PROPOSE]` = my best guess at the mapping — needs founder confirmation or correction
- `[FOUNDER]` = annotation from founder brief (2026-03-29)
- `[VALIDATE: athlete]` = this mapping should produce the right answer for the named athlete

---

## LAYER 0: LIMITER LIFECYCLE STATES

_Source: Founder architectural brief, 2026-03-29_

Every limiter finding carries one of five lifecycle states. The plan engine only reads `active` limiters. The coach layer surfaces `emerging` limiters for athlete confirmation. `Structural` traits modify plan delivery but are not treated as problems to solve.

| State | Definition | Who reads it | Plan effect |
|---|---|---|---|
| `emerging` | Correlation strengthening in L90 data. Not yet dominant in full history. Candidate frontier. | Coach layer | None — surfaced as question to athlete |
| `active` | Current frontier. Strongest recent signal. Confirmed by training pattern or athlete. | Plan engine | Session type and dosing adjustments per LM mappings |
| `resolving` | Intervention underway. Correlation weakening. Limiter closing. | Plan engine (reduced) | Reduced emphasis, engine scanning for next frontier |
| `closed` | Historical signal. Athlete solved it. No longer constrains performance. | None (archived) | None — preserved in development arc |
| `structural` | Physiological trait, not a solvable limiter. Recovery half-life, injury history. | Fingerprint bridge | Delivery parameter modifications (spacing, cutback, dosing) |

**Implementation phases:**
- Phase 1 (done): Static taxonomy + fingerprint bridge. Works for `structural` traits (Brian's L-REC). Wrong for historical solved problems (Michael's L-VOL).
- Phase 2 (next): Temporal weighting in correlation engine. L90 recency dominance.
- Phase 3: `lifecycle_state` field on CorrelationFinding. Classifier assigns states.
- Phase 4: Coach layer integration for `emerging` → `active` confirmation flow.
- Phase 5: Transition detection. `active` → `resolving` → `closed` triggers next-frontier scan.

---

## LAYER 1: CORRELATION → LIMITER MAPPING

**What this answers:** Given a correlation finding, which physiological limiter does it indicate?

**Critical frame (from founder brief):** These signatures identify the limiter TYPE. The lifecycle classifier determines whether the limiter is currently active, closed, or structural. A CS-1 match (long_run_ratio → threshold) in a `closed` state means "volume WAS the limiter — athlete solved it." Only `active` and `emerging` states drive plan changes.

### Limiter Categories

| ID | Limiter | Definition | Lifecycle note |
|---|---|---|---|
| L-VOL | Volume-constrained | More aerobic volume is the primary lever | Solvable — closes when volume reaches target |
| L-CEIL | Ceiling-constrained | VO2max / speed ceiling is the bottleneck | Solvable — closes when ceiling rises |
| L-THRESH | Threshold-constrained | Lactate threshold fitness is the limiter | Solvable — closes when threshold improves |
| L-REC | Recovery-constrained | Accumulated load / insufficient recovery is the limiter | Can be structural OR solvable. Brian = structural. An overtrained athlete = solvable. |
| L-CON | Consistency-responsive | Performance improves with consecutive training days | `[FOUNDER]` Renamed from L-DUR. Larry's signal. Rare, athlete-specific. |
| L-NONE | No limiter identified | Insufficient data or balanced profile | Default to population rules |

---

### Correlation Signatures

| ID | Correlation Pattern | Direction | Indicates Limiter | Rationale | Founder Notes |
|---|---|---|---|---|---|
| CS-1 | `long_run_ratio → pace_threshold` | positive | L-VOL | Threshold responds to aerobic volume investment, not threshold-specific work. | `[FOUNDER]` Michael r=0.75. Historically accurate, currently `closed` — he ran 40 long runs and fixed it. With temporal weighting, this signal correctly weakens. |
| CS-2 | `long_run_ratio → pace_easy` | positive | L-VOL | Volume is the general aerobic lever. | |
| CS-3 | `weekly_volume_km → pace_threshold` | positive | L-VOL | More total volume → faster threshold. | |
| CS-4 | `weekly_volume_km → pace_easy` | positive | L-VOL | More total volume → faster easy pace. | |
| CS-5 | `weekly_volume_km → efficiency` | positive | L-VOL | Volume drives efficiency (after CTL confounder control). | |
| CS-6 | `tsb → pace_threshold` | positive (strong) | L-REC | Freshness drives threshold performance. Has fitness, can't access it when fatigued. | `[FOUNDER]` Michael r=0.52. May indicate structural freshness-sensitivity rather than solvable recovery constraint. Context: everyone performs better fresh — signal must be STRONGER than population baseline to indicate L-REC. |
| CS-7 | `tsb → efficiency` | positive (strong) | L-REC | Freshness drives efficiency. | |
| CS-8 | `daily_session_stress → efficiency` | negative (strong) | L-REC | Hard sessions directly hurt next-day efficiency. | `[FOUNDER]` Brian r=-0.58. Structural — stable across time, multiple confirming signals. |
| CS-9 | `atl → efficiency` | negative | L-REC | Accumulated load hurts efficiency. | `[FOUNDER]` Brian — confirming signal for structural L-REC. |
| CS-10 | `days_since_rest → pb_events` | positive | L-CON | More consecutive days → better PBs. Consistency-responsive. | `[FOUNDER]` Larry r=0.77, n=11. Selection bias risk. Renamed L-DUR → L-CON. "suggested" until n≥20. |
| CS-11 | `days_since_quality → pace_threshold` | positive | L-THRESH | Threshold decays quickly without regular stimulus. | |
| CS-12 | `days_since_quality → pace_easy` | negative | L-CEIL | Easy pace holds while speed ceiling atrophies. Needs ceiling work. | |
| CS-13 | `consecutive_run_days → efficiency` | negative | L-REC | More consecutive days → lower efficiency. Standard recovery-constrained pattern. Opposite of CS-10. | |
| CS-14 | `garmin_body_battery_end → pace_threshold` | positive (strong) | L-REC | Recovery state predicts threshold performance. Performs to recovery, not fitness. | |
| CS-15 | `sleep_hours → pace_threshold` | positive | L-REC | More sleep → faster threshold. Recovery bottleneck. | |
| CS-16 | `ctl → pace_easy` | positive | L-VOL | Chronic load → better easy pace. Fitness is volume-built. | |
| CS-17 | `elevation_gain_m → efficiency` | negative | L-NONE | Terrain artifact. Controlled by confounder map. | |
| CS-18 | `weekly_elevation_m → pace_easy` | negative | L-NONE | Context variable, not limiter. | |

---

### Limiter Resolution Logic `[PROPOSE]`

When multiple correlation signatures are present in `active` or `emerging` state, resolve to a single primary limiter:

| Priority | Rule | Rationale | Founder Notes |
|---|---|---|---|
| 1 | L-REC structural (stable, multiple confirming, not shifting) → classify as `structural`, not `active` | Accommodated in delivery, not targeted as a training problem. | `[FOUNDER]` Brian's pattern. |
| 2 | L-REC solvable (recent onset, acute overtraining signal) → `active` L-REC | Recovery must be addressed first. Training without recovery is counterproductive. | |
| 3 | If L-VOL signals dominate in L90 data → `active` L-VOL | Volume is the current lever. | |
| 4 | If L-THRESH (CS-11) or L-CEIL (CS-12) in L90 → assign directly | Specific system deficiency. | |
| 5 | If L-CON (CS-10) → assign at confidence tier | Rare, athlete-specific. | |
| 6 | No clear dominant L90 signal → L-NONE | Default to distance-based prescription. | |

**Key distinction (from founder brief):** L-REC can be either structural OR solvable. Brian's L-REC is structural — his physiology. An overtrained athlete's L-REC is solvable — address it, then move on. The lifecycle classifier must distinguish these by checking temporal stability: stable for 90+ days = structural. Recent emergence = solvable.

**Founder Notes:** _[Does the structural vs solvable L-REC distinction need additional signals beyond temporal stability? For example: recovery half-life > 48h + stable L-REC signals → structural. Recovery half-life < 36h + recent L-REC signals → solvable (overtraining). Is half-life a useful gate here?]_

---

## LAYER 2: LIMITER → SESSION TYPE MAPPING

**What this answers:** Given an `active` limiter, what should the primary quality emphasis be?

**Frame:** These mappings apply ONLY to `active` limiters. `Structural` traits (L-REC structural) modify delivery parameters via the fingerprint bridge, not session types. `Closed` limiters are ignored. `Emerging` limiters are surfaced to the coach layer, not acted on.

### Default (No Fingerprint / L-NONE) — Population Rules from KB

| Distance | Primary System | Secondary System | KB Source |
|---|---|---|---|
| 5K | Ceiling (intervals) | Threshold | DQ-1 |
| 10K | Threshold | Ceiling (intervals) | DQ-3 |
| Half Marathon | Threshold | Durability + Ceiling | DQ-5 (population default) |
| Marathon | Race-specific (MP) | Threshold + Durability | DQ-6 |

Distance rules set the FLOOR — minimum session types that must be present. Active limiter adjusts the RATIO within that floor.

---

### Fingerprint-Driven Overrides (Active Limiters Only)

| ID | Limiter | Primary Quality Emphasis | Session Types Favored | Session Types De-emphasized | KB Cross-ref | Founder Notes |
|---|---|---|---|---|---|---|
| LM-1 | L-VOL (active) | Long run quality | Long runs with quality (MP, progressive, fast finish), MLR, volume growth | Additional midweek quality beyond 2 | GP-1, CS-1 | `[PROPOSE]` Only applies when L-VOL is the CURRENT frontier, not historical. Distance floor still applies. |
| LM-2 | L-CEIL (active) | Interval emphasis | VO2 intervals (800m-1200m), reps (200m-400m), ceiling-raising | Long run quality volume (keep LRs easy) | GP-1, DQ-1, DQ-2 | `[PROPOSE]` Half marathoner with L-CEIL gets 10K-style training per DQ-5 annotation. |
| LM-3 | L-THRESH (active) | Threshold emphasis | Cruise intervals, continuous threshold, tempo, HMP in long runs | VO2 at maintenance dose | GP-1, DQ-3, DQ-6 | `[PROPOSE]` |
| LM-4 | L-REC (structural) | No session type change | Unchanged from distance default | Unchanged | GP-3, RC-2, VR-11 | `[FOUNDER]` Session TYPE unchanged — SPACING and FREQUENCY change. 2 quality max, 72h spacing, cutback every 3rd week. This is delivery, not prescription. |
| LM-4b | L-REC (active/solvable) | Recovery block | Reduced quality, increased easy volume, active recovery emphasis | All quality sessions reduced or suspended | GP-3 | `[PROPOSE]` Overtrained athlete. Short-term intervention: cut quality, rebuild, then resume. Different from structural L-REC. |
| LM-5 | L-CON (suggested/confirmed) | Consistency emphasis | Consecutive running days, MLR, easy mileage accumulation | Unnecessary rest days, aggressive cutbacks | CS-10 | `[FOUNDER]` Renamed from L-DUR. At "suggested": don't add rest. At "confirmed": actively reduce rest. |
| LM-6 | L-NONE | Distance-based default | Per DQ-1 through DQ-6 | No overrides | All DQ rules | Default fallback. |

---

### Half Marathon Special Case — DQ-5 Limiter Fork `[PROPOSE]`

| Profile | Fingerprint Signal (active limiter) | Build Structure | Training Style |
|---|---|---|---|
| Marathon-profile | L-VOL active | T-block → HMP long runs → dress rehearsal | Marathon-type: high volume, threshold emphasis |
| Speed-profile | L-CEIL active | Intervals → threshold → HMP sharpening | 10K-type: interval emphasis, ceiling work |
| Unknown | L-NONE | DQ-5 default: T-block → HMP long runs | Population default (marathon-profile assumed) |

**Founder Notes:** _[Is this fork correct? Are there intermediate profiles? Does the speed-profile half marathoner ever get MP long runs, or is that exclusively marathon-profile?]_

---

## LAYER 3: CONFIDENCE GATES

### Gate Structure

| ID | Gate | Minimum | Effect Below Gate | Effect Above Gate | Founder Notes |
|---|---|---|---|---|---|
| CG-1 | Correlation strength | \|r\| >= 0.30, p < 0.05 | Finding not persisted | Finding persisted | Already enforced |
| CG-2 | Reproducibility | times_confirmed >= 3 | Not surfaced, not used for limiter | Eligible for limiter assignment | Already enforced |
| CG-3 | Limiter (suggested) | ≥2 CS-rules matching same limiter, each confirmed ≥3× | L-NONE | Conservative overrides only | `[PROPOSE]` |
| CG-4 | Limiter (confirmed) | ≥3 CS-rules, each confirmed ≥5×, ≥20 total observations | Suggested overrides | Full overrides | `[PROPOSE]` |
| CG-5 | Recovery bridge | recovery_confidence >= 0.3 | Default cutback/spacing | Fingerprint-driven | Already implemented |
| CG-6 | Load tier override | ≥90% peak or building at ≥80% | Half-life alone | Half-life capped by VR-11 safety | Already implemented |
| CG-7 | L-CON preference | Per `_detect_consecutive_day_preference` | Standard rest scheduling | suggested (n<20): don't add rest. confirmed (n≥20): reduce rest. | Already implemented |
| CG-8 | Temporal recency (Phase 2) | L90-weighted correlation strength | Full-history correlation drives limiter | L90-weighted correlation drives limiter | Phase 2 implementation |
| CG-9 | Lifecycle state (Phase 3) | Lifecycle classifier assigns state | Static limiter assignment | Lifecycle-aware: only `active` drives plan | Phase 3 implementation |

### What "suggested" vs "confirmed" means for `active` limiters

| Override Type | Suggested (CG-3) | Confirmed (CG-4) |
|---|---|---|
| Primary quality type | Unchanged from distance default | Shifted to limiter-driven emphasis |
| Quality session count | Unchanged | May increase or decrease |
| Long run quality type | Unchanged | Shifted (e.g., L-VOL → more quality LRs) |
| Quality spacing | Unchanged (except L-REC structural, which overrides at suggested) | Fully limiter-driven |
| Rest day scheduling | Unchanged | L-CON confirmed can reduce rest |
| Cutback frequency | Already fingerprint-driven via CG-5 | Same |

**Founder Notes:** _[Should L-REC (structural) override at suggested level? Conservative spacing is safety, not optimization. Rather be too conservative than too aggressive.]_

---

## LAYER 4: TEMPORAL WEIGHTING (Phase 2 Spec)

_Source: Founder architectural brief, 2026-03-29_

The correlation engine needs L90 weighting before lifecycle classification works. Without it, strong old correlations dominate weak new emerging signals.

### Proposed Weights

| Window | Weight | Rationale |
|---|---|---|
| L30 (last 30 days) | 4× | Most recent data is most relevant to current state |
| L31-90 | 2× | Recent but allowing for training phase transitions |
| L91-180 | 1× | Baseline (standard weight) |
| Beyond 180 days | 0.5× | Historical context, fading relevance |

### Expected Effect on Three Athletes

| Athlete | Signal | L90 effect | Expected lifecycle state |
|---|---|---|---|
| Michael | CS-1 (long_run_ratio → threshold, r=0.75) | Weakens — signal is 8+ months old, training shifted to threshold/intervals | `closed` |
| Michael | Current training: threshold + intervals + quality LRs | Strengthens — recent pattern | `active` L-CEIL or L-THRESH (emerging) |
| Larry | CS-10 (days_since_rest → PBs, r=0.77) | Stable — ongoing pattern, n=11 | `emerging` L-CON (still insufficient n) |
| Brian | CS-8 (session_stress → efficiency, r=-0.58) | Stable — recent and consistent, multiple confirming | `structural` L-REC |

### Implementation Location

`correlation_engine.py` → `find_time_shifted_correlations` → weight observations by recency before computing r.

**Founder Notes:** _[Are the exact weights right? 4×/2×/1×/0.5× is the proposal. The principle (recency dominates) is non-negotiable. The coefficients are adjustable.]_

---

## VALIDATION AGAINST THREE ATHLETE PROFILES

### Michael Shaffer (Founder)

- **Recovery:** 23.8h half-life, high load currently (crash block for 10K)
- **Key correlations:** long_run_ratio → threshold (r=0.75), TSB → threshold (r=0.52)
- **Static taxonomy says:** L-VOL primary
- **Lifecycle model says:** `[FOUNDER]` L-VOL is `closed`. He ran 40 long runs and fixed it. Threshold improved as a result. Then threshold became the weakness. The correlation captured the history of solved problems. His CURRENT limiter is race-specific sharpening — intervals, threshold, quality long runs. The plan should support exactly what he is already doing, not add long run emphasis.
- **Phase 2 effect:** L90 weighting correctly weakens CS-1. Current training pattern (intervals + threshold) would surface as `emerging` L-CEIL or L-THRESH.

### Larry Shaffer (79, state record holder)

- **Recovery:** 46.4h half-life
- **Key correlations:** days_since_rest → PBs (r=0.77, n=11), cadence → efficiency (confounded, suppressed)
- **Static taxonomy says:** L-DUR suggested
- **Lifecycle model says:** `[FOUNDER]` L-CON (renamed). Signal remains at `suggested` confidence (n=11, selection bias caveat). Structural trait: 46.4h recovery half-life → delivery modifications (every 3rd week cutback, 48h spacing). No active limiter confirmed. Gets distance-default prescription with structural delivery modifications. As data accumulates, engine watches for L-CON to strengthen or other limiters to emerge.

### Brian Levesque (data-sparse, slow recoverer)

- **Recovery:** 51.3h half-life
- **Key correlations:** session_stress → efficiency (r=-0.58), TSB → efficiency (+), ATL → efficiency (-)
- **Static taxonomy says:** L-REC
- **Lifecycle model says:** `[FOUNDER]` L-REC correctly identified as `structural`. Stable, not shifting, multiple confirming signals. This is his physiology. Plan accommodates: 72h spacing, 2 quality max, cutback every 3rd week. Not a problem to solve — a trait to work with. As data grows, engine watches for OTHER limiters to emerge within the structural recovery constraint.

---

## OPEN QUESTIONS FOR ANNOTATION

1. **L-REC structural vs solvable gate.** `[PROPOSE]` Recovery half-life > 48h + stable L-REC signals across 90+ days = structural. Recovery half-life < 36h + recent L-REC emergence = solvable (overtraining). Is half-life a useful discriminator here?

2. **Does L-REC structural override at "suggested" confidence?** Conservative spacing is safety, not optimization. Founder brief implies yes.

3. **Half marathon fork — intermediate profiles?** DQ-5 annotation describes two profiles. Is there a third?

4. **Limiter vs distance floor interaction.** `[PROPOSE]` Distance rules set the minimum session types. Active limiter adjusts the RATIO. A 5K runner with active L-VOL still gets VO2 intervals (DQ-1 floor) but the balance shifts toward volume investment. Correct?

5. **CS-6 (TSB → threshold) sensitivity.** Everyone performs better fresh. At what strength does TSB → performance stop being "obviously true for all humans" and start being a genuine L-REC signal? `[PROPOSE]` Only flag L-REC from TSB when |r| > 0.50 (stronger than typical population baseline).

6. **Phase 2 temporal weights.** 4×/2×/1×/0.5× proposed. Principle is non-negotiable. Coefficients adjustable. Are these coefficients right?

7. **What is Michael's CURRENT active limiter?** The brief says race-specific sharpening. Is that L-CEIL, L-THRESH, or something the taxonomy doesn't yet name (e.g., L-SPECIFIC)?
