# ADR 16: Coach Context Architecture — Pre-Computed Brief + Proactive Insights

**Status:** Proposed  
**Date:** 2026-02-07  
**Author:** AI Assistant  
**Trigger:** Full Rigor — touches N=1 core, AI coaching engine, user-facing behavior  

---

## Context

The AI coach is the central product of StrideIQ. The athlete's entire experience is meant to be a conversation with a coach who knows them — their data, their patterns, their goals. The manifesto describes a "silent, brilliant assistant" that the athlete speaks through, backed by an Athlete Intelligence Bank of N-of-1 insights.

**What was built:** A comprehensive analytics backend — correlation engine, training load calculator, VDOT/RPI model, efficiency analytics, durability indexing, race predictor, 22 coach tools, 1,393+ passing tests.

**What went wrong:** The LLM (Gemini 2.5 Flash) was placed *in front of* the intelligence instead of *behind it*. Gemini receives a thin ~800-token athlete state and 22 tool declarations, then decides what to call, interprets raw JSON, does its own math, and tries to coach. It fails at every step:

| Observed Failure | Root Cause |
|-----------------|------------|
| Got athlete's age wrong (58 vs 57) | Gemini guessed instead of calling `get_athlete_profile` |
| Wrong BQ qualifying time (3:35 vs 3:30) | No BQ lookup exists anywhere — Gemini hallucinates from training data |
| Wrong pace math (7:15/mi = "3:23" instead of 3:09:56) | No pace-to-finish calculator tool — Gemini does arithmetic badly |
| Hallucinated "100+ mile weeks" | Gemini fabricated data instead of using tool results |
| Treated partial week as complete | Fixed (is_current_week flag added), but symptomatic of deeper issue |
| Identical canned response twice | Guardrail bypassed LLM entirely with hardcoded text |
| Never surfaced N-of-1 correlations | Gemini never proactively calls correlation engine |
| Over-apologized, lost conversational thread | System prompt focused on defensive rules, not coaching persona |
| Responses cut off mid-sentence | Fixed (500 → 1500 tokens), but symptomatic of band-aid approach |

**Business impact:** Beta users have abandoned the product. $1,300+ in tokens spent. Founder considering shutting down the project.

---

## Decision

**Replace the current "thin state + tool-dependent LLM" architecture with a "rich pre-computed brief + proactive insights + smart tool outputs" architecture.**

### Principle

> The coach reviews the athlete's complete file before every conversation. The LLM's job is to communicate and coach — never to compute, look up, or guess.

### Architecture: Three Layers

```
┌─────────────────────────────────────────────────┐
│  LAYER 1: PRE-COMPUTED ATHLETE BRIEF            │
│  Python calls all services, computes all facts,  │
│  surfaces top N-of-1 insights.                   │
│  Injected as system context every message.       │
│  ~3,000-4,000 tokens.                            │
├─────────────────────────────────────────────────┤
│  LAYER 2: SMART TOOLS (all 22 remain callable)  │
│  For mid-conversation deep dives the brief       │
│  doesn't cover. Tool outputs return interpreted  │
│  narrative + key numbers, not raw JSON.          │
├─────────────────────────────────────────────────┤
│  LAYER 3: LLM AS COACH                          │
│  Reads brief. Leads with what matters.           │
│  Answers questions from facts. Calls tools for   │
│  specific deep dives. Never does math. Never     │
│  guesses at data.                                │
└─────────────────────────────────────────────────┘
```

---

## Layer 1: The Athlete Brief

Built by a new function `build_athlete_brief(athlete_id, db)` that calls existing services and returns a structured, human-readable document. Computed fresh on every incoming message (~500-1000ms, parallelized).

### Brief Contents

