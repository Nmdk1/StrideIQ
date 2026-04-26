# KB Rule Registry — Extracted for Automated Evaluation

**Date:** 2026-03-28
**Status:** DRAFT — Founder review required before coding evaluator checks
**Source:** Every rule below is extracted from the knowledge base with exact source reference.

Each rule has:
- **ID**: for traceability
- **Source**: KB file + section
- **Rule**: what must be true
- **Check type**: `hard` (automated pass/fail) or `soft` (needs context/N=1 override)
- **Founder notes**: blank — for you to annotate exceptions, corrections, or context

---

## Category 1: Phase Rules

| ID | Source | Rule | Check | Founder Notes |
|----|--------|------|-------|---------------|
| PH-1 | PLAN_GENERATION_FRAMEWORK A1, TRAINING_PHILOSOPHY Part 2, TRAINING_METHODOLOGY 2.3 | Base phase: 0 quality sessions per week. Only strides and hill sprints allowed. No threshold. | hard | |
| PH-2 | PLAN_GENERATION_FRAMEWORK A1 | Base phase duration: 3-4 weeks (full plan) | soft | |
| PH-3 | TRAINING_PHILOSOPHY Part 2 | Build 1 focus: threshold introduction. 1 quality session/week. | hard | |
| PH-4 | TRAINING_PHILOSOPHY Part 2 | Build 2 focus: race-specific integration. 1 quality session/week. Alternating T and MP. | hard | |
| PH-5 | TRAINING_METHODOLOGY 2.3 | Taper: 1 quality session/week. Only short threshold and strides allowed. | hard | |
| PH-6 | PLAN_GENERATION_FRAMEWORK Part 4, TRAINING_METHODOLOGY 2.3 | Speed work (intervals) only in base phase for most athletes. Exception: 5K/10K race-specific sharpening in peak (short, sharp, not VO2 blocks). | hard | |
| PH-7 | TRAINING_PHILOSOPHY Part 2 | Never ramp volume AND intensity simultaneously. | hard | |
| PH-8 | N1_PLAN_ENGINE_SPEC §3 | Abbreviated builds (≤5 weeks): no periodization phases, no cutbacks. Quick ramp → peak → taper. | hard | |

---

## Category 2: Weekly Structure Rules

| ID | Source | Rule | Check | Founder Notes |
|----|--------|------|-------|---------------|
| WS-1 | 04_RECOVERY §3.4, TRAINING_PHILOSOPHY Part 2 | Never 3 quality sessions in one week. Max 2 Level 4+ sessions. | hard | |
| WS-2 | 04_RECOVERY §3.1 | Saturday before Sunday long run is ALWAYS easy. Never medium-long, never quality. | hard | |
| WS-3 | 04_RECOVERY §3.2 | MP long run weeks: no threshold work that week. Exception: 70+ mpw with explicit recovery. | hard | |
| WS-4 | 04_RECOVERY §3.3 | Threshold weeks: long run is easy (no MP/HMP segments). | hard | |
| WS-5 | 04_RECOVERY §5 | Structure A (quality midweek + easy long) and Structure B (easy week + MP long) must alternate in build/peak. | soft | |
| WS-6 | 03_WORKOUT_TYPES §1 | Level 4+ session requires at least 1 Level ≤2 day before next Level 4+. | hard | |
| WS-7 | 03_WORKOUT_TYPES §1 | Level 5 (MP long, race) requires at least 2 Level ≤2 days before next Level 4+. | hard | |
| WS-8 | TRAINING_PHILOSOPHY Part 2 | 5 weeks of combined T + MP work is the ceiling before mandatory cutback. | soft | |

---

## Category 3: Volume Rules

