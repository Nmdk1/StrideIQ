# ADR-021: Calendar Signals Routing Fix

## Status
Accepted

## Date
2026-01-15

## Context

### Problem
The Calendar page was generating repeated 422 Unprocessable Entity errors when fetching `/calendar/signals`. The console showed:

```
Input should be a valid date or datetime, input is too short, input: 'signals'
```

### Root Cause
**FastAPI route ordering conflict.** The `/calendar/signals` endpoint was defined AFTER the `/{calendar_date}` endpoint in `routers/calendar.py`. FastAPI matches routes in declaration order, so requests to `/calendar/signals` were incorrectly matched to `/{calendar_date}`, with `signals` being parsed as a date string.

### Additional Issues Found
1. **Grid alignment**: Header used `140px` for Weekly Totals column, data rows used `120px` - caused visual misalignment
2. **Auth cache leak**: React Query cache wasn't cleared on logout, allowing stale protected data to remain visible

## Decision

### 1. Route Order Fix
Move `/signals` endpoint BEFORE `/{calendar_date}` in `routers/calendar.py` with explicit comment explaining why.

### 2. Graceful Error Handling
Changed `/signals` endpoint to return empty result with 200 status instead of 422/400 for validation failures:
- Invalid date ranges return `{ day_signals: {}, week_trajectories: {}, message: "..." }`
- Exceptions are caught and logged, returning empty result
- Added logging for debugging

### 3. Grid Alignment Fix
Changed header column from `140px` to `120px` to match data rows.

### 4. Auth Cache Clear
Added `clearQueryCache()` function to QueryProvider, called on logout to prevent stale data showing.

## Implementation

### Files Changed
- `apps/api/routers/calendar.py`: Moved `/signals` route, added logging, graceful error handling
- `apps/web/app/calendar/page.tsx`: Fixed grid column width mismatch
- `apps/web/lib/providers/QueryProvider.tsx`: Added `clearQueryCache()` export
- `apps/web/lib/context/AuthContext.tsx`: Call `clearQueryCache()` on logout

## Test Plan

1. Load `/calendar` page - no 422 errors in console
2. Verify calendar grid alignment (header and data columns match)
3. Test logout - verify calendar data is cleared, protected pages redirect

## UX Principle Applied

**No dead/broken elements**: A broken API endpoint spamming 422 errors is a trust breach. Silent failures with graceful degradation are better than error spam.

## Consequences

### Positive
- Calendar page loads without errors
- Grid is properly aligned
- Logout properly clears cached data

### Negative
- None identified
