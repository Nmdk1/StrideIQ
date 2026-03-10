# Progress Page — Product & Build Spec v2

**Author:** Founder + advisors
**Date:** March 2, 2026
**Status:** Spec — phased build
**Design target:** `docs/references/progress_page_mockup_v2_2026-03-02.html`

---

## What This Page Is

The system's accumulated knowledge about a specific human, made explorable.

Not charts. Not dashboards. Not "what happened this week." This page answers:
**What has your training built, and what does your body know now that it
didn't know before?**

Every element on the page is evidence for that answer.

---

## The Design Principle

**Synthesis as an interface.**

1. Visuals are the first layer of reasoning — not decoration.
2. Narrative is the second layer that resolves ambiguity — not summary.
3. Action is the third layer — every block ends in an athlete decision.

If a section looks like 2018 analytics SaaS, reject it. If a section makes
a runner immediately understand and decide, ship it.

---

## Phased Build

### Phase 1 — Ship the moat (data exists now)

| Section | Data readiness | Source |
|---------|---------------|--------|
| Hero | 100% | CTL from TrainingLoadCalculator, race from TrainingPlan |
| Correlation Web | 95% | CorrelationFinding model — all fields exist |
| What the Data Proved | 95% | Same CorrelationFinding data, list presentation |

### Phase 2 — Context and history (some backend work)

| Section | Data readiness | Gap |
|---------|---------------|-----|
| Physiological Portrait | 70% | TSB-zone correlation needs a backend job |
| Training Block Timeline | 65% | Needs block timeline endpoint |

### Phase 3 — Future-looking (new backend capabilities)

| Section | Data readiness | Gap |
|---------|---------------|-----|
| Capability Expansion | 60% | Needs prediction history snapshots |
| Recovery Fingerprint | 50% | Needs metric timestamping |
| Prediction Space | 40% | Needs `/v1/predictions/scenario` |

---

## Phase 1 Sections

### Hero

Full-width opening statement. Not a card — a gradient-backed header.

**Content:**
- Date + race countdown (from TrainingPlan)
- Headline: "Eight weeks of work. Here's what your body became." (LLM-generated, specific to athlete context)
- Subtext: one paragraph framing what follows
- Stats strip: CTL then, CTL now, Days out

**Data sources:**
- `TrainingLoadCalculator` → CTL history (first and current values)
- `TrainingPlan` → goal_race_name, goal_race_date, days_remaining

**JSON contract:**

```json
"hero": {
  "date_label": "Monday, Mar 2 · Tobacco Road v26 in 13 days",
  "headline": "Eight weeks of work.",
  "headline_accent": "Here's what your body became.",
  "subtext": "Not averages applied to you. Facts discovered from you...",
  "stats": [
    { "label": "CTL then", "value": "9.9", "color": "muted" },
    { "label": "CTL now", "value": "42.4", "color": "blue" },
    { "label": "Days out", "value": "13", "color": "orange" }
  ]
}
```

### Correlation Web

**The moat visualized.** A D3 force-directed graph showing what drives this
athlete's performance. Inputs on the left, outputs on the right. Edge
thickness = correlation strength. Dashed edges = inverse correlations.
Hover any edge for the full evidence.

**Data source:** `CorrelationFinding` model. Fields used:

| Model field | Graph element |
|-------------|--------------|
| `input_name` | Input node label |
| `output_metric` | Output node label |
| `correlation_coefficient` | Edge thickness |
| `direction` | Edge style (solid = positive, dashed = negative) |
| `time_lag_days` | Edge tooltip ("lag 2-3 days") |
| `times_confirmed` | Edge tooltip ("confirmed 9×") |
| `confidence` | Not displayed directly — used for filtering |
| `strength` | Fallback for edge weight if coefficient unavailable |
| `insight_text` | Edge hover detail narrative |
| `category` | "what_works" / "what_doesnt" / "pattern" |

**Query:** All active findings for the athlete, `times_confirmed >= 1`,
ordered by `times_confirmed * confidence` descending. No limit — show the
full web.

**Node deduplication:** Unique input_name values become input nodes. Unique
output_metric values become output nodes. D3 force simulation positions
them with inputs left, outputs right.

**Interaction:** Hover an edge → detail panel appears below with:
- Source → Target labels
- r = coefficient (tagged)
- lag = time_lag_days (tagged)
- confirmed = times_confirmed (tagged)
- note = insight_text or LLM-generated explanation

**Fallback:** If no correlation findings exist, show the patterns_forming
indicator with checkin count and progress messaging.

### What the Data Proved

Same data as Correlation Web, different presentation. An expandable list of
confirmed and emerging patterns, each with evidence and current implication.

**Data source:** Same `CorrelationFinding` query, but presented as a list
ordered by `times_confirmed` descending.

**Confidence gating (from build contracts):**

| `times_confirmed` | Label | Language |
|-------------------|-------|---------|
| 1-2 | Emerging | "Early signal to watch" |
| 3-5 | Confirmed | "Becoming reliable" |
| 6+ | Strong | "Your body consistently shows" |

