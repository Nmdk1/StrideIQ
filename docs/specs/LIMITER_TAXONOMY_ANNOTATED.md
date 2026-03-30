# LIMITER → SESSION TAXONOMY — ANNOTATED

**Date:** 2026-03-29
**Status:** Founder-annotated. Ready for Phase 2 implementation.
**Governs:** `fingerprint_bridge.py`, `limiter_classifier.py` (Phase 3), `correlation_engine.py` (Phase 2)
**Read first:** `LIMITER_ENGINE_BRIEF.md` (lifecycle model)
**Depends on:** `KB_RULE_REGISTRY_ANNOTATED.md`, `03_WORKOUT_TYPES.md`

**Notation key:**
- `[FOUNDER]` = founder annotation (2026-03-29)
- `[CONFIRMED]` = proposed mapping confirmed by founder
- `[DISABLED]` = not yet enabled, pending validation

---

## LAYER 0: LIMITER LIFECYCLE STATES

| State | Definition | Who reads it | Plan effect |
|---|---|---|---|
| `emerging` | Correlation strengthening in L90 data. Candidate frontier. | Coach layer | None — surfaced as question to athlete |
| `active` | Current frontier. Strongest recent signal. Confirmed by training pattern or athlete. | Plan engine | Session type and dosing adjustments per LM mappings |
| `active-fixed` | `[FOUNDER]` Special state for L-SPEC only. By definition always active when present. Short-term pre-race state. Does not move through resolving → closed via correlation weakening. Closes on race date. | Plan engine | Support existing crash block, protect taper, do not add volume or sessions |
| `resolving` | Intervention underway. Correlation weakening. Limiter closing. | Plan engine (reduced) | Reduced emphasis, engine scanning for next frontier |
| `closed` | Historical signal. Athlete solved it. | None (archived) | None — preserved in development arc |
| `structural` | Physiological trait, not a solvable limiter. | Fingerprint bridge | Delivery parameter modifications only |

Implementation phases (from LIMITER_ENGINE_BRIEF.md):
- Phase 1 (done): Static taxonomy + fingerprint bridge
- Phase 2 (next): Temporal weighting in correlation engine
- Phase 3: `lifecycle_state` field on CorrelationFinding + classifier
- Phase 4: Coach layer integration for `emerging` → `active` confirmation
- Phase 5: Limiter transition detection (`active` → `resolving` → `closed` → scan)

---

## LAYER 1: CORRELATION → LIMITER MAPPING

### Limiter Categories

| ID | Limiter | Definition | Lifecycle note |
|---|---|---|---|
| L-VOL | Volume-constrained | More aerobic volume is the primary lever | Solvable. Closes when volume deficit is addressed. |
| L-CEIL | Ceiling-constrained | VO2max / speed ceiling is the bottleneck | Solvable. Closes when ceiling rises through interval work. |
| L-THRESH | Threshold-constrained | Lactate threshold fitness is the limiter | Solvable. Closes when threshold improves through threshold-specific work. |
| L-REC | Recovery-constrained | Accumulated load / insufficient recovery | `[FOUNDER]` Can be `structural` OR `solvable`. Discriminated by half-life + temporal stability. See CG-11. |
| L-CON | Consistency-responsive | Performance improves with consecutive training days | `[FOUNDER]` Rare, athlete-specific. Larry's signal. At `suggested` until n≥20. |
| L-DUR | True durability fade | Pace fades over distance — strong first half, falls apart second half | `[FOUNDER]` Distinct from L-CON. Different correlation signatures (split pace deterioration). `[PENDING — signatures not yet defined]` |
| L-SPEC | Race-specific integration | Athlete has base, threshold, and ceiling but has not trained the specific expression of all three at goal pace and duration | `[FOUNDER]` Always `active-fixed` when present. Short-term pre-race state. Resolves at race day. Rule-based assignment, not correlation-based. Common in return-from-injury athletes, distance transitions, final 4-6 weeks pre-A-race. |
| L-NONE | No limiter identified | Insufficient data or balanced profile | Default to distance population rules. |

**`[FOUNDER]` L-DUR vs L-CON:** These were conflated in the original draft. They are different animals. L-CON is Larry — performs better with more consecutive days, fitness builds through density. L-DUR is a different athlete — one whose aerobic base is insufficient to hold pace over the full race distance. The fix for L-DUR is more volume and longer long runs. The fix for L-CON is not adding unnecessary rest. Do not conflate them in code.

---

### Correlation Signatures

