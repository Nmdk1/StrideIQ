# Builder Note — Progress Page Fixes (Hero, Acronyms, Sweep)

**Date:** March 3, 2026
**Assigned to:** Builder
**Urgency:** High — founder is looking at this page right now
**Advisor sign-off required:** No

---

## Before Your First Tool Call

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. This builder note

---

## Objective

Fix four issues on the Progress page that the founder identified on
live production today.

---

## Fix 1: Hero Layout — Full Width

**Problem:** The hero section uses a side-by-side flex layout that puts
the headline left and stats right. On production it looks "slapped
together" — the headline is cramped and the stats float awkwardly.

**File:** `apps/web/components/progress/ProgressHero.tsx`

**Fix:** Change the hero to a stacked layout:
- Headline + date label: full width
- Stats row: full width below the headline, centered or left-aligned

The current layout (line 101-110) uses:
```
display: 'flex',
justifyContent: 'space-between',
alignItems: 'flex-start',
flexWrap: 'wrap',
```

Change to:
```
display: 'flex',
flexDirection: 'column',
gap: 24,
```

The stats container (line 142) should become a full-width row:
```
display: 'flex',
gap: 32 (or more),
alignItems: 'center',
```

Keep the max-width constraint on the outer container. The headline
should breathe. The stats should feel like a data bar, not a sidebar.

---

## Fix 2: No-Race Fallback Hero

**Problem:** When no active training plan with a goal race exists,
the hero defaults to generic text. The founder asked "what happens
when no race?" multiple times during spec review and this wasn't
handled properly.

**File:** `apps/api/routers/progress.py`, lines 2093-2112

**Current behavior (lines 2098-2100):**
```python
date_label = f"{day_name}, {date_str}"
stat_third = HeroStat(label="Weeks tracked", value=str(weeks_tracked), color="orange")
```

And the headline is always:
```python
headline=f"Your progress over {weeks_tracked} weeks.",
headline_accent="Here's what the data shows.",
```

**Fix:** The no-race hero needs to be meaningful on its own:

When no race:
- `date_label`: `"{day_name}, {date_str}"`  (just the date, no race)
- `headline`: Something about what the data has built. Use the CTL
  delta: if CTL grew significantly, say so. If the athlete has many
  findings, reference the knowledge. Example logic:
  - CTL grew 10+: `f"Fitness surged: {ctl_first} to {ctl_now} in {weeks_tracked} weeks."`
  - CTL stable: `f"{weeks_tracked} weeks of data. {len(findings)} patterns discovered."`
  - New user: `f"Building your physiological profile."`
- `headline_accent`: Reference the N=1 nature:
  - With findings: `"Your data reveals what drives your performance."`
  - Without findings: `"Every session teaches the system about your body."`
- `stat_third`: `HeroStat(label="Patterns found", value=str(len(findings)), color="orange")`

When race exists (current behavior, keep but improve):
- Same as now but use the race-specific CTL framing
- The LLM pass can still override headline/accent

**Important:** The hero must look intentional in both modes. The no-race
mode is the DEFAULT experience for most users. It's not a fallback — it's
the primary mode.

---

## Fix 3: Acronym Explanations on First Use

**Problem:** The "What the Data Proved" section shows text like:
- "High form (tsb) reduces personal bests within 6 days"

The acronym rule is a global project rule stated many times:
**First use on any athlete-facing surface must be the full term with
the acronym in parentheses.** The founder should not have to repeat this.

**File:** `apps/api/routers/progress.py`

**Root cause:** `_METRIC_LABELS` (line 1973-1999) already has the right
format: `"tsb": "Form (TSB)"`, `"ctl": "Fitness (CTL)"`, etc. But
`_build_headline()` (line 2010-2015) lowercases the result:

```python
inp = _humanize_metric(finding.input_name)
return f"High {inp.lower()} {verb} ..."
```

`inp.lower()` turns "Form (TSB)" into "form (tsb)". The parenthetical
acronym survives but it's all lowercase, which looks broken.

**Fix:** Don't lowercase the full label. Either:
- Keep the label's original casing: `f"High {inp} {verb} {out} {lag}"`
- Or capitalize properly: `f"High {inp.lower().split('(')[0].strip()} ({inp.split('(')[1] if '(' in inp else ''}) {verb}..."`

Simplest correct approach — don't lowercase at all, just use the label
as-is since it's already human-readable:

```python
def _build_headline(finding: CorrelationFinding) -> str:
    inp = _humanize_metric(finding.input_name)
    out = _humanize_metric(finding.output_metric)
    verb = "improves" if finding.direction == "positive" else "reduces"
    lag = f"within {finding.time_lag_days} day{'s' if finding.time_lag_days != 1 else ''}" if finding.time_lag_days > 0 else "same day"
    return f"High {inp} {verb} {out} {lag}"
```

This produces: "High Form (TSB) reduces Personal Bests within 6 days"

That reads correctly. The acronym is explained in parentheses on first
use.

**Also check:** The Correlation Web node labels use `_humanize_metric()`
too (line 2042-2044). Those should already be correct since they don't
lowercase. Verify.

**Also check:** Any LLM-generated text (`_generate_knowledge_llm`) that
might introduce raw acronyms. The prompt should instruct: "Always use
full term with acronym in parentheses on first use."

---

## Fix 4: Trigger Full Correlation Sweep

**Problem:** Effort classification just shipped. The correlation
aggregates now return data for all 9 metrics. But the sweep hasn't
run yet with the new data, so the Progress page only shows 2 emerging
patterns.

**Action:** Trigger the daily sweep manually for the founder:

```bash
docker exec strideiq_api python -c "
from database import SessionLocal
from models import Athlete
from tasks.correlation_tasks import run_daily_correlation_sweep
db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
run_daily_correlation_sweep.delay(str(user.id))
print('Sweep triggered')
db.close()
"
```

Or if Celery isn't available, call `analyze_correlations()` directly
for each output metric:

```bash
docker exec strideiq_api python -c "
from database import SessionLocal
from models import Athlete
from services.correlation_engine import analyze_correlations
db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
metrics = ['efficiency', 'pace_easy', 'pace_threshold', 'completion',
           'efficiency_threshold', 'efficiency_race', 'efficiency_easy',
           'pb_events', 'race_pace']
for m in metrics:
    try:
        r = analyze_correlations(str(user.id), days=90, db=db, output_metric=m)
        corrs = r.get('correlations', [])
        print(f'{m}: {len(corrs)} correlations found')
    except Exception as e:
        print(f'{m}: error - {e}')
db.close()
"
```

After the sweep, check the Progress page again — the Correlation Web
should be denser and more proved facts should appear.

---

## Evidence Required in Handoff

1. Screenshot of hero layout (desktop) — full width, stats below
2. Screenshot/output showing no-race hero mode (temporarily remove
   goal race from test plan or test with a user who has no plan)
3. Before/after of proved facts text showing proper acronym casing
4. Sweep output showing correlation counts per metric
5. Correlation Web screenshot showing new edges (if any surfaced)

---

## Acceptance Criteria

- [ ] Hero headline spans full width on desktop
- [ ] Stats row displays as a row below the headline, not beside it
- [ ] No-race hero shows meaningful content (not generic placeholder)
- [ ] All acronyms on the page use full term with abbreviation in
      parentheses on first use (TSB, CTL, ATL, HRV, HRR, RPE)
- [ ] Full correlation sweep has been triggered for the founder
- [ ] All existing tests pass

---

## Mandatory: Site Audit Update

Update `docs/SITE_AUDIT_LIVING.md` post-deploy.
