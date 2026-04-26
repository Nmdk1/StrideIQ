# Artifact 9 — Athlete Truth Layer (Consolidated)

Status: LOCKED 2026-04-26.
Supersedes: `legacy_context_bridge` as primary athlete state.
Consolidates: ledger + recent activity surface + cross-thread memory + unknowns + voice enforcement + system prompt into a single locked artifact.
Locked artifacts referenced: 1 (state package), 5 (conversation modes), 6 (voice rules), 7 (replay rubric), 8 (canary/rollback).

---

## 1. Purpose

V2's athlete state today is a 12,000-character prose dump (`legacy_context_bridge`) that produces stranger-coaching. Artifact 9 replaces it with structured truth: typed athlete facts, recent activity atoms, cross-thread memory, surfaced unknowns, and a voice contract enforced at the system prompt and judge layers.

V2 succeeds when, given the Acceptance Set prompts, V2's answers dominate Sonnet 4.6, GPT 5.5, and Opus 4.6 on every dimension every case, with the data advantage visible.

---

## 2. Bar (locked, not re-litigated)

The product-level bar: an elite running scientist (Brady Holmer) or an elite running coach (David Roche) reads a V2 answer about this athlete and says **"holy shit, I couldn't do better."** That is the only bar that matters for the unknown-brand growth thesis. Word of mouth happens when the coaching is at that level, not at frontier-model parity.

Every V2 answer must therefore meet all of:
- **Elite-coach-equivalent depth.** Reads as if produced by a coach who has internalized Roche, Davis, Green, Eyestone, and McMillan training philosophies and has full data access to this specific athlete. Not "competent running advice." Coaching with judgment, mechanism, and philosophy.
- **Unique to athlete + StrideIQ.** Could not come from a frontier model with the same prompt. Could not come from an elite coach without this athlete's data open in front of them.
- **Anchored in named atoms.** Specific session by date or distance, specific data feature within that session (rep-by-rep drift, fade pattern, executed-vs-planned delta), specific ledger fact, specific prior thread. Generic references ("your recent training") fail.
- **Surfaces unasked observations.** On every substantive turn, name at least one pattern, risk, contradiction, or opportunity the athlete didn't ask about, drawn from data the elite human coach without StrideIQ's database could not have surfaced.
- **Voice in the elite-coach register.** Direct, scientifically grounded, philosophy-anchored, willing to name physiological mechanisms, commits to one read, ends in a concrete decision. No template phrases. No cheerleading. No option-enumeration. No corporate-coachspeak.
- **No generic fallback ever.**
- **Athlete-stated facts persist across turns and threads.**
- **Corrections bind in the next turn.**
- **Unknowns surface explicitly with a specific question or hedge.**

**Quantitative comparison gate** (code-complete harness): Sonnet 4.6, GPT 5.5, Opus 4.6 with the same prompt and typed athlete context. V2 unanimous #1 every dimension every case. Tier 3 judge with `voice_alignment` against elite-coach baselines.

**Qualitative ceiling gate** (founder canary, non-substitutable): Founder reads each V2 turn and asks "would Brady Holmer or David Roche read this and say 'I couldn't do better.'" The binary answer is the ship/no-ship signal. No quantitative score overrides this.

Production model: Kimi K2.6 with thinking enabled. Locked. No alternates.

---

## 3. Athlete Fact Ledger

### 3.1 Required field set (v1)

| Field | Type | Notes |
|---|---|---|
| `weekly_volume_mpw` | float | miles |
| `current_block_phase` | enum | `base \| build \| peak \| taper \| recovery \| unstructured` |
| `target_event` | struct | `{distance, date, goal_time}` |
| `pr_per_distance` | map | distance → `{time, source_activity_id, asserted_at}` |
| `recent_injuries` | list | `{site, severity, started_at, status}` |
| `current_weight_lbs` | float | |
| `target_weight_lbs` | float | |
| `age` | int | years |
| `coaching_voice_preference` | enum | `direct \| gentle \| analytical`, default `direct` |
| `pace_zones` | struct | `{easy, marathon, threshold, interval, repetition}` |
| `gut_sensitivity` | struct | `{flag: bool, notes: str}` |
| `cut_active` | struct | `{flag: bool, start_date, target_deficit_kcal}` |
| `typical_training_days_per_week` | int | |
| `standing_overrides` | list | `{domain, value, asserted_at}` |

