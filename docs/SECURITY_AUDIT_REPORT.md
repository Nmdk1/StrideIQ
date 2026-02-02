# StrideIQ Security Audit Report

**Date:** February 1, 2026  
**Scope:** Full-stack security review (API, authentication, authorization, integrations)

---

## Executive Summary

This comprehensive security audit identified **6 Critical**, **5 High**, **8 Medium**, and **6 Low** severity issues. The most severe issues involve **missing authentication on multiple endpoints** that would allow any unauthenticated user to access, modify, or delete any user's data.

### Risk Score: HIGH

The application has good security infrastructure (JWT auth, token encryption, rate limiting, security headers) but several routers were implemented without authentication, creating critical IDOR vulnerabilities.

---

## Critical Findings (Fix Immediately)

### C1. Body Composition Router - All Endpoints Unauthenticated

**Severity:** CRITICAL  
**File:** `apps/api/routers/body_composition.py`  
**Impact:** Any user (including unauthenticated) can CRUD any athlete's body composition data

**Vulnerable Endpoints:**
- `POST /body-composition` - Create for any user
- `GET /body-composition/{id}` - Read any record
- `PUT /body-composition/{id}` - Update any record  
- `DELETE /body-composition/{id}` - Delete any record
- `GET /body-composition` - List any user's records

**Fix Required:**
```python
# Add to all endpoints:
current_user: Athlete = Depends(get_current_user)

# Add ownership check:
if entry.athlete_id != current_user.id:
    raise HTTPException(status_code=403, detail="Access denied")
```

---

### C2. Work Pattern Router - All Endpoints Unauthenticated

**Severity:** CRITICAL  
**File:** `apps/api/routers/work_pattern.py`  
**Impact:** Any user can CRUD any athlete's work patterns

**Vulnerable Endpoints:**
- `POST /work-patterns`
- `GET /work-patterns` 
- `GET /work-patterns/{id}`
- `PUT /work-patterns/{id}`
- `DELETE /work-patterns/{id}`

---

### C3. Nutrition Router - Most Endpoints Unauthenticated

**Severity:** CRITICAL  
**File:** `apps/api/routers/nutrition.py`  
**Impact:** Any user can CRUD any athlete's nutrition entries

**Vulnerable Endpoints:**
- `POST /nutrition`
- `GET /nutrition`
- `GET /nutrition/{id}`
- `PUT /nutrition/{id}`
- `DELETE /nutrition/{id}`

**Note:** Only `/nutrition/parse` is properly protected.

---

### C4. Feedback Router - All Endpoints Unauthenticated with IDOR

**Severity:** CRITICAL  
**File:** `apps/api/routers/feedback.py`  
**Impact:** Any user can access any athlete's coaching feedback data via URL manipulation

**Vulnerable Endpoints:**
- `GET /athletes/{athlete_id}/observe`
- `GET /athletes/{athlete_id}/hypothesize`
- `GET /athletes/{athlete_id}/intervene`
- `GET /athletes/{athlete_id}/loop`
- `POST /athletes/{athlete_id}/validate`

---

### C5. Strava Token Stored Unencrypted After Refresh

**Severity:** CRITICAL  
**File:** `apps/api/services/strava_service.py:439`

```python
# VULNERABLE CODE:
token = refresh_access_token(athlete.strava_refresh_token)
athlete.strava_access_token = token["access_token"]  # NOT ENCRYPTED!
```

**Impact:** When tokens are refreshed in `get_activity_laps()`, the new access token is stored in plaintext, breaking the encryption model and exposing OAuth credentials.

**Fix:**
```python
from services.token_encryption import encrypt_token
athlete.strava_access_token = encrypt_token(token["access_token"])
```

---

### C6. Token Encryption Key Auto-Generates in Production

**Severity:** CRITICAL  
**File:** `apps/api/services/token_encryption.py:27-35`

**Issue:** If `TOKEN_ENCRYPTION_KEY` is not set, a temporary key is generated. On server restart, all encrypted tokens become unreadable, breaking all OAuth integrations.

**Fix:**
```python
encryption_key = os.getenv("TOKEN_ENCRYPTION_KEY")
if not encryption_key:
    if os.getenv("ENVIRONMENT") == "production":
        raise RuntimeError("TOKEN_ENCRYPTION_KEY must be set in production")
    logger.warning("Generating temporary key (NOT FOR PRODUCTION)")
    encryption_key = Fernet.generate_key().decode()
```

---

## High Severity Findings

### H1. V1 Router - Activity Modification Without Auth

**Severity:** HIGH  
**File:** `apps/api/routers/v1.py:577-605`

**Vulnerable Endpoints:**
- `POST /activities/{activity_id}/mark-race` - Mark any activity as race
- `POST /activities/{activity_id}/backfill-splits` - Trigger backfill on any activity

---

### H2. Strava Webhook Signature Verification Optional

**Severity:** HIGH  
**File:** `apps/api/routers/strava_webhook.py:64-73`

