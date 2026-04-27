# AI Nutrition Intelligence

## Current State

Full nutrition tracking with three input modes (photo, barcode, text), a fueling product library, nutrition planning with load-adaptive daily targets, and a reporting surface. Deployed April 9-10, 2026.

## Input Modes

### Photo Parsing
- Camera capture → LLM vision analysis → macro estimation
- Primary: **Kimi `kimi-k2.6`** (multimodal, Moonshot API — `nutrition_photo_parser.py`), Fallback: **GPT-4.1 Mini**
- Returns per-item breakdown with portion estimates
- `macro_source: "llm_estimated"`

### Barcode Scanning
- `html5-qrcode` for cross-platform UPC scanning (iOS Safari compatible)
- GTIN-14 normalization for variant barcodes
- Lookup chain: local `usda_food` table (1.8M branded foods with UPCs) → Open Food Facts API → USDA FoodData Central API
- `macro_source: "branded_barcode"` or `"usda_local"`

### Natural Language Text
- "0.5 lb hamburger patty, kaiser roll" → parsed by **Kimi `kimi-k2.6`** or GPT-4.1 Mini (`nutrition_parser.py`)
- Prompt instructs LLM to respect explicit weights/quantities, not default to standard servings
- USDA lookup attempted on parsed notes for verification
- `macro_source: "llm_estimated"` or `"usda_local"` / `"usda_api"`
- **Known gap:** NL text parse results have no UPC / FDC ID / fueling_product_id assigned. When the athlete manually corrects macros after a text parse, `_maybe_learn_override_from_entry` silently skips (hits the `else: return` branch). **Text-keyed overrides are not yet built** — only barcode scans and USDA-matched entries learn from corrections. Workaround: save the food as a named meal in the Meals tab.

## Data Model

### Tables

| Table | Purpose |
|-------|---------|
| `nutrition_entry` | Per-entry log: date, entry_type, macros, caffeine, fluid, timing, notes, macro_source, fueling_product_id, **source_fdc_id**, **source_upc** |
| `nutrition_goal` | Athlete targets: goal_type, protein_g_per_kg, carb_pct, fat_pct, caffeine, load_adaptive, load_multipliers |
| `usda_food` | 1.8M branded foods from USDA FoodData Central with UPCs |
| `fueling_product` | 97 endurance products (gels, drink mixes, bars, chews) with verified macros |
| `athlete_fueling_profile` | Per-athlete shelf of favorite fueling products |
| `athlete_food_override` | Per-athlete macro corrections keyed on UPC / FDC ID / fueling_product_id (Apr 18, 2026) |
| `meal_template` | Saved or implicitly-learned meal patterns: name, is_user_named, name_prompted_at, items (Apr 18, 2026) |

### Entry Types

| Type | When |
|------|------|
| `daily` | General meals/snacks |
| `pre_activity` | Pre-run nutrition |
| `during_activity` | Mid-run fueling |
| `post_activity` | Post-run recovery |

## Nutrition Planning

### Goal Types

| Type | Behavior |
|------|----------|
| `performance` | Multipliers: rest 1.0, easy 1.15, moderate 1.3, hard 1.45, long 1.6 |
| `maintain` | Same multipliers as performance |
| `recomp` | Rest 0.85, easy 1.0, moderate 1.3, hard 1.45, long 1.6 (deficit on rest/easy only) |

### Daily Target Calculation

1. BMR via Mifflin-St Jeor (requires height_cm, weight_kg, age, sex)
2. Base calories = BMR × 1.2 (sedentary NEAT) — never add Garmin active_kcal on top
3. Day tier resolved from PlannedWorkout or Activity (highest tier wins for multi-activity days)
4. Final target = base × load_multiplier for day tier
5. Protein = protein_g_per_kg × weight_kg (subtracted first from calorie budget)
6. Remaining calories split by carb_pct / fat_pct (must sum to 1.0, validated on POST)
7. Timezone-aware pacing (time_pct) using `Athlete.timezone` via `zoneinfo`

