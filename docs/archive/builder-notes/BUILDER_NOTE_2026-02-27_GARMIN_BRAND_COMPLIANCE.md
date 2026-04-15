# Builder Note — Garmin Brand Attribution Compliance

**Date:** 2026-02-27
**Assigned to:** Frontend Builder
**Advisor sign-off required:** Yes — advisor reviews before deploy
**Urgency:** High — blocks Garmin production access approval (reply due by March 3)

---

## Before Your First Tool Call

Read these in order:
1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/GARMIN_CONNECT_DEVELOPER_COMPLIANCE.md`
3. This document

---

## Objective

Update all Garmin attribution in the StrideIQ frontend to comply with the official Garmin API Brand Guidelines (v2, dated 6/30/2025). The current implementation uses informal attribution text and custom SVG icons. Marc Lussi at Garmin Connect Partner Services has requested screenshots showing brand compliance as a gate for production API access.

---

## Brand Guidelines Summary (from official PDF)

### Attribution Format

**Required:** "Garmin [device model]" — e.g., "Garmin Forerunner 165"

- If device model is unknown or unavailable from the API, use "Garmin" as the data source
- Do NOT use "Garmin Connect" in data attribution — "Garmin Connect" is the app name, used only for authentication/connection references
- Do NOT use "Recorded on ... via Garmin Connect" or "Splits are sourced from Garmin Connect"

### Placement Rules

- **Title-level/primary displays:** Attribution must be directly beneath or adjacent to the primary title or heading of the data view, above the fold, visually associated with the data
- **Never** bury attribution in tooltips, footnotes, or expandable containers
- **Secondary screens:** Attribution in all expanded views or subscreens — globally (header) or per entry
- **Exports/PDFs:** Attribution adjacent to data, repeated on each page

### Combined/Derived Data (AI)

When Garmin data is an input to analytics, algorithms, ML, or AI:
- Attribution must list Garmin as a "distinct or contributing data source"
- Must NOT imply Garmin endorsement
- Acceptable text: "Insights derived in part from Garmin device-sourced data"

### Garmin Tag Logo

- The official Garmin tag logo (GARMIN® wordmark) may be used alongside the "[device model]" text
- Do NOT alter, animate, recolor, stretch, or distort the logo
- Do NOT use the logo where Garmin data is not present
- If using the logo, follow the Consumer Brand Style Guide

### Authentication Button

- Use the full app name: "Garmin Connect™" — do not abbreviate or truncate
- Use the official app badge/tile provided in the branding assets kit

---

## Official Assets (already on disk)

Source: `C:\Users\mbsha\OneDrive\Desktop\garmin developer program\branding_assets\GCDP Branding Assets_v2\`

### Copy these to `apps/web/public/`:

| Source File | Destination | Usage |
|-------------|-------------|-------|
| `Garmin Tag/PNG/Garmin Tag-white-high-res.png` | `apps/web/public/garmin-tag-white.png` | Data attribution on dark backgrounds (app UI) |
| `Garmin Tag/PNG/Garmin Tag-black-high-res.png` | `apps/web/public/garmin-tag-black.png` | Data attribution on light backgrounds (PDF export) |
| `Garmin_Connect_app_1024x1024-02.png` | `apps/web/public/garmin-connect-icon.png` | Garmin Connect app icon for Settings connection UI |

---

## Changes Required

### 1. `apps/web/components/integrations/GarminBadge.tsx`

**Current behavior:** Shows custom SVG icon + "Garmin Connect" or "Garmin Connect · Forerunner 165"

**Required behavior:**
- Replace the custom SVG with the official Garmin tag logo image (`/garmin-tag-white.png`)
- Change text format from "Garmin Connect · [Device Name]" to "[device model]" (the logo itself says "GARMIN®", so the text only needs the device model)
- If no device model available, show just the Garmin tag logo (the wordmark IS the attribution)
- Size the logo appropriately — small inline mark, not a hero banner. Approximate height: 12-16px for `sm` size, 16-20px for `md` size.

### 2. `apps/web/components/integrations/GarminConnectButton.tsx`

**Current behavior:** Custom-styled blue button (#007CC3) with hand-drawn SVG icon and text "Connect with Garmin Connect"

**Required behavior (production-review safe default):**
- Replace the custom-styled button treatment with the official Garmin Connect badge asset as the primary CTA visual (`Garmin_connect_badge_digital_RESOURCE_FILE-01.png`).
- Keep an accessible button wrapper (keyboard/focus/aria) around the official badge image.
- Keep the full app name "Garmin Connect" intact (no abbreviation/truncation).
- Do **not** redraw or restyle the icon/wordmark manually for this flow.

### 3. Activity Detail Page — Attribution Placement

**File:** Find where "Recorded on Garmin Forerunner 165 via Garmin Connect" is rendered on the activity detail page.

**Current behavior:** Attribution text appears below "More details" — potentially below the fold or in an expandable container.

**Required behavior:**
- Move the `GarminBadge` component to appear directly beneath the activity title and date, above the fold
- Remove the "Recorded on ... via Garmin Connect" text — the badge now handles attribution
- The badge shows: [Garmin tag logo] + "[device model]" (e.g., "Forerunner 165")

### 4. Activity Splits Table — Footer Attribution

**File:** Find where "Splits are sourced from Garmin Connect. Pace is computed from split distance/time." is rendered.

**Current behavior:** Footer text says "Splits are sourced from Garmin Connect."

**Required behavior:**
- Change to: "Garmin [device model]" — or use the GarminBadge component inline
- Keep the "Pace is computed from split distance/time" note (that's StrideIQ's own disclosure, not Garmin attribution)

### 5. Home Page — Last Run Attribution

**File:** Find where "Garmin Forerunner 165" appears in the last run metrics line on the home page.

**Current behavior:** Shows "Garmin Forerunner 165" inline with run metrics. This is close to correct.

**Required behavior:**
- Verify it says "Garmin [device model]" (it appears to already)
- Optionally add the Garmin tag logo inline before the device text
- Ensure this is above the fold and visually associated with the data (it appears to be)

### 6. Combined/Derived Data — AI Attribution

**Where:** Any surface where AI-generated insights incorporate Garmin-sourced data (morning voice, coach briefing, progress analysis).

**Scope for this sprint:**
- **Do not** build broad AI-wide attribution plumbing in this pass.
- Apply derived-data attribution only where Garmin provenance is already explicit and cheap to verify in existing UI state.
- Minimum acceptable for this submission: one visible, truthful attribution on a Garmin-backed insight surface using:
  - "Insights derived in part from Garmin device-sourced data"
- If accurate conditional detection is non-trivial, document as follow-up and do not block the core brand/UI fixes.

**Why this scope:**
- Marc's immediate review gate is primarily app UI trademark/attribution compliance.
- Over-engineering provenance logic now risks timeline and does not increase approval odds proportionally.

### 7. PDF Plan Export — Conditional Attribution

**Status:** **Deferred (out of scope for this review cycle)**

- Do not change `apps/api/templates/plan_pdf.html` or `apps/api/services/plan_pdf.py` in this brand-compliance sprint.
- Marc's current gate is app UI evidence; PDF attribution can be handled in a dedicated follow-up once UI approval is secured.
- Track this as a backlog compliance task with explicit provenance rules before implementation.

---

## What NOT To Do

- Do NOT remove the `GarminConnection.tsx` component or change the connect/disconnect flow logic
- Do NOT modify the OAuth flow or webhook handling
- Do NOT change backend Garmin code in this sprint (PDF/back-end attribution is deferred)
- Do NOT use the Garmin logo or attribution on screens where Garmin data is NOT displayed
- Do NOT imply Garmin endorses StrideIQ anywhere

---

## Testing

**Visual verification (required):**
- Screenshot each surface showing Garmin attribution after changes
- Compare against the examples in Marc's email (the Activity API and Health API mockups)

**Automated tests:**
- `npm run build` must succeed (zero errors)
- TypeScript typecheck clean
- Existing frontend tests pass

**No backend tests needed** — this is a frontend-only change.

---

## Evidence Required

1. Screenshot: Activity detail page with Garmin tag logo + "[device model]" above the fold
2. Screenshot: Activity splits table with updated attribution footer
3. Screenshot: Home page last run with Garmin attribution
4. Screenshot: Settings page with Garmin Connect connection UI (connected state)
5. Screenshot: Settings page with Garmin Connect button (disconnected state)
6. Screenshot: one Garmin-backed derived insight surface with "Insights derived in part from Garmin device-sourced data" attribution (if implemented in-scope)
7. Build output: success
8. TypeScript: clean
9. Production: all containers healthy, key pages return 200

---

## After This Ships

The founder will:
1. Run the Garmin Partner Verification Tool
2. Capture final production screenshots
3. Reply to Marc Lussi with the evidence pack

These screenshots are the gate for Garmin production API access. Getting them right on the first submission avoids a round-trip rejection cycle.
