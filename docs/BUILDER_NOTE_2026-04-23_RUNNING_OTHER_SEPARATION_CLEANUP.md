# Builder Note — Running/Other Activity Separation: Platform-Wide Cleanup

**Date:** 2026-04-23
**Assigned to:** Backend + Frontend Builder (composer-2-fast)
**Advisor sign-off required:** Yes (founder reviews verification output before push)
**Urgency:** High — same bug class as the Dejan Apr 22 incident is still live on at least three other surfaces.

---

## Before Your First Tool Call

Read in order:
1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/PRODUCT_MANIFESTO.md` (running is the first-class metric)
3. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` (Part 4 rejected patterns; "Never hide numbers"; cross-training has separate visual treatment)
4. `docs/AGENT_WORKFLOW.md`
5. `docs/SITE_AUDIT_LIVING.md`
6. This builder note
7. The just-shipped reference fix (the pattern to mirror): commit `0af4bcd`, files `apps/api/routers/home.py` (week aggregation block) and `apps/api/routers/activities.py` (`/summary`).

---

## Objective

Eliminate the `mixed-sport aggregation + silent-dedup` bug class everywhere it lives in the platform. After this work, every athlete-facing surface that shows running mileage, completion status, or "this week" volume must (a) include only running activities in the running number, (b) never silently drop a second activity on the same day, and (c) surface non-running activity through a dedicated, selectable affordance — never by mixing it into running totals.

When done, no surface in production conflates a walk, strength session, or cycle with a run, and no surface drops a real activity because another activity shared the day.

---

## Scope

### Group 1 — Stabilize the baseline (do first; ~1 hour)

1.1 **Fix 7 long-standing red tests in `apps/api/tests/test_home_api.py`.**
- Failing classes: `TestComputeCoachNoticed::*` (4), `TestComputeRaceCountdown::*` (3).
- Root cause: tests pass `"athlete-1"` as `athlete_id` to functions that now do `uuid.UUID(athlete_id)` (`routers/home.py:3453`).
- Preferred fix: change fixtures to `str(uuid4())` rather than loosen the function's type contract. The function being strict is correct; the tests were written before the strict path landed.

1.2 **Add `.gitattributes` so `*.sh` stops getting CRLF line endings on Windows checkouts.**
- Add at minimum: `*.sh text eol=lf`, `*.py text eol=lf`, `*.ts text eol=lf`, `*.tsx text eol=lf`.
- Re-normalize: `git add --renormalize .` (preview with `git status` before committing).
- Verify: a freshly checked-out `.sh` runs on the production droplet without `sed -i 's/\r$//'`.

1.3 **Fix double-rounding in the new `other_sport_summary` aggregation in `apps/api/routers/home.py`.**
- Current code rounds `duration_min` per-activity to 1 dp, then sums, then rounds to whole minutes. This is order-dependent and dropped 1 minute on a 7,767-second strength session in tests.
- Fix: in the `_other_agg` loop accumulate raw `duration_s` (int seconds) and `distance_m`, divide and round once at the end. Same change in the per-day `other_activities` loop only if you want consistent display rounding — discuss before changing the per-activity values, since tests pin them.
- Update `apps/api/tests/test_home_week_running_separation.py` so the strength duration assertion is `== 130` (not `in (129, 130)`). The looser assertion is a bandaid and must be removed.

1.4 **Make the hot-patch healthcheck loop fail-loud, not silent.**
- File: `.hotpatch_weekly_fix.sh` (or replace with a re-usable script in `scripts/`).
- The current loop exits even when `/healthz` never returns 2xx. Change to: poll up to 30s, fail script with non-zero exit if not healthy, print the last 30 lines of `docker logs strideiq_api`.

### Group 2 — Platform-wide running/other separation (~2-3 hours)

