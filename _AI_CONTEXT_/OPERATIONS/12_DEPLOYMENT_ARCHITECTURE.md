# Deployment Architecture

**Status:** Planning (Pre-Production)  
**Domain:** strideiq.run  
**Decision:** Vercel (frontend) + Railway (backend)

---

## Environment Strategy

We will maintain **two environments**:

| Environment | Purpose | URL | Deploys |
|-------------|---------|-----|---------|
| **Staging** | Testing, bug fixes, new features | staging.strideiq.run | Every push to `develop` branch |
| **Production** | Live users | strideiq.run | Manual promotion from staging |

### Workflow

```
Local Development
       ↓
   Push to `develop` branch
       ↓
   Auto-deploy to STAGING
       ↓
   Test on staging.strideiq.run
       ↓
   When ready: Merge `develop` → `main`
       ↓
   Auto-deploy to PRODUCTION
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      strideiq.run                        │
│                    (Vercel - Frontend)                   │
│                                                          │
│    Next.js App                                           │
│    - React UI                                            │
│    - Static assets                                       │
│    - Edge functions for auth                             │
└────────────────────────┬────────────────────────────────┘
                         │ API calls
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   api.strideiq.run                       │
│                   (Railway - Backend)                    │
│                                                          │
│    FastAPI Application                                   │
│    - REST API                                            │
│    - Background workers (Celery)                         │
│    - Strava webhooks                                     │
└────────────────────────┬────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
   ┌───────────┐  ┌───────────┐  ┌───────────┐
   │ PostgreSQL │  │   Redis   │  │   Sentry  │
   │ (Railway)  │  │ (Railway) │  │  (Cloud)  │
   └───────────┘  └───────────┘  └───────────┘
```

---

## Why Vercel + Railway

| Component | Platform | Reason |
|-----------|----------|--------|
| **Frontend** | Vercel | Built for Next.js, automatic deployments, edge network, zero config |
| **Backend** | Railway | Docker support, PostgreSQL/Redis included, simple scaling |
| **Database** | Railway PostgreSQL | Co-located with backend, automated backups |
| **Cache/Queue** | Railway Redis | Same as above |
| **Error Tracking** | Sentry | Already integrated, free tier sufficient |
| **Uptime Monitoring** | UptimeRobot | Free, simple, reliable |

---

## Pre-Production Checklist

Before deploying to production, we need:

### Code Readiness
- [ ] All critical bugs fixed
- [ ] Core user flows tested end-to-end
- [ ] Error handling covers edge cases
- [ ] No console.log/print statements in production code

### Security
- [x] Rate limiting implemented
- [x] Security headers configured
- [x] JWT authentication working
- [x] Passwords properly hashed
- [ ] Environment variables documented
- [ ] Secrets management plan

### Reliability
- [x] Health check endpoints
- [x] Sentry integration (needs DSN)
- [x] Backup scripts ready
- [ ] Database migrations tested

### Integration
- [ ] Strava OAuth configured for production domain
- [ ] Email sending configured (password reset, etc.)
- [ ] Domain DNS configured

---

## Environment Variables

These need to be set in Railway and Vercel:

### Backend (Railway)

```bash
# Database (Railway provides these automatically)
DATABASE_URL=postgresql://...

# Redis (Railway provides)
REDIS_URL=redis://...

# Application
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<generate-random-64-char-string>
TOKEN_ENCRYPTION_KEY=<generate-random-32-char-string>

# Strava API (from strava.com/settings/api)
STRAVA_CLIENT_ID=<your-client-id>
STRAVA_CLIENT_SECRET=<your-client-secret>
STRAVA_REDIRECT_URI=https://strideiq.run/auth/strava/callback
STRAVA_WEBHOOK_VERIFY_TOKEN=<generate-random-string>

# Error Tracking (from sentry.io)
SENTRY_DSN=https://xxx@xxx.ingest.sentry.io/xxx

# Email (optional - for password reset)
EMAIL_ENABLED=true
SMTP_SERVER=smtp.your-provider.com
SMTP_PORT=587
SMTP_USERNAME=...
SMTP_PASSWORD=...
```

### Frontend (Vercel)

```bash
NEXT_PUBLIC_API_URL=https://api.strideiq.run
NEXT_PUBLIC_STRAVA_CLIENT_ID=<your-client-id>
```

---

## Deployment Steps (When Ready)

### Phase 1: Staging Environment

1. **Create Railway project**
   - Sign up at railway.app
   - Create new project
   - Add PostgreSQL service
   - Add Redis service
   - Deploy API from GitHub

2. **Create Vercel project**
   - Sign up at vercel.com
   - Import GitHub repo
   - Set root directory to `apps/web`
   - Add environment variables

3. **Configure DNS**
   - Add staging.strideiq.run → Vercel
   - Add api-staging.strideiq.run → Railway

4. **Test everything on staging**

### Phase 2: Production Environment

1. Duplicate Railway/Vercel setup for production
2. Configure strideiq.run → Vercel
3. Configure api.strideiq.run → Railway
4. Enable automatic backups
5. Configure uptime monitoring

---

## Cost Estimate

| Service | Tier | Monthly Cost |
|---------|------|--------------|
| Railway | Starter | ~$5-20 (scales with usage) |
| Vercel | Pro | $20 |
| Sentry | Free | $0 |
| UptimeRobot | Free | $0 |
| Domain (strideiq.run) | Annual | ~$15/year |
| **Total** | | **~$25-40/month** |

At 20,000 athletes, expect ~$100-200/month.

---

## What We Focus On Now

**Before deployment, we should:**

1. Continue fixing bugs and improving features locally
2. Run automated tests frequently
3. Document any remaining work
4. When ready, I'll walk you through Railway + Vercel setup step-by-step with screenshots

**You tell me when you're ready to deploy. Until then, we build.**

---

**Last Updated:** 2026-01-11
