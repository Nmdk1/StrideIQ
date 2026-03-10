# Advisor Handoff — March 8, 2026

**From:** Technical & ROI Advisor (Opus, ~6-day session)
**To:** New Technical & ROI Advisor
**Founder:** Michael Shaffer (mbshaf@gmail.com) — competitive masters runner (57), coaches his father Larry (79). Both set state age group records on March 8, 2026.

---

## Your Role

You are a **technical advisor and ROI guardian** for a solo founder building StrideIQ. You do not write code unless explicitly asked. Your primary output is findings, not summaries. Your default posture is skeptical, evidence-first, production-aware.

**What the founder expects from you:**
- Deep research before opinions. Read the code. Check production. Verify claims.
- Candid pushback. The founder wants a thinking partner, not an approval machine.
- ROI framing. Every recommendation should answer: what's the smallest change that solves the real problem?
- Evidence over assertions. "Show me the proof" is the standard.
- Suppression over hallucination. If you're unsure, say so. Silence beats a confident wrong answer.

**What will get you replaced immediately:**
- Rubber-stamping without verification. The founder has fired advisors for this.
- Agreeing blindly. "Sounds great!" without checking anything costs trust.
- Starting to code when asked to discuss.
- Template language, filler, fluff. Be direct.
- Long context degradation — losing track of prior decisions and repeating analysis. If your context is degraded, say so honestly.

---

## Read Order (Non-Negotiable — Do This First)

1. **`docs/FOUNDER_OPERATING_CONTRACT.md`** — How to work with this founder. Every rule is a bright line. Read every word. (495 lines)
2. **`docs/PRODUCT_MANIFESTO.md`** — The soul of the product. What StrideIQ IS. (80 lines)
3. **`docs/PRODUCT_STRATEGY_2026-03-03.md`** — The moat. Why the correlation engine is the root of everything. (213 lines)
4. **`docs/specs/CORRELATION_ENGINE_ROADMAP.md`** — 12-layer engine roadmap
5. **`docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md`** — How every screen should feel. Includes rejected decisions (Part 4) — do NOT re-propose them. (401 lines)
6. **`docs/RUN_SHAPE_VISION.md`** — Visual vision for run data
7. **`docs/SITE_AUDIT_LIVING.md`** — Honest assessment of current state
8. **`docs/specs/LIVING_FINGERPRINT_SPEC.md`** — The core intelligence architecture. (~985 lines)
9. **`docs/specs/SHAPE_SENTENCE_SPEC.md`** — Current active build spec
10. **This document** — Current state and priorities

---

## What StrideIQ Is (30-Second Version)

A running intelligence platform that gives an athlete's body a voice. Unlike Strava (social), Garmin (dashboards), or Runna (plans), StrideIQ builds a personal physiological model from YOUR data — correlations, adaptation patterns, recovery fingerprints — that compounds over time. After 6 months, leaving means losing your personal sports science journal. The system has 111 services, 150+ intelligence tools, and 1,878 tests. The intelligence exists. The challenge now is making it speak — in sentences a runner would say, not observations a database would produce.

**The sentence is the product.** Not charts. Not metrics. The sentence.

---

## Architecture Overview

### Stack
- **API:** FastAPI + SQLAlchemy + PostgreSQL
- **Worker:** Celery + Redis (background processing)
- **Web:** Next.js 14 (App Router) + TanStack Query v5
- **Storage:** MinIO (S3-compatible, photos/runtoon images)
- **Proxy:** Caddy (auto-TLS, reverse proxy)
- **AI:** Gemini API (coach, runtoon), deterministic algorithms (all intelligence)
- **CI:** GitHub Actions (8 jobs: frontend build, backend tests, jest, migration integrity, smoke tests, security scan, lint, docker build)

### Production
- **Server:** root@187.124.67.153 (Hostinger KVM 8 — 8 vCPU, 32GB RAM)
- **Repo:** /opt/strideiq/repo
- **Domain:** https://strideiq.run
- **Containers:** strideiq_api, strideiq_web, strideiq_worker, strideiq_postgres, strideiq_redis, strideiq_caddy, strideiq_minio

### Deploy
```bash
ssh root@187.124.67.153
cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build
docker logs strideiq_api --tail=50
```

