# ADR-052: API Endpoints Must Use /v1/ Prefix

## Status
Accepted

## Date
2026-01-26

## Context

StrideIQ uses a monorepo with:
- **FastAPI backend** serving API endpoints
- **Next.js frontend** serving pages
- **Caddy** as reverse proxy routing requests

A critical production outage occurred when API endpoints at `/home` and `/calendar` conflicted with Next.js pages at the same paths. Caddy's routing rules sent browser requests to the API instead of the frontend, causing pages to display raw JSON errors.

## Decision

**All API endpoints MUST use the `/v1/` prefix** (or `/v2/` for future versions).

### Router Definition Pattern
```python
# Correct - uses versioned prefix
router = APIRouter(prefix="/v1/home", tags=["home"])
router = APIRouter(prefix="/v1/calendar", tags=["Calendar"])
router = APIRouter(prefix="/v1/coach", tags=["Coach"])

# Wrong - conflicts with frontend pages
router = APIRouter(prefix="/home", tags=["home"])
router = APIRouter(prefix="/calendar", tags=["Calendar"])
```

### Frontend API Calls
```typescript
// Correct
apiClient.get('/v1/home');
apiClient.get('/v1/calendar');

// Wrong
apiClient.get('/home');
apiClient.get('/calendar');
```

### Caddyfile Routing
```caddy
@api path /v1/* /v2/* /docs* /openapi.json /redoc* /health* /ping /debug
handle @api {
  reverse_proxy api:8000
}

handle {
  reverse_proxy web:3000
}
```

## Consequences

### Positive
- Clear separation between API and frontend routes
- No ambiguity in Caddy routing
- Follows REST API versioning best practices
- Easier to deprecate and migrate API versions

### Negative
- All existing API calls need `/v1/` prefix
- Slightly longer URLs
- Must remember to add prefix when creating new routers

### Neutral
- Operational endpoints (`/health`, `/ping`, `/debug`) remain at root level for simplicity

## Compliance

When adding new API routers:
1. Always use `prefix="/v1/yourfeature"`
2. Never use a prefix that matches a Next.js page path
3. Update frontend service files to use `/v1/` prefix
4. Test both API endpoint and frontend page work independently
