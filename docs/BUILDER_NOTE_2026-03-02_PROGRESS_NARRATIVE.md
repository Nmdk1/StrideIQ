# Builder Note — Progress Page Phase 1: Ship the Moat

**Date:** March 2, 2026
**Spec:** `docs/specs/PROGRESS_NARRATIVE_SPEC_V1.md`
**Design target:** `docs/references/progress_page_mockup_v2_2026-03-02.html`
**Design principle:** `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` Part 1

---

## Before Your First Tool Call

Read these in order:

1. `docs/FOUNDER_OPERATING_CONTRACT.md` — how you work (non-negotiable)
2. `docs/PRODUCT_MANIFESTO.md` — the soul
3. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` — visual doctrine
4. `docs/specs/PROGRESS_NARRATIVE_SPEC_V1.md` — this feature's spec
5. `docs/references/progress_page_mockup_v2_2026-03-02.html` — open in browser, this IS the design
6. This builder note — scope, contracts, tests

**Canonical mockup:** `docs/references/progress_page_mockup_v2_2026-03-02.html`
There is an older v1 mockup in the same folder — ignore it. v2 is the only
design target. If any doc references a different mockup filename, it is stale.

---

## Objective

Kill the current progress page (12 disjointed text cards, embarassingly
generic) and replace it with three sections that show what no competitor
can show: the system's accumulated knowledge about this specific human.

**Phase 1 ships:** Hero + Correlation Web + What the Data Proved.
All three use data that exists today. No new backend computation needed
beyond querying `CorrelationFinding` and `TrainingLoadCalculator`.

---

## Scope

### In scope

1. **New endpoint:** `GET /v1/progress/knowledge`
   - Deterministic data assembly only (< 500ms) for correlation graph data
   - LLM pass for hero headline + per-finding implication text (< 5s total)
   - Redis caching: `progress_knowledge:{athlete_id}`, 30min TTL
   - Graceful fallback: all data renders with deterministic text if LLM fails

2. **Frontend — complete page replacement:**
   - `ProgressHero` — gradient-backed header with CTL stats strip, coach headline
   - `CorrelationWeb` — D3 force-directed graph of confirmed N=1 correlations
   - `WhatDataProved` — expandable fact list with evidence + confidence tiers
   - `PatternsForming` — indicator shown when no findings exist yet

3. **New dependency:** `d3` (npm) — force simulation for the correlation web

4. **Old components removed from progress page:**
   - SparklineChart, BarChart, HealthStrip, FormGauge, PairedSparkline,
     CapabilityBars, CompletionRing, StatHighlight — none of these render
     on the new page. Keep the component files (other pages may use them)
     but remove all imports from `progress/page.tsx`.

### Out of scope (Phase 2-3)

- Physiological Portrait (needs TSB-zone correlation job)
- Training Block Timeline (needs block timeline endpoint)
- Capability Expansion (needs prediction history snapshots)
- Recovery Fingerprint (needs metric timestamping)
- Prediction Space (needs `/v1/predictions/scenario`)
- NarrativeFeedback model / feedback endpoint (defer until page proves itself)
- Old `/v1/progress/narrative` endpoint — leave for now, do not break

---

## Data Sources

| Source | What it provides | Section |
|--------|-----------------|---------|
| `CorrelationFinding` model | All active N=1 correlation findings | Correlation Web + What Data Proved |
| `TrainingLoadCalculator` | CTL history (first value, current value) | Hero stats strip |
| `TrainingPlan` | goal_race_name, goal_race_date | Hero date label |
| `DailyCheckin` | Checkin count (for patterns_forming fallback) | Patterns Forming |

---

## Files to Change

| File | Change |
|------|--------|
| `apps/api/routers/progress.py` | Add `GET /v1/progress/knowledge` endpoint + new response models (`KnowledgeResponse`, `CorrelationNode`, `CorrelationEdge`, `ProvedFact`, `HeroData`) |
| `apps/web/app/progress/page.tsx` | **Complete rewrite** — replace card grid with Hero + CorrelationWeb + WhatDataProved |
| `apps/web/lib/hooks/queries/progress.ts` | Add `useProgressKnowledge()` hook + new types |
| `apps/web/components/progress/CorrelationWeb.tsx` | **New file** — D3 force graph |
| `apps/web/components/progress/WhatDataProved.tsx` | **New file** — expandable fact list |
| `apps/web/components/progress/ProgressHero.tsx` | **New file** — hero header |
| `apps/web/components/progress/index.ts` | Update exports |
| `apps/web/package.json` | Add `d3` + `@types/d3` |
| `docs/SITE_AUDIT_LIVING.md` | Update post-deploy |

---

## Backend: `GET /v1/progress/knowledge`

### Response Models

```python
class CorrelationNode(BaseModel):
    id: str               # e.g. "sleep_hours" or "efficiency"
    label: str            # e.g. "Sleep" or "Efficiency"
    group: str            # "input" or "output"

