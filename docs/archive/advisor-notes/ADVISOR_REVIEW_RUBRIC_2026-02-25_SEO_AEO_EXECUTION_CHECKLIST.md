# Advisor Review Rubric: SEO + AEO Execution Checklist

Date: 2026-02-25  
Scope: Review builder execution against `docs/BUILDER_NOTE_2026-02-25_SEO_AEO_EXECUTION_CHECKLIST.md`

## Purpose

Use this rubric after each phase handoff to determine:
- whether acceptance criteria are truly met,
- whether evidence is sufficient,
- whether regressions were introduced,
- whether the next phase is approved.

## Read Order (for reviewer)

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/PRODUCT_MANIFESTO.md`
3. `C:\Users\mbsha\.cursor\plans\seo_aeo_visibility_plan_db058230.plan.md`
4. `docs/BUILDER_NOTE_2026-02-25_SEO_AEO_EXECUTION_CHECKLIST.md`

---

## Review Decision Scale

- **PASS**: Acceptance criteria met, evidence complete, no blocking regressions.
- **PASS WITH CONDITIONS**: Minor gaps only; explicit follow-up task required before next phase close.
- **FAIL**: Missing evidence, unmet acceptance criteria, or regression risk.

## Hard Fail Conditions (automatic FAIL)

- No command output evidence for claimed checks.
- Missing deploy verification (`sitemap.xml`, `robots.txt`, live route status).
- Unscoped git changes or contract violations.
- Claimed metadata/schema changes not visible in rendered HTML.
- Regression in public route availability (unexpected non-200/redirect loops).

---

## Scoring (100 points total)

### A) Evidence Quality (30 points)
- 10: Exact commands provided
- 10: Exact outputs provided (not summaries only)
- 10: Before/after proof included where relevant

### B) Acceptance Criteria Coverage (40 points)
- 10: Criteria checked for each changed item
- 10: Live environment verification done post-deploy
- 10: Edge checks included (canonical correctness, status codes, schema validation)
- 10: Open items clearly listed

### C) Regression Safety (20 points)
- 10: No broken routes/metadata regressions introduced
- 10: Rollback risk assessed or mitigated

### D) Process Discipline (10 points)
- 5: Scoped commits, clear message style
- 5: Handoff format complete and structured

Thresholds:
- **90-100**: PASS
- **75-89**: PASS WITH CONDITIONS
- **<75**: FAIL

---

## Phase-Specific Review Checklist

## Phase 1 - Technical Baseline

### 1) Measurement Baseline
- [ ] Baseline table includes route, status, canonical, LCP/INP/CLS
- [ ] `view-source` verification done and recorded
- [ ] Crawlability decision gate documented (SSR refactor required or not)

### 2) Sitemap + Robots
- [ ] `sitemap.ts` uses `https://strideiq.run`
- [ ] Public routes included correctly
- [ ] `robots.txt` includes sitemap URL
- [ ] Live checks:
  - [ ] `https://strideiq.run/sitemap.xml` -> 200
  - [ ] `https://strideiq.run/robots.txt` -> 200

### 3) Canonical + Redirect Hygiene
- [ ] Canonical tags are self-referencing on public pages
- [ ] `http -> https` confirmed
- [ ] `www -> non-www` confirmed
- [ ] No redirect loops or soft 404 behavior

### 4) Metadata + OG
- [ ] Unique title/description per public page
- [ ] OG image wired and resolvable
- [ ] Rendered HTML confirms metadata presence

### 5) Search Console Manual Step
- [ ] Marked as operator-owned (not fabricated by builder)
- [ ] Verification + sitemap submission evidence attached by operator

---

## Phase 2 - Content and AEO

### 6) FAQ + FAQ JSON-LD
- [ ] FAQ answers are direct, concise, and runner-intent aligned
- [ ] FAQ content is visible on-page (not schema-only)
- [ ] FAQ JSON-LD matches visible content
- [ ] Rich Results validation proof included

### 7) Tool Pages
- [ ] Three dedicated pages exist and return 200
- [ ] Unique metadata/canonical per tool page
- [ ] `/tools` links crawlably to all tool pages
- [ ] Canonical strategy avoids duplicate-content ambiguity

### 8) Landing Copy Alignment
- [ ] Search-aligned terms included naturally
- [ ] Evidence/outcomes framing preserved
- [ ] Brand voice preserved (no generic SEO spam)

### 9) Organization + WebApplication JSON-LD
- [ ] Schema validates
- [ ] URLs/logo/offers are production-correct
- [ ] No mismatch between schema claims and page content

---

## Phase 3 - Authority Asset

### 10) Stories Shell
- [ ] `/stories` exists, returns 200, and is discoverable via internal link
- [ ] Metadata + canonical present

### 11) Case Study Template Readiness
- [ ] Template or route pattern prepared
- [ ] Article schema plan documented
- [ ] Publish checklist ready for 48-hour post-race turnaround

---

## KPI Cadence Review

Weekly:
- [ ] GSC indexed pages trend
- [ ] GSC impressions/clicks for target query set
- [ ] CWV trend for `/` and `/tools`

Monthly:
- [ ] AI citation checks (ChatGPT/Gemini/Claude) logged with prompts/results

---

## Required Builder Handoff Format (must be present)

- [ ] Files changed + why
- [ ] Commands run (tests/build/checks)
- [ ] Deploy command run
- [ ] Smoke outputs
- [ ] Risks/open items

Missing any item above -> cannot mark PASS.

---

## Advisor Decision Template

Use this exact template when responding to a phase handoff:

```markdown
Phase reviewed: <Phase X>
Decision: PASS | PASS WITH CONDITIONS | FAIL
Score: <0-100>

Findings (highest severity first):
- <issue/evidence gap/regression risk>

Acceptance criteria status:
- <criterion>: PASS/FAIL with evidence reference

Required follow-ups:
- <if any>

Approval:
- Next phase approved: YES/NO
```