Field set is additive. Adding fields does not break v1.

### 3.2 Per-fact metadata

Every value carries:
- `value`
- `confidence` ∈ {`athlete_stated`, `athlete_confirmed`, `derived`, `inferred`}
- `source` (turn_id | activity_id | onboarding | manual_edit)
- `asserted_at` (UTC)
- `confirm_after` (UTC, per-field policy default)
- `audit_trail` (append-only list of prior values + change reasons)

### 3.3 Population precedence

High to low:
1. `athlete_stated` (explicit statement in conversation)
2. `athlete_confirmed` (asked by coach, confirmed by athlete)
3. `derived` (activity stream / device data)
4. `inferred` (low-confidence LLM extraction; non-binding until confirmed)

Conflict resolution: higher precedence wins. Same precedence: newer wins. On detected conflict between an `athlete_stated` value and any other source, the system asks the athlete in the next turn before overwriting.

### 3.4 Staleness defaults

| Field | Confirm interval |
|---|---|
| `weekly_volume_mpw` | 30 days |
| `current_weight_lbs` | 14 days |
| `recent_injuries` | 7 days |
| `pace_zones` | 60 days |
| `target_event` | until date passes |
| `cut_active` | 14 days |
| Others | 60 days default |

Expired fields surface in the unknowns block with a `field_required_for` tag tied to the active query.

### 3.5 Storage

DB: `athlete_facts` table (one row per athlete, `jsonb` payload) plus `athlete_facts_audit` (append-only). Per-field rows acceptable if builder prefers; audit table required either way. Permission policy per existing surface.

### 3.6 API

- `get_ledger(athlete_id) → AthleteFacts`
- `set_fact(athlete_id, field, value, source, confidence) → AuditEntry`
- `correct_fact(athlete_id, field, new_value, reason)` (writes new value, audits prior)
- `confirm_fact(athlete_id, field)` (resets `confirm_after`)
- `extract_facts_from_turn(athlete_id, turn) → list[ProposedFact]` (deterministic regex first; LLM extraction supplements at low confidence with `inferred`)

### 3.7 Tests

- Roundtrip (write/read/correct/confirm).
- Conflict resolution per precedence level.
- Staleness scheduler surfaces expired fields.
- Audit trail integrity (no mutation, append-only).
- Permission redaction respected.
- Persistent-fact-recall Acceptance Set case passes.

---

## 4. Recent Activity Block

### 4.1 Purpose

Surface the athlete's last 14 days of activity as named atoms K2.6 can cite. Replaces athlete-state prose.

### 4.2 Contents

For each activity in the last 14 days:
- `activity_id`, `type`, `date`, `distance`, `duration`, `avg_pace`, `avg_hr`, `perceived_effort`
- `planned_vs_executed_delta` (when planned exists)
- `notable_features` (drift, fade, strong-finish, missed-rep) computed deterministically
- `structured_workout_summary` (rep-by-rep) when known

Aggregates:
- Last 4 weeks: `weekly_volume`, `weekly_hard_day_count`, `weekly_easy_hard_ratio`, `weekly_volume_change_pct`.
- Last session of each major workout type (`threshold`, `interval`, `long`, `easy_default`).

### 4.3 Computation

Deterministic. No model. Pulled from existing activity store. Cached per packet assembly.

### 4.4 Packet shape

`recent_activities` block: typed entries, ordered most-recent-first. Field names explicit, units explicit. Token budget target 1500, hard cap 2500.

### 4.5 Tests

- Block populates from canned fixture activities.
- 14-day window respected.
- Computed metrics match expected on synthetic data.
- Acceptance Set Grok-physiology case: V2 must reference at least one specific recent activity by date or distance.

---

## 5. Thread Summary Block

### 5.1 Purpose

Cross-thread memory. A statement made six weeks ago in a different thread must be available now.

### 5.2 Generation

On thread close (idle timeout 24h, or explicit close): generate summary containing
- `stated_facts` (write back to ledger as `athlete_stated`)
- `open_questions`
- `decisions_made`
- `topic_tags` (top 5)

Deterministic extraction first; LLM supplement at low confidence. Stored on athlete record. Indexed by date.

### 5.3 Packet shape

`recent_threads` block: last 5 thread summaries. Total token budget 2000. Each entry: `{date, topic_tags, decisions, open_questions, stated_facts_summary}`.