Key files: `services/nutrition_targets.py`, `routers/nutrition.py`

## Fueling Shelf

- One-tap logging for endurance products (gels, bars, chews, drink mixes)
- Shelf items show full product name, variant, calories, and caffeine
- Products from `fueling_product` table (97 seeded products from Maurten, SiS, Gu, Clif, etc.)
- Athletes can add/remove products from their personal shelf

## Correlation Engine Wiring

Nutrition data feeds the correlation engine via `aggregate_fueling_inputs()`:

| Input Metric | Source |
|-------------|--------|
| `pre_run_caffeine_mg` | Pre-activity caffeine |
| `pre_run_carbs_g` | Pre-activity carbs |
| `during_run_carbs_g_per_hour` | During-activity carbs / duration |
| `pre_run_meal_gap_minutes` | Time between last meal and activity start |
| `daily_caffeine_mg` | Total daily caffeine |
| `daily_calories` | Total daily calories |
| `daily_protein_g` | Total daily protein |
| `daily_carbs_g` | Total daily carbs |
| `daily_fat_g` | Total daily fat |

## Coach Integration

The coach sees nutrition via two mechanisms:

1. **Athlete brief** (`services/coach_tools/brief.py` → `build_athlete_brief`): "Nutrition Snapshot" section includes today's totals, goal type, day tier, multiplier, and calorie/macro targets
2. **Tools**: `get_nutrition_correlations` (relevant findings) and `get_nutrition_log` (recent entries) — coach can look up nutrition data on request

As of Apr 27, 2026, the visible **Coach Runtime V2 packet** path has a selective `nutrition_context` retrieval slice in `services/coaching/runtime_v2_packet.py`. It is not a static nutrition encyclopedia: the block is added only when the latest athlete turn is about food logging, nutrition trends, fueling, race fueling, body-composition goals, or similar nutrition planning. The assembler queries `nutrition_entry` for the bounded athlete-local window implied by the question (today, yesterday, recent week/pattern window), returns capped rows plus additive per-date totals, and marks all totals as logged-so-far partial records rather than complete-day proof. Current-log/date-range asks also carry response guidance to answer the nutrition question directly and avoid connecting to training, races, workouts, or older threads unless the athlete explicitly asks for that linkage. The compact LLM prompt for those direct log asks is scoped to the current conversation turn plus `nutrition_context` only; calendar, recent-activity, training-adaptation, athlete-fact, and recent-thread blocks remain in the audit packet but are omitted from the prompt. Kimi still receives no tool definitions. Visible answers are additionally guarded by `services/coaching/voice_enforcement.py` and `services/coaching/qualitative_eval.py` so they should not expose implementation words like `packet`, `calendar_context`, `nutrition_context`, `runtime`, or `tool`; missing data should be phrased as “I don’t see logged entries” rather than “I do not have access.”

## Reporting

### Nutrition Page Tabs

| Tab | Content |
|-----|---------|
| **Today** | Today's entries (tap-to-edit, delete), input modes, fueling shelf, daily target progress |
| **History** | Date navigation, per-day entries with target comparison, 7-day summary, CSV export, **inline backfill via the same input modes** (photo / barcode / NL parse / shelf / manual), tap-to-edit any past entry within the 60-day window (Apr 18, 2026) |
| **Meals** | Saved meal templates: create, name, edit per-item macros, one-tap log to any selected day, delete (Apr 18, 2026) |
| **Insights** | Weekly averages, 30-day trend chart, pre-run fueling linked to activities |

