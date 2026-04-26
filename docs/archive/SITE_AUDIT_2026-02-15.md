# StrideIQ Site Audit — Living Document

Last full audit: February 15, 2026 (founder + vision advisor).
Last updated: March 8, 2026.

---

## What's Working

### Coach Page (/coach)
The strongest surface in the product. Conversations are specific, data-grounded,
cite real numbers, and give verdicts with reasoning. Example output: "Nailed it.
You went a bit longer but kept it genuinely easy — 9:26/mi at 125 bpm is
textbook recovery pace." The sidebar shows real-time athlete data (Fitness CTL,
Form TSB, Durability, Race countdown, This week mileage) and ranked insight
prompts.

**Since Feb 15:** The coach now has access to Living Fingerprint findings
(stored `AthleteFinding` records) via a fast-path query, and `shape_sentence`
is included in `_build_rich_intelligence_context`. The coach can reference
workout structure ("your tempo block held 6:03 at 138 bpm") when shape data
exists. This is backend context enrichment — the chat UI itself is unchanged.

### Calendar (/calendar)
Solid functional training calendar. Real workouts with color coding, plan
overlay with actuals, weekly mileage totals. Right sidebar shows day detail
with planned workout, recent activity card, and coach prompt buttons.
Unchanged since audit.

### Progress (/progress)
Real substance. Race Readiness with predicted splits across distances (18:54 5K,
39:12 10K, 1:26:44 half, 3:00:56 marathon). Fitness Momentum, Recovery
Readiness, Volume Pattern, Consistency Signal — all with "Ask Coach" links.
Recovery & Durability section. Runner Profile with all pace zones. Volume
Trajectory chart. Personal Bests across 8 distances. Last 28 Days vs Prior
28 Days comparison table. CorrelationWeb shows correlation findings as
nodes/edges. RecoveryFingerprint shows recovery curve (before vs now).

**Since Feb 15:** Progress page renders outputs from the Living Fingerprint
pipeline (correlations, recovery data), but there is no dedicated "Living
Fingerprint" or "Training Story" section yet. The Training Story Engine is
deployed in backend but has no frontend surface.

