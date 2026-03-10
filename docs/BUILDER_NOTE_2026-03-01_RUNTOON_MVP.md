# Builder Note: Runtoon MVP

**Date:** March 1, 2026
**Assigned to:** Backend + Frontend Builder
**Priority:** HIGH — primary growth feature
**Phase 0 Status:** GO — 6/6 rubric thresholds passed. 6 test images generated, all share-worthy, no safety blocks.
**Proposal:** `docs/RUNTOON_PHASE_0_PROPOSAL.md`

---

## Objective

Ship an MVP of Runtoon: an AI-generated, personalized, humorous caricature image created after every run. The athlete previews it, optionally regenerates, and downloads it to share wherever they want. Every shared image carries `strideiq.run` branding — organic acquisition.

---

## Scope

### New Backend Components

| Component | Type | Detail |
|---|---|---|
| `apps/api/services/runtoon_service.py` | **New service** | Prompt assembly from Activity/InsightLog/DailyCheckin + `gemini-3.1-flash-image-preview` API call + image storage write |
| `apps/api/tasks/runtoon_tasks.py` | **New Celery task** | `generate_runtoon(activity_id)`: called post-sync, fully async, silent on failure |
| `RuntoonImage` model in `models.py` | **New model** | See schema below |
| `AthletePhoto` model in `models.py` | **New model** | See schema below |
| `runtoon_001` Alembic migration | **New migration** | Creates `runtoon_image` + `athlete_photo` tables. Chains off current head. Update `EXPECTED_HEADS` in `.github/scripts/ci_alembic_heads_check.py` |
| `apps/api/routers/runtoon.py` | **New router** | Endpoints for photo upload, Runtoon retrieval, regeneration, download |
| `apps/api/services/storage_service.py` | **New service** | Cloudflare R2 integration — upload, signed URL generation, deletion |

### Frontend Components

| Component | Type | Detail |
|---|---|---|
| `apps/web/app/activities/[id]/page.tsx` | **Modify** | Add "Your Runtoon" card below run analysis |
| `apps/web/app/settings/page.tsx` | **Modify** | Add "Runtoon Photos" section for photo upload/management |
| `apps/web/components/runtoon/RuntoonCard.tsx` | **New component** | Preview modal with regenerate + download buttons |
| `apps/web/app/home/page.tsx` | **Modify** | Add Runtoon teaser thumbnail after LastRunHero (cached URL only) |

### Infrastructure

| Component | Detail |
|---|---|
| **Cloudflare R2** | New private bucket for athlete photos + generated Runtoons. All access via signed URLs with 15-minute TTL. |

---

## Data Models

### `AthletePhoto`

```python
class AthletePhoto(Base):
    __tablename__ = "athlete_photo"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)
    storage_key = Column(Text, nullable=False)  # R2 object key (never a public URL)
    photo_type = Column(Text, nullable=False)  # "face", "running", "full_body", "additional"
    mime_type = Column(Text, nullable=False)  # "image/jpeg", "image/png"
    size_bytes = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Consent tracking (required for biometric-adjacent data)
    consent_at = Column(DateTime(timezone=True), nullable=False)  # When athlete agreed
    consent_version = Column(Text, nullable=False, default="1.0")  # Consent policy version

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

**Consent requirement:** The photo upload endpoint MUST capture an explicit consent timestamp and policy version before accepting the upload. The frontend upload flow must include a consent acknowledgment ("I agree that StrideIQ may use these photos to generate personalized run images") before the upload button activates.

**Deletion/retention contract:**
- When an athlete **deletes a photo** via `DELETE /v1/runtoon/photos/{id}`: mark `is_active = False` in DB AND delete the object from R2 immediately.
- When an athlete **deletes their account**: cascade-delete all `AthletePhoto` and `RuntoonImage` records AND delete all corresponding R2 objects. Use a background task if the R2 deletion is slow.
- When an athlete **disconnects Garmin/Strava**: photos are NOT deleted (photos are athlete-owned, not provider-owned). Runtoon generation stops because there are no new activities, but existing photos and Runtoons remain until the athlete explicitly deletes them or their account.

### `RuntoonImage`

```python
class RuntoonImage(Base):
    __tablename__ = "runtoon_image"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)
    activity_id = Column(UUID(as_uuid=True), ForeignKey("activity.id"), nullable=False, index=True)

    # Idempotency: only one auto-generated image per activity (attempt_number=1)
    # UniqueConstraint prevents duplicate auto-generation from concurrent sync hooks
    __table_args__ = (
        UniqueConstraint("activity_id", "attempt_number", name="uq_runtoon_activity_attempt"),
    )

    storage_key = Column(Text, nullable=False)  # R2 object key (never a public URL)
    prompt_hash = Column(Text, nullable=True)  # SHA256 of prompt for debugging
    generation_time_ms = Column(Integer, nullable=True)
    cost_usd = Column(Numeric(6, 4), nullable=True)  # e.g., 0.0670
    model_version = Column(Text, nullable=False, default="gemini-3.1-flash-image-preview")
    attempt_number = Column(Integer, nullable=False, default=1)  # 1 = auto, 2-3 = regeneration
    is_visible = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

