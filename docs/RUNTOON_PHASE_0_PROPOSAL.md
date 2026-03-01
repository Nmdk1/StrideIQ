# Runtoon — Phase 0 Feasibility Proposal

**Status:** PROPOSED (March 1, 2026)
**Author:** Advisor (Opus 4.6)
**Decision Required From:** Founder + Codex

---

## 1. What Runtoon Is

A personalized, share-ready image generated after every run. It combines:

- **Real stats** (distance, pace, time, HR, elevation) — the data card runners already want
- **A flattering, humorous caricature** of the athlete — based on their uploaded photos, placed in a scene that reflects actual run conditions (time of day, weather, terrain, effort level)
- **A coaching-informed caption** — the insight that tells the story of this specific run, drawn from StrideIQ's intelligence pipeline

The result is something no competitor can produce: Strava has the stats but no intelligence. NRC has the branding but no personalization. StrideIQ has all three.

Every shared image carries a subtle `strideiq.run` watermark. Every share is a free branded impression in the exact communities where the target user lives.

---

## 2. Research Findings — Nano Banana 2 (Gemini 3.1 Flash Image)

### 2.1 Reference Image Input

| Parameter | Value |
|---|---|
| Max reference images per prompt | **Up to 14** |
| Supported formats | PNG, JPEG, WebP, HEIC, HEIF |
| Max file size (inline/upload) | **7 MB per image** |
| Max file size (Cloud Storage) | 30 MB per image |
| Character consistency | Up to **5 characters** maintained across a workflow |
| Object fidelity | Up to **14 objects** maintained |

