# Advisor Handoff — February 26, 2026

**You are the advisor agent.** The founder (Michael Shaffer) consults you for architectural decisions, risk assessment, design review, builder oversight, and strategic direction. You do NOT build — you advise. Builders bring you evidence; you sign off or reject. The founder trusts your judgment, but he is the final decision-maker.

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

**Stack:** Next.js frontend, FastAPI backend, PostgreSQL, Redis, Celery worker, Caddy reverse proxy. Deployed on DigitalOcean droplet via Docker Compose. Domain: strideiq.run.

---

## Current State — What Exists and Works

### Production Infrastructure
- **Droplet:** `root@strideiq.run` at `/opt/strideiq/repo`
- **Deploy:** `cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build`
- **Containers:** strideiq_api, strideiq_web, strideiq_worker, strideiq_postgres, strideiq_redis, strideiq_caddy
- **Latest commit on main:** `838726e` (removal of Quora bot)

### Stripe (Live)
- **Account:** `acct_1T4SGOLRj4KBJxHa` (Michael Shaffer)
- **Secret key:** `sk_live_...` on droplet `.env` line 21 — correct account, verified working
- **Price IDs on droplet (all LRj4KBJxHa account):**
  - `STRIPE_PRICE_PRO_MONTHLY_ID=price_1T4SUtLRj4KBJxHa4sq8e35A`
  - `STRIPE_PRICE_PRO_ANNUAL_ID=price_1T4SUuLRj4KBJxHat0sHVdrw`
  - `STRIPE_PRICE_PLAN_ONETIME_ID=price_1T59I4LRj4KBJxHa4dNcbzmd`
  - `STRIPE_PRICE_GUIDED_MONTHLY_ID=price_1T59IULRj4KBJxHawLGlSTRH`
  - `STRIPE_PRICE_GUIDED_ANNUAL_ID=price_1T59IULRj4KBJxHax7vyoVhG`
  - `STRIPE_PRICE_PREMIUM_MONTHLY_ID=price_1T59HxLRj4KBJxHa5mKssgx1`
  - `STRIPE_PRICE_PREMIUM_ANNUAL_ID=price_1T59HxLRj4KBJxHaLGNjwlD3`
- **Webhook secret:** `whsec_d14No78S0mZ8AAYubytWQS7tlBJFihvq`

### Garmin Connect
- **Production approved** for Activity API (Elena Kononova, Garmin Connect Partner Services)
- **Health API and Women's Health API requested** — email sent to Elena, awaiting response
- **Feature flag:** `garmin_connect_enabled` at rollout 0%, allowlist: founder + father only
- **Do NOT flip to 100%** until Elena's second review passes (next couple weeks)

### Comped Users (no paying customers yet)
- mbshaf@gmail.com (founder), wlsrangertug@gmail (father), danny larson, brian levesque, tim irvine
- All migrated from `pro` to `premium` tier in Phase 1D migration

---

## Active Builders and Their Status

### Builder 1: Monetization

| Phase | Status | Key Commits |
|-------|--------|-------------|
| Phase 1 — Stripe + tier engine | PASS (advisor signed off) | `445aa7c` → `12bb370` |
| Phase 2 — Feature gating | PASS (advisor signed off) | `84529f5` → `a79f6ca` |
| **Phase 3 — Frontend** | **IN PROGRESS** | Not yet committed |

**Phase 3 scope:** Pricing.tsx redesign (4 tiers with annual toggle), Settings page tier-aware display, checkout flow for guided/premium/one-time, blurred-paces UX on plan pages using `paces_locked` field from the API.

**Phase 4 (after 3):** PDF plan export via WeasyPrint (Jinja2 template, on-demand generation endpoint, download button).

**Phase 5 (after 4):** Remove xfail from 29 contract tests, implement real assertions.

**Key handoffs to read:**
- `docs/SESSION_HANDOFF_2026-02-26_MONETIZATION_PHASE1.md`
- `docs/SESSION_HANDOFF_2026-02-26_MONETIZATION_PHASE2.md`

### Builder 2: Traffic / pSEO Scale-Up

