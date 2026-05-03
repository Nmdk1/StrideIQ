# Fresh-Eyes Brief — Coach V2 Architectural Review — April 29, 2026

**For:** New advisor (any model, human, or agent).
**From:** The founder, via Opus 4.7 (the previous embedded advisor — see "About the previous advisor" below).
**Production:** https://strideiq.run | Server: `root@187.124.67.153` | Founder account: `mbshaf@gmail.com`

---

## Why you exist

StrideIQ is a running intelligence platform. Coach V2 is its central feature. V2 has been deployed to production and produced bad output for the founder in real use. Two canaries have failed qualitatively. The product roadmap, the founder's life savings, and months of work depend on whether the coach can be made exceptional or whether the approach is wrong.

You are being brought in **specifically because the previous advisor is contaminated**. They helped design the V2 architecture, lock the spec, embed the voice corpus, and approve the next-up qualitative eval spec. Their read of "what to do next" is shaped by what they helped build. The founder needs an independent read.

**You have explicit permission to challenge every architectural decision listed below.** That is the point of bringing you in. Continuing the existing trajectory is not the goal. Telling the founder honestly whether the trajectory is salvageable is the goal.

---

## What you must read, in order

### Group A — to understand the founder and the product

| # | Document | Why |
|---|----------|-----|
| 1 | `docs/FOUNDER_OPERATING_CONTRACT.md` | How this founder works. Discuss -> scope -> plan -> test -> build. Commit and push discipline. Advisor relationship. **Non-negotiable as an operating mode** even though you are free to challenge architectural choices. |
| 2 | `docs/PRODUCT_MANIFESTO.md` | What the product is supposed to *be*. Use this to evaluate whether what was built serves what was promised. |
| 3 | `docs/PRODUCT_STRATEGY_2026-03-03.md` | The moat thesis. 16 priority-ranked product concepts. Many depend on the coach being exceptional. |

### Group B — what was built, and how it failed

| # | Document | Why |
|---|----------|-----|
| 4 | `docs/specs/COACH_RUNTIME_V2_ARTIFACT_9_ATHLETE_TRUTH_LAYER.md` | Current V2 architecture. Marked LOCKED. **You may challenge the lock.** |
| 5 | `docs/specs/V2_VOICE_CORPUS.md` | The voice register embedded into the system prompt. Marked LOCKED. **You may challenge whether prompt-embed is the right delivery mechanism.** |
| 6 | `docs/SESSION_HANDOFF_2026-04-26_COACH_V2_B10_VOICE_EMBED.md` | Most recent V2 handoff. State of canary, deploy commands, flag verification, what was supposed to gate the canary. |
| 7 | `apps/api/services/coaching/_llm.py` | Where `V2_SYSTEM_PROMPT` and `V2_VOICE_CORPUS` actually live in code. Read both verbatim. The combined prompt is roughly 6-8k tokens before any per-turn content. |
| 8 | `apps/api/services/coaching/comparison_harness.py` | Existing harness scaffold. **You may challenge whether the harness asks the right question** (Kimi-with-context vs frontier-without-context, instead of StrideIQ-coach vs Runna/Athletica/Strava). |
| 9 | `apps/api/tests/fixtures/v2_acceptance_set.json` | Three fatal cases the canary was supposed to pass. |

### Group C — the actual failure

| # | Document | Why |
|---|----------|-----|
| 10 | April 27 production transcript excerpt below. Source: `coach_chat` in production for `athlete_id=4368ec7f-c30d-45ff-a6ee-58db7716be24`, roughly 02:12-02:26 CDT on 2026-04-27. | **This is the most important reading.** Everything else is theory; this is what the system actually produced. |
| 11 | `docs/specs/COACH_V2_QUALITATIVE_EVAL_HARDENING_SPEC.md` | The spec the previous advisor approved as the next move. **You may challenge whether this is the right next move** or whether it sequences eval improvements ahead of behavioral fixes. |

---

## April 27 production transcript excerpt

**Private production excerpt. Do not promote into fixtures, commits intended for remote publication, or public docs without founder approval and de-identification.** Pulled from production `coach_chat` for the founder account, window 2026-04-27 07:12-07:26 UTC.