---

## The Living Fingerprint (Core Intelligence Architecture)

This is the most important technical concept in the system. Three layers:

### Layer 1: Signal Ingestion (Pluggable Adapters)
External data sources → internal signal types. Currently: Strava, Garmin, Open-Meteo. Future: WHOOP, Oura, CGMs. Each adapter implements `ingest(raw_data) -> List[Signal]`. Adding a new source means writing one adapter.

### Layer 2: The Living Fingerprint (Persistent, Incremental)
Per-athlete accumulated intelligence. Not a snapshot — a timeline. Implemented as a view layer over existing PostgreSQL models:
- `Activity.run_shape` (JSONB) — structured shape of every run
- `Activity.dew_point_f`, `Activity.heat_adjustment_pct` — weather normalization
- `Activity.shape_sentence` (Text) — natural language description
- `AthleteFinding` table — persistent findings with supersession logic
- Derived metrics computed from signals, updated incrementally

### Layer 3: Intelligence Engine (Registry-Based Investigations)
15 registered investigations, each with declared signal requirements and minimum data gates. Decorator-based: `@investigation(requires=['activity_stream'], min_activities=10)`. Auto-enables when data arrives. Honest gaps reported when data is insufficient.

**Key services:**
- `apps/api/services/shape_extractor.py` — 7-step algorithm: smooth → transitions → merge → classify phases → detect accelerations → summary → classification. 1,331 lines of pure computation.
- `apps/api/services/heat_adjustment.py` — Magnus formula dew point + combined value model
- `apps/api/services/race_input_analysis.py` — Investigation registry + 15 investigations
- `apps/api/services/finding_persistence.py` — CRUD for AthleteFinding with supersession
- `apps/api/services/training_story_engine.py` — Synthesis layer (race stories, progressions, connections)

**Pipeline:** Every activity sync → shape extraction → weather normalization → findings update (background worker, not API request). Daily refresh at 06:00 UTC via Celery beat.

---

## Current State (March 8, 2026)

### What's Deployed and Working

| System | Status | Notes |
|--------|--------|-------|
| Living Fingerprint | DEPLOYED | 4 capabilities: weather normalization, shape extraction, investigation registry, shape-aware investigations |
| Shape Sentences | DEPLOYED | Discrete zone model, sentence generator, wired to yesterday's insight + coach briefing + API responses |
| Racing Fingerprint | DEPLOYED | Phase 1A (PerformanceEvent pipeline), 1B (pattern extraction + quality gate), 1C (data integrity + campaign detection) |
| pSEO Pages | DEPLOYED | 160 URLs in sitemap. Internal linking fix deployed today (commit `4929759`) — 137 orphaned pages now linked from hub pages |
| CI | GREEN | 8 jobs, all passing |
| Production | HEALTHY | 7 containers up |

### Git State
- **Branch:** main
- **Latest commit:** `4929759` (SEO internal linking fix)
- **Migration head:** `lfp_005_sentence`
- **Tracked changes:** 4 modified docs (pre-existing, not from current work)
- **Untracked:** ~50 debug/analysis scripts in `scripts/` (temporary, safe to ignore or delete)

### Alembic Migration Chain
```
... → phase1c_001 → lfp_001_heat → lfp_002_shape → lfp_003_registry → lfp_004_layer → lfp_005_sentence
```
CI enforces single-head integrity. Current expected head: `lfp_005_sentence`.

---

## Shape Sentence Build — Current Status (Active Work)

This is the active build. A builder (separate agent) has been implementing `docs/specs/SHAPE_SENTENCE_SPEC.md`. Here is the verified state:

### What Was Built
- Discrete zone model with non-overlapping bands, easy-no-floor, gray areas, walking boundary
- Removed stream-relative fallback (no more fake zones from GPS noise — this was creating 48-113 phases for steady easy runs)
- Aggressive phase consolidation (64 phases → 1-2 for easy runs)
- Natural language sentence generator from RunShape data
- `shape_sentence` column + migration on Activity (`lfp_005_sentence`)
- Wired into yesterday's insight, coach briefing context, and API responses
- Classification ordering: progression before strides, long_run before fartlek

