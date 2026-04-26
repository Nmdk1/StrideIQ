# Personal Coach Tier — Product Specification

**Date:** April 9, 2026
**Status:** Scoped — ready to build when prioritized
**Estimated effort:** 2 builder sessions
**Priority:** Revenue unlock (Product Strategy #15)
**Dependencies:** Existing Stripe integration, existing N=1 intelligence pipeline

---

## Product Summary

A separate coaching product inside StrideIQ. Two products, one platform.

**Self-coached athletes (existing):** Full platform — briefing, AI coach
chat, Manual, Progress, Calendar, Activities, Analytics, Fingerprint.
Athlete pays their own subscription.

**Coaching platform (this spec):** Coaches pay $29.99/mo + $14.99/mo per
athlete. They get a dashboard with N=1 intelligence per athlete, an AI
research analyst, private notes, compliance tracking, plan management.
Their athletes get a stripped experience: Home (full briefing), Calendar,
Activities. No AI coach chat. The human coach replaces the AI.

---

## Strategic Rationale

### The Moat

No coaching platform has confirmed N=1 findings per athlete.
TrainingPeaks shows data. Final Surge shows data. StrideIQ tells the
coach what the data means for each specific athlete.

- "Adam's efficiency drops 22% when sleep is below 6.2h"
- "Jim races 7% faster than his best training efforts"
- "Larry's HRV cliff is 32ms — below that, next-day efficiency collapses"

This intelligence already exists in the system. This build surfaces it
to coaches.

### Competitive Positioning

| Platform | 10 athletes/mo | Intelligence | Coach AI |
|---|---|---|---|
| Final Surge | $39 | None | None |
| TrainingPeaks | $112 | PMC/TSS only | None |
| **StrideIQ** | **$180** | **N=1 findings, race character, operating manual** | **Research analyst per athlete** |

Premium pricing justified by fundamentally different capability.

### Financial Model

Cost per coached athlete: ~$5.30/month (briefing LLM, correlation
engine, Garmin ingestion, weather, coach-AI queries, infrastructure).

| Coach size | Revenue | Cost | Profit | Margin |
|---|---|---|---|---|
| 3 athletes | $70 | $21 | $49 | 70% |
| 10 athletes | $180 | $58 | $122 | 68% |
| 25 athletes | $405 | $138 | $267 | 66% |

Profitable at every scale.

---

## Architecture Decisions

### 1. Coach is a separate entity

New `Coach` table. Not an Athlete with `role='coach'`. Different auth
flow, different JWT shape (`type: "coach"` vs `role: "athlete"`),
different API surface.

A coach who also runs signs up separately as an athlete with a different
email. The accounts are fully independent.

### 2. Coached athletes see Home + Calendar + Activities only

No AI Coach chat. No Manual. No Progress. No Analytics. No Fingerprint.
The human coach provides all intelligence interpretation. The athlete
gets their plan and their data. The coach gets the intelligence layer.

The home page for coached athletes includes the **full LLM briefing**.
This is the most expensive option but gives the best athlete experience.
Cost is absorbed in the per-athlete pricing.

### 3. The AI is a research analyst, not a coach

Different endpoint (`POST /v1/coach/ai/chat`), different system prompt.
The coach-AI never prescribes training. It surfaces data, patterns,
confirmed findings, and lets the human coach decide.

Example: Coach asks "How is Adam's HRV trending?" →
"Adam's overnight HRV averaged 34ms over the last 7 days, down 18% from
his 30-day average of 41ms. His confirmed cliff is 32ms. Sleep averaged
5.4h this week, below his 6.2h threshold. The HRV decline correlates
with the sleep deficit in his data."

### 4. Self-serve Stripe billing

Coach signs up at `/for-coaches`, enters payment via Stripe Checkout.
$29.99/mo base subscription. When athletes are linked, an "Athlete
Intelligence Seat" line item is added at $14.99/mo per seat. Stripe
handles proration automatically.

Volume pricing (25+ athletes): contact founder directly.

### 5. Athletes can disconnect anytime

Athlete has a "Disconnect from Coach" option in Settings. No coach
permission required. StrideIQ does not market the full platform to
coached athletes or attempt to convert them while they're coached.
After disconnect, athlete can subscribe independently or their account
goes to a basic read-only state.

### 6. Ethics

- StrideIQ does not poach coached athletes
- No upsell banners or "see what you're missing" within the coached experience
- Coach's private notes are never visible to athletes
- Coach retains their notes history even after an athlete disconnects
- The athlete owns their data — it carries over if they become self-coached

---

## Database Schema

### New: `coach` table

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| created_at | DateTime | |
| email | Text, unique | |
| password_hash | Text | |
| display_name | Text | |
| stripe_customer_id | Text, nullable | |
| stripe_subscription_id | Text, nullable | |
| subscription_status | Text | trialing/active/past_due/canceled |
| referral_code | Text, unique | 8-char auto-generated |
| is_blocked | Boolean | default false |

### New: `coach_note` table

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| coach_id | UUID FK → coach | |
| athlete_id | UUID FK → athlete | |
| created_at | DateTime | |
| updated_at | DateTime | |
| content | Text | Private to coach |

### Modified: `athlete` table

| Column | Change |
|---|---|
| coach_id | ADD: UUID FK → coach, nullable, indexed |

### Modified: `training_plan` table

| Column | Change |
|---|---|
| goal_race_date | ALTER: nullable=True (was False) |
| goal_race_distance_m | ALTER: nullable=True (was False) |
| season_start | ADD: Date, nullable |
| season_end | ADD: Date, nullable |
| focus | ADD: Text, nullable |

Expand `plan_type` accepted values: `base_build`, `5k`, `10k`,
`half_marathon`, `marathon`, `ultra`, `cross_country`, `track`,
`comeback`, `maintenance`, `custom`.

---

## API Surface

### Coach Auth (`/v1/coach/auth/`)

| Method | Endpoint | Purpose |
|---|---|---|
| POST | /register | Create coach account |
| POST | /login | Coach login (returns JWT with type: "coach") |
| GET | /me | Coach profile + athlete count |

### Coach Dashboard (`/v1/coach/`)

| Method | Endpoint | Purpose |
|---|---|---|
| GET | /athletes | Roster (sorted: needs-attention first) |
| GET | /athletes/{id} | Full N=1 intelligence for one athlete |
| GET | /feed | Activity feed across all athletes (48h) |
| POST | /notes | Create private note |
| PUT | /notes/{id} | Update note |
| DELETE | /notes/{id} | Delete note |
| GET | /referral-link | Get invite URL |
| DELETE | /athletes/{id} | Remove athlete from roster |

### Coach AI (`/v1/coach/ai/`)

| Method | Endpoint | Purpose |
|---|---|---|
| POST | /chat | Research analyst chat scoped to one athlete |

### Coach Plan Management (`/v1/coach/athletes/{id}/plan/`)

| Method | Endpoint | Purpose |
|---|---|---|
| POST | / | Create plan for athlete |
| POST | /workouts | Add workout |
| PUT | /workouts/{wid} | Edit workout |
| DELETE | /workouts/{wid} | Delete workout |
| POST | /swap | Swap workout days |

### Athlete Endpoints (modified)

| Method | Endpoint | Purpose |
|---|---|---|
| POST | /v1/athlete/disconnect-coach | Athlete disconnects from coach |
| GET | /v1/auth/coach-info?code=X | Public: look up coach name by referral code |
| POST | /v1/auth/register | Modified: accept `coach_code` field |

---

## Frontend Pages

| Page | Auth | Purpose |
|---|---|---|
| `/for-coaches` | Public | Landing page (sales, pricing, CTA) |
| `/for-coaches/signup` | Public | Coach registration |
| `/for-coaches/login` | Public | Coach login |
| `/coach` | Coach | Dashboard (roster + feed) |
| `/coach/athletes/[id]` | Coach | Athlete detail (intelligence + AI + notes) |
| `/join/[code]` | Public | Athlete registration via coach referral |

### Navigation changes for coached athletes

When `user.coach_id` is set, primary nav reduces to:
**Home | Calendar | Activities**

"Coached by [Name]" badge appears on the home page.
Settings page gains a "Disconnect from Coach" section.

---

## Onboarding Flows

### Coach signup
1. Visit `/for-coaches` → click "Start Coaching"
2. `/for-coaches/signup` — name, email, password
3. Redirect to Stripe Checkout ($29.99/mo)
4. Stripe success → redirect to `/coach` (empty dashboard)
5. Empty state shows referral link + "Invite your first athlete"

### Athlete via coach
1. Coach shares referral link: `strideiq.run/join/ABC12345`
2. Athlete visits link → sees "Join StrideIQ — Coached by Coach Sarah"
3. Registers: name, email, password (no payment)
4. Account created with `coach_id` set, `subscription_tier = "coached"`
5. Redirect to onboarding (connect Garmin)
6. Coach's Stripe subscription updated: +1 athlete seat

### Athlete disconnection
1. Athlete goes to Settings → "Disconnect from Coach" → confirms
2. `coach_id` set to NULL
3. Coach notified via email
4. Coach's Stripe subscription updated: -1 athlete seat
5. Athlete sees "Want to continue with StrideIQ? [Upgrade]" banner
6. Historical data retained, intelligence generation stops until
   athlete subscribes independently

---

## Build Sequence

### Session 1: Backend + Stripe
1. Alembic migration (coach table, coach_note, athlete.coach_id, training_plan changes)
2. Coach auth (register, login, JWT with type: "coach")
3. Coach auth helpers (get_current_coach, require_active_coach)
4. Coach dashboard endpoints (roster, detail, feed, notes, referral)
5. Coach AI research analyst endpoint
6. Coach plan management endpoints
7. Athlete disconnect endpoint
8. Registration modification (coach_code handling)
9. Coach-info public endpoint
10. Stripe: coach checkout, seat management, webhook handling
11. Backend tests

### Session 2: Frontend
1. Coach landing page (`/for-coaches`)
2. Coach signup + login pages
3. Coach dashboard (roster view, feed view)
4. Athlete detail page (intelligence, AI chat, notes, plan)
5. `/join/[code]` registration page
6. Navigation changes for coached athletes
7. Coached athlete home page badge
8. Settings: disconnect from coach section
9. Post-disconnect state
10. Mobile responsiveness verification (390px)

---

## What This Is NOT

- Not a messaging platform between coach and athlete
- Not a marketplace where athletes find coaches
- Not a white-label product for coaches
- Not a team/group analytics tool
- Not a coach certification system
- Not a payment intermediary between coach and athlete