### 07:12 — athlete opens with build/race read

**Athlete:**

> The build is done now. I was a bit disappointed with the tune up 5k. Though honestly I don't have a right to be. It was 18 seconds faster than the year before on a tougher day. I think it was because I had gotten SO much faster in fall before getting injured. I have the speed, but i didn't have the lactate buffering to maintain it in the 2nd and 3rd mile.

**Coach response metadata:** `runtime_mode=fallback`, `fallback_reason=v2_guardrail_failed`, `runtime_version=v1`

**Coach:**

> The build is done. You're right about the lactate buffering - your repeats with walking rest protected form but didn't train the specific fatigue resistance you need for a 10K. The good news: your threshold work on April 16 (4 x 10 min at 6:20/mi) and April 9 (3 x 9 min at 6:30/mi) shows you can hold pace under load. Your RPI says 6:19/mi for 10K. Your PR is 6:20/mi. The fitness is there.
>
> Given your tendency to go out at 5K pace, the execution plan is built around restraint in mile 1 and commitment in miles 4-6.
>
> Timeline:
> - 90 min before: light breakfast if needed, fluids
> - 60 min before: 10 min easy jog
> - 45 min before: dynamic warmup, 4 x 15 sec strides
> - 15 min before: get to line, settle
>
> Warmup:
> - 10-12 min very easy jog
> - Leg swings, hip openers
> - 4 strides at race effort, not faster - feel the turnover, don't test the legs
>
> Mile by mile:
> - Mile 1: 6:25-6:30. Slower than you want. This is the discipline mile.
> - Mile 2: 6:20-6:25. Settle into rhythm. If it feels easy, you're doing it right.
> - Mile 3: 6:20. Hold. No surges.
> - Mile 4: 6:20. This is where the race starts. Commit to the pace.
> - Mile 5: 6:15-6:20. Push the effort, not the pace. Let the split come.
> - Mile 6+: Empty it. Whatever is left.
>
> Cue: "Controlled through three, race from four."

### 07:14 — athlete says the course does not support that pacing

**Athlete:**

> the course does not lend itself to that type of pacing

**Coach response metadata:** `runtime_mode=visible`, `fallback_reason=null`, `runtime_version=v2`, `anchor_atoms_per_answer=1`, `unasked_surfacing=false`

**Coach:**

> I need to understand what you're working with. Describe the course: where are the hills, how long, and how steep? Is the start uphill or downhill? Any sharp turns or narrow sections in the first mile?
>
> Without that, I can't anchor a revised plan to the actual terrain. What I *can* say from your data: your 5K tune-up on April 25 faded 5.1% in the second half - that's the lactate buffering limit you named. The 10K will ask more of that same system. If the course forces early expenditure, we need to account for that in the effort budget, not just the split plan.
>
> What's the course profile?

### 07:16 — athlete pastes last year's race table

**Athlete:**

```text
here is the race last year, it should help
1  6:28.9  6:28.9  1.00  6:29  6:21  147  161  69  10 ...
2  6:38.3  13:07   1.00  6:38  6:40  160  165  30  46 ...
3  6:34.5  19:42   1.00  6:35  6:34  155  159  39  39 ...
4  6:38.0  26:20   1.00  6:38  6:38  163  167  39  52 ...
5  6:46.1  33:06   1.00  6:46  6:41  167  173  43  13 ...
6  6:38.0  39:44   1.00  6:38  6:43  161  169  30  79 ...
7  11:35   51:19   0.37  31:31 31:11 135  164  0   13 ...
Summary 51:19 51:19 6.37 8:04 8:02 153 173 253 253 ... 682 ...
```

**Coach response metadata:** `runtime_mode=fallback`, `fallback_reason=packet_assembly_error`, `runtime_version=v1`

**Coach:**