### API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /v1/nutrition` | List entries by date range |
| `POST /v1/nutrition` | Create entry |
| `PUT /v1/nutrition/{id}` | Update entry |
| `DELETE /v1/nutrition/{id}` | Delete entry |
| `GET /v1/nutrition/summary` | Rolling window summary |
| `GET /v1/nutrition/activity-linked` | Activities with pre/during/post nutrition |
| `GET /v1/nutrition/export` | CSV download |
| `POST /v1/nutrition/parse` | NL text → single merged entry (Today-tab "Type" input) |
| `POST /v1/nutrition/parse-meal` | NL text → list of per-item entries (meal builder textarea) |
| `POST /v1/nutrition/parse-photo` | Photo → per-item entries |
| `POST /v1/nutrition/scan-barcode` | UPC → product lookup |
| `GET/POST /v1/nutrition/goal` | Nutrition goal CRUD |
| `GET /v1/nutrition/daily-target` | Computed daily targets + actuals + pacing |
| `POST /v1/nutrition/log-fueling` | One-tap shelf log (accepts optional `entry_date` for backfill) |
| `GET/POST/PATCH/DELETE /v1/nutrition/meals` | Saved meal templates CRUD |
| `POST /v1/nutrition/meals/{id}/log` | Log a saved meal to today or a selected past day (60-day window) |
| `POST /v1/nutrition/meals/{id}/dismiss-name-prompt` | Dismiss the "name this meal" prompt for a learned pattern |

### Past-Day Window (Apr 18, 2026)

`_validate_entry_date()` enforces a 60-day backfill window on every write path: `POST /v1/nutrition`, `PUT /v1/nutrition/{id}`, `PATCH /v1/nutrition/{id}`, `POST /v1/nutrition/log-fueling`, `POST /v1/nutrition/meals/{id}/log`. Future dates → 400. Anything older than `MAX_BACKLOG_DAYS = 60` → 400. Today through 60 days back → allowed. The window keeps correlation analytics clean while letting athletes correct missed meals.

## Per-Athlete Food Overrides (Apr 18, 2026)

When an athlete edits the macros of a logged food that came from a barcode scan or USDA lookup, the correction is persisted as an `athlete_food_override` row keyed on `(athlete_id, identifier)`. The next scan or parse for the same food returns the corrected values automatically, and the response is tagged `is_athlete_override=true` so the UI shows a **"Your values"** chip.

| Identifier | Precedence | Source |
|------------|------------|--------|
| `upc_normalized` | 1 (highest) | Barcode scans |
| `fueling_product_id` | 2 | Shelf logs |
| `fdc_id` | 3 | USDA lookups (text/photo parse) |

A check constraint on `athlete_food_override` enforces exactly one identifier per row. Edit auto-learn is best-effort and never blocks the user's save; failures log a warning. Service: `services/food_override_service.py`. Wires: `scan_barcode`, `parse_photo`, `create_nutrition_entry`, `update_nutrition_entry`, `patch_nutrition_entry`.

## Saved Meals — Meal Templates (Apr 18, 2026)

Athletes save recurring meals ("Workday Breakfast", "Long-run Pre-fuel") under a name and re-log them in one tap. Implicitly-learned patterns (the system already detected via `find_template`) surface a **"name this meal"** prompt once they've been confirmed three times so they become reusable.

- **Schema:** `meal_template` carries `name`, `is_user_named`, `name_prompted_at`, `created_at`. Partial index on `(athlete_id) WHERE is_user_named = true` for the named-meals picker.
- **Promotion, not duplication:** `save_named_template` promotes an existing implicit row in place rather than creating a duplicate.
- **Logging:** `log_template_for_athlete` builds a `NutritionEntry` with summed macros and `macro_source = "meal_template"`. Logs land on the user's `selectedDate` so the picker doubles as a backfill tool.
- **Noise control:** `upsert_template` skips single-item entries — the implicit learner only acts on comma-separated, multi-item, non-barcode entries. Prevents single barcode logs from polluting the table.
- Service: `services/meal_template_service.py`.

### Meal Builder Parse (Apr 18, 2026)

The meal builder has a "Paste your meal" textarea above the item rows. Athletes type free text ("2 eggs scrambled, 1 slice whole wheat toast, 1 tbsp peanut butter") and `POST /v1/nutrition/parse-meal` returns a list of structured items that pre-populate the rows. Each row stays editable so the athlete can adjust quantities or correct macros before saving.

