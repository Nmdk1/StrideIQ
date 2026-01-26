# Agent Handoff: 2026-01-26 Production Routing Fix

## Session Summary

**Date:** January 26, 2026  
**Duration:** Extended session (user started at 1 AM local time)  
**Status:** Production site restored and functional  
**Branch:** `phase8-s2-hardening`

## Critical Issues Resolved

### 1. API Routing Conflicts with Next.js Pages

**Problem:** API endpoints at `/home` and `/calendar` conflicted with Next.js frontend pages at the same paths. Caddy routed browser requests to the API instead of serving the frontend pages, causing:
- Home page showed raw JSON `{"detail":"Not authenticated"}` instead of UI
- Calendar page showed "Error loading calendar"

**Root Cause:** API routers used prefixes without `/v1/` versioning:
```python
# Before (broken)
router = APIRouter(prefix="/home", tags=["home"])
router = APIRouter(prefix="/calendar", tags=["Calendar"])
```

**Solution:** Moved all conflicting API endpoints to `/v1/` namespace:

| File | Before | After |
|------|--------|-------|
| `apps/api/routers/home.py` | `prefix="/home"` | `prefix="/v1/home"` |
| `apps/api/routers/calendar.py` | `prefix="/calendar"` | `prefix="/v1/calendar"` |
| `apps/web/lib/api/services/home.ts` | `/home` | `/v1/home` |
| `apps/web/lib/api/services/calendar.ts` | `/calendar/*` | `/v1/calendar/*` |
| `apps/web/components/home/SignalsBanner.tsx` | `/home/signals` | `/v1/home/signals` |
| `apps/web/app/calendar/page.tsx` | `/calendar/signals` | `/v1/calendar/signals` |

**Commits:**
- `9917279` - fix(routing): move /home API endpoint to /v1/home
- `a6b8c59` - fix(routing): update /home/signals to /v1/home/signals
- `94c9a86` - fix(routing): move /calendar API to /v1/calendar
- `aee14b8` - fix(routing): update /calendar/signals to /v1/calendar/signals

### 2. Database Restoration

**Problem:** Production database was empty after a failed migration attempt by a previous agent.

**Solution:** Restored from local backup:
1. Created binary dump locally: `pg_dump -Fc`
2. Transferred to Droplet via `scp`
3. Dropped and recreated database
4. Restored with `pg_restore`

**Data recovered:** All athlete data, activities, training plans, coach chat history.

### 3. Missing Database Columns

**Problem:** `athlete` table was missing `password_hash` and `role` columns required by the current codebase.

**Solution:** Added columns manually via `ALTER TABLE`:
```sql
ALTER TABLE athlete ADD COLUMN IF NOT EXISTS password_hash TEXT;
ALTER TABLE athlete ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'athlete';
```

### 4. Corrupted OpenAI API Key

**Problem:** The `.env` file on the Droplet had `OPENAI_API_KEY=set -euo pipefail` (corrupted value).

**Solution:** Copied correct `.env` from local machine and force-recreated the API container:
```bash
docker compose -f docker-compose.prod.yml up -d --force-recreate api
```

### 5. Caddyfile Routing

**Problem:** Initial Caddyfile didn't route `/health` to the API.

**Solution:** Updated Caddyfile to include operational endpoints:
```caddy
@api path /v1/* /v2/* /docs* /openapi.json /redoc* /health* /ping /debug
handle @api {
  reverse_proxy api:8000
}
```

## Deployment Notes

### Droplet Details
- **IP:** 104.248.212.71
- **Path:** `/opt/strideiq/repo`
- **Note:** This is NOT a git repository on the Droplet - files are deployed via `scp`

### Deployment Process
Since the Droplet doesn't have git configured, deployments require:
1. `scp` files from local to Droplet
2. SSH into Droplet
3. Rebuild containers: `docker compose -f docker-compose.prod.yml up -d --build`

### Key Commands
```bash
# SSH to Droplet
ssh root@104.248.212.71

# Rebuild specific service
cd /opt/strideiq/repo
docker compose -f docker-compose.prod.yml up -d --build api web

# Check logs
docker compose -f docker-compose.prod.yml logs --tail 50 api
```

## Known Issues (Non-blocking)

1. **Missing `athlete_calibrated_model` table** - Causes WARNING in logs but doesn't break functionality. The fitness bank service handles this gracefully.

2. **Deprecation warnings in console** - `<meta name="apple-mobile-web-app-capable">` deprecation warnings in browser console. Cosmetic only.

## Architecture Decision

**ADR: API endpoints must use `/v1/` prefix**

All API routers that could conflict with frontend pages MUST use the `/v1/` prefix. This ensures:
- Caddy routes `/v1/*` to the API container
- All other paths go to the Next.js frontend
- No ambiguity between API and page routes

Example pattern:
```python
# Correct
router = APIRouter(prefix="/v1/myfeature", tags=["MyFeature"])

# Wrong - will conflict with Next.js pages
router = APIRouter(prefix="/myfeature", tags=["MyFeature"])
```

## Files Modified This Session

### API (Backend)
- `apps/api/routers/home.py` - prefix change
- `apps/api/routers/calendar.py` - prefix change

### Web (Frontend)
- `apps/web/lib/api/services/home.ts` - API path updates
- `apps/web/lib/api/services/calendar.ts` - API path updates
- `apps/web/components/home/SignalsBanner.tsx` - API path update
- `apps/web/app/calendar/page.tsx` - API path update

### Infrastructure
- `Caddyfile` - routing rules (already correct in repo)

## Next Steps

1. **Continue testing other pages** - Analytics, Insights, Coach, Admin
2. **Set up git on Droplet** - Would simplify deployments
3. **Create `athlete_calibrated_model` table** - Run missing migration or create manually
4. **Consider CI/CD** - Automate deployments to avoid manual scp/rebuild

## Session Handoff

The production site at https://strideiq.run is now functional:
- ✅ Home page loads with data
- ✅ Calendar page loads with data
- ✅ Coach chat works (OpenAI key fixed)
- ✅ Authentication works
- ⚠️ Other pages need testing

User is transitioning to rest. Continue with page-by-page testing when they return.
