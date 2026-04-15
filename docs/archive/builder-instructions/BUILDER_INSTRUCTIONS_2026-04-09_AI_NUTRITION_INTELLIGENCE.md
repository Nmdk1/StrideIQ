# Builder Instructions: AI Nutrition Intelligence

**Date:** April 9, 2026
**Status:** APPROVED — build when founder says GO
**Spec:** `docs/specs/NUTRITION_PHOTO_TRACKING_SPEC.md` (full research, decision log, schemas)
**Estimated effort:** 3 sessions
**Priority:** Strategic (Product Strategy #16)

---

## Read Order (mandatory)

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/specs/NUTRITION_PHOTO_TRACKING_SPEC.md` (the full spec — read all of it)
3. This file (build instructions)
4. `apps/api/models.py` — `NutritionEntry` model (line ~904)
5. `apps/api/services/nutrition_parser.py` — existing text parser (deprecated gpt-4o-mini)
6. `apps/web/app/nutrition/page.tsx` — existing frontend (will be replaced)
7. `apps/api/routers/nutrition.py` — existing CRUD endpoints
8. `apps/api/services/correlation_engine.py` — `aggregate_daily_inputs()` for wiring

---

## What This Is

Three input modes for nutrition data, all feeding the correlation engine:

1. **Photo-based meals** — snap a photo, Kimi K2.5 identifies food,
   USDA FoodData Central provides verified macros, athlete confirms.
   Meal templates learn from repeated meals for one-tap logging.

2. **Barcode scanning** — scan a packaged food's barcode, get exact
   manufacturer nutrition from USDA Branded Foods via UPC lookup.
   Zero estimation error. No LLM involved. Fastest input method for
   packaged grocery items (protein bars, yogurt, granola, etc.).

3. **Fueling product library** — pre-seeded catalog of gels, drink mixes,
   bars, chews with exact manufacturer composition (carb source, G:F ratio,
   caffeine, fluid). Athletes build a personal shelf. One-tap logging
   with zero estimation error.

---

## CRITICAL: Mobile-First Design

This feature lives on phones. Every screen, every interaction, every
layout must be designed for a 390px-wide viewport FIRST, then adapted
upward. Athletes log food standing in their kitchen or sitting in their
car after a run. They will not use this on desktop.

**Design principles:**

- **Touch targets minimum 44px.** Every tappable element.
- **One-hand operation.** Primary actions reachable with thumb.
- **Photo capture uses native camera.** `<input type="file" accept="image/*" capture="environment">` — opens the device camera directly. No custom camera UI.
- **Loading states during Kimi analysis** (~2-3 seconds). Show a subtle
  shimmer or progress indicator over the photo. Do not block the UI.
- **Confirmation screen is a bottom sheet**, not a new page. Slides up
  over the photo. Athlete sees what they photographed and the detected
  items simultaneously.
- **Fueling shelf is a horizontal scroll of product chips**, not a grid.
  Brand logo/color optional. Product name + key stat (e.g., "40g carbs").
  One tap logs. Long-press for quantity.
- **No form fields visible by default.** The manual entry form is behind
  "Custom entry" — the primary paths are photo and shelf taps.
- **Dark theme, consistent with the rest of the app.** `slate-900` bg,
  `slate-800` cards, `slate-700` borders. Same design language as home,
  activity detail, and manual pages.
- **Daily summary at the top.** Show today's running total (cal, protein,
  carbs, fat, caffeine) as a compact horizontal bar. Updates live as
  entries are added.

**Reference the existing app for visual language.** The nutrition page
should feel like it belongs next to the activity detail page and the
Manual. Not like a bolted-on food logger.

---

## Session 1: Backend — Photo Pipeline + USDA Database

### 1.1 Alembic Migration: `usda_food` table

```sql
CREATE TABLE usda_food (
    id SERIAL PRIMARY KEY,
    fdc_id INTEGER UNIQUE NOT NULL,
    description TEXT NOT NULL,
    food_category TEXT,
    calories_per_100g FLOAT,
    protein_per_100g FLOAT,
    carbs_per_100g FLOAT,
    fat_per_100g FLOAT,
    fiber_per_100g FLOAT,
    source TEXT NOT NULL DEFAULT 'sr_legacy',
    cached_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_usda_food_description ON usda_food
    USING gin(to_tsvector('english', description));
```

### 1.2 Seed Script: `scripts/seed_usda_foods.py`

- Download SR Legacy + Foundation datasets from
  https://fdc.nal.usda.gov/download-datasets
- Parse the CSV/JSON. Extract per-100g values for calories (Energy),
  protein, carbohydrate, total fat, fiber.
- INSERT into `usda_food`. ~13MB of data, several thousand foods.
- Run manually on server after migration: `docker exec strideiq_api python scripts/seed_usda_foods.py`
- NOT in the alembic migration itself — keeps migrations fast.
- Idempotent: skip rows where `fdc_id` already exists.

### 1.3 USDA Food Lookup Service: `services/usda_food_lookup.py`

Three-tier lookup:

```python
def lookup_food(search_term: str, db: Session) -> Optional[FoodMatch]:
    """
    Tier 1: Local Postgres full-text search (sub-ms)
    Tier 2: USDA API search, cache result locally (200-500ms)
    Tier 3: Return None (caller falls back to LLM estimate)
    """
```

**Tier 1 — Local:**
```sql
SELECT *, ts_rank(to_tsvector('english', description), plainto_tsquery('english', :term)) AS rank
FROM usda_food
WHERE to_tsvector('english', description) @@ plainto_tsquery('english', :term)
ORDER BY rank DESC
LIMIT 1;
```

**Tier 2 — USDA API:**
- `POST https://api.nal.usda.gov/fdc/v1/foods/search`
  with `api_key` from env var `USDA_API_KEY` (free, get from fdc.nal.usda.gov)
- Parse top result, extract nutrients per 100g
- INSERT into `usda_food` with `source='api_cached'`
- Return the match

**Return type:**
```python
@dataclass
class FoodMatch:
    fdc_id: int
    description: str
    calories_per_100g: float
    protein_per_100g: float
    carbs_per_100g: float
    fat_per_100g: float
    fiber_per_100g: float
    source: str  # 'sr_legacy', 'foundation', 'api_cached'
```

### 1.4 Photo Nutrition Parser: `services/nutrition_photo_parser.py`

```python
def parse_food_photo(image_bytes: bytes, db: Session) -> PhotoParseResult:
    """
    1. Send image to Kimi K2.5 with chain-of-thought prompt
    2. Parse structured JSON (food items + estimated grams)
    3. Look up each item via usda_food_lookup
    4. Compute macros from (USDA per-100g × estimated grams / 100)
    5. Return structured result
    """
```

**Kimi K2.5 integration:** Use the existing Kimi client from the coach
model integration (`openai.AsyncOpenAI` with `settings.KIMI_BASE_URL`).
The Moonshot API is OpenAI-compatible and supports image input via the
standard multimodal content format:
```python
messages=[{
    "role": "user",
    "content": [
        {"type": "text", "text": "<chain-of-thought prompt from spec>"},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}}
    ]
}]
```
The prompt is in the spec (Component 1). Key: the LLM outputs
`usda_search` terms alongside food names — these are optimized for
USDA full-text search.

**IMPORTANT: Test the image input path explicitly.** The existing coach
client only sends text. The image content format must be tested against
the live Moonshot API to confirm it works with the `kimi-k2.5` model.
Write a standalone test script that sends a real food photo (any
sandwich or plate of food) to verify the API accepts images and returns
structured JSON before building the full pipeline.

**Fallback to GPT-5.4 Mini:** If Kimi returns an error, times out, or
returns malformed JSON, retry with OpenAI using the existing OpenAI
API key. Same prompt, same JSON schema. This fallback must be tested
explicitly — not just specced. Write a test that simulates a Kimi
failure and verifies the GPT-5.4 Mini path produces valid output.

**Return type:**
```python
@dataclass
class ParsedFoodItem:
    food: str
    grams: float
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    macro_source: str  # 'usda_local', 'usda_api', 'llm_estimated'
    fdc_id: Optional[int]

@dataclass
class PhotoParseResult:
    items: List[ParsedFoodItem]
    total_calories: float
    total_protein_g: float
    total_carbs_g: float
    total_fat_g: float
    total_fiber_g: float
```

### 1.5 API Endpoint: `POST /v1/nutrition/parse-photo`

- Accept `multipart/form-data` with `image` file field
- Optional query params: `entry_type` (default 'daily'), `activity_id`
- Call `parse_food_photo()`, return the `PhotoParseResult` as JSON
- Do NOT auto-save. Return the result for athlete confirmation.
  The frontend submits a separate `POST /v1/nutrition` to save.

### 1.6 Barcode Lookup Service: `services/barcode_lookup.py`

```python
def lookup_barcode(upc: str, db: Session) -> Optional[FoodMatch]:
    """
    1. Check local usda_food table for cached barcode result
    2. Query USDA FoodData Central API: /foods/search with query=upc, dataType=Branded
    3. Cache result locally in usda_food with source='branded_barcode'
    4. Return FoodMatch with exact manufacturer nutrition
    """
```

- USDA FoodData Central's Branded Foods dataset includes UPC/GTIN codes.
  The API search endpoint accepts a UPC string and returns the matching
  branded product with full nutrient data.
- On first scan of any product, the API call takes 200-500ms. The result
  is cached locally in `usda_food` with the UPC stored in a new
  `upc_gtin` column (add to the `usda_food` table migration):
  ```sql
  upc_gtin TEXT  -- UPC/GTIN barcode, nullable, indexed for barcode lookups
  ```
  Add index: `CREATE INDEX idx_usda_food_upc ON usda_food(upc_gtin) WHERE upc_gtin IS NOT NULL;`
- On repeat scans of the same product (any athlete), local lookup by
  `upc_gtin` is sub-millisecond. The barcode database grows organically
  across all athletes with zero ongoing API cost.
- If USDA API returns no match for a UPC, return None. The frontend
  falls back to photo or text input for that item.

**API endpoint:** `POST /v1/nutrition/scan-barcode`
- Accept JSON body: `{ "upc": "012345678905" }`
- Return: food name, serving size, macros per serving, `macro_source='branded_barcode'`
- Do NOT auto-save. Return for confirmation (the athlete may want to
  adjust the number of servings).

### 1.7 Update Text Parser: `services/nutrition_parser.py`

- Replace `gpt-4o-mini` (deprecated) with Kimi K2.5
- After Kimi identifies food items, look up each via `usda_food_lookup`
  instead of using the LLM-generated macro values
- Same two-step: LLM identifies → USDA provides macros
- Fall back to LLM macros if USDA lookup fails, with `macro_source='llm_estimated'`

### 1.8 Meal Template Model + Service

New table (alembic migration):
```sql
CREATE TABLE meal_template (
    id SERIAL PRIMARY KEY,
    athlete_id UUID NOT NULL REFERENCES athlete(id),
    meal_signature TEXT NOT NULL,
    items JSONB NOT NULL,
    times_confirmed INTEGER DEFAULT 1,
    last_used TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(athlete_id, meal_signature)
);
```

**Template matching:** When a new photo parse returns items, compute
a `meal_signature` from sorted food names. Check if the athlete has
a template with that signature. If match found AND `times_confirmed >= 3`,
return the template portions instead of the LLM estimate. The athlete
can still edit.

**Template learning:** When the athlete confirms a meal (taps "Looks right"
or edits and saves), upsert the template. Increment `times_confirmed`.
Update `items` with the confirmed portions.

**Match threshold should be generous.** 80% item overlap counts as a match.
If the athlete usually has oatmeal+banana+peanut butter and today skips
the banana, still suggest the template. The athlete removes the banana
with one tap rather than going through the full photo flow.

---

## Session 2: Backend — Fueling Product Library

### 2.1 Alembic Migration: `fueling_product` + `athlete_fueling_profile` + NutritionEntry updates

**Three schema changes in one migration:**

`fueling_product` table — schema in spec. Key columns: `brand`,
`product_name`, `variant`, `category`, `carbs_g`, `caffeine_mg`,
`carb_source`, `glucose_fructose_ratio`, `fluid_ml`, `sodium_mg`.

`athlete_fueling_profile` table — schema in spec. Links athlete to
products with `usage_context` and `notes`.

`NutritionEntry` additions:
```python
caffeine_mg = Column(Float, nullable=True)
fluid_ml = Column(Float, nullable=True)
carb_source = Column(Text, nullable=True)
glucose_fructose_ratio = Column(Float, nullable=True)
macro_source = Column(Text, nullable=True)
fueling_product_id = Column(Integer, ForeignKey("fueling_product.id"), nullable=True)
```

### 2.2 Seed Script: `scripts/seed_fueling_products.py`

Seed the product catalog from the table in the spec. ~22 products.

**STOP: Do NOT run this seed script until the founder has verified every
number against manufacturer labels or websites.** This is a founder
task, not a builder task. Wrong seed data corrupts the correlation
engine permanently — if Maurten Gel 160 says 38g carbs instead of 40g,
every caffeine-carb correlation finding for every athlete using it is
wrong forever unless caught. The builder writes the script and the seed
data file. The founder reviews the data file and says GO. Then the
script runs.

Idempotent: match on `(brand, product_name, variant)`.

### 2.3 Fueling Endpoints

`GET /v1/nutrition/fueling-products`
- Query params: `brand`, `category`, `search`
- Returns catalog entries. Public — all athletes see the same catalog.

`POST /v1/nutrition/fueling-products`
- Athlete adds a custom product not in catalog
- Set `is_verified=False`
- Require: brand, product_name, carbs_g, caffeine_mg at minimum

`GET /v1/nutrition/fueling-profile`
- Returns this athlete's shelf (active products from their profile)

`POST /v1/nutrition/fueling-profile`
- Add a product to the athlete's shelf
- Body: `{ product_id, usage_context, notes }`

`DELETE /v1/nutrition/fueling-profile/{product_id}`
- Remove from shelf (soft delete: `is_active=False`)

`POST /v1/nutrition/log-fueling`
- Log a fueling product use
- Body: `{ product_id, entry_type, activity_id?, quantity?, timing? }`
- Creates a `NutritionEntry` pre-populated from the product record:
  `calories`, `protein_g`, `carbs_g`, `fat_g`, `caffeine_mg`, `fluid_ml`,
  `carb_source`, `glucose_fructose_ratio`, `macro_source='product_library'`,
  `fueling_product_id`
- If `quantity > 1`, multiply all values
- If `quantity = 0.5`, halve all values

### 2.4 Correlation Engine Fueling Inputs

New function `aggregate_fueling_inputs()` in `correlation_engine.py`:

For each activity, query linked `NutritionEntry` rows. Derive:
- `pre_run_caffeine_mg` — sum caffeine from entries with
  `entry_type='pre_activity'` linked to this activity
- `pre_run_carbs_g` — same for carbs
- `during_run_carbs_g` — sum carbs from `entry_type='during_activity'`
- `during_run_carbs_g_per_hour` — `during_run_carbs_g / (activity.duration_s / 3600)`
- `during_run_caffeine_mg` — sum caffeine from during
- `during_run_fluid_ml` — sum fluid from during
- `daily_caffeine_mg` — sum caffeine across all entries for that date

Additionally derive:
- `pre_run_meal_gap_minutes` — minutes between last `NutritionEntry`
  with `timing < activity.start_time` and activity start. Reveals
  individual carb timing sensitivity: "You perform better when your
  last meal is 90-120 minutes before a threshold session" vs
  "Your long runs are better with food within 45 minutes."

Wire these into `aggregate_activity_level_inputs()` for activity-indexed
signals and `aggregate_daily_inputs()` for daily caffeine.

---

## Session 3: Frontend — Complete Nutrition Page Rebuild

**Replace `apps/web/app/nutrition/page.tsx` entirely.** The current page
is a basic form with hardcoded presets. The new page has three sections.

### 3.1 Page Layout (Mobile-First)

```
┌─────────────────────────────┐
│  Today's Nutrition          │
│  1,240 cal  98g P  142g C   │
│  48g F  210mg caffeine      │
├─────────────────────────────┤
│                             │
│  ┌─────┐ ┌─────┐ ┌────────┐ │
│  │  📷  │ │ ▦▦▦ │ │ Type   │ │
│  │Photo │ │Scan │ │ it...  │ │
│  └─────┘ └─────┘ └────────┘ │
│                             │
│  My Fueling Shelf           │
│  ┌────┐┌────┐┌────┐┌────┐  │
│  │M160││MCaf││SiS ││SiS+│→ │
│  │40g ││25g ││40g ││40g │  │
│  └────┘└────┘└────┘└────┘  │
│  [+ Add products]           │
│                             │
├─────────────────────────────┤
│  Today's Log                │
│  ┌───────────────────────┐  │
│  │ 🍳 Breakfast     475cal│  │
│  │ Oatmeal, banana, PB   │  │
│  ├───────────────────────┤  │
│  │ ⚡ Pre-run       25g C │  │
│  │ Maurten Gel Caf 100   │  │
│  │ + 100mg caffeine      │  │
│  ├───────────────────────┤  │
│  │ 🥗 Lunch        620cal│  │
│  │ Chicken salad          │  │
│  └───────────────────────┘  │
└─────────────────────────────┘
```

### 3.2 Photo Capture Flow

1. Athlete taps camera icon → native camera opens via
   `<input type="file" accept="image/*" capture="environment">`
2. Photo taken → show the image with a shimmer overlay while Kimi
   processes (~2-3 seconds)
3. Results arrive → bottom sheet slides up over the photo showing
   detected items with portions and macros
4. Each item is an editable row: food name, portion (g), macros
5. Bottom of sheet: total bar + "Looks right" (primary) + "Edit" (secondary)
6. "Looks right" → saves NutritionEntry, dismisses sheet, updates daily total
7. Edit → inline portion adjustment with +/- steppers, swipe to remove item,
   "+ Add item" at bottom

**Template match:** If the detected items match a saved template
(`times_confirmed >= 3`), show at the top of the sheet:
"Your usual breakfast?" with one-tap confirm using template portions.
The full detection results are below as fallback.

### 3.3 Barcode Scanner

1. Athlete taps barcode icon → camera opens in barcode scanning mode
2. **Implementation:** The safest cross-platform approach is
   `<input type="file" accept="image/*" capture="environment">` (same
   as photo capture) with client-side barcode decoding from the captured
   image using `html5-qrcode` (< 50KB, works on all browsers including
   iOS Safari). Do NOT rely on the browser `BarcodeDetector` API as the
   primary path — it is not supported on iOS Safari, and masters athletes
   skew heavily toward iPhone. The `html5-qrcode` library handles both
   live video scanning and static image decoding.
   **Test on iOS Safari explicitly.** If the iOS path is broken, half
   the user base cannot scan barcodes.
3. UPC detected → call `POST /v1/nutrition/scan-barcode`
4. Result arrives → show product name, serving size, macros
5. Athlete adjusts servings (default 1) with +/- stepper
6. Tap "Log" → saves NutritionEntry with `macro_source='branded_barcode'`

**If no match found:** Show a brief message "Product not found — try a photo
instead" with a one-tap fallback to photo or text input. No dead end.
**This will happen.** USDA Branded Foods covers ~400K products from
large manufacturers. Smaller brands, regional products, newly released
items, and store-brand products may not be in the dataset. The fallback
is not a bug — it is an expected limitation of a free database. Do not
treat scan failures as errors in logging or metrics.

**The barcode scanner is the fastest path for packaged foods.** An athlete
at Whole Foods scanning their Greek yogurt, protein bar, or granola gets
exact manufacturer macros in under 2 seconds. No LLM, no estimation.

### 3.4 Fueling Shelf

- Horizontal scrollable row of product chips
- Each chip shows: abbreviated product name + key stat
  (carbs for gels, caffeine if caffeinated, fluid for drinks)
- **Tap:** logs one serving immediately. Brief toast confirmation
  "Logged: Maurten Gel 160 (40g carbs)" with undo option (3 seconds)
- **Long-press:** opens quantity selector (0.5x, 1x, 2x, 3x)
- **[+ Add products]** button opens the catalog browser:
  search by brand, filter by category (gel/drink/bar/chew/electrolyte),
  tap to add to shelf

### 3.5 Activity Detail Integration

On `apps/web/app/activities/[id]/page.tsx`, add a section below the
existing content (below map, below Runtoon):

**For completed activities:**
```
What did you take?
[Shelf chips: M160, MCaf, SiS, SiS+, ...]
[📷 Photo]  [▦ Scan]  [Type it]
```

Timing context is auto-set based on position:
- If logged before activity start_time → `pre_activity`
- If logged during → `during_activity`  
- If logged after → `post_activity`

For during-run fueling on long runs (>60 min), show a timeline view
where the athlete can tap products onto approximate time points along
the run. This is optional — most athletes will just tap products and
the system tags them as `during_activity`.

### 3.6 Text Input

Keep the existing NL text input but route it through the updated parser
(Kimi + USDA lookup instead of gpt-4o-mini). Same UX: type, parse,
confirm, save. This handles "black coffee", "handful of almonds",
and other items that don't warrant a photo.

### 3.7 Daily Summary Bar

Fixed at the top of the nutrition page. Compact horizontal layout:

```
Today: 1,240 cal | 98g P | 142g C | 48g F | 210mg caf
```

Updates in real-time as entries are added. If no entries, show
"No entries today" in muted text — no guilt, no streaks, no pressure.

---

## What NOT to Build

- **Meal planning / recommendations.** The system discovers patterns,
  it doesn't prescribe diets.
- **Calorie targets or deficit tracking.** This is not a weight loss app.
  It's a correlation engine input.
- **Guilt mechanics.** No streaks, no "you forgot to log" notifications,
  no empty-state shaming. Partial data is fine. The engine works with
  what it has.
- **Meal selection menus.** The photo + template system handles recurring
  meals without a separate selection interface. Adding one creates three
  input modes for the same thing and feels like manual logging.

---

## Testing Requirements

### Backend Tests

- `test_usda_food_lookup.py`: local hit, API fallback, cache on API hit,
  both miss → None
- `test_nutrition_photo_parser.py`: mock Kimi response, verify USDA
  lookup called per item, verify macro computation, verify fallback to
  GPT-5.4 Mini
- `test_barcode_lookup.py`: local cache hit by UPC, API fallback on miss,
  cache on API hit, no-match returns None
- `test_fueling_log.py`: log product → NutritionEntry has correct macros
  from product record, quantity multiplier works, activity linking works
- `test_meal_template.py`: template creation on confirm, template match
  on re-detection, threshold behavior (< 3 confirms → no template suggestion)
- `test_fueling_inputs.py`: verify `aggregate_fueling_inputs()` produces
  correct `pre_run_caffeine_mg`, `during_run_carbs_g_per_hour`, etc.

### Frontend Tests

- Photo flow: camera opens, loading state shows, confirmation sheet
  renders with items, "Looks right" saves entry
- Fueling shelf: tap logs product, long-press shows quantity, add product
  from catalog works
- Mobile viewport: all touch targets >= 44px, no horizontal overflow,
  bottom sheet doesn't obscure photo

---

## Environment Variables

```
USDA_API_KEY=<free key from fdc.nal.usda.gov>
```

No other new env vars. Kimi K2.5 API key is already configured for
the coach model. OpenAI API key already exists for the text parser
fallback.

---

## Success Criteria

1. **Photo → macros in under 5 seconds** end-to-end (capture to
   confirmation screen). Measurable: log `photo_parse_latency_ms` on
   every call.
2. **One-tap fueling logging** from personal shelf, correct macros
   verified against manufacturer labels
3. **Meal templates activate by day 14** for athletes with regular
   eating patterns (>= 3 confirmations of same meal)
4. **Correlation engine produces nutrition findings by day 30** for
   athletes logging 2+ entries per day
5. **Kimi K2.5 → GPT-5.4 Mini fallback tested** with a real photo
   through both paths. Not just unit-mocked — a real image through
   each model producing valid structured JSON.
6. **Barcode scanning works on iOS Safari.** Tested on a real iPhone.
   Not just Chrome/Android.
7. **Mobile viewport compliance:**
   - Every interactive element >= 44px touch target (audit with
     browser DevTools in responsive mode)
   - No horizontal overflow at 390px viewport width
   - Bottom sheet confirmation does not obscure the action buttons
   - Fueling shelf scrolls horizontally without page scroll hijack
8. **`macro_source` field populated on every `NutritionEntry`.** Query
   `SELECT macro_source, COUNT(*) FROM nutrition_entry GROUP BY 1` —
   every row has one of: `usda_local`, `usda_api`, `llm_estimated`,
   `product_library`, `branded_barcode`. No NULLs on new entries.
