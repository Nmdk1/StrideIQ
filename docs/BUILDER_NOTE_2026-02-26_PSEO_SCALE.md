# Builder Note — pSEO Scale-Up (Batch 2 + Batch 3)

**Date:** 2026-02-26
**Assigned to:** Traffic Builder
**Advisor sign-off required:** Yes — advisor reviews before deploy

---

## Before Your First Tool Call

Read these in order:
1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/SESSION_HANDOFF_2026-02-26_ADVISOR_NOTE.md`
3. This document

---

## Objective

Scale StrideIQ's programmatic SEO pages from 22 to 560+. The infrastructure is built and proven. This is a data generation + config expansion task, not an architecture task.

---

## Existing Infrastructure (DO NOT REBUILD)

- **Data generation:** `scripts/generate-pseo-data.mjs` — generates JSON data files in `apps/web/data/`
- **Verification:** `scripts/verify-bluf-data.mjs` — verifies all BLUF/FAQ numbers match generated data
- **Shared RPI formula:** `scripts/lib/rpi-formula.mjs` — Daniels/Gilbert oxygen cost equations
- **WMA age factors:** Hardcoded in `generate-pseo-data.mjs` (Alan Jones 2025 factors)
- **Sitemap:** `apps/web/app/sitemap.ts` — manual entries per page

### Existing Templates

| Template | Path | Config Object | Data File |
|----------|------|---------------|-----------|
| Goal pages | `apps/web/app/tools/training-pace-calculator/goals/[slug]/page.tsx` | `GOAL_PAGE_CONFIG` | `goal-pace-tables.json` |
| Demographic pages | `apps/web/app/tools/age-grading-calculator/demographics/[slug]/page.tsx` | `DEMO_PAGE_CONFIG` | `age-gender-tables.json` |
| Distance training paces | `apps/web/app/tools/training-pace-calculator/[distance]/page.tsx` | `DISTANCE_CONFIG` | `training-pace-tables.json` |
| Distance age grading | `apps/web/app/tools/age-grading-calculator/[distance]/page.tsx` | `DISTANCE_CONFIG` | `age-grading-tables.json` |
| Race equivalency | `apps/web/app/tools/race-equivalency/[conversion]/page.tsx` | `CONVERSION_PAGE_CONFIG` | `equivalency-tables.json` |

### How Pages Get Added (the pipeline)

1. Add slug config to the page template's config object (metadata, BLUF, FAQs)
2. Add data generation logic to `generate-pseo-data.mjs` for new slugs
3. Run `node scripts/generate-pseo-data.mjs` to produce/update JSON
4. Run `node scripts/verify-bluf-data.mjs` to verify all numbers match
5. Sitemap entries are generated automatically from config objects (see Sitemap Strategy section)
6. `npm run build` in `apps/web` — must succeed with zero errors
7. Deploy

---

## Execution Order (revised per advisor review)

1. **Batch 2B** (BQ pages) — highest search intent, highest conversion potential
2. **Batch 2A** (goal pages) — high volume, existing template
3. **Batch 2D** (equivalency pages) — quick win, existing template
4. **Batch 2C** (demographic pages) — fill the matrix, existing template
5. **Batch 3** (per-age pages) — GATED: do not start until Batches 2A-2D show measurable GSC impressions/clicks

Deploy after each batch. Do not wait until all batches are complete.

### Pass/Fail Gates Between Batches

- **After Batch 2B:** All BQ pages return 200, sitemap updated, `verify-bluf-data.mjs` passes. Deploy and submit sitemap to GSC.
- **After Batch 2A:** Same quality gates. Check GSC for BQ page impressions (may take 1-2 weeks to appear).
- **After Batch 2D + 2C:** Full Batch 2 deployed. Wait 2-4 weeks for GSC data.
- **Batch 3 gate (HARD):** Do NOT start Batch 3 until at least ONE of these is true:
  - GSC shows >500 impressions/week across Batch 2 pages
  - At least 1 organic click-through to a conversion page (pricing, signup, checkout)
  - Founder explicitly approves based on other evidence

---

## Batch 2A: Goal Page Expansion (44 new pages)

Expand `GOAL_PAGE_CONFIG` and `goal-pace-tables.json`. Existing template, no structural changes.

### New Slugs

**5K (9 new):**
- `sub-17-minute-5k`, `sub-18-minute-5k`, `sub-19-minute-5k`, `sub-21-minute-5k`, `sub-22-minute-5k`, `sub-23-minute-5k`, `sub-24-minute-5k`, `sub-27-minute-5k`, `sub-30-minute-5k`

**10K (10 new):**
- `sub-35-minute-10k`, `sub-36-minute-10k`, `sub-37-minute-10k`, `sub-38-minute-10k`, `sub-39-minute-10k`, `sub-42-minute-10k`, `sub-45-minute-10k`, `sub-48-minute-10k`, `sub-55-minute-10k`, `sub-60-minute-10k`

**Half Marathon (8 new):**
- `sub-1-15-half-marathon`, `sub-1-20-half-marathon`, `sub-1-25-half-marathon`, `sub-1-30-half-marathon`, `sub-1-35-half-marathon`, `sub-1-40-half-marathon`, `sub-1-45-half-marathon`, `sub-1-50-half-marathon`

**Marathon (11 new):**
- `sub-2-30-marathon`, `sub-2-45-marathon`, `sub-3-hour-marathon`, `sub-3-05-marathon`, `sub-3-10-marathon`, `sub-3-15-marathon`, `sub-3-20-marathon`, `sub-3-30-marathon`, `sub-3-45-marathon`, `sub-4-30-marathon`, `sub-5-hour-marathon`

### Per-Slug Requirements

Each config entry must have:
- `title`: SEO title (e.g., "Sub 3 Hour Marathon Training Paces | StrideIQ")
- `description`: Meta description targeting the search query
- `h1`: Page heading
- `goalTime`: Target time in seconds
- `distanceMeters`: Race distance
- `bluf`: BLUF paragraph with exact numbers from the generated data (verified by `verify-bluf-data.mjs`)
- `faqs`: 3 FAQs with answers containing exact data-verified numbers
- `n1Hook`: CTA connecting to StrideIQ's personalized coaching

### Data Generation

In `generate-pseo-data.mjs`, the goal page data is deterministic (uses `scripts/lib/rpi-formula.mjs`). For each new slug:
1. Compute RPI from goal time + distance
2. Derive all 5 training pace zones (easy, marathon, threshold, interval, repetition)
3. Compute equivalent race times at other distances
4. Write to `goal-pace-tables.json` under the slug key

---

## Batch 2B: Boston Qualifying Pages (NEW template, 23 pages)

### New Route

`apps/web/app/tools/boston-qualifying/page.tsx` — hub page
`apps/web/app/tools/boston-qualifying/[slug]/page.tsx` — per-age-group pages

### BQ Standards (2026 Boston Marathon — VERIFIED)

Source: https://www.baa.org/races/boston-marathon/qualify (verified 2026-02-26)

These are the official 2026 BAA qualifying times. Ages 18-59 were tightened by 5 minutes compared to 2025. These are NOT calculated from WMA — they are fixed standards set by BAA. Hardcode them.

| Age Group | Men | Women & Non-Binary |
|-----------|-----|-------------------|
| 18-34 | 2:55:00 | 3:25:00 |
| 35-39 | 3:00:00 | 3:30:00 |
| 40-44 | 3:05:00 | 3:35:00 |
| 45-49 | 3:15:00 | 3:45:00 |
| 50-54 | 3:20:00 | 3:50:00 |
| 55-59 | 3:30:00 | 4:00:00 |
| 60-64 | 3:50:00 | 4:20:00 |
| 65-69 | 4:05:00 | 4:35:00 |
| 70-74 | 4:20:00 | 4:50:00 |
| 75-79 | 4:35:00 | 5:05:00 |
| 80+ | 4:50:00 | 5:20:00 |

**Note:** Achieving a BQ time does not guarantee entry. BAA applies a cutoff buffer that varies each year based on total field size and applicant depth. BQ pages should explain this reality without hardcoding a specific cutoff number — it changes annually. Direct readers to the official BAA registration updates for the current year's cutoff.

### Hub Page Content

- Full table of all BQ standards
- Explanation of the BQ process (qualifying time + cutoff buffer)
- Links to each age-group subpage
- FAQ: "What is a good BQ buffer?", "How do BQ cutoffs work?", "When is the 2026 Boston Marathon?"
- JSON-LD: FAQPage + BreadcrumbList

### Per-Age-Group Pages (22 slugs)

Slugs use natural search language (how runners actually type these queries):

`boston-qualifying-time-men-18-34` through `boston-qualifying-time-men-80-plus` (11)
`boston-qualifying-time-women-18-34` through `boston-qualifying-time-women-80-plus` (11)

Each page shows:
- BQ standard for that age group
- Training paces to hit that BQ time (from RPI calculation)
- What that time means age-graded (WMA percentage)
- Equivalent performance at 5K, 10K, half marathon
- "Your BQ journey" section linking to the training pace calculator pre-filled with their BQ goal
- 3 FAQs specific to that age group
- JSON-LD: FAQPage + BreadcrumbList

### Data Generation

New file: `apps/web/data/bq-tables.json`

For each age group + gender:
1. BQ standard time (hardcoded from BAA)
2. RPI for that marathon time (computed via rpi-formula)
3. Training paces for that RPI
4. WMA age-graded percentage (using midpoint of age range)
5. Equivalent times at 5K, 10K, half

---

## Batch 2C: Demographic Page Expansion (50 new pages)

Expand `DEMO_PAGE_CONFIG` and `age-gender-tables.json`. Existing template.

### Full Matrix (56 total, 50 new)

4 distances x 2 genders x 7 decades = 56

**Slug format:** `{distance}-times-{gender}-age-{decade}s`

**Distances:** 5k, 10k, half-marathon, marathon
**Genders:** men, women
**Decades:** 20s, 30s, 40s, 50s, 60s, 70s, 80s

**Existing (6):** `5k-times-women-age-40s`, `5k-times-women-age-50s`, `marathon-times-men-age-50s`, `marathon-times-women-age-50s`, `10k-times-men-age-60s`, `marathon-times-men-age-60s`

**New (50):** All other combinations in the matrix.

### Per-Slug Requirements

Same as existing demographic pages: metadata, BLUF with verified numbers, age rows with performance levels, training paces per level, 3 FAQs, JSON-LD.

---

## Batch 2D: Race Equivalency Expansion (13 new pages)

Expand `CONVERSION_PAGE_CONFIG` and `equivalency-tables.json`. Existing template.

### New Slugs (13)

- `mile-to-5k`, `mile-to-10k`, `mile-to-half-marathon`, `mile-to-marathon`
- `5k-to-10k`, `5k-to-half-marathon`
- `10k-to-marathon`
- `half-marathon-to-marathon`
- `marathon-to-5k`, `marathon-to-10k`, `marathon-to-half-marathon`
- `800m-to-mile`, `800m-to-5k`

**Note on mile/800m:** These distances may not be in the current data generation script. Add them using the same Daniels/Gilbert formula. Mile = 1609.34m, 800m = 800m.

---

## Batch 3: Per-Age Pages (408 new pages, NEW template)

### New Route

`apps/web/app/tools/age-grading-calculator/per-age/[slug]/page.tsx`

### Slug Format

`good-{distance}-time-{age}-year-old-{gender}`

Slugs use natural search language:
- `good-5k-time-35-year-old-male`
- `good-marathon-time-52-year-old-female`
- `good-10k-time-44-year-old-male`

### Matrix

4 distances x 2 genders x 51 ages (25-75) = 408 pages

### Per-Page Content

Each page has genuinely different data (unique WMA factor per age):

- **BLUF:** "A good 5K time for a 35-year-old man is [X:XX]. That puts you at [XX]% age-graded — [performance level]. Elite masters runners at 35 run [X:XX]."
- **Performance table:** 5 levels (50%, 60%, 70%, 80%, 90%) with time, pace, and label
- **Training paces:** For the 70% performance level (typical "good" runner)
- **Equivalent times:** At other distances for the same fitness level
- **Comparison:** How this age compares to adjacent ages (e.g., "At 36, the same fitness produces a 5K of [X:XX] — about [N] seconds slower")
- **3 FAQs** with age-specific answers
- **JSON-LD:** FAQPage + BreadcrumbList

### Data Generation

New file: `apps/web/data/per-age-tables.json`

Structure:
```json
{
  "good-5k-time-35-year-old-male": {
    "distance": "5k",
    "distanceMeters": 5000,
    "age": 35,
    "gender": "male",
    "wmsFactor": 0.9876,
    "levels": {
      "50": { "timeSeconds": 1800, "timeFormatted": "30:00", "pace": "9:39/mi", "label": "Recreational" },
      "60": { ... },
      "70": { ... },
      "80": { ... },
      "90": { ... }
    },
    "trainingPaces": { "easy": "...", "marathon": "...", "threshold": "...", "interval": "...", "repetition": "..." },
    "equivalents": { "10k": "...", "half": "...", "marathon": "..." },
    "adjacentAges": { "34": "...", "36": "..." }
  }
}
```

### Thin Content Risk Mitigation

Google's Helpful Content Update penalizes mass-generated thin pages. Each page MUST have:
1. Unique BLUF with actual numbers for that exact age (NOT a template with swapped variables)
2. Genuine variation in FAQ answers — not the same 3 questions with age swapped
3. Adjacent-age comparison section (unique to per-age pages)
4. At least 200 words of unique content per page
5. Calculator embed for hands-on engagement

The data IS genuinely different per age (WMA factors change at every age). The text must reflect this.

---

## Sitemap Strategy (MANDATORY: Automate)

Manual sitemap entries at 150+ pages will drift and break. The builder MUST automate sitemap generation.

**Implementation:** Generate sitemap entries programmatically from the same config objects that drive `generateStaticParams()`. Import the config objects into `apps/web/app/sitemap.ts` and map them to sitemap entries. This keeps the sitemap in sync with the pages automatically — adding a new page config entry automatically adds it to the sitemap.

**First task in Batch 2B:** Before adding any new pages, refactor `sitemap.ts` to generate existing 22 entries from config objects. Verify the output matches the current sitemap exactly. Then all new batches get sitemap entries for free.

---

## Non-Negotiable Quality Gates

- `node scripts/verify-bluf-data.mjs` must pass with 0 errors after every batch
- `npm run build` in `apps/web` must succeed with 0 errors
- Every BLUF paragraph and FAQ answer must contain numbers from the generated JSON — NO manually written numbers
- All pages return 200 in production after deploy
- All new URLs appear in `sitemap.xml`
- Existing 22 pages must be unchanged and still return 200

---

## Evidence Required Per Batch

1. Verification script output (0 errors)
2. Build output (success)
3. URL status check for all new pages (200)
4. Sitemap entry count (expected vs actual)
5. Spot-check: 3 randomly selected pages have correct BLUF numbers matching JSON data
6. Existing pages spot-check (3 random, still 200, unchanged)

---

## What NOT To Do

- Do NOT modify existing 22 pages
- Do NOT change the data generation pipeline architecture
- Do NOT use the production API for data that can be computed deterministically (only training paces require the API; age-grading, BQ, and equivalency are deterministic)
- Do NOT write BLUF or FAQ text from memory — all numbers come from generated data
- Do NOT skip the verification script
- Do NOT commit all 500+ pages in a single commit — batch commits per execution phase