| ID | Pattern | Direction | Limiter | Annotation |
|---|---|---|---|---|
| CS-1 | `long_run_ratio → pace_threshold` | positive | L-VOL | `[FOUNDER]` Michael r=0.75. `closed` — solved problem. With temporal weighting correctly weakens. For a different athlete where this signal is recent and strengthening in L90: correctly identifies `active` L-VOL. |
| CS-2 | `long_run_ratio → pace_easy` | positive | L-VOL | `[CONFIRMED]` Same limiter, broader expression. CS-1 + CS-2 together strengthens L-VOL signal. |
| CS-3 | `weekly_volume_km → pace_threshold` | positive | L-VOL | `[CONFIRMED]` |
| CS-4 | `weekly_volume_km → pace_easy` | positive | L-VOL | `[CONFIRMED]` |
| CS-5 | `weekly_volume_km → efficiency` | positive | L-VOL | `[FOUNDER]` Weakest L-VOL signal. Raw volume → efficiency can be fitness artifact — fitter athletes run more AND run more efficiently. Only assign L-VOL from CS-5 if partial correlation holds after CTL confounder control. **CS-5 alone never drives a limiter assignment. Confirming signal only.** |
| CS-6 | `TSB → pace_threshold` | positive | L-REC | `[FOUNDER]` Interaction rule: only flag L-REC when \|r\| >0.45 AND half-life >36h. Fast recoverers (≤30h half-life) with TSB correlation get a timing signal note only, not L-REC. Michael at r=0.52 with 23.8h: timing signal. Brian with 51.3h + similar: genuine L-REC. See CG-10. |
| CS-7 | `TSB → efficiency` | positive | L-REC | `[FOUNDER]` Same interaction rule as CS-6. See CG-10. |
| CS-8 | `daily_session_stress → efficiency` | negative | L-REC | `[FOUNDER]` Strongest L-REC signal. Direct and unambiguous. Brian r=-0.58. No strength modifier needed beyond CG-1 gate. Clear L-REC regardless of half-life. |
| CS-9 | `ATL → efficiency` | negative | L-REC | `[FOUNDER]` Chronic version of CS-8. CS-8 + CS-9 together strongly confirms L-REC. Structural if stable 90+ days, solvable if recent emergence. |
| CS-10 | `days_since_rest → pb_events` | positive | L-CON | `[FOUNDER]` Renamed from L-DUR. Larry r=0.77, n=11. Selection bias risk. `suggested` until n≥20. Not L-DUR — different limiter. |
| CS-11 | `days_since_quality → pace_threshold` | positive | L-THRESH | `[CONFIRMED]` Threshold decaying without regular stimulus. Adaptation is perishable. |
| CS-12 | `days_since_quality → pace_easy` | negative | L-CEIL | `[DISABLED — pending validation]` `[FOUNDER]` May be confounded by training phase. Athletes in base phase naturally have faster easy paces AND fewer quality sessions — produces this correlation as phase artifact. Do not enable until validated against at least one athlete whose fingerprint contains this pattern outside base phase context. |
| CS-13 | `consecutive_run_days → efficiency` | negative | L-REC | `[CONFIRMED]` Standard recovery-constrained pattern. Opposite of CS-10. CS-8 + CS-9 + CS-13 = very strong L-REC. |
| CS-14 | `garmin_body_battery_end → pace_threshold` | positive | L-REC | `[FOUNDER]` High-value signal. Athlete performs to recovery state, not fitness. Also actionable in real time — athlete can check body battery before quality session. |
| CS-15 | `sleep_hours → pace_threshold` | positive | L-REC | `[FOUNDER]` Crude measure. Where Garmin sleep quality data available, prefer it over sleep hours. If sleep quality present, use it. If only hours, use CS-15 as written. |
| CS-16 | `CTL → pace_easy` | positive | L-VOL | `[CONFIRMED]` Clean volume-responsiveness signal. Confirming for L-VOL. |
| CS-17 | `elevation_gain_m → efficiency` | negative | L-NONE | `[CONFIRMED]` Terrain artifact. Confounder map handles it. |
| CS-18 | `weekly_elevation_m → pace_easy` | negative | L-NONE | `[CONFIRMED]` Context variable, not limiter. |

**`[FOUNDER]` Pending future signatures:**

L-DUR needs its own correlation signatures (not yet in engine):
- `second_half_pace_delta → race_performance` negative
- `long_run_completion_pace_drop`
- `split_deterioration_index`

L-SPEC has no correlation signatures — it is rule-based (see CG-12).

---

### Limiter Resolution Logic

