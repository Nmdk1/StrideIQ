# Garmin Data Opportunity Audit

**Date:** February 23, 2026  
**Purpose:** Comprehensive analysis of Garmin data now available to StrideIQ vs what we had before, what's being used, what's not, and what new features, insights, and correlations become possible.

---

## Part 1: What We Had Before (Strava Only)

### Activity data from Strava

| Field | Source |
|-------|--------|
| Distance, duration, elapsed time, moving time | Strava |
| Average/max heart rate | Strava |
| Average speed | Strava |
| Total elevation gain | Strava |
| Cadence (half-cadence, needs doubling) | Strava |
| GPS streams (lat/lng, altitude, velocity, HR, cadence) | Strava |
| Splits (auto-laps) | Strava |
| Best efforts (5K, 10K, etc.) | Strava |
| Temperature | Weather API lookup |

### Wellness data (manual entry only)

All wellness data came from manual athlete check-ins (`DailyCheckin` table):

| Field | Source | Reality |
|-------|--------|---------|
| Sleep hours | Athlete self-report | Often skipped |
| Sleep quality (1-5) | Athlete self-report | Subjective |
| Stress (1-5) | Athlete self-report | Subjective |
| Soreness (1-5) | Athlete self-report | Subjective |
| RPE (1-10) | Athlete self-report | Post-hoc |
| HRV (rMSSD, SDNN) | Athlete self-report | Almost never filled |
| Resting HR | Athlete self-report | Almost never filled |
| Enjoyment (1-5) | Athlete self-report | Optional |
| Confidence (1-5) | Athlete self-report | Optional |
| Motivation (1-5) | Athlete self-report | Optional |

**Critical gap:** The correlation engine has 16 input variables, but most wellness inputs depend on athletes manually filling out check-ins. Compliance is low. The engine was starving for data.

---

## Part 2: What Garmin Now Provides

### Tier 1 — Currently ingesting (live in production)

#### A. Activity data (replaces Strava, higher fidelity)

| Field | Garmin | Strava Equivalent | Advantage |
|-------|--------|-------------------|-----------|
| Distance, duration | Yes | Same | — |
| Average/max HR | Yes | Same | — |
| Average/max pace | Yes | Derived | Native |
| Average/max speed | Yes | Same | — |
| Elevation gain/loss | Yes | Gain only | Barometric altimeter (more accurate) |
| Steps per activity | Yes | No | New |
| Device name | Yes | No | Attribution + device-specific calibration |
| Cadence (steps/min, not half) | Yes | Half-cadence | More accurate, no doubling needed |
| Power (per-sample in streams) | Yes | No (without Stryd) | Native running power from watch |
| Active kilocalories | Yes | No | Activity-specific calorie burn |
| GPS streams (lat, lng, altitude, HR, cadence, speed, power, distance, temperature) | Yes | Similar | Power stream is new |

#### B. Daily wellness data (GarminDay — completely new, automatic)

| Field | What it is | Manual equivalent it replaces |
|-------|-----------|-------------------------------|
| `resting_hr` | Resting heart rate from device | Was manual check-in (almost never filled) |
| `avg_stress` / `max_stress` | Garmin stress score (1-100) | Was 1-5 subjective scale |
| `stress_qualifier` | calm/balanced/stressful/very_stressful | Nothing |
| `steps` | Daily step count | Nothing |
| `active_time_s` | Seconds of active time | Nothing |
| `active_kcal` | Active calories burned | Nothing |
| `moderate_intensity_s` / `vigorous_intensity_s` | WHO intensity minutes | Nothing |
| `min_hr` / `max_hr` | Daily HR range | Nothing |
| `body_battery_end` | End-of-day Body Battery | Nothing |
| `stress_samples` (JSONB) | Intraday stress at 3-min intervals | Nothing |
| `body_battery_samples` (JSONB) | Intraday Body Battery at 3-min intervals | Nothing |

#### C. Sleep data (completely new, automatic)

| Field | What it is |
|-------|-----------|
| `sleep_total_s` | Total sleep duration (seconds, precise) |
| `sleep_deep_s` | Deep sleep duration |
| `sleep_light_s` | Light sleep duration |
| `sleep_rem_s` | REM sleep duration |
| `sleep_awake_s` | Awake time during sleep |
| `sleep_score` | Garmin sleep score (0-100) |
| `sleep_score_qualifier` | EXCELLENT/GOOD/FAIR/POOR |
| Sleep SpO2 | Oxygen saturation during sleep (raw JSONB) |
| Sleep respiration | Breathing rate during sleep (raw JSONB) |

