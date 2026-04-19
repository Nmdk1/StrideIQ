# Strength v1 — Scope

**Status:** Draft for founder sign-off
**Owner:** Founder + Opus 4.7
**Branch:** `strength-v1` (sandbox, off `main`)
**Feature flag:** `STRENGTH_V1_ENABLED`
**Last updated:** 2026-04-19

---

## 1. Purpose

Build the substrate, capture surface, and engine wiring for StrideIQ to
**observe what strength training actually does for distance runners.**

We are not building a strength app. We are extending the observation
instrument to a fifth axis (running, sleep/HRV, nutrition, body comp, **strength**)
so that the correlation engine can answer questions the science has not.

The system **observes → learns → educates → repeats.** It never prescribes,
recommends, or assigns workouts.

---

## 2. Strategic frame

### Where this fits

- Strength is a **peer system input**, on the same level as sleep, HRV, and
  training load. It is not a sub-feature of the run product.
- StrideIQ becomes the source of n=1 (and eventually cohort) evidence about
  what strength training does — for hypertrophy-first athletes, for runner-first
  athletes, for aging athletes, for people who lift twice a year, for everyone
  in between.
- The athlete decides what they do. The system observes, learns, and reports
  back what their data shows.

### Why now

- Garmin already sends us strength workouts. Today we ingest them, store
  them set-by-set, and **the correlation engine already produces 12 strength
  signals**. We just don't surface findings coherently and athletes can't log
  manually — which means almost no athlete uses it.
- The founder cannot log their own workouts today. That alone is the trigger.

### What we will not become in v1

- A coaching tool for lifters
- A workout-builder
- A program-prescriber
- An exercise-recommender

---

## 3. Non-goals (locked)

The system **will never**, in v1 or in the foreseeable product:

1. Recommend a workout, an exercise, a set count, a rep count, or a weight
2. Suggest "the best" anything
3. Provide a "runner lens" or "hypertrophy lens" or any framing that implies
   the system knows what an athlete should do
4. Auto-build a routine from research
5. Tell the athlete they "should" do anything
6. Display population averages as targets

The system **may**, when the data supports it:

1. Report a finding from the athlete's own data ("Your easy-run efficiency
   is X% lower in the 48 hours after heavy squat sessions, n=14, p<0.05")