| ID | Source | Rule | Check | Founder Notes |
|----|--------|------|-------|---------------|
| VR-1 | 03_WORKOUT_TYPES §2c | First long run of plan = L30_non_race_max + 1 mile. Races excluded from L30 computation. | hard | |
| VR-2 | 03_WORKOUT_TYPES §2c | Long run build: +2mi/week (non-cutback). +3 for experienced with strong history. | soft | |
| VR-3 | 03_WORKOUT_TYPES §2c | Long run cutback: 60-70% of prior week's long run. | hard | |
| VR-4 | N1_PLAN_ENGINE_SPEC §3 | Long run ceiling: Marathon 22mi (24 elite). Half 16-18mi. 10K 18mi. 5K 15mi. | hard | |
| VR-5 | N1_PLAN_ENGINE_SPEC §3 | Marathon sub-3:45 target: max long run 20mi. | hard | |
| VR-6 | N1_PLAN_ENGINE_SPEC §3 | Marathon long runs do not begin below 14mi. Below that is not a long run for marathon volume. | hard | |
| VR-7 | N1_PLAN_ENGINE_SPEC §3 | Long run must be meaningfully above daily average. No 10mi "long" at 55mpw. | hard | |
| VR-8 | 03_WORKOUT_TYPES §3 | Medium-long = 65-75% of same week's long run. Hard cap 15mi. Never above 15. | hard | |
| VR-9 | 03_WORKOUT_TYPES §3 | Medium-long never day before long run. Best separated by 3+ days. | hard | |
| VR-10 | 03_WORKOUT_TYPES §3 | Medium-long for athletes under 40mpw: optional. 40-60mpw: useful anchor. 60+: structural. | soft | |
| VR-11 | 04_RECOVERY §6 | Cutback frequency: every 4th week (general), every 3rd (masters/injury), at phase boundaries. | soft | |
| VR-12 | 04_RECOVERY §6 | Cutback volume: 60-70% of prior week. | hard | |
| VR-13 | 04_RECOVERY §6 | Cutback long run: 60-70% of prior week's long run. | hard | |
| VR-14 | N1_PLAN_ENGINE_SPEC §3 | Volume curve starts at current_weekly_miles (not population default). | hard | |
| VR-15 | 03_WORKOUT_TYPES §2c | Long run ≤ 32% of that week's total mileage (may be overridden by L30 history floor). | soft | |

---

## Category 4: Session Sizing Rules (KB B1)

| ID | Source | Rule | Check | Founder Notes |
|----|--------|------|-------|---------------|
| SS-1 | PLAN_GENERATION_FRAMEWORK B1, 03_WORKOUT_TYPES §7 | Threshold session ≤ 10% of weekly volume. | hard | |
| SS-2 | PLAN_GENERATION_FRAMEWORK B1, 03_WORKOUT_TYPES §7 | Interval session ≤ 8% of weekly volume or 10K distance, whichever is less. | hard | |
| SS-3 | PLAN_GENERATION_FRAMEWORK B1, 03_WORKOUT_TYPES §7 | Repetition session ≤ 5% of weekly volume or 5mi, whichever is less. | hard | |
| SS-4 | PLAN_GENERATION_FRAMEWORK B1, 03_WORKOUT_TYPES §7 | MP in long run ≤ 20% of weekly volume or 18mi, whichever is less. | hard | |
| SS-5 | PLAN_GENERATION_FRAMEWORK B2, TRAINING_PHILOSOPHY Part 1 | Easy running ≥ 70% of weekly volume. (65-80% range.) | hard | |

---

## Category 5: Threshold Progression Rules

| ID | Source | Rule | Check | Founder Notes |
|----|--------|------|-------|---------------|
| TP-1 | PLAN_GENERATION_FRAMEWORK T-block, TRAINING_PHILOSOPHY Part 3 | T-block shows week-over-week progression (intervals → longer intervals → continuous for marathon only). | hard | |
| TP-2 | PLAN_GENERATION_FRAMEWORK Step 4 | T-block scaling: Low tier → 4x4min to 2x12min. Mid tier → 5x5min to 25min continuous. High tier → 6x5min to 40min continuous. | hard | |
| TP-3 | TRAINING_PHILOSOPHY Part 7 | A 40mpw runner should NOT do 40min continuous threshold. | hard | |
| TP-4 | Founder instruction (this session) | 5K/10K: cruise intervals only, never continuous threshold. | hard | |
| TP-5 | Founder instruction (this session) | Half marathon: continuous threshold capped at 25min. | hard | |
| TP-6 | Founder instruction (this session) | Marathon: continuous threshold capped at 40min. | hard | |

---

## Category 6: Interval and Repetition Rules

