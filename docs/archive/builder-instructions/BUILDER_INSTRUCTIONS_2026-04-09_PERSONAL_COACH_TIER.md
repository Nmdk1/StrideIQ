# Builder Instructions: Personal Coach Tier

**Date:** April 9, 2026
**Status:** Ready to build
**Estimated effort:** 2 sessions (Session 1: backend + Stripe, Session 2: frontend)
**Priority:** Revenue unlock (Product Strategy #15)

---

## Read Order (mandatory)

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. This file (complete build instructions)
3. `apps/api/models.py` — `Athlete` model, `TrainingPlan`, `CoachChat`
4. `apps/api/core/auth.py` — current auth helpers
5. `apps/api/services/stripe_service.py` — existing Stripe integration
6. `apps/api/services/ai_coach.py` — AI coach service (reference only)
7. `apps/api/routers/home.py` — briefing generation
8. `apps/web/app/components/Navigation.tsx` — current nav structure

---

## What This Is

A separate coaching product inside StrideIQ. Not a feature bolted onto
the athlete app. Two different products, one platform, one database.

**Product 1 — Self-coached athlete (existing):**
Signs up, connects Garmin, gets full platform: briefing, AI coach chat,
Manual, Progress, Calendar, Activities, Analytics, Fingerprint.
Pays their own subscription.

**Product 2 — Coaching platform (this build):**
Coaches sign up at a dedicated landing page. They pay $29.99/mo base +
$14.99/mo per athlete. They get a dashboard with N=1 intelligence on
every athlete, an AI research analyst (NOT the athlete-facing AI coach),
private notes, compliance tracking, plan management, and full
Operating Manual visibility per athlete.

Their athletes sign up via a referral link. Coached athletes see a
stripped experience: Home (with full briefing), Calendar, Activities.
No AI Coach chat. No Manual. No Progress. No Analytics. The human
coach replaces all of that. Athletes can disconnect from their coach
anytime from Settings.

---

## Why This Architecture

The AI coach and the human coach cannot coexist on the same athlete.
The AI coach says "take tomorrow easy." The human coach says "I want
you to do strides." The athlete gets confused, trust breaks. The
human coach IS the coach. The AI is the human coach's research tool.

This means:
- Coached athletes never see the AI coach chat
- The coach gets a different AI — an analytical assistant that surfaces
  data and findings, never prescribes training
- The intelligence layer (findings, Manual, race character) is visible
  to the coach, not the athlete
- The athlete's experience is: plan, activities, morning briefing. Clean.

---

## Database Schema

### New table: `coach`

```python
class Coach(Base):
    __tablename__ = "coach"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    email = Column(Text, unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    display_name = Column(Text, nullable=False)

    # Stripe billing
    stripe_customer_id = Column(Text, nullable=True)
    stripe_subscription_id = Column(Text, nullable=True)
    subscription_status = Column(Text, default="trialing")
    # Values: 'trialing', 'active', 'past_due', 'canceled', 'unpaid'

    # Referral
    referral_code = Column(Text, unique=True, nullable=False)
    # Auto-generated on creation: 8-char uppercase alphanumeric

    # Limits
    is_blocked = Column(Boolean, default=False)

    # Relationships
    athletes = relationship("Athlete", back_populates="coach",
                            foreign_keys="[Athlete.coach_id]")
    notes = relationship("CoachNote", back_populates="coach")
```

### New column on `Athlete`

```python
coach_id = Column(UUID(as_uuid=True), ForeignKey("coach.id"),
                  nullable=True, index=True)
coach = relationship("Coach", back_populates="athletes",
                     foreign_keys=[coach_id])
```

### New table: `coach_note`

```python
class CoachNote(Base):
    __tablename__ = "coach_note"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    coach_id = Column(UUID(as_uuid=True), ForeignKey("coach.id"), nullable=False)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    content = Column(Text, nullable=False)
    # Private to the coach. The athlete never sees these.

    coach = relationship("Coach", back_populates="notes")
    athlete = relationship("Athlete")
```

### TrainingPlan changes

Make `goal_race_date` and `goal_race_distance_m` nullable:

```python
goal_race_date = Column(Date, nullable=True)      # was nullable=False
goal_race_distance_m = Column(Integer, nullable=True)  # was nullable=False
```

Add columns for non-race plans:

```python
season_start = Column(Date, nullable=True)
season_end = Column(Date, nullable=True)
focus = Column(Text, nullable=True)  # e.g., "base aerobic", "speed", "XC fitness"
```

Expand `plan_type` to accept: `'base_build'`, `'5k'`, `'10k'`,
`'half_marathon'`, `'marathon'`, `'ultra'`, `'cross_country'`, `'track'`,
`'comeback'`, `'maintenance'`, `'custom'`.

---

## Alembic Migration

Single migration file. Operations:

1. Create `coach` table
2. Create `coach_note` table
3. Add `coach_id` FK column to `athlete` table
4. Alter `training_plan.goal_race_date` to nullable
5. Alter `training_plan.goal_race_distance_m` to nullable
6. Add `season_start`, `season_end`, `focus` columns to `training_plan`

---

## Backend API

### Coach Auth — `apps/api/routers/coach_auth.py` (NEW)

Separate auth endpoints for coaches. Do NOT reuse athlete auth.

**`POST /v1/coach/auth/register`**
```json
{
    "email": "coach@example.com",
    "password": "...",
    "display_name": "Coach Sarah"
}
```
- Validate email uniqueness against `coach` table (NOT athlete table)
- Hash password with same bcrypt as athlete auth
- Generate 8-char referral code: `''.join(random.choices(string.ascii_uppercase + string.digits, k=8))`
- Create Coach record
- Return JWT with `{"sub": coach.id, "email": coach.email, "type": "coach"}`
- Note the JWT uses `type: "coach"` not `role`. This distinguishes
  coach tokens from athlete tokens at the decode level.

**`POST /v1/coach/auth/login`**
- Standard email/password login against `coach` table
- Returns same JWT shape with `type: "coach"`

**`GET /v1/coach/auth/me`**
- Returns coach profile: id, email, display_name, referral_code,
  subscription_status, athlete_count

### Coach Auth Helpers — `apps/api/core/coach_auth.py` (NEW)

```python
async def get_current_coach(token = Depends(oauth2_scheme), db = ...):
    """Decode JWT, verify type='coach', return Coach record."""
    payload = decode_access_token(token)
    if payload.get("type") != "coach":
        raise HTTPException(403, "Not a coach account")
    coach = db.query(Coach).filter(Coach.id == payload["sub"]).first()
    if not coach or coach.is_blocked:
        raise HTTPException(403, "Coach account not found or blocked")
    return coach

async def require_active_coach(coach = Depends(get_current_coach)):
    """Verify coach has active Stripe subscription."""
    if coach.subscription_status not in ("active", "trialing"):
        raise HTTPException(402, "Coach subscription inactive")
    return coach
```

### Coach Dashboard API — `apps/api/routers/coach_dashboard.py` (NEW)

All endpoints require `Depends(require_active_coach)`.

**`GET /v1/coach/athletes`** — Roster

Returns all athletes where `athlete.coach_id == coach.id`:
```json
{
    "athletes": [
        {
            "id": "uuid",
            "display_name": "Adam Stewart",
            "email": "adam@...",
            "joined_at": "2026-04-10",
            "last_activity_date": "2026-04-09",
            "last_activity_summary": "6.2mi run, 8:55/mi, HR 122",
            "compliance_7d": 0.85,
            "alerts": ["HRV dropped 22% below personal baseline"],
            "has_plan": true,
            "needs_attention": true
        }
    ],
    "total_count": 3
}
```

Sorting: athletes with `needs_attention = true` float to top.
`needs_attention` is true when ANY of:
- No activity in 3+ days (and has an active plan)
- HRV dropped >15% below their 14-day average
- Missed 2+ planned workouts in last 7 days
- Coach flagged them for follow-up

`compliance_7d`: (completed planned workouts / total planned workouts)
in the last 7 days. Count a workout as completed if an activity exists
on that day with matching sport type.

**`GET /v1/coach/athletes/{athlete_id}`** — Athlete Detail

Full N=1 intelligence view. This is the Operating Manual + home
briefing + activity history combined for the coach's eyes.

```json
{
    "athlete": { "id", "display_name", "email", "joined_at" },
    "current_briefing": "...",  // Latest cached briefing text
    "wellness": {
        "sleep_hours": 5.3,
        "resting_hr": 52,
        "hrv_overnight": 38,
        "hrv_status": "below_baseline",
        "readiness": 42
    },
    "training_load": {
        "atl": 65,
        "ctl": 48,
        "tsb": -17,
        "weekly_distance_km": 95.2,
        "phase": "build"
    },
    "confirmed_findings": [
        {
            "signal": "sleep_hours",
            "direction": "higher_is_better",
            "threshold": 6.2,
            "friendly_name": "Sleep below 6.2h costs efficiency",
            "times_confirmed": 12,
            "strength": "strong"
        }
    ],
    "race_character": {
        "overperformance_pct": 7.0,
        "description": "Races 7% faster than best training efforts"
    },
    "recent_activities": [/* last 14 days */],
    "active_plan": { "name", "plan_type", "phase", "week_number", "compliance_pct" },
    "coach_notes": [/* ordered by created_at desc */],
    "upcoming_workouts": [/* next 7 days from PlannedWorkout */]
}
```

Build this response by reusing existing service functions:
- Briefing: query latest cached `BriefingCache` for this athlete
- Wellness: query latest `GarminDay`
- Training load: call `compute_training_load()` from existing service
- Findings: query `AthleteFinding` with `times_confirmed >= 3`
- Race character: query `RaceAnalysis` summary
- Activities: query `Activity` ordered by date desc, limit 20
- Plan: query active `TrainingPlan` + `PlannedWorkout`
- Notes: query `CoachNote` for this coach + athlete

**`GET /v1/coach/feed`** — Activity Feed

All activities across all coached athletes, last 48 hours:
```json
{
    "activities": [
        {
            "athlete_name": "Adam Stewart",
            "athlete_id": "uuid",
            "activity": { "id", "date", "sport", "distance_km",
                          "duration_s", "avg_pace", "avg_hr" },
            "was_planned": true,
            "compliance_note": "Hit target distance, pace 15s/km slower"
        }
    ]
}
```

**`POST /v1/coach/notes`** — Create note
```json
{ "athlete_id": "uuid", "content": "Discussed pacing. Watch next intervals." }
```

**`PUT /v1/coach/notes/{note_id}`** — Update note
```json
{ "content": "Updated text" }
```

**`DELETE /v1/coach/notes/{note_id}`** — Delete note

**`GET /v1/coach/referral-link`** — Get invite link
Returns `{ "url": "https://strideiq.run/join/{referral_code}", "code": "ABC12345" }`

**`DELETE /v1/coach/athletes/{athlete_id}`** — Remove athlete
- Sets `athlete.coach_id = NULL`
- Decrements Stripe subscription athlete seat quantity
- Sends athlete email: "Your coaching relationship has ended"
- Returns 204

### Coach AI Research Assistant — `POST /v1/coach/ai/chat`

Separate endpoint. NOT the athlete `/v1/coach/chat` endpoint.

Requires `Depends(require_active_coach)` + `athlete_id` in request body.
Verifies the athlete belongs to this coach.

System prompt (fundamentally different from athlete AI coach):

```
You are an analytical research assistant for a running coach using
StrideIQ. You have access to this athlete's complete physiological
data: all activities, wellness metrics (sleep, HRV, resting HR,
readiness), confirmed N=1 correlation findings, race history,
training plan, and personal operating manual findings.

YOUR ROLE:
- Present data, confirmed patterns, and trends with specifics
- Highlight concerning changes or notable deviations
- Compare current state to this athlete's personal baselines
- Answer the coach's questions with data-backed analysis
- Surface findings the coach may not have noticed

YOU DO NOT:
- Prescribe workouts, paces, or training changes
- Give motivational coaching language
- Make training decisions — the coach makes all decisions
- Reference population statistics or age-graded norms
- Use phrases like "I recommend" or "you should"
- Discuss your own capabilities or limitations

RESPONSE STYLE:
Lead with the data point. Then the personal context. Then the
implication for the coach to consider. Be concise. The coach is
busy and managing multiple athletes. No preamble.

Example exchange:
Coach: "How is Adam's HRV trending?"
You: "Adam's overnight HRV averaged 34ms over the last 7 days,
down 18% from his 30-day average of 41ms. His confirmed cliff
is 32ms — below that, his next-day efficiency drops 22% on
average. He's currently 2ms above the cliff. His sleep has
averaged 5.4h this week, below his confirmed 6.2h threshold.
The HRV decline correlates with the sleep deficit in his data."
```

Build the context the same way as the athlete AI coach:
- Load athlete's recent activities (14 days)
- Load wellness data (GarminDay, last 14 days)
- Load confirmed findings (AthleteFinding)
- Load training plan context
- Load Operating Manual highlights
- Load race character data

Use the same LLM routing as the athlete coach (Kimi K2.5 primary,
Claude Sonnet fallback). The model is the same. The prompt is different.

### Athlete Disconnect — `POST /v1/athlete/disconnect-coach`

Add to existing athlete settings/auth router.

Requires authenticated athlete with `coach_id IS NOT NULL`.
- Sets `athlete.coach_id = NULL`
- Decrements coach's Stripe subscription athlete seat quantity
- Sends notification email to coach: "[Athlete Name] has disconnected"
- Returns `{ "status": "disconnected" }`

No confirmation required on the backend. The frontend handles the
confirmation dialog.

### Athlete Registration via Coach Referral

**`GET /v1/auth/coach-info?code={referral_code}`** — Public endpoint
- Looks up `Coach` by `referral_code`
- Returns `{ "coach_name": "Coach Sarah" }` or 404
- Used by the registration page to show "Coached by Coach Sarah"

**`POST /v1/auth/register`** — Modify existing endpoint
Add optional `coach_code` field to registration request.
If present:
- Look up `Coach` by `referral_code`
- Set `athlete.coach_id = coach.id`
- Set `athlete.subscription_tier = "coached"` (new tier value)
- Increment coach's Stripe subscription athlete seat quantity
- Do NOT require athlete to pay. The coach pays for them.

### Navigation Gate

Add `coach_id` and `coach_name` to the athlete's auth/me response.
The frontend uses this to determine navigation.

In `GET /v1/auth/me` (or however the current user endpoint works):
```json
{
    "id": "...",
    "email": "...",
    "role": "athlete",
    "coach_id": "uuid-or-null",
    "coach_name": "Coach Sarah",
    "has_correlations": true,
    ...
}
```

---

## Stripe Billing

### Products to create in Stripe Dashboard

**Product 1: "StrideIQ Coach Platform"**
- Price: $29.99/month, recurring
- This is the base coach subscription

**Product 2: "Athlete Intelligence Seat"**
- Price: $14.99/month, recurring
- Usage type: licensed (quantity-based)
- This gets added as a subscription item when athletes are linked

### Coach Signup Checkout Flow

```python
# In coach_auth.py or a new coach_billing.py

async def create_coach_checkout(coach: Coach, db):
    """Create Stripe Checkout for new coach signup."""
    if not coach.stripe_customer_id:
        customer = stripe.Customer.create(
            email=coach.email,
            name=coach.display_name,
            metadata={"coach_id": str(coach.id)}
        )
        coach.stripe_customer_id = customer.id
        db.commit()

    session = stripe.checkout.Session.create(
        customer=coach.stripe_customer_id,
        mode="subscription",
        line_items=[{
            "price": COACH_BASE_PRICE_ID,  # $29.99/mo
            "quantity": 1,
        }],
        success_url="https://strideiq.run/coach?setup=complete",
        cancel_url="https://strideiq.run/for-coaches",
        metadata={"coach_id": str(coach.id)}
    )
    return session.url
```

### Adding/Removing Athlete Seats

```python
async def add_athlete_seat(coach: Coach, db):
    """Increment athlete seat quantity on coach's subscription."""
    subscription = stripe.Subscription.retrieve(coach.stripe_subscription_id)

    # Find the athlete seat item, or add it
    seat_item = next(
        (item for item in subscription["items"]["data"]
         if item["price"]["id"] == ATHLETE_SEAT_PRICE_ID),
        None
    )

    if seat_item:
        stripe.SubscriptionItem.modify(
            seat_item["id"],
            quantity=seat_item["quantity"] + 1,
            proration_behavior="create_prorations"
        )
    else:
        stripe.SubscriptionItem.create(
            subscription=coach.stripe_subscription_id,
            price=ATHLETE_SEAT_PRICE_ID,
            quantity=1,
            proration_behavior="create_prorations"
        )

async def remove_athlete_seat(coach: Coach, db):
    """Decrement athlete seat quantity."""
    subscription = stripe.Subscription.retrieve(coach.stripe_subscription_id)
    seat_item = next(
        (item for item in subscription["items"]["data"]
         if item["price"]["id"] == ATHLETE_SEAT_PRICE_ID),
        None
    )
    if seat_item and seat_item["quantity"] > 1:
        stripe.SubscriptionItem.modify(
            seat_item["id"],
            quantity=seat_item["quantity"] - 1,
            proration_behavior="create_prorations"
        )
    elif seat_item and seat_item["quantity"] == 1:
        stripe.SubscriptionItem.delete(seat_item["id"],
                                        proration_behavior="create_prorations")
```

### Webhook Handling

Add coach-specific handling to existing Stripe webhook endpoint:

- `customer.subscription.updated` — update `coach.subscription_status`
- `customer.subscription.deleted` — set `coach.subscription_status = "canceled"`
- `invoice.payment_failed` — set `coach.subscription_status = "past_due"`

When a coach subscription is canceled:
- Do NOT immediately disconnect athletes
- Set a 7-day grace period
- After 7 days with no reactivation: set all `athlete.coach_id = NULL`,
  send athletes notification emails

---

## Frontend

### Page: `/for-coaches` — Coach Landing Page (PUBLIC)

This is the sales page. Must be polished. This is what converts
coaches to customers.

**Hero section:**
> "The only coaching platform that knows your athletes better
> than you do."
>
> StrideIQ discovers confirmed physiological patterns in each
> athlete's data — thresholds, cliffs, race-day character,
> sleep-performance relationships — and puts them in your hands.
>
> [Start Coaching — $29.99/mo]

**Feature grid (3 columns on desktop, stacked on mobile):**

1. **N=1 Intelligence**
   "Every athlete gets a personal operating manual built from their
   own data. Not population averages. Their confirmed thresholds,
   their recovery patterns, their race character."

2. **AI Research Analyst**
   "Ask questions about any athlete. 'What's happening with Adam's
   HRV?' 'How does Jim's current block compare to his pre-marathon
   build?' Backed by every data point, every confirmed finding."

3. **Full Briefing for Athletes**
   "Your athletes open the app and see a personalized daily briefing —
   today's plan, yesterday's analysis, wellness context. You stay
   focused on coaching. The platform handles the data."

**Pricing section:**
> $29.99/month platform fee
> + $14.99/month per athlete
>
> Everything included. N=1 intelligence engine. AI research analyst.
> Daily athlete briefings. Plan management. Private notes.
>
> Coaching 25+ athletes? [Contact us] for volume pricing.

**CTA:** "Start Coaching" → `/for-coaches/signup`

**Footer link:** "Already have an account? [Log in](/for-coaches/login)"

### Page: `/for-coaches/signup` — Coach Registration

Simple form:
- Display name
- Email
- Password
- Confirm password

On submit:
1. `POST /v1/coach/auth/register`
2. Store JWT
3. Redirect to Stripe Checkout (coach base plan)
4. On Stripe success: redirect to `/coach` (dashboard)

### Page: `/for-coaches/login` — Coach Login

- Email
- Password

On submit: `POST /v1/coach/auth/login`, store JWT, redirect to `/coach`

### Page: `/coach` — Coach Dashboard (AUTHENTICATED)

This is the coach's daily tool. Mobile-first. Dark theme.

**Layout:** Single column on mobile. No sidebar.

**Top bar:** "StrideIQ Coach" + coach name + logout

**Athlete roster (main view):**
Cards, one per athlete. Sorted: needs-attention first, then by
last activity date.

Each card shows:
- Athlete name (large, tappable → detail view)
- Last activity: "6.2mi run · 8:55/mi · yesterday"
- Compliance badge: "85% this week" (green >80%, yellow 50-80%, red <50%)
- Alert chips (if any): "HRV ↓22%" / "3 days inactive" / "Missed 2 workouts"
- Quick actions: [Note] [AI] icons

**Empty state (no athletes):**
> "Invite your first athlete"
>
> Share this link with your athletes:
> `strideiq.run/join/ABC12345` [Copy]
>
> When they sign up, they'll appear here automatically.
> You'll be billed $14.99/mo per athlete.

**Header actions:**
- "Invite Athlete" button → shows referral link modal
- "Feed" tab → switches to activity feed view

**Activity Feed view:**
Chronological feed of all athlete activities, last 48 hours.
Each entry: athlete name, activity summary, compliance note.
Tappable → goes to athlete detail.

### Page: `/coach/athletes/[id]` — Athlete Detail (AUTHENTICATED)

Full intelligence view for one athlete. This is where the coach
spends time understanding each athlete.

**Sections (scrollable, single column):**

1. **Header:** Athlete name, "Last active: 2h ago", compliance badge

2. **Today's Briefing:** The athlete's latest cached briefing text.
   Rendered as-is. Same content the athlete sees on their home page.

3. **Wellness Panel:** Current sleep, HRV (with personal baseline
   comparison), resting HR, readiness. Color-coded: green (above
   baseline), yellow (near baseline), red (below threshold/cliff).

4. **Training Load:** ATL, CTL, TSB as numbers with trend arrows.
   Current phase and week.

5. **This Week's Plan:** Next 7 days of PlannedWorkout entries with
   completion status. Tappable to edit (coach can modify workouts).

6. **Confirmed Findings (top 10):** The athlete's strongest N=1
   findings, friendly-named. "Sleep below 6.2h → efficiency drops 22%."
   Expandable to see all.

7. **Race Character:** If the athlete has race data, show
   overperformance percentage and key race insights.

8. **Recent Activities (14 days):** Activity cards with key metrics.
   Tappable → links to the activity detail page (read-only view
   of the athlete's activity page).

9. **Coach Notes:** Private notes the coach has written about this
   athlete. Add/edit/delete. Timestamped.

10. **AI Research Assistant:** Chat interface at the bottom.
    "Ask about this athlete..." input. Opens into a conversation
    view. Scoped to this athlete's data.

11. **Actions:** [Remove Athlete] button (confirmation dialog).

### Coach Plan Management

Coaches can manage their athletes' training plans using existing
plan endpoints. The auth layer needs to be updated:

**Pattern:** When a coach calls a plan endpoint with an athlete_id
that belongs to them, the system authorizes it as if the coach were
that athlete. This reuses ALL existing plan endpoints without
duplicating them.

Add a helper to `core/coach_auth.py`:
```python
async def get_coached_athlete(
    athlete_id: UUID,
    coach: Coach = Depends(require_active_coach),
    db = ...
):
    """Verify this athlete belongs to this coach, return athlete."""
    athlete = db.query(Athlete).filter(
        Athlete.id == athlete_id,
        Athlete.coach_id == coach.id
    ).first()
    if not athlete:
        raise HTTPException(404, "Athlete not found in your roster")
    return athlete
```

Create coach-specific plan endpoints that proxy to existing logic:
- `POST /v1/coach/athletes/{id}/plan` — create plan for athlete
- `PUT /v1/coach/athletes/{id}/plan/workouts/{workout_id}` — edit workout
- `DELETE /v1/coach/athletes/{id}/plan/workouts/{workout_id}` — delete workout
- `POST /v1/coach/athletes/{id}/plan/workouts` — add workout
- `POST /v1/coach/athletes/{id}/plan/swap` — swap workout days

These endpoints use `get_coached_athlete` for auth, then call the
same service functions the existing plan endpoints use. Do NOT
duplicate plan logic. Reuse it.

For non-race plans (base building, XC, track): the coach creates
a plan manually by adding workouts one at a time. The plan
generator is only available for race-specific plans where
`goal_race_date` and `goal_race_distance_m` are provided.

### Navigation Changes for Coached Athletes

In `Navigation.tsx`, check `user.coach_id`:

```tsx
// Simplified logic
const isCoached = !!user?.coach_id;

const primaryNav = isCoached
    ? [
        { label: "Home", href: "/home", icon: Home },
        { label: "Calendar", href: "/calendar", icon: Calendar },
        { label: "Activities", href: "/activities", icon: Activity },
      ]
    : [
        // existing full nav
        { label: "Home", href: "/home", icon: Home },
        { label: "Coach", href: "/coach-chat", icon: MessageCircle },
        { label: "Calendar", href: "/calendar", icon: Calendar },
        // ... Manual, Progress, etc.
      ];
```

Add "Coached by [Name]" badge in the nav or home page header for
coached athletes.

### Coached Athlete Home Page

The home page for coached athletes shows the SAME full briefing as
self-coached athletes. The briefing is already being generated by
the nightly pipeline regardless of coaching status.

One addition to the home page for coached athletes: a small card
above the briefing:

```
Coached by Coach Sarah
```

No link, no action. Just attribution.

### Coached Athlete Settings

Add a section to the Settings page when `user.coach_id` is set:

```
── Coaching ──────────────────────────
Coached by: Coach Sarah
Connected since: April 10, 2026

[Disconnect from Coach]
```

The "Disconnect" button shows a confirmation dialog:

> "Are you sure you want to disconnect from Coach Sarah?
>
> Your training data stays with you. You'll lose access to
> your daily briefing and coached experience. You can sign up
> for a full StrideIQ account to continue independently."
>
> [Cancel] [Disconnect]

On confirm: `POST /v1/athlete/disconnect-coach`

After disconnect:
- Nav reverts to... basic. The athlete has no subscription of their own.
- Show a banner: "Want to continue with StrideIQ? [Upgrade to full access]"
- The upgrade link goes to the regular subscription checkout.
- Until they subscribe, they can view their historical activities
  but get no new briefings, no AI coach, no intelligence surfaces.

### Page: `/join/[code]` — Athlete Registration via Coach

This is what athletes see when they click the coach's referral link.

1. Page loads, calls `GET /v1/auth/coach-info?code={code}`
2. If valid: shows "Join StrideIQ — Coached by Coach Sarah"
3. Registration form: display name, email, password, confirm password
4. On submit: `POST /v1/auth/register` with `coach_code: code`
5. No payment required. The coach pays.
6. After registration: redirect to onboarding (connect Garmin).
7. The onboarding flow is the same as existing athletes minus
   the payment step.

If the code is invalid: "This coaching link is not valid. [Sign up
for StrideIQ independently →]"

---

## Mobile-First Constraints

Everything above must work at 390px viewport width.

- 44px minimum touch targets
- No horizontal scroll
- Dark theme: slate-900/800/700 backgrounds
- Cards stack vertically on mobile
- Coach dashboard: no table views. Cards only.
- Activity feed: compact list items, not cards
- AI chat: full-screen overlay on mobile
- Coach landing page: single column, stacked sections

---

## Testing Requirements

### Backend tests:

1. Coach registration creates record with referral code
2. Coach login returns JWT with `type: "coach"`
3. Athlete registration with `coach_code` sets `coach_id` correctly
4. Coach can only see athletes where `athlete.coach_id == coach.id`
5. Coach cannot access athletes belonging to another coach
6. Athlete disconnect sets `coach_id = NULL`
7. Coach remove athlete sets `coach_id = NULL`
8. Stripe seat quantity increments on athlete link
9. Stripe seat quantity decrements on athlete unlink
10. Coach-AI endpoint loads correct athlete context
11. Coach-AI endpoint rejects requests for non-coached athletes

### Frontend tests (manual):

1. Coach landing page renders at 390px
2. Coach signup → Stripe → dashboard flow completes
3. Referral link registration works
4. Coached athlete sees only Home/Calendar/Activities nav
5. Coached athlete does NOT see Coach chat, Manual, Progress
6. Disconnect flow works, nav changes
7. Coach dashboard sorts needs-attention athletes first
8. Coach-AI chat returns athlete-specific data

---

## What NOT to Build

- Coach-to-athlete messaging within the platform. Coaches text,
  email, or call. StrideIQ is not a messaging app.
- Coach branding/white-labeling. Not in scope.
- Marketplace (athletes find coaches). Not in scope.
- Coach certifications or verification. Not our business.
- Group training views or team analytics. Individual athletes only.
- Coach mobile app. This is responsive web, not native.
- Athlete payment to coach through the platform. The coach handles
  their own client billing externally.

---

## Success Criteria

1. A coach can sign up, pay, and see an empty dashboard in under 3 minutes
2. A coach can share a referral link and have an athlete appear on
   their dashboard within 5 minutes of the athlete registering
3. The coach can see every piece of N=1 intelligence for each athlete
4. The coach can ask the AI research analyst questions about any athlete
   and get data-backed answers
5. A coached athlete sees ONLY Home, Calendar, Activities
6. A coached athlete cannot access the AI coach chat
7. An athlete can disconnect from their coach at any time
8. Stripe billing correctly tracks athlete count
9. Everything works at 390px viewport width
