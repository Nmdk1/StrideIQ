# Northstar Review Checklist — PLAN_GENERATION_VISION_ALIGNMENT_RECOVERY_SPEC

## A) Problem framing
- [ ] Confirmed this is architecture/control-flow risk (not single tuning bug)
- [ ] Confirmed cross-distance exposure (5k/10k/10mile/half/marathon)

## B) Recovery contracts (must all pass)
- [ ] C1 Athlete intent preserved through fallback/regeneration
- [ ] C2 Personal long-run floor enforced at final gate for high-data athletes
- [ ] C3 Distance-appropriate workout mix + variant competency
- [ ] C4 Real cutback enforcement (volume + long + quality all reduced)
- [ ] C5 Prediction contract preserved (all required fields unchanged)

## C) P0 implementation scope
- [ ] P0-A fallback intent preservation implemented
- [ ] P0-B distance-aware gate correction implemented
- [ ] P0-C high-data long-run floor protection implemented
- [ ] P0-D endpoint-level cohort validator implemented (includes fallback branch)

## D) CI-gated test matrix
- [ ] override preserved on fallback
- [ ] high-data 10k long-run floor not breached
- [ ] valid high-mileage 10k not false-flagged
- [ ] marathon valid progression not hit by 10k artifacts
- [ ] half mix remains threshold+MP
- [ ] cutback is real reduction
- [ ] prediction contract unchanged
- [ ] hard-block path tested for invariant conflict
- [ ] personal-floor formula test added
- [ ] fail-closed payload contract shape tested

## E) Acceptance check (release gate)
- [ ] founder-like 10k sample passes all structural checks
- [ ] non-10k cohorts pass distance-specific checks
- [ ] fallback never mutates explicit athlete intent silently
- [ ] production cohort samples captured and reviewed

## F) Evidence completeness
- [ ] commit SHA + file list
- [ ] full test output pasted
- [ ] before/after matrix (volume, long-run sequence, mix/variants, volume contract, fallback metadata)
- [ ] CI URL green
- [ ] production payload samples for 10k/half/marathon/cold-start