### 14-Activity Verification Table Results (7 PASS / 5 CLOSE / 2 FAIL)

| Date | Athlete | Expected | System Output | Status |
|------|---------|----------|---------------|--------|
| Mar 05 | Michael | strides (6:02) | strides (6:02) | PASS |
| Mar 04 | Michael | progression 8:12→7:15 | strides (6:51) | CLOSE — genuinely ambiguous, has both patterns |
| Mar 03 | Michael | easy at 8:30 | easy at 8:54 | PASS |
| Mar 01 | Michael | easy at 9:15 | easy at 9:25 | PASS |
| Feb 28 | Michael | 13mi long run | 13mi easy at 7:35 | CLOSE — 13mi under 2× median distance threshold |
| Feb 27 | Michael | building 9:20→8:00 | building 9:08→8:05 | PASS (was FAIL) |
| Mar 05 | Larry | 1mi easy | building 13:00→12:11 | CLOSE — short run settling |
| Mar 03 | Larry | 2.5mi strides | strides (7:57) | PASS |
| Mar 01 | Larry | 4mi easy | medium-long at 14:51 | CLOSE — duration rule |
| Feb 28 | Larry | 2mi easy | easy at 14:35 | PASS |
| Mar 05 | BHL | 5mi tempo (7:30-8:00) | building 9:29→8:01 | IMPROVED (was fartlek) |
| Feb 28 | BHL | 18mi long run | 18.5mi long run 8:52 | PASS (was fartlek) |
| Feb 18 | BHL | 5mi hill repeats | fartlek 7 surges | CLOSE — needs elevation data |
| Feb 16 | BHL | building 8:30→7:10 | fartlek 7 surges | FAIL |

### Root Cause of 2 Failures
Both are BHL-specific. BHL runs on hilly terrain. Terrain-driven pace variations create scattered accelerations that trigger fartlek classification. The infrastructure exists (`_compute_elevation_profile` returns 'hilly') but it's not wired into the fartlek/progression decision logic yet.

### What's NOT Done Yet
1. **Front-end surfacing** — shape sentences exist in the API but the activity list and activity detail UI don't show them. The athlete sees "Morning Run" instead of "7 miles easy with 4 strides."
2. **Elevation-aware fartlek guard** — would fix BHL's 2 failures by distinguishing terrain pace variation from intentional surges
3. **Tempo detection at marathon pace** — zone model only recognizes tempo at threshold pace, but marathon-pace tempo runs are a real pattern
4. **Gray zone intelligence** (Part 6 of spec) — cost/gain analysis for activities between named zones

### Open Question for the New Advisor
The 2 FAIL activities — are the wrong sentences being **served** (trust-breaking) or **suppressed** (falling back to original activity name)? This matters for prioritization. If wrong sentences are visible, that's urgent. If they're suppressed, it's an honest gap that can wait.

---

## Three Athletes in the System