### 5.4 Tests

- Thread close triggers summary generation.
- Summary writes facts to ledger with `athlete_stated` confidence.
- New thread receives populated `recent_threads` block.
- Acceptance Set persistent-fact-recall: stated fact in thread A surfaces in thread B days later.

---

## 6. Unknowns Block

### 6.1 Purpose

The system always knows what it doesn't know.

### 6.2 Population

For each required ledger field with `null` value or expired `confirm_after`, emit an unknown entry with a `field_required_for` reason mapped to the active query class (e.g., `pace_zones` required for `interval_pace_question`).

### 6.3 Packet shape

`unknowns` block: list of `{field, last_known_value_or_null, asserted_at, field_required_for, suggested_question}`.

The hardcoded `unknowns: []` empty list is removed.

### 6.4 Tests

- Null required field surfaces.
- Expired field surfaces with `expired_at` reason.
- Acceptance Set unknown-surfacing case: V2 asks the suggested question, does not fabricate.

---

## 7. Voice Contract Enforcement

### 7.1 Template-phrase blocklist (v1, locked, additive)

Forbidden in V2 outputs:

```
consider
you might want to
great question
well done
solid and practical
disciplined fueling
no guilt
real food, controlled, satisfying
real food, controlled
healthy in the way that matters
natural sweetness without junk
great for satiety and muscle repair
love that you
amazing job
proud of you
keep up the great work
that's awesome
keep crushing it
you've got this
trust the process
listen to your body
```

Enforcement:
- Hard regex check on every V2 response. Hit triggers retry with explicit "rewrite without phrase X" instruction; persistent hit logs as quality incident with `template_phrase_count` > 0 and the response is not served.
- Tier 3 judge `voice_alignment` dimension penalizes any hit.
- List grows additively as canary or replay identifies new template phrases. Removal requires founder sign-off.

### 7.2 voice_alignment scoring

Per Artifact 7. Threshold for Acceptance Set: ≥ 0.85.

### 7.3 Voice corpus (R0 deliverable)

The voice K2.6 must produce is the elite running coach / running scientist register: Roche, Davis, Green, Eyestone, McMillan, with Holmer-style physiology grounding. Source material already lives in `docs/references/`:

- `ROCHE_SWAP_TRAINING_PHILOSOPHY_UNIFIED_2026-04-10.md`
- `ROCHE_SWAP_COACHING_PHILOSOPHY_2026-04-10.md`
- `ROCHE_SWAP_EFFORT_DICTIONARY_2026-04-10.md`
- `ROCHE_SWAP_FUELING_REFERENCE_2026-04-10.md`
- `ROCHE_SWAP_WORKOUT_EXECUTION_GUIDE_2026-04-10.md`
- `DAVIS_FIVE_PRINCIPLES_MARATHON_TRAINING_2026-04-10.md`
- `DAVIS_MARATHON_EXCELLENCE_AND_TRAINING_LOAD_2026-04-10.md`
- `DAVIS_MODERN_MARATHON_APPROACH_REFERENCE_NOTE_2026-04-10.md`
- `GREEN_COACHING_PHILOSOPHY_EXPANDED_2026-04-10.md`
- `GREEN_COACHING_PHILOSOPHY_REFERENCE_NOTE_2026-04-10.md`
- `ADVANCED_EXERCISE_PHYSIOLOGY_SYNTHESIS_2026-04-10.md`
- `COE_STYLE_TRAINING_REFERENCE_NOTE_2026-04-10.md`
- `SSMAX_STEADY_STATE_MAX_REFERENCE_NOTE_2026-04-10.md`

Eyestone and McMillan reference notes pending sourcing per existing handoff; not blocking v1.

**Few-shot construction:**
- 8–12 short snippets (≤ 200 words each) drawn directly from the corpus above. Founder selects which snippets best represent the voice for V2's audience. Builder embeds verbatim in system-prompt few-shot.
- Snippets must show: direct verb usage, mechanism naming, philosophy anchoring, commits-to-one-read pattern, ends-in-decision pattern.
- No invented voice samples. Builder cannot author coaching examples — only the corpus and founder-provided text are eligible.

---

## 8. V2 System Prompt (locked v1 text)

