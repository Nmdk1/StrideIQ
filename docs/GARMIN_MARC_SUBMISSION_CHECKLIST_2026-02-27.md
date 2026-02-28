# Garmin Marc Lussi — Submission Checklist

**Target:** Marc Lussi, Garmin Connect Partner Services  
**Deadline:** Reply due March 3, 2026  
**Goal:** Evidence pack proving brand compliance → production API access approval  
**Risk to minimize:** A single non-compliant or missing screenshot causes a full round-trip cycle.

---

## Pre-Capture Verification (do this before taking any screenshots)

- [ ] App is running on **production** (`strideiq.run`), not localhost — Marc needs live URLs, not staged captures
- [ ] Logged in as an athlete with a **connected Garmin account and at least one synced activity** (so device model is present in every shot)
- [ ] Note the exact device model that will appear — e.g., "Forerunner 165" — keep it consistent across all shots

---

## Capture Order and Pass/Fail Criteria

Capture in this order. Each item has the specific failure mode that causes rejection.

### 1. Activity Detail — Above-the-fold attribution
**URL:** `/activities/[id]`  
**What to show:** The Garmin tag logo (GARMIN® wordmark image, not text) and device model directly beneath the activity title and date — **visible without scrolling**.  
**Common failure:** Attribution buried below "More details" or in a collapsible section.  
**Checklist:**
- [ ] Garmin tag logo visible (white version on dark background)
- [ ] Device model text adjacent: "Forerunner 165" (not "Garmin Connect · Forerunner 165")
- [ ] Attribution is above the fold — nothing needs to be clicked or expanded to see it
- [ ] No text reading "Recorded on ... via Garmin Connect"

---

### 2. Activity Splits Table — Footer attribution
**URL:** `/activities/[id]` (scroll to splits section)  
**What to show:** Splits table footer updated to "Garmin [device model]" (or inline GarminBadge).  
**Common failure:** Footer still reads "Splits are sourced from Garmin Connect."  
**Checklist:**
- [ ] Footer does NOT say "Garmin Connect" as data source
- [ ] Footer says "Garmin Forerunner 165" (or device model shown) OR uses the GarminBadge component
- [ ] StrideIQ pace computation note is still present ("Pace is computed from split distance/time") — that's our own disclosure, keep it

---

### 3. Home Page — Last run attribution
**URL:** `/` (logged in, Garmin activity synced)  
**What to show:** Last run metrics row with "Garmin [device model]" text visible.  
**Common failure:** Attribution says "Garmin Connect" instead of the device model.  
**Checklist:**
- [ ] Text reads "Garmin Forerunner 165" (or device model) — not "Garmin Connect"
- [ ] Attribution is above the fold and visually associated with the run data
- [ ] Optional: Garmin tag logo inline before device text (include if implemented)

---

### 4. Settings — Connected state (Garmin Connect button, connected)
**URL:** `/settings` → Garmin integration section, connected athlete  
**What to show:** Connected state UI with official Garmin Connect branding treatment and full app name "Garmin Connect".  
**Common failure:** Custom icon/button treatment instead of official asset; truncated or altered app name.  
**Checklist:**
- [ ] Official Garmin Connect branding asset is visible (badge/tile treatment, not a hand-drawn/custom icon)
- [ ] Full app name "Garmin Connect" is present and not abbreviated/truncated
- [ ] No StrideIQ-custom icon replacing the official asset

---

### 5. Settings — Disconnected state (Connect button)
**URL:** `/settings` → Garmin integration section, disconnected athlete  
**What to show:** The official Garmin Connect badge as the primary CTA visual (not a custom blue button).  
**Common failure:** Custom-styled button with hand-drawn SVG remains — Marc specifically looks for the official badge asset here.  
**Checklist:**
- [ ] Official Garmin Connect badge image used as the CTA visual
- [ ] Button is accessible (keyboard-focusable, aria label present)
- [ ] "Garmin Connect" full name readable — not truncated
- [ ] No custom `#007CC3` button with hand-drawn SVG

---

