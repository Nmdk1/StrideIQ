# ADR-009: Pre-Race State Fingerprinting

## Status
Accepted

## Date
2026-01-14

## Context

### The Problem

Conventional fitness apps apply population-level rules to HRV and readiness:
- "High HRV = ready to perform"
- "Low HRV = fatigued, back off"

**User's actual data contradicts this:**
> "My best races were after the evening of my lowest HRV"

This is not an anomaly. Sports science research shows:
1. Pre-race sympathetic activation lowers HRV but primes performance
2. Taper-induced HRV drops can signal readiness, not fatigue
3. Individual response patterns vary enormously

### Current Gap

StrideIQ has:
- DailyCheckin with HRV (rMSSD, SDNN), sleep, stress, soreness, motivation, confidence
- Race detection (is_race_candidate, workout_type='race', performance_percentage)
- Training load metrics

What's missing:
- Analysis of pre-race state patterns
- Comparison of best vs. worst race states
- Personal readiness signature detection

## Decision

Implement Pre-Race State Fingerprinting:

### 1. Data Collection Window

For each race, extract state from 24-72 hours before:
- HRV (rMSSD deviation from baseline)
- Sleep (hours and quality)
- Resting HR (deviation from baseline)
- Subjective stress (1-5)
- Training load (7-day ATL)
- Days since last hard workout
- Motivation/confidence (if available)

### 2. Race Classification

Classify races by performance quality:
- **Best**: Top 25% by age-graded percentage
- **Good**: 50-75th percentile
- **Average**: 25-50th percentile
- **Worst**: Bottom 25%

### 3. Pattern Discovery

Statistical comparison between best and worst races:
- For each feature: mean, variance across race categories
- Mann-Whitney U test for significance (non-parametric, handles non-normal distributions)
- Effect size (Cohen's d)

### 4. Personal Readiness Profile

Output:
- Features that distinguish best vs. worst races
- Optimal pre-race state ranges (personalized)
- Counter-conventional findings (e.g., "Your best races follow low HRV")

### 5. Insight Surfacing

Only surface when:
- N >= 5 races with pre-race data
- At least one feature shows p < 0.05
- Effect size is meaningful (Cohen's d > 0.5)

## Implementation

### New Service

`apps/api/services/pre_race_fingerprinting.py`:
- `extract_pre_race_state(race: Activity, db: Session)` - Get state 24-72h before
- `classify_races(races: List[Activity])` - Classify by performance
- `compare_race_categories(best: List, worst: List)` - Statistical comparison
- `generate_readiness_profile(athlete_id: str, db: Session)` - Full analysis

### API Endpoint

`/v1/analytics/readiness-profile`:
- Returns personal readiness fingerprint
- Lists distinguishing features with confidence
- Shows optimal pre-race ranges

### Database

No schema changes needed - uses existing DailyCheckin and Activity tables.

## Consequences

### Positive
- Discovers athlete's actual readiness patterns (not population assumptions)
- Can surface counter-conventional insights
- Directly addresses user's HRV observation
- High engagement: shows personalized, non-obvious insights

### Negative
- Requires enough race data (N >= 5)
- Pre-race check-in data must exist
- May surface confusing insights initially (needs good explanation)

## Test Plan

1. Unit tests for each function
2. Test with synthetic data (known patterns)
3. Test edge cases (no races, all same performance, missing pre-race data)
4. Validate statistical tests with known distributions

## Feature Flag

`analytics.pre_race_fingerprinting` - Currently disabled, enable after implementation