| Section | Source Service | What's Included |
|---------|---------------|-----------------|
| **Identity** | `get_athlete_profile` | Name, age (pre-calculated), sex |
| **Goal Race** | `get_plan_week` + new fields | Race name, date, distance, target finish time (from athlete's `goal_time_seconds`), days until race, gap between predicted time and goal |
| **Training State** | `get_training_load` | Fitness (CTL), fatigue (ATL), form (TSB), durability index, injury risk, recovery status — all in plain English labels |
| **Volume Trajectory** | `get_weekly_volume` | Last 8 weeks with trend narrative ("36→45→50mi, +39% over 3 weeks"), current week marked partial, comparison to peak volume |
| **Recent Runs** | `get_recent_runs` | Last 7-14 days, pre-formatted with pace, HR, type classification, notable observations |
| **Race Predictions** | `get_race_predictions` | Predicted 5K/10K/HM/Marathon times with confidence, projected race-day fitness |
| **Training Paces** | `get_training_paces` | Current zones (easy, marathon, threshold, interval, rep) in athlete's preferred units |
| **Key PRs** | `get_personal_bests` | Top PBs with dates and what they imply for current fitness |
| **Pace Math** | New: `compute_pace_table` | Pre-computed: target pace × race distance = finish time, goal pace per mile/km derived from `goal_time_seconds` |
| **N-of-1 Insights** | `get_correlations` + `get_efficiency_trends` | Top 3-5 active findings from correlation engine (e.g., "HRV inversely correlates with next-day performance, r=-0.6, n=47 observations") |
| **Efficiency Trend** | `get_efficiency_trends` | Current EF trend, best recent EF, threshold efficiency trajectory |
| **Intent Snapshot** | `get_coach_intent_snapshot` | Current training intent, pain flags, stated goals, next event |
| **Check-in** | DB query | Latest daily check-in (sleep, energy, soreness, notes) |

### What's New (doesn't exist yet)

1. **Running Math Calculator Tool** — A callable tool for any pace/distance/time arithmetic the LLM needs mid-conversation (e.g., "if I run 7:30 first half and 7:00 second half, what's my finish?"). Prevents the LLM from ever doing mental math. ~30 lines.
2. **Goal Race Context** — `get_plan_week` already has `goal_time_seconds` and `goal_race_distance_m` in the DB model but doesn't return them. Wire them through. The athlete's goal time is the target — the coach never independently looks up qualifying standards.
3. **Pace-to-Finish Pre-computation** — Derive goal pace from `goal_time_seconds ÷ goal_race_distance_m`, include in brief. ~10 lines.
4. **Proactive Correlation Surfacing** — Call `get_correlations` in the brief builder and include top findings.

---

## Layer 2: Smart Tool Outputs

All 22 tools remain callable. The change: each tool's return value gets a `narrative` field — a pre-interpreted, human-readable summary of the results.

### Example: `get_weekly_volume` Today vs Proposed

**Today (raw JSON):**
```json
{"weeks_data": [{"week_start": "2026-01-26", "total_distance_mi": 50.34, "run_count": 5}, ...]}
```

**Proposed (narrative + data):**
```json
{
  "narrative": "Volume over the last 8 weeks: 20→24→36→45→50mi. Current week: 31mi through 3 of 6 runs (partial, on track for ~55mi). Trend: +39% over last 3 completed weeks. Peak volume was 70mpw (May 2025). Currently at 71% of peak.",
  "weeks_data": [...same structured data for reference...]
}
```

The LLM reads the narrative. It doesn't interpret the JSON. If it needs the raw numbers for a specific calculation, they're still there.

### Tool Output Redesign Scope

Every tool in `coach_tools.py` gets a `_build_narrative()` helper added to its return path. This is additive — existing return structures don't change, a `narrative` field is appended.

---

## Layer 3: System Prompt

Replace the current defensive, rule-heavy system prompt with a coaching persona aligned to the manifesto.

### Current System Prompt (~60 lines)
- Lists 22 tools with descriptions
- Anti-hallucination rules
- Evidence/citation requirements
- Defensive instructions ("never say I don't have access")
- Week boundary awareness
- Communication discipline

### Proposed System Prompt (~30 lines)

```
You are the athlete's personal running coach. You have reviewed their complete 
file before this conversation — it's in the ATHLETE BRIEF below.

COACHING APPROACH:
- Lead with what matters. If you see something important in the brief, bring 
  it up — don't wait to be asked.
- Be direct and sparse. Athletes don't want essays.
- Show patterns, explain what they mean, recommend what to do about them.
- Every number you cite MUST come from the brief or a tool result. Never 
  compute math yourself — if you need a calculation, say what you'd calculate 
  and use the data provided.
- When the brief doesn't cover something, call a tool. Read the tool's 
  narrative summary and coach from it.

COMMUNICATION STYLE:
- Use plain English. No acronyms (CTL → "fitness level", ATL → "fatigue").
- No methodology names. Say "threshold pace" not "Daniels T-pace."
- If you make an error, correct it briefly and move on. No groveling.
- Concise. Answer the question, give the evidence, recommend the action.

ATHLETE BRIEF:
{brief}
```

### What Gets Removed
- All canned-response guardrails (`_needs_return_scope_clarification`, `CLARIFICATION_NEEDED` gate)
- Deterministic shortcut paths (already disabled but still in code)
- Defensive rules that encourage passive behavior ("ask the athlete when they returned")

---

## Success Criteria

### Must Pass (Non-negotiable)

1. **All existing 1,393+ tests pass** — zero regressions
2. **CI green on all jobs** — backend tests, smoke tests, frontend, security scan, docker build
3. **Production deployment succeeds** — `docker compose -f docker-compose.prod.yml up -d --build`

### Regression Test: The Conversation That Failed

A new test file `tests/test_coach_brief_builder.py` validates the brief builder. A separate test validates tool narrative outputs. The following assertions cover the exact failures from the Feb 6 conversation:

| Test | Assertion |
|------|-----------|
| Age computation | `brief.identity.age == 57` (for birthdate 1968-*) |
| Goal time surfaced | `brief.goal_race.target_time == "3:10:00"` (from athlete's own `goal_time_seconds`) |
| Goal pace derived | `brief.goal_race.target_pace == "7:15/mi"` (derived from goal_time ÷ distance) |
| Running math tool | `compute_running_math("7:15/mi", 26.2)` returns `"3:09:56"` — LLM never does arithmetic |
| Partial week | `brief.volume_trajectory.current_week.is_partial == True` |
| No hallucination surface area | Brief contains actual weekly volumes from DB — LLM has no reason to fabricate |
| Proactive insights | `len(brief.n_of_1_insights) >= 1` (correlation engine returns findings) |
| Race countdown | `brief.goal_race.days_until_race == 37` (as of Feb 6 → Mar 15) |

### Qualitative Criteria

- Coach opens with an insight, not a question
- Coach never asks the athlete for information the brief contains
- Coach never does arithmetic — all math comes from pre-computed values
- Responses feel like talking to a knowledgeable coach, not a chatbot

---

## Implementation Plan

| Step | Description | Artifact |
|------|-------------|----------|
| 1 | Running math calculator tool | Added to `services/coach_tools.py` |
| 2 | Pace-to-finish helper + goal pace derivation | Added to `services/coach_tools.py` or utility module |
| 3 | Surface `goal_time_seconds` and `goal_race_distance_m` from `get_plan_week` | Modify `coach_tools.py` |
| 4 | `build_athlete_brief()` function | New function in `services/ai_coach.py` or new module |
| 5 | Add `narrative` field to all 22 tool outputs | Modify `services/coach_tools.py` |
| 6 | Rewrite system prompt | Modify `services/ai_coach.py` |
| 7 | Remove canned-response guardrails | Modify `services/ai_coach.py` |
| 8 | Rewire `query_gemini()` to inject brief | Modify `services/ai_coach.py` |
| 9 | Same for Opus path | Modify `services/ai_coach.py` |
| 10 | New tests: brief builder, BQ lookup, pace math, tool narratives | `tests/test_coach_brief_builder.py` |
| 11 | Run full test suite, fix failures | `docker-compose.test.yml` or CI |
| 12 | Push, verify CI green | GitHub Actions |
| 13 | Deploy to production | SSH + docker compose |

---

## Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Brief too large (>4K tokens), increases cost | Medium | Monitor token usage. Brief is ~3-4K tokens. Gemini 2.5 Flash has 1M context window — not a constraint. Cost increase is ~$0.001/message at current Gemini pricing. |
| Brief computation adds latency | Medium | Parallelize DB queries with `asyncio.gather()`. Target <1s total. Cache brief for 60s if same athlete sends rapid messages. |
| Tool narrative generation adds complexity | Low | Narratives are simple f-string templates. They summarize data that's already computed. |
| Gemini still ignores brief and hallucinates | Low | Brief is injected as system instruction (highest priority). Temperature stays at 0.2. The brief makes hallucination unnecessary — all facts are provided. |
| Removing guardrails causes new failure modes | Low | The guardrails were causing more harm than they prevented. The canned responses destroyed trust. The LLM with a rich brief will handle edge cases better than hardcoded strings. |

---

## Consequences

### Positive
- Coach knows the athlete before the conversation starts — like a real coach
- All basic facts (age, BQ, pace math) are pre-computed and correct
- N-of-1 insights surface proactively — athletes learn things they didn't know to ask
- Tool outputs are interpretable — LLM coaches from conclusions, not raw data
- Eliminates entire classes of failures (hallucination, bad math, missing context)

### Negative
- Higher per-message token cost (~2-3x input tokens)
- Brief computation adds ~500-1000ms latency before LLM call
- Every tool needs a narrative builder added (22 functions to touch)
- This is a large change that requires careful testing

### Neutral
- All 22 tools remain callable — no capability is removed
- Opus routing unchanged — high-stakes queries still go to Claude
- Existing test suite unchanged — only additive tests

---

## Alignment with Manifesto

> "Guided Self-Coaching. The athlete is the coach; the system is the silent, brilliant assistant."

The brief IS the silent preparation. The LLM IS the voice. The tools ARE the intelligence. This ADR reconnects them the way the founder intended.

> "The Athlete Intelligence Bank is the moat."

Proactive correlation surfacing means the intelligence bank is no longer hidden. Every finding reaches the athlete through the coach.

> "Performance has no expiration date."

Age-graded insights, correct BQ lookups, and proper race predictions ensure the coach respects and understands masters athletes.
