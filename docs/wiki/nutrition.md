# AI Nutrition Intelligence

## Current State

Full nutrition tracking with three input modes (photo, barcode, text), a fueling product library, nutrition planning with load-adaptive daily targets, and a reporting surface. Deployed April 9-10, 2026.

## Input Modes

### Photo Parsing
- Camera capture → LLM vision analysis → macro estimation
- Primary: Kimi K2.5 (multimodal), Fallback: GPT-4.1 Mini
- Returns per-item breakdown with portion estimates
- `macro_source: "llm_estimated"`

### Barcode Scanning
- `html5-qrcode` for cross-platform UPC scanning (iOS Safari compatible)
- GTIN-14 normalization for variant barcodes
- Lookup chain: local `usda_food` table (1.8M branded foods with UPCs) → Open Food Facts API → USDA FoodData Central API
- `macro_source: "branded_barcode"` or `"usda_local"`

### Natural Language Text
- "0.5 lb hamburger patty, kaiser roll" → parsed by Kimi K2.5 or GPT-4.1 Mini
- Prompt instructs LLM to respect explicit weights/quantities, not default to standard servings
- USDA lookup attempted on parsed notes for verification
- `macro_source: "llm_estimated"` or `"usda_local"` / `"usda_api"`

## Data Model

### Tables

| Table | Purpose |
|-------|---------|
| `nutrition_entry` | Per-entry log: date, entry_type, macros, caffeine, fluid, timing, notes, macro_source, fueling_product_id |
| `nutrition_goal` | Athlete targets: goal_type, protein_g_per_kg, carb_pct, fat_pct, caffeine, load_adaptive, load_multipliers |
| `usda_food` | 1.8M branded foods from USDA FoodData Central with UPCs |
| `fueling_product` | 97 endurance products (gels, drink mixes, bars, chews) with verified macros |
| `athlete_fueling_profile` | Per-athlete shelf of favorite fueling products |

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

1. **Athlete brief** (`coach_tools.py` → `build_athlete_brief`): "Nutrition Snapshot" section includes today's totals, goal type, day tier, multiplier, and calorie/macro targets
2. **Tools**: `get_nutrition_correlations` (relevant findings) and `get_nutrition_log` (recent entries) — coach can look up nutrition data on request

## Reporting

### Nutrition Page Tabs

| Tab | Content |
|-----|---------|
| **Log** | Today's entries (tap-to-edit, delete), input modes, fueling shelf, daily target progress |
| **History** | Date navigation, per-day entries with target comparison, 7-day summary, CSV export |
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
| `POST /v1/nutrition/parse-text` | NL text → macros |
| `POST /v1/nutrition/parse-photo` | Photo → macros |
| `POST /v1/nutrition/scan-barcode` | UPC → product lookup |
| `GET/POST /v1/nutrition/goal` | Nutrition goal CRUD |
| `GET /v1/nutrition/daily-target` | Computed daily targets + actuals + pacing |

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

## Sources

- `docs/specs/NUTRITION_PHOTO_TRACKING_SPEC.md`
- `docs/BUILDER_INSTRUCTIONS_2026-04-09_AI_NUTRITION_INTELLIGENCE.md`
- `docs/BUILDER_INSTRUCTIONS_2026-04-10_NUTRITION_PLANNING.md`
- `apps/api/routers/nutrition.py`
- `apps/api/services/nutrition_parser.py`
- `apps/api/services/nutrition_targets.py`
- `apps/web/app/nutrition/page.tsx`