| Priority | Rule | Annotation |
|---|---|---|
| 0 | Context: ≤6 weeks to race + advanced tier + intervals + threshold in L30 → L-SPEC `active-fixed` | `[FOUNDER]` Highest priority. Time-bounded, context-specific. Overrides all correlation-based limiters. |
| 1 | L-REC structural (half-life >48h + stable 90+ days) → `structural` | `[FOUNDER]` Brian's pattern. Accommodate, don't target. |
| 1b | L-REC (half-life 36-48h + stable) → `structural, monitored` | `[FOUNDER]` May shift to solvable if acute cause identified. Watch for change. |
| 2 | L-REC solvable (half-life <36h + recent emergence <60 days) → `active` L-REC | `[FOUNDER]` Overtrained athlete with fast baseline recovery. Address first. |
| 3 | L-VOL signals dominant in L90 → `active` L-VOL | `[CONFIRMED]` Only when recent, not historical. |
| 4 | L-THRESH (CS-11) in L90 → `active` L-THRESH | `[CONFIRMED]` |
| 5 | L-CEIL (CS-12) → `active` L-CEIL | `[DISABLED]` Pending CS-12 validation. |
| 6 | L-CON (CS-10) → assign at confidence tier | `[CONFIRMED]` Larry's pattern. |
| 7 | No clear dominant L90 signal → L-NONE | `[CONFIRMED]` |

**`[FOUNDER]` Dual limiters:** An athlete can have primary and secondary limiters. Secondary limiter modifies the DELIVERY of the primary prescription — it does not add a parallel prescription layer. Secondary limiter is a dosing modifier only. Does not change session type.

---

## LAYER 2: LIMITER → SESSION TYPE MAPPING

### Default (L-NONE) — Population Rules from KB

| Distance | Primary System | Secondary System | KB Source |
|---|---|---|---|
| 5K | Ceiling (intervals) | Threshold | DQ-1 |
| 10K | Threshold | Ceiling (intervals) | DQ-3 |
| Half Marathon | Threshold | Durability + Ceiling | DQ-5 |
| Marathon | Race-specific (MP) | Threshold + Durability | DQ-6 |

`[FOUNDER]` Distance rules set the FLOOR — minimum session types always present. Active limiter adjusts the RATIO within the floor. Floor session types are never removed by a limiter — only the balance changes.

---

### Fingerprint-Driven Overrides (Active Limiters Only)

| ID | Limiter | Primary Quality Emphasis | Session Types Favored | Session Types De-emphasized | Annotation |
|---|---|---|---|---|---|
| LM-1 | L-VOL (active) | Long run quality | Quality LRs (MP, progressive, fast finish), MLR, volume growth | Additional midweek quality beyond 2 | `[FOUNDER]` Only when L-VOL is CURRENT frontier in L90. Distance floor still applies. Do not increase midweek quality session count. |
| LM-2 | L-CEIL (active) | Interval emphasis | VO2 intervals (800-1200m), reps (200-400m), ceiling-raising | Long run quality (keep LRs easy) | `[FOUNDER]` Long runs stay easy when L-CEIL active. HM speed-profile gets 10K-style training. No MP long runs for speed-profile. |
| LM-3 | L-THRESH (active) | Threshold emphasis | Cruise intervals, continuous threshold, tempo, HMP in LRs | VO2 at maintenance dose | `[FOUNDER]` Marathon: T already the base, L-THRESH increases dosage — longer sessions within 40min cap, more frequent before adding intervals. 10K: T already population default per DQ-3, so increase T volume/duration. VO2 at minimum dose (DQ-3 requires it). |
| LM-4 | L-REC (structural) | No session type change | Distance default unchanged | Distance default unchanged | `[FOUNDER]` SPACING and FREQUENCY change only: 2 quality max, 72h spacing, cutback every 3rd week. Exception: severely structural (half-life >60h + CS-8 + CS-9 confirmed) may substitute one interval session with a progressive easy run. Only case where structural L-REC touches session type. |
| LM-4b | L-REC (solvable) | Recovery block | Reduced quality, increased easy volume, active recovery | All quality reduced or suspended | `[FOUNDER]` Overtrained athlete. Short-term: 2-3 weeks max before reassessing. Track intervention start date. Once acute signals resolve, resume normal prescription. |
| LM-5 | L-CON (suggested/confirmed) | Consistency emphasis | Consecutive running days, MLR, easy mileage | Unnecessary rest days, aggressive cutbacks | `[FOUNDER]` Suggested (n<20): don't add rest. Confirmed (n≥20): actively schedule consecutive days. Never remove requested rest (N1-3 is hard). Larry at `suggested` — no age-based rest padding. |
| LM-6 | L-NONE | Distance default | Per DQ-1 through DQ-6 | No overrides | `[CONFIRMED]` Safe fallback. |
| LM-7 | L-SPEC (active-fixed) | Support crash block | Organize existing quality sessions, maintain spacing per half-life, protect taper, handle double-race structure | Do not add volume, sessions, or session types | `[FOUNDER]` Plan engine role: organize, space, protect, get out of the way. Supercompensation mechanism already engaged — plan does not improve it by adding stimulus, only by protecting taper window. |

