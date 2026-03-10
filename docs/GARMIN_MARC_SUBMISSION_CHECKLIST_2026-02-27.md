# Garmin Marc Lussi — Submission Checklist

**Target:** Marc Lussi, Garmin Connect Partner Services  
**Deadline:** Reply due March 3, 2026  
**Goal:** Evidence pack proving brand compliance → production API access approval  
**Risk to minimize:** A single non-compliant or missing screenshot causes a full round-trip cycle.

---

## Pre-Capture Verification

- [x] App is running on **production** (`strideiq.run`) — confirmed, commits `2e4f661` + `b265526` deployed 2026-02-26
- [x] Two Garmin Connect users authorized in evaluation environment:
  - `mbshaf@gmail.com` — `garmin_connected = true` (founder)
  - `wlsrangertug@gmail.com` — `garmin_connected = true` (father)
- [ ] Screenshots captured from production (founder to take manually post-deploy)

---

## Build Evidence

**Frontend build:** `npm run build` — ✅ CLEAN (2026-02-26)
```
✓ Compiled successfully
✓ Generating static pages (195/195)
Zero errors. Zero warnings.
```

**TypeScript typecheck:** `npx tsc --noEmit` — ✅ CLEAN (2026-02-26)
```
Exit code: 0 — zero errors
```

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

**Screenshot:** `screenshots/01-activity-detail-above-fold.png` ← CAPTURE MANUALLY

---

### 2. Activity Splits Table — Footer attribution
**URL:** `/activities/[id]` (scroll to splits section)  
**What to show:** Splits table footer updated to GarminBadge with device model.  
**Common failure:** Footer still reads "Splits are sourced from Garmin Connect."  
**Checklist:**
- [ ] Footer does NOT say "Garmin Connect" as data source
- [ ] Footer shows GarminBadge (GARMIN® logo image) + device model
- [ ] StrideIQ pace computation note is still present ("Pace is computed from split distance/time.")

**Screenshot:** `screenshots/02-splits-footer-attribution.png` ← CAPTURE MANUALLY

---

### 3. Home Page — Last run attribution
**URL:** `/home` (logged in, Garmin activity synced)  
**What to show:** Last run hero with GarminBadge (logo + device model).  
**Common failure:** Attribution says "Garmin Connect" instead of the device model.  
**Checklist:**
- [ ] GarminBadge visible (GARMIN® logo image + device model — not "Garmin Connect")
- [ ] Attribution is above the fold and visually associated with the run data

**Screenshot:** `screenshots/03-home-last-run-attribution.png` ← CAPTURE MANUALLY

---

### 4. Settings — Connected state
**URL:** `/settings` → Garmin integration section, connected athlete  
**What to show:** Official Garmin Connect icon + "Garmin Connect™" heading.  
**Common failure:** Custom icon/button treatment instead of official asset.  
**Checklist:**
- [ ] Official `garmin-connect-icon.png` visible (36×36 rounded icon)
- [ ] Heading reads "Garmin Connect™" (with trademark symbol)
- [ ] No StrideIQ-custom icon replacing the official asset

**Screenshot:** `screenshots/04-settings-connected.png` ← CAPTURE MANUALLY

---

### 5. Settings — Disconnected state (Connect button)
**URL:** `/settings` → Garmin integration section, disconnected athlete  
**What to show:** Official `garmin-connect-badge.png` as the primary CTA visual.  
**Common failure:** Custom-styled blue button with hand-drawn SVG remains.  
**Checklist:**
- [ ] Official Garmin Connect badge image is the CTA visual
- [ ] Button is accessible (keyboard-focusable, aria-label present)
- [ ] No custom `#007CC3` button with hand-drawn SVG

**Screenshot:** `screenshots/05-settings-disconnected-badge.png` ← CAPTURE MANUALLY  
**Note:** To capture disconnected state — disconnect Garmin in settings, then screenshot, then reconnect.

---

### 6. Derived-data attribution (if visible on your activity)
**URL:** `/activities/[id]` — scroll to Coachable Moments section  
**What to show:** "Insights derived in part from Garmin device-sourced data." text below AI insights.  
**Condition:** Only include if visible. If not present on your specific activity, mark deferred below.  
**Checklist:**
- [ ] Attribution text exact: "Insights derived in part from Garmin device-sourced data."
- [ ] Does not imply Garmin endorses or produces the insight

**Screenshot:** `screenshots/06-derived-data-attribution.png` ← CAPTURE IF VISIBLE

---

## Pre-Flight (before sending to Marc)

- [ ] Evaluation key ID obtained from Garmin Developer Portal and pasted into email
- [ ] Garmin Partner Verification Tool run — results pasted into email
- [ ] API Blog subscribed at `https://www.garmin.com/en-US/forms/api-blog-subscribe/` — confirmation pasted into email
- [x] Two Garmin Connect users authorized in eval — `mbshaf@gmail.com` + `wlsrangertug@gmail.com`
- [ ] All 5-6 screenshots captured from production
- [ ] All three sections (Technical, Team, UX) addressed in email — no section left blank
- [ ] Sender address is `michael@strideiq.run`

---

## Deferred (out of scope for this submission)

| Item | Deferred Until |
|------|----------------|
| PDF plan export attribution | After UI approval secured |
| Broad AI provenance plumbing | Phase 3B/3C when coach surfaces are built |

---

## After Marc Replies

- If approved → document production API key receipt in `docs/`, proceed with credential swap on droplet
- If rejected → note the exact screenshot he flags, fix only that surface, resubmit the same day
- If he asks about PDF/AI attribution → share the explicit plan and timeline, do not improvise commitments