---

## API Endpoints

### Photo Management

```
POST   /v1/runtoon/photos          — Upload athlete reference photo (multipart)
GET    /v1/runtoon/photos          — List athlete's photos (signed URLs)
DELETE /v1/runtoon/photos/{id}     — Remove a photo
```

**Upload constraints:**
- 3 photos minimum before Runtoon generation is enabled
- Max 10 photos per athlete
- Max 7 MB per photo
- Accepted formats: JPEG, PNG, WebP
- Photos stored in private R2 bucket under `photos/{athlete_id}/{photo_id}.{ext}`

### Runtoon Operations

```
GET    /v1/activities/{id}/runtoon          — Get Runtoon for activity (signed URL + metadata)
POST   /v1/activities/{id}/runtoon/generate — Manual regeneration (rate-limited)
GET    /v1/runtoon/download/{id}            — Generate signed download URL (1:1 or 9:16 format)
```

**Rate limits (enforced, not advisory):**
- Auto-generation: 1 per activity (enforced by `UniqueConstraint("activity_id", "attempt_number")` — insert with `attempt_number=1` will fail on duplicate)
- Manual regeneration: max 2 per activity (enforced by query: `SELECT COUNT(*) FROM runtoon_image WHERE activity_id = ? AND athlete_id = ?` — reject if count >= 3)
- Daily cap: max 5 generations per athlete per day (enforced by query: `SELECT COUNT(*) FROM runtoon_image WHERE athlete_id = ? AND created_at >= today_utc_start` — reject if count >= 5)

**Enforcement path in Celery task:**
```python
# Step 1: Check daily cap BEFORE generation
today_count = db.query(func.count(RuntoonImage.id)).filter(
    RuntoonImage.athlete_id == athlete_id,
    RuntoonImage.created_at >= today_start_utc,
).scalar()
if today_count >= 5:
    logger.info(f"Daily Runtoon cap reached for {athlete_id}")
    return  # silent exit, no error

# Step 2: Check activity already has auto-generated image
existing = db.query(RuntoonImage).filter(
    RuntoonImage.activity_id == activity_id,
    RuntoonImage.attempt_number == 1,
).first()
if existing:
    logger.info(f"Runtoon already exists for activity {activity_id}")
    return  # idempotent exit

# Step 3: Generate and insert — UniqueConstraint is the final safety net
# If concurrent tasks race, the loser gets IntegrityError and exits silently
```

---

## Entitlement Gating

Use `tier_satisfies()` from `apps/api/core/tier_utils.py`. Follow `plan_export.py` pattern.

| Tier | Access |
|---|---|
| **Free** | 1 Runtoon on first-ever activity only. Regeneration blocked. |
| **One-time ($5)** | No Runtoon access |
| **Guided ($15/mo)** | Unlimited Runtoons (1 per activity auto + 2 regenerations). 1K resolution. |
| **Premium ($25/mo)** | Unlimited Runtoons + 2K resolution option |

**Feature flag for beta:** Use `FeatureFlag` table with key `runtoon.enabled`. Check `enabled` + `allowed_athlete_ids` for founder-only testing. Migrate to entitlement gating at launch.

---

## Prompt Architecture

The prompt sent to `gemini-3.1-flash-image-preview` (marketed as "Nano Banana 2") has 4 layers assembled by `runtoon_service.py`. **Always use the API model string `gemini-3.1-flash-image-preview` in code — never the marketing name.**

### Layer 1: Style Anchor (hardcoded constant)

