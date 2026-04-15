# Tech Advisor Runbook — Identify Live `claude-opus-4-6` Caller

Purpose: determine exactly why Anthropic billing shows **`claude-opus-4-6` today** when the checked-in repo appears to have removed live Opus runtime paths.

This is an investigation runbook, not a design note. It is intentionally operational and evidence-first.

## Verified From Local Code

These statements are verified against the local checked-in repo:

1. `apps/api/services/ai_coach.py` sets:
   - `MODEL_HIGH_STAKES = "claude-sonnet-4-6"`
   - no live coach runtime string `claude-opus-4-6` was found in the current file

2. `apps/api/routers/home.py` home briefing Anthropic call uses:
   - `model="claude-sonnet-4-6"`

3. `apps/api/tasks/home_briefing_tasks.py` still prefers Anthropic first when `ANTHROPIC_API_KEY` is present:
   - `_call_llm_for_briefing()` tries Sonnet first, then Gemini fallback

4. Home briefing refresh is scheduled every 15 minutes:
   - `apps/api/celerybeat_schedule.py`
   - task: `tasks.refresh_active_home_briefings`

5. The literal string `claude-opus-4-6` still exists in:
   - tests
   - docs/specs
   - `tmp_coach_model_eval.py`
   - `tmp/coach_model_eval_results.json`
   but not in the live backend runtime paths I inspected.

## Conclusion From Local Code Only

From the repo alone, I cannot prove why **Opus** is being billed today.

What I can prove:

- the current checked-in backend code does not appear to intentionally route live runtime traffic to `claude-opus-4-6`
- therefore the Opus spend must come from one of:
  1. stale production deploy (API and/or worker)
  2. another runtime process outside the checked-in path
  3. a manual/eval script using the same Anthropic key
  4. a different machine/service using the same key

The rest of this document is the exact procedure to resolve that uncertainty.

## Success Criteria

This investigation is complete only when all 4 are answered with evidence:

1. Which process made the Opus calls today?
2. Which host/container/script used the key?
3. What exact model string was executed at runtime?
4. What change stops the spend immediately?

## Required Evidence

Do not conclude anything without pasting:

- deployed git SHA in `strideiq_api`
- deployed git SHA in `strideiq_worker`
- grep results for `claude-opus-4-6` inside both live containers
- relevant log lines from API and worker
- container image + created timestamp for both API and worker
- env/source provenance showing where `ANTHROPIC_API_KEY` is loaded from
- if possible, Anthropic usage export / usage details for today

## Step 1 — Check Deployed Revision In Live Containers

Run on production host:

```bash
docker exec strideiq_api sh -lc 'cd /app && git rev-parse HEAD'
docker exec strideiq_worker sh -lc 'cd /app && git rev-parse HEAD'
```

Compare both SHAs to the commit that supposedly removed live Opus routing.

If either container is not on the expected SHA, that is the first root cause candidate.

## Step 2 — Grep Live Containers For Opus Model String

Run on production host:

```bash
docker exec strideiq_api sh -lc 'cd /app && rg -n "claude-opus-4-6|opus-4-6" .'
docker exec strideiq_worker sh -lc 'cd /app && rg -n "claude-opus-4-6|opus-4-6" .'
```

If `rg` is unavailable in the container image, use this fallback:

```bash
docker exec strideiq_api sh -lc 'cd /app && grep -RIn "claude-opus-4-6\|opus-4-6" .'
docker exec strideiq_worker sh -lc 'cd /app && grep -RIn "claude-opus-4-6\|opus-4-6" .'
```

Interpretation:

- If the worker still contains runtime references to `claude-opus-4-6`, that likely explains all-day background spend.
- If only tests/docs/tmp files match, continue.

## Step 3 — Inspect Home Briefing Runtime Path In Worker

Home briefing is the highest-probability background caller because it:

- runs on a schedule
- uses Anthropic first when key is present
- can generate spend even when no one is actively chatting

Read the live worker file (symbol-anchored first, then context):

```bash
docker exec strideiq_worker sh -lc 'cd /app && rg -n "_call_llm_for_briefing|claude-sonnet-4-6|claude-opus-4-6|source_model" apps/api/tasks/home_briefing_tasks.py'
docker exec strideiq_worker sh -lc 'cd /app && rg -n "_call_opus_briefing_sync|claude-sonnet-4-6|claude-opus-4-6" apps/api/routers/home.py'
```

If `rg` is unavailable, use:

```bash
docker exec strideiq_worker sh -lc 'cd /app && grep -n "_call_llm_for_briefing\|claude-sonnet-4-6\|claude-opus-4-6\|source_model" apps/api/tasks/home_briefing_tasks.py'
docker exec strideiq_worker sh -lc 'cd /app && grep -n "_call_opus_briefing_sync\|claude-sonnet-4-6\|claude-opus-4-6" apps/api/routers/home.py'
```

After finding line anchors, print local context around the matched lines (do not rely on fixed line windows):

```bash
docker exec strideiq_worker sh -lc 'cd /app && sed -n "<start>,<end>p" apps/api/tasks/home_briefing_tasks.py'
docker exec strideiq_worker sh -lc 'cd /app && sed -n "<start>,<end>p" apps/api/routers/home.py'
```