---

### Half Marathon Fork (DQ-5)

| Profile | Fingerprint Signal | Build Structure | Training Style | Annotation |
|---|---|---|---|---|
| Marathon-profile | L-VOL active in L90 | T-block → HMP long runs → dress rehearsal | High volume, threshold emphasis | `[FOUNDER]` MP long runs included. Founder's profile at HM distance. |
| Speed-profile | L-CEIL active in L90 | Intervals → threshold → HMP sharpening | 10K-type: interval emphasis, ceiling work | `[FOUNDER]` Long runs stay easy. **No MP long runs** — MP is marathon-profile exclusively. |
| Balanced | L-NONE | DQ-5 default: T-block → HMP long runs | Population default (marathon-profile assumed) | `[FOUNDER]` No third named profile needed. L-NONE IS the intermediate profile. |

---

## LAYER 3: CONFIDENCE GATES

| ID | Gate | Minimum | Effect Below | Effect Above | Annotation |
|---|---|---|---|---|---|
| CG-1 | Correlation strength | \|r\| ≥ 0.30, p < 0.05 | Not persisted | Persisted | Already enforced. |
| CG-2 | Reproducibility | times_confirmed ≥ 3 | Not surfaced | Eligible for limiter | Already enforced. |
| CG-3 | Limiter suggested | ≥2 CS-rules matching same limiter, each confirmed ≥3× | L-NONE | Conservative overrides | `[CONFIRMED]` |
| CG-4 | Limiter confirmed | ≥3 CS-rules, each confirmed ≥5×, ≥20 total observations | Suggested only | Full overrides | `[CONFIRMED]` |
| CG-5 | Recovery bridge | recovery_confidence ≥ 0.3 | Default spacing | Fingerprint-driven | Already implemented. |
| CG-6 | Load tier override | ≥90% peak or building ≥80% | Half-life alone | Capped by VR-11 | Already implemented. |
| CG-7 | L-CON preference | Per `_detect_consecutive_day_preference` | Standard rest | suggested: don't add. confirmed: reduce. | Already implemented. |
| CG-8 | Temporal recency | L90-weighted correlation strength | Full-history drives limiter | L90-weighted drives limiter | Phase 2. |
| CG-9 | Lifecycle state | Classifier assigns state | Static assignment | Only `active` drives plan | Phase 3. |
| CG-10 | CS-6/CS-7 interaction | \|r\| >0.45 AND half-life >36h | Timing signal note only | L-REC assignment | `[FOUNDER]` Fast recoverers with TSB correlation do not get L-REC. Michael at r=0.52 + 23.8h half-life = timing signal. |
| CG-11 | L-REC discriminator | See tiers below | See tiers | See tiers | `[FOUNDER]` Three-tier system. |
| CG-12 | L-SPEC context | ≤6 wks to race + advanced + intervals + threshold in L30 | No L-SPEC | L-SPEC active-fixed | `[FOUNDER]` Rule-based. Highest priority — overrides all other limiters. |

### CG-11 L-REC Structural vs Solvable Discriminator

| Half-life | Temporal pattern | Classification |
|---|---|---|
| >48h | Stable signals 90+ days | `structural` |
| 36-48h | Stable signals 90+ days | `structural, monitored` — may shift if acute cause identified |
| 36-48h | Recent emergence (<60 days) | `solvable` |
| <36h | Recent emergence (<60 days) | `solvable` — overtrained athlete with fast baseline recovery |

**`[FOUNDER]` L-REC structural overrides at suggested confidence (CG-3), not confirmed (CG-4).** Conservative spacing is safety, not optimization. Cost of too conservative: few percent optimization loss. Cost of too aggressive: injury, overtraining, plan abandonment.

### What "suggested" vs "confirmed" means for active limiters

| Override Type | Suggested (CG-3) | Confirmed (CG-4) |
|---|---|---|
| Primary quality type | Unchanged from distance default | Shifted to limiter-driven emphasis |
| Quality session count | Unchanged | May increase or decrease |
| Long run quality type | Unchanged | Shifted (L-VOL → more quality LRs) |
| Quality spacing | Unchanged (except L-REC structural, which overrides here) | Fully limiter-driven |
| Rest day scheduling | Unchanged | L-CON confirmed can reduce rest |
| Cutback frequency | Already fingerprint-driven via CG-5 | Same |

