# Query Engine System Documentation

## Overview

The Query Engine is a comprehensive data mining system for StrideIQ that enables:

1. **Admin Query Engine** - Full-power data mining for admins/owners
2. **Athlete Insights** - Guided queries for athletes on their own data
3. **Tier-Based Access** - Premium features for top-tier subscribers

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend                                │
├──────────────────────┬──────────────────────────────────────┤
│   /admin (Query Tab) │   /insights (Athlete)                │
│   - Template queries │   - Guided templates                 │
│   - Custom queries   │   - Visual results                   │
│   - Results table    │   - Charts & insights                │
└──────────┬───────────┴─────────────────┬────────────────────┘
           │                             │
           ▼                             ▼
┌──────────────────────┐     ┌───────────────────────────────┐
│ /v1/admin/query/*    │     │ /v1/athlete/insights/*        │
│ (Admin only)         │     │ (All authenticated athletes)  │
└──────────┬───────────┘     └────────────┬──────────────────┘
           │                              │
           ▼                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    QueryEngine Service                       │
│  - QuerySpec: Full query specification                       │
│  - QueryFilter: Flexible filter conditions                   │
│  - QueryResult: Standardized result format                   │
│  - Access control: SELF_ONLY / TOP_TIER / ADMIN_ONLY        │
└─────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│                    PostgreSQL Database                       │
│  Activities, Nutrition, BodyComposition, Correlations, etc.  │
└─────────────────────────────────────────────────────────────┘
```

---

## Access Control

### Tier-Based Access

Defined in `core/auth.py`:

```python
TOP_TIERS = ("premium", "pro", "elite", "guided")

def require_query_access(current_user):
    # Admins always have access
    if current_user.role in ("admin", "owner"):
        return current_user
    # Check subscription tier
    if current_user.subscription_tier in TOP_TIERS:
        return current_user
    raise HTTPException(403, "Query access requires premium subscription")
```

### Query Scopes

| Scope | Description | Who Can Use |
|-------|-------------|-------------|
| `SELF_ONLY` | Own data only | All authenticated users |
| `TOP_TIER` | Own data + advanced features | Premium/Pro/Elite subscribers |
| `ADMIN_ONLY` | Cross-athlete aggregates | Admin/Owner roles |

---

## Backend API

### Admin Query Endpoints

**Base path:** `/v1/admin/query`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/templates` | GET | List available query templates |
| `/entities` | GET | List queryable entities with fields |
| `/execute` | POST | Execute a template query |
| `/custom` | POST | Execute a custom query with DSL |

#### Example: Execute Template

```bash
POST /v1/admin/query/execute?template=efficiency_by_workout_type&days=180
```

#### Example: Custom Query

```bash
POST /v1/admin/query/custom?entity=activity&group_by=workout_type&aggregations=efficiency:avg,distance_m:sum&days=90
```

### Athlete Insights Endpoints

**Base path:** `/v1/athlete/insights`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/templates` | GET | List available insight templates |
| `/execute/{template_id}` | POST | Execute an insight |

#### Available Templates

| Template ID | Name | Premium? | Description |
|------------|------|----------|-------------|
| `efficiency_trend` | Efficiency Trend | No | Track efficiency over time |
| `workout_distribution` | Workout Distribution | No | Training breakdown by type |
| `best_performances` | Best Performances | No | Top runs by efficiency |
| `weather_impact` | Weather Impact | Yes | Temperature vs performance |
| `weekly_volume` | Weekly Volume | No | Training volume trends |
| `heart_rate_zones` | Heart Rate Analysis | Yes | Time at different HR levels |
| `personal_records` | Personal Records | No | PRs by distance |
| `consistency_score` | Consistency Score | Yes | Training consistency rating |

---

## Query Engine Service

### Location

`apps/api/services/query_engine.py`

### Core Classes

#### QuerySpec

Full specification for a query:

```python
@dataclass
class QuerySpec:
    entity: str                    # activity, nutrition, body_composition, etc.
    filters: List[QueryFilter]     # Filter conditions
    days: Optional[int]            # Time range
    group_by: Optional[List[str]]  # Group by fields
    aggregations: Optional[Dict]   # Aggregation operations
    fields: Optional[List[str]]    # Specific fields to return
    sort_by: Optional[str]         # Sort field
    limit: int = 100               # Pagination
    athlete_id: Optional[UUID]     # Single athlete filter
    anonymize: bool = True         # Anonymize for cross-athlete
```

#### QueryFilter

Flexible filter conditions:

```python
@dataclass
class QueryFilter:
    field: str
    operator: str  # eq, ne, gt, gte, lt, lte, in, not_in, like, between, is_null
    value: Any
```

#### Aggregation Types

```python
class AggregationType(str, Enum):
    NONE = "none"
    AVG = "avg"
    SUM = "sum"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    STDDEV = "stddev"
```

#### Queryable Entities

| Entity | Date Field | Description |
|--------|------------|-------------|
| `activity` | `start_time` | Running activities |
| `nutrition` | `date` | Nutrition entries |
| `body_composition` | `measured_at` | Weight, BMI, body fat |
| `work_pattern` | `date` | Work/life patterns |
| `sleep` | `date` | Sleep/recovery data |
| `correlation` | `created_at` | Correlation results |
| `feedback` | `created_at` | Activity feedback |

---

## Frontend Components

### Admin Dashboard Query Tab

**Location:** `apps/web/app/admin/page.tsx`

Features:
- Template query selector
- Parameter inputs (days, athlete_id, etc.)
- Custom query builder
- Results table with pagination
- Raw JSON view

### Athlete Insights Page

**Location:** `apps/web/app/insights/page.tsx`

Features:
- Categorized template cards
- Premium badge for restricted templates
- Parameter controls
- Rich visualizations:
  - Line charts for trends
  - Pie charts for distributions
  - Bar charts for comparisons
  - Metric cards for KPIs

### Navigation

Added to authenticated navigation:
- 💡 **Insights** → `/insights`

---

## Visualization Components

### Charts Used

All charts use **Recharts** library:

```tsx
import { LineChart, BarChart, PieChart, ... } from 'recharts';
```

### Compare Results Charts

Added overlay charts for 10-run comparison:

| Chart | Description |
|-------|-------------|
| Pace Per Split | Line chart overlaying pace across activities |
| Heart Rate Per Split | Line chart overlaying HR |
| Efficiency Comparison | Bar chart comparing efficiency scores |

**Location:** `apps/web/app/compare/results/page.tsx`

---

## Testing

### Syntax Verification

All Python files pass `py_compile`:
- `services/query_engine.py` ✓
- `routers/admin.py` ✓
- `routers/athlete_insights.py` ✓
- `core/auth.py` ✓

All TypeScript files pass type checking (no new errors introduced).

### Manual Testing

To test the system:

1. **Start servers:**
   ```bash
   docker-compose up -d
   ```

2. **Test Admin Query Engine:**
   - Login as admin
   - Go to `/admin` → "🔍 Query Engine" tab
   - Select a template, set parameters, click "Execute Query"

3. **Test Athlete Insights:**
   - Login as any user
   - Go to `/insights`
   - Select an insight template
   - Click "Run Insight"

4. **Test Compare Charts:**
   - Go to `/activities`
   - Click "📊 Compare"
   - Select 2+ activities
   - View overlay charts on results page

---

## Files Created/Modified

### New Files

| File | Lines | Description |
|------|-------|-------------|
| `apps/api/services/query_engine.py` | ~400 | Query engine service |
| `apps/api/routers/athlete_insights.py` | ~500 | Athlete insights API |
| `apps/web/lib/api/services/insights.ts` | ~60 | Insights API service |
| `apps/web/lib/api/services/query-engine.ts` | ~80 | Query engine API service |
| `apps/web/lib/hooks/queries/insights.ts` | ~35 | React Query hooks |
| `apps/web/lib/hooks/queries/query-engine.ts` | ~50 | React Query hooks |
| `apps/web/app/insights/page.tsx` | ~400 | Insights page |

### Modified Files

| File | Changes |
|------|---------|
| `apps/api/core/auth.py` | Added `require_query_access`, `require_tier` |
| `apps/api/routers/admin.py` | Added query endpoints (~150 lines) |
| `apps/api/main.py` | Registered `athlete_insights` router |
| `apps/api/services/activity_comparison.py` | Added splits to comparison |
| `apps/web/app/admin/page.tsx` | Added Query Engine tab (~200 lines) |
| `apps/web/app/compare/results/page.tsx` | Added overlay charts (~200 lines) |
| `apps/web/app/components/Navigation.tsx` | Added Insights link |
| `apps/web/lib/api/services/compare.ts` | Added `ChartSplitData` type |

---

## Security Considerations

1. **Access Control:** All endpoints enforce role/tier checks
2. **Data Isolation:** Athletes can only query their own data
3. **Anonymization:** Cross-athlete queries anonymize sensitive fields
4. **Rate Limiting:** Query endpoints inherit API rate limits
5. **Audit Logging:** Query execution is logged

---

## Future Enhancements

1. **Query History** - Save and replay queries
2. **Scheduled Queries** - Run queries on schedule, email results
3. **Export** - Export query results to CSV/JSON
4. **NLP Queries** - Natural language query interface
5. **Query Sharing** - Share query templates between admins
6. **Correlation Explorer** - Interactive correlation discovery UI

---

## Related Documentation

- `_AI_CONTEXT_/SESSION_SUMMARY_2026_01_09_RECOVERY.md` - Session summary
- `_AI_CONTEXT_/OPERATIONS/02_CODE_STANDARDS.md` - Coding standards
- `_AI_CONTEXT_/00_MANIFESTO.md` - Project principles

---

*Documentation generated: January 9, 2026*
