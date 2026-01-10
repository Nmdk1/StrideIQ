# StrideIQ Deployment Architecture

> **Status**: Pre-deployment (Local Development)
> **Last Updated**: 2026-01-09
> **Owner**: Engineering

This document defines the production-grade deployment architecture for StrideIQ. 
All development MUST follow these practices to ensure system reliability and user trust.

---

## 1. Environment Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│                        PRODUCTION                                │
│                     strideiq.run                                 │
│          Branch: main (protected, requires PR approval)          │
│                   ↑ Merge only after staging verified            │
├─────────────────────────────────────────────────────────────────┤
│                         STAGING                                  │
│                   staging.strideiq.run                           │
│          Branch: staging (auto-deploy on merge)                  │
│                   ↑ PR from feature branches                     │
├─────────────────────────────────────────────────────────────────┤
│                    LOCAL DEVELOPMENT                             │
│                     localhost:3000                               │
│          Branch: feature/* (developer's machine)                 │
└─────────────────────────────────────────────────────────────────┘
```

### Environment Purposes

| Environment | Purpose | Data | Who Tests |
|-------------|---------|------|-----------|
| **Production** | Live users | Real user data | End users |
| **Staging** | Pre-release validation | Sanitized copy or synthetic | Founder + QA |
| **Local** | Active development | Developer's test data | Developer |

---

## 2. Git Branching Strategy

### Branch Types

| Branch | Pattern | Lifetime | Deploys To |
|--------|---------|----------|------------|
| `main` | Protected | Permanent | Production |
| `staging` | Protected | Permanent | Staging |
| `feature/*` | `feature/add-calendar` | Until merged | None (local only) |
| `hotfix/*` | `hotfix/fix-auth-crash` | Until merged | Staging → Prod |
| `release/*` | `release/v1.2.0` | Until released | Staging → Prod |

### Branch Protection Rules (GitHub)

**`main` branch:**
- ✅ Require pull request before merging
- ✅ Require 1 approval (founder)
- ✅ Require status checks to pass (CI/CD)
- ✅ Require branches to be up to date
- ✅ Do not allow bypassing the above settings
- ❌ No force pushes
- ❌ No deletions

**`staging` branch:**
- ✅ Require pull request before merging
- ✅ Require status checks to pass
- ❌ No force pushes

---

## 3. Development Workflow

### Standard Feature Development

```bash
# 1. Start from latest staging
git checkout staging
git pull origin staging

# 2. Create feature branch
git checkout -b feature/training-calendar

# 3. Develop and test locally
# ... make changes ...
# ... test on localhost:3000 ...

# 4. Commit with meaningful messages
git add .
git commit -m "feat(calendar): add activity-first view with plan overlay

- Implements activity-first calendar design
- Adds toggle for showing/hiding planned workouts
- Integrates with useUnits for distance display
- Closes #42"

# 5. Push feature branch
git push origin feature/training-calendar

# 6. Create Pull Request: feature/training-calendar → staging
# ... Review, discuss, iterate ...

# 7. Merge to staging (auto-deploys to staging.strideiq.run)
# ... Test on staging environment ...

# 8. If verified: Create PR staging → main
# ... Merge triggers production deployment ...
```

### Hotfix Workflow (Production Issues)

```bash
# 1. Branch from main (not staging)
git checkout main
git pull origin main
git checkout -b hotfix/fix-auth-crash

# 2. Fix the issue, test locally

# 3. Push and create PR to BOTH staging AND main
git push origin hotfix/fix-auth-crash

# 4. Merge to staging first, verify fix
# 5. Then merge to main (production deployment)
```

---

## 4. CI/CD Pipeline

### GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, staging]
  pull_request:
    branches: [main, staging]

jobs:
  # ==================== BACKEND ====================
  backend-lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install ruff
      - run: ruff check apps/api/

  backend-test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -r apps/api/requirements.txt
      - run: pytest apps/api/tests/

  # ==================== FRONTEND ====================
  frontend-lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: cd apps/web && npm ci
      - run: cd apps/web && npm run lint

  frontend-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - run: cd apps/web && npm ci
      - run: cd apps/web && npm run build

  # ==================== DEPLOY ====================
  deploy-staging:
    needs: [backend-lint, backend-test, frontend-lint, frontend-build]
    if: github.ref == 'refs/heads/staging'
    runs-on: ubuntu-latest
    steps:
      - run: echo "Vercel/Railway auto-deploy from staging branch"

  deploy-production:
    needs: [backend-lint, backend-test, frontend-lint, frontend-build]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - run: echo "Vercel/Railway auto-deploy from main branch"
```

### Quality Gates

Before any merge to `main`:
- [ ] All linter checks pass
- [ ] All unit tests pass
- [ ] Build succeeds
- [ ] Staging deployment verified manually
- [ ] No security vulnerabilities (npm audit, pip-audit)

---

## 5. Infrastructure Setup

### Hosting Providers

| Component | Provider | Reason |
|-----------|----------|--------|
| Frontend | **Vercel** | Native Next.js support, edge CDN, free tier |
| Backend API | **Railway** | Easy Docker deploy, auto-scaling, good DX |
| PostgreSQL | **Railway** | Managed, backups, same network as API |
| Redis | **Railway** | Managed, same network as API |
| Domain DNS | **Cloudflare** | Free, fast, DDoS protection |

### Environment Variables

**Production** (set in Vercel/Railway dashboards):
```env
# Frontend (Vercel)
NEXT_PUBLIC_API_URL=https://api.strideiq.run
NEXT_PUBLIC_BASE_URL=https://strideiq.run

# Backend (Railway)
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
SECRET_KEY=<generated-256-bit-key>
STRAVA_CLIENT_ID=<from-strava>
STRAVA_CLIENT_SECRET=<from-strava>
OPENAI_API_KEY=<from-openai>
ENCRYPTION_KEY=<fernet-key>
```

**Staging** (separate values):
```env
NEXT_PUBLIC_API_URL=https://api-staging.strideiq.run
NEXT_PUBLIC_BASE_URL=https://staging.strideiq.run
DATABASE_URL=postgresql://...(staging-db)
# ... etc
```

---

## 6. Database Management

### Migration Strategy

1. **Never modify production database directly**
2. **All schema changes via Alembic migrations**
3. **Test migrations locally → staging → production**

```bash
# Create migration
cd apps/api
alembic revision --autogenerate -m "add_workout_classification_fields"

# Test locally
alembic upgrade head

# Push to staging, verify
# Then push to production
```

### Backup Strategy

| Frequency | Type | Retention | Storage |
|-----------|------|-----------|---------|
| Hourly | WAL archiving | 24 hours | Railway |
| Daily | Full snapshot | 30 days | Railway |
| Weekly | Full export | 1 year | Cloud storage |

### Rollback Procedures

**Schema rollback:**
```bash
# Identify current revision
alembic current

# Rollback one revision
alembic downgrade -1

# Or rollback to specific revision
alembic downgrade abc123
```

**Code rollback:**
```bash
# Revert last commit on main
git revert HEAD
git push origin main
# Auto-deploys reverted code
```

---

## 7. Monitoring & Observability

### Logging

| Layer | Tool | What |
|-------|------|------|
| Frontend | Vercel Logs | Client errors, edge function logs |
| Backend | Railway Logs | Request logs, errors, warnings |
| Application | Structured JSON | All API requests, business events |

### Metrics to Track

**Health Metrics:**
- API response time (p50, p95, p99)
- Error rate by endpoint
- Database connection pool usage
- Redis memory usage
- Celery queue depth

**Business Metrics:**
- Daily active users
- Activities synced
- AI coach conversations
- Strava sync success rate

### Alerting

| Condition | Severity | Action |
|-----------|----------|--------|
| API error rate > 5% | Critical | Page founder |
| API p99 latency > 2s | Warning | Email |
| Database connections > 80% | Warning | Email |
| Celery queue > 100 | Warning | Email |

---

## 8. Security Practices

### Pre-Deployment Checklist

- [ ] All secrets in environment variables (not in code)
- [ ] HTTPS enforced everywhere
- [ ] CORS configured for production domains only
- [ ] Rate limiting enabled
- [ ] SQL injection protection (SQLAlchemy ORM)
- [ ] XSS protection (React escaping)
- [ ] CSRF protection (SameSite cookies)
- [ ] Authentication tokens expire appropriately
- [ ] Password hashing with bcrypt (cost factor 12)
- [ ] Sensitive data encrypted at rest (Fernet)
- [ ] Dependency audit clean (npm audit, pip-audit)

### Security Headers (Vercel)

```json
// vercel.json
{
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "X-XSS-Protection", "value": "1; mode=block" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
        { "key": "Permissions-Policy", "value": "camera=(), microphone=(), geolocation=()" }
      ]
    }
  ]
}
```

---

## 9. Incident Response

### Severity Levels

| Level | Definition | Response Time | Examples |
|-------|------------|---------------|----------|
| **P1** | Service down | < 15 min | API unreachable, data corruption |
| **P2** | Major feature broken | < 1 hour | Strava sync failing, auth broken |
| **P3** | Minor issue | < 24 hours | UI glitch, non-critical error |
| **P4** | Enhancement | Next sprint | Feature request, optimization |

### Incident Workflow

1. **Detect**: Monitoring alert or user report
2. **Assess**: Determine severity, impact scope
3. **Communicate**: Update status page if P1/P2
4. **Mitigate**: Rollback if needed
5. **Fix**: Develop fix in hotfix branch
6. **Deploy**: Through proper staging → prod flow
7. **Postmortem**: Document what happened, prevent recurrence

---

## 10. Cost Management

### Current Estimated Monthly Costs

| Service | Staging | Production | Total |
|---------|---------|------------|-------|
| Vercel | $0 | $0 | $0 |
| Railway (API) | $5 | $5 | $10 |
| Railway (DB) | $5 | $5 | $10 |
| Railway (Redis) | $5 | $5 | $10 |
| Domain | - | $15/yr | ~$1.25 |
| **Total** | **$15** | **$15** | **~$31/mo** |

### Scaling Triggers

| Metric | Threshold | Action |
|--------|-----------|--------|
| API CPU > 80% sustained | 1 hour | Upgrade Railway plan |
| DB connections > 90% | - | Add connection pooling (PgBouncer) |
| Users > 1000 | - | Evaluate caching strategy |
| Users > 10000 | - | Consider dedicated infrastructure |

---

## Document History

| Date | Change | Author |
|------|--------|--------|
| 2026-01-09 | Initial document | AI Assistant |