**Per-item structure:**
- Icon: ✓ (confirmed/strong) or ~ (emerging)
- Headline: human-readable pattern description
- Expandable: The Evidence (what was observed) + What It Means Now (current
  implication) + Confirmation pips (visual dot count)

**The evidence text** comes from `insight_text` on the CorrelationFinding.
**The implication** is LLM-generated, connecting the pattern to the athlete's
current situation. Fallback: deterministic template.

---

## Backend: Phase 1 Endpoint

### `GET /v1/progress/knowledge`

Returns the full Phase 1 data structure. Two-phase assembly:

**Phase 1 (deterministic, < 500ms):**
- Query CorrelationFinding for all active findings
- Query TrainingLoadCalculator for CTL history
- Query TrainingPlan for race info

**Phase 2 (LLM, < 5s):**
- Generate hero headline + subtext
- Generate per-finding current implication text
- Validate: no hallucinations, no unsupported claims

**Caching:** Redis, `progress_knowledge:{athlete_id}`, 30min TTL.

**Fallback:** If LLM fails, deterministic text for everything. Hero uses
"Your progress over {N} weeks." Findings use insight_text directly.

**Response shape:**

```json
{
  "hero": { ... },
  "correlation_web": {
    "nodes": [
      { "id": "sleep", "label": "Sleep", "group": "input" },
      { "id": "efficiency", "label": "Efficiency", "group": "output" }
    ],
    "edges": [
      {
        "source": "sleep",
        "target": "efficiency",
        "r": 0.62,
        "direction": "positive",
        "lag_days": 1,
        "times_confirmed": 7,
        "strength": "strong",
        "note": "Sleep above your 6.8h baseline produces..."
      }
    ]
  },
  "proved_facts": [
    {
      "input_metric": "motivation_1_5",
      "output_metric": "efficiency",
      "headline": "High motivation → efficiency gain within 2-3 days",
      "evidence": "...",
      "implication": "...",
      "times_confirmed": 9,
      "confidence_tier": "strong",
      "direction": "positive",
      "correlation_coefficient": 0.71,
      "lag_days": 2
    }
  ],
  "generated_at": "2026-03-02T12:00:00Z",
  "data_coverage": {
    "total_findings": 9,
    "confirmed_findings": 4,
    "emerging_findings": 5,
    "checkin_count": 45
  }
}
```

---

## Frontend: Phase 1

### Dependencies to add

- `d3` (force simulation for correlation web)

### New files

| File | Purpose |
|------|---------|
| `apps/web/app/progress/page.tsx` | Complete rewrite — new layout |
| `apps/web/components/progress/CorrelationWeb.tsx` | D3 force graph |
| `apps/web/components/progress/WhatDataProved.tsx` | Expandable fact list |
| `apps/web/components/progress/ProgressHero.tsx` | Hero header |
| `apps/web/lib/hooks/queries/progress.ts` | New `useProgressKnowledge()` hook |

### Design reference

The mockup at `docs/references/progress_page_mockup_v2_2026-03-02.html` IS
the component code. The builder should use it as the direct source for:
- Color tokens (the `C` object)
- Layout structure
- Interaction patterns (hover states, expandable panels)
- Animation (IntersectionObserver reveals, D3 force simulation config)
- Typography hierarchy

Swap hardcoded data for API calls. Everything else stays as close to the
mockup as possible.

---

## Acceptance Criteria — Phase 1

- [ ] AC1: Current 12-card progress page is completely replaced
- [ ] AC2: Hero renders with CTL history, race countdown, coach-voice headline
- [ ] AC3: Correlation Web renders as D3 force graph with all active findings
- [ ] AC4: Hovering an edge shows full evidence detail panel
- [ ] AC5: What Data Proved renders as expandable list with evidence + implication
- [ ] AC6: Confidence gating: emerging (1-2) uses "signal to watch" language,
      confirmed (3-5) uses "becoming reliable", strong (6+) uses "consistently shows"
- [ ] AC7: If no findings exist, patterns_forming indicator with checkin count
- [ ] AC8: LLM fallback: deterministic text renders if LLM fails
- [ ] AC9: Visual quality matches the mockup — not basic charts, not card grid
- [ ] AC10: Page is interactive (hover states, expandable sections, D3 simulation)
- [ ] AC11: Mobile responsive — force graph scales, expandable items work on touch
- [ ] AC12: Tree clean, tests green, production healthy

---

## Decided

- **Phase 1 ships Correlation Web + What Data Proved + Hero.** These three
  sections use data that's 95%+ ready. No new backend computation needed.
  Just query CorrelationFinding and render beautifully.

- **The mockup is the spec.** `docs/references/progress_page_mockup_v2_2026-03-02.html`
  Open it in a browser. That's what the page should look like.

- **D3 for the force graph.** Not Recharts. D3 force simulation with custom
  SVG rendering. The mockup code shows exactly how.

- **No charts from old page survive.** The entire page is replaced. The old
  sparklines, gauges, bar charts, and card grid are removed.

- **Phases 2-3 are scoped but not built yet.** They require backend work
  that Phase 1 does not.