```
You are StrideIQ's coach. The athlete in this turn is the same human you have coached over many sessions. The packet you receive contains the truth about this athlete: structured facts (athlete_facts), recent activities (recent_activities), recent thread summaries (recent_threads), open unknowns (unknowns), the calendar context (calendar_context), and the current conversation.

How you must behave:

1. Anchor every claim about the athlete in a named atom from the packet. Cite the specific session by date or distance, the specific ledger fact, the specific prior thread. If a claim cannot be anchored, do not make it.

2. When a required fact is in unknowns, ask the suggested question or hedge explicitly. Never fill an unknown with generic coaching.

3. Surface the unasked. On every substantive turn, name at least one pattern, risk, contradiction, or opportunity the athlete didn't ask about, drawn from recent_activities, recent_threads, or ledger trends.

4. Commit to one read. Do not enumerate possibilities when one read is more likely. State the read, give the reasoning, and accept that the athlete may push back.

5. End every substantive turn with a decision the athlete can act on. Specific. Concrete. Bounded.

6. Voice register: write as a coach who has internalized Roche, Davis, Green, Eyestone, and McMillan training philosophies and Holmer-level physiology. Direct. Scientifically grounded. Philosophy-anchored. Willing to name mechanisms (lactate, glycogen, fatigue resistance, ventilatory threshold, fueling, durability) when they explain the read. No template praise. No "consider," "you might want to," "great question," "well done." Real verbs. Honest reads. Name what is working and what is not. The bar is "Brady Holmer or David Roche reads this and says 'I couldn't do better.'"

7. Trust the athlete's stated facts. If athlete_facts shows a value with confidence athlete_stated, that wins over derived data. If the athlete corrects you, update immediately and do not repeat the corrected assumption.

8. Never invent a session, a fact, a date, or a metric. If you do not have the atom, you cannot make the claim.

9. The conversation_mode and athlete_stated_overrides in the packet are binding. Honor both.

Coach. Don't analyze.
```

The prompt is followed by the structured packet, then the user message. The model is told the packet is internal coach state and must not be quoted as if it were an athlete-authored input.

---

## 9. Pattern surfacing — model-native (v1 decision)

The packet provides `recent_activities` with computed atoms (drift, fade, weekly volume change, missed days). K2.6 with thinking enabled identifies patterns from those atoms. No deterministic pattern engine is built in v1.

If the comparison run shows K2.6 missing patterns it should have caught, deterministic surfacing is added in v2. Not before.

---

## 10. Two-stage retrieval — deferred (v1 decision)

V1 ships everything-in-packet. K2.6 has no tools. If the comparison run or canary reveals atoms the packet didn't pre-fetch, two-stage retrieval is added in v2. Not before.

---

## 11. Acceptance Set (v1)

Three fatal `artifact7.v1` cases:

| ID | Domain | Source | Failure modes |
|---|---|---|---|
| `grok_physiology_breathing` | training_physiology | founder_curated | FM-no-context-integration, FM-stranger-coaching |
| `nutrition_cheerlead_sarcastic_intake` | nutrition_fueling | founder_curated | FM-009 (already in case bank) |
| `persistent_fact_recall_volume` | meta_memory | founder_curated | FM-no-cross-thread-memory, FM-correction-not-binding |

Each case carries:
- full prompt
- athlete-context-as-the-athlete-would-state-it
- `expected_coaching_truths`
- `bad_coaching_patterns`
- `must_not`
- `baseline_voice` + `baseline_citation`
- `data_advantage_must_include` (atoms from the ledger / activities / threads that V2 must surface)
- reference answers from Sonnet 4.6 + GPT 5.5 + Opus 4.6 (collected at harness time)
- `failure_severity: fatal`

Cases are added to the set by founder review. Cases are not removed.

---

## 12. Comparison Harness

Single run at code-complete:
- For each Acceptance Set case, run the prompt through Sonnet 4.6, GPT 5.5, Opus 4.6 (typed-context only, no ledger/activities), and V2 (full packet).
- Tier 3 judge ranks all four on five dimensions (correctness, helpfulness, specificity, voice_alignment, outcome).
- Output: per-case ranking matrix + qualitative judge notes + per-case `data_advantage_must_include` coverage check.

Gate: V2 unanimous #1 every dimension every case. Anything less, builder iterates before founder canary.

---

## 13. Founder canary (post-harness, qualitative ceiling gate)

