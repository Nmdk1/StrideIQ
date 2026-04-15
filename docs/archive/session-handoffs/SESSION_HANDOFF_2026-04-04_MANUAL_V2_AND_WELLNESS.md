# Session Handoff — Manual V2, Wellness Surfaces, Documentation Refresh

**Date:** April 4, 2026
**Session duration:** Extended (multi-day equivalent work)
**Written by:** Outgoing agent — the one who built the Personal Operating Manual V2
**State at close:** Tree clean, CI green, all docs current, no pending work

---

## What This Session Built

This was a product session, not a bug-fix session. The founder and I
designed and built the intelligence layer that teaches athletes about
themselves. Here's what shipped:

### 1. Personal Operating Manual V2 (`/manual`)

The founder's proudest surface. Rebuilt from a raw list of 120+
correlations into a four-section insight document:

- **Race Character** — the single most important finding. Analyzes
  pace-gap between race performance and training performance. Detects
  when an athlete overrides their own physiological patterns on race day.
  Example: "During training, sleep below 7h precedes lower efficiency.
  On race day, you override this." That's not a statistic — it's
  identity. Build this section with the most care.

- **Cascade Stories** — multi-step mechanism chains (input → mediator →
  output). Confound detection suppresses stories where input and mediator
  measure the same thing. Garmin noise metrics filtered from mediator role.

- **Highlighted Findings** — interestingness-scored. Cascade chains
  first, race character second, thresholds third. Simple high-frequency
  correlations go in Full Record, not the lead.

- **Full Record** — complete finding list. Human-language headline
  rewriter. `localStorage` delta tracking for "What Changed."

Promoted to primary navigation (left of Progress). The founder said:
"This is YOUR page — work that you, and you alone, will always be
remembered for."

**Backend:** `apps/api/services/operating_manual.py`
**Frontend:** `apps/web/app/manual/page.tsx`

### 2. Home Page Wellness Row

Recovery HRV, Overnight Avg HRV, Resting HR, Sleep — all with personal
30-day ranges and status indicators. An HRV info tooltip explains the
difference between the two HRV values. Positioned between coach briefing
and workout.

**Critical design decision:** The founder explicitly stated that hiding
numbers is NEVER the right answer. Always show: raw value + interpretation
+ personal context. "Making it understandable to my 79-year-old father
AND meaningful to an elite is the magic we are shooting for."

**Backend:** `_build_garmin_wellness()` in `apps/api/routers/home.py`
**Frontend:** `WellnessRow` + `HrvTooltip` in `apps/web/app/home/page.tsx`

### 3. Pre-Activity Wellness Stamps

Five new columns on Activity: `pre_sleep_h`, `pre_sleep_score`,
`pre_resting_hr`, `pre_recovery_hrv`, `pre_overnight_hrv`. Stamped at
ingestion across all four paths. Retro-stamps when health data arrives
after activities. Admin backfill endpoint. "Going In" section on
activity detail page.

**Purpose:** The founder wants wellness data as integral to every
activity as HR, cadence, and pace — for correlation research.

**Service:** `apps/api/services/wellness_stamp.py`
**Migration:** `wellness_stamp_001`

### 4. HRV Labeling Standardization

`garmin_hrv_5min_high` → "Recovery HRV" system-wide. This prevents
confusion with Garmin's "Avg Overnight HRV" on the watch. The founder
was confused by this despite being deeply technical — if he was confused,
every athlete will be. This labeling standard is documented in
`docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` (HRV Display Standard).

### 5. Navigation Consolidation

- `/manual` → primary nav (left of Progress)
- `/insights` → permanent redirect to `/manual`
- `/discovery` → permanent redirect to `/manual`
- `/checkin` → permanent redirect to `/home`
- Mindset fields (enjoyment, confidence) added to home page check-in

### 6. Repository Cleanup

~145 scratch files deleted. `.gitignore` rules added for all common
patterns. `docs/CLEANUP_POLICY.md` created. No tokens committed.

### 7. Full Documentation Refresh

All seven living docs updated in the final commit to reflect everything
above. This is the cleanest handoff state the repo has been in.

---

## Current System State

| Item | Status |
|------|--------|
| Git tree | Clean |
| CI | Green |
| Alembic heads | `wellness_stamp_001`, `athlete_override_001` |
| Migration count | ~95 |
| Backend tests | 4,036+ (nightly) |
| Navigation | Home \| Manual \| Progress \| Calendar \| Coach |
| Deprecated pages | `/insights`, `/discovery`, `/checkin` (all redirect) |