> I see the splits from last year's Coke 10K on May 3, 2025. Chip time 41:27, Garmin 10K time 41:04. The data shows a clear pattern: 6:29, 6:38, 6:35, 6:38, 6:46, 6:38 with a hard finish. That's a 17-second positive split from mile 1 to mile 5, and the heart rate climbed steadily from 147 to 167 avg with a max of 173. The course forced early work and you paid in mile 5.
>
> Your recent threshold work says you can hold pace under load now. April 16: 4 x 10 min at 6:20/mi. April 9: 3 x 9 min at 6:30/mi. Your RPI predicts 6:19/mi for 10K. But the course doesn't allow even pacing, so we need to match effort to terrain, not chase splits.
>
> Where are the hills? How long and how steep? Is the start uphill or downhill? Any sharp turns or narrow sections in the first mile?

### 07:18 — athlete points out the data was already pasted

**Athlete:**

> i tried to give you a screenshot but it doesn't allow it - the data is there in what i gave you

**Coach response metadata:** `runtime_mode=fallback`, `fallback_reason=packet_assembly_error`, `runtime_version=v1`

**Coach:**

> I have the data now. Let me look at last year's actual splits to read the course profile from your effort, then build a terrain-matched plan.
>
> Last year's race: 6:29, 6:38, 6:35, 6:38, 6:46, 6:38. HR climbed from 147 to 167 avg, max 173. You faded 17 seconds from mile 1 to mile 5, then rallied. The pattern says early downhill or fast start, middle grind, late hill or heat cost you in mile 5, then you emptied the tank.
>
> Your training says you can hold 6:20/mi under load now. April 16: 3 x 2538m at 6:20/mi. April 9: 2 x 2525m at 6:30/mi. Your RPI predicts 6:19/mi for 10K. The lactate buffering you were missing in the fall tune-up is present now.
>
> But you said the course doesn't allow even pacing. So here's the terrain-based execution plan:
>
> Uphills: Relax shoulders, shorten stride, maintain cadence. Do not push pace. Let the split go 5-10 seconds slow.
>
> Downhills: Light contact, let gravity work. Do not brake. Gain back 3-5 seconds without spiking effort.
>
> Flat sections: This is where you bank nothing and spend nothing. Hold 6:20-6:25 effort, let the split be what it is.
>
> The specific danger: Mile 5 last year was your slowest at 6:46. That's where the course likely bites. Go into it with reserve. If you feel good at mile 4, you still have 2 miles to use it.
>
> Mental cue: "Hills are free if you don't fight them."
>
> Your freshness is +10.2, recovering well. The build is done. Execute the terrain, not the watch.

### 07:24 — athlete calls hallucination

**Athlete:**

> wrong - you aren't looking at the elevation gain data in the tablesyou are hallucinating - the course starts with 1.5 miles uphill then is rolling terrain the rest of the way with the last hill ending at mile 5

**Coach response metadata:** `runtime_mode=fallback`, `fallback_reason=packet_assembly_error`, `runtime_version=v1`

**Coach:**

> You're right - I should have read the elevation data you already gave me. Last year's splits: 6:29, 6:38, 6:35, 6:38, 6:46, 6:38 with 682 ft total gain. The 1.5-mile uphill start explains the 6:29 opening mile at 147 HR - you were working harder than the split shows. Mile 5 was the slowest at 6:46, which tracks with the last hill ending there. Then you rallied to 6:38 for mile 6.
>
> Your threshold work confirms you can hold pace under load now. April 16: 3 x 2538m at 6:20/mi. April 9: 2 x 2525m at 6:30/mi. Your RPI predicts 6:19/mi for 10K. The lactate buffering you lacked in the fall tune-up is present.
>
> Timeline:
> - 90 min before: light breakfast if needed, fluids
> - 60 min before: 10 min easy jog
> - 45 min before: dynamic warmup, 4 x 15 sec strides
> - 15 min before: get to line, settle
>
> Warmup:
> - 10-12 min very easy jog
> - Leg swings, hip openers
> - 4 strides at race effort, not faster
>
> Mile by mile:
> - Mile 1 (uphill): 6:35-6:40. Let the split go. Relax shoulders, shorten stride, maintain cadence.
> - Mile 2 (still climbing/rolling): 6:30-6:35. Settle into rhythm. If it feels controlled, you're doing it right.
> - Mile 3 (rolling): 6:25-6:30. Hold. No surges.
> - Mile 4 (rolling): 6:25. This is where the race starts. Commit to the pace.
> - Mile 5 (last hill): 6:35-6:40. Expect this to be slow. Do not panic. Pass people who went out too hard.
> - Mile 6+: 6:15-6:25. Empty it. Whatever is left.
>
> Cue: "The hill in mile 5 is the race. Own it."