```
Bold, vibrant caricature/comic style. NOT photorealistic.
The runner is the HERO. Accurate to their real body from reference photos,
always powerful and determined. Depict them honestly — do not idealize or
alter their body type. Make them look heroic AS THEY ARE.
Fully clothed in appropriate running gear. PG-safe always.
GPS watch on wrist.
THE IMAGE MUST BE FUNNY — visual humor, exaggerated expressions,
situational comedy that matches the run's emotional truth.

IMAGE LAYOUT:
- Top 65%: Caricature scene with humorous visual element
- Bottom 35%: Dark banner with stats and witty caption
- Bottom watermark: "strideiq.run"

ASPECT RATIO: 1:1 square
```

### Layer 2: Athlete Reference (3-10 photos)

All active `AthletePhoto` records for the athlete, loaded from R2 via signed URL, passed as `Part.from_bytes()` image parts.

### Layer 3: Activity Data

Assembled from `Activity` record:
- Date and time of day (for scene lighting/mood)
- Distance, pace, duration, average HR
- Workout type (from `Activity.workout_type`)
- Location (from `Activity.name` — typically includes location)
- Race context (if `Activity.is_race_candidate`)
- Training plan context (if active `TrainingPlan` exists — what phase, days to race)

### Layer 4: Coaching Insight + Humor

Two-step process:
1. **Check `InsightLog`** for any insight that fired on the same day as this activity. If found, use the insight's narrative as the coaching context.
2. **If no insight exists**, generate a witty caption using a text-only Gemini Flash call with the activity data. The caption must be genuinely funny — NOT motivational coaching speak.

The caption is baked into the image by the model, not overlaid.

**Content guardrails for captions:**
- No profanity or slurs in generated captions. Add a simple blocklist check after caption generation — if a blocked word appears, regenerate the caption (text-only call, cheap).
- No third-party logos or brand text should appear in the generated image. Add to the style anchor prompt: "Do not include any real brand logos, trademarked text, or copyrighted material in the image. The only text allowed is the stats line, caption, and strideiq.run watermark."

### Prompt Assembly

```python
def assemble_runtoon_prompt(activity, insights, plan_context):
    parts = []

    # Layer 2: athlete photos (loaded from R2)
    for photo in athlete_photos:
        parts.append(Part.from_bytes(data=photo_bytes, mime_type=photo.mime_type))

    # Layers 1 + 3 + 4: text prompt
    prompt = f"""
    {STYLE_ANCHOR}

    {format_activity_data(activity)}

    STATS TO RENDER: {format_stats_line(activity)}
    CAPTION TO RENDER: "{generate_or_fetch_caption(activity, insights)}"
    VISUAL DIRECTION: {generate_scene_direction(activity, plan_context)}

    WATERMARK: strideiq.run

    Create a flattering, heroic, HUMOROUS caricature using the reference
    photos. The runner should be depicted in a scene that reflects the
    actual run conditions described above.
    """

    parts.append(Part.from_text(text=prompt))
    return parts
```

---

## Celery Task Integration

### Post-Sync Hook

**In `apps/api/tasks/strava_tasks.py`** — add to `post_sync_processing_task()` after existing processing:

```python
try:
    from tasks.runtoon_tasks import generate_runtoon_for_latest
    generate_runtoon_for_latest.delay(str(athlete.id))
except Exception as e:
    logger.warning(f"Could not queue Runtoon generation: {e}")
```

**In `apps/api/tasks/garmin_webhook_tasks.py`** — add after `enqueue_briefing_refresh()` when `created > 0`:

```python
try:
    from tasks.runtoon_tasks import generate_runtoon_for_latest
    generate_runtoon_for_latest.delay(str(athlete_id))
except Exception as e:
    logger.warning(f"Could not queue Runtoon generation: {e}")
```

### Runtoon Task Module: `apps/api/tasks/runtoon_tasks.py`

```python
@celery_app.task(bind=True, max_retries=1, soft_time_limit=60, time_limit=90)
def generate_runtoon_for_latest(self, athlete_id: str):
    """
    Generate a Runtoon for the athlete's most recent activity.
    Called post-sync. Fire-and-forget. Silent on failure.
    """
    # 1. Check feature flag / entitlement
    # 2. Check daily generation cap (max 5/day)
    # 3. Get most recent Activity without a RuntoonImage
    # 4. Get athlete's active AthletePhoto records (min 3 required)
    # 5. Load photo bytes from R2
    # 6. Assemble prompt via runtoon_service
    # 7. Call gemini-3.1-flash-image-preview API with SDK timeout + task soft_time_limit
    # 8. Decode base64 response, upload to R2
    # 9. Create RuntoonImage record
    # 10. On ANY failure: log warning, do NOT raise, do NOT retry
```