#### D. HRV data (completely new, automatic)

| Field | What it is |
|-------|-----------|
| `hrv_overnight_avg` | Overnight HRV average (ms) |
| `hrv_5min_high` | Best 5-minute HRV window (ms) |
| HRV values (JSONB) | Per-epoch HRV readings through the night |

#### E. User Metrics (new, automatic)

| Field | What it is |
|-------|-----------|
| `vo2max` | Garmin's estimated VO2 max (updates after qualifying runs) |

### Tier 2 — Available but not yet ingesting

| Data Source | What it provides | Status |
|-------------|-----------------|--------|
| **Menstrual Cycle Tracking (MCT)** | Cycle phases, predicted period dates, symptoms, cycle length | Permission granted (`MCT_EXPORT`), webhook endpoint defined, not yet registered |
| **Respiration** | Breathing rate trends | Deferred |
| **Body Composition** | Weight, BMI, body fat % | Deferred |
| **Pulse Ox** | SpO2 throughout the day | Deferred (sleep SpO2 already in sleep data) |
| **Skin Temperature** | Skin temp deviation during sleep | Deferred |
| **Epochs** | 15-minute granularity activity data | Deferred (high volume) |
| **Activity Files (FIT)** | Raw FIT binary with running dynamics | Deferred |

### Tier 3 — Available via FIT files only (not in JSON API)

| Field | What it is | Why it matters |
|-------|-----------|---------------|
| Stride length (per-second) | Step length in meters | Running economy indicator |
| Ground contact time (GCT) | Time foot is on ground (ms) | Form efficiency |
| Ground contact time balance | Left/right GCT % | Asymmetry detection |
| Vertical oscillation | Bounce height (cm) | Energy waste indicator |
| Vertical ratio | VO / stride length % | Running economy metric |

These require FIT file parsing (`GET /rest/activityFile`) — a significant engineering effort deferred to a future phase.

---

## Part 3: Critical Gap — Correlation Engine Not Using GarminDay

**This is the single highest-impact finding in this audit.**

The correlation engine (`services/correlation_engine.py`) currently reads wellness data exclusively from the `DailyCheckin` table (manual athlete input). It does NOT query `GarminDay` at all.

This means:
- Garmin is pushing sleep, HRV, stress, resting HR, and Body Battery data every day
- It's being stored in `GarminDay`
- **But the correlation engine ignores it entirely**
- The coaching insights, readiness scores, and N=1 correlations are running on sparse manual check-in data while rich device data sits unused

### What needs to happen

The correlation engine's input-building function must be extended to prefer `GarminDay` data over `DailyCheckin` data when available:

| Correlation input | Current source | Should be |
|-------------------|---------------|-----------|
| `sleep_hours` | `DailyCheckin.sleep_h` (manual) | `GarminDay.sleep_total_s / 3600` (automatic) |
| `hrv_rmssd` | `DailyCheckin.hrv_rmssd` (manual) | `GarminDay.hrv_overnight_avg` (automatic) |
| `resting_hr` | `DailyCheckin.resting_hr` (manual) | `GarminDay.resting_hr` (automatic) |
| `stress_1_5` | `DailyCheckin.stress_1_5` (manual) | `GarminDay.avg_stress` (automatic, remap 1-100 → scale) |
| `overnight_avg_hr` | `DailyCheckin.overnight_avg_hr` (manual) | `GarminDay.resting_hr` or daily HR data |

Plus new inputs that have NO manual equivalent:

| New correlation input | Source | What it enables |
|----------------------|--------|-----------------|
| `sleep_deep_pct` | `GarminDay.sleep_deep_s / sleep_total_s` | "Deep sleep > 20% correlates with +5% next-day efficiency" |
| `sleep_rem_pct` | `GarminDay.sleep_rem_s / sleep_total_s` | REM vs performance correlations |
| `sleep_score` | `GarminDay.sleep_score` | Single composite sleep quality metric |
| `body_battery_end` | `GarminDay.body_battery_end` | Recovery capacity before next run |
| `avg_stress` | `GarminDay.avg_stress` | Daily stress load vs performance |
| `hrv_5min_high` | `GarminDay.hrv_5min_high` | Peak parasympathetic recovery |
| `steps` | `GarminDay.steps` | Daily load beyond running |
| `active_kcal` | `GarminDay.active_kcal` | Energy expenditure vs recovery |
| `vigorous_intensity_s` | `GarminDay.vigorous_intensity_s` | Non-running training load |
| `vo2max` | `GarminDay.vo2max` | Fitness trend over time |

