# ADR 10: Contextual Comparison Overhaul

**Status:** In Progress  
**Date:** 2026-01-11  
**Author:** AI Assistant  

---

## Context

The contextual comparison page currently displays minimal data from Strava activities. Beta testers include a world-renowned exercise physiologist (2:20 marathoner) and a sponsored professional runner. The current implementation appears as a toy, not a serious analytical tool.

Per the manifesto, this tool should provide **"the kind of insight that used to require a high-cost coach"** to everyday athletes.

## Decision

Overhaul the contextual comparison to display comprehensive analytical signals aligned with the manifesto's core metrics.

## Key Signals to Display

### 1. Efficiency Analysis (Master Signal per Manifesto)
- **Pace @ HR**: Speed produced per unit of physiological cost
- **Efficiency Factor (EF)**: Normalized pace / avg HR  
- **Efficiency vs Baseline**: % better/worse than similar runs
- **Aerobic Decoupling (Pa:Hr)**: First half vs second half efficiency ratio

### 2. Cardiac Analysis
- **Cardiac Drift**: HR increase over the run at similar pace
- **HR Zones Distribution**: Time in each zone
- **Max HR Context**: How close to max, recovery implications
- **HR vs Baseline**: Higher/lower than similar efforts

### 3. Pacing Analysis  
- **Fade Curve**: First half vs second half pace
- **Pace Variability**: Coefficient of variation across splits
- **Negative/Positive Split**: Classification and magnitude
- **Grade Adjusted Pace (GAP)**: If elevation significant

### 4. Environmental Context
- **Temperature Impact**: Heat/cold effects on performance
- **Elevation Profile**: Gain/loss and impact
- **Humidity**: If available
- **Conditions-Normalized Performance**: What would this have been at baseline conditions

### 5. Training Context
- **Workout Type Classification**: Easy, tempo, threshold, etc.
- **Where This Fits**: In weekly/monthly volume context
- **Intensity Score**: Relative to athlete's zones

### 6. Split-Level Analysis
Per split (mile/km):
- Pace
- HR  
- Cadence (if available)
- Efficiency (pace/HR for that split)
- GAP (if elevation data)

## Data Sources

### Already Available in Backend
From `Activity` model:
- duration_s, distance_m, avg_hr, max_hr
- total_elevation_gain, average_speed
- workout_type, workout_zone, intensity_score
- temperature_f, humidity_pct, weather_condition
- performance_percentage (age-graded)

From `ActivitySplit` model:
- split_number, distance, elapsed_time, moving_time
- average_heartrate, max_heartrate
- average_cadence
- gap_seconds_per_mile (Grade Adjusted Pace)

### Already Computed in `contextual_comparison.py`
- Similarity scores with breakdown
- Ghost average (baseline from similar runs)
- Performance score (vs baseline)
- Context factors with explanations
- Efficiency calculation (speed / avg_hr)

## Implementation Plan

### Phase 1: Backend Enhancement
1. Add cardiac drift calculation to split analysis
2. Add aerobic decoupling (Pa:Hr) calculation
3. Add pace variability metrics
4. Ensure all ActivitySplit data is returned
5. Add first-half vs second-half analysis

### Phase 2: Frontend Overhaul
1. Redesign page layout for serious analysis
2. Add efficiency comparison section
3. Add cardiac analysis section
4. Add pacing analysis section  
5. Enhanced split-by-split table with all metrics
6. Proper unit handling throughout

### Phase 3: Visualization
1. Dual-axis chart: Pace + HR over splits
2. Efficiency trend line
3. Cardiac drift visualization
4. Comparison overlays with ghost average

## Security Review

- No new endpoints - enhancing existing `/v1/compare/context/{activity_id}`
- All data is user's own data - no IDOR concerns
- No PII changes

## Testing Plan

- Unit tests for new calculations (cardiac drift, decoupling, variability)
- Integration test for enhanced API response
- Manual verification with real activity data

## Rollout

- Feature flag: Not required (enhancement to existing feature)
- Direct deployment after testing

---

## Files to Modify

### Backend
- `apps/api/services/contextual_comparison.py` - Add new calculations
- `apps/api/routers/contextual_compare.py` - Ensure full data returned

### Frontend  
- `apps/web/app/compare/context/[activityId]/page.tsx` - Complete overhaul
- `apps/web/lib/api/services/contextual-compare.ts` - Update types

---
