# StrideIQ Code Standards

> **Last Updated**: 2026-01-09
> **Purpose**: Ensure consistent, maintainable, world-class code

---

## Core Principles

1. **Correctness over cleverness** - Code that works beats code that's clever
2. **Explicit over implicit** - Make intentions clear
3. **Simple over complex** - The right amount of complexity is the minimum needed
4. **Test before ship** - Verify locally, verify on staging, then ship
5. **Document the why** - Code shows what, comments explain why

---

## Backend Standards (Python/FastAPI)

### Code Organization

```
apps/api/
├── core/           # Framework-level: auth, database, config
├── models.py       # SQLAlchemy models (single source of truth)
├── schemas.py      # Pydantic request/response schemas
├── routers/        # API endpoints (thin, delegate to services)
├── services/       # Business logic (testable, reusable)
├── tasks/          # Celery background tasks
├── tests/          # Unit and integration tests
└── alembic/        # Database migrations
```

### Naming Conventions

```python
# Files: snake_case
workout_classifier.py
activity_comparison.py

# Classes: PascalCase
class WorkoutClassifierService:
    pass

# Functions/methods: snake_case
def classify_activity(self, activity: Activity) -> WorkoutClassification:
    pass

# Constants: UPPER_SNAKE_CASE
MAX_RETRIES = 3
DEFAULT_PAGE_SIZE = 50

# Private methods: leading underscore
def _calculate_intensity(self, ...):
    pass
```

### API Endpoint Standards

```python
# Router file structure
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

router = APIRouter(prefix="/v1/activities", tags=["activities"])

@router.get("/{activity_id}", response_model=ActivityResponse)
def get_activity(
    activity_id: UUID,
    current_user: Athlete = Depends(get_current_user),  # Auth first
    db: Session = Depends(get_db),                      # Then dependencies
):
    """
    Get a single activity by ID.
    
    Returns the activity with full details including workout classification.
    Only returns activity if it belongs to the current user.
    """
    # Thin router - delegate to service
    activity = activity_service.get_by_id(activity_id, current_user.id, db)
    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found"
        )
    return activity
```

### Error Handling

```python
# Use specific HTTP status codes
raise HTTPException(status_code=400, detail="Invalid input")      # Bad request
raise HTTPException(status_code=401, detail="Not authenticated")  # Auth required
raise HTTPException(status_code=403, detail="Access denied")      # No permission
raise HTTPException(status_code=404, detail="Not found")          # Missing resource
raise HTTPException(status_code=409, detail="Already exists")     # Conflict
raise HTTPException(status_code=500, detail="Internal error")     # Server error

# Log errors with context
import logging
logger = logging.getLogger(__name__)

try:
    result = risky_operation()
except Exception as e:
    logger.error(f"Operation failed for athlete {athlete_id}: {e}", exc_info=True)
    raise HTTPException(status_code=500, detail="Operation failed")
```

### Database Queries

```python
# Always filter by athlete_id for user data
activities = db.query(Activity).filter(
    Activity.athlete_id == current_user.id,  # Security: user's own data only
    Activity.sport == "run"
).order_by(Activity.start_time.desc()).limit(50).all()

# Use SQL aggregation for performance
from sqlalchemy import func
summary = db.query(
    func.count(Activity.id).label('count'),
    func.sum(Activity.distance_m).label('total_distance')
).filter(Activity.athlete_id == current_user.id).first()

# Never use raw SQL unless absolutely necessary
# If you must, use text() and parameterize
from sqlalchemy import text
result = db.execute(
    text("SELECT * FROM activity WHERE athlete_id = :id"),
    {"id": str(athlete_id)}
)
```

---

## Frontend Standards (TypeScript/React/Next.js)

### Code Organization

```
apps/web/
├── app/                    # Next.js App Router pages
│   ├── (public)/          # Public pages (no auth required)
│   ├── (authenticated)/   # Protected pages
│   ├── components/        # Page-specific components
│   └── layout.tsx         # Root layout
├── components/            # Shared components
│   ├── ui/               # Generic UI (buttons, inputs)
│   └── activities/       # Domain-specific components
├── lib/
│   ├── api/              # API client and services
│   ├── context/          # React contexts
│   └── hooks/            # Custom hooks
└── public/               # Static assets
```

### Component Structure

```tsx
"use client";

/**
 * ActivityCard Component
 * 
 * Displays a summary of a single activity in a list.
 * Uses units context for distance/pace formatting.
 */

import { memo } from 'react';
import { useUnits } from '@/lib/context/UnitsContext';
import type { Activity } from '@/lib/api/types';

interface ActivityCardProps {
  activity: Activity;
  onClick?: (id: string) => void;
  className?: string;
}

export const ActivityCard = memo(function ActivityCard({
  activity,
  onClick,
  className = '',
}: ActivityCardProps) {
  const { formatDistance, formatPace } = useUnits();

  return (
    <div 
      className={`bg-gray-800 rounded-lg p-4 ${className}`}
      onClick={() => onClick?.(activity.id)}
    >
      <h3 className="font-semibold">{activity.name}</h3>
      <p className="text-gray-400">{formatDistance(activity.distance_m)}</p>
    </div>
  );
});
```