class CorrelationEdge(BaseModel):
    source: str           # node id
    target: str           # node id
    r: float              # correlation_coefficient
    direction: str        # "positive" or "negative"
    lag_days: int          # time_lag_days
    times_confirmed: int
    strength: str         # "weak", "moderate", "strong"
    note: str             # insight_text or LLM-generated

class ProvedFact(BaseModel):
    input_metric: str
    output_metric: str
    headline: str         # human-readable pattern description
    evidence: str         # what was observed
    implication: str      # current relevance (LLM or fallback)
    times_confirmed: int
    confidence_tier: str  # "emerging", "confirmed", "strong"
    direction: str
    correlation_coefficient: float
    lag_days: int

class HeroStat(BaseModel):
    label: str
    value: str
    color: str            # "muted", "blue", "orange"

class HeroData(BaseModel):
    date_label: str
    headline: str
    headline_accent: str
    subtext: str
    stats: list[HeroStat]

class DataCoverageKnowledge(BaseModel):
    total_findings: int
    confirmed_findings: int
    emerging_findings: int
    checkin_count: int

class KnowledgeResponse(BaseModel):
    hero: HeroData
    correlation_web: dict  # {"nodes": [...], "edges": [...]}
    proved_facts: list[ProvedFact]
    patterns_forming: Optional[PatternsFormingResponse] = None
    generated_at: str
    data_coverage: DataCoverageKnowledge
```

### Assembly Logic

```
1. Query CorrelationFinding:
   - WHERE athlete_id = current, is_active = True
   - ORDER BY (times_confirmed * confidence) DESC
   - No limit — show the full web

2. Build nodes:
   - Deduplicate input_name → input nodes
   - Deduplicate output_metric → output nodes
   - Label: input_name.replace("_", " ").title()

3. Build edges:
   - One per finding
   - r = correlation_coefficient
   - direction = finding.direction
   - lag_days = finding.time_lag_days
   - note = finding.insight_text or deterministic fallback

4. Build proved_facts:
   - Same findings, list presentation
   - confidence_tier: 1-2 = "emerging", 3-5 = "confirmed", 6+ = "strong"
   - headline: deterministic template from input_name + output_metric + direction
   - evidence: from insight_text
   - implication: LLM-generated or fallback

5. Build hero:
   - CTL history from TrainingLoadCalculator
   - Race info from TrainingPlan
   - Stats: CTL then, CTL now, days out (or weeks tracked if no race)
   - Headline: LLM-generated or fallback "Your progress over N weeks."

6. If no findings exist:
   - correlation_web = {"nodes": [], "edges": []}
   - proved_facts = []
   - patterns_forming = PatternsFormingResponse with checkin count + message

