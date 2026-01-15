# ADR-007: Age-Grading Calculator Enhancement

## Status
Proposed

## Date
2026-01-13

## Context
The current Age-Grading Calculator returns minimal information:
- Performance percentage
- Equivalent open time

Competitor analysis shows best-in-class calculators (e.g., runningagegrading.com) provide significantly more value:
- Detailed summary with all calculation components
- Equivalent performances at other distances
- Close performances (times for nearby percentage levels)
- Classification interpretation

Users need this level of detail to truly understand and trust the calculation.

## Decision
Enhance the Age-Grading Calculator to provide comprehensive results:

### 1. Enhanced API Response
Add to `/v1/public/age-grade` response:
- `open_class_standard_seconds` - World record time for the distance/sex (senior athletes)
- `age_standard_seconds` - World record time for the age/sex/distance
- `age_factor` - The WMA factor applied
- `age_graded_time_seconds` - Time adjusted by age factor
- `classification` - Performance tier (World class, National class, etc.)
- `equivalent_performances` - Times for other distances at same percentage
- `close_performances` - Times needed for nearby percentages

### 2. Frontend Enhancement
New results display with:
- Summary table (matches reference site style)
- Equivalent Performances tables (Track and Road)
- Close Performances table
- Classification with visual indicator

### 3. Preserved Elements
- Existing API contract (backwards compatible - only adds fields)
- Current explanation text
- Orange accent styling
- Input validation

## Trade-offs

### Pros
- Significantly more value for users
- Builds trust through transparency
- Matches/exceeds competitor functionality
- No breaking changes to existing API

### Cons
- Larger API response payload
- More complex frontend component
- Computation cost slightly higher (multiple distance calculations)

## Technical Approach

### API Changes (Backend)
1. Enhance `calculate_age_grade()` in `public_tools.py`
2. Add helper functions for equivalent performances
3. All new fields are optional additions (backwards compatible)

### Frontend Changes
1. Expand results section with styled tables
2. Use existing shadcn/ui Card, Badge components
3. Follow slate-800 card styling from Home/Compare

### Security Considerations
- No new user input beyond existing validated fields
- No PII involved
- Public endpoint (no auth changes)

### Feature Flag
- `AGE_GRADE_V2` - Controls enhanced display
- Fallback to current minimal display if disabled

## Consequences
- Users get comprehensive age-grading analysis
- API response size increases ~3-5x
- Frontend bundle size increases slightly (~2KB)

## Implementation Plan
1. Enhance API with new response fields
2. Add unit tests for new calculations
3. Update frontend with enhanced display
4. Feature flag the new UI
5. Rebuild and verify