### Naming Conventions

```tsx
// Components: PascalCase
ActivityCard.tsx
WorkoutTypeSelector.tsx

// Hooks: camelCase with use prefix
useAuth.ts
useUnits.ts

// Contexts: PascalCase with Context suffix
AuthContext.tsx
UnitsContext.tsx

// Services: camelCase
activitiesService.ts
preferencesService.ts

// Types: PascalCase
interface Activity { }
type WorkoutType = 'easy_run' | 'tempo_run';
```

### Data Fetching

```tsx
// Use React Query for server state
import { useQuery, useMutation } from '@tanstack/react-query';

export function useActivities(filters: ActivityFilters) {
  return useQuery({
    queryKey: ['activities', filters],
    queryFn: () => activitiesService.list(filters),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// Mutations with optimistic updates
export function useUpdateActivity() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: UpdateActivityRequest) => 
      activitiesService.update(data.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['activities'] });
    },
  });
}
```

### Error Handling

```tsx
// Use error boundaries for unexpected errors
<ErrorBoundary fallback={<ErrorFallback />}>
  <ActivityList />
</ErrorBoundary>

// Handle expected errors gracefully
const { data, error, isLoading } = useActivities();

if (isLoading) return <LoadingSpinner />;
if (error) return <ErrorMessage error={error} />;
if (!data?.length) return <EmptyState message="No activities yet" />;

return <ActivityList activities={data} />;
```

### Styling

```tsx
// Use Tailwind CSS with consistent patterns
// Color scheme: gray-900 (bg), gray-800 (cards), orange-500 (accent)

// Base card
<div className="bg-gray-800 rounded-lg border border-gray-700 p-6">

// Interactive element
<button className="px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-lg transition-colors">

// Status indicators
<span className="text-green-400">Success</span>
<span className="text-amber-400">Warning</span>
<span className="text-red-400">Error</span>
```

---

## Git Commit Standards

### Commit Message Format

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `perf` | Performance improvement |
| `docs` | Documentation only |
| `style` | Formatting, missing semicolons, etc. |
| `test` | Adding or updating tests |
| `chore` | Maintenance tasks |

### Examples

```
feat(calendar): add activity-first calendar view

- Implements activity-first design per user feedback
- Adds toggle for showing/hiding planned workouts
- Integrates with useUnits for distance display

Closes #42
```

```
fix(auth): clear stale tokens on 401 response

The auth context was showing authenticated UI even when
tokens were expired. Now validates tokens with the server
before displaying authenticated state.
```

---

## Testing Standards

### Backend Tests

```python
# tests/test_workout_classifier.py
import pytest
from services.workout_classifier import WorkoutClassifierService, WorkoutType

class TestWorkoutClassifier:
    def test_classifies_easy_run_correctly(self, db_session, sample_activity):
        """Easy runs should be classified based on HR and pace."""
        sample_activity.avg_hr = 130
        sample_activity.duration_s = 3600  # 1 hour
        
        classifier = WorkoutClassifierService(db_session)
        result = classifier.classify_activity(sample_activity)
        
        assert result.workout_type == WorkoutType.EASY_RUN
        assert result.confidence >= 0.7

    def test_detects_intervals_from_splits(self, db_session, interval_activity):
        """Activities with high pace variance should be detected as intervals."""
        classifier = WorkoutClassifierService(db_session)
        result = classifier.classify_activity(interval_activity)
        
        assert result.detected_intervals is True
        assert result.work_segments >= 3
```

### Frontend Tests

```tsx
// __tests__/ActivityCard.test.tsx
import { render, screen } from '@testing-library/react';
import { ActivityCard } from '@/components/activities/ActivityCard';

describe('ActivityCard', () => {
  it('displays activity name and distance', () => {
    const activity = {
      id: '1',
      name: 'Morning Run',
      distance_m: 5000,
    };

    render(<ActivityCard activity={activity} />);

    expect(screen.getByText('Morning Run')).toBeInTheDocument();
    expect(screen.getByText(/5.*km/)).toBeInTheDocument();
  });
});
```

---

## Performance Guidelines

### Backend

- Use database indexes for filtered columns
- Paginate all list endpoints (max 100 items)
- Use SQL aggregation instead of loading all rows
- Cache expensive computations in Redis
- Use Celery for long-running tasks

### Frontend

- Use `React.memo()` for expensive components
- Use `useMemo()` and `useCallback()` appropriately
- Lazy load below-the-fold content
- Optimize images with Next.js Image component
- Keep bundle size minimal (analyze with `next build --analyze`)

---

## Security Guidelines

- Never log sensitive data (passwords, tokens, PII)
- Always use parameterized queries (SQLAlchemy ORM)
- Validate all user input (Pydantic schemas)
- Escape output (React handles this automatically)
- Use HTTPS everywhere
- Set appropriate CORS origins
- Rate limit authentication endpoints
- Use secure, HTTP-only cookies for sessions
- Encrypt sensitive data at rest (Fernet)

---

## Document History

| Date | Change | Author |
|------|--------|--------|
| 2026-01-09 | Initial standards | AI Assistant |