7. Cache in Redis: progress_knowledge:{athlete_id}, 30min TTL
```

### LLM Usage

LLM generates:
- `hero.headline` + `hero.headline_accent` + `hero.subtext`
- `proved_fact[].implication` (one sentence per finding)

LLM is NOT required for page to render. If LLM fails:
- hero.headline = "Your progress over {N} weeks."
- hero.headline_accent = "Here's what the data shows."
- hero.subtext = "Facts discovered from your own training data."
- proved_fact[].implication = "" (evidence section still shows)

---

## Frontend Implementation

### Design Reference

**The mockup is the spec.** Open `docs/references/progress_page_mockup_v2_2026-03-02.html`
in a browser. That is what the page should look like.

Use the mockup code directly for:
- Color tokens (the `C` object)
- Layout structure and spacing
- Hover interaction patterns
- Animation (IntersectionObserver reveals, count-up animations)
- D3 force simulation configuration (node positioning, forces, edge rendering)
- Typography hierarchy

Swap hardcoded data for API calls. Everything else matches the mockup.

### CorrelationWeb Component

- D3 force simulation with `forceLink`, `forceX` (inputs left, outputs right),
  `forceY` (center), `forceCollide`, `forceManyBody`
- SVG rendering: nodes as circles, edges as paths
- Edge thickness = `Math.abs(r) * scale`
- Edge style: solid (positive), dashed (negative)
- Edge color: green (positive), red (negative)
- Hover edge → detail panel below with r, lag, confirmed count, note
- Input nodes clustered left (x ≈ 18%), output nodes right (x ≈ 82%)
- Legend: Positive / Inverse / Stronger = thicker
- Responsive: `ResizeObserver` adjusts SVG dimensions
- LiveDot indicator: "Live data" (green dot)

### WhatDataProved Component

- List of ProvedFact items, ordered by times_confirmed desc
- Each item: confidence icon + headline + expandable detail
- Expanded: evidence text + implication text + confirmation pips
- Confidence visual:
  - Emerging (1-2): `~` icon, "Early signal to watch" language
  - Confirmed (3-5): `✓` icon, "Becoming reliable" language
  - Strong (6+): `✓✓` icon, "Your body consistently shows" language
- Tags with appropriate colors per confidence tier

### ProgressHero Component

- Full-width gradient background (orange faint gradient from top-left)
- Date label with race countdown
- Headline (large) + accent (orange)
- Subtext paragraph
- Stats strip: 3 stat blocks (CTL then, CTL now, Days out)
- Count-up animation on stat values
- No card border — hero sits at top of page

### Patterns Forming (fallback)

- Shown when `patterns_forming` is non-null (no correlation findings)
- Checkin count / needed
- Progress bar
- Encouraging message about daily check-ins accelerating discovery

---

## Build Contracts (non-negotiable)

1. **Single endpoint.** `GET /v1/progress/knowledge` returns everything.
   No two-call split.

2. **Render independence.** Visual data (nodes, edges, facts) is assembled
   deterministically. LLM generates text embellishments only. Page renders
   fully without LLM.

3. **Latency.** Deterministic assembly < 500ms. With LLM < 5s. Cache < 100ms.

4. **Confidence gating.** emerging (1-2) = "signal to watch."
   confirmed (3-5) = "becoming reliable." strong (6+) = "consistently shows."
   Emerging patterns NEVER presented as causal claims. Validate LLM output.

5. **N=1 uniqueness.** If a pattern callout could appear on a different
   athlete's page, reject it.

6. **All distances in miles.**

---

## Required Tests

1. Endpoint returns valid JSON with hero, correlation_web, proved_facts
2. correlation_web.nodes deduplicates input/output names correctly
3. correlation_web.edges maps 1:1 to CorrelationFinding rows
4. proved_facts ordered by times_confirmed descending
5. Confidence tiers assigned correctly (1-2=emerging, 3-5=confirmed, 6+=strong)
6. When no findings exist: empty web, empty facts, patterns_forming populated
7. LLM failure: all data fields present, text fields use fallback
8. Redis cache hit on second call within TTL
9. Cache invalidated on new checkin or activity
10. Hero stats populated from TrainingLoadCalculator + TrainingPlan
11. Hero without race: "Days out" replaced with "Weeks tracked"
12. Frontend: D3 force graph renders with correct node/edge count
13. Frontend: Hover edge shows detail panel
14. Frontend: Mobile responsive — SVG scales, touch works

---

## Production Smoke Checks (post-deploy)

```bash
# 1. Endpoint returns valid response shape
TOKEN=$(...generate token...)
curl -s -H "Authorization: Bearer $TOKEN" \
  https://strideiq.run/v1/progress/knowledge | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert 'hero' in d, 'Missing hero'