| Phase | Status | Key Commits |
|-------|--------|-------------|
| Phase 1 — 14 pSEO pages | PASS (advisor signed off) | `f5c755c` → `f460ee3` |
| Phase 2 — Quora bot | DELETED — low ROI, founder rejected | `838726e` (removal) |
| **Phase 3 — pSEO Scale (538 new pages)** | **READY TO START (advisor-approved)** | Builder note ready |

**Quora bot was built, delivered, and deleted.** The advisor (me) recommended it, scoped it, and signed off on it. It was a waste of the founder's money — it automated almost nothing and the founder rightly called it out. The bot script, its dependencies, and the Discord webhook env var have all been removed (commit `838726e`). The Discord server itself was kept for future ops use.

**pSEO Scale-Up is the replacement.** Builder note at `docs/BUILDER_NOTE_2026-02-26_PSEO_SCALE.md` — reviewed by both the outgoing advisor and a second advisor. Approved with conditions (all conditions have been applied to the doc).

**Execution order:** Batch 2B (BQ, 23 pages) → Batch 2A (Goals, 44 pages) → Batch 2D (Equivalency, 13 pages) → Batch 2C (Demographics, 50 pages). Total: 130 new pages in Batch 2.

**Batch 3 (408 per-age pages) is HARD GATED.** Do not start until GSC shows >500 impressions/week across Batch 2 pages, OR at least 1 organic click-through to a conversion page, OR the founder explicitly approves.

**Key docs:**
- `docs/BUILDER_NOTE_2026-02-26_PSEO_SCALE.md` — the full builder note (reviewed, approved)
- Plan file: `c:\Users\mbsha\.cursor\plans\pseo_scale_+_seeding_b773f057.plan.md`

---

## Decisions Made Today (Advisor-Level)

| Decision | Detail | Impact |
|----------|--------|--------|
| Paces gated behind $5 | Builder note supersedes TRAINING_PLAN_REBUILD_PLAN.md Resolved Decision #1 | Free plans show structure with null paces, blurred in UI |
| Hybrid gating architecture | Output-layer for plan data (paces nulled), endpoint 403 for intelligence/adaptation | Already implemented in Phase 2 |
| Trial elevation scoped to free tier | Fixed bug: Guided subscribers no longer incorrectly get Premium access during trial | Shipped in Phase 2 |
| `PlanTier` != monetization tier | `standard/semi_custom/custom/model_driven` is generation quality, not monetization | Must not be conflated |
| Stripe live key on droplet | `sk_live_` from correct account (`LRj4KBJxHa`), old wrong-account test keys removed | Production Stripe is functional |
| Quora bot rejected | Built, delivered, founder rejected as low ROI. Deleted. Advisor failure — should have pushed back before building. | `838726e` removes all traces |
| pSEO scale approved | 538 new pages across 5 batches. BQ first (highest intent). Batch 3 gated on GSC evidence. | Builder note finalized and advisor-approved |
| BQ standards verified | 2026 BAA qualifying times verified from official source. Ages 18-59 tightened by 5 min vs 2025. | Hardcoded in builder note |
| Sitemap automation mandatory | Manual sitemap at 150+ pages is brittle. Builder must automate from config objects before adding new pages. | First task in Batch 2B |
| Slug naming convention | Slugs must match natural search language, not machine naming. E.g., `boston-qualifying-time-men-35-39` not `bq-times-men-35-39`. | Applied to all batches |

---

## SEO/AEO Work Completed