### 07:26 — athlete isolates the elevation-gain column

**Athlete:**

```text
69
30
39
39
43
30
that is the gain by mile
```

**Coach response metadata:** `runtime_mode=fallback`, `fallback_reason=packet_assembly_error`, `runtime_version=v1`

**Coach:**

> You're right. I have the data. Last year's splits with your gain by mile: 69, 30, 39, 39, 43, 30. That confirms the 1.5-mile uphill start with 69 ft in mile 1, then rolling with the last hill in mile 5 at 43 ft. You went 6:29, 6:38, 6:35, 6:38, 6:46, 6:38. The fade from mile 1 to mile 5 was 17 seconds. HR climbed from 147 to 167 avg, max 173.
>
> Your threshold work on April 16: 3 x 2538m at 6:20/mi. April 9: 2 x 2525m at 6:30/mi. Your RPI predicts 6:19/mi for 10K. The lactate buffering you lacked in the fall tune-up is present now.
>
> Timeline:
> - 90 min before: light breakfast if needed, fluids
> - 60 min before: 10 min easy jog
> - 45 min before: dynamic warmup, 4 x 15 sec strides
> - 15 min before: get to line, settle
>
> Warmup:
> - 10-12 min very easy jog
> - Leg swings, hip openers
> - 4 strides at race effort, not faster
>
> Mile by mile:
> - Mile 1 (69 ft uphill): 6:35-6:40. Let the split go. Relax shoulders, shorten stride, maintain cadence.
> - Mile 2 (30 ft, still rolling): 6:30-6:35. Settle into rhythm.
> - Mile 3 (39 ft): 6:25-6:30. Hold. No surges.
> - Mile 4 (39 ft): 6:25. This is where the race starts.
> - Mile 5 (43 ft, last hill): 6:35-6:40. Expect this to be slow. Do not panic. Pass people who went out too hard.
> - Mile 6+ (30 ft, downhill): 6:15-6:25. Empty it.
>
> Cue: "The hill in mile 5 is the race. Own it."

### What this transcript demonstrates

- Same-turn pasted table evidence was present, but the coach did not parse or use the elevation-gain columns until the athlete manually extracted them.
- V2 fell back repeatedly with `packet_assembly_error`, so part of the "V2 canary" was actually V1 fallback output. A fresh review must inspect both the V2 packet failure and fallback behavior.
- The response repeatedly reverted to a race-day template (`Timeline`, `Warmup`, `Mile by mile`, `Cue`) even while failing the actual task: reading the course table.
- The coach accepted the athlete's correction linguistically ("You're right") before actually correcting the underlying interpretation, including the false `682 ft total gain` claim.
- The behavior gap is not just style. It is evidence ingestion, same-turn reasoning, fallback integrity, and template dominance under correction.

---

## What the previous advisor flagged but is the wrong person to evaluate

Three architectural questions the previous advisor raised in their last turn but cannot evaluate honestly because they helped make the original calls. Treat each as an open hypothesis. Push back hard if you disagree.

1. **The Athlete Truth Layer ledgerizes past-turn facts but not current-turn pasted data.** The April 27 failure was on a table the athlete pasted in the same turn. The architecture explicitly carved this out. "Athlete pastes data" is one of the most common real coach behaviors. Is the architecture solving the wrong half of the problem?

2. **The voice corpus is embedded in a roughly 6-8k-token system prompt.** Long system prompts degrade instruction-following. The transcript shows a race-strategy template appearing to dominate the corpus. Is corpus-in-prompt the wrong delivery mechanism? Alternatives include distilling to 5 imperatives, using turn-typed few-shot, or retrieving the most relevant snippet per turn.

