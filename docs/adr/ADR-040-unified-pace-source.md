# ADR-040: Unified Pace Source for Plan Generation

**Status:** Accepted  
**Date:** 2026-01-17  
**Author:** Opus 4.5 (Planner Architect)  
**Accepted:** 2026-01-18 (Judge: Michael)

---

## Context

StrideIQ has two pace calculation methods:

1. **Daniels/Gilbert Equations** (`vdot_calculator.py` → `calculate_training_paces()`): Uses the actual oxygen cost physics (public domain):
   - `VO2 = -4.6 + 0.182258*v + 0.000104*v^2`
   - Reverse-solves with quadratic formula to derive velocity from target VO2
   - Uses intensity percentages at benchmark RPI values with linear interpolation
   - Powers the **Training Pace Calculator** (public tool)

2. **Linear Approximation** (`workout_prescription.py` → `calculate_paces_from_vdot()`): Uses simplified formulas:
   - `marathon_pace = 10.5 - (rpi * 0.07)`
   - `threshold_pace = marathon_pace - 0.35`
   - Powers plan generation and workout prescriptions

For an athlete with RPI 53.3:

| Pace Type | Training Pace Calculator | Prescription (Linear) | Discrepancy |
|-----------|-------------------------|----------------------|-------------|
| Marathon | 6:57/mi | 6:46/mi | 11 sec |
| Threshold | 6:32/mi | 6:25/mi | 7 sec |
| Interval | 5:45/mi | 5:58/mi | 13 sec |

An athlete who calculates paces in the Training Pace Calculator, then generates a plan, receives workouts with **different paces**. This violates single-source-of-truth and N=1 principles.

---

## Decision

**Replace the linear approximation in `WorkoutPrescriptionGenerator` with the Daniels/Gilbert equations already implemented in `vdot_calculator.py`.**

Specifically:
1. Remove `calculate_paces_from_vdot()` from `workout_prescription.py`
2. Import `calculate_training_paces()` from `vdot_calculator.py`
3. Adapt the returned pace format to match what `WorkoutPrescriptionGenerator` expects (minutes per mile as float)
4. Verify all workout descriptions render with correct paces

**Scope:** Plan generation and workout prescription only. Other site-wide pace usages are out of scope for this ADR.

---

## Considered Alternatives Rejected

**A. Copy the Daniels equations into workout_prescription.py**  
Rejected. Duplicating physics code invites drift. Single source is `vdot_calculator.py`.

**B. Keep the linear approximation and document the difference**  
Rejected. Violates N=1 philosophy. Athlete's VDOT must produce consistent paces everywhere.

**C. Create a new shared pace module**  
Rejected for this scope. The correct implementation already exists in `vdot_calculator.py`. Refactoring to a shared module is future work.

**D. Use database lookup tables instead of calculations**  
Rejected. The Daniels equations ARE the source of truth. Lookup tables were an optimization layer, not a replacement.

---

## Consequences

**Positive:**
- Paces in generated plans match Training Pace Calculator exactly
- Single source of truth for pace physics
- Removes incorrect approximation code
- Plans align with industry-standard Daniels methodology

**Negative:**
- Existing plans in database were generated with old paces; regenerated plans will differ
- Requires regression testing of workout description strings
- Minor import dependency added to workout_prescription.py

---

## Rationale

**N=1 Philosophy alignment:**
> "Population averages are noise. The individual is the signal."

An athlete's RPI produces a specific threshold pace via physics. That pace must be the same in the Training Pace Calculator, in their plan, and on their calendar. Two different formulas producing different results means the system doesn't trust its own math.

**Architecture alignment:**
- `vdot_calculator.py` already has the validated Daniels/Gilbert implementation
- `WorkoutPrescriptionGenerator` already consumes a pace dictionary
- Change is a source swap, not a structural change

**Workflow alignment:**
- Touches `workout_prescription.py` (core plan generation file) → requires ADR
- Affects pace output for all generated plans
- Single file primary change, import from existing module

---

## Implementation Notes

**Source of truth:**
- `apps/api/services/vdot_calculator.py` → `calculate_training_paces(vdot)`

**File to modify:**
- `apps/api/services/workout_prescription.py`

**Key change:**
- Replace `calculate_paces_from_vdot()` (lines 29-69) with import from `vdot_calculator.py`
- Adapt return format: `calculate_training_paces()` returns `{pace: {mi: "M:SS", km: "M:SS"}}` 
- `WorkoutPrescriptionGenerator` expects `{pace: float}` (minutes per mile)
- Add conversion function to parse "M:SS" → float

**Testing focus:**
- Compare generated workout paces against Training Pace Calculator for same RPI
- Verify all pace format strings render correctly in workout descriptions

**Note on internal naming:**
Internal file names (`vdot_calculator.py`, `vdot_enhanced.py`) use legacy terminology. User-facing terminology is **RPI** (Running Performance Index). The underlying physics (Daniels/Gilbert oxygen cost equations) are public domain.