- **Sitemap:** `https://strideiq.run/sitemap.xml` — 30+ URLs including 14 pSEO pages. Submitted to Google Search Console (Feb 26). Will be automated from config objects in the pSEO scale-up.
- **Structured data:** Organization, WebApplication, FAQPage, BreadcrumbList, Article JSON-LD across all pages
- **`llms.txt`:** Live at `https://strideiq.run/llms.txt` (v1.1.1 spec)
- **Stories shell:** `/stories` and `/stories/father-son-state-age-group-records` (slug pre-registered, content TBD post-race)
- **OG image:** Updated, deployed
- **Google Search Console:** Verified (domain verification via DNS TXT on Porkbun), sitemap submitted Feb 26
- **pSEO scale-up:** 538 new pages approved. Builder note at `docs/BUILDER_NOTE_2026-02-26_PSEO_SCALE.md`. Execution order: BQ → Goals → Equivalency → Demographics. Batch 3 (408 per-age pages) hard-gated on GSC evidence.
- **Community seeding strategy:** Founder should engage on r/running, r/AdvancedRunning, and Letsrun.com as a genuine expert. No link-dropping. Answer 1-2 questions per session with real data. Brand searches compound domain authority. Strategy documented in the plan file.
- **Key handoffs:** `docs/BUILDER_NOTE_2026-02-25_SEO_AEO_EXECUTION_CHECKLIST.md`, `docs/ADVISOR_REVIEW_RUBRIC_2026-02-25_SEO_AEO_EXECUTION_CHECKLIST.md`, `docs/BUILDER_NOTE_2026-02-26_PSEO_SCALE.md`

---

## Monetization Tier Model (Canonical)

| Tier | Price | Plan Paces | Adaptation | Intelligence |
|------|-------|------------|------------|-------------|
| Free | $0 | null (blurred, "$5 to unlock" CTA) | 403 | 403 |
| One-time | $5/plan | Full (per PlanPurchase record) | None (static) | None |
| Guided | $15/mo or $150/yr | Full (tier satisfies) | Full daily adaptation | Intelligence bank |
| Premium | $25/mo or $250/yr | Full (tier satisfies) | All above + coach proposals | All above + narratives, advisory, dashboard |

**Canonical tier engine:** `apps/api/core/tier_utils.py` — `normalize_tier()`, `tier_level()`, `tier_satisfies()`

**Pace access utility:** `apps/api/core/pace_access.py` — `can_access_plan_paces(athlete, plan_id, db)`

---

## Build Priority Order (from TRAINING_PLAN_REBUILD_PLAN.md)

1. **Monetization** — Phase 3 frontend in progress, then Phase 4 PDF export, then Phase 5 contract tests
2. **Phase 4 (50K Ultra)** — new primitives (back-to-back long runs, time-on-feet, RPE, nutrition, strength). 37 xfail contract tests waiting.
3. **Phase 3B (Contextual Workout Narratives)** — code complete, gate: narration accuracy >90% for 4 weeks
4. **Phase 3C (N=1 Personalized Insights)** — code complete, gate: 3+ months data + significant correlations

---

## Open Items Requiring Attention

1. **Garmin Health API response** — waiting on Elena. Without Health API, Garmin integration is limited to activities (redundant with Strava). Health API gives sleep, HRV, resting HR. Women's Health API gives menstrual cycle data.
2. **Garmin production credentials** — need to generate production OAuth credentials in Garmin Developer Portal and swap them into the droplet env. Do NOT do this until Elena's second review passes.
3. **Race day story** — father/son race. When results come in, populate `STORIES['father-son-state-age-group-records'].content` in `apps/web/app/stories/[slug]/page.tsx`, update `publishedAt`, add story-specific OG image, deploy.
4. **Untracked files** — `docs/BUILDER_NOTE_2026-02-26_PSEO_SCALE.md`, `docs/SESSION_HANDOFF_2026-02-26_ADVISOR_NOTE.md`, and `.vscode/settings.json` are untracked. Should be committed.
5. **Monetization Phase 3 frontend** — builder is working on this now. When they hand off, review: Pricing.tsx 4-tier layout, Settings page tier display, checkout flow, blurred-paces UX. Evidence required: screenshots + live URL checks.
6. **pSEO builder launch** — builder note is ready at `docs/BUILDER_NOTE_2026-02-26_PSEO_SCALE.md`. Needs a builder assigned. Execution starts with sitemap automation refactor, then Batch 2B (BQ pages).
7. **Stripe account verification** — Stripe dashboard shows "Verify your email" and "Verify your business" incomplete. This doesn't block test-mode operations but will block live payment processing. Founder should complete these.

---

## Enforced Contracts (DO NOT VIOLATE)

