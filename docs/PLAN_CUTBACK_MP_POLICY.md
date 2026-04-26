# Cutback weeks & marathon-pace policy (plan framework)

**Status:** Implemented in `plan_framework` (generator + scaler + validator).  
**Owner intent:** Founder / head coach — consolidation deloads, not “hide MP inside a cutback long.”

## Principles

1. **No marathon-pace long on cutback weeks**  
   `_will_week_have_mp_long` keeps `if is_cutback: return False`. A cutback is not the week to run a dress-rehearsal MP long.

2. **Cutback = lower intensity, not a second threshold day**  
   For `marathon` and `half_marathon`, the primary quality slot on a cutback is **`easy_strides`** (not threshold). Shorter easy long is already selected via `_get_long_run_type`.

3. **Optional MP “touch” (mid/high/elite only)**  
   On cutback weeks in `marathon_specific` / `race_specific`, the **medium-long** slot may become **`mp_touch`**: a **shorter** mid-week run with **~2.5–4 mi at MP** and easy bookends.  
   **Gates:** `tier in ("mid", "high", "elite")` **and** (`weekly_volume >= 50` **or** `experienced_high_volume`).  
   **Builder / low:** no MP on cutback — pure consolidation.

4. **Validator alignment**

   - **`MP_TYPES`** includes `mp_touch` so totals and alternation rules stay consistent.  
   - **`assert_mp_total`** uses **miles at MP from segments** (not full session distance) for all `MP_TYPES`.  
   - **`assert_mp_total` floors** use `plan.volume_tier` when no athlete profile is passed (builder / low get lower strict floors — realistic for volume).  
   - **`assert_cutback_pattern`** treats `plan.volume_tier == "builder"` like a profile builder tier for detection threshold (10% cutbacks visible).

## Code map

| Piece | Location |
|-------|----------|
| Cutback → no MP long | `generator.py` — `_will_week_have_mp_long` |
| Cutback → easy_strides quality (M/HM) | `generator.py` — `_get_quality_workout` |
| Cutback → optional `mp_touch` | `generator.py` — `_get_workout_for_day` (`medium_long`) |
| `mp_touch` scaling | `workout_scaler.py` — `_scale_mp_touch` |
| MP totals, cutback detection | `tests/plan_validation_helpers.py` — `assert_mp_total`, `assert_cutback_pattern` |

## Explicit non-goals

- Do **not** reintroduce full MP longs on cutback to satisfy a numeric MP-mile floor.  
- Do **not** apply `mp_touch` on builder/low cutbacks.
