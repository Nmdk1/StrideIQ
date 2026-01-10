# VDOT Calculator Enhancement - January 5, 2026

## Overview

Enhanced the VDOT calculator to match the full functionality of vdoto2.com, providing a comprehensive, professional-grade tool for runners.

## Requirements

The calculator needed to match vdoto2.com's three-tab interface:
1. **Race Paces Tab**: Shows paces for different distances (5K, 1Mi, 1K, 800M, 400M)
2. **Training Tab**: Comprehensive training paces with:
   - Per mile/km paces (Easy with range, Marathon, Threshold, Interval, Repetition)
   - Interval distances (1200m, 800m, 600m) for Threshold/Interval/Repetition
   - Short intervals (400m, 300m, 200m) for Interval/Repetition/Fast Reps
3. **Equivalent Tab**: Equivalent race times for all standard distances

## Implementation

### Backend (`apps/api/services/vdot_enhanced.py`)

Created a new enhanced VDOT calculator service with three main functions:

#### `calculate_race_paces(vdot, input_distance_m, input_time_seconds)`
- Calculates race paces for: 5K, 1Mi, 1K, 800M, 400M
- Uses equivalent race time calculations for accuracy
- Returns formatted paces with decimal precision (e.g., "6:26.2")

#### `calculate_training_paces_enhanced(vdot)`
- **Per mile/km paces**: All training paces in both units
  - Easy pace shown as a range (e.g., "8:16 ~ 9:06") based on Daniels' guidance
  - Marathon, Threshold, Interval, Repetition paces
- **Interval distances**: Times for 1200m, 800m, 600m at Threshold/Interval/Repetition paces
- **Short intervals**: Times for 400m, 300m, 200m at Interval/Repetition/Fast Reps paces
- Uses lookup tables from `vdot_lookup.py` for accuracy

#### `calculate_equivalent_races_enhanced(vdot)`
- Calculates equivalent race times for all standard distances:
  - Marathon, Half Marathon, 15K, 10K, 5K, 3Mi, 2Mi, 3200M, 3K, 1mi, 1600M, 1500M
- Uses equivalent race time lookup tables
- Returns formatted times and paces

#### `calculate_vdot_enhanced(distance_meters, time_seconds)`
- Main entry point that orchestrates all calculations
- Returns comprehensive data structure:
  ```python
  {
    "vdot": 50.0,
    "input": {
      "distance_m": 5000,
      "distance_name": "5K",
      "time_seconds": 1200,
      "time_formatted": "20:00",
      "pace_mi": "6:26.2"
    },
    "race_paces": [...],
    "training": {
      "per_mile_km": {...},
      "interval_distances": {...},
      "short_intervals": {...}
    },
    "equivalent": [...]
  }
  ```

### Frontend (`apps/web/app/components/tools/VDOTCalculator.tsx`)

Completely rewrote the component to match vdoto2.com's interface:

#### Features
- **Three-tab navigation**: Race Paces, Training, Equivalent
- **Tab styling**: Active tab highlighted with orange border and text
- **Race Paces Tab**: Clean table showing distance and pace
- **Training Tab**: Three sections:
  1. Per mile/km paces table
  2. Interval distances table (1200m, 800m, 600m)
  3. Short intervals table (400m, 300m, 200m)
- **Equivalent Tab**: Table showing race, time, and pace/mile
- **VDOT display**: Large, prominent VDOT score with input details
- **Info tooltip**: Subtle explanation of what VDOT means for new runners

#### Styling
- Dark mode consistent with site aesthetic
- Orange accent color for highlights
- Monospace font for pace/time values
- Responsive grid layouts
- Subtle borders and spacing

### API Integration (`apps/api/routers/public_tools.py`)

Updated `/v1/public/vdot/calculate` endpoint:
- Uses `calculate_vdot_enhanced()` for full functionality
- Falls back to `calculate_vdot_comprehensive()` if enhanced fails
- Returns comprehensive data structure for frontend

### Age-Grading Calculator Enhancement

Added subtle explanation tooltip to `WMACalculator.tsx`:
- Info icon with expandable explanation
- Explains what age-grading means in plain language
- Maintains site aesthetic with subtle gray background
- Helps new runners understand the metric

## Technical Details

### Easy Pace Range Calculation
- Based on Daniels' guidance: Easy pace can vary ±20 seconds per mile
- Formula: Faster = base - 24 seconds, Slower = base + 26 seconds
- For km: Faster = base - 15 seconds, Slower = base + 16 seconds
- Displayed as range: "8:16 ~ 9:06"

### Interval Distance Calculations
- Uses training pace (seconds per mile) from lookup tables
- Calculates time for specific distance: `time = pace_seconds * (distance_m / 1609.34)`
- Formats as MM:SS for display

### Race Pace Calculations
- Uses equivalent race time function for accuracy
- Falls back to training pace extrapolation if needed
- Distance-specific pace factors for shorter distances

## Testing

Tested with:
- 5K in 20:00 (VDOT ~50)
- Verified all three tabs populate correctly
- Confirmed pace calculations match vdoto2.com format
- Checked Easy pace range displays correctly
- Verified interval distances calculate properly

## Files Modified

1. `apps/api/services/vdot_enhanced.py` - New enhanced calculator service
2. `apps/web/app/components/tools/VDOTCalculator.tsx` - Complete rewrite with three tabs
3. `apps/web/app/components/tools/WMACalculator.tsx` - Added age-grading explanation
4. `apps/api/routers/public_tools.py` - Updated to use enhanced calculator

## Status

✅ **Complete** - Calculator now matches vdoto2.com functionality
- All three tabs working
- Training paces with ranges and intervals
- Equivalent race times
- User-friendly explanations
- Professional aesthetic maintained

## Next Steps

- Fine-tune calculations if values differ slightly from vdoto2.com (may be due to lookup table precision)
- Consider adding temperature/altitude adjustments (future enhancement)
- Monitor user feedback for usability improvements