---

## LAYER 4: TEMPORAL WEIGHTING

| Window | Weight | Annotation |
|---|---|---|
| L30 (last 30 days) | 4× | `[CONFIRMED]` Most relevant to current state |
| L31-90 | 2× | `[CONFIRMED]` Recent, allows phase transitions |
| L91-180 | 1× | `[CONFIRMED]` Baseline |
| Beyond 180 days | 0.75× | `[FOUNDER]` Adjusted from 0.5×. Historical context still informative — injury patterns, structural traits. 0.5× discards too much. |

Principle (recency dominates) is non-negotiable. Coefficients are best current estimate — adjustable as engine accumulates data across more athletes.

### Expected Effect on Three Athletes

| Athlete | Signal | L90 effect | Expected lifecycle state |
|---|---|---|---|
| Michael | CS-1 (long_run_ratio → threshold, r=0.75) | Weakens — 8+ months old | `closed` |
| Michael | Current: intervals + threshold + quality LRs, ≤6 weeks to 10K | Context match for CG-12 | `active-fixed` L-SPEC |
| Michael | CS-6 (TSB → threshold, r=0.52) | Filtered by CG-10 (half-life 23.8h < 36h) | Timing signal, not L-REC |
| Larry | CS-10 (days_since_rest → PBs, r=0.77, n=11) | Stable — ongoing pattern | `emerging` L-CON (insufficient n) |
| Larry | Structural: 46.4h half-life | Stable delivery modifier | `structural` (delivery only) |
| Brian | CS-8 (session_stress → efficiency, r=-0.58) | Stable — recent and consistent | `structural` L-REC |

---

## VALIDATION

**Michael (founder):**
L-VOL `closed`. CS-1 captured solved problem. L-SPEC `active-fixed` — ≤6 weeks to goal 10K, advanced, intervals + threshold in L30. CG-12 fires, overrides all. Plan supports crash block, protects double-race taper. TSB at r=0.52 correctly filtered by CG-10 (23.8h half-life) — timing signal only.

**Larry (79, state record holder):**
L-CON `suggested`. CS-10 at r=0.77, n=11 — selection bias risk, insufficient for `confirmed`. Structural: 46.4h half-life → delivery modifications (every 3rd week cutback, 48h spacing). Cadence suppressed by elevation confounder. No active limiter confirmed. Distance-default prescription + structural delivery modifications. L-DUR does not apply to Larry.

**Brian (data-sparse, slow recoverer):**
L-REC `structural`. CS-8 r=-0.58, CS-9, TSB positive — stable, multiple confirming, not shifting. Half-life 51.3h → CG-11 classifies structural. Delivery: 72h spacing, 2 quality max, cutback every 3rd week. Session type unchanged from distance default. Exception: if CS-8 + CS-9 both confirmed at >5× AND half-life remains >60h, may substitute one interval with progressive easy run (LM-4 severely structural clause). As data grows, engine watches for other limiters to emerge.

---

## SUMMARY OF CHANGES FROM DRAFT

**New additions:**
- L-SPEC (race-specific integration) + `active-fixed` lifecycle state + LM-7 + CG-12
- L-DUR split from L-CON (pending — needs correlation signatures)
- CG-10 (CS-6/CS-7 interaction gate)
- CG-11 (L-REC three-tier discriminator)
- Priority 0 in resolution logic (L-SPEC overrides all)
- Secondary limiter concept (dosing modifier, not parallel prescription)

**Changes from draft:**
- CS-6 threshold: \|r\| >0.45 (not 0.50), with half-life interaction
- CS-12: DISABLED pending validation
- CS-5: confirming signal only, never drives limiter alone
- CS-10: L-DUR → L-CON
- Temporal weight beyond 180: 0.75× (not 0.5×)
- L-REC structural overrides at suggested confidence
- HM speed-profile: no MP long runs
- LM-4 severely structural clause (>60h + CS-8 + CS-9 → may substitute one interval)
- No third HM profile — L-NONE handles balanced athletes

**Unchanged:**
- CG-1 through CG-7 (already implemented)
- Distance floor principle (non-negotiable)
- Limiter ratio interaction with floor (confirmed)
- Phase implementation sequence
- CS-1 through CS-4, CS-8, CS-9, CS-11, CS-13 through CS-18 substance