2.1 **`apps/api/routers/calendar.py:400` — `get_day_status`.**
- Current: `total_distance = sum(a.distance_m or 0 for a in activities)` mixes a walk into the planned-run completion ratio. A 1.56 km walk on a planned 16 km run day shifts the ratio.
- Fix: when comparing against `planned.target_distance_km` (which is a running plan target), compute `total_distance` from runs only (`a.sport == "run"`). If zero runs but the planned workout is a run, don't flip status to "completed" or "modified" based on cross-training distance.
- If the planned workout's discipline is non-running (very rare in current product but possible), match same-discipline. Add a doc comment explaining the contract.

2.2 **`apps/api/routers/calendar.py:801` — `/v1/calendar` day cells.**
- Currently returns `total_distance` and `total_duration` summed across every sport on the day. This will then render as "the day's mileage" in the UI.
- Fix: return BOTH `running_distance_m` / `running_duration_s` AND `other_distance_m` / `other_duration_s` (or a structured `by_sport`). Keep `total_distance` for backwards compatibility but mark in code that it is cross-sport and unsuitable for "running mileage" displays.
- Coordinate with the frontend calendar consumer (`apps/web/app/calendar/...`): wherever `total_distance` is rendered as "miles" today, switch to `running_distance_m` so a walk doesn't appear as run mileage.

2.3 **`apps/api/routers/calendar.py:938` — `/v1/calendar/day/{date}`.**
- Same issue and same fix shape as 2.2.

2.4 **`apps/web/app/analytics/page.tsx:235` — week chip with dead legacy branch.**
- The `day.sport && day.sport !== 'run'` branch is now unreachable (under the new `WeekDay` contract `day.sport` is only set for runs). The analytics week chip therefore (a) never shows the sport icon for non-run days because there are no non-run primary days, AND (b) lacks the `+N` multi-run affordance and the per-day other-sport icons that the home week chip now has.
- Fix: mirror the home page chip exactly. Reuse the chip render — extract `WeekChipDay` into `apps/web/components/home/WeekChipDay.tsx` (or similar) and consume it from both `app/home/page.tsx` and `app/analytics/page.tsx`. Single source of truth prevents the next drift.

2.5 **Audit-and-document pass on every other Activity aggregation site.**
The following call sites were identified by grepping `db\.query\(Activity\)` in `apps/api/routers/`. For each, read the call site, document the intended semantics in a comment (running-only vs all-sport vs single-activity lookup), and only change behavior when the surface is labeled or rendered as "running mileage" / "training volume" / "weekly distance":

  - `apps/api/routers/compare.py:172`
  - `apps/api/routers/progress.py:1595` (line 398 is already running-only — leave alone)
  - `apps/api/routers/training_load.py:151` (intentionally cross-sport for TSS — leave alone, but add the doc-comment)
  - `apps/api/routers/onboarding.py:75` (already running-only — leave alone, add doc-comment)
  - `apps/api/routers/attribution.py:128, 200`
  - `apps/api/routers/fingerprint.py:129, 201, 240, 349`
  - `apps/api/routers/strava.py:623`
  - `apps/api/routers/admin.py:1871, 2423`
  - `apps/api/routers/nutrition.py:724, 895, 1130, 1195, 1311`
  - `apps/api/routers/run_analysis.py` (whole file scan)
  - `apps/api/routers/run_delivery.py`
  - `apps/api/routers/stream_analysis.py`
  - `apps/api/services/correlation_engine.py`
  - `apps/api/services/causal_attribution.py`
  - `apps/api/services/fingerprint_context.py`
  - `apps/api/services/individual_performance_model.py`
  - `apps/api/services/anchor_finder.py`
  - `apps/api/services/consistency_streaks.py`

For each site, the deliverable is either: (a) a one-line code comment stating the intended semantics + a no-op, OR (b) a fix with a regression test. Do not blanket-patch.

### Group 3 — Finish what was half-shipped (~1-2 hours)