---

## Object Storage: Cloudflare R2

### Setup

Create a private R2 bucket: `strideiq-runtoon` (or similar).

**Env vars to add:**
```
R2_ACCOUNT_ID=<cloudflare account id>
R2_ACCESS_KEY_ID=<r2 access key>
R2_SECRET_ACCESS_KEY=<r2 secret key>
R2_BUCKET_NAME=strideiq-runtoon
R2_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
```

### Storage Service: `apps/api/services/storage_service.py`

Use `boto3` with S3-compatible R2 endpoint. Three operations:

```python
def upload_file(key: str, data: bytes, content_type: str) -> None
def generate_signed_url(key: str, expires_in: int = 900) -> str  # 15 min TTL
def delete_file(key: str) -> None
```

### Key Structure

```
photos/{athlete_id}/{photo_id}.{ext}       — Athlete reference photos
runtoons/{athlete_id}/{runtoon_id}.png      — Generated Runtoon images
```

---

## Privacy Invariant (NON-NEGOTIABLE)

**ALL athlete data is private by default.** This is a platform-level invariant.

- All R2 buckets are **private** (no public access).
- All access is via **signed URLs with 15-minute TTL**.
- Photo URLs and Runtoon URLs are **never returned as public URLs** in any API response.
- The API always returns signed URLs generated server-side for the authenticated athlete's own data.
- The athlete explicitly downloads their Runtoon and posts it themselves. StrideIQ never publishes on their behalf.

---

## Hard Constraints

1. **Fully async.** Runtoon generation runs in a Celery task. It MUST NEVER block the sync pipeline, the home page, or any request thread. Generation failure = log server-side, show "Runtoon unavailable for this run" on frontend.

2. **Idempotency.** Both Strava and Garmin sync paths trigger Runtoon generation. The task MUST be idempotent — if a Runtoon already exists for an activity (same `activity_id` + `attempt_number`), exit silently. Enforced by DB unique constraint + app-level check before API call.

3. **LLM timeout.** `gemini-3.1-flash-image-preview` API call must have both an SDK-level timeout AND a task-level `soft_time_limit`. Consistent with existing LLM timeout rules.

4. **DB sessions.** Do all DB reads in the Celery worker before passing pure data to the API call. Never pass a SQLAlchemy session across thread boundaries.

5. **Cost guard.** Cap at 1 auto-generate per activity. Max 2 manual regenerations per activity. Max 5 total generations per athlete per day. Track `cost_usd` in `RuntoonImage`. Enforced by DB queries (see Rate Limits section), not prose.

6. **Home page rule.** The Runtoon teaser on `/home` MUST use a cached signed URL. Never trigger generation from the home page request path.

7. **PG-safe.** The style anchor enforces: fully clothed runner in appropriate athletic gear, no nudity, no suggestive content. Safety filter at "Block some" (default) or higher. The athlete previews before downloading.

8. **Body honesty.** The caricature depicts the runner accurately based on their photos. Do not idealize or alter body type. Make them heroic AS THEY ARE. Every runner is a hero.

9. **Consent + retention.** Photo upload requires explicit consent timestamp. Account deletion cascades to R2 object deletion. See AthletePhoto deletion/retention contract above.

10. **No third-party content.** Generated images must not contain real brand logos, trademarked text, or copyrighted material. Enforced via prompt instruction + caption blocklist.

---

## Gemini API Integration

**Model:** `gemini-3.1-flash-image-preview`

**Existing pattern:** Follow `apps/api/services/adaptation_narrator.py`. Use same `GOOGLE_AI_API_KEY` env var and `google.genai.Client`.

```python
from google import genai
from google.genai import types as genai_types

client = genai.Client(api_key=os.getenv("GOOGLE_AI_API_KEY"))

response = client.models.generate_content(
    model="gemini-3.1-flash-image-preview",
    contents=genai_types.Content(parts=parts),
    config=genai_types.GenerateContentConfig(
        response_modalities=["Text", "Image"],
        temperature=0.9,
    ),
)

# Response image data is base64-encoded — MUST decode before storing
for part in response.candidates[0].content.parts:
    if part.inline_data and part.inline_data.mime_type.startswith("image/"):
        raw = part.inline_data.data
        if isinstance(raw, str):
            image_bytes = base64.b64decode(raw)
        else:
            image_bytes = base64.b64decode(raw) if raw[:4] != b'\x89PNG' else raw
```

