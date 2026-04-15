# Builder Note: SEO + AEO Execution Checklist (Phased, Verifiable)

Date: 2026-02-25  
Owner: Builder  
Advisor: Codex

## Read Order (Mandatory)

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/PRODUCT_MANIFESTO.md`
3. `C:\Users\mbsha\.cursor\plans\seo_aeo_visibility_plan_db058230.plan.md`

## Objective

Execute the revised SEO/AEO plan in small, verifiable phases with evidence after each phase. Prioritize technical foundation and measurable outcomes before larger content work.

## Scope

- In scope: sitemap, robots, metadata, canonical/redirect hygiene, OG image, JSON-LD, FAQ, tool pages, stories shell, Search Console setup support, KPI tracking.
- Out of scope: native app, paid ads, social strategy, broad SSR refactor unless measurement proves required.

---

## Phase 1 - Technical Baseline (Ship First)

### 1) Measure baseline first (no edits yet)

Tasks:
- Check `view-source:https://strideiq.run` for meaningful HTML content.
- Capture Lighthouse/PageSpeed baseline for `/` and `/tools` (LCP, INP, CLS).
- Verify public route status codes (`200/301/404` expected behavior).
- Verify canonical tags currently rendered.

Evidence required:
- Baseline table in builder report with:
  - Route
  - Status code
  - Canonical present (yes/no)
  - LCP/INP/CLS

### 2) Sitemap + robots hygiene

Files:
- `apps/web/app/sitemap.ts`
- `apps/web/public/robots.txt`

Changes:
- Hardcode production base URL `https://strideiq.run`.
- Include all current public routes.
- Ensure `robots.txt` includes:
  - `Sitemap: https://strideiq.run/sitemap.xml`

Acceptance:
- `https://strideiq.run/sitemap.xml` returns `200`.
- `https://strideiq.run/robots.txt` returns `200`.
- Sitemap URLs are canonical production URLs only.

### 3) Canonical + redirect hygiene

Files:
- `apps/web/app/layout.tsx` (or metadata config)
- `Caddyfile` (only if redirect normalization is wrong)

Checks/changes:
- Confirm `metadataBase` is `https://strideiq.run`.
- Confirm self-referencing canonical per public page.
- Confirm `http -> https`.
- Confirm `www -> non-www`.
- Confirm status codes are clean (no accidental loops/soft 404s).

Acceptance:
- Canonical tags render correctly on all public pages.
- `http://` and `www.` normalize to canonical host.

### 4) Page metadata + OG image

Files:
- `apps/web/app/layout.tsx`
- `apps/web/app/page.tsx`
- `apps/web/app/mission/page.tsx`
- `apps/web/app/about/page.tsx`
- `apps/web/app/tools/page.tsx`
- `apps/web/public/og-image.png` (1200x630)

Changes:
- Add/fix title + description + canonical + OG metadata for each page.
- Wire OG image in global metadata.

Acceptance:
- Each page has unique title and description.
- OG tags render in page HTML.
- No build warnings/errors from metadata config.

### 5) Search Console setup (manual operator step)

Operator steps:
1. Open Google Search Console.
2. Add property: `strideiq.run`.
3. Verify via DNS TXT in Porkbun.
4. Submit `https://strideiq.run/sitemap.xml`.
5. Run URL inspection for landing page.

Evidence required:
- Confirmation screenshot/text from operator that property is verified and sitemap submitted.

---

## Phase 2 - Content and AEO

### 6) FAQ section + FAQ JSON-LD

Files:
- `apps/web/app/page.tsx` (or section component)
- `apps/web/components/seo/JsonLd.tsx` (create if missing)

Changes:
- Add FAQ with 30-50 word direct answers targeting runner-intent queries.
- Add matching `FAQPage` JSON-LD tied to visible FAQ content.

Acceptance:
- FAQ content is visible in rendered HTML.
- JSON-LD validates in Rich Results Test.

### 7) Dedicated tool pages

Files:
- `apps/web/app/tools/training-pace-calculator/page.tsx`
- `apps/web/app/tools/age-grading-calculator/page.tsx`
- `apps/web/app/tools/heat-adjusted-pace/page.tsx`
- Update internal links from `/tools`.

Changes:
- Add intent-matched SEO copy + calculator islands.
- Add unique metadata and canonical per page.

Acceptance:
- All three pages return `200`.
- Each page has unique metadata/canonical.
- `/tools` links to all three pages crawlably.

### 8) Landing copy alignment

File:
- `apps/web/app/page.tsx`

Changes:
- Align hero/subheads/body copy with target runner queries while preserving brand voice.
- Keep evidence/outcomes emphasis.

Acceptance:
- Query terms present naturally in headings/body copy.
- No UX regressions.

### 9) Organization + WebApplication JSON-LD

Files:
- `apps/web/components/seo/JsonLd.tsx`
- `apps/web/app/layout.tsx` or landing page

Acceptance:
- Schema validates.
- URLs/logo/offers are correct and production-canonical.

---

## Phase 3 - Authority Asset

### 10) Stories shell

File:
- `apps/web/app/stories/page.tsx`

Changes:
- Public server-rendered shell with metadata and canonical.
- Placeholder copy indicating incoming real outcomes.

Acceptance:
- `/stories` returns `200` and is linked from the public site.

### 11) Post-race case study template readiness

Files:
- `apps/web/app/stories/[slug]/page.tsx` (if dynamic), or static story route plan

Changes:
- Prepare article structure and `Article` JSON-LD support.

Acceptance:
- Template ready for publish within 48h post-race.

---

## KPI Tracking (Required)

Track weekly:
- Indexed page count (GSC)
- Impressions/clicks for:
  - training pace calculator
  - age grading calculator
  - heat adjusted pace
  - AI running coach
- Monthly AI citation checks (ChatGPT/Gemini/Claude prompts)
- CWV trend for `/` and `/tools`

---

## Deploy and Verify (Every Phase)

Deploy command:

```bash
cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build
```

Smoke checks:

```bash
curl -I https://strideiq.run
curl -I https://strideiq.run/sitemap.xml
curl -I https://strideiq.run/robots.txt
```

Plus:
- Verify rendered HTML includes expected canonical + metadata.
- Validate JSON-LD via Rich Results Test.

---

## Git Discipline (Non-Negotiable)

- Scoped commits only (never `git add -A`).
- One commit per phase chunk.
- Commit prefixes:
  - `feat(seo): ...`
  - `fix(seo): ...`
  - `chore(seo): ...`

## Handoff Format Required

Each builder handoff must include:
- Exactly what changed (files + brief reason)
- Exact test/build commands run
- Exact deploy command run
- Smoke-check output
- Any risks/open items