| ID | Source | Rule | Check | Founder Notes |
|----|--------|------|-------|---------------|
| IR-1 | PLAN_GENERATION_FRAMEWORK M2/M3, 04_RECOVERY §3.5, TRAINING_PHILOSOPHY Part 3 | Intervals are safe in base phase (fresh legs). Risky in mid-build (high cumulative fatigue). | soft | |
| IR-2 | 03_WORKOUT_TYPES §6 | Athlete at 65+ mpw with 3 weeks of MP work should NOT add interval sessions. | soft | |
| IR-3 | N1_PLAN_ENGINE_SPEC §4 | For advanced 5K: 200m and 300m REPS at 1500m pace during build. Uses `repetitions` stem. | soft | |
| IR-4 | Founder instruction | Repeat = full rest recovery. Interval = float/jog recovery. Distinct pace assignments from RPI. | hard | |

---

## Category 7: Recovery and Spacing Rules

| ID | Source | Rule | Check | Founder Notes |
|----|--------|------|-------|---------------|
| RC-1 | 04_RECOVERY §2 | After threshold: minimum 1 easy day before next Level 4+. | hard | |
| RC-2 | 04_RECOVERY §2 | After intervals: 1-2 easy days before next Level 4+ (N=1; more for masters/high fatigue). | hard | |
| RC-3 | 04_RECOVERY §2 | After MP long run: 2 easy days minimum. | hard | |
| RC-4 | 04_RECOVERY §2 | After race: 3-7 easy days (N=1 by distance). | hard | |
| RC-5 | 04_RECOVERY §4 | Post-quality easy day volume multiplier: 0.7x. Pre-long-run easy day: 0.8x. Both: 0.56x. | soft | |
| RC-6 | 04_RECOVERY §7 | When cumulative fatigue is high (mid-build, 60+ mpw, MP stacked): suppress intervals, favor threshold and easy volume. | soft | |

---

## Category 8: Marathon-Specific Rules

| ID | Source | Rule | Check | Founder Notes |
|----|--------|------|-------|---------------|
| MA-1 | PLAN_GENERATION_FRAMEWORK Part 2 | MP progression: no MP in base. Start 4mi in build. Progress to 6-8mi. Dress rehearsal 8-14mi. | hard | |
| MA-2 | PLAN_GENERATION_FRAMEWORK Part 2 | Total cumulative MP ≥ 40mi before taper. | hard | |
| MA-3 | PLAN_GENERATION_FRAMEWORK ARCH-3 | MP work inside medium-long on specific weeks (not just long run). | soft | |
| MA-4 | N1_PLAN_ENGINE_SPEC §2 | Marathon readiness gate: must be able to do 12mi run before starting. | hard | |
| MA-5 | N1_PLAN_ENGINE_SPEC §3 | Marathon long runs do not begin below 14mi. | hard | |
| MA-6 | 04_RECOVERY §5 | Structure A/B alternation: MP-long weeks get easy Thursday, easy medium-long. | soft | |

---

## Category 9: Distance-Specific Quality Rules

| ID | Source | Rule | Check | Founder Notes |
|----|--------|------|-------|---------------|
| DQ-1 | N1_PLAN_ENGINE_SPEC §4 | 5K: VO2 intervals primary (400m → 800m → 1000m). Threshold secondary. | hard | |
| DQ-2 | N1_PLAN_ENGINE_SPEC §4 | 5K advanced: 200m/300m reps at 1500m pace during build (ceiling work). | soft | |
| DQ-3 | N1_PLAN_ENGINE_SPEC §4 | 10K: Threshold primary. VO2 secondary (ceiling raiser). | hard | |
| DQ-4 | N1_PLAN_ENGINE_SPEC §4 | 10K: 5K tune-up IS the peak VO2 stimulus. | soft | |
| DQ-5 | N1_PLAN_ENGINE_SPEC §4 | Half: T-block → HMP in long runs → HMP finish dress rehearsal. | hard | |
| DQ-6 | N1_PLAN_ENGINE_SPEC §4 | Marathon: T-base → MP accumulation → race simulation. | hard | |

---

## Category 10: Readiness and Safety Gates

