# URGENT: CI Pipeline Failures - Handoff Document

**Created:** 2026-02-01
**Status:** CRITICAL - All CI jobs failing
**Previous Agent:** Failed to fix after multiple attempts

---

## CURRENT STATE

The CI pipeline at https://github.com/Nmdk1/StrideIQ/actions is failing on ALL jobs:
1. Backend Smoke (Golden Paths)
2. Backend Tests  
3. Frontend Tests
4. Security Scan

## RECENT COMMITS (ALL ATTEMPTED FIXES - ALL FAILED)

```
148f9f3 fix: comprehensive CI and test mock fixes
1f11d2d fix: construct JWT canary at runtime to avoid GitHub masking
281562d fix: use individual POSTGRES_* env vars in CI (not DATABASE_URL)
e22ae80 fix: CI security scan regex + frontend test mocks
3141978 fix: update model tiering tests to use MODEL_DEFAULT constant
4d4f87b fix: update to google-genai SDK (replaces deprecated google-generativeai)
316223a feat: migrate AI coach from GPT-4o-mini to Gemini 2.5 Flash
```

The root cause is commit `316223a` (Gemini migration) and `4d4f87b` (SDK update). Everything after has been failed fix attempts.

---

## KNOWN ISSUES

### 1. Security Scan - Self-Test Failure

**Error:**
```
Secret scan self-test FAILED to match canary: 'Authorization: ***'
```

**Location:** `.github/workflows/ci.yml` lines 283-369

**Problem:** GitHub Actions masks strings that look like bearer tokens. The JWT canary string is being masked before the Python code runs.

**Attempted fixes:**
- Constructed canary at runtime with string concatenation
- Fixed regex escaping (double backslash → single backslash)

**What's NOT been tried:**
- Base64 encoding the canary and decoding at runtime
- Using environment variables
- Moving the self-test to a separate script file

### 2. Frontend Tests - Multiple Failures

**Failing tests:**
- `admin-access-guard.test.tsx`
- `admin-ops-visibility.test.tsx`
- `admin-user-detail-actions.test.tsx`
- `subscriber-value-deep-dive.test.tsx`
- `landing-cta-register.test.tsx`

**Known issues:**
- Admin page imports ~30 hooks from `@/lib/hooks/queries/admin`
- Tests mock only ~20 of them
- Missing mocks cause "X is not a function" errors

**Missing mocks (as of last check):**
- Check `apps/web/app/admin/page.tsx` line 20 for ALL imported hooks
- Compare against each test file's mock list

**Other issues:**
- `InsightActionLink` component uses `useRouter` from `next/navigation` - some tests don't mock this
- `scrollIntoView` not implemented in JSDOM - Coach tests fail

### 3. Backend Smoke Tests - Database Connection

**Error:**
```
could not translate host name "postgres" to address: Temporary failure in name resolution
```

**Problem:** Code builds DB URL from `settings.POSTGRES_HOST` (default: "postgres" for Docker). CI needs localhost.

**Attempted fix:** Added individual POSTGRES_* env vars to CI workflow.

**Location to verify:** `.github/workflows/ci.yml` lines 64-84 (backend-smoke job)

### 4. Backend Tests - Similar DB Issue

Same as above - verify env vars are set in the backend-test job (lines 133-141).

---

## FILES TO CHECK

### CI Workflow
- `.github/workflows/ci.yml` - The entire workflow definition

### Database Config
- `apps/api/core/config.py` - Settings class with POSTGRES_HOST default
- `apps/api/core/database.py` - Builds URL from settings, ignores DATABASE_URL env var

### Frontend Tests (check ALL mocks match page imports)
- `apps/web/app/admin/page.tsx` - Line 20 has ALL hook imports
- `apps/web/__tests__/admin-access-guard.test.tsx`
- `apps/web/__tests__/admin-ops-visibility.test.tsx`
- `apps/web/__tests__/admin-user-detail-actions.test.tsx`
- `apps/web/__tests__/subscriber-value-deep-dive.test.tsx`

### Backend Tests
- `apps/api/tests/conftest.py` - Runs Alembic migrations on session start
- `apps/api/tests/test_phase9_backend_smoke_golden_paths.py`
- `apps/api/tests/test_coach_model_tiering.py` - Uses MODEL_DEFAULT constant

---

## RECOMMENDED APPROACH

1. **Get actual CI logs** - Don't guess. Read the full error output from GitHub Actions.

2. **Fix Security Scan first** - Simplest isolated issue:
   - Option A: Base64 encode the JWT canary, decode at runtime
   - Option B: Remove the JWT canary self-test entirely (less safe but works)
   - Option C: Put test in separate Python file, not inline YAML

3. **Fix Frontend Tests systematically:**
   - Export ALL hooks from admin.ts
   - Create a shared mock file that mocks ALL of them
   - Import shared mock in all admin tests

4. **Fix Backend Tests:**
   - Verify POSTGRES_HOST=localhost is being read
   - Check if there's a .env file being loaded that overrides it
   - Consider making database.py respect DATABASE_URL env var directly

5. **Consider reverting** to before commit `316223a` if fixes take too long.

---

## COMMANDS TO RUN

```bash
# Check current CI status
# Go to: https://github.com/Nmdk1/StrideIQ/actions

# View recent commits
git log --oneline -10

# Revert to before Gemini migration if needed
git revert 316223a 4d4f87b

# Run frontend tests locally (from apps/web)
npm test

# Run backend tests locally (from apps/api, needs DB)
pytest -v tests/test_phase9_backend_smoke_golden_paths.py
```

---

## CRITICAL: DO NOT

- Make changes without reading actual error logs first
- Assume regex patterns are correct without testing them
- Add partial mock fixes - check ALL imports and mock ALL of them
- Push fixes without local verification when possible

---

## CONTACT

The user is frustrated with multiple failed fix attempts. Be thorough and systematic. Test locally before pushing when possible.