assert 'correlation_web' in d, 'Missing correlation_web'
web = d['correlation_web']
assert 'nodes' in web and 'edges' in web, 'Bad web shape'
assert 'proved_facts' in d, 'Missing proved_facts'
print(f'Nodes: {len(web[\"nodes\"])}, Edges: {len(web[\"edges\"])}, Facts: {len(d[\"proved_facts\"])}')
print('PASS: response shape valid')
"

# 2. Fallback — LLM failure still returns data
# Temporarily set ANTHROPIC_API_KEY="" or GOOGLE_AI_API_KEY="" then:
# Verify hero, nodes, edges, facts all present. Text fields have fallback.
# Restore key after.

# 3. Hero stats present
curl -s -H "Authorization: Bearer $TOKEN" \
  https://strideiq.run/v1/progress/knowledge | python3 -c "
import sys, json
d = json.load(sys.stdin)
hero = d['hero']
assert hero['stats'] and len(hero['stats']) >= 2, 'Missing hero stats'
assert hero['date_label'], 'Missing date label'
print(f'Hero: {hero[\"headline\"]} {hero[\"headline_accent\"]}')
print(f'Stats: {hero[\"stats\"]}')
print('PASS: hero valid')
"

# 4. Mobile rendering — open https://strideiq.run/progress on phone:
#    - Force graph visible, nodes and edges render
#    - Edge hover/tap shows detail panel
#    - Facts list expandable
#    - Hero text readable, stats strip wraps
#    - No horizontal scroll
```

---

## Evidence Required in Handoff

The builder must provide ALL of the following:

1. **Commit hash(es)** — scoped commits only
2. **Files changed table** — file + one-line description
3. **Test output** — full pytest output, total count, 0 failures
4. **Production smoke check output** — paste results of checks above
5. **Screenshot or recording** — desktop + mobile showing Hero, Correlation
   Web with edges, What Data Proved with expanded item
6. **Fallback evidence** — screenshot showing page renders without LLM
7. **AC checklist** — every AC from the spec marked with evidence

---

## Mandatory: Site Audit Update

After deploy, update `docs/SITE_AUDIT_LIVING.md`:
- New entry under "Delta Since Last Audit"
- Update "Progress" page description: "D3 force-directed correlation web,
  expandable proved facts, coach-voice hero — replaces old card grid"
- Document new endpoint `/v1/progress/knowledge`
- Update `last_updated` date

---

## Immediate Next Priority: Correlation Engine Quality

**This is not part of this build.** But it is the highest priority after
this page ships. The correlation engine is the heartbeat of this product —
the reason it exists. Right now it surfaces misleading findings.

**Known problem (founder-identified):** The engine reports "High motivation
reduces efficiency within 3 days" as STRONG (9x confirmed). This is
technically true but useless — high motivation days are hard workout days,
and the efficiency "drop" 3 days later is normal recovery. The engine is
detecting deload dips and blaming the input variable. Training load is the
confounder.

**What the engine should detect instead:** trend-within-the-pattern. Are
the recovery-day efficiency values rising over time? That shows adaptation.
Not "A causes B" but "the relationship between A and B is changing, and
here's what that means about your body."

**Fixes needed (next builder note):**
1. Confounding variable awareness — filter or flag findings where training
   load explains both the input and output
2. Trend-within-pattern detection — track whether the correlated values
   are trending even within the repeated pattern
3. Direction validation — distinguish "natural training response" from
   "problem to address"
4. Interpretation quality gate — no finding surfaces unless the
   interpretation would survive a coach's scrutiny

**A builder note for this work must be written before any code changes.**
