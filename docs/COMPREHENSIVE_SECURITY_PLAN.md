# StrideIQ Comprehensive Security Plan

**Version:** 1.0  
**Date:** February 1, 2026  
**Classification:** Internal - Security Sensitive  
**Scope:** Complete security posture for company and athlete protection

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Risk Assessment](#risk-assessment)
3. [Findings by Category](#findings-by-category)
4. [Athlete Data Protection](#athlete-data-protection)
5. [Company Security](#company-security)
6. [Compliance Status](#compliance-status)
7. [Remediation Plan](#remediation-plan)
8. [Security Policies](#security-policies)
9. [Incident Response](#incident-response)
10. [Ongoing Security Program](#ongoing-security-program)

---

## Executive Summary

### Overall Security Posture: HIGH RISK

This comprehensive audit identified **67 security findings** across all layers:

| Severity | Count | Status |
|----------|-------|--------|
| **Critical** | 12 | Immediate action required |
| **High** | 10 | Fix within 1 week |
| **Medium** | 16 | Fix within 2 weeks |
| **Low** | 9 | Backlog |
| **Positive** | 20+ | Already secured |

### Top 5 Critical Issues

1. **6 API routers have NO authentication** - Anyone can access any user's health data
2. **Strava OAuth tokens stored unencrypted after refresh** - Credentials exposed
3. **GDPR deletion missing 24 database tables** - Non-compliant data erasure
4. **JWT tokens stored in localStorage** - Vulnerable to XSS theft
5. **30-day token expiration with no revocation** - Extended attack window

### What This Means

**For Athletes:**
- Health data (weight, heart rate, HRV, training) could be accessed by unauthorized parties
- Account takeover risk if tokens are stolen
- Incomplete data deletion if they request account removal

**For the Company:**
- GDPR non-compliance risk (fines up to 4% of revenue)
- Reputation damage if breach occurs
- Legal liability for health data exposure

---

## Risk Assessment

### Threat Model

| Threat Actor | Motivation | Capability | Risk Level |
|--------------|------------|------------|------------|
| Security Researchers | Bug bounty, recognition | Medium-High | **ACTIVE** (email received) |
| Malicious Users | Access other users' data | Low-Medium | **HIGH** (no auth on routes) |
| Script Kiddies | Automated scanning | Low | **MEDIUM** |
| Competitors | Data theft, sabotage | Medium | **LOW** |
| Nation State | Health data of VIPs | High | **LOW** (not a target yet) |

### Attack Vectors

| Vector | Exploitability | Impact | Current Protection |
|--------|---------------|--------|-------------------|
| IDOR via unauthenticated endpoints | **TRIVIAL** | Critical | **NONE** |
| XSS to steal localStorage tokens | Medium | Critical | React escaping only |
| OAuth token theft from database | Medium | High | Encryption (with bug) |
| Brute force login | Low | Medium | Account lockout (in-memory) |
| SQL injection | Low | Critical | Parameterized queries |
| CSRF | Low | Medium | Bearer tokens |

### Data Classification

| Data Type | Classification | Examples | Protection Required |
|-----------|---------------|----------|---------------------|
| **Credentials** | SECRET | Passwords, OAuth tokens | Encryption at rest, never log |
| **Health Data** | SENSITIVE | Heart rate, HRV, body composition | Auth required, encrypted preferred |
| **Personal Data** | PRIVATE | Email, birthdate, name | Auth required, GDPR compliant |
| **Training Data** | PRIVATE | Activities, plans, pace | Auth required |
| **Public Data** | PUBLIC | Anonymous aggregates | Consent required for sharing |

---

## Findings by Category

### A. API Security (Backend)

#### Critical Issues

| ID | Finding | File | Impact |
|----|---------|------|--------|
| A-C1 | body_composition.py - No auth | `routers/body_composition.py` | Full CRUD on any user's body data |
| A-C2 | work_pattern.py - No auth | `routers/work_pattern.py` | Full CRUD on any user's work patterns |
| A-C3 | nutrition.py - No auth | `routers/nutrition.py` | Full CRUD on any user's nutrition |
| A-C4 | feedback.py - No auth + IDOR | `routers/feedback.py` | Access any user's coaching data |
| A-C5 | Strava token unencrypted after refresh | `services/strava_service.py:439` | OAuth credentials exposed |
| A-C6 | TOKEN_ENCRYPTION_KEY auto-generates | `services/token_encryption.py:27` | Encryption breaks on restart |

#### High Issues

| ID | Finding | File |
|----|---------|------|
| A-H1 | v1.py mark-race/backfill without auth | `routers/v1.py:577-605` |
| A-H2 | Strava webhook signature optional | `routers/strava_webhook.py:64` |
| A-H3 | VDOT endpoints expose any user | `routers/knowledge.py:234` |
| A-H4 | 30-day JWT expiration | `core/security.py:32` |
| A-H5 | In-memory account lockout | `core/account_security.py:14` |

#### Medium Issues

| ID | Finding | File |
|----|---------|------|
| A-M1 | SQL LIKE pattern injection | Multiple files |
| A-M2 | Weak password policy | `routers/auth.py:136` |
| A-M3 | No token revocation | System-wide |
| A-M4 | Password reset reusable | `routers/auth.py:433` |
| A-M5 | Missing JWT claims (iat, jti) | `core/security.py:49` |
| A-M6 | File upload content-type not validated | `routers/imports.py:60` |
| A-M7 | OAuth state optional | `routers/strava.py:265` |
| A-M8 | Rate limiting gaps on auth | System-wide |

---

### B. Frontend Security

#### High Issues

| ID | Finding | File | Impact |
|----|---------|------|--------|
| B-H1 | JWT in localStorage | `lib/context/AuthContext.tsx` | XSS can steal tokens |
| B-H2 | Missing security headers | `next.config.js` | No CSP protection |

#### Medium Issues

| ID | Finding | File |
|----|---------|------|
| B-M1 | No CSRF protection | `lib/api/client.ts` |
| B-M2 | Full user profile in localStorage | `lib/context/AuthContext.tsx` |
| B-M3 | Direct localStorage access scattered | Multiple components |
| B-M4 | Client-side admin check only | `app/admin/page.tsx` |

---

### C. Infrastructure Security

#### Critical Issues

| ID | Finding | File | Impact |
|----|---------|------|--------|
| C-C1 | Containers run as root | All Dockerfiles | Container escape risk |
| C-C2 | Default DB password "postgres" | `docker-compose*.yml` | Trivial DB access |
| C-C3 | No SSL for DB connections | `core/database.py` | Traffic sniffing |
| C-C4 | (Duplicate) 30-day JWT expiry | `core/security.py` | Extended attack window |

#### High Issues

| ID | Finding | File |
|----|---------|------|
| C-H1 | Redis no authentication | `docker-compose*.yml` |
| C-H2 | Dev ports exposed (5432, 6379) | `docker-compose.yml` |

#### Medium Issues

| ID | Finding | File |
|----|---------|------|
| C-M1 | Backups not encrypted | `scripts/backup_database.py` |
| C-M2 | Missing Caddy security headers | `Caddyfile` |
| C-M3 | Debug endpoints in production | `Caddyfile` |

---

### D. Privacy & Compliance

#### Critical Issues

| ID | Finding | Impact |
|----|---------|--------|
| D-C1 | GDPR deletion missing 24 tables | Non-compliant erasure |
| D-C2 | (Duplicate) No auth on health endpoints | Health data exposed |

#### High Issues

| ID | Finding |
|----|---------|
| D-H1 | Data export is skeleton only |
| D-H2 | Consent field not in database |

#### Medium Issues

| ID | Finding |
|----|---------|
| D-M1 | Email addresses in logs |
| D-M2 | No data retention automation |
| D-M3 | Health data not encrypted at rest |
| D-M4 | Consent timestamps not tracked |

---

## Athlete Data Protection

### Current State

| Protection Layer | Status | Notes |
|-----------------|--------|-------|
| **Authentication** | BROKEN | 6 routers have no auth |
| **Authorization** | PARTIAL | Good where implemented, missing in many places |
| **Encryption in Transit** | GOOD | HTTPS enforced |
| **Encryption at Rest (Credentials)** | GOOD | Fernet encryption (with bug) |
| **Encryption at Rest (Health Data)** | MISSING | Plaintext in database |
| **Data Deletion** | BROKEN | Only deletes 35% of user data |
| **Data Export** | BROKEN | Skeleton implementation |

### What Athletes Entrust to StrideIQ

| Data Category | Examples | Current Risk |
|--------------|----------|--------------|
| **Identity** | Email, name, birthdate, sex | Medium - auth exists on main endpoints |
| **Body Metrics** | Weight, body fat, BMI | **CRITICAL - No auth** |
| **Health Vitals** | Heart rate, HRV, sleep, stress | **CRITICAL - No auth on check-ins** |
| **Performance** | VDOT, pace, race times | Medium - some endpoints exposed |
| **Training** | Activities, plans, calendar | Low - well protected |
| **Financial** | Subscription, payment via Stripe | Low - Stripe handles |
| **Third-Party Tokens** | Strava/Garmin OAuth | Medium - encryption bug |

### Required Protections

1. **Authentication on ALL endpoints containing user data**
2. **Ownership verification** - User can only access their own data
3. **Complete data deletion** - All 24+ tables on erasure request
4. **Full data export** - All user data, not skeleton
5. **Consent management** - Explicit opt-in for data sharing
6. **Audit logging** - Track all access to sensitive data

---

## Company Security

### Operational Security

| Area | Current State | Recommendation |
|------|--------------|----------------|
| **Secrets Management** | Environment variables | Good - add rotation schedule |
| **Access Control** | Owner role exists | Add admin audit logging |
| **Deployment** | Docker + Caddy | Add non-root containers |
| **Monitoring** | Sentry for errors | Add security event monitoring |
| **Backups** | Script exists | Add encryption, test restores |
| **Incident Response** | None documented | Create playbook (see below) |

### Business Continuity

| Scenario | Preparedness | Action Required |
|----------|--------------|-----------------|
| Database compromise | Low | Encrypt health data, rotate credentials |
| OAuth token leak | Medium | Encryption exists (fix bug) |
| Account takeover | Low | Short-lived tokens, revocation |
| DDoS attack | Medium | Rate limiting exists |
| Ransomware | Low | Encrypt and test backups |

### Third-Party Risk

| Service | Data Shared | Risk Level | Mitigation |
|---------|-------------|------------|------------|
| Strava | Activities, OAuth | Medium | Encrypted tokens, scoped permissions |
| Garmin | Activities, health | Medium | Encrypted credentials |
| Stripe | Payment info | Low | Stripe handles PCI compliance |
| Sentry | Error logs | Low | PII filtering configured |
| OpenAI/Anthropic | Training data for coach | Medium | No PII sent to AI |

---

## Compliance Status

### GDPR (EU General Data Protection Regulation)

| Requirement | Status | Gap |
|-------------|--------|-----|
| **Art. 13-14: Privacy Notice** | COMPLIANT | Comprehensive policy exists |
| **Art. 15: Right to Access** | NON-COMPLIANT | Export is skeleton only |
| **Art. 17: Right to Erasure** | NON-COMPLIANT | 24 tables not deleted |
| **Art. 20: Data Portability** | NON-COMPLIANT | No machine-readable export |
| **Art. 25: Privacy by Design** | PARTIAL | Good foundation, gaps in implementation |
| **Art. 32: Security of Processing** | NON-COMPLIANT | Missing auth on health data |
| **Art. 33: Breach Notification** | UNKNOWN | No incident response plan |

### Health Data Regulations

| Regulation | Applicability | Status |
|------------|---------------|--------|
| HIPAA (US) | Not applicable | StrideIQ is not a covered entity |
| GDPR Health Data | Applicable | NON-COMPLIANT (access controls) |
| UK GDPR | If UK users | Same gaps as GDPR |
| CCPA (California) | If CA users | Similar requirements to GDPR |

### Strava API Compliance

| Requirement | Status |
|-------------|--------|
| OAuth flow with consent | COMPLIANT |
| Access token encryption | COMPLIANT (with bug) |
| Disconnect functionality | COMPLIANT |
| Data attribution | COMPLIANT |

---

## Remediation Plan

### Phase 0: Emergency (Deploy within 24 hours)

These are actively exploitable and may be what the security researcher found:

| Priority | Task | Effort | Owner |
|----------|------|--------|-------|
| P0-1 | Add auth to `body_composition.py` | 1 hour | |
| P0-2 | Add auth to `work_pattern.py` | 1 hour | |
| P0-3 | Add auth to `nutrition.py` | 1 hour | |
| P0-4 | Add auth to `feedback.py` | 1 hour | |
| P0-5 | Fix Strava token encryption (line 439) | 15 min | |
| P0-6 | Fail hard on missing TOKEN_ENCRYPTION_KEY | 15 min | |

**Estimated Total: 4.5 hours**

### Phase 1: Critical (Deploy within 1 week)

| Priority | Task | Effort |
|----------|------|--------|
| P1-1 | Add auth to v1.py mark-race/backfill | 30 min |
| P1-2 | Make Strava webhook signature mandatory | 15 min |
| P1-3 | Add auth to knowledge.py VDOT endpoints | 30 min |
| P1-4 | Add 24 missing tables to GDPR deletion | 2 hours |
| P1-5 | Reduce JWT expiration to 7 days | 30 min |
| P1-6 | Move account lockout to Redis | 2 hours |
| P1-7 | Add security headers to next.config.js | 1 hour |
| P1-8 | Add non-root user to Dockerfiles | 1 hour |
| P1-9 | Remove default DB password | 30 min |
| P1-10 | Enable SSL for database connections | 1 hour |

**Estimated Total: 10 hours**

### Phase 2: High Priority (Deploy within 2 weeks)

| Priority | Task | Effort |
|----------|------|--------|
| P2-1 | Escape SQL LIKE metacharacters | 2 hours |
| P2-2 | Strengthen password policy | 1 hour |
| P2-3 | Implement token revocation (Redis) | 4 hours |
| P2-4 | Make password reset tokens single-use | 2 hours |
| P2-5 | Add iat/jti JWT claims | 1 hour |
| P2-6 | Validate file upload content-type | 1 hour |
| P2-7 | Make OAuth state required | 15 min |
| P2-8 | Add rate limiting to auth endpoints | 1 hour |
| P2-9 | Complete GDPR data export | 4 hours |
| P2-10 | Add consent_anonymized_data to model | 1 hour |
| P2-11 | Evaluate httpOnly cookie migration | 8 hours |
| P2-12 | Add Next.js middleware for auth | 2 hours |
| P2-13 | Add Redis authentication | 1 hour |
| P2-14 | Add Caddy security headers | 30 min |

**Estimated Total: 29 hours**

### Phase 3: Medium Priority (Deploy within 1 month)

| Priority | Task | Effort |
|----------|------|--------|
| P3-1 | Implement refresh token rotation | 8 hours |
| P3-2 | Hash emails in log statements | 2 hours |
| P3-3 | Implement data retention automation | 4 hours |
| P3-4 | Add consent timestamp tracking | 1 hour |
| P3-5 | Encrypt database backups | 2 hours |
| P3-6 | Remove debug print statements | 1 hour |
| P3-7 | Centralize frontend token access | 2 hours |
| P3-8 | Add password strength indicator | 1 hour |
| P3-9 | Remove debug endpoints from Caddyfile | 15 min |

**Estimated Total: 21 hours**

### Phase 4: Hardening (Ongoing)

| Task | Frequency |
|------|-----------|
| Dependency vulnerability scanning | Weekly |
| Secret rotation | Quarterly |
| Penetration testing | Annually |
| Security training | New hires + annually |
| Backup restore testing | Monthly |
| Access review | Quarterly |

---

## Security Policies

### Password Policy (Recommended)

```
Minimum length: 12 characters (upgrade from 8)
Maximum length: 128 characters
Complexity: At least 1 uppercase, 1 lowercase, 1 number
Blocklist: Top 100,000 common passwords
Reuse: Cannot reuse last 5 passwords
Rotation: Not required (NIST guidance)
```

### Token Lifecycle Policy (Recommended)

```
Access Token:
  - Expiration: 15 minutes (down from 30 days)
  - Storage: Memory only (not localStorage)
  - Revocation: On logout, password change, suspicious activity

Refresh Token:
  - Expiration: 7 days
  - Storage: httpOnly cookie
  - Rotation: New refresh token on each use
  - Revocation: Stored in Redis, checked on each use
```

### Data Retention Policy (Recommended)

```
Active Accounts:
  - All data: Retained while account active
  - Sync data: Refreshed on each sync
  - Cache: 7 days maximum

Deleted Accounts:
  - All personal data: Deleted immediately
  - Anonymized aggregates: Retained (with consent)
  - Audit logs: 2 years (legal requirement)
  - Backups containing data: Deleted within 30 days

Inactive Accounts:
  - No activity 2 years: Send reactivation email
  - No activity 3 years: Delete account (with notice)
```

### Secret Management Policy

```
Required Secrets:
  - SECRET_KEY: 32+ characters, cryptographically random
  - TOKEN_ENCRYPTION_KEY: Fernet-compatible key
  - POSTGRES_PASSWORD: 24+ characters, random
  - REDIS_PASSWORD: 24+ characters, random (add this)
  - STRAVA_CLIENT_SECRET: From Strava dashboard
  - STRIPE_SECRET_KEY: From Stripe dashboard

Rotation Schedule:
  - All application secrets: Quarterly
  - OAuth client secrets: Annually
  - API keys: On any suspected compromise

Storage:
  - Development: .env file (gitignored)
  - CI/CD: GitHub Secrets
  - Production: Environment variables via hosting platform
  - NEVER: Hardcoded in source code
```

---

## Incident Response

### Security Incident Classification

| Level | Description | Example | Response Time |
|-------|-------------|---------|---------------|
| SEV-1 | Active breach, data exfiltrated | Database dump leaked | Immediate |
| SEV-2 | Confirmed vulnerability, exploitable | Auth bypass discovered | 4 hours |
| SEV-3 | Potential vulnerability, investigation needed | Security researcher email | 24 hours |
| SEV-4 | Minor issue, no user impact | Dependency CVE (unexploitable) | 1 week |

### Incident Response Playbook

#### Step 1: Detection
- Monitor Sentry for unusual errors
- Monitor logs for failed auth attempts
- Respond to security researcher reports
- Check GitHub security alerts

#### Step 2: Containment (SEV-1/SEV-2)
1. Rotate affected secrets immediately
2. Revoke all active tokens (if auth compromised)
3. Block suspicious IPs at Caddy level
4. If database compromised: Take offline, restore from backup

#### Step 3: Investigation
1. Identify attack vector
2. Determine scope of access
3. Identify affected users
4. Preserve logs for forensics

#### Step 4: Remediation
1. Fix the vulnerability
2. Deploy fix to production
3. Verify fix effective
4. Monitor for continued attempts

#### Step 5: Notification (if required)
- GDPR: 72 hours to notify supervisory authority
- Users: "Without undue delay" if high risk
- Prepare communication:
  - What happened
  - What data affected
  - What we're doing
  - What users should do

#### Step 6: Post-Incident
1. Document incident fully
2. Conduct post-mortem
3. Identify preventive measures
4. Update security program

### Contact List

| Role | Responsibility | Escalation |
|------|----------------|------------|
| Developer (You) | Initial response, fix deployment | Immediate |
| Legal counsel | GDPR notification, liability | If breach confirmed |
| Hosting provider | Infrastructure issues | As needed |

---

## Ongoing Security Program

### Weekly

- [ ] Review Sentry errors for security anomalies
- [ ] Check GitHub Dependabot alerts
- [ ] Monitor failed login attempts

### Monthly

- [ ] Run `pip-audit` on dependencies
- [ ] Run `npm audit` on frontend
- [ ] Review access logs for anomalies
- [ ] Test backup restoration

### Quarterly

- [ ] Rotate application secrets
- [ ] Review user access permissions
- [ ] Update this security document
- [ ] Review third-party integrations

### Annually

- [ ] External penetration test
- [ ] Full security audit
- [ ] Update privacy policy
- [ ] Review compliance requirements

---

## Response to Security Researcher

Based on this audit, when the researcher sends their proof-of-concept, compare against these findings:

**Most likely findings:**
1. IDOR in body_composition, nutrition, work_pattern, or feedback endpoints
2. Missing authentication on specific endpoints
3. Information disclosure via VDOT endpoints

**Recommended response template:**

```
Hi Khurram,

Thank you for the proof-of-concept. We've reviewed your findings.

[If matches our known issues:]
This is a valid security finding. We've already identified this issue 
in our internal security review and are deploying a fix this week.

[If new issue:]
This is a valid security finding that we were not aware of. 
We appreciate your responsible disclosure.

While we don't have a formal bug bounty program, we'd like to:
- Credit you in our security acknowledgments (if desired)
- [Offer appropriate recognition based on severity]

We'll notify you when the fix is deployed.

Best regards,
[Name]
```

---

## Appendix A: Files Requiring Immediate Changes

```
CRITICAL - Add authentication:
  apps/api/routers/body_composition.py
  apps/api/routers/work_pattern.py
  apps/api/routers/nutrition.py
  apps/api/routers/feedback.py
  apps/api/routers/v1.py (mark-race, backfill endpoints)
  apps/api/routers/knowledge.py (VDOT endpoints)

CRITICAL - Fix encryption:
  apps/api/services/strava_service.py (line 439)
  apps/api/services/token_encryption.py (fail on missing key)

CRITICAL - GDPR compliance:
  apps/api/routers/gdpr.py (add 24 missing tables to deletion)

HIGH - Infrastructure:
  apps/api/Dockerfile (add non-root user)
  apps/web/Dockerfile (add non-root user)
  apps/worker/Dockerfile (add non-root user)
  docker-compose.prod.yml (remove default passwords)
  apps/api/core/database.py (add SSL)
  Caddyfile (add security headers)

HIGH - Frontend:
  apps/web/next.config.js (add security headers)
  apps/web/lib/context/AuthContext.tsx (review token storage)
```

---

## Appendix B: Security Checklist for New Features

Before deploying any new feature:

- [ ] All endpoints require authentication (unless explicitly public)
- [ ] Ownership verified for all resource access
- [ ] Input validated and sanitized
- [ ] SQL queries parameterized
- [ ] No secrets in code or logs
- [ ] Error messages don't leak internal details
- [ ] Rate limiting applied to expensive operations
- [ ] GDPR data export updated if new user data collected
- [ ] GDPR deletion updated if new user data stored
- [ ] Privacy policy updated if new data types collected

---

**Document Owner:** Development Team  
**Next Review:** March 1, 2026  
**Classification:** Internal - Security Sensitive