### 6. Derived-data attribution (if implemented in-scope)
**URL:** Any AI insight surface backed by Garmin data (morning voice, coach briefing, progress analysis)  
**What to show:** Attribution text "Insights derived in part from Garmin device-sourced data" visible on the surface.  
**Condition:** Only capture and include this if it was implemented. If skipped (non-trivial detection path), omit from pack and document as follow-up in the email.  
**Checklist:**
- [ ] Attribution text is exact: "Insights derived in part from Garmin device-sourced data"
- [ ] Text does NOT imply Garmin endorses or produces the insight
- [ ] Only appears on surfaces where Garmin data was actually an input

---

### 7. Build evidence (attach to email)
- [ ] `npm run build` output — last line confirms success, zero errors
- [ ] TypeScript typecheck output — zero errors
- [ ] Optional internal ops proof (not for Marc): production containers healthy

---

## What to Write in the Email to Marc

Keep it short. Marc needs to verify compliance, not read a story. The reply must address **all three sections** of Marc's checklist — not just brand screenshots.

**Subject:** RE: StrideIQ — Production Access Verification

**Body structure:**

### Section 1: Technical Review

1. **Evaluation key:** [PASTE EVALUATION KEY ID HERE]
   **Requesting production access for:** Activity API, Health API, Women's Health API (feature-gated, not yet exposed publicly).
2. **APIs in use (read-only):**
   - Activity API — activity summaries and streams
   - Activity Details API — GPS, HR, cadence, velocity samples
   - Health API — sleep, HRV, stress, dailies, user metrics
   - Training/Courses API — not in our integration scope. StrideIQ does not write data to Garmin Connect.
3. **Authorization:** Two Garmin Connect users are authorized in our evaluation environment.
4. **User Deregistration:** Endpoint enabled at `/v1/garmin/webhook/deregistrations`. Returns HTTP 200 and processes asynchronously.
5. **User Permissions:** Endpoint enabled at `/v1/garmin/webhook/permissions`. Returns HTTP 200 and processes asynchronously.
6. **PING/PUSH:** All webhook endpoints receive Garmin push notifications and return HTTP 200 within seconds. Processing is asynchronous via task queue. Primary ingestion is webhook PING/PUSH; no scheduled polling pipeline is used.
7. **Payload handling:** Endpoints accept payloads up to 100MB. HTTP 200 is returned immediately; data is processed asynchronously.
8. **Partner Verification Tool:** [PASTE RESULTS HERE — run before sending]
9. **Training/Courses API:** Not applicable — StrideIQ does not transfer workouts or courses to Garmin Connect.

### Section 2: Team Members and Account Setup

1. **API Blog:** Subscribed. [SUBSCRIBE BEFORE SENDING]
2. **Authorized account:** `michael@strideiq.run` (sole operator, company domain). No additional team members.
3. **No third-party integrators.** No NDA required.

### Section 3: UX and Brand Compliance

1. "We've updated all Garmin attribution in StrideIQ to comply with the Garmin API Brand Guidelines v2 (6/30/2025)."
2. Bulleted list of what was changed (match checklist items 1-6 above, one line each)
3. "Screenshots are attached in order below." — attach in the same order as this checklist
4. One sentence for PDF deferred: "PDF export attribution is out of scope for this UI compliance review and will be addressed as a follow-up."
5. If item 6 was deferred: "Derived-data AI surface attribution is documented as a follow-up compliance task; the primary UI trademark/attribution surfaces are all compliant."

### Do NOT include:
- Apologies for the prior state
- Technical implementation details Marc didn't ask for
- Unsolicited feature descriptions

---

## Before Sending — Pre-Flight

- [ ] API Blog subscribed
- [ ] Partner Verification Tool run and results captured
- [ ] All screenshots captured from **production** (not localhost)
- [ ] Sections 1, 2, and 3 all addressed in the email — no section left blank

---

## After Marc Replies

- If approved → document production API key receipt in `docs/`, proceed with credential swap on droplet
- If rejected → note the exact screenshot he flags, fix only that surface, resubmit the same day
- If he asks about PDF/AI attribution → share the explicit plan and timeline, do not improvise commitments

---

## Deferred (out of scope for this submission)

| Item | Deferred Until |
|------|---------------|
| PDF plan export attribution | After UI approval secured |
| Broad AI provenance plumbing | Phase 3B/3C work when coach surfaces are built |