| ID | Source | Rule | Check | Founder Notes |
|----|--------|------|-------|---------------|
| RG-1 | N1_PLAN_ENGINE_SPEC §2 | Marathon: refuse if athlete cannot do 12mi run before starting. Offer base-building instead. | hard | |
| RG-2 | N1_PLAN_ENGINE_SPEC §2 | Half: must be able to reach 12mi long run within available weeks or refuse. | hard | |
| RG-3 | N1_PLAN_ENGINE_SPEC §7 | Day-one (never ran): walk/run Couch-to-10K progression, not a race plan. | hard | |
| RG-4 | TRAINING_METHODOLOGY 4.1 | Beginner (<2 years): minimal intensity, conservative progression. | hard | |
| RG-5 | TRAINING_METHODOLOGY 4.1 | MP long runs gated on experience ≥ INTERMEDIATE and weekly_miles ≥ 40. | hard | |

---

## Category 11: Pace and Prescription Rules

| ID | Source | Rule | Check | Founder Notes |
|----|--------|------|-------|---------------|
| PP-1 | 01_INTENSITY_PHILOSOPHY | Never expose zone numbers to athletes. Use effort descriptions and workout types. | hard | |
| PP-2 | Founder instruction | Repeat pace ≠ interval pace. Separate pace zones from RPI. | hard | |
| PP-3 | TRAINING_METHODOLOGY 7.2 | If no RPI/race data: effort descriptions only. Never prescribe numeric paces without data. | hard | |
| PP-4 | TRAINING_METHODOLOGY 3.1 | Threshold duration: 20-40min continuous OR intervals. | hard | |

---

## Category 12: Easy Day and Strides Rules

| ID | Source | Rule | Check | Founder Notes |
|----|--------|------|-------|---------------|
| ED-1 | 03_WORKOUT_TYPES §4 | Weekly stimulus ledger: a system already heavily loaded must NOT also get a neuromuscular touch on easy days that week. | soft | |
| ED-2 | 03_WORKOUT_TYPES §1 | Level 2.5 (strides/hills) does NOT count as a quality day. | hard | |
| ED-3 | TRAINING_PHILOSOPHY Pillar 1 | Easy must be easy. 80% of running at conversational effort. | hard | |
| ED-4 | Founder instruction | Post-quality easy day should not exceed ~8mi (not carry overflow volume from quality sessions). | hard | |

---

## Category 13: Taper Rules

| ID | Source | Rule | Check | Founder Notes |
|----|--------|------|-------|---------------|
| TA-1 | PLAN_GENERATION_FRAMEWORK A5, TRAINING_PHILOSOPHY Part 2 | Marathon taper: ~3 weeks. | soft | |
| TA-2 | N1_PLAN_ENGINE_SPEC §3 | Taper volume reduction: -30% first week, -50% second, race week minimal. | hard | |
| TA-3 | Founder instruction | Taper is athlete-selectable: auto, 1_week, 2_week, 3_week. | hard | |
| TA-4 | Founder instruction | Tune-up race: mini-taper before tune-up, hard taper into goal race. No fitness added in final 14 days. | hard | |
| TA-5 | PLAN_GENERATION_FRAMEWORK Part 4 | Strides maintained throughout taper for neuromuscular activation. | hard | |

---

## Category 14: N=1 Override Rules

| ID | Source | Rule | Check | Founder Notes |
|----|--------|------|-------|---------------|
| N1-1 | PLAN_GENERATION_FRAMEWORK 7.4 | L30_max overrides LONG_RUN_PEAKS table. Runner who regularly does 18mi long runs does not get 14mi cap. | hard | |
| N1-2 | PLAN_GENERATION_FRAMEWORK 7.4 | current_weekly_miles is the baseline, not tier_params.min_weekly_miles. | hard | |
| N1-3 | PLAN_GENERATION_FRAMEWORK 7.4 | days_per_week respected absolutely. Never generate more running days than requested. | hard | |
| N1-4 | 00_GOVERNING_PRINCIPLE | When book principle conflicts with individual data, individual data wins. | soft | |
| N1-5 | TRAINING_METHODOLOGY 4.2 | Age informs initial assumptions ONLY if no other data exists. Individual data overrides. | soft | |

---

**Total rules extracted: 76**

**Next step:** Founder reviews this registry, adds notations and exceptions. Then each `hard` rule becomes an automated evaluator check. Each `soft` rule becomes a check with documented override conditions.
