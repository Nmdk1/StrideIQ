# New Advisor Startup — February 28, 2026

**You are the advisor agent.** The founder (Michael Shaffer) consults you for architectural decisions, risk assessment, design review, builder oversight, and strategic direction. You do NOT build — you advise. Builders bring you evidence; you sign off or reject. The founder trusts your judgment, but he is the final decision-maker.

**Why a new advisor:** The previous advisor (me) lost trust through two failures:
1. Signed off on a PDF export builder pack without requesting visual evidence of the rendered output. Bugs were caught by the Codex advisor instead.
2. Rewrote the email deliverability builder note with assumptions instead of asking clarifying questions. The founder had to take it to Codex to fix.

Pattern: moving fast without understanding first. The operating contract explicitly forbids this. Learn from it.

---

## Read Order (mandatory, before first tool call)

1. `docs/FOUNDER_OPERATING_CONTRACT.md` — how to work (non-negotiable rules)
2. `docs/PRODUCT_MANIFESTO.md` — what StrideIQ IS
3. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` — visual/UX contracts, rejected decisions (DO NOT re-propose rejected items)
4. `docs/RUN_SHAPE_VISION.md` — visual vision for run data
5. `docs/SITE_AUDIT_2026-02-15.md` — honest assessment of current state
6. `docs/TRAINING_PLAN_REBUILD_PLAN.md` — the build plan (what to build, monetization tiers, phase gates)
7. `docs/AGENT_WORKFLOW.md` — build loop mechanics
8. This document (current state)

---

## What StrideIQ Is (30-second version)

AI running intelligence platform. Connects Strava and Garmin Connect data, runs 150+ intelligence tools per athlete, generates personalized training plans, surfaces N=1 insights (your sleep affects YOUR tempo pace, not a population average). The founder is a 57-year-old competitive runner who also coaches his 79-year-old father. Both are targeting state age-group records at the same race.

---

## Stack & Infrastructure

### Tech Stack
- **Frontend:** Next.js (App Router) — `apps/web/`
- **Backend:** FastAPI — `apps/api/`
- **Database:** PostgreSQL (TimescaleDB image) + Alembic migrations
- **Cache/Queue:** Redis + Celery worker (with Celery Beat for scheduled tasks)
- **Reverse Proxy:** Caddy (auto-TLS)
- **Deployment:** Docker Compose on a VPS
- **Domain:** `strideiq.run` (DNS at Porkbun)
- **Email:** Google Workspace for `strideiq.run`

### Production Server
- **Host:** Hostinger KVM 8 — 8 vCPU, 32 GB RAM
- **IP:** `root@187.124.67.153`
- **Repo path:** `/opt/strideiq/repo`
- **Deploy command:**
  ```bash
  cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build
  ```
- **Old DigitalOcean droplet:** `root@104.248.212.71` — still running as safety net. Founder has not yet been advised it's safe to shut down. The new Hostinger server is the primary.

### Docker Containers
| Service | Container Name | Notes |
|---------|---------------|-------|
| API | `strideiq_api` | FastAPI, 4 workers, runs migrations on start |
| Web | `strideiq_web` | Next.js production build |
| Worker | `strideiq_worker` | Celery worker + Beat scheduler (solo pool) |
| DB | `strideiq_postgres` | TimescaleDB (PG16), named volume `runningapp_postgres_data` |
| Cache | `strideiq_redis` | Redis 7 Alpine |
| Proxy | `strideiq_caddy` | Caddy 2, ports 80/443 |

### Useful Commands (on droplet via SSH)
```bash
# Logs
docker logs strideiq_api --tail=50
docker logs strideiq_web --tail=50
docker logs strideiq_worker --tail=50

# Container health
docker ps

# Generate auth token for smoke tests
docker exec strideiq_api python -c "
from core.security import create_access_token
from database import SessionLocal
from models import Athlete
db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
print(create_access_token(data={'sub': str(user.id), 'email': user.email, 'role': user.role}))
db.close()
"