3.1 **Render the `other_sport_summary` field that was added to `WeekProgress`.**
- Currently the home page does not display it. The field is dead weight on the wire.
- Add a single, dignified line under the trajectory sentence: e.g. `Also this week: 1 walk · 35 min strength`. Words/structure may vary — discuss with founder if uncertain — but no template phrasing per `DESIGN_PHILOSOPHY` Part 4.
- If `other_sport_summary` is empty, render nothing (no "0 walks" placeholder).

3.2 **Frontend tests for the home week chip.**
- `apps/web/__tests__/home/week-chip.test.tsx` (Jest + RTL).
- Cases: single-run day renders distance + checkmark; multi-run day renders `+N` affordance with correct deep link; day with a walk renders the walking icon as a separate `<a>`; rest day renders dash; today gets the `ring-2 ring-orange-500` class.

3.3 **Frontend tests for the activities-page Running/Other/All toggle.**
- `apps/web/__tests__/activities/sport-view-toggle.test.tsx`.
- Cases: clicking each option updates `aria-pressed`; clicking `Running` filters list to `sport=run`; clicking `Other` clears sport and shows the sport-pills row; clicking `All` clears sport; the 4 stat cards rebind to the chosen bucket; Avg Pace card hides on Other and All.

### Group 4 — Dev loop (last; do only if time permits this session)

4.1 **`docker-compose.dev.yml` override that volume-mounts `apps/api/` and `apps/web/`** so the local `strideiq_api` container reflects the on-disk code without `docker cp`. Reference acceptance: `docker exec strideiq_api python -c "from services.timezone_utils import to_activity_local_date"` succeeds without copying files in.

---

## Out of Scope

- Any change to `apps/api/services/plan_framework/**` or `apps/api/routers/plan_generation.py`. Those touch the P0 plan registry gate. If you must touch them, stop and request a separate builder note with the P0 attestation rules attached.
- Any new OAuth or third-party permission scopes. None are needed for this work.
- Adding new top-level surfaces or pages. This is a correctness + cleanup pass, not a new feature.
- Replacing or extending the `WeekDay` / `WeekProgress` schemas in any way that breaks the back-compat fields (`completed_mi`, `planned_mi`, `distance_mi`, `activity_id`).
- Changing `routers/training_load.py`'s cross-sport TSS aggregation. That mixing is intentional.

---

## Implementation Notes

**Files expected to change (planning estimate, may grow during 2.5 audit):**

Backend
- `apps/api/routers/home.py` (1.3 rounding only)
- `apps/api/routers/calendar.py` (2.1, 2.2, 2.3)
- 0 — N services from the 2.5 audit list, with most likely being doc-comment-only
- `apps/api/tests/test_home_api.py` (1.1)
- `apps/api/tests/test_home_week_running_separation.py` (1.3 strict assertion)
- `apps/api/tests/test_calendar_*.py` (new regression tests for 2.1-2.3)

Frontend
- `apps/web/app/analytics/page.tsx` (2.4)
- `apps/web/components/home/WeekChipDay.tsx` (extracted, reused by home + analytics) — 2.4
- `apps/web/app/home/page.tsx` (consume extracted chip + render `other_sport_summary`) — 2.4 + 3.1
- `apps/web/app/calendar/...` (consume new `running_distance_m` from 2.2/2.3)
- `apps/web/__tests__/home/week-chip.test.tsx` (3.2)
- `apps/web/__tests__/activities/sport-view-toggle.test.tsx` (3.3)

Repo hygiene
- `.gitattributes` (1.2)
- `.hotpatch_weekly_fix.sh` or replacement in `scripts/` (1.4)
- `docker-compose.dev.yml` (4.1, optional)

**Core contracts to preserve:**

1. The `WeekDay` schema fields shipped in commit `0af4bcd` are now part of the public API surface for the home and (after 2.4) the analytics page:
   - `distance_mi` is RUNNING ONLY.
   - `activity_id` is the LONGEST run that day.
   - `run_count` reflects the count of runs that day.
   - `other_activities[]` carries non-running activity for the day.
