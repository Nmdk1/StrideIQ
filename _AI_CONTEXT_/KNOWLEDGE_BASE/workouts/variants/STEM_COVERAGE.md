# Plan engine stems → pilot KB (coverage)

**Purpose:** One place to see which **`workout_type`** strings the **plan generator** chooses and which strings the **scaler** puts on **`ScaledWorkout`**, and which **pilot file** owns variant prose. Update when `generator.py` or `workout_scaler.py` adds a new primary type.

**Source of truth for shapes:** `apps/api/services/plan_framework/workout_scaler.py` (`scale_workout`) and `generator.py` (`_get_workout_for_day` return values).

| `workout_type` | Pilot KB file | Notes |
|----------------|---------------|--------|
| `threshold` | `threshold_pilot_v1.md` | Continuous T |
| `threshold_intervals` | `threshold_pilot_v1.md` | Cruise / broken T |
| `long` | `long_run_pilot_v1.md` | **`generator.py`** — weekly long slot (easy long) **before** scaling. |
| `long_run` | `long_run_pilot_v1.md` | **`ScaledWorkout.workout_type`** from `_scale_long_run` when input is `long` or `long_run` — same easy-long intent as `long`. |
| `medium_long` | `long_run_pilot_v1.md` | Mid-week endurance |
| `long_mp` | `long_run_pilot_v1.md` | Option B may emit `long_mp_intervals` — same family |
| `long_hmp` | `long_run_pilot_v1.md` | |
| `easy` | `easy_pilot_v1.md` | Alias `easy_run` in scaler |
| `recovery` | `easy_pilot_v1.md` | |
| `easy_strides` | `easy_pilot_v1.md` | |
| `rest` | `easy_pilot_v1.md` | |
| `hills` | `easy_pilot_v1.md` | |
| `strides` | `easy_pilot_v1.md` | Standalone strides stem |
| `intervals` | `intervals_pilot_v1.md` | Aliases `interval`, `vo2max` |
| `repetitions` | `repetitions_pilot_v1.md` | Alias `reps` |

**Not a separate pilot (variants live inside pilots above):** `long_mp_intervals` (MP long option B — document under long/MP family; scaler emits explicitly).

**Last reviewed:** 2026-03-22 (added explicit `long_run` scaler emission)