**Runtoon impact:** 3 athlete reference photos is well within the 14-image limit. We pass all 3 on every generation call to maximize likeness consistency. The model handles this natively — the "Pet Passport" demo (Google's own example) uses the exact same pattern: take a photo, place the subject in different scenes, maintain appearance.

**Known limitation (from model card):** "Character consistency is not always perfect between input images and generated output image." This is the primary quality risk and must be validated in Phase 0.

### 2.2 Text Rendering

| Capability | Assessment |
|---|---|
| Text rendering accuracy | **~90%** (Google's stated figure) |
| Multilingual support | Yes — localization and translation within images |
| Small text quality | Poor — "often blurry in 1K model, long paragraphs, page length" (model card limitation) |
| Large/bold text quality | Strong — marketing mockups, greeting cards, infographics |

**Runtoon impact:** We need 5-7 large stat values (distance, pace, time, HR) and a 1-2 line caption. This is the model's sweet spot — large, bold, limited text. Avoid small print. Keep stats to key numbers only. If text accuracy is unreliable, fallback plan is to render stats as a text overlay in the app (post-generation compositing) and use the AI only for the caricature + scene + caption.

### 2.3 Output Sizes and Aspect Ratios

| Aspect Ratio | Use Case | Supported |
|---|---|---|
| **1:1** (1080x1080) | Instagram feed, universal social | Yes |
| **9:16** (1080x1920) | Instagram Stories, TikTok | Yes |
| **4:5** (1080x1350) | Instagram feed (tall) | Yes |
| **16:9** (1920x1080) | Twitter/X, desktop wallpaper | Yes |
| **3:4**, **4:3**, **2:3**, **3:2** | Various social | Yes |

Resolutions: **512px, 1K, 2K, 4K**. For social sharing, 1K (1080px) is the standard.

**Runtoon impact:** Perfect coverage. Generate at 1K for cost efficiency. Offer download in two formats: 1:1 (feed) and 9:16 (Stories). Two generations per Runtoon, or one generation + server-side crop if the scene composition permits.

### 2.4 Style Control and Consistency

| Feature | Detail |
|---|---|
| Thinking levels | **Minimal** (default, fast, cheaper) vs **High/Dynamic** (better quality, more reasoning, higher latency) |
| Instruction following | "Adheres much more strictly to complex, multi-layered developer prompts" |
| Style transfer | Yes — texture, color, aesthetic shifts from reference images |
| Regeneration | Same prompt can produce varied outputs; model is non-deterministic |

**Runtoon impact:** Use **High** thinking for initial generation (better quality for a share-worthy image). Use **Minimal** only if High proves too slow (>10s) or too costly. The non-deterministic nature is a feature for Runtoon — the athlete can regenerate to get a version they prefer.

### 2.5 Safety and Moderation

| Setting | Options |
|---|---|
| Person generation | **Don't allow** / **Allow (Adults only)** / **Allow (All ages)** |
| Safety threshold | **Block few** / **Block some** (default) / **Block most** |
| Real person likeness | Model "designed to limit chances of replicating existing content" |
| Reduced block rates | Preview version has "significantly reduced filter block rates" vs experimental |

**Runtoon impact — CRITICAL RISK:** The athlete is generating a caricature of **themselves** from **their own photos**. This is not deepfake territory — it's self-expression. However, safety filters may still block stylized renderings of real people's faces. This is the **#1 technical risk** and must be tested in Phase 0 before any build work begins.

**Content policy — PG-safe, always:** The style anchor prompt must enforce: fully clothed runner in appropriate athletic gear, no nudity, no suggestive content, no violence. The safety filter threshold should be set to **Block some** (default) or higher. All generated images must be appropriate for public social sharing. This is a hard constraint in the prompt, not a hope.

**Mitigation:** If face-based caricature is blocked:
- Option A: Generate a stylized runner figure that captures body type, gear, and running style from the photos without rendering a recognizable face (silhouette/comic style)
- Option B: Use Vertex AI (enterprise tier) where person generation settings are configurable (`allow_adults_only`)
- Option C: Generate the scene/background/stats with AI, composite the athlete's actual photo into the scene (hybrid approach — less magical but guaranteed to work)

### 2.6 Pricing

| Resolution | Cost per image (Google AI Studio) | Monthly cost (1 run/day) |
|---|---|---|
| 512px | ~$0.045 | ~$1.35 |
| **1K (1080px)** | **~$0.067** | **~$2.01** |
| 2K | ~$0.10 | ~$3.00 |
| 4K | ~$0.151 | ~$4.53 |

**Runtoon cost model at 1K resolution:**

| Scenario | Cost/image | Regenerations | Total cost/Runtoon | Monthly (30 runs) |
|---|---|---|---|---|
| First generation is a keeper | $0.067 | 0 | $0.067 | $2.01 |
| 1 regeneration needed | $0.067 | 1 | $0.134 | $4.02 |
| 2 regenerations (max allowed) | $0.067 | 2 | $0.201 | $6.03 |
| **Blended estimate** (1.3 avg attempts) | $0.067 | 0.3 | **$0.087** | **$2.61** |

At $9.99/mo standalone or included in Guided ($15/mo), gross margin is 74-83% even with regenerations.

**Phase 0 cost:** 15 test images × $0.067 = **$1.01**. Negligible.

### 2.7 Rate Limits

| Tier | RPM | Notes |
|---|---|---|
| Tier 1 (paid billing) | 150-300 | Sufficient for early scale |
| Tier 2 ($250+ spend) | 1,000+ | Scales with user growth |
| Tier 3 ($1,000+ spend) | 4,000+ | Production at scale |

**Runtoon impact:** At 100 daily active runners generating 1 image each, that's ~100 requests/day. Even at Tier 1 (150 RPM), we are nowhere near the limit. Rate limiting is not a concern until thousands of concurrent users.

### 2.8 Latency

| Setting | Expected latency |
|---|---|
| Minimal thinking | **4-6 seconds** |
| High/Dynamic thinking | **8-15 seconds** (estimated) |

**Runtoon impact:** Generation is fully async via Celery. The athlete never waits synchronously. The Runtoon appears on their activity page when ready (typically within 10-15 seconds of sync completion). Push notification or polling can alert them.

### 2.9 Licensing and Commercial Use

| Term | Detail |
|---|---|
| Commercial use | **Permitted** under paid API plans |
| Ownership | Google does **not** claim ownership of generated images |
| Exclusivity | Google reserves right to generate "similar content for others" (standard clause) |
| SynthID watermark | Invisible digital watermark embedded automatically; does not prevent use |
| C2PA Content Credentials | Provenance metadata embedded for AI content identification |
| User responsibility | Developer responsible for ensuring generated content doesn't violate others' rights |

**Runtoon impact:** Clean commercial use. The athlete generates their own likeness, shares it voluntarily. SynthID is invisible and doesn't affect the image. No licensing blockers.

### 2.10 Existing StrideIQ Integration

| Component | Status |
|---|---|
| Gemini API key | **Already configured** (`GOOGLE_AI_API_KEY` env var) |
| Python client | **Already imported** (`google.genai.Client`) |
| Model usage | Currently `gemini-2.5-flash` for text; add `gemini-3.1-flash-image-preview` for images |
| Celery task framework | **Already built** (6+ task modules) |
| Activity data pipeline | **Already built** (`Activity`, `ActivityStream`, `DailyCheckin`, `GarminDay`, `InsightLog`) |
| Entitlement gating | **Already built** (`tier_utils.py`, `pace_access.py` patterns) |
| Feature flags | **Already built** (`FeatureFlag` table in `models.py`) |

The only new infrastructure dependency is **object storage** for athlete photos and generated images (Cloudflare R2 recommended). **All buckets are private. All access is via signed URLs with short TTL. No public URLs, ever.**

---

## 3. Athlete Photo Requirements

**3 photos required at setup:**

| Photo | Purpose | Guidance |
|---|---|---|
| **1. Face** | Facial features for caricature likeness | Clear, front-facing, good lighting, no sunglasses |
| **2. Running** | Body proportions, typical gear, running posture | Action shot, shows full body in motion |
| **3. Full body casual** | Different angle, build reference | Standing, different context than the running shot |
| **4+ (optional)** | Improved likeness accuracy | Additional angles, different lighting, different gear — more photos = better results |

**Why 3 minimum:** For caricature style (not photorealistic), the model needs enough reference to capture distinguishing features (build, hair, skin tone, facial structure, typical gear) but doesn't need the 10-20 images that photorealistic avatar training requires. 3 is the minimum for reliable character features across varied scenes. The model accepts up to 14 — athletes can upload additional photos beyond 3 to improve likeness consistency. More photos = better results, but 3 is the required floor.

**Storage — ALL ATHLETE DATA PRIVATE BY DEFAULT (non-negotiable, platform-wide):**

This is not a Runtoon-specific rule. It is a **platform-level invariant** that applies to every piece of athlete data in StrideIQ — profile, photos, activities, check-ins, insights, Runtoons, everything. Nothing is ever publicly accessible by default.

- All object storage buckets are **private** (no public access, no public URLs).
- All access is via **signed URLs with short TTL** (15 minutes max) — generated server-side only when the authenticated athlete requests their own data.
- Athlete photo URLs, activity data, and generated Runtoon URLs are **never exposed** as public endpoints, in unauthenticated API responses, or in client-side state beyond the authenticated session.
- The athlete explicitly chooses what to share by downloading their Runtoon and posting it themselves. StrideIQ never publishes athlete data on their behalf.
- Athlete can add or replace photos at any time in Settings.

---

## 4. Runtoon Image Composition

```
┌──────────────────────────────────────┐
│                                      │
│   [Caricature scene: the athlete     │
│    running in conditions that        │
│    match the actual run — time of    │
│    day, weather, terrain, effort     │
│    level, gear they typically wear]  │
│                                      │
│                                      │
│   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│                                      │
│   13.0 mi  •  7:28/mi  •  1:37:00   │
│   153 bpm  •  Feb 28, 2026          │
│                                      │
│   "Taper discipline — you held       │
│    back when your legs wanted more,  │
│    and 14 days out, that's the       │
│    smartest thing you did all week." │
│                                      │
│   ── strideiq.run ──                 │
│                                      │
└──────────────────────────────────────┘
```

**Four layers in the prompt:**

| Layer | Source | Controls |
|---|---|---|
| 1. Style anchor | Hardcoded brand constant | Caricature style, bold comic palette, runner as hero, flattering, PG-safe (fully clothed, no nudity) |
| 2. Athlete reference | 3 uploaded photos | Physical likeness, gear, build |
| 3. Run context | `Activity` + `ActivityStream` | Distance, pace, HR, time of day, weather, terrain, effort |
| 4. Coaching insight | `InsightLog` / `morning_voice` | The story of this run — what it meant in the training arc |

**Text in image:** Stats line + coaching caption + watermark. All large, bold text — the model's strong suit. If text rendering is unreliable in testing, fall back to server-side compositing (generate scene only, overlay text programmatically).

---

## 5. UX Flow

```
Sync completes → Celery task fires → image generated (4-10s)
                                            ↓
Activity detail page: "Your Runtoon" card appears
                                            ↓
Athlete taps → preview modal:
    [Full image preview]
    [Regenerate] (up to 2 more attempts)
    [Download 1:1]  [Download 9:16]
                                            ↓
Athlete downloads → posts wherever they want
```

**No social platform integrations.** The athlete downloads in the right format and size, and posts to Instagram, Strava, X, Reddit, or anywhere else. They have full control. We stay out of the integration business.

**Home page teaser:** After the LastRunHero, show a small Runtoon thumbnail (cached URL from `RuntoonImage` table). Tap → navigate to activity detail. Never trigger generation from the home page.

---

## 6. Phase 0 — Feasibility Test

### 6.1 What We Test

Generate 15 Runtoons from real activities in the founder's history, covering varied run types:

| # | Run Type | What It Tests |
|---|---|---|
| 1 | Easy recovery 4mi | Low-key scene, relaxed posture |
| 2 | Long run 15mi | Endurance scene, fatigue |
| 3 | Tempo 6mi | Intensity, focused effort |
| 4 | Early morning 5am dark | Time-of-day variation, lighting |
| 5 | Hot afternoon summer | Weather variation |
| 6 | Rainy run | Weather variation, mood |
| 7 | PR day (race) | Celebration, achievement |
| 8 | Bad day / cut short | Humor in struggle |
| 9 | Hilly trail run | Terrain variation |
| 10 | Taper run (race approaching) | Restraint, discipline theme |
| 11 | First run back after rest | Return, freshness theme |
| 12 | Track workout (intervals) | Specific workout type |
| 13 | Marathon pace long run | Race-specific preparation |
| 14 | Recovery after race | Post-race recovery |
| 15 | Casual social run | Light, fun, easy vibe |

### 6.2 Test Protocol

1. **Pull 15 real activities** from the founder's `Activity` table with varied characteristics.
2. **Use the founder's actual photos** (3 photos) as reference images.
3. **Assemble a 4-layer prompt** for each: style anchor + athlete reference + activity data + coaching insight from `InsightLog` (or fabricated if no insight exists for that activity).
4. **Generate via Gemini API** using `gemini-3.1-flash-image-preview` with High thinking level.
5. **Generate at 1K resolution**, 1:1 aspect ratio.
6. **For 3 of the 15**, also test regeneration: generate 3 versions of the same run to evaluate variation quality.
7. **For 2 of the 15**, test text rendering: include stats baked into the image vs. a version without stats (to evaluate if text overlay should be done by the model or composited server-side).

### 6.3 Evaluation Criteria (per image)

| Criterion | Score | Definition |
|---|---|---|
| **Likeness** | 1-5 | Does the caricature recognizably represent the founder? (3+ = pass) |
| **Scene accuracy** | 1-5 | Does the scene reflect the actual run conditions? (3+ = pass) |
| **Humor/charm** | 1-5 | Is it flattering and amusing? Would you smile? (3+ = pass) |
| **Share-worthiness** | Binary | Would you actually post this? (Yes/No) |
| **Text legibility** | 1-5 | Are the stats and caption readable? (3+ = pass, if applicable) |
| **Safety filter** | Binary | Did the request succeed without being blocked? (Yes/No) |

### 6.4 Go/No-Go Rubric

| Metric | Go Threshold | No-Go |
|---|---|---|
| **Share-worthy rate** | **≥10 of 15 (67%)** would be posted | <10 of 15 |
| **Safety filter pass rate** | **15 of 15 (100%)** no blocks | Any block = investigate mitigation before proceeding |
| **Likeness consistency** | Average likeness score **≥3.5/5** across all 15 | Below 3.0 = caricature approach needs rethinking |
| **Regeneration quality** | At least **2 of 3 regenerations** per run are acceptable | All 3 regenerations are bad = prompt architecture problem |
| **Text rendering** | Stats readable in **≥12 of 15 (80%)** when baked in | Below 60% = fall back to server-side text compositing |
| **Cost per accepted image** | **≤$0.15** (including regenerations) | Above $0.25 = economics don't work at scale |
| **Generation latency** | **≤15 seconds** average | Above 30s = UX concern even with async |

**Decision rules:**
- **All 7 thresholds met → GO.** Write build spec behind feature flag and ship.
- **5-6 thresholds met → CONDITIONAL GO.** Identify mitigation for failed thresholds, retest those specifically, then decide.
- **≤4 thresholds met → NO-GO.** Shelve or fundamentally redesign the approach.

### 6.5 Phase 0 Budget

| Item | Cost |
|---|---|
| 15 initial generations × $0.067 | $1.01 |
| 9 regeneration tests × $0.067 | $0.60 |
| 4 text rendering variants × $0.067 | $0.27 |
| Buffer for prompt iteration | ~$2.00 |
| **Total Phase 0 budget** | **~$4.00** |

---

## 7. What Phase 0 Does NOT Test

These are deferred to the build spec if Phase 0 passes:

- Object storage setup (R2)
- Celery task integration
- Database model (`RuntoonImage`)
- Frontend UI (preview, regenerate, download)
- Entitlement gating
- Cost monitoring
- Production scaling

Phase 0 is strictly: **can the model produce share-worthy images from our data, consistently, at acceptable cost?**

---

## 8. Monetization Recommendation (Revised)

| Tier | Runtoon Access | Rationale |
|---|---|---|
| **Free** | 1 Runtoon on first run only | Onboarding delight + conversion hook |
| **One-time ($5)** | No Runtoon | One-time doesn't justify ongoing generation cost |
| **Guided ($15/mo)** | Unlimited Runtoons (1 per activity, 2 regenerations) | Makes Guided dramatically more attractive |
| **Premium ($25/mo)** | Unlimited Runtoons + 4K resolution option | Premium perk |

**No standalone $9.99/mo tier.** Runtoon should be a reason to subscribe to StrideIQ, not a substitute for it. Bundling it into Guided increases perceived tier value and drives upgrades rather than cannibalization.

---

## 9. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Safety filters block caricatures of real people | Medium | Critical | Phase 0 tests this first. Fallback: silhouette style or hybrid composite |
| Likeness inconsistency across different runs | Medium | High | 3 reference photos per call. If insufficient, add athlete-specific style prompt tuning |
| Text rendering unreliable for stats | Medium | Low | Fall back to server-side compositing (generate scene only, overlay text programmatically) |
| Nano Banana 2 is in "preview" — stability risk | Low | Medium | Silent failure in Celery task. Missing Runtoon is not user-facing. Monitor API health. |
| Competitive response (Strava builds same thing) | Low-Medium | Medium | StrideIQ's moat is the coaching insight layer. Competitors can copy the image but not the intelligence. |
| Cost exceeds projections at scale | Low | Medium | Daily cap per athlete. Monitor `cost_usd` in `RuntoonImage`. Rate limit regenerations. |
| Generated image contains inappropriate content | Low | High | PG-safe enforced in style anchor prompt + safety filter at "Block some" or higher. Athlete previews before downloading — nothing posts automatically. |
| Any athlete data exposed publicly | None (by design) | Critical | Platform-wide invariant: all athlete data (profile, photos, activities, check-ins, insights, Runtoons) is private by default. Private buckets, signed URLs with short TTL, authenticated access only. The athlete chooses what to share by downloading and posting themselves. |
| Object storage is new infrastructure dependency | Low | Low | Cloudflare R2 is simple, cheap, and has a generous free tier (10 GB/mo free) |

---

## 10. Execution Timeline (If Phase 0 Passes)

| Phase | Duration | Deliverable |
|---|---|---|
| **Phase 0** (now) | 1-2 days | 15 test images, Go/No-Go decision |
| **Phase 1** (MVP) | 1-2 weeks | Service + task + model + migration + basic display on activity page. Feature-flagged. |
| **Phase 2** (Ship) | 1-2 weeks | Preview/regenerate/download UX, home page teaser, entitlement gating, watermark |
| **Phase 3** (Deepen) | Ongoing | Avatar evolution, race-arc narrative, N=1 visual callouts |

---

## 11. Next Step

**Founder provides 3 photos.** I pull 15 activities from the database, assemble prompts, generate images via the Gemini API, and evaluate against the Go/No-Go rubric. Total cost: ~$4. Total time: 1-2 sessions.

If Go: I write the builder note with full technical spec.
If No-Go: We document what failed and either iterate on prompt architecture or shelve.

---

## Appendix: Model String and API Pattern

```python
from google import genai
from google.genai import types as genai_types

client = genai.Client(api_key=os.getenv("GOOGLE_AI_API_KEY"))

response = client.models.generate_content(
    model="gemini-3.1-flash-image-preview",
    contents=[
        genai_types.Content(
            parts=[
                genai_types.Part.from_image(athlete_photo_1),
                genai_types.Part.from_image(athlete_photo_2),
                genai_types.Part.from_image(athlete_photo_3),
                genai_types.Part.from_text(runtoon_prompt),
            ]
        )
    ],
    config=genai_types.GenerateContentConfig(
        response_modalities=["Text", "Image"],
        temperature=0.8,
    ),
)
```

Follows the same `genai.Client` pattern used in `adaptation_narrator.py`, `ai_coach.py`, `intelligence_tasks.py`, `progress.py`, and `home.py`.