2. `WeekProgress.completed_mi` and `WeekProgress.planned_mi` are RUNNING ONLY.
3. `/v1/activities/summary` returns `running` / `other` / `combined` buckets and ALSO mirrors `running` to the legacy top-level fields. Do not remove the back-compat mirroring this session.
4. `Avg Pace` is only meaningful for the running bucket. Do not compute or display a cross-sport pace average.
5. Never use `keep first per day` style dedup that drops real rows. If multiple activities share a day, separate by sport, then aggregate.

**Guardrails / no-regression constraints:**

- Do not change the response shape of `/v1/home` or `/v1/activities/summary` in a way that breaks the just-shipped frontend. Add fields, don't rename or remove.
- Do not blanket-add `Activity.sport == "run"` to query sites without reading the surrounding code; some sites are intentionally all-sport (training load, total-activity counts, raw activity lists). The 2.5 audit is documentation-first.
- Never `git add -A`. Scoped commits only. See `docs/FOUNDER_OPERATING_CONTRACT.md`.
- Production hot-patch is allowed for verification ONLY, after the founder approves the diff. Final ship is `git push origin main` → CI green → `docker compose -f docker-compose.prod.yml up -d --build` on the droplet.

---

## Tests Required

**Unit / behavior tests (backend):**

- The 7 fixed `test_home_api.py` tests pass without xfail markers.
- New `test_calendar_running_separation.py` — pin the same Dejan Apr 22 fixture (run + walk same day) and assert: `get_day_status` returns "completed" only when running miles satisfy the planned ratio (walk does not satisfy a planned run); `/v1/calendar/day` exposes both running and other distance fields.
- `test_home_week_running_separation.py::test_other_sport_summary_aggregates_distance_and_duration` — strict equality after the rounding fix (`== 130`, not `in (129, 130)`).

**Integration tests:**

