# Agent Handoff: 2026-01-31 Garmin & COROS API Preparation

**READ `_AI_CONTEXT_/00_SESSION_RULES.md` FIRST BEFORE ANY ACTION.**

---

## Quick Status

| Item | Status |
|------|--------|
| **Branch** | `phase8-s2-hardening` |
| **Production URL** | https://strideiq.run |
| **Strava API** | ✅ APPROVED and working |
| **Garmin API** | ⏳ Application submitted Jan 30, waiting (~Feb 3) |
| **COROS API** | 📋 Form responses ready, owner must submit manually |
| **Site Status** | ✅ Working - beta users can connect Strava |
| **Last Deploy** | Jan 30, 2026 (CORS fix + password reset) |

---

## Owner Profile

**Name:** Michael Shaffer  
**Technical Level:** Non-technical business person  
**Environment:** Windows 10, PowerShell, Cursor IDE  
**Production:** DigitalOcean droplet (ssh root@strideiq.run)

**Communication rules:**
- Provide exact copy/paste commands
- Wait for "commit approved" before committing
- Show diffs before committing
- One step at a time
- No jargon without explanation

---

## What the Previous Session Accomplished

### 1. Garmin API Application - SUBMITTED
**File:** `docs/GARMIN_API_APPLICATION.md`

- Application submitted January 30, 2026
- Expected response: ~February 3, 2026 (2 business days)
- Program: Garmin Connect Developer Program (Activity API)
- Pre-requisites verified complete:
  - Privacy Policy at https://strideiq.run/privacy (includes Garmin data handling)
  - Terms of Service at https://strideiq.run/terms (includes Garmin references)
  - Support page at https://strideiq.run/support
  - Technical architecture ready (provider abstraction via ADR-057)

**Status:** WAITING FOR GARMIN RESPONSE - no action needed until they reply.

### 2. COROS API Application - READY FOR OWNER TO SUBMIT
**File:** `docs/COROS_APPLICATION_FORM_RESPONSES.md`

All form responses are drafted and ready. The owner must manually submit.

**Application URL:** https://docs.google.com/forms/d/e/1FAIpQLSe2i_nIRV62yCeld8J9UR41I_vC34Z2_S82CodxurHHjFEo9Q/viewform

**Owner actions to submit:**
1. Open the application URL above
2. Copy/paste responses from `docs/COROS_APPLICATION_FORM_RESPONSES.md`
3. Check "Activity/Workout Data Sync" checkbox
4. Submit the form
5. Email logo images to api@coros.com:
   - Subject: "StrideIQ - API Images"
   - Attach: Logo 144×144 PNG and Logo 102×102 PNG
   - Source file for resizing: `assets/stride_logo.png`
   - Resize tool: https://www.iloveimg.com/resize-image

### 3. Password Reset - DEPLOYED AND WORKING
**Previous Handoff:** `docs/AGENT_HANDOFF_2026-01-30_PASSWORD_RESET.md`

- Admin password reset button works in /admin
- Self-service forgot password flow implemented
- Larry (beta user) successfully logged in
- CORS issue fixed on production

---

## Current Pending Tasks

### Immediate (Owner Actions)
1. [ ] Wait for Garmin API response (~Feb 3)
2. [ ] Submit COROS application manually (form is ready)
3. [ ] Email COROS logo images after form submission

### Technical (Post-Approval)
When Garmin or COROS approves:
1. [ ] Garmin: Implement OAuth flow (mirror Strava pattern in `apps/api/routers/strava.py`)
2. [ ] Garmin: Add activity sync worker (mirror `apps/api/tasks/strava_tasks.py`)
3. [ ] COROS: Implement OAuth flow
4. [ ] COROS: Implement webhook endpoint at `/v1/webhooks/coros`

### Still Needed (Not Started)
1. [ ] Strava webhooks for deauthorization notifications
2. [ ] Email service configuration for self-service password reset

---

## Uncommitted Changes

There are modified files that may need review:

```
Modified (unstaged):
- apps/api/services/ai_coach.py
- apps/web/app/privacy/page.tsx
- apps/web/app/terms/page.tsx
- apps/web/app/training-load/page.tsx
- apps/web/lib/api/services/admin.ts
- apps/web/lib/hooks/queries/admin.ts
- apps/web/lib/hooks/queries/strava.ts
- docs/COACH_ROBUSTNESS_PLAN.md
- docs/PHASED_WORK_PLAN.md

Untracked:
- docs/COROS_API_APPLICATION.md
- docs/LLM_MODEL_RESEARCH.md
- docs/STRAVA_API_STATUS.md
```

Check with owner before committing any of these.

---

## Key Documentation to Read

| Document | Purpose |
|----------|---------|
| `_AI_CONTEXT_/00_SESSION_RULES.md` | **READ FIRST** - mandatory rules |
| `_AI_CONTEXT_/00_MANIFESTO.md` | Project philosophy, AI protocol, language rules |
| `_AI_CONTEXT_/OPERATIONS/DEPLOYMENT_WORKFLOW.md` | How to deploy changes |
| `docs/GARMIN_API_APPLICATION.md` | Garmin application details |
| `docs/COROS_APPLICATION_FORM_RESPONSES.md` | COROS form responses |
| `docs/PHASED_WORK_PLAN.md` | Current roadmap |

---

## Deployment Process (Quick Reference)

**Standard flow:**
1. Make changes locally
2. `git add <files>`
3. `git diff --staged` (show to owner)
4. **STOP - wait for "commit approved"**
5. `git commit -m "type(scope): description"`
6. `git push origin phase8-s2-hardening`
7. SSH to droplet and deploy:
   ```
   ssh root@strideiq.run
   cd /opt/strideiq/repo && git pull origin phase8-s2-hardening && docker compose -f docker-compose.prod.yml up -d --build
   ```
8. Wait 3-8 minutes for build
9. Verify feature works

**Never use scp. Never use heredocs in PowerShell. Always wait for approval.**

---

## Known Issues

### Cursor Co-Author Injection
Cursor automatically injects `Co-authored-by: Cursor <cursoragent@cursor.com>` into commits. This is unauthorized and a formal complaint has been filed. Do not waste tokens trying to fix it - the owner is pursuing legal action.

### Session Burnout
Previous sessions have experienced agent loops (stuck summarizing context) that burned tokens. If you feel stuck, create a handoff document and let the owner start a new session.

---

## Tech Stack Reference

| Component | Technology |
|-----------|------------|
| Backend | FastAPI (Python) |
| Frontend | Next.js (TypeScript) |
| Database | PostgreSQL |
| Cache/Broker | Redis |
| Background Tasks | Celery |
| Reverse Proxy | Caddy |
| Hosting | DigitalOcean Droplet |

---

## Production Containers

| Container | Purpose |
|-----------|---------|
| strideiq_api | FastAPI backend |
| strideiq_web | Next.js frontend |
| strideiq_worker | Celery background tasks |
| strideiq_postgres | PostgreSQL database |
| strideiq_redis | Redis cache/broker |
| strideiq_caddy | Reverse proxy + SSL |

---

## Contact

- **Owner:** Michael Shaffer
- **Email:** michael@strideiq.run
- **Support:** support@strideiq.run
- **Production:** https://strideiq.run

---

**Created:** 2026-01-31
**Previous Handoff:** `docs/AGENT_HANDOFF_2026-01-30_PASSWORD_RESET.md`
