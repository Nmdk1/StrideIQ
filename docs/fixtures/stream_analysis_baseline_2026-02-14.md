# Stream Analysis Baseline Fixture — 2026-02-14

**Activity:** Morning Run
**Activity ID:** `256a2bcc-ead2-4d99-af65-62c3a6b46fcb`
**Athlete:** Michael Shaffer (Tier 1 — threshold_hr=165, max_hr=180, resting_hr=50)
**Date:** 2026-02-14 14:48:54 UTC
**Points:** 5,253 (~87 minutes per-second data)
**Channels:** altitude, latlng, moving, cadence, velocity_smooth, time, heartrate, grade_smooth, distance (9/9, 0 missing)

## Analysis Result

| Field | Value |
|---|---|
| tier_used | tier1_threshold_hr |
| confidence | 0.95 |
| cross_run_comparable | true |
| estimated_flags | (none) |

## Segments

| # | Type | Duration | Avg Pace (s/km) | Avg HR | Avg Grade |
|---|---|---|---|---|---|
| 1 | warmup | 17.5 min (0–1050s) | 343.4 | 118.9 | 0.16 |
| 2 | recovery | 46.5 min (1051–3842s) | 335.1 | 114.8 | 0.05 |
| 3 | steady | 41s (3843–3884s) | 300.9 | 108.6 | -0.99 |
| 4 | recovery | 8.8 min (3885–4412s) | 338.6 | 108.5 | -0.02 |
| 5 | steady | 52s (4413–4465s) | 297.8 | 107.1 | 0.05 |
| 6 | cooldown | 10.3 min (4466–5083s) | 286.4 | 98.8 | 0.34 |
| 7 | steady | 2.8 min (5084–5252s) | 253.1 | 99.6 | -0.83 |

**Note:** Segment labels "recovery" and "cooldown" are mechanical classifications based on HR relative to threshold. Athlete described the run as easy/recovery with a progressive finish to sub-marathon pace in the last 2 miles. HR data may have been unreliable during the fast finish (optical wrist HR suspected of underreading during pace change).

## Drift

| Metric | Value |
|---|---|
| Cardiac drift | -6.63% (HR decreased — likely artifact of unreliable HR during fast section) |
| Pace drift | +10.86% (pace got faster — progressive run) |
| Cadence trend | null |

## Moments (4)

| Type | Time (s) | Value | Context |
|---|---|---|---|
| grade_adjusted_anomaly | 1244 | 4.7 | Hill section |
| pace_surge | 2213 | 15.3 | Significant pace increase |
| grade_adjusted_anomaly | 4318 | -5.4 | Downhill |
| grade_adjusted_anomaly | 5142 | -4.0 | Downhill |

## Effort Intensity

- **Range:** 0.49 – 0.85
- **Warmup:** ~0.49–0.50 (low)
- **Main body:** ~0.65–0.78 (easy-moderate for Tier 1)
- **Progressive finish:** ~0.78–0.85 (moderate-hard)
- **End cooldown:** ~0.58–0.60

Full 5,253-point array available via endpoint or server archive.

## Known Issues Observed

1. **Cadence null in all segments** despite cadence channel being present. Strava cadence may need normalization (doubling from steps to spm) or format handling.
2. **Segment label accuracy** — main body labeled "recovery" because HR was below threshold recovery ceiling. Label reflects correct mechanical classification from the data, but doesn't match athlete's subjective description. HR data reliability may be the root cause.
3. **Optical HR underread suspected** — HR 99-108 during 253 s/km (6:47/mi) pace is physiologically unlikely for this athlete. Athlete confirmed subjective experience didn't match HR data for the fast section.

## Athlete Subjective Report

> "Easy/recovery until last two miles, then progressively got quicker down to sub marathon pace by the last half mile. HR seemed really low — possible watch HR glitch. Mechanically very tired but could have been singing the whole way."

This mismatch between data and perception validates the need for the reflection prompt (harder/as expected/easier) as a first-class input.

## Calibration Plan

Athlete will wear a high-end chest strap HRM on runs next week (week of 2026-02-17) to provide calibration data with reliable HR. Tomorrow's long hilly run (2026-02-15) will use wrist HR only — will provide terrain-based gradient test data.