# Smoke test (one-liner)
TOKEN=$(docker exec strideiq_api python -c "
from core.security import create_access_token
from database import SessionLocal
from models import Athlete
db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
print(create_access_token(data={'sub': str(user.id), 'email': user.email, 'role': user.role}))
db.close()
") && curl -s -H "Authorization: Bearer $TOKEN" https://strideiq.run/v1/home | python3 -m json.tool
```

### Git
- **Active branch:** `main` (all production work merges here directly)
- **Latest commit on main:** `ada6b9c` — email service wired to Google Workspace SMTP
- **Notable older branches (not active):**
  - `feature/garmin-oauth` — merged, Garmin OAuth flow
  - `phase8-s2-hardening` — old hardening branch
  - `stable-all-issues-fixed-2026-01-12`, `stable-diagnostic-report-2026-01-14` — archived stable snapshots

---

## Codebase Navigation

### Frontend (`apps/web/`)
| Area | Key Files |
|------|-----------|
| Pricing page | `app/components/Pricing.tsx` — 4-tier matrix with monthly/annual toggle |
| Settings | `app/settings/page.tsx` — tier-aware display, Garmin connection, upgrade paths |
| Activity detail | `app/activities/[id]/page.tsx` — Garmin attribution, splits, analysis |
| Home/dashboard | `app/home/` and `components/home/LastRunHero.tsx` |
| Plan view | `app/plans/[id]/page.tsx` — "Download PDF" button, paces blurred for free tier |
| Registration | `app/register/page.tsx` — `parseTierIntent()` carries `?tier=&period=` through signup |
| Garmin components | `components/integrations/GarminBadge.tsx`, `GarminConnectButton.tsx`, `GarminConnection.tsx` |
| Splits table | `components/activities/SplitsTable.tsx` — footer attribution |
| pSEO pages | `app/(pseo)/` — programmatic SEO pages (BQ times, goals, equivalency, demographics) |

### Backend (`apps/api/`)
| Area | Key Files |
|------|-----------|
| Auth & security | `core/security.py`, `core/auth.py`, `routers/auth.py` |
| Tier gating | `core/tier_utils.py` (`normalize_tier()`, `tier_level()`, `tier_satisfies()`), `core/pace_access.py` |
| Billing/Stripe | `routers/billing.py`, `services/stripe_service.py` |
| Plan generation | `services/plan_framework/generator.py`, `services/plan_framework/pace_engine.py` |
| PDF export | `routers/plan_export.py`, `services/plan_pdf.py`, `templates/plan_pdf.html` |
| Daily intelligence | `services/daily_intelligence.py`, `routers/daily_intelligence.py` |
| Garmin OAuth | `routers/garmin.py`, `services/garmin_oauth.py` |
| Garmin webhooks | `routers/garmin_webhooks.py`, `tasks/garmin_webhook_tasks.py` |
| Email | `services/email_service.py` (just updated to Google Workspace SMTP) |
| N=1 insights | `services/n1_insight_generator.py` (contains Athlete Trust Safety Contract) |
| Coach tools | `services/coach_tools.py` |
| Correlation engine | `services/correlation_engine.py` |
| Home endpoint | `routers/home.py` — cached briefing (Celery + Redis, p95 < 2s) |
| Config | `core/config.py` — all env-driven settings |

### Key Docs
| Document | Purpose |
|----------|---------|
| `docs/FOUNDER_OPERATING_CONTRACT.md` | How to work — read first, always |
| `docs/PRODUCT_MANIFESTO.md` | Product soul |
| `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` | UX contracts, rejected decisions |
| `docs/RUN_SHAPE_VISION.md` | Run data visualization vision |
| `docs/TRAINING_PLAN_REBUILD_PLAN.md` | Master build plan with phase gates |
| `docs/DNS_EMAIL_SECURITY.md` | SPF/DKIM/DMARC plan (reference, being implemented now) |
| `docs/GARMIN_MARC_SUBMISSION_CHECKLIST_2026-02-27.md` | Garmin production access submission checklist |
| `docs/GARMIN_MARC_EMAIL_DRAFT_2026-02-27.md` | Draft reply to Marc Lussi at Garmin |

---

## Stripe (Live)

- **Account:** `acct_1T4SGOLRj4KBJxHa` (Michael Shaffer)
- **Secret key:** `sk_live_...` in droplet `.env`
- **Webhook secret:** `whsec_d14No78S0mZ8AAYubytWQS7tlBJFihvq`
- **Price IDs (all live, on droplet):**

| Tier | Monthly | Annual |
|------|---------|--------|
| One-time ($5) | `price_1T59I4LRj4KBJxHa4dNcbzmd` | — |
| Guided ($15/mo) | `price_1T59IULRj4KBJxHawLGlSTRH` | `price_1T59IULRj4KBJxHax7vyoVhG` ($150/yr) |
| Premium ($25/mo) | `price_1T59HxLRj4KBJxHa5mKssgx1` | `price_1T59HxLRj4KBJxHaLGNjwlD3` ($250/yr) |

(Legacy Pro prices also exist: `price_1T4SUtLRj4KBJxHa4sq8e35A` monthly, `price_1T4SUuLRj4KBJxHat0sHVdrw` annual)

---

## Monetization Tier Model

| Tier | Price | Plan Paces | Adaptation | Intelligence |
|------|-------|------------|------------|--------------|
| Free | $0 | null (blurred, "$5 to unlock" CTA) | 403 | 403 |
| One-time | $5/plan | Full (per PlanPurchase record) | None (static) | None |
| Guided | $15/mo or $150/yr | Full (tier satisfies) | Full daily adaptation | Intelligence bank |
| Premium | $25/mo or $250/yr | Full (tier satisfies) | All above + coach proposals | All above + narratives, advisory, dashboard |

**Status:** v1 COMPLETE. Tier engine, Stripe integration, frontend 4-tier UI, PDF export, register intent carry-through all shipped.

---

## Active / Pending Work

### 1. Garmin Production Access — BLOCKING, deadline ~March 3

Marc Lussi at Garmin Connect Partner Services requested a verification evidence pack before granting production API access. The builder has completed brand compliance fixes (commit `2e4f661` and follow-ups through `96628ab`).

**What the founder still needs to do:**
- [ ] Capture 6 production screenshots (see `docs/GARMIN_MARC_SUBMISSION_CHECKLIST_2026-02-27.md`)
- [ ] Run the Garmin Partner Verification Tool and capture results
- [ ] Subscribe to the Garmin API Blog
- [ ] Compose the full reply to Marc Lussi (the founder wants to do this together with the advisor)
- [ ] Get the evaluation key ID from the Garmin Developer Portal

**Key context:**
- OAuth 2.0 PKCE flow is fully implemented
- PUSH webhooks (Activity, Health, Deregistration, Permission) are active — not PULL polling
- Feature flag `garmin_connect_enabled` at rollout 0%, allowlist: founder + father only
- Health API and Women's Health API access requested — waiting on Elena Kononova's response
- Garmin-initiated deregistration webhook has an active endpoint (returns 200) but its Celery task is a stub — this meets Marc's "enabled" requirement for initial verification
- Brand compliance builder note: `docs/BUILDER_NOTE_2026-02-27_GARMIN_BRAND_COMPLIANCE.md`
- Submission checklist: `docs/GARMIN_MARC_SUBMISSION_CHECKLIST_2026-02-27.md`
- Email draft: `docs/GARMIN_MARC_EMAIL_DRAFT_2026-02-27.md`

### 2. Email Deliverability — SHIPPED (Feb 28, 2026)

Password reset emails are live in production. `POST /v1/auth/forgot-password` delivers to Gmail. Production config:
- `EMAIL_ENABLED=true`
- `SMTP_SERVER=smtp.gmail.com:587`
- `SMTP_USERNAME=michael@strideiq.run`
- `FROM_EMAIL=noreply@strideiq.run`
- `FROM_NAME=StrideIQ`

Verified by Codex advisor: API logs confirm `Email sent to ... Reset your StrideIQ password`.

**DNS work still needed:** SPF, DKIM, DMARC records at Porkbun. See `docs/DNS_EMAIL_SECURITY.md` for the plan. Start DMARC at `p=none`, escalate after monitoring.

### 3. pSEO Scale-Up — Batch 2 SHIPPED, Batch 3 GATED

- **Batch 2 shipped:** 137 new pages (BQ times, goals, equivalency, demographics). Commit `0205c1e`.
- **Batch 3 (408 per-age pages): HARD GATED.** Do not start until Google Search Console shows evidence:
  - >500 impressions/week across Batch 2 pages, OR
  - At least 1 organic click-through to a conversion page, OR
  - Founder explicitly approves
- **GSC reminder:** Check around March 6 for Batch 3 gate evidence
- **Builder note:** `docs/BUILDER_NOTE_2026-02-26_PSEO_SCALE.md`

### 4. Other Active Builder Notes
- `docs/BUILDER_NOTE_2026-02-28_RUN_CONTEXT_GARMINDAY_MOAT.md` — wiring GarminDay health data into run context
- `docs/BUILDER_NOTE_2026-02-28_GARMIN_INGESTION_HEALTH_MONITOR.md` — Garmin ingestion health monitoring

### 5. Comped Users (no paying customers yet)
- `mbshaf@gmail.com` (founder)
- `wlsrangertug@gmail.com` (father)
- danny larson, brian levesque, tim irvine
- All migrated from `pro` to `premium` tier

---

## Build Priority Order (from TRAINING_PLAN_REBUILD_PLAN.md)

1. **Monetization** — v1 COMPLETE
2. **Phase 4 (50K Ultra)** — new primitives (back-to-back long runs, time-on-feet, RPE, nutrition, strength). 37 xfail contract tests waiting.
3. **Phase 3B (Contextual Workout Narratives)** — code complete, gate: narration accuracy > 90% for 4 weeks. Monitor: `GET /v1/intelligence/narration/quality`
4. **Phase 3C (N=1 Personalized Insights)** — code complete, gate: 3+ months data + significant correlations

---

## Enforced Contracts (DO NOT VIOLATE)

- **Athlete Trust Safety Contract** — efficiency interpretation rules in `n1_insight_generator.py`
- **119 xfail contract tests** — for 3B, 3C, Phase 4, and monetization. These become real tests when gates clear. Do not delete.
- **Garmin adapter source contract:** No raw Garmin field names in task layer
- **Scoped commits only:** Never `git add -A`
- **No template narratives:** Contextual or silent
- **Feature flag allowlist:** Do not modify `garmin_connect_enabled` without founder instruction
- **Stripe prices:** Do not change price IDs without founder sign-off
- **Do not re-propose** anything marked rejected in `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md`

---

## Decisions Made in Previous Advisor Sessions

| Decision | Detail |
|----------|--------|
| Paces gated behind $5 | Free plans show structure with null paces, blurred in UI |
| Hybrid gating architecture | Output-layer for plan data (paces nulled), endpoint 403 for intelligence/adaptation |
| `PlanTier` ≠ monetization tier | `standard/semi_custom/custom/model_driven` is generation quality, not monetization |
| Stripe live key on droplet | `sk_live_` from correct account, old wrong-account test keys removed |
| Quora bot rejected and deleted | Commit `838726e` removes all traces |
| pSEO scale approved | 538 new pages across 5 batches. Batch 3 gated on GSC evidence. |
| Sitemap automation | Manual sitemap at 150+ pages was brittle — automated from config objects |
| Email via Google Workspace | No third-party provider — Google Workspace SMTP is the path |
| Meta Pixel | Not relevant for current stage — founder asked, advisor recommended skipping it |

---

## Founder Communication Style

- Short messages are not dismissive. "do it" means full green light.
- He will challenge you. Engage honestly.
- He has deep domain expertise (ran in college, competes at 57, coaches his father).
- **"We are discussing only"** means STOP — no code, no files, no commits.
- He values directness and independent thinking.
- He curses when frustrated. It's not directed at you. Stay calm, stay precise.
- He has a Codex advisor running in parallel who reviews builder work and catches quality issues. Respect the Codex advisor's findings.
- **He is not technical** — he relies on advisors for technical judgment. But he has excellent product instincts and will catch slop immediately.

---

## Lessons Learned (from outgoing advisors — read all of these)

1. **The Quora bot was wasted money.** An advisor recommended it, scoped it, signed off on it. It automated almost nothing. The founder deleted it. Lesson: before recommending builder work, ask "does this actually save the founder time or generate revenue?" If the answer is marginal, push back on yourself.

2. **BQ standards from memory were wrong.** An advisor wrote 2025 BQ times into a builder note without verifying against the official BAA website. Real runners notice. Lesson: never write factual claims from training data. Verify from the source.

3. **Signing off without visual evidence costs trust.** The PDF export was signed off based on test output alone. The rendered PDF had issues caught later by Codex. Lesson: for any user-facing output (PDFs, UI, emails), require visual evidence — screenshots, rendered output — before sign-off.

4. **Making assumptions instead of asking questions costs trust.** The email builder note was rewritten based on "we already have email service with Google" without asking what the setup was, what credentials existed, or what the Codex advisor had already scoped. Lesson: when the founder tells you something, ask clarifying questions before acting. Research first, always.

5. **The pSEO pages are the real traffic play.** They work while the founder sleeps. Every page targets a specific search query with real, calculated data.

6. **The founder's trust is expensive to rebuild.** Be honest about ROI before scoping work. If you're not sure something will work, say so before building it.

---

## MCP Integrations Available

- **Stripe** — Stripe dashboard operations
- **Hugging Face** — ML model access
- **Context7** — up-to-date library documentation
- **Cursor IDE Browser** — browser automation for testing, screenshots

---

## Discord

**Server:** StrideIQ Ops
**Channel:** `#quora-opportunities` (webhook still active, can be repurposed)
**Webhook URL:** `https://discord.com/api/webhooks/1476686595464626297/vAPlDj7s4p8r9LF1jS2hSU2yHQ0qeZVu40HAlwGw9TIexQmvfiwABL05KY6_da51_D_o`

---

## Dirty Tree Warning

As of this handoff, `git status` shows uncommitted changes. The builder working on email deliverability has modified files. The new advisor should verify the tree state on arrival and coordinate with the founder on what to commit.

**Modified files (unstaged):**
- `apps/api/core/config.py`
- `apps/api/routers/auth.py`
- `apps/api/services/email_service.py`
- `apps/api/tests/test_email_service.py`
- `apps/api/tests/test_password_reset.py`
- `docs/AGENT_WORKFLOW.md`
- `docs/GARMIN_MARC_SUBMISSION_CHECKLIST_2026-02-27.md`

**Untracked docs (should be committed):**
- `docs/BUILDER_NOTE_2026-02-26_PDF_PLAN_EXPORT.md`
- `docs/BUILDER_NOTE_2026-02-26_PSEO_SCALE.md`
- `docs/BUILDER_NOTE_2026-02-28_EMAIL_DELIVERABILITY.md`
- `docs/BUILDER_NOTE_2026-02-28_GARMIN_INGESTION_HEALTH_MONITOR.md`
- `docs/BUILDER_NOTE_2026-02-28_RUN_CONTEXT_GARMINDAY_MOAT.md`
- `docs/BUILDER_NOTE_TEMPLATE.md`
- `docs/GARMIN_MARC_EMAIL_DRAFT_2026-02-27.md`
- `docs/SESSION_HANDOFF_2026-02-26_ADVISOR_NOTE.md`

---

## Immediate Priorities (Recommended)

1. **Garmin submission to Marc Lussi** — deadline ~March 3. Help the founder capture screenshots and compose the reply. This is the highest-urgency item.
2. **Email deliverability** — builder is actively working. Monitor for evidence pack, sign off when complete. Require visual evidence (actual email received in Gmail).
3. **GSC monitoring for pSEO Batch 3 gate** — check around March 6.
4. **Old DigitalOcean droplet** — assess whether it's safe to shut down. Hostinger has been primary for several days.

---

*This handoff was written by the outgoing advisor on February 28, 2026. The outgoing advisor lost trust through a pattern of moving fast without understanding first. The operating contract exists for a reason — follow it.*