**Service:** `services/nutrition_parser.py::parse_meal_items()`. Same provider order as the single-entry parser (**Kimi `kimi-k2.6`** primary, OpenAI fallback). Per-item USDA enrichment fills only the macros the LLM left null — never overwrites a value the LLM already produced. Empty input → 422. Both providers fail → 503.

The endpoint mirrors `/v1/nutrition/parse` but returns `{items: [{food, calories, protein_g, carbs_g, fat_g, fiber_g, macro_source}]}` instead of one merged total. Use `/parse` for the Today-tab "Type" input (single entry) and `/parse-meal` for the meal builder (per-item array).

## Nutrition as a First-Class Metric

Nutrition is not a sidecar feature. It sits at #3 in the hierarchy of training interventions — after health and consistency, before easy volume. The rationale: for athletes early in development, the difference between a good race and a bad race is almost always fueling, not fitness. For advanced athletes, fueling optimization (75-120 g/hr, GI training) is the difference between good and great. At every level, nutrition is a rate-limiter.

### Plan Generator Integration

All workouts ≥90 min include:
- `fueling_target_g_per_hr` in the segments schema
- A fueling reminder in the workout description text

Fueling targets scale with training age:
- Early development: 60 g/hr (building gut tolerance)
- Developing: 75 g/hr (standard trained)
- Established: 75-90 g/hr (race-ready)
- Race day: athlete's practiced rate from training logs

### Daily Briefing Integration

When tomorrow's workout is ≥90 min and nutrition data exists:
- Fueling history vs target comparison
- Pre-long-run preparation reminders

When no nutrition data exists: say nothing (no penalty UX).

### Future: Fueling Product Calculator

When the product library is combined with workout targets, the system can compute whether an athlete's planned products hit their g/hr target (e.g., "Your 2 gels + 1 bottle = ~65 g/hr. You need one more gel per hour to hit 90 g/hr.").

## Key Decisions

- **N=1 philosophy**: No population-based recommendations. No "you should eat X." Tracks what you eat, shows targets you set, surfaces correlations your data reveals.
- **First-class metric**: Nutrition is weighted equally with training load, sleep, and HRV in the correlation engine and briefing system. Not a sidecar.
- **Three-source macro lookup**: Local USDA → API → LLM fallback. LLM is last resort.
- **Load-adaptive**: Daily targets scale with training load tier, not a flat number.
- **`macro_source` tracked**: Every entry records how its macros were determined.
- **No `pytz`**: Uses Python stdlib `zoneinfo` for timezone handling.
- **Override scope gap (known, not yet fixed):** `_maybe_learn_override_from_entry` only learns from entries with a `source_upc`, `source_fdc_id`, or `fueling_product_id`. Plain NL text parse results never get an identifier assigned, so manual macro corrections on text-parsed entries are silently discarded. Mitigation: save the food as a named Meal template with correct macros. Fix: add `source_text_key` (normalized food name) as a 4th identifier type — not yet built.

## Frontend Notes

- **Autofill prevention (Apr 24, 2026):** All `<input>` and `<textarea>` fields in `apps/web/app/nutrition/page.tsx` have `autoComplete="off"` plus a semantic `name` attribute. Both surrounding `<form>` elements also carry `autoComplete="off"`. Without this, Android's system autofill service misidentified the macro entry grid as a payment form and offered credit card suggestions. The fix is deployed; existing PWA installs require force-close + reopen to clear the old autofill session.

## Sources

- `docs/specs/NUTRITION_PHOTO_TRACKING_SPEC.md`
- `docs/BUILDER_INSTRUCTIONS_2026-04-09_AI_NUTRITION_INTELLIGENCE.md`
- `docs/BUILDER_INSTRUCTIONS_2026-04-10_NUTRITION_PLANNING.md`
- `apps/api/routers/nutrition.py`
- `apps/api/services/nutrition_parser.py`
- `apps/api/services/nutrition_targets.py`
- `apps/api/services/coaching/runtime_v2_packet.py`
- `apps/api/services/coaching/voice_enforcement.py`
- `apps/web/app/nutrition/page.tsx`