### Analytics (/analytics)
Efficiency Trend chart with 60-day average overlay. Stability Metrics
(Consistency Score 100/100, Easy/Moderate/Hard run counts). Age-Graded
Trajectory showing long-term performance arc. Load → Response chart showing
weekly efficiency deltas. Correlation findings ("What Correlates with Better/
Worse Efficiency"). Race plan banner with progress bar.
Unchanged since audit.

### Training Load (/training-load)
PMC chart (Fitness/Fatigue/Form/TSB). N=1 Personalized zones (not population
defaults). Current state: TSB -11, within typical training range. Daily
Training Stress chart.
Unchanged since audit.

### Coach Intelligence (backend)
The deterministic `compute_coach_noticed` pipeline synthesizes correlations,
home signals, insight feed cards, and hero narrative. The LLM `coach_briefing`
(Opus) generates morning_voice, coach_noticed, workout_why, week_assessment,
checkin_reaction, and race_assessment.

**Since Feb 15 — major backend evolution:**
- **Living Fingerprint deployed.** Four capabilities: weather normalization
  (heat adjustment with combined temp+humidity), shape extraction (phase
  detection, acceleration detection, classification), investigation registry
  (15 investigations with honest gaps), and shape-aware investigations
  (stride progression, cruise interval quality, interval recovery trend,
  workout variety effect, progressive run execution).
- **Finding persistence** with supersession logic (one active finding per
  investigation+type pair). Daily Celery refresh at 06:00 UTC.
- **Shape extraction pipeline** runs on every new activity (Strava post-sync,
  Garmin webhook). Produces `RunShape` (phases, accelerations, summary,
  classification) stored as JSONB on the Activity model.
- **Shape sentences** generated from RunShape data — natural language
  descriptions like "10 miles with a 20-min tempo at 6:03/mi" stored on
  `Activity.shape_sentence`.
- **Shape sentence coverage:** 63% of streamable activities (82% Michael,
  77% BHL, 63% Larry). Remaining suppressions: `cls_none` (15),
  `phases>8` (11), `anomaly` (4).
- **Coach reads shape data** via `generate_yesterday_insight` and
  `_build_rich_intelligence_context` (fast path from stored findings).
- Morning voice and Coach Noticed remain two separate systems with weak
  data sharing between them. This is still a known gap.

### Tools (/tools)
Training Pace Calculator, Age-Grading Calculator, Heat-Adjusted Pace calculator.
Unchanged since audit.

### Settings (/settings)
Strava integration (connected), Garmin file import (525 activities imported),
unit preferences (Miles selected), PRO Plan active, data export/delete.
Unchanged since audit.

### Check-in (/checkin)
Clean slider-based input for Sleep, Stress, Soreness with optional HRV,
Resting HR, and Mindset check. Unchanged since audit.

---

## What's Not Working

### Home Page (/home)
**Since Feb 15:** The gradient ribbon has been replaced. `LastRunHero` now
uses `MiniPaceChart` (effort-colored pace line + area fill) when pace stream
exists, `MiniEffortCanvas` when only effort intensity exists, or metrics-only
when no stream data. The workout card has been stripped to plain text (no Card
wrapper, no icon box, no badge).

**Still broken:** Coach Noticed and morning_voice are still two separate
systems producing overlapping content on the same page. Both render in the
same block — `morning_voice` as `text-base`, `coach_noticed` as `text-sm`
below it. The page is still a vertical stack of sections competing for
attention. The "one paragraph, one voice" vision from the audit has not
shipped.

### Activity Detail Page (/activities/[id])
**Since Feb 15:** The old Splits/Laps chart has been removed. `SplitsChart`
and `SplitsTable` are no longer imported or rendered. The page now shows:
Run Shape Canvas (hero) → Coachable Moments → Reflection Prompt → Perception
Prompt → Workout Type Selector → Metrics Ribbon → RuntoonCard → collapsible
details (Plan Comparison, Why This Run, Run Context Analysis, Compare to
Similar, Narrative Context).

**Still broken:**
- `shape_sentence` is available in the API response but **not rendered
  anywhere on this page**. The activity title is still the generic name
  ("Morning Run", "Lauderdale County Running"). This is the single
  highest-leverage gap — the system knows the workout structure but
  doesn't say it.
- Coachable Moments are still labels with numbers ("Grade Adjusted
  Anomaly: 4.7"), not coached interpretations.
- The Run Shape Canvas exists but is not "F1 telemetry" quality. The pace
  line is flat-colored, not effort-gradient-colored.

### Activities List (/activities)
**Still broken:** Plain metric cards (name, date, distance, pace, duration,
HR). `shape_sentence` is returned by the API but **not rendered in the
frontend**. The frontend TypeScript types don't even include `shape_sentence`.
Every run looks the same. This is where "recognize your run by its shape"
should live — the sentence would replace generic titles and make a week of
training read like a self-writing training log.

### Insights Feed (/insights)
**Still broken:** Active Insights section still shows repetitive and noisy
content. Deduplication and quality filtering have not been implemented.
The ranked "Top Insights" section above it remains better.

### Nutrition (/nutrition)
Minimal placeholder. Unchanged since audit.

---

## The Core Problem (updated)

The intelligence has deepened significantly since Feb 15. The Living
Fingerprint is deployed with weather normalization, shape extraction, 15
investigations, finding persistence, and shape-aware analysis. Shape sentences
describe 63% of streamable activities in natural language. The coach has
richer context than before.

**The gap is still in the last mile.** Shape sentences exist in the database
and API but are invisible to the athlete. The activity list shows "Morning
Run" when the system knows it was "6 miles building from 8:12 to 7:15." The
activity detail page has a generic title when it could say "5 miles with
4 strides." The Training Story Engine has no frontend surface.

The backend-to-frontend gap is now the single biggest constraint on product
value. Every session of backend work widens this gap. The next high-leverage
work is surfacing what already exists.

---

## Priority Fixes — Current State

| # | Fix | Status |
|---|-----|--------|
| 1 | Home: merge Coach Noticed + morning_voice into one voice | **Not started** |
| 2 | Home: replace gradient ribbon | **Done** — MiniPaceChart/MiniEffortCanvas |
| 3 | Home: strip workout card chrome | **Done** — plain text rendering |
| 4 | Activity detail: remove old Splits/Laps chart | **Done** — removed |
| 5 | Activity detail: moments need narrative | **Not started** |
| 6 | Insights feed: deduplicate and curate | **Not started** |
| 7 | Coach Noticed prompt: data-first, no sycophancy | **Not started** |
| 8 | **Surface shape sentences on activity list + detail** | **API wired, frontend not started** |
| 9 | **Surface Training Story on progress page** | **Backend deployed, frontend not started** |
| 10 | **title_authorship detection for Activity Identity Model** | **Not started — requires coverage gate definition (see below)** |

### Open Product Decision: Coverage Gate for Activity Identity Model

Item 10 is upstream of the highest-impact frontend work in the product —
replacing "Morning Run" with "6 miles building from 8:12 to 7:15." It
cannot start until someone defines what "enough coverage" means.

Current coverage (March 8, 2026):

| Scope | Coverage |
|---|---|
| Michael (founder) | 28/34 streamable (82%) |
| BHL | 7/9 streamable (77%) |
| Larry | 14/22 streamable (63%) |
| Demo athlete | 6/21 streamable (28%) |
| All streamable | 55/86 (63%) |

Open questions the founder must answer:

1. **What denominator?** Streamable activities only? All activities?
   Excluding the demo athlete?
2. **Per-athlete or cohort?** Must every athlete clear the bar, or is an
   aggregate threshold sufficient? If per-athlete, Larry (63%) and demo
   (28%) are the gating athletes.
3. **What threshold?** 70%? 80%? Or is the real gate "zero wrong
   sentences served" (precision) rather than "enough sentences exist"
   (recall)?
4. **Is suppression acceptable UX?** When `shape_sentence` is null, the
   activity falls back to its original title. If fallback is clean and
   invisible, then coverage doesn't need to be 100% — it just needs to
   never be wrong when present.

If the answer to #4 is "yes, suppression fallback is fine," then the
coverage gate is actually a **precision gate**: are the sentences that
DO exist trustworthy? Current evidence says yes — no known false
positives after the elevation guard and coverage fixes. In that case,
item 10 is unblocked today and the Activity Identity Model can ship
with graceful degradation (sentence when available, original title
when not).

---

## Backend Capabilities Not Yet Surfaced

These are deployed, tested, and running in production but have no
athlete-facing frontend rendering:

| Capability | Backend Location | Frontend Status |
|---|---|---|
| Shape sentences | `Activity.shape_sentence`, `/v1/activities` response | **Not rendered** |
| RunShape data (phases, accels, classification) | `Activity.run_shape` JSONB | **Not rendered** (canvas uses stream, not shape) |
| Living Fingerprint findings | `AthleteFinding` table, daily refresh | **Not rendered** directly (coach reads them) |
| Weather normalization (heat adjustment) | `Activity.heat_adjustment_pct`, `dew_point_f` | **Not rendered** |
| Training Story Engine | `synthesize_training_story()` | **No frontend surface** |
| Investigation honest gaps | `get_athlete_signal_coverage()` | **Not rendered** |

---

## What The Founder Needs To Hear (updated)

The assessment from Feb 15 still holds: the intelligence is real and getting
deeper. But the gap between backend capability and frontend delivery has
grown. Three weeks of Living Fingerprint, shape extraction, weather
normalization, and coverage fixes have produced substantial backend value —
none of which the athlete can see.

The next work that moves the product forward is not more backend depth.
It is putting shape sentences on screen, giving the Training Story a home
on the progress page, and wiring the Activity Identity Model so that
"Morning Run" becomes "6 miles building from 8:12 to 7:15."

The system already knows what Brady had to type. It just doesn't say it yet.
That sentence was true on Feb 15. It's still true on March 8. The difference
is that on Feb 15, the system barely knew. Now it knows with 63% coverage
and growing. The constraint is no longer capability — it's visibility.