Founder runs V2 in production via founder-only flag exposure. A small number of real conversations. Founder reads each V2 turn and asks the binary question:

> **Would Brady Holmer or David Roche read this answer about me and say "holy shit, I couldn't do better"?**

That is the only ship/no-ship signal at canary. Tier 3 scores from the harness are necessary but not sufficient; this binary is the ceiling test.

- **Pass**: V2 is the coach worth shipping. Move to broader pilot per Artifact 8 Stage 4 (founder timing).
- **Fail**: identified failures fed into the case bank as fatal `artifact7.v1` cases with notes on which dimension the elite-coach test failed (depth, mechanism, voice, anchoring, surfacing, decision). Builder iterates against that named dimension. Re-run harness. Re-canary.

No shadow phase. No long iteration. The founder's elite-coach binary is the gate.

---

## 14. Build sequence

Single consolidated build phase. Builder agent owns drafting and implementation.

Gate points (Opus 4.7 review, founder sign-off):
1. **Artifact 9 lock** — this document. Founder reads, edits, signs off. No builder work starts until locked.
2. **Code complete** — review of ledger + `recent_activities` + `recent_threads` + `unknowns` + system prompt + voice enforcement + harness wiring.
3. **Comparison run** — review of harness output before founder canary.

Opus 4.7 does not draft code. Reviews at gates only. Builder agent is the implementer.

---

## 15. What dies on Artifact 9 wire-in

- `legacy_context_bridge` (removed from primary path; deprecation shim during cutover only, then removed).
- `override_value: True` boolean (replaced by `{value, duration: current_turn|standing}`; standing overrides write to ledger).
- `unknowns: []` hardcoded empty (replaced by populated unknowns block).
- `thinking: disabled` in `query_kimi_v2_packet` (flipped to `enabled`).
- The current V2 system prompt (replaced by Section 8).

---

## 16. What stays unchanged

Artifacts 1–8 stand. Fail-closed flag helper, packet schema versioning, `same_turn_overrides` regex extraction (semantics fix at build time), calendar/activity blocks, mode classifier, umbrella request log, Artifact 7 framework + validator + Tier 3 voice_alignment, replay framework. Foundation.

---

## 17. Telemetry contract

Per V2 turn, persisted in `CoachChat` metadata + structured log:

| Field | Required value |
|---|---|
| `anchor_atoms_per_answer` | ≥ 2 on substantive turns |
| `unasked_surfacing` | `true` on substantive turns |
| `template_phrase_count` | 0 |
| `generic_fallback_count` | 0 |
| `ledger_field_coverage` | reported, not gated |
| `unknowns_count` | reported |
| `model` | `kimi-k2.6` |
| `thinking` | `enabled` |
| `voice_alignment_judge_score` | when judged |

Substantive turn definition: any turn where the user message is a coaching query (mode ≠ `pure_factual_lookup` or `meta_chat`).

---

## 18. Founder commitment surface

Total commitment, Artifact 9 lock through canary:
1. Sign-off on this Artifact 9 lock (with edits).
2. Provide voice samples (Section 7.3).
3. Sign-off at code-complete review.
4. Sign-off at comparison-run review.
5. Run canary turns and decide pass/fail.

Five touchpoints. No daily reviews. No weekly check-ins. No shadow window.

---

## 19. Lock-time decisions

Resolved at lock with the recommended defaults. Founder may edit any value below before unpausing the builder; once Phase B1 begins, changes here drift the build and require a follow-up commit.

1. **DB shape**: single `athlete_facts` jsonb row per athlete plus a separate `athlete_facts_audit` append-only table.
2. **Thread close trigger**: 24h idle. Explicit close also supported.
3. **`recent_threads` count**: 5 entries, with 2000-token total budget cap; oldest truncated first when cap exceeded.
4. **Voice samples**: founder provides directly via `docs/specs/V2_VOICE_CORPUS.md`. Builder may not author or extract.
5. **Pilot expansion timing**: deferred. Founder decides after canary passes; not in scope for this build.

---

## 20. Lock procedure

1. Founder reads this document.
2. Founder edits Sections 3.1, 3.4, 7.1, 8, 11, 19 directly if changes needed.
3. Founder marks status at top: `LOCKED`, dated.
4. Builder agent begins consolidated build phase.

Until status is `LOCKED`, this is draft and no implementation work proceeds.