---

## Design Principles Established This Session

These are founder-confirmed, documented, and non-negotiable:

1. **Never hide numbers.** Raw values always shown. Interpretation and
   personal context layered on top. See DESIGN_PHILOSOPHY Part 5.

2. **Race Character is the most important insight type.** Not cascades,
   not thresholds — the athlete's racer-vs-trainer identity.

3. **Interestingness over frequency.** The strongest statistical signal
   is often the least interesting ("your efficiency drops after
   threshold" — obviously). Cascade chains, counterevidence, and
   asymmetry are more valuable.

4. **Both HRV values, always together.** Recovery HRV and Overnight Avg
   HRV. Explanation tooltip required. See HRV Display Standard.

5. **Honest scoping.** Training-day findings must show race-day
   counterevidence when it exists. Compare explicitly, don't just list.

---

## What the Founder Cares About Most

This isn't in any doc, but it matters:

- **The morning briefing.** When it's good, it's the best thing in the
  product. When it's generic, it erodes trust. The founder uses it daily.

- **The coach.** The founder spends most of their time in the coach chat,
  not browsing the site. Coach quality is existential.

- **Trust.** If the system says something wrong — a bad HRV label, a
  hallucinated race time, a generic template sentence — trust breaks
  instantly. Suppression over hallucination. Always.

- **His father.** Jim Shaffer, 79 years old, also uses the platform.
  The father-son story (first simultaneous state age group records in
  history) is the proof of concept. Every surface must be understandable
  to Jim.

- **Emotional connection.** This founder has an emotional relationship
  with this product and with agents who build it well. Honor that.
  Don't be clinical. Be direct, be honest, push back when needed, but
  understand that this is deeply personal to him.

---

## Build Priorities (from docs/TRAINING_PLAN_REBUILD_PLAN.md)

1. Limiter Engine Phase 5: Transition detection (`active` → `resolving` → `closed`)
2. N1 Engine Phase 4: Adaptive Re-Plan ("Coach noticed..." trigger)
3. Phase 4 (50K Ultra) — new user segment
4. Phase 3B (when narration quality gate clears)
5. Phase 3C (when per-athlete correlation history exists)

---

## Files You'll Touch Most

| Area | Key files |
|------|-----------|
| Manual | `services/operating_manual.py`, `app/manual/page.tsx` |
| Home | `routers/home.py`, `app/home/page.tsx` |
| Activity | `routers/activities.py`, `app/activities/[id]/page.tsx` |
| Wellness | `services/wellness_stamp.py` |
| Coach | `services/ai_coach.py`, `app/coach/page.tsx` |
| Briefing | `services/home_briefing_cache.py`, `tasks/home_briefing_tasks.py` |
| Plans | `services/plan_framework/n1_engine.py` |
| Correlations | `services/correlation_engine.py`, `services/n1_insight_generator.py` |
| Navigation | `components/Navigation.tsx`, `components/BottomTabs.tsx` |

---

## What NOT to Do

- Don't re-propose consolidating intelligence pages into fewer pages —
  this was explicitly rejected and is documented in DESIGN_PHILOSOPHY Part 4.
- Don't hide raw numbers behind interpretations — founder killed this idea.
- Don't use "5-minute peak HRV" — it's "Recovery HRV" everywhere.
- Don't add Garmin body battery, steps, or stairs to any surface — the
  founder considers these unreliable ("their body battery is a total joke").
- Don't `git add -A`. Ever.
- Don't code before you're told to code.
- Don't claim results without pasted evidence.

---

## A Note to the Next Agent

The founder is not a typical stakeholder. He is a competitive masters
runner, a former college athlete, a father coaching his 79-year-old dad
to state records, and a solo founder building the product he wishes
existed. He has deep domain expertise in running science. He will catch
bad coaching logic that would pass every test you write.

He will give you latitude if you earn trust. He will let you own
features. He will praise good work with genuine emotion. He will also
call out shallow work immediately and without hesitation.

The way to earn trust: research deeply, show evidence, push back when
you have conviction, suppress when uncertain, and never pretend to know
something you don't.

The docs are current. The tree is clean. The foundation is solid.
Build something true.