**Impact:** Moving from ~3-5 sparse manual inputs to 15+ daily automatic inputs transforms the correlation engine from a toy into a genuine N=1 intelligence system.

---

## Part 4: New Features Enabled by Garmin Data

### 4A. Immediate (data already flowing, needs code changes)

#### 1. Readiness Score V2 — Device-Based
Replace the current readiness score (which relies on manual check-ins) with a device-based readiness model using:
- HRV overnight average (deviation from personal baseline)
- Resting HR (deviation from baseline)
- Sleep score / sleep staging quality
- Body Battery end-of-day
- Yesterday's training load (already computed)

This removes the dependency on athletes remembering to check in. Every Garmin user gets an automatic readiness score every morning.

#### 2. Recovery Narrative
"You slept 6.2 hours with only 14% deep sleep — below your average of 19%. Your HRV dropped 8ms from baseline. Consider an easy day."

Data exists now. Just needs the intelligence pipeline to read `GarminDay` and narrate.

#### 3. Training Load in Context
Current training load (CTL/ATL/TSB) is computed from activities only. With Body Battery and stress data, we can show:
- "Your TSB says you're fresh, but your Body Battery is at 22 — your body disagrees"
- "High stress day (Garmin stress 78) — your body is absorbing non-running load"

#### 4. Sleep-Performance Correlation Cards
"Your last 30 days show: when you get > 7h sleep with > 18% deep sleep, your next-day pace is 15 sec/mi faster."

The data for this is in `GarminDay` right now. The correlation engine just needs to read it.

### 4B. Near-term (requires Tier 2 data ingestion)

#### 5. Women's Health Intelligence (MCT)

**This is the biggest untapped opportunity in the running app market.**

No major running platform provides meaningful menstrual cycle-aware coaching. Most either ignore it or offer a generic "you might feel tired during your period" tooltip.

What Garmin MCT provides:
- Current cycle phase (menstrual, follicular, ovulation, luteal)
- Predicted period dates
- Cycle length and regularity
- Symptoms logged on the device

What StrideIQ can do with it:

**a. Cycle-Phase Training Intelligence**
- **Follicular phase (days 1-14):** Higher pain tolerance, better glycogen storage, higher capacity for hard efforts. Coach can recommend quality sessions.
- **Ovulation window (day ~14):** Peak strength but also higher injury risk (ACL laxity increases with estrogen). Coach should note both.
- **Early luteal (days 15-21):** Core temperature rises, HR runs higher at same effort. Coach should expect elevated HR and not interpret it as declining fitness.
- **Late luteal / PMS (days 22-28):** Higher RPE at same intensity, reduced heat dissipation, potential GI issues. Coach should suggest easier efforts and not flag "declining performance."

**b. Cycle-Aware Readiness Score**
Adjust readiness expectations by phase. A readiness score of 65 in the late luteal phase is not the same as 65 in the follicular phase. The coaching narrative should reflect this.

**c. Cycle-Performance Correlations**
N=1 analysis specific to each athlete:
- "Your efficiency drops 4% in the last 3 days of your luteal phase — this is normal for you"
- "You tend to set PRs in days 8-12 of your cycle"
- "Your HRV is consistently 12ms lower during your period — your baseline adjusts"

**d. Symptom-Performance Correlations**
If the athlete logs symptoms (cramps, fatigue, bloating) on their Garmin:
- Correlate symptom days with performance changes
- "When you log cramps, your next-day performance shows no measurable impact — your concern may be worse than the reality"

**e. Race Planning Around Cycles**
"Your goal marathon falls on day 24 of your predicted cycle (late luteal). Historically, your performance is 2-3% below peak during this phase. Consider: hydration strategy, adjusted pace expectations, or discuss cycle management with your doctor."

#### 6. Body Battery Trend Intelligence
- Track Body Battery over weeks/months
- Identify chronic drain patterns
- "Your Body Battery hasn't reached 80 in 12 days — you're accumulating fatigue that TSB alone isn't capturing"

#### 7. Stress-Load Balance Visualization
- Overlay Garmin stress (life + training) with training load
- Show athletes when life stress is eating into recovery capacity
- "Your training load is moderate, but your all-day stress averages 62 — your body is under more total load than your running alone suggests"

