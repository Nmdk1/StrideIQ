# Nutrition Photo Tracking — Research & Implementation Spec

**Date:** April 8, 2026
**Status:** Researched, ready to build
**Estimated effort:** 2 builder sessions
**Priority:** Strategic (Product Strategy #16)

---

## The Problem

Athletes don't log food because manual entry is painful. StrideIQ already
has the full nutrition pipeline built — `NutritionEntry` model, CRUD API,
correlation engine wiring (`daily_protein_g`, `daily_carbs_g`, etc.),
activity-linked nutrition analysis, and a coach tool for nutrition
correlations. The missing piece is a low-friction input method: snap a
photo of your meal, get macros back, data flows into the correlation
engine automatically.

## Why This Matters for the Correlation Engine

The correlation engine needs consistent directional accuracy across many
observations. "Pre-run carbs above X grams correlate with better interval
quality" is a finding that requires the macro estimates to be directionally
consistent — not clinically precise, but reliably ranking high-carb vs
low-carb meals the same way every time.

This constraint eliminates pure LLM macro generation as an approach.

---

## Research Summary

### Approaches Evaluated

#### 1. General-Purpose LLM Vision (REJECTED)

Tested/benchmarked models: GPT-4o (deprecated Feb 2026), GPT-5 Mini
(deprecated Feb 2026), GPT-5.4 Mini (current), Claude Sonnet, Gemini 2.5
Flash, Kimi K2.5, Grok 4.1/4.20.

**Why rejected:** All general LLMs have two compounding error sources:
1. **Identification error** — model guesses what the food is
2. **Generation error** — model generates macro values from training data

A University of Gothenburg study (Oct 2025, 52 standardized food photos)
found 35-37% MAPE on calorie estimation across GPT-4o, Claude 3.5 Sonnet,
and Gemini 1.5 Pro. Systematic underestimation of large portions. High
variability in macronutrient estimation. The researchers concluded these
models are "not yet suitable for precise dietary assessment in athletic
populations."

The critical failure for our use case: inconsistent errors. If the model
sometimes estimates 45g carbs and sometimes 80g for the same meal type,
the correlation engine finds patterns between the model's imagination and
performance, not actual nutrition. The findings are meaningless.

**Food-specific benchmark data (current models):**

| Model | Benchmark | Score/Error | Notes |
|-------|-----------|-------------|-------|
| January AI (dedicated) | JFB | 86.24/100 | Best, but $1,499/mo |
| GPT-5 Mini | Nutrition Prediction | 13.9% MAPE (rank 3/50) | Deprecated Feb 2026 |
| Gemini 2.5 Pro | Nutrition Prediction | 15.8% MAPE (rank 4/50) | |
| Grok 4 | Nutrition Prediction | 22.3% MAPE (rank 17/50) | |
| Grok 3 Mini | Nutrition Prediction | 23.5% MAPE (rank 12/50) | |
| Kimi K2.5 | No food benchmark | Unknown | Strong general vision (78.5% MMMU-Pro) |
| GPT-5.4 Mini | No food benchmark | Unknown | Current OpenAI model |

No current (non-deprecated) model has been tested on the January Food
Benchmark. The JFB only tested deprecated models (GPT-4o, Gemini 2.5).
The Nutrition Prediction Benchmark tested 50 models but on text-based
ingredient-to-nutrition, not photo-to-nutrition.

#### 2. Dedicated Food Recognition APIs (EVALUATED, NOT SELECTED)

| API | Database Size | Pricing | Verdict |
|-----|--------------|---------|---------|
| **January AI** | 54M+ foods | $1,499/mo | Too expensive |
| **Passio AI** | 3.5M foods | $99/mo + $25/1M token overage. 30 athletes × 3 meals/day = ~$1,800/mo | Prohibitively expensive at our scale |
| **Edamam** | 900K foods | $14-299/mo + cumulative per-recipe licensing fees | Smallest database. Cumulative licensing trap. Mandatory attribution. Confusing plan structure. |
| **FatSecret** | 2.3M foods, 56 countries | Free for startups <$1M (Premier Free). Image recognition add-on priced in 25K-input tiers, 50% startup discount. | Opaque image recognition pricing. Requires contacting sales. Attribution required on free tier. |
| **LogMeal** | 1,300+ dishes | Credit-based, pricing not public | Limited ecosystem |
| **Calorie Mama** | 100K+ foods | $100/mo for 1,000 calls | Expensive per-call |

**Passio deep dive:** The $99/mo Starter plan includes only 1M tokens.
One photo = 20-30K tokens. At 30 athletes × 3 meals/day × 25K tokens =
67.5M tokens/month. The 1M included tokens last < 2 days. Overages at
$25/1M = $1,662.50/month on top of the $99 base. Auto-refill is enabled
by default.

**Edamam deep dive:** The "10,000 free vision calls" is only on the
$299/month EnterprisePlus plan. The Nutrition Analysis API charges a
per-recipe licensing fee that accumulates monthly forever. 100 unique
meals month 1, 50 month 2, 1 month 3 = paying for 151 recipes every
month indefinitely. Mandatory "Powered by Edamam" attribution with logo;
failure = immediate service suspension.

**FatSecret** remains a viable fallback if the build-your-own approach
hits coverage gaps. Premier Free qualification confirmed for StrideIQ
(under $1M revenue, under $1M raised). Image recognition add-on with
50% startup discount, actual pricing requires sales contact.

#### 3. Build Your Own: LLM Vision + USDA Database (SELECTED)

**Architecture:** Separate the two problems.
1. LLM identifies food items and estimates portion sizes (in grams)
2. USDA FoodData Central provides verified macro values for those foods

This is the same architecture all paid APIs use internally. We build it
ourselves with free components.

---

## Selected Architecture

```
Photo → LLM Vision → Structured ingredient list with portions
                          ↓
              USDA FoodData Central lookup
                          ↓
              Verified macros (cal, protein, carbs, fat, fiber)
                          ↓
              Athlete confirmation screen (tap to adjust)
                          ↓
              NutritionEntry saved → correlation engine
```

### Component 1: Vision Model for Food Identification

**Primary:** GPT-5.4 Mini ($0.75/1M input, $4.50/1M output)
- Already have OpenAI API key (used by existing NL parser)
- Current, non-deprecated model with vision support
- ~$0.003-0.005 per photo analysis

**Alternative:** Kimi K2.5 ($0.38/1M input, $1.72/1M output)
- Already integrated (coach model)
- Cheaper per call (~$0.001-0.003)
- No food-specific benchmarks available
- Native vision with MoonViT encoder

**Cost at 30 athletes, 3 meals/day:**
- GPT-5.4 Mini: ~$40/month
- Kimi K2.5: ~$25/month

**The LLM's job is narrow:** identify what food is in the photo, estimate
portion size in grams, output structured JSON. It does NOT generate
macro values. This eliminates the generation error source entirely.

**Prompt structure (chain-of-thought for accuracy):**

```
Analyze this food photo. For each food item visible:
1. Identify the food item specifically
2. Estimate its dimensions/volume relative to the plate/container
3. Estimate weight in grams based on the estimated volume
4. Provide a standardized search name for USDA FoodData Central lookup

Return JSON array:
[
  {"food": "grilled chicken breast", "grams": 180,
   "usda_search": "chicken breast meat cooked grilled"},
  {"food": "brown rice", "grams": 150,
   "usda_search": "rice brown cooked"},
  {"food": "steamed broccoli", "grams": 100,
   "usda_search": "broccoli cooked boiled"}
]
```

### Component 2: USDA FoodData Central (Nutrition Database)

**Verified facts:**
- Public domain, CC0 1.0 Universal license
- No restrictions on commercial use
- Free API: 1,000 requests/hour per IP (adequate for our scale)
- Full database downloadable: 458MB zipped, 3.1GB unzipped
- Covers 300,000+ foods: Foundation, SR Legacy, Branded, FNDDS
- Nutrients returned: 28+ including all macros we need
- Search endpoint: `/foods/search` with keyword matching
- Detail endpoint: `/food/{fdcId}` with full nutrient data

**API endpoints we need:**
- `POST /fdc/v1/foods/search` — search by food name
- `GET /fdc/v1/food/{fdcId}` — get full nutrient data

**Local hosting option:** Download the full CSV/JSON dataset and load
into our Postgres database. Eliminates rate limits entirely. The Branded
Foods dataset alone is 195MB zipped. For our use case, SR Legacy (12.3MB)
+ Foundation (467KB) covers common whole foods comprehensively.

**Open Food Facts (4M+ products) was evaluated but NOT selected** due
to the ODbL share-alike clause: merging their data into our database
would require releasing the combined database as open data. USDA has
no such restriction.

### Component 3: Food Matching Layer

The hardest engineering problem: bridging "grilled chicken breast" from
the LLM to USDA's "Chicken, broilers or fryers, breast, meat only,
cooked, grilled" (FDC ID 171077).

**Approach:**
1. Pre-build a cache of the 200-300 most common athlete foods with
   pre-resolved FDC IDs and nutrient values. Chicken breast, brown rice,
   oats, eggs, pasta, salmon, sweet potato, banana, protein powder, etc.
   This covers 80%+ of what serious runners eat.
2. For cache misses, use the USDA `/foods/search` endpoint with the
   LLM's `usda_search` term.
3. Store successful lookups in the cache for future use (the cache grows
   over time).
4. If no USDA match found, fall back to LLM-estimated macros with a
   flag marking the entry as "unverified" so the correlation engine can
   optionally exclude it.

### Component 4: Athlete Confirmation Flow

After the system identifies foods and retrieves macros, show the athlete:

```
Detected meal:
  Grilled chicken breast — 180g — 297 cal, 55g protein, 0g carbs, 6g fat
  Brown rice — 150g — 166 cal, 3g protein, 36g carbs, 1g fat
  Steamed broccoli — 100g — 35 cal, 2g protein, 7g carbs, 0g fat
  ─────────────────────────────────────────────
  Total: 498 cal | 60g protein | 43g carbs | 7g fat

  [Looks right ✓]  [Edit portions]  [Remove item]  [Add item]
```

Athlete taps "Looks right" for one-tap logging. Or adjusts portions if
the estimate is off. Corrections are stored and used for meal templates.

### Component 5: Meal Template Learning

After 30 days of logging, the system knows this athlete's recurring meals.
When the LLM identifies "chicken and rice" again, pre-populate with the
athlete's own confirmed portion sizes from previous logs rather than
generating a new estimate. Accuracy compounds over time.

Store templates as:
```python
{
    "athlete_id": uuid,
    "meal_signature": "chicken_breast+brown_rice+broccoli",
    "items": [
        {"food": "chicken breast", "fdc_id": 171077, "default_grams": 180},
        {"food": "brown rice", "fdc_id": 169704, "default_grams": 150},
        {"food": "broccoli", "fdc_id": 170379, "default_grams": 100}
    ],
    "times_confirmed": 12,
    "last_used": "2026-04-15"
}
```

---

## Accuracy Guardrails

1. **Chain-of-thought prompting** — LLM identifies items, estimates
   dimensions, then estimates weight. Halves error on simple dishes
   vs single-pass prompting.

2. **Reference object UX** — "For best results, include your hand or
   a fork in the photo." Provides scale reference for portion estimation.

3. **Athlete confirmation** — one-tap confirm or edit. Corrections
   calibrate future estimates.

4. **Meal templates** — recurring meals use athlete-confirmed portions.
   Accuracy compounds with use.

5. **Database-verified macros** — USDA values eliminate the macro
   generation error entirely. Error is contained to portion estimation
   only, which is a single inspectable source.

6. **Unverified flag** — entries where no USDA match was found are
   flagged so the correlation engine can weight or exclude them.

---

## What Already Exists (No Changes Needed)

- `NutritionEntry` model with calories, protein_g, carbs_g, fat_g,
  fiber_g, timing, activity_id linking
- Full CRUD API at `/v1/nutrition` (7 endpoints)
- `POST /v1/nutrition/parse` — text NL parsing (currently uses
  deprecated gpt-4o-mini, generates macros from model weights)
- Frontend nutrition page with quick-add presets and custom entry
- Correlation engine wiring: `daily_protein_g`, `daily_carbs_g`,
  `daily_fat_g`, `daily_fiber_g`, `daily_calories` as input signals
- `aggregate_activity_nutrition` for pre/post activity analysis
- Coach tool `get_nutrition_correlations`
- `VoiceInput.tsx` component (built but not connected)

## What Needs to Be Built

### Session 1: Backend Pipeline

1. **USDA food lookup service** (`services/usda_food_lookup.py`)
   - Pre-seeded cache of 200-300 common athlete foods with FDC IDs
   - Search function that queries USDA API for cache misses
   - Nutrient extraction: calories, protein, carbs, fat, fiber per gram
   - Cache persistence (store successful lookups in database or JSON)

2. **Photo nutrition parser** (`services/nutrition_photo_parser.py`)
   - Accept image bytes or base64
   - Send to GPT-5.4 Mini (or Kimi K2.5) with chain-of-thought prompt
   - Parse structured JSON response (food items + estimated grams)
   - Look up each item in USDA via the food lookup service
   - Compute total macros from (USDA nutrients per gram × estimated grams)
   - Return structured result with ingredient list + macros + confidence

3. **New API endpoint** (`POST /v1/nutrition/parse-photo`)
   - Accept multipart/form-data with image file
   - Return detected ingredients, portions, macros, and confirmation UI data
   - Optional: accept `entry_type` and `activity_id` for linking

4. **Update existing text parser** (`services/nutrition_parser.py`)
   - Replace deprecated `gpt-4o-mini` with current model
   - Route macro lookup through USDA instead of LLM generation
   - Same two-step architecture: LLM identifies food → USDA provides macros

5. **Meal template model and service**
   - Store athlete-confirmed meal patterns
   - Match incoming meals against templates
   - Pre-populate portions from confirmed history

### Session 2: Frontend + Polish

6. **Photo capture on nutrition page**
   - Camera button on `/nutrition` page (mobile-first)
   - Capture or select photo from gallery
   - Show loading state during analysis

7. **Confirmation screen**
   - Display detected ingredients with portions and macros
   - One-tap confirm or edit individual items
   - "Add item" / "Remove item" controls
   - Submit confirmed entry to `POST /v1/nutrition`

8. **Post-run nutrition prompt** (home page integration)
   - After a run is detected, show a subtle prompt:
     "What did you eat before your run?" with camera + text options
   - Links nutrition entry to the activity via `activity_id`

9. **Meal template suggestions**
   - When photo analysis matches a previously confirmed meal,
     show "Is this your usual [chicken and rice]?" with one-tap logging

---

## Cost Analysis

| Scale | Photos/month | Vision cost | USDA cost | Total |
|-------|-------------|-------------|-----------|-------|
| 5 athletes, 2 meals/day | 300 | $1.50 | $0 | $1.50/mo |
| 30 athletes, 3 meals/day | 2,700 | $13.50 | $0 | $13.50/mo |
| 200 athletes, 3 meals/day | 18,000 | $90 | $0 | $90/mo |
| 1,000 athletes, 3 meals/day | 90,000 | $450 | $0 | $450/mo |

At 1,000+ athletes, consider hosting a local USDA database copy to
eliminate API rate limits (1,000/hour would need ~90 requests/hour,
well within limits, but local is faster).

---

## Comparison to Rejected Alternatives

| | Build Your Own | Passio AI | Edamam | FatSecret |
|---|---|---|---|---|
| **Monthly cost (30 athletes)** | $13.50 | ~$1,800 | $299+ cumulative | Free + opaque add-on |
| **Database size** | 300K+ (USDA) | 3.5M | 900K | 2.3M |
| **Attribution required** | No | No | Yes (mandatory) | Yes (free tier) |
| **Vendor lock-in** | None | High | High | Medium |
| **Accuracy source** | USDA verified | Database-backed | Database-backed | Database-backed |
| **Meal learning** | Yes (we build it) | No | No | No |
| **Integration effort** | 2 sessions | 1-2 sessions | 1-2 sessions | Unknown |

---

## Fallback Plan

If USDA FoodData Central has meaningful coverage gaps for foods our
athletes commonly eat (e.g., specific restaurant dishes, regional foods),
contact FatSecret for Premier Free qualification and image recognition
add-on pricing. StrideIQ qualifies now (under $1M revenue, under $1M
raised). FatSecret's 2.3M food database across 56 countries would fill
coverage gaps. The architecture is designed so the database lookup layer
can be swapped without changing the vision or confirmation components.

---

## Minimum Accuracy Threshold

For the correlation engine specifically: we need consistent direction,
not absolute precision. A model that consistently estimates 45g carbs
when the actual value is 60g will still find the correct relative
threshold — just at a lower absolute number.

The failure mode that destroys correlation discovery is random
inconsistency: sometimes 45g, sometimes 80g, sometimes 30g for the
same meal type. That is noise, not signal.

Database-matched macros with USDA verified values eliminate random
inconsistency from the macro estimation step entirely. The remaining
error — portion size estimation — is:
1. A single, inspectable error source (not two compounding ones)
2. Reducible through athlete confirmation and meal templates
3. The same limitation accepted by nutrition researchers using
   photo-based dietary assessment methods

---

## Decision Log

| Date | Decision | Reasoning |
|------|----------|-----------|
| 2026-04-08 | Rejected pure LLM macro generation | Two compounding error sources produce inconsistent noise that corrupts correlation signals |
| 2026-04-08 | Rejected Passio AI | $1,800/mo at our athlete count due to token overage economics |
| 2026-04-08 | Rejected Edamam | Smallest database (900K), cumulative licensing trap, mandatory attribution |
| 2026-04-08 | Deferred FatSecret | Viable fallback. Opaque image recognition pricing. Will contact if USDA coverage is insufficient. |
| 2026-04-08 | Rejected January AI | $1,499/mo. Order of magnitude over budget. |
| 2026-04-08 | Selected build-your-own | LLM vision (identification only) + USDA database (verified macros). $13.50/mo at current scale. No vendor lock-in. Meal template learning compounds accuracy. |
| 2026-04-08 | Selected GPT-5.4 Mini for vision | Current model, existing API key, adequate vision accuracy for food identification (not macro generation) |
| 2026-04-08 | USDA FoodData Central for database | Public domain, free, 300K+ foods, downloadable for local hosting |
| 2026-04-08 | Rejected Open Food Facts | ODbL share-alike clause would require releasing combined database as open data |

---

## References

- University of Gothenburg study (Oct 2025): "Image-based nutritional
  assessment: Evaluating the performance of ChatGPT-4o on simple and
  complex meals" — 35-37% MAPE across GPT-4o, Claude 3.5, Gemini 1.5
- January Food Benchmark (JFB): 1,000 real-world food images,
  January AI scored 86.24, GPT-4o scored 74.11 (both deprecated)
- Nutrition Prediction Benchmark (jdleo): 50 models tested on Google
  cafeteria menus, DeepSeek R1 best at 12.3% MAPE
- USDA FoodData Central: fdc.nal.usda.gov — CC0 license, free API
- Open Food Facts: openfoodfacts.org — ODbL license, 4M+ products