- `tests/test_activities_summary_sport_buckets.py` — must run green in CI on this branch (was deferred last session because the local container couldn't import; CI must validate it).

**Contract / behavior tests (frontend):**

- `apps/web/__tests__/home/week-chip.test.tsx` (Group 3.2 cases above).
- `apps/web/__tests__/activities/sport-view-toggle.test.tsx` (Group 3.3 cases above).

**Production smoke checks:**

After deploy, paste verbatim output of (the verify script `.verify_dejan_week.sh` already exists; clone it for an athlete with a calendar entry that mixes a run and a walk, e.g. Dejan):

```bash
# /v1/home for an athlete with a multi-sport day
bash /tmp/vd.sh

# /v1/calendar day for the same date
TOKEN=...  # generate as in OPS_PLAYBOOK
curl -s -H "Authorization: Bearer $TOKEN" "https://strideiq.run/v1/calendar/day/2026-04-22" | python3 -m json.tool

# /v1/activities/summary
curl -s -H "Authorization: Bearer $TOKEN" "https://strideiq.run/v1/activities/summary?days=30" | python3 -m json.tool
```

Expected in handoff: full JSON response (or relevant excerpt) for each, demonstrating that running and non-running figures are separated and the day with the walk + run reports the run as primary.

Paste command output verbatim. No "tests passed" summaries.

---

## Evidence Required in Handoff

1. **Scoped file list** changed (output of `git diff --stat HEAD~N HEAD`).
2. **Test output verbatim**:
   - `pytest tests/test_home_api.py tests/test_home_week_running_separation.py tests/test_calendar_running_separation.py tests/test_activities_summary_sport_buckets.py -v`
   - `npx jest apps/web/__tests__/home/week-chip.test.tsx apps/web/__tests__/activities/sport-view-toggle.test.tsx`
3. **CI run URL** showing all gated jobs green for the head commit.
4. **Production verification output** (the three curl commands above, as JSON).
5. **2.5 audit table**: a markdown table in the handoff listing every site from the 2.5 list with columns: `path:line` | `intent (running-only / all-sport / single-activity)` | `change made (none / doc-comment / behavior fix)` | `regression test (path or N/A)`.
6. **Screenshot or DOM snippet** showing the analytics week chip now matches the home week chip behavior (`+N` and other-sport icons visible on the same fixture day).

---

## Acceptance Criteria

1. The `pytest test_home_api.py` suite has zero failures (the 7 long-standing reds are fixed, not skipped).
2. On `/v1/calendar/day/2026-04-22` for Dejan (or equivalent fixture athlete), the day's running distance does not include the walk's distance, and the planned-run completion status is computed from running miles only.
3. On `/v1/home` for any athlete with a multi-sport day, the response shape from commit `0af4bcd` is preserved AND `other_sport_summary` is rendered on the home page (not just present on the wire).
4. The analytics page (`/analytics`) week chip behaves identically to the home page week chip for the same data: multi-run days show `+N`, days with a walk show a walking icon link, day primary tap goes to the longest run.
5. Every site in the Group 2.5 audit list has either a regression test (if behavior changed) or a doc-comment (if intent confirmed). The audit table is in the handoff.
6. `.gitattributes` is in place; checkout fresh on the droplet shows `.sh` files have LF endings (verify with `file scripts/<some>.sh`).
7. The hot-patch healthcheck script exits non-zero when `/healthz` is not healthy. Demonstrate by running it against a stopped container.
8. CI is green for the final commit before any production deploy.
9. After deploy, the three production curl outputs above are pasted in the handoff and show running/other separation on every surface.

---

## Mandatory: Site Audit Update

`docs/SITE_AUDIT_LIVING.md` must be updated in the same session.

Required update block in the delivery pack:

1. **Exact section(s) updated** in `docs/SITE_AUDIT_LIVING.md`:
   - Calendar surface — note that running and non-running distance are now separate fields.
   - Analytics surface — note that the week chip now mirrors the home chip (multi-run +N affordance and other-sport icon links).
   - Home surface — note that `other_sport_summary` is now rendered (1-line under trajectory).
   - Repo hygiene — note `.gitattributes` is in place.
   - Add a "running vs other separation" row to the contract section listing the four guarantees in Implementation Notes / Core Contracts.
2. **What changed in product truth** (not plan text): every screen that renders "weekly mileage" or "today's mileage" now refers to running only by contract; non-running activity is a separately-rendered, dignified affordance.
3. **Inventory updates**: any new shared component (e.g. `WeekChipDay`) added to the components inventory.

No task is complete until this is done.

---

## Notes for the agent

- The reference implementation for the running/other separation pattern lives in commit `0af4bcd`. Read `apps/api/routers/home.py` lines 78-148 (schemas), the `_runs_by_day` / `_other_by_day` block (~line 3815), the per-day construction loop, and `_other_agg` (~line 3915). Mirror that shape for the calendar work.
- The fixture used for the home regression test (`apps/api/tests/test_home_week_running_separation.py::_dejan_apr22_fixture`) is the right fixture to lift for the calendar regression test. Same activities, same dates.
- If you discover a 4th surface with the same bug during the 2.5 audit, treat it as in-scope (add it to the list, fix it, write its test). Document in the handoff.
- If you discover a surface that is mixing sports intentionally (e.g. cross-training TSS, raw activity counts), the deliverable is a doc-comment explaining the intent — don't change the behavior.
- Founder operating contract is non-negotiable: scoped commits, no push without approval, evidence not claims, CI before local. The just-completed Dejan session pushed under the founder's directive "fix this all the way through live and tested on production"; a similar explicit approval is required from the founder before pushing this batch.
- If anything in this note conflicts with `docs/FOUNDER_OPERATING_CONTRACT.md`, the operating contract wins.