**Cost:** ~$0.067 per image at 1K resolution. Track in `RuntoonImage.cost_usd`.

**Latency:** 10-13 seconds average. Fully async, athlete never waits synchronously.

---

## Frontend UX

### Activity Detail Page (`/activities/[id]`)

Add a "Your Runtoon" card below run analysis. States:

1. **No photos uploaded:** "Upload photos in Settings to enable Runtoon" with link to Settings.
2. **Generating:** Subtle loading state — "Creating your Runtoon..." with a spinner. Poll every 5s until ready or 90s timeout.
3. **Ready:** Show the Runtoon image with:
   - Full preview on tap
   - "Regenerate" button (if attempts < 3 and entitled)
   - "Download 1:1" button (square, Instagram feed)
   - "Download 9:16" button (tall, Instagram Stories)
4. **Generation failed:** Neutral state — "Runtoon unavailable for this run." No scary error, no stack trace, no retry button. Just a clean acknowledgment. Log failure details server-side.
5. **Free tier, first run used:** "Upgrade to Guided for unlimited Runtoons" CTA.
6. **Not entitled:** "Available with Guided plan" — no image shown.

### Settings Page (`/settings`)

Add "Runtoon Photos" section:
- Grid of uploaded photos with delete option
- "Add Photo" upload button
- Min 3 / Max 10 indicator
- Accepted formats note (JPEG, PNG, WebP, max 7MB)

### Home Page (`/home`)

**Brand subline:** Add `"Your body. Your data. Your voice."` as a persistent brand-level subline on the home page. Position it directly below the greeting/logo area, above the fold, before any cards. Style: subtle, lowercase-feeling typography (light weight, muted but legible against the dark background). It is a brand promise, not a feature label — do not attach it to any specific card or component. It should feel like the first thing the athlete reads after their name.

**Runtoon teaser:** After LastRunHero, show a small Runtoon thumbnail for the most recent activity (if one exists). Tap navigates to the activity detail page. **Use cached signed URL only — never trigger generation.**

### Download

When the athlete taps "Download 1:1" or "Download 9:16":
- Generate a fresh signed URL (15-min TTL)
- Trigger browser download with proper filename: `runtoon_{date}_{distance}.png`

**9:16 format (Stories):** Server-side deterministic recompose from the 1:1 original. Do NOT make a second API call. Use Pillow to:
1. Create a 1080x1920 canvas with the dark banner color as background
2. Place the 1:1 image (1024x1024) centered in the upper portion
3. Re-render the stats line and caption below in the expanded space
4. Add `strideiq.run` watermark at the bottom

This avoids a $0.067 second API call per download format and gives deterministic output.

---

## Alembic Migration

New migration `runtoon_001`:
- `down_revision`: current head (verify with `alembic heads`)
- Creates `athlete_photo` and `runtoon_image` tables
- Update `EXPECTED_HEADS` in `.github/scripts/ci_alembic_heads_check.py`

---

## Dependencies

### Python (add to requirements)
- `boto3` — S3-compatible client for Cloudflare R2
- `Pillow` — 9:16 server-side recompose from 1:1 original (canvas creation, image placement, text rendering)

### Existing (already installed)
- `google-genai` — Gemini API client (already used by adaptation_narrator, ai_coach, etc.)

---

## Out of Scope

- No social platform integrations (no Instagram API, no X API, no Strava posting)
- No avatar evolution across runs (Phase 3 aspiration)
- No race-arc narrative tone shifts (Phase 3)
- No N=1 visual callouts (Phase 3)
- No standalone $9.99/mo Runtoon pricing tier
- No backend changes to existing Activity/InsightLog models
- No changes to existing sync pipelines beyond adding the Runtoon task hook

---

## Acceptance Criteria

