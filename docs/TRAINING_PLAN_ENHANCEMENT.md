# Training Plan Enhancement - Complete Documentation

## Overview

This document captures the full context, implementation, and future roadmap for StrideIQ's training plan generation system. It serves as the authoritative reference for understanding how plans are generated and what enhancements have been made.

**Date**: January 2026  
**Status**: Phase 1 Complete, Phase 2 Proposed

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Phase 1 Enhancements (Complete)](#phase-1-enhancements-complete)
3. [Phase 2 Roadmap (Proposed)](#phase-2-roadmap-proposed)
4. [User Feedback Analysis](#user-feedback-analysis)
5. [Technical Reference](#technical-reference)
6. [Testing Requirements](#testing-requirements)

---

## System Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    PLAN GENERATION FLOW                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Individual Performance Model                                │
│     └─► Calibrates τ1, τ2, k1, k2 from athlete history         │
│     └─► services/individual_performance_model.py                │
│                                                                 │
│  2. Optimal Load Calculator                                     │
│     └─► Calculates week-by-week TSS trajectory                 │
│     └─► Determines taper timing based on τ1, τ2                │
│     └─► services/optimal_load_calculator.py                     │
│                                                                 │
│  3. Model-Driven Plan Generator                                 │
│     └─► Converts TSS targets to actual workouts                │
│     └─► Scales to athlete baseline (not population defaults)   │
│     └─► services/model_driven_plan_generator.py                 │
│                                                                 │
│  4. Race Predictor                                              │
│     └─► Projects race-day performance from planned load        │
│     └─► services/race_predictor.py                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Key Data Structures

```python
# Individual model parameters (from athlete's training history)
BanisterModel:
    tau1: float        # Fitness time constant (days) - how fast you adapt
    tau2: float        # Fatigue time constant (days) - how fast you recover
    k1: float          # Fitness gain multiplier
    k2: float          # Fatigue gain multiplier
    confidence: Enum   # HIGH, MODERATE, LOW, UNCALIBRATED

# Daily workout prescription
DayPlan:
    date: date
    workout_type: str      # "easy", "threshold", "long_run", etc.
    name: str              # Human-readable name
    description: str       # Detailed instructions
    target_tss: float      # Training Stress Score
    target_miles: float    # Distance
    target_pace: str       # Pace prescription
    intensity: str         # "easy", "moderate", "hard", "race"
    notes: List[str]       # Additional guidance
    rationale: str         # NEW: Why this workout (transparency)

# Weekly structure
WeekPlan:
    week_number: int
    phase: str             # "base", "build", "peak", "taper"
    target_tss: float
    target_miles: float
    days: List[DayPlan]
    is_cutback: bool
```

---

## Phase 1 Enhancements (Complete)

### 1. τ1-Aware Taper Calculation

**Problem**: Taper duration was only based on τ2 (fatigue clearance). Fast adapters (low τ1) lose fitness faster and need shorter tapers, but this wasn't considered.

**Solution**: Modified `calculate_optimal_taper_days()` to factor in τ1:

```python
# New logic in individual_performance_model.py
if self.tau1 < 30:
    # Fast adapter: shorter taper (1.75 × τ2, bounded 7-14 days)
    taper_days = int(1.75 * self.tau2)
    taper_days = max(7, min(14, taper_days))
elif self.tau1 < 40:
    # Standard adapter: 2 × τ2, bounded 10-18 days
    taper_days = int(2.0 * self.tau2)
    taper_days = max(10, min(18, taper_days))
else:
    # Slow adapter: can handle longer taper (2.25 × τ2, bounded 14-21 days)
    taper_days = int(2.25 * self.tau2)
    taper_days = max(14, min(21, taper_days))
```

**Impact for User**: With τ1=25d (fast adapter), expected taper is now ~12 days (2 weeks) instead of 21 days (3 weeks).

**Files Modified**: `apps/api/services/individual_performance_model.py`

### 2. Strides in All Training Phases

**Problem**: Strides were only in base phase. High-volume athletes (75+ mpw) need neuromuscular maintenance throughout the cycle to prevent "dead legs."

**Solution**: Added `easy_strides` workout type to build, peak, and taper phases:

| Phase | Days with Strides | Rationale |
|-------|-------------------|-----------|
| Base  | Thursday          | Neuromuscular development |
| Build | Tuesday           | Maintain speed while adding threshold |
| Peak  | Tuesday           | Stay sharp, prevent staleness |
| Taper | Tuesday, Friday   | Preserve turnover as volume drops |

**Stride Prescription**:
```
6 × 20s accelerating to ~90% effort
Full recovery (60-90s walk) between each
NOT sprinting - smooth, relaxed, quick turnover
```

**Files Modified**: `apps/api/services/model_driven_plan_generator.py`

### 3. Terminology Clarity (Threshold vs Tempo)

**Problem**: Plan labeled workouts as "Tempo" but prescribed threshold intervals (with recovery). This is technically incorrect and confusing.

**Definitions**:
- **Threshold Intervals**: Repeated efforts at lactate threshold with recovery (e.g., 3×10min with 2min jog)
- **Tempo Run**: Continuous sustained effort at slightly below threshold (e.g., 25min straight)
- **Cruise Intervals**: Similar to threshold but with shorter recovery

**Solution**: Renamed "Threshold Workout" to "Threshold Intervals" with explicit structure:

```python
name="Threshold Intervals",
description=(
    "Warm up 2mi easy. Main set: 3×10min at T-pace "
    "with 2min easy jog recovery. Cool down 1mi easy. "
    "Comfortably hard - you could speak in short phrases."
)
```

**Files Modified**: `apps/api/services/model_driven_plan_generator.py`

### 4. Rationale Field for Transparency

**Problem**: Workouts lacked explanation of WHY they're prescribed. Users couldn't understand the logic behind prescription.

**Solution**: Added `rationale` field to `DayPlan` dataclass:

```python
@dataclass
class DayPlan:
    # ... existing fields ...
    rationale: Optional[str] = None  # Why this workout on this day
```

Example rationale for threshold intervals:
```
"Threshold intervals build lactate clearance capacity. 
Breaking into segments makes the effort sustainable while achieving same adaptation."
```

Example rationale for peak long run:
```
"This is your final race simulation. The longest MP portion of the cycle confirms 
you can hold goal pace for extended distance. This builds both physical and 
psychological confidence for race day."
```

**Files Modified**: `apps/api/services/model_driven_plan_generator.py`

---

## Phase 2 Roadmap (Proposed)

**Full details in**: `docs/adr/ADR-034-training-plan-variation.md`

### Problem Statement

Plans exhibit algorithmic monotony - workouts repeat with similar structures week over week. This:
1. Limits physiological adaptation (body accommodates to repeated stimulus)
2. Increases injury risk (repetitive stress patterns)
3. Reduces psychological engagement (training becomes boring)

### Proposed Solution: Workout Variation Engine

#### Component 1: Template Library

Create structured templates for each workout type with multiple variants:

```python
THRESHOLD_VARIANTS = [
    {"id": "cruise_3x10", "structure": "3×10min @ T, 2min jog"},
    {"id": "tempo_continuous", "structure": "20min continuous @ T"},
    {"id": "cruise_2x15", "structure": "2×15min @ T, 3min jog"},
    {"id": "threshold_hills", "structure": "4×3min uphill @ T-effort"},
]
```

#### Component 2: Long Run Progression

Long runs should vary in both distance AND structure:

```
Week 1: 14mi easy throughout
Week 2: 16mi with pickups (4×1min surge to MP)
Week 3: 18mi progressive (start 60s slow, finish at MP)
Week 4: 15mi cutback, easy
Week 5: 18mi with 6mi @ MP finish
Week 6: 20mi with MP sandwich (easy-4MP-easy-4MP-easy)
```

#### Component 3: Easy Run Distribution

Vary easy run distances instead of uniform distribution:

```
Current:  [8, 8, 8, 8]  (32mi over 4 days)
Proposed: [5, 7, 9, 11] (32mi over 4 days, natural variation)
```

### Implementation Phases

| Phase | Scope | Feature Flag |
|-------|-------|--------------|
| 2a | Template Library | `plan.variation_templates` |
| 2b | Long Run Progression | `plan.long_run_variation` |
| 2c | Easy Run Distribution | `plan.easy_variation` |
| 2d | Full Integration | `plan.variation_engine` |

---

## User Feedback Analysis

### Original Feedback

1. **Zero strides or hill work/sprints** despite 75 mpw volume
   - ✅ Fixed in Phase 1: Strides now in all phases

2. **Tempo and Threshold conflated** - prescribing threshold but calling it tempo
   - ✅ Fixed in Phase 1: Renamed to "Threshold Intervals" with clear structure

3. **Too long taper** (3 weeks despite τ1=25d suggesting 2 weeks)
   - ✅ Fixed in Phase 1: τ1-aware taper calculation

4. **Little variation in distances/types** throughout program
   - 📋 Documented in Phase 2 (ADR-034)

### User Context (from Grok conversation)

User is:
- High-volume athlete (75 mpw capable)
- Fast adapter (τ1 ≈ 25 days)
- Marathon-focused training
- Prefers data-driven, evidence-based explanations
- Willing to trust algorithm but needs to understand rationale

---

## Technical Reference

### File Locations

```
apps/api/services/
├── individual_performance_model.py   # τ1, τ2 calibration, taper calculation
├── optimal_load_calculator.py        # Week-by-week TSS trajectory
├── model_driven_plan_generator.py    # Workout prescription
├── race_predictor.py                 # Performance predictions
├── vdot_calculator.py                # Pace calculations
└── training_load.py                  # CTL/ATL/TSB calculations

docs/adr/
├── ADR-022-individual-performance-model.md
├── ADR-025-model-driven-plan-endpoint.md
└── ADR-034-training-plan-variation.md   # NEW - Phase 2 roadmap
```

### Key Functions

```python
# Get athlete's individual model parameters
model = get_or_calibrate_model(athlete_id, db)
# Returns: BanisterModel with tau1, tau2, confidence

# Calculate optimal taper duration (Phase 1 enhanced)
taper_days = model.calculate_optimal_taper_days()
# Returns: int (7-21 days based on tau1 and tau2)

# Get taper explanation
rationale = model.get_taper_rationale()
# Returns: str explaining why this taper duration

# Generate full training plan
plan = generate_model_driven_plan(
    athlete_id=athlete_id,
    race_date=race_date,
    race_distance="marathon",
    db=db,
    goal_time_seconds=10800,  # 3:00:00
    tune_up_races=[...]
)
# Returns: ModelDrivenPlan with weeks, predictions, personalization
```

### Week Structures by Phase

| Phase | Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|-------|-----|-----|-----|-----|-----|-----|-----|
| Base  | Rest | Easy | Easy | Easy+Strides | Easy | Med-Long | Long |
| Build | Rest | Easy+Strides | Easy | Threshold | Easy | Med-Long | Long+MP |
| Peak  | Rest | Easy+Strides | Easy | Race Pace | Easy | Med-Long | Long+MP |
| Taper | Rest | Easy+Strides | Sharpening | Easy | Easy+Strides | Rest | Reduced Long |
| Race  | Rest | Shakeout | Strides | Easy | Rest | Shakeout | **RACE** |

---

## Testing Requirements

### Unit Tests Required

```python
# test_taper_calculation.py
def test_fast_adapter_gets_shorter_taper():
    """τ1=25d should yield ~12 day taper, not 21."""
    model = BanisterModel(tau1=25, tau2=7, ...)
    assert model.calculate_optimal_taper_days() <= 14

def test_slow_adapter_gets_longer_taper():
    """τ1=55d should yield 14-21 day taper."""
    model = BanisterModel(tau1=55, tau2=7, ...)
    assert model.calculate_optimal_taper_days() >= 14

def test_taper_rationale_mentions_tau1():
    """Rationale should explain τ1-based reasoning."""
    model = BanisterModel(tau1=25, tau2=7, ...)
    rationale = model.get_taper_rationale()
    assert "25" in rationale or "fast" in rationale.lower()
```

```python
# test_strides_in_phases.py
def test_build_phase_includes_strides():
    """Build phase should have easy_strides on Tuesday."""
    structure = generator._get_build_week_structure()
    assert any(s["type"] == "easy_strides" for s in structure)

def test_peak_phase_includes_strides():
    """Peak phase should have easy_strides."""
    structure = generator._get_peak_week_structure()
    assert any(s["type"] == "easy_strides" for s in structure)
```

```python
# test_day_plan_rationale.py
def test_threshold_workout_has_rationale():
    """Threshold workouts should explain the reasoning."""
    day = generator._create_day_plan(
        workout_type="quality",
        phase=TrainingPhase.BUILD,
        ...
    )
    assert day.rationale is not None
    assert len(day.rationale) > 20
```

### Integration Tests Required

```python
# test_plan_generation_integration.py
def test_generated_plan_has_strides_throughout():
    """Full 16-week plan should have strides in multiple phases."""
    plan = generate_model_driven_plan(...)
    strides_count = sum(
        1 for w in plan.weeks for d in w.days 
        if "strides" in d.name.lower()
    )
    assert strides_count >= 10  # At least 10 stride sessions

def test_fast_adapter_plan_has_short_taper():
    """Fast adapter (τ1=25) should have 2-week taper, not 3."""
    plan = generate_model_driven_plan(...)
    taper_weeks = sum(1 for w in plan.weeks if w.phase == "taper")
    assert taper_weeks <= 2
```

---

## Appendix: Grok Conversation Summary

The user engaged with Grok AI to analyze their training plan. Key points:

1. **τ1=25d interpretation**: Grok correctly identified this as indicating "fast fitness response" but the plan wasn't using this for taper.

2. **3-week taper concern**: Standard 3-week taper is designed for average responders (τ1≈42d). Fast adapters risk losing fitness with extended taper.

3. **Tempo/threshold distinction**: Grok confirmed that true "tempo" is continuous sub-threshold effort, while plan was prescribing threshold intervals.

4. **Stride importance**: Grok emphasized strides prevent "neural staleness" at high volumes and should be present throughout.

---

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2026-01-15 | Phase 1 implementation: τ1-aware taper, strides, terminology, rationale | AI Agent |
| 2026-01-15 | Created ADR-034 for Phase 2 variation | AI Agent |
| 2026-01-15 | This documentation created | AI Agent |