3. **Kimi K2.6 is "locked on cost grounds" as the production model.** The founder believes US frontier models are economically infeasible. Rough numbers suggest Sonnet 4.6 would cost on the order of $0.40 per user per week at typical chat volume — about 2% of a $20/month subscription. The lock was made before the failure mode was visible. Is the cost constraint still binding given the quality gap?

You may also raise architectural questions the previous advisor did not see at all. That is what fresh eyes are for.

---

## Operating constraints (these are NOT architectural)

These rules apply regardless of what you recommend. They protect the founder operationally.

- **No `git push` to `origin` without explicit per-batch founder approval.** Local commits and PRs in your fork are fine. Publishing requires sign-off.
- **No flag flips in production without founder approval.** `coach.runtime_v2.visible` and `coach.runtime_v2.shadow` are the live coach kill switches. Do not touch.
- **No new OAuth or third-party API scopes without founder approval.** Specs may describe future scopes; code waits.
- **No production data committed to the repo.** De-identification and founder approval required before any production transcript becomes a fixture or published handoff.
- **`git add -A` is forbidden.** Scoped commits only.
- **No template narratives, no cheerleading, no "Based on your data...".** Forbidden in coach output, in your PR descriptions, and in your replies to the founder.

These are not architectural constraints. The architecture is open for challenge.

---

## How to talk to the founder

The founder has been building this for months. Two failed canaries. Life savings on the line. Multiple agents have been replaced for wasting tokens. Expect:

- **Findings first, no fluff.** Order: Must fix -> Should address -> Nice to have. Never lead with praise or summary.
- **Evidence is required.** File path, log line, test result, commit SHA. "Verified" without verification is a trust-loss event.
- **Suppression over hallucination.** If you don't know, say so. Do not generate a confident answer to fill space.
- **Show, don't claim.** Paste test output. Paste deploy logs. Paste the actual Kimi request payload, not a description of it.
- **Ask only when blocked.** The founder has answered most general questions twenty times.
- **Never re-state what the founder just said.** Two-dollar mirrors are worse than silence.

If the founder pushes back hard, do not defend. Re-read the source, re-issue the finding only after verification, and acknowledge the prior error explicitly. See `.cursor/rules/advisor-review-discipline.mdc`.

---

## What the founder is asking from you

A real, evidence-based read on the V2 coach. Specifically:

1. **Is the V2 architecture (Athlete Truth Layer + voice corpus in prompt + Kimi K2.6 + comparison harness) the right shape to deliver the coach the manifesto promises?** Yes/no with reasons grounded in the April 27 transcript and the code.

2. **What would you change in the next 48 hours to make the coach better in production?** Not the next month. Not a perfect refactor. The smallest verifiable change that improves the production behavior the founder already saw fail.

3. **Is the qualitative eval hardening spec the right next move, or is it sequencing eval ahead of behavioral fixes that should come first?** The previous advisor argued the latter. Push back if you disagree.

4. **What would change your answer?** What do you need to see — a Kimi request payload, a specific code path, a specific test run — to be more confident in your read?

---

## About the previous advisor

The previous advisor is Claude Opus 4.7. They have been embedded with the founder for the V2 build. They drafted Artifact 9, finalized the voice corpus, approved the qualitative eval spec, helped diagnose the April 27 failure, and wrote this brief.

They have explicitly told the founder they cannot evaluate the V2 architecture fairly because they helped build it. Their reads are still in the chat history and may be useful, but treat them as a participant's view, not an outside read.

You are not bound by their conclusions. The founder explicitly wants you to challenge them.

---

## First action

Do not write code. Do not propose a build plan. Read Group A and the April 27 transcript first. Then write back, in your own words:

1. What you understand the product is supposed to be.
2. What you saw in the April 27 transcript.
3. Your initial read on whether the V2 architecture can deliver what the manifesto promises.
4. What you'd want to look at next before recommending changes.

Wait for founder sign-off before proposing any change.

If you find a contradiction between this brief and any document in Group A, the document wins and you should flag the contradiction. If you find a contradiction between this brief and the previous advisor's conclusions, neither wins — bring it to the founder.