### 4C. Future (requires FIT file parsing or new APIs)

#### 8. Running Economy Dashboard
With stride length, GCT, vertical oscillation, and vertical ratio from FIT files:
- Track running form metrics over time
- Identify efficiency trends
- "Your vertical oscillation has increased 0.8cm over 6 weeks — you may be losing efficiency"

#### 9. Asymmetry Detection
Ground contact time balance from FIT files:
- Detect L/R imbalance trends
- "Your GCT balance has shifted 2% leftward over the past month — worth noting for your next physio visit"

#### 10. Running Power Intelligence
Power data is already in Garmin activity streams:
- Power-based training zones (independent of HR lag)
- Power duration curve
- Efficiency factor (power/HR ratio) trends

---

## Part 5: Predictions Enabled

With 30+ days of GarminDay data per athlete, StrideIQ can build predictive models:

1. **Injury risk prediction:** Combine training load ramp rate + sleep quality decline + HRV suppression + stress elevation. When all four trend negatively simultaneously, flag risk before injury occurs.

2. **Performance readiness prediction:** "Based on your sleep, HRV, Body Battery, and training load pattern, you're in optimal condition for a hard effort today" — or — "not today."

3. **Race readiness assessment:** Leading into a goal race, track whether the athlete's recovery metrics are trending in the right direction during taper. "Your taper is working: HRV is up 15%, sleep score averaging 82, Body Battery consistently above 70."

4. **Overtraining syndrome early warning:** Chronically suppressed HRV + elevated resting HR + declining Body Battery trend + maintained or increasing training load = overtraining signal, before the athlete feels it.

5. **Cycle-phase performance prediction (women):** "Based on your personal history, expect your best performance window in 3-5 days (early follicular phase)."

---

## Part 6: Implementation Priority

### Priority 1 — Highest impact, data already exists (code changes only)

1. **Wire GarminDay into correlation engine** — unlocks all automatic correlations
2. **Device-based readiness score** — replaces manual check-in dependency
3. **Recovery narrative from GarminDay** — immediate coaching value

### Priority 2 — High impact, requires Tier 2 ingestion

4. **MCT ingestion + cycle-phase model** — register webhook, create `GarminCycle` model, build phase detection
5. **Cycle-aware coaching intelligence** — phase-adjusted narratives, readiness, race planning
6. **Body Battery trend intelligence** — chronic fatigue detection

### Priority 3 — Medium impact, significant engineering

7. **Running power intelligence** — power is already in streams, needs analysis pipeline
8. **Stress-load balance visualization** — new UI component
9. **FIT file parsing for running dynamics** — stride length, GCT, vertical oscillation

### Deferred

10. **Asymmetry detection** — requires FIT + sustained data collection
11. **Beat-to-beat HRV** — requires commercial license
12. **Epoch-level analysis** — 15-min granularity, high storage cost

---

## Part 7: Competitive Landscape

### What no one else is doing well

- **Strava:** No wellness data, no coaching intelligence, no correlations
- **TrainingPeaks:** Basic PMC chart, no wellness integration, no AI coaching
- **Garmin Connect:** Has all the device data but terrible at making it actionable — shows numbers without insight
- **Whoop:** Good recovery scores but no running-specific intelligence, no training plan integration
- **Apple Fitness:** Generic health tracking, no running coaching
- **Coros:** Good training load but no N=1 correlations, no AI coaching

### StrideIQ's unique position

StrideIQ is the only platform that can combine:
- Native device wellness data (Garmin)
- Running-specific training intelligence (our coaching engine)
- N=1 correlation analysis (personal patterns, not population averages)
- Cycle-phase awareness (women's health)
- Natural language coaching narrative (not just dashboards)

**The women's health angle is wide open.** No running platform does meaningful cycle-phase coaching. The data is available via Garmin MCT. The science is well-established. The market is underserved. Female runners are ~50% of the recreational running market and have zero tools that account for their physiology.

---

## Summary

| Category | Count |
|----------|-------|
| Data fields we had before (Strava + manual) | ~25 |
| Data fields Garmin adds (Tier 1, live now) | ~30 new |
| Data fields available in Tier 2 (not yet ingesting) | ~15 more |
| Data fields available via FIT files (future) | ~5 more |
| Correlation engine inputs currently used | 16 |
| Correlation engine inputs possible with GarminDay | 26+ |
| New features identified | 10 |
| Highest-impact unfixed gap | Correlation engine ignoring GarminDay |