```python
if x_strava_signature:  # OPTIONAL!
    # ... verification only if header present
```

**Impact:** Attacker can forge webhook events by omitting signature header.

**Fix:** Make signature mandatory:
```python
if not x_strava_signature:
    raise HTTPException(status_code=401, detail="Missing signature")
```

---

### H3. Knowledge Router - VDOT Data Exposed

**Severity:** HIGH  
**File:** `apps/api/routers/knowledge.py:234-268`

**Issue:** VDOT endpoints accept optional `athlete_id` but have no authentication, allowing access to any athlete's calculated performance data.

---

### H4. 30-Day JWT Token Expiration

**Severity:** HIGH  
**File:** `apps/api/core/security.py:32`

```python
ACCESS_TOKEN_EXPIRE_MINUTES = 30 * 24 * 60  # 30 days
```

**Issue:** If a token is compromised, it remains valid for 30 days. Industry standard is 15-60 minutes with refresh tokens.

---

### H5. In-Memory Account Lockout (Not Production-Ready)

**Severity:** HIGH  
**File:** `apps/api/core/account_security.py:14-17`

**Issue:** Login attempt tracking is in-memory:
- Lost on server restart
- Not shared across API instances
- Attacker can bypass by round-robin requests

**Fix:** Move to Redis-backed lockout tracking.

---

## Medium Severity Findings

### M1. SQL LIKE Pattern Injection

**Files:** Multiple (`admin.py`, `knowledge.py`, `plan_generation.py`, etc.)

```python
query = query.filter(Athlete.email.ilike(f"%{search}%"))
```

**Issue:** LIKE metacharacters (`%`, `_`) not escaped. Attacker can craft wildcard searches.

**Fix:**
```python
import re
def escape_like(s: str) -> str:
    return re.sub(r'([%_\\])', r'\\\1', s)
```

---

### M2. Weak Password Policy

**File:** `apps/api/routers/auth.py:136-140`

**Issue:** Only checks minimum length (8 chars). Missing:
- Maximum length (bcrypt truncates at 72 bytes)
- Complexity requirements
- Common password blocklist

---

### M3. No Token Revocation Mechanism

**Issue:** No way to invalidate JWT tokens before expiration. If compromised, tokens remain valid for 30 days.

**Fix Options:**
1. Short-lived access tokens with refresh rotation
2. Token version tracking in database
3. Redis-backed token blocklist

---

### M4. Password Reset Tokens Reusable

**File:** `apps/api/routers/auth.py:433-493`

**Issue:** Password reset tokens can be used multiple times until expiration.

**Fix:** Track used tokens and invalidate after first use.

---

### M5. Missing JWT Claims (iat, jti)

**File:** `apps/api/core/security.py:49-59`

**Issue:** Tokens missing `iat` (issued-at) and `jti` (JWT ID) claims, hindering token age policies and revocation.

---

### M6. File Upload Content-Type Not Validated

**File:** `apps/api/routers/imports.py:60-62`

**Issue:** Only filename extension checked, not actual content. Malicious file with `.zip` extension could be uploaded.

**Fix:** Validate ZIP magic bytes (`PK\x03\x04`).

---

### M7. OAuth State Parameter Optional

**File:** `apps/api/routers/strava.py:265`

**Issue:** `state` parameter is Optional, weakening CSRF protection.

---

### M8. Rate Limiting Not Applied to Auth Endpoints

**Issue:** Registration and password reset endpoints may lack rate limiting.

---

## Low Severity Findings

### L1. Debug Print Statements in Production Code

**File:** `apps/api/services/strava_service.py` (multiple lines)

**Issue:** `print()` statements expose internal state in logs.

---

### L2. Deprecated datetime.utcnow() Usage

**Files:** Multiple

**Issue:** `datetime.utcnow()` deprecated in Python 3.12+. Use `datetime.now(timezone.utc)`.

---

### L3. Role Exposure in JWT

**File:** `apps/api/routers/auth.py:207-209`

**Issue:** User role embedded in JWT payload, visible via base64 decode. Low risk but reveals privilege levels.

---

### L4. CORS Allows All Origins in DEBUG Mode

**File:** `apps/api/main.py:104-105`

```python
if settings.DEBUG:
    allowed_origins = ["*"]
```

**Issue:** Ensure DEBUG=False in production.

---

### L5. Filename Sanitization Allows @ Character

**File:** `apps/api/routers/imports.py:36-46`

**Issue:** Unusual character that could cause edge-case issues.

---

### L6. Rate Limit Fails Open

**File:** `apps/api/core/rate_limit.py:138-141`

```python
if not redis_client:
    # If Redis unavailable, allow request
    return True, limit, int(time.time()) + window
```

**Issue:** If Redis is down, rate limiting is bypassed. Consider fail-closed for sensitive endpoints.

---

## Positive Security Findings

The following security measures are correctly implemented:

| Area | Implementation | Status |
|------|----------------|--------|
| **Password Hashing** | bcrypt with proper salt | ✅ Secure |
| **JWT Signing** | HS256 with 32+ char key validation | ✅ Secure |
| **OAuth State Signing** | HMAC-SHA256 with TTL | ✅ Secure |
| **Open Redirect Prevention** | Validates return_to starts with `/` | ✅ Secure |
| **Zip Bomb Protection** | MAX_EXTRACTED_BYTES cap | ✅ Secure |
| **Zip-Slip Protection** | Path traversal check | ✅ Secure |
| **File Size Limits** | IMPORT_MAX_FILE_BYTES (75MB) | ✅ Secure |
| **Stripe Webhook Verification** | `stripe.Webhook.construct_event()` | ✅ Secure |
| **Stripe Idempotency** | StripeEvent table prevents replays | ✅ Secure |
| **Token Encryption** | Fernet (AES-128-CBC + HMAC) | ✅ Secure |
| **Timing-Safe Comparison** | `hmac.compare_digest()` | ✅ Secure |
| **Security Headers** | CSP, HSTS, X-Frame-Options, etc. | ✅ Secure |
| **Blocked User Enforcement** | Checked at auth middleware level | ✅ Secure |
| **Admin Routes** | require_admin, require_owner decorators | ✅ Secure |
| **Impersonation Controls** | Owner-only, time-limited, audited | ✅ Secure |
| **Sentry PII Filtering** | Removes auth headers before sending | ✅ Secure |

---

## Remediation Plan

### Phase 1: Critical (Deploy within 24 hours)

| Priority | Issue | Effort | Owner |
|----------|-------|--------|-------|
| P0-1 | Add auth to body_composition.py | 1 hour | - |
| P0-2 | Add auth to work_pattern.py | 1 hour | - |
| P0-3 | Add auth to nutrition.py | 1 hour | - |
| P0-4 | Add auth to feedback.py | 1 hour | - |
| P0-5 | Fix Strava token encryption (line 439) | 15 min | - |
| P0-6 | Fail hard on missing TOKEN_ENCRYPTION_KEY | 15 min | - |

### Phase 2: High (Deploy within 1 week)

| Priority | Issue | Effort |
|----------|-------|--------|
| P1-1 | Add auth to v1.py mark-race/backfill | 30 min |
| P1-2 | Make Strava webhook signature mandatory | 15 min |
| P1-3 | Add auth to knowledge.py VDOT endpoints | 30 min |
| P1-4 | Reduce JWT expiration to 1-7 days | 30 min |
| P1-5 | Move account lockout to Redis | 2 hours |

### Phase 3: Medium (Deploy within 2 weeks)

| Priority | Issue | Effort |
|----------|-------|--------|
| P2-1 | Escape LIKE metacharacters | 2 hours |
| P2-2 | Strengthen password policy | 1 hour |
| P2-3 | Implement token revocation | 4 hours |
| P2-4 | Make reset tokens single-use | 2 hours |
| P2-5 | Add iat/jti JWT claims | 1 hour |
| P2-6 | Validate file upload content-type | 1 hour |
| P2-7 | Make OAuth state required | 15 min |
| P2-8 | Ensure rate limiting on auth endpoints | 1 hour |

### Phase 4: Low (Backlog)

| Priority | Issue | Effort |
|----------|-------|--------|
| P3-1 | Remove debug print statements | 1 hour |
| P3-2 | Update deprecated datetime.utcnow() | 1 hour |
| P3-3 | Remove role from JWT (optional) | 30 min |
| P3-4 | Verify DEBUG=False in production | Config check |
| P3-5 | Review filename @ allowlist | 15 min |
| P3-6 | Consider fail-closed rate limiting | 1 hour |

---

## Response to Security Researcher

Based on this audit, the researcher may have found any of the critical IDOR vulnerabilities in the unauthenticated routers. When they send their proof-of-concept, compare it against these findings.

**Likely vulnerabilities they found:**
1. Body composition, nutrition, or work pattern endpoints without auth
2. Feedback router IDOR via athlete_id in URL
3. V1 router activity modification without auth

**Recommended response:**
- Thank them professionally
- Request the PoC
- Don't commit to rewards until you verify the issue
- If it matches these findings, acknowledge and credit appropriately
- Implement fixes before public disclosure

---

## Appendix: Files Requiring Immediate Attention

```
apps/api/routers/body_composition.py  - Add auth to all endpoints
apps/api/routers/work_pattern.py      - Add auth to all endpoints
apps/api/routers/nutrition.py         - Add auth to all endpoints (except /parse)
apps/api/routers/feedback.py          - Add auth to all endpoints
apps/api/routers/v1.py                - Add auth to mark-race, backfill-splits
apps/api/routers/knowledge.py         - Add auth to VDOT endpoints
apps/api/routers/strava_webhook.py    - Make signature mandatory
apps/api/services/strava_service.py   - Encrypt token at line 439
apps/api/services/token_encryption.py - Fail hard on missing key
apps/api/core/security.py             - Reduce token expiration
apps/api/core/account_security.py     - Move to Redis
```

---

**Report generated by automated security audit**