1. **Photo upload:** Athlete can upload 3-10 photos in Settings. Photos stored in private R2 bucket. Signed URLs returned for preview.
2. **Auto-generation:** After a Garmin or Strava sync, a Runtoon is generated asynchronously and appears on the activity detail page within 30 seconds.
3. **Preview + regenerate:** Athlete can view their Runtoon, regenerate up to 2 more times, and download in 1:1 format.
4. **Entitlement gating:** Free tier gets 1 Runtoon on first activity only. Guided/Premium get unlimited. Regeneration blocked for free.
5. **Feature flag:** Runtoon is gated behind `runtoon.enabled` feature flag with `allowed_athlete_ids` for founder-only testing.
6. **Privacy:** No public URLs anywhere. All signed URLs have 15-minute TTL. Verify by inspecting API responses — no R2 bucket URLs exposed.
7. **Failure handling:** If Runtoon generation fails (API error, timeout, safety block), the activity page shows a neutral "Runtoon unavailable for this run" message — no scary error, no stack trace. Failure details are logged server-side only.
8. **Cost tracking:** Every `RuntoonImage` record has `cost_usd` and `generation_time_ms` populated.
9. **Home teaser:** Latest Runtoon thumbnail appears on home page. Tap navigates to activity detail.
10. **Brand subline:** "Your body. Your data. Your voice." visible on `/home` below greeting, above the fold, on every load.
11. **Build green:** `npm run build` passes. All existing tests pass. No regressions.
12. **Idempotency:** Triggering sync twice for the same activity does NOT produce a duplicate Runtoon. Verified by checking `runtoon_image` table count.
13. **Account deletion:** Deleting an athlete cascades to delete all `AthletePhoto` and `RuntoonImage` records AND their R2 objects.
14. **Analytics events:** Log structured events for: `runtoon.generated`, `runtoon.regenerated`, `runtoon.downloaded`, `runtoon.generation_failed` — each with `athlete_id`, `activity_id`, and relevant metadata (cost, latency, attempt_number, failure_reason).

### Required Evidence for Sign-off

- Screenshot: Settings page with 3+ photos uploaded
- Screenshot: Activity detail page showing Runtoon card with preview
- Screenshot: Download dialog / downloaded file
- Screenshot: Home page with Runtoon teaser thumbnail
- Screenshot: Free tier user seeing upgrade CTA instead of Runtoon
- API response sample showing signed URLs (no public URLs)
- Server logs showing successful generation + "Runtoon unavailable" failure state
- DB query showing no duplicate `runtoon_image` rows for the same activity + attempt_number
- Server logs showing `runtoon.generated` and `runtoon.downloaded` analytics events
- Screenshot: Home page showing "Your body. Your data. Your voice." subline below greeting

---

## Mandatory Site Audit Update

After shipping, update `docs/SITE_AUDIT_LIVING.md`:
- Add Runtoon to Delta section
- Add `RuntoonImage` and `AthletePhoto` to Core Data Models
- Add `runtoon_tasks.py` to Celery task inventory
- Add `runtoon.py` router to router count
- Add R2/object storage to Infrastructure table
- Update Frontend inventory with new components
- Note feature flag status

---

## Key File Paths (follow these patterns)

```
# Existing patterns to follow
apps/api/services/adaptation_narrator.py    ← Gemini API client pattern
apps/api/tasks/strava_tasks.py              ← Post-sync hook + Celery task pattern
apps/api/tasks/garmin_webhook_tasks.py      ← Garmin post-sync hook
apps/api/core/tier_utils.py                 ← Entitlement gating (tier_satisfies)
apps/api/routers/plan_export.py             ← Entitlement-gated endpoint pattern
apps/api/models.py                          ← Model definitions + FeatureFlag

# Create new
apps/api/services/runtoon_service.py
apps/api/services/storage_service.py
apps/api/tasks/runtoon_tasks.py
apps/api/routers/runtoon.py
apps/web/components/runtoon/RuntoonCard.tsx

# Modify
apps/api/tasks/strava_tasks.py              ← Add runtoon hook to post_sync_processing_task
apps/api/tasks/garmin_webhook_tasks.py      ← Add runtoon hook after activity creation
apps/api/models.py                          ← Add AthletePhoto + RuntoonImage
apps/web/app/activities/[id]/page.tsx       ← Add Runtoon card
apps/web/app/settings/page.tsx              ← Add photo upload section
apps/web/app/home/page.tsx                  ← Add Runtoon teaser

# Migration
apps/api/alembic/versions/runtoon_001_....py
.github/scripts/ci_alembic_heads_check.py   ← Update EXPECTED_HEADS
```