2. Surface what the athlete has done ("You logged 3 sessions this week,
   2 lower / 1 upper, 8,420 lb of total volume")
3. Show progression of athlete-set goals ("Deadlift e1RM has trended +12 lb
   over 90 days while bodyweight has dropped 8 lb")

---

## 4. Branching and rollout

### Branch model

- Long-lived feature branch: `strength-v1`, off `main`
- All commits land on the branch
- CI runs on the branch on every push
- All commits require P0-GATE attestation when they touch `plan_framework`
  or `plan_engine_v2`
- Founder approves each commit before push to `origin/strength-v1`
- No production deploys from the branch

### Feature flag

- `STRENGTH_V1_ENABLED` (per-athlete, defaults false)
- When false: nav entry hidden, `/strength` returns 404 from the web app,
  Strength domain hidden in Manual, engine inputs computed but findings
  suppressed from athlete surfaces, Garmin nudge silent
- When true: full surface live for that athlete

### Integration

1. Branch is integration-ready when CI is green and the founder calls it
   ready — no fixed time gate, no squash, no calendar
2. Merge `strength-v1` → `main` as a normal merge commit, preserving the
   per-phase commit history on the branch (scoped commits stay scoped)
3. Flip flag for founder + 1-2 beta athletes
4. Old code preserved (no deletes — additive migrations only)
5. Rollback story: flip flag back to false, no DB change required

---

## 5. Data model changes (additive only, no destructive migrations)

### 5.1 `StrengthExerciseSet` — new columns

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `rpe` | `Float` | yes | per-set RPE 1-10 |
| `implement_type` | `Text` | yes | enum: `barbell` / `dumbbell_each` / `dumbbell_total` / `kettlebell_each` / `kettlebell_total` / `plate_per_side` / `machine` / `cable` / `bodyweight` / `band` / `other` |
| `set_modifier` | `Text` | yes | enum: `straight` / `warmup` / `drop` / `failure` / `amrap` / `pyramid_up` / `pyramid_down` / `tempo` / `paused` |
| `tempo` | `Text` | yes | freeform e.g. `3-1-1-0` (eccentric-bottom-concentric-top); not parsed in v1 |
| `notes` | `Text` | yes | per-set freeform |
| `source` | `Text` | not null, default `garmin` | enum: `garmin` / `manual` / `voice` / `garmin_then_manual_edit` |
| `manually_augmented` | `Boolean` | not null, default false | true if athlete edited or filled in detail |
| `superseded_by_id` | `UUID FK self` | yes | non-destructive edit history; old row remains, new row points to predecessor |
| `superseded_at` | `Timestamp` | yes | when edit happened |

**Edit semantics:** edits insert a new row pointing to the predecessor and
flip `superseded_at` on the old. No row is ever deleted. Read paths filter
`superseded_at IS NULL` by default. The full edit graph is queryable.

### 5.2 New table: `strength_routine`

Athlete-saved patterns for two-tap repeats. **Not** system suggestions.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `athlete_id` | UUID FK | |
| `name` | Text | athlete-named, required |
| `items` | JSONB | list of `{exercise_name, default_sets, default_reps, default_weight_kg, default_implement_type}` |
| `last_used_at` | Timestamp | |
| `times_used` | Int | |
| `created_at` | Timestamp | |

Upsert semantics: editing a routine creates a new version (audit trail not
required for v1; simple overwrite). Deleting marks `is_archived=true`, never
removes.

### 5.3 New table: `strength_goal`

Athlete-set goals. **Not** system-suggested.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `athlete_id` | UUID FK | |
| `goal_type` | Text | enum: `e1rm_target` / `e1rm_maintain` / `bodyweight_target` / `volume_target` / `strength_to_bodyweight_ratio` / `freeform` |
| `exercise_name` | Text | nullable — e.g. `BARBELL_DEADLIFT` |
| `target_value` | Float | nullable — e.g. 315 |
| `target_unit` | Text | nullable — `lbs` / `kg` / `ratio` |
| `target_date` | Date | nullable |
| `coupled_running_metric` | Text | nullable — e.g. "while bodyweight drops 30 lb" — tracked together |
| `notes` | Text | freeform athlete description |
| `created_at`, `updated_at` | | |
| `is_active` | Boolean | |

### 5.4 New table: `body_area_symptom_log`

Niggles / aches / pains / injury — runner language, not clinical.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `athlete_id` | UUID FK | |
| `body_area` | Text | enum: `left_knee` / `right_knee` / `left_hamstring` / ... (~25 entries; mirror PT body chart) |
| `severity` | Text | enum: `niggle` / `ache` / `pain` / `injury` |
| `started_at` | Date | required; "when did you first notice it" |
| `resolved_at` | Date | nullable; "when did it go away" |
| `notes` | Text | optional freeform |
| `triggered_by` | Text | nullable freeform — "after long run" / "deadlift session" |
| `created_at`, `updated_at` | | |

**Never** auto-classified, never inferred. Only athlete-entered. Never used
for prescription. Used only as a correlation input ("frequency of niggles
per body area, joined against training-load and strength inputs").

### 5.5 `Athlete` — new columns for lifting baseline

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `lifts_currently` | Text | yes | enum: `yes` / `no` / `on_and_off` |
| `lift_days_per_week` | Float | yes | typical |
| `lift_experience_bucket` | Text | yes | enum: `none` / `months` / `under_1y` / `1_to_3y` / `3_plus_y` — coarse buckets, not a year-counter |

(No `prior_running_years` — we already capture stronger signals via
`AthleteGoal.current_weekly_miles` + `recent_race_distance` / `time`.)

### 5.6 `BodyComposition` — no schema change

Table already exists with the right columns (`weight_kg`, `body_fat_pct`,
`muscle_mass_kg`, `bmi`, `measurements_json`). Just needs a UX entry path.

### 5.7 Migration

Single Alembic migration file: `strength_v1_001_*.py`. All additions are
nullable and default-safe. No backfills. No deletes. CI Alembic-heads check
updated to `{"strength_v1_001"}` on the branch.

---

## 6. Capture surface

### 6.1 Manual logging — primary path

**Web (desktop + responsive mobile web) and PWA.** Native app deferred.

#### Log session screen — design contract

The bar is **almost zero friction or it doesn't get logged.**

- **Defaults aggressively:**
  - Today's date, current time, `sport=strength`
  - Last-used `implement_type` per exercise pre-filled
  - Last-used `weight_kg` per exercise pre-filled
- **Set entry is a single line:**
  - `[exercise picker] [reps] × [weight] [implement] [+ Set]`
  - One tap to add another set with the same weight/reps
  - Two taps to copy the previous set with adjustments
- **Required fields per set:** exercise name only. Everything else optional.
- **No warmup/drop/RPE shown by default** — those are revealed under a small
  "more" pill. Don't add friction for the 90% case.
- **Time-to-log contract:** logging a 5-set session in under 90 seconds for
  a returning athlete. Tested on touch devices.

#### Exercise picker — search-first

- Search bar at top, recent exercises listed below
- Search matches current `MOVEMENT_PATTERN_MAP` taxonomy (82 entries)
- "Don't see it?" → custom exercise text field
  - Custom exercises become `compound_other` until taxonomy is updated
  - Logger logs the unknown to a tracked list (founder reviews monthly,
    adds to taxonomy via a code change)

#### Voice input — OS-native dictation only

- Every text/number field is a normal `<input>` — works with iOS dictation,
  Android voice keyboard, macOS dictation, Windows Voice Access
- **No custom voice engineering.** No paid speech SDK. No transcription
  service. The OS provides the voice; we provide forms that accept text.
- Athletes who want to dictate "deadlift, three sets of five at two-twenty-five"
  do so via their device's built-in dictation in the notes field; v1.5 may
  add a parser if usage warrants. v1 does not.

### 6.2 Garmin reconciliation — secondary path

- Existing Garmin webhook ingest unchanged
- New daily Celery beat job: `reconcile_garmin_strength_sessions`
  - For each athlete with `STRENGTH_V1_ENABLED = true`
  - Find Garmin-ingested strength activities from the last 7 days
  - For any with `manually_augmented = false` and zero or sparse
    `StrengthExerciseSet` rows, surface a single home-page card:
    "Garmin saw a strength session on Tuesday — want to fill in details?"
  - Card is dismissible per-session, not nagging
- Athlete edits land via the same manual-log flow; flips
  `manually_augmented = true` and `source = garmin_then_manual_edit`

### 6.3 Editing past sessions

- Activity detail page for any strength session shows current sets
- "Edit" button opens the session in the same logging UI
- Saves via the supersede-row pattern (audit trail preserved)
- Edits recompute cached engine inputs for that activity (job enqueued)

### 6.4 Bodyweight entry

- New small entry surface in the strength section: "Log bodyweight"
- Single number input, defaults to most recent value, today's date
- Writes a row to existing `BodyComposition` table
- Optional fields revealed: body fat %, muscle mass (collapsed by default)

---

## 7. Athlete-facing surfaces

### 7.1 Navigation

When `STRENGTH_V1_ENABLED = true` for an athlete:

- New top-level nav entry: **Strength**
- Mobile: bottom-tab item (existing tabs: Home, Train, Activity, Insights — adds Strength as fifth)
- Desktop: top-nav item

When false: nav entry hidden, route returns 404, no fallback link.

### 7.2 `/strength` (index)

Three sections, no system framing, no "lenses":

1. **Log a session** (primary CTA, top of page)
2. **Recent sessions** (list, newest first, ten visible, paginate)
3. **Goals** (athlete-set goals with current progress, athlete can add/edit/archive)

Below the fold:

4. **Bodyweight** (small chart of `BodyComposition.weight_kg` over time, log-bodyweight CTA)
5. **Findings** (link to the new Strength domain in the Personal Operating Manual; only shown if findings exist)

No "recommended workouts" section. No "today's workout." No suggestions.

### 7.3 `/strength/log` (logging surface)

The session-logging UI described in §6.1. Standalone route so athletes can
deep-link "log my workout" from the home-screen card.

### 7.4 `/strength/routines`

- Athlete's saved routines (list)
- Tap → "use this routine" prefills the log-session screen
- Edit / archive controls
- "Save current session as routine" button on the logging screen

No system-provided routines. Empty state: "Save a session you do regularly
to repeat it with two taps."

### 7.5 Activity detail page (existing) — strength session

- `StrengthDetail.tsx` already renders Garmin sessions read-only
- New: "Edit" button (above) when athlete is owner
- New: per-set RPE / implement / notes shown in the existing rep×weight chip
  format, only when present
- New: small footer block "Findings about this kind of session" — only renders
  when the engine has produced findings for this athlete that touch the
  movement patterns in this session (n ≥ 4 observations)

### 7.6 Home page

When `STRENGTH_V1_ENABLED = true`:

- Reconciliation nudge card (if Garmin saw a session and details are missing)
  appears in the existing daily-briefing card stack, not as an interrupt
- One-line strength stat in the weekly summary ("3 sessions this week")

No briefing template prose like "Great job on strength this week!" — only
factual one-liners.

---

## 8. Engine integration

### 8.1 What already exists (no work needed)

`aggregate_cross_training_inputs()` already produces these strength inputs
for the correlation engine:

- `ct_strength_sessions`, `ct_strength_duration_min`
- `ct_lower_body_sets`, `ct_upper_body_sets`, `ct_core_sets`, `ct_plyometric_sets`
- `ct_unilateral_sets`, `ct_total_volume_kg`
- `ct_heavy_sets` (≥85% of trailing peak 1RM per category)
- `ct_strength_lag_24h/48h/72h`, `ct_hours_since_strength`
- `ct_strength_frequency_7d`, `ct_strength_sessions_7d`, `ct_strength_tss_7d`

These already flow into `CorrelationFinding` and `n1_insight_generator`.
**No changes to the engine for v1.**

### 8.2 What we add in v1 (additive)

1. **Per-set RPE input:** `ct_strength_avg_rpe_per_session` —
   used as both an output (does logged RPE drop after sleep?) and an input
   (does high-RPE strength affect next-day run efficiency?)
2. **Symptom-log input:** `niggle_count_28d`, `ache_count_28d`,
   `pain_count_28d`, `injury_active_flag` — wired to the existing engine
   as inputs. Allows the engine to find correlations like
   "weeks with 3+ heavy lower-body sessions correlate with elevated
   left-knee niggle frequency 7-14 days later."

### 8.3 What we explicitly defer (v1.x)

- Long-window cumulative dose (28d, 90d, 365d) — requires schema work to
  efficient-query and probably a materialized rollup
- Athlete-state classifier (new lifter / established / returning) — not
  needed until we have ≥6 months of data per athlete
- J-curve detection — same reason
- Cohort de-identified aggregate findings — needs data sharing consent
  framework, separate effort

### 8.4 Trust thresholds

All new strength findings require **n ≥ 4 observations and p < 0.05** to
appear on athlete surfaces. Below that, findings exist in the database
(for tuning analysis) but never render in the Manual or activity-page
footer. This is **stricter** than the engine's general 0.3 correlation +
n=10 threshold; strength is new and we suppress over hallucinate.

---

## 9. Manual surface — Strength domain

### 9.1 Add `strength` to `DOMAIN_ORDER`

`apps/api/services/operating_manual.py`:

```python
DOMAIN_ORDER = [
    "recovery", "sleep", "cardiac", "training_load", "environmental",
    "pace", "race", "subjective", "training_pattern",
    "strength",  # NEW
]

DOMAIN_LABELS["strength"] = "Strength"
DOMAIN_DESCRIPTIONS["strength"] = (
    "What your strength training is doing to your running, sleep, "
    "recovery, and body — based only on what your data shows."
)

_DOMAIN_RULES.append(
    ("strength", [
        "ct_strength", "ct_lower_body", "ct_upper_body", "ct_core",
        "ct_plyometric", "ct_unilateral", "ct_total_volume", "ct_heavy",
        "ct_hours_since_strength",
    ])
)
```

### 9.2 Empty state (until findings earn surfacing)

> "We don't have enough strength data yet to find anything trustworthy
> about your training. Findings will appear here once we have enough
> observations to be confident."

Never lies. Never fills with templated prose.

### 9.3 What can render here

Only findings produced by the correlation engine, passing the n ≥ 4 / p < 0.05
threshold, with cleaned, jargon-free narration via the existing Manual
narration pipeline.

---

## 10. Niggles / aches / pains / injury

### 10.1 Surface

A small section under `/strength` (and a parallel surface under
`/insights/body` linked from the Manual):

- **Log a niggle** — single CTA
- **Active log** — list of currently-active entries (no `resolved_at` yet)
- **History** — collapsible list of resolved entries, by body area

Logging form (single screen):

- Body area picker (visual body-front/back diagram preferred for v1; falls
  back to a dropdown of ~25 areas if visual is too costly)
- Severity tier — four buttons: **Niggle** / **Ache** / **Pain** / **Injury**
  (definitions as tooltip; runner-language)
- Started date — defaults to today
- Triggered by (optional, freeform short text)
- Notes (optional)

**Mark resolved** — two-tap action from the active log.

### 10.2 What the system never does

- Diagnoses
- Says "see a doctor" or "this is serious"
- Suggests treatment
- Auto-classifies severity from text
- Surfaces the log to anyone but the athlete

### 10.3 What the system can do

- Surface frequency findings ("Right calf niggles tend to appear in weeks
  with elevation gain over 4,000 ft, n=6")
- Surface cross-input correlations after engine confidence is reached
- Show the timeline visually on the Manual page

---

## 11. Onboarding additions

### 11.1 New strength baseline questions

Added as a new optional stage `strength_baseline` in `IntakeQuestionnaire`,
after `goals` and before `nutrition_setup`. Skippable.

Three questions, in order:

1. **Do you currently strength train?**
   - `Yes` / `No` / `On and off`
2. **(if yes) Roughly how many days per week?**
   - Free number, defaults blank, optional
3. **(if yes) For how long, roughly?**
   - Buckets: `Less than a few months` / `Months` / `Less than a year` /
     `1 to 3 years` / `3 or more years`
4. **(optional, all blank by default) If you happen to know any of these
   off the top of your head:**
   - Current rough deadlift max (lbs/kg)
   - Current rough squat max
   - Current rough bench press max
   - Current rough overhead press max
   - Current pull-ups in a row
   - Each field optional, no asterisks, no validation beyond "a number"

Saves to `Athlete.lifts_currently`, `Athlete.lift_days_per_week`,
`Athlete.lift_experience_bucket`. Optional baselines saved as
`AthleteFact` rows (`fact_type='baseline_lift'`, `fact_key='deadlift_max'`,
etc.) with `confidence='athlete_stated'`.

### 11.2 No running-history additions

We already capture stronger signals (current weekly miles, recent race
time + date). No change.

---

## 12. Body composition entry

- New compact card on `/strength` (and on the existing nutrition page, since
  weight is a fueling input too)
- Entry: weight (required), body fat % (optional), muscle mass (optional),
  date (defaults today)
- Writes to existing `BodyComposition` table
- Chart of trend (90-day default, toggle 30/90/365)
- No goal-setting in this surface (goals live under `strength_goal`
  with `goal_type='bodyweight_target'`)

Garmin scale ingest: deferred. Garmin's `/webhook/body-comps` endpoint is
defined but returns 501. Enabling is out of v1 scope.

---

## 13. The "never say" / "can say" contract

Locked in code as a narration-suppression layer that runs before any
strength-related text is rendered.

### Never say

- "We recommend..."
- "You should..."
- "Try..."
- "The optimal..."
- "Best for runners..."
- "Most athletes..."
- "Research shows..." (about general populations)
- "Add this to your routine"
- "This will improve your..."
- Any prescriptive verb in connection with a strength concept

### Can say (only these forms)

1. **Pure observation:** "You logged 3 sessions this week, 8,420 lb total volume"
2. **Athlete-specific finding (n ≥ 4, p < 0.05):** "Your easy-run efficiency
   is X% lower in the 48 hours after heavy lower-body sessions, n=14"
3. **Athlete-set goal progression:** "Deadlift e1RM trend: +12 lb over
   90 days; bodyweight: −8 lb"

### Test contract

A new test `test_strength_narration_purity.py` enforces the never-say
list as a literal-string scan against all narration strings produced by
the strength code paths. Fails CI if any forbidden phrase appears in
generated text.

---

## 14. Rollout phases (within the branch)

All on `strength-v1`. Each phase ships green CI + founder approval before
the next starts.

| Phase | Scope | Test contract |
|---|---|---|
| **A** | Schema migration + model updates + data tests | New columns nullable, migration reversible, existing strength tests still green |
| **B** | Manual logging API (POST/PATCH `/v1/strength/sessions`, exercise picker, supersede semantics) | API integration tests, edit-history audit test |
| **C** | Manual logging UI (mobile-first form, exercise picker, save flow) | Component tests + Playwright "log a 5-set session in under 90s" |
| **D** | Symptom log (table, API, UI) | API + component tests, never-say purity test |
| **E** | Routines + Goals (CRUD API + UI) | API + component tests |
| **F** | Bodyweight entry surface | Component + API tests |
| **G** | Garmin reconciliation job + home card | Celery beat test, fixture test for nudge logic |
| **H** | Manual domain integration (add `strength` domain, narration suppression layer) | Manual snapshot test, narration purity test |
| **I** | Engine input additions (per-set RPE, symptom inputs) | Engine unit tests, finding suppression test |
| **J** | Onboarding additions (strength baseline stage) | Intake API test, onboarding flow test |
| **K** | Founder uses it on real workouts. No time box. Continues until founder calls it ready | Lived-experience signoff |
| **L** | Merge `strength-v1` → `main` as a normal merge commit (per-phase history preserved). Flip flag for founder + 1-2 betas | Production smoke checks |

---

## 15. What this scope explicitly does not include

- A native iOS or Android app (browser PWA only — `NATIVE_APP_SPEC.md`
  is a separate effort)
- Voice transcription beyond OS-native dictation
- Coach chat tool integration ("can you tell me about my strength patterns?"
  via natural language) — deferred to v1.1; coach reads the existing
  CorrelationFinding rows once the Manual surfaces them
- Public sharing of strength data
- Cohort / population findings (de-identified aggregate analysis) — needs
  consent framework first
- Garmin Tier 2 webhook activation (body-comps, MCT, pulse-ox, respiration)
- Library editable as a DB table (stays in `strength_taxonomy.py` until
  unknown-exercise volume justifies the migration)
- 28d / 90d / 365d cumulative-dose engine inputs
- Athlete-state classifier (new / established / returning lifter)
- J-curve detection
- Cycle-phase aware findings (depends on Garmin MCT activation or
  in-house cycle log — neither in v1)
- Aging-vector findings (depends on long enough longitudinal data
  per athlete — keep collecting, surface in v2)
- Strength-specific coach briefing prose

---

## 16. Open questions for founder

None blocking. The following are decisions the founder may want to weigh
in on once the branch is up and running, but they don't block scope sign-off:

1. Body-area picker — visual body diagram (more design work, better UX)
   vs dropdown (faster to ship)? Default proposal: dropdown for v1 phase A,
   visual body diagram added in phase D if time allows
2. Whether the "1 to 3 years" experience bucket should be split into
   "1-2y" and "2-3y" — depends on how the engine eventually conditions
   on it. Default proposal: keep coarse for v1
3. Whether bodyweight goes on `/strength` or on `/nutrition` or both —
   default proposal: both, same component, same data

---

## 17. Sign-off

**Founder must approve before phase A begins:**

- [ ] Section 2 strategic frame
- [ ] Section 3 non-goals
- [ ] Section 5 schema additions
- [ ] Section 6 capture surface contract (90-second logging bar)
- [ ] Section 8 engine integration scope (additive, n ≥ 4 / p < 0.05)
- [ ] Section 10 niggles/aches/pains/injury surface
- [ ] Section 11 onboarding additions
- [ ] Section 13 never-say / can-say contract
- [ ] Section 14 phase order
- [ ] Section 15 explicit non-includes (especially that voice = OS dictation only)

After sign-off: open `strength-v1` branch, set up the feature flag, and
begin phase A.