Confirm the actual model strings in the live container, not in local git.

## Step 4 — Check Worker Logs For Briefing Calls Today

Run:

```bash
docker logs strideiq_worker --since=24h | rg "Home briefing|Sonnet|Opus|claude|Anthropic|input=|output="
docker logs strideiq_api --since=24h | rg "Home briefing|Sonnet|Opus|claude|Anthropic|input=|output="
```

If `rg` is unavailable on host, use:

```bash
docker logs strideiq_worker --since=24h | grep -E "Home briefing|Sonnet|Opus|claude|Anthropic|input=|output="
docker logs strideiq_api --since=24h | grep -E "Home briefing|Sonnet|Opus|claude|Anthropic|input=|output="
```

Specifically look for:

- repeated home briefing generations
- model names
- token logs
- fallback paths

Important: `routers/home.py` currently logs `"Home briefing generated via Sonnet ..."`.
If logs instead show old Opus wording or old model names, production drift is proven.

## Step 5 — Check Whether A Script/Eval Was Run With Live Key

Potential non-runtime caller in repo:

- `tmp_coach_model_eval.py`

Check production host and operator execution traces for manual invocations:

```bash
history | rg "coach_model_eval|claude-opus-4-6|anthropic"
docker exec strideiq_api sh -lc 'cd /app && rg -n "coach_model_eval|claude-opus-4-6" .'
docker exec strideiq_worker sh -lc 'cd /app && rg -n "coach_model_eval|claude-opus-4-6" .'
```

If `rg` is unavailable, use:

```bash
history | grep -E "coach_model_eval|claude-opus-4-6|anthropic"
docker exec strideiq_api sh -lc 'cd /app && grep -RIn "coach_model_eval\|claude-opus-4-6" .'
docker exec strideiq_worker sh -lc 'cd /app && grep -RIn "coach_model_eval\|claude-opus-4-6" .'
```

`history` alone is not sufficient. Also check persisted history files:

```bash
grep -En "coach_model_eval|claude-opus-4-6|anthropic" /root/.bash_history /home/*/.bash_history 2>/dev/null
```

If `tmp_coach_model_eval.py` or similar was executed today with the production key, that may fully explain the Opus-only billing.

## Step 6 — Verify No Other Host Process Uses The Same Key

Search the host for exported env vars, shell scripts, cron jobs, or ad hoc tooling:

```bash
crontab -l
rg -n "ANTHROPIC_API_KEY|claude-opus-4-6|opus-4-6" /root /opt/strideiq /etc/cron* 2>/dev/null
docker ps --format '{{.Names}}'
```

Add runtime env/source provenance and container metadata:

```bash
docker inspect strideiq_api | rg -n "Image|Created|ANTHROPIC_API_KEY|STRIDEIQ"
docker inspect strideiq_worker | rg -n "Image|Created|ANTHROPIC_API_KEY|STRIDEIQ"
```

If `rg` is unavailable on host:

```bash
docker inspect strideiq_api | grep -E "Image|Created|ANTHROPIC_API_KEY|STRIDEIQ"
docker inspect strideiq_worker | grep -E "Image|Created|ANTHROPIC_API_KEY|STRIDEIQ"
```

Goal: determine whether another service or forgotten script is sharing the same Anthropic key.

## Step 6.5 — Timebox Alignment (Billing Window Integrity)

Before concluding, lock investigation timestamps so evidence aligns with spend:

```bash
date -u
```

Record:
- `INVESTIGATION_START_UTC`
- `NOW_UTC`

Then re-run log checks using a bounded window matching the billing spike period (for example, from `INVESTIGATION_START_UTC`).

## Step 7 — Immediate Containment If Billing Is Still Climbing

If Opus billing is actively climbing and root cause is not yet isolated, choose one immediate containment action:

1. Remove `ANTHROPIC_API_KEY` from worker and API, redeploy, and force Gemini/deterministic fallbacks temporarily.
2. Disable the `refresh-home-briefings` beat task temporarily.
3. Rotate the Anthropic key after confirming all intended callers can be safely reconfigured.

Containment should be reversible, but stopping spend takes priority over elegance.

## Most Likely Live Offender To Prove/Disprove First

First suspect:

- stale `strideiq_worker` running old home briefing code on the 15-minute schedule

Why this is first:

- background process
- no active athlete interaction required
- Anthropic-first path
- matches all-day spend pattern

This is still only a suspect until Steps 1-4 are completed.

## Investigation Template For Tech Advisor

Paste back results in this exact structure:

```text
API SHA:
WORKER SHA:

API grep for claude-opus-4-6:
WORKER grep for claude-opus-4-6:

API live home model string:
WORKER live home model string:

Worker log evidence:
API log evidence:

Manual/eval script evidence:
Other host process evidence:

Confirmed root cause:
Immediate containment taken:
Permanent fix:
```

## Decision Rule

Do not accept any answer of the form:

- "probably stale deploy"
- "maybe eval script"
- "seems like worker"

Accept only:

- a specific process
- on a specific host/container
- with a pasted model string or log line
- with matching timestamp window to billing evidence
- and a verified containment action
