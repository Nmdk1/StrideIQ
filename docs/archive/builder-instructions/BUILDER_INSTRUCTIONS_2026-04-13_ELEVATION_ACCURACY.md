# Builder Instructions: Improve Elevation Accuracy

**Date:** April 13, 2026
**Priority:** P1 — athletes go to Strava because our elevation is noisier / less accurate
**Symptom:** Elevation profiles are noisy compared to Strava's clean rendering
**Assigned to:** Whichever builder finishes their P0 task first

---

## Problem

Athletes compare StrideIQ's elevation data to Strava's and find Strava's clearer and more accurate. Strava uses server-side elevation correction with a global DEM dataset. We likely display raw GPS altitude from the device, which is inherently noisy.

## Investigation needed first

Before building, answer these questions:

1. **What elevation data are we storing?** Check `ActivityStream` — is it raw GPS altitude? Barometric altitude? Strava-corrected?

2. **For Strava-sourced activities:** Does the Strava streams API return corrected elevation? (Answer: yes — their `altitude` stream uses corrected data when available). If so, we should already have good elevation for Strava activities. Verify by comparing a Strava-synced activity's stored elevation to what Strava shows.

3. **For Garmin-sourced activities:** What altitude data comes through the webhook detail samples? Garmin devices with barometric altimeters are usually accurate. Check if we're storing the barometric or GPS altitude.

4. **Rendering:** Check `ElevationProfile` component and `RunShapeCanvas` — are we applying any smoothing? Strava smooths their elevation profile for visual clarity.

## Likely fixes (in priority order)

### Fix A: Use Strava's corrected elevation when available
- For activities synced from Strava, the `altitude` stream should already be corrected
- Verify this is what we store. If we're re-deriving elevation from GPS coords, stop — use Strava's value.

### Fix B: Apply smoothing to elevation profile rendering
- A simple moving average (window of 5-10 points) on the elevation data before rendering removes GPS noise
- This is a frontend/rendering fix, not a data fix
- Apply in `ElevationProfile` component and in `RunShapeCanvas` grade overlay

### Fix C: Server-side DEM correction for Garmin activities
- Use a public DEM dataset (SRTM 30m, Mapbox Terrain) to correct raw GPS altitude
- This is a real project — only do if Fix A and Fix B don't close the gap
- Would require: download DEM tiles, lookup lat/lng → corrected altitude, store corrected stream

## Key files to investigate

| File | What to check |
|------|---------------|
| `tasks/strava_tasks.py` | What streams are requested from Strava API |
| `services/strava_service.py` | `get_activity_streams()` — which stream types are fetched |
| `tasks/garmin_webhook_tasks.py` | What altitude data comes from Garmin detail samples |
| `services/garmin_adapter.py` | `adapt_activity_detail_samples` — altitude field mapping |
| `components/activities/map/ElevationProfile.tsx` | Current rendering — any smoothing? |
| `components/activities/rsi/RunShapeCanvas.tsx` | Grade/elevation overlay rendering |

## Evidence required

- [ ] Document what elevation data source is currently used (per provider)
- [ ] If Strava-corrected elevation is available but not used, use it
- [ ] If smoothing is missing, add it with before/after screenshots
- [ ] CI green
- [ ] Deploy and verify visually against Strava for same activity