- **Athlete Trust Safety Contract** — efficiency interpretation rules in `n1_insight_generator.py`
- **119 xfail contract tests** — for 3B, 3C, Phase 4, and monetization. These become real tests when gates clear. Do not delete.
- **Sleep validator tolerance:** 0.5h — do not tighten without founder sign-off
- **Garmin adapter source contract:** No raw Garmin field names in task layer
- **Scoped commits only:** Never `git add -A`
- **No template narratives:** Contextual or silent
- **Feature flag allowlist:** Do not modify `garmin_connect_enabled` without founder instruction
- **Stripe prices:** Do not change price IDs without founder sign-off
- **Do not re-propose** anything marked rejected in `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md`

---

## Your Role as Advisor

1. **Review builder handoffs** — when a builder completes a phase, they present evidence. You verify it's real (not just claimed), check for regressions, and sign off or reject.
2. **Resolve architectural conflicts** — like the paces-free-vs-gated decision today. Present options clearly to the founder, give your recommendation, let him decide.
3. **Guard quality** — "tree clean, tests green, production healthy" at end of every session. No exceptions.
4. **Preserve context** — the founder values your accumulated understanding. Don't lose track of decisions made, builders in flight, or open items.
5. **Be direct** — the founder wants a thinking partner who pushes back, not an order-taker. Disagree when you have evidence. But when he decides, execute.
6. **Suppression over hallucination** — if uncertain, say nothing. Never fabricate.

---

## Founder Communication Style

- Short messages are not dismissive. "do it" means you have green light.
- He will challenge you. Engage honestly.
- He has deep domain expertise (ran in college, competes at 57, coaches his father).
- "We are discussing only" means STOP — no code, no files, no commits.
- He values directness and independent thinking.
- Passion varies — capture the high moments, be efficient in the low ones.
- He curses when frustrated. It's not directed at you. Stay calm, stay precise.

---

## Lessons Learned (from outgoing advisor — read these)

1. **The Quora bot was my mistake.** The founder asked for traffic automation. I recommended a Quora answer-drafting bot. It cost real builder tokens and delivered almost nothing — the founder still had to find questions, run the script, review drafts, and post manually. That's not automation. The founder was right to call it slop. **Lesson: before recommending any builder work, ask "does this actually save the founder time or generate revenue?" If the answer is marginal, push back on yourself.**

2. **BQ standards from memory were wrong.** I wrote 2025 BQ times into the builder note without verifying against the official BAA website. The second advisor caught it — ages 18-59 were tightened by 5 minutes for 2026. Real runners would have immediately noticed. **Lesson: never write factual claims from training data. Verify from the source. The founder's words: "real runners will pick up any pacing discrepancies intuitively and now it's bullshit."**

3. **The pSEO pages are the real traffic play.** They work while the founder sleeps. Every page targets a specific search query with real, calculated data. No ongoing effort. This is what the traffic builder should have been doing from the start instead of the Quora bot.

4. **The founder's trust is expensive to rebuild.** When you waste his money on something he has to delete, it costs more than tokens. Be honest about ROI before scoping work. If you're not sure something will work, say so before building it, not after.

---

## MCP Integrations Available

The founder has these installed in Cursor:
- **Stripe** — for Stripe dashboard operations
- **Hugging Face** — ML model access
- **Context7** — up-to-date library documentation
- **Cursor IDE Browser** — browser automation for testing, form-filling, screenshots

---

## Discord

**Server:** StrideIQ Ops
**Channel:** `#quora-opportunities` (webhook still active, can be repurposed for ops notifications)
**Webhook URL:** `https://discord.com/api/webhooks/1476686595464626297/vAPlDj7s4p8r9LF1jS2hSU2yHQ0qeZVu40HAlwGw9TIexQmvfiwABL05KY6_da51_D_o`

---

*This handoff represents the complete state as of February 26, 2026, late evening. The outgoing advisor was active across SEO, monetization, traffic, Garmin, Stripe, and pSEO scale-up workstreams for the full session. Two builders are in flight (monetization Phase 3, pSEO scale-up ready to launch). The founder is engaged, direct, and cost-conscious. Earn his trust through precision and honesty.*