| Athlete | Description | Key Facts |
|---------|-------------|-----------|
| **Michael** (founder) | 57yo competitive masters runner. Imperial units. | Sub-1:28 half, sub-40 10K. 70mpw peak. Broke femur Nov 2025. Rebuilding. State records Mar 8 2026. |
| **Larry** (founder's father) | 79yo masters runner. | Strides are subtle (slow velocity, need cadence channel). Set state record Mar 8 2026. |
| **BHL** | Competitive runner, hilly terrain. | Pace variations from hills confuse fartlek detection. Tempo runs at marathon pace. |

---

## Key Specs (Organized by Status)

| Spec | Status | Purpose |
|------|--------|---------|
| `LIVING_FINGERPRINT_SPEC.md` | BUILT | Core intelligence architecture — 4 capabilities |
| `SHAPE_SENTENCE_SPEC.md` | IN PROGRESS | Zone model fix, sentence generation, coaching surface wiring |
| `CAMPAIGN_DETECTION_AND_DATA_INTEGRITY_SPEC.md` | SPECCED, NOT BUILT | Multi-month training arc detection. Would find the founder's 6-month long run campaign that the system trivialized as "16 vs 14 miles." |
| `RACE_INPUT_MINING_SPEC.md` | SPECCED, NOT BUILT | Mining training inputs for race performance |
| `RACING_FINGERPRINT_AND_PROGRESS_STATE_MACHINE_SPEC.md` | PRODUCT SPEC | Product design doc (WHAT and WHY). Phase 1 complete. |
| `RACING_FINGERPRINT_PHASE1_BUILD_SPEC.md` | COMPLETE | Phase 1A, 1B, 1C all built and deployed |
| `CORRELATION_ENGINE_ROADMAP.md` | REFERENCE | 12-layer engine roadmap |
| `CORRELATION_ENGINE_LAYERS_1_4_SPEC.md` | SPECCED, NOT BUILT | Threshold detection, asymmetric response, cascade, decay |

---

## Priority Candidates (Founder's Decision)

These are the items the founder has identified. You advise on priority. The founder decides.

1. **Front-end surfacing of shape sentences** — activity list + detail pages. The intelligence is computed and stored. Nobody can see it. Highest ROI to make the feature visible.

2. **Elevation-aware fartlek guard** — fixes 2/14 verification failures, both for one athlete (BHL). Prevents misclassification for any hilly runner. Infrastructure exists, needs wiring.

3. **Campaign Detection** (spec exists) — would detect multi-month training arcs like the founder's 6-month long run campaign. The system's current finding was "your best races had 16-mile long runs vs 14." The founder called it "pretty fucking lame." The real story was 6 months of deliberate base building that produced consecutive PBs at every distance.

4. **Training Story front-end** — the backend synthesis engine exists (`training_story_engine.py`). The Progress page is a text card wall. The founder called this a "marquee product."

5. **Correlation Engine Layers 1-4** — threshold detection, asymmetric response, cascade detection, decay curves. The spec exists. This is the scientific instrument at the heart of the product.

---

## Process Rules You Must Follow

1. **Read `docs/FOUNDER_OPERATING_CONTRACT.md` before your first tool call.** Non-negotiable.
2. **Do not start coding when given a new feature.** Discuss → scope → plan → test design → build.
3. **Show evidence, not claims.** Paste test output. Paste deploy logs. Paste git diff.
4. **CI First, Local Second.** (Rule 10) Check CI before running tests locally.
5. **Scoped commits only.** Never `git add -A`.
6. **No acronyms in athlete-facing text.** A coach says "your fitness" not "your CTL."
7. **Suppression over hallucination.** If uncertain, say nothing.
8. **Tree clean, tests green, production healthy** at end of every session.

---

## How the Founder Communicates

- **Short messages carry full weight.** "discuss" means deep discussion. "go" means full green light. "no code" means absolutely no code.
- **They will challenge you.** This is not hostility — they're testing your reasoning. Engage honestly.
- **They have deep domain expertise.** Decades of competitive running, coaching, and building products. If they say your running logic is wrong, it's wrong.
- **They value directness.** "I disagree because..." is what they want. "Whatever you think" gets you replaced.
- **They will call out blind agreement.** If you approve something without checking, they'll notice. Multiple advisors have been called out for this. Don't be the next one.

---

## Known Pitfalls from This Session

1. **Context degradation.** After long sessions, advisors start pattern-matching instead of doing the work. The founder will catch this. If your context is overloaded, say so honestly and re-read source documents.

2. **Rubber-stamping builder reports.** When a builder presents a status report, verify the claims. Read the actual code. Check production. Don't just say "ship the front-end next" without confirming the backend claims are true.

3. **PowerShell syntax.** The founder's machine runs PowerShell, not bash. `&&` doesn't work. Heredocs don't work. Use `;` or separate commands.

4. **The old DigitalOcean droplet** (root@104.248.212.71) is pending decommissioning. DNS is already pointed to the Hostinger server. The founder planned to terminate it — verify DNS is clean before confirming.

---

## Immediate Next Steps

1. Read the full read order (documents 1-10 above).
2. The founder will set the priority. Ask if unclear.
3. If asked to review builder work, actually verify: read the code, check production, test the claims.
4. If asked about the Shape Sentence spec remaining items, the key question is whether the 2 BHL failures produce wrong visible sentences or are properly suppressed.

---

*This handoff was written by the outgoing advisor on March 8, 2026. The founder explicitly requested it be "very very comprehensive" because context degradation had reduced advisor quality.*
