# Architectural Decisions

## Current State

56 ADRs in `docs/adr/` plus 4 root-level ADR files. ADRs are point-in-time decisions; later code/specs may override behavior without deleting ADRs. This page summarizes the most impactful decisions that shape current architecture.

## Key Decisions (Current Impact)

### Model & Intelligence

| ADR | Decision | Current state |
|-----|----------|---------------|
| ADR-060 | Coach LLM tiering (GPT-based) | **Superseded** — universal Kimi K2.5 routing (Apr 6, 2026) |
| ADR-061 | Athlete Plan Profile — N=1 overrides | Active — `AthleteOverride`, `AthleteLearning` models |
| ADR-062 | Taper democratization — personalized taper | Active — taper calculator uses individual data |
| COACH_MODEL_ROUTING_RESET_SPEC | Sonnet premium lane, remove Opus runtime | **Superseded** — Kimi K2.5 for all (Apr 6, 2026) |

### Planning & Training

| ADR | Decision | Current state |
|-----|----------|---------------|
| N1_ENGINE_ADR_V2 | Diagnosis-first plan engine, 12 blocking criteria, 14 archetypes | Active — `n1_engine.py` rebuilt Mar 29 |
| Plan generation comprehensive path | Phases 0-6 + waivers, strict matrix | Active — governs plan generation |
| Workout fluency registry | JSON-based variant registry, P0 gate | Active — 38 approved variants |

### Data & Integration

| ADR | Decision | Current state |
|-----|----------|---------------|
| ADR-052 (a) | API versioned routing (`/v1/`) | Active |
| ADR-052 (b) | Signed OAuth state + latency bridge | Active |
| Activity stream | Stream-based analysis architecture | Active — `ActivityStream`, `CachedStreamAnalysis` |
| Effort classification | 3-tier classification without max_hr gate | Active |

### Infrastructure

| ADR | Decision | Current state |
|-----|----------|---------------|
| Home briefing off-path | Lane 2A: briefing never blocks request | Active — critical architecture |
| Correlation wiring (ADR-045-A) | Amendment to correlation input registration | Active |

### Trust & Quality

| ADR | Decision | Current state |
|-----|----------|---------------|
| OutputMetricMeta | Directional whitelist for metric claims | Active — fail-closed |
| KB Rule Registry | 76 annotated rules, evaluator gates | Active — 445 PASS / 0 FAIL |
| Athlete Trust Safety Contract | In `n1_insight_generator.py` | Active |

## Duplicate Numbering

**ADR-052** has two files with different topics:
- `ADR-052-API-VERSIONED-ROUTING.md`
- `ADR-052-signed-oauth-state-and-latency-bridge-onboarding.md`

## Missing References

- `BUILDER_INSTRUCTIONS_2026-03-20_PLAN_QUALITY_RECOVERY_V2.md` is referenced by `BUILDER_INSTRUCTIONS_2026-03-23_PLAN_INTEGRITY_SYSTEMIC_RECOVERY.md` but does not exist in the repo

## Sources

- `docs/adr/` — 56 ADR files
- `docs/ADR_060_COACH_LLM_TIERING.md` — root-level
- `docs/ADR_061_ATHLETE_PLAN_PROFILE.md` — root-level
- `docs/ADR_062_TAPER_DEMOCRATIZATION.md` — root-level
- `docs/specs/N1_ENGINE_ADR_V2.md` — plan engine rebuild
