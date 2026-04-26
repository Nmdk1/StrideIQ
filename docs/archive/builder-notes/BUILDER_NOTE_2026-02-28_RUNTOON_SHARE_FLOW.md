# Builder Note: Runtoon "Share Your Run" Flow

**Date:** 2026-02-28  
**Assigned to:** Full-Stack Builder  
**Advisor sign-off required:** Yes  
**Urgency:** High — this is the feature's UX pivot from "hidden page widget" to "post-run sharing moment"

---

## Before Your First Tool Call

Read in order:
1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/PRODUCT_MANIFESTO.md`
3. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md`
4. `docs/specs/RUNTOON_SHARE_FLOW_SPEC.md` — **the full spec, all decisions finalized**
5. `docs/AGENT_WORKFLOW.md`
6. This builder note

---

## Objective

When a run syncs, a mobile bottom sheet prompts "Share Your Run" —
tapping it generates the Runtoon on-demand, presents it full-screen,
and lets the athlete share via native OS share sheet in two taps total.
No auto-generation. No wasted API calls. The athlete decides.

---

## Scope

### In scope

- Remove auto-generation from Garmin/Strava sync pipelines
- New `GET /v1/runtoon/pending` endpoint (share-eligible activity check)
- New `POST /v1/activities/{id}/runtoon/dismiss` endpoint (keyed by activity, not runtoon)
- New `POST /v1/runtoon/{id}/shared` analytics endpoint (share_target is best-effort/nullable)
- Modify existing `POST /v1/activities/{id}/runtoon/generate` to be the sole trigger
- New `RuntoonSharePrompt` component (mobile bottom sheet, root layout)
- New `RuntoonShareView` component (full-screen overlay with generation wait state)
- Modify existing `RuntoonCard` to use "Share Your Run" button → opens `RuntoonShareView`
- Web Share API integration (`navigator.share({ files: [...] })`)
- Desktop fallback (download + copy caption)
- Data model: `share_dismissed_at` on `Activity` (dismiss is pre-generation)
- Data model: `shared_at`, `share_format`, `share_target` on `RuntoonImage` (`share_target` nullable/best-effort)
- Alembic migration for new columns on both tables

### Out of scope

- Push notifications (no push infrastructure exists — don't build one for this)
- Direct social media API integrations (Web Share API handles this natively)
- Runtoon gallery/feed page
- Auto-sharing or posting on behalf of the athlete
- Changes to the Runtoon generation quality (prompts, style, captions — already shipped)

---

## Implementation Notes

### Files to change (backend)

| File | Change |
|------|--------|
| `apps/api/tasks/garmin_webhook_tasks.py` ~line 557 | Remove `generate_runtoon_for_latest.delay()` call |
| `apps/api/tasks/strava_tasks.py` ~line 1090 | Remove `generate_runtoon_for_latest.delay()` call |
| `apps/api/routers/runtoon.py` | Add `GET /pending`, `POST /activities/{id}/runtoon/dismiss`, `POST /runtoon/{id}/shared` |
| `apps/api/models.py` | Add `share_dismissed_at` to `Activity`; add `shared_at`, `share_format`, `share_target` to `RuntoonImage` |
| `apps/api/alembic/versions/` | New migration for both `Activity` and `RuntoonImage` columns |

### Files to change (frontend)

| File | Change |
|------|--------|
| `apps/web/components/activities/RuntoonCard.tsx` | Replace download dropdown with "Share Your Run" button → opens share view |
| `apps/web/components/runtoon/RuntoonSharePrompt.tsx` | **New** — mobile bottom sheet, polls `/pending` |
| `apps/web/components/runtoon/RuntoonShareView.tsx` | **New** — full-screen overlay, generation wait, Web Share API |
| `apps/web/app/layout.tsx` (or root layout) | Mount `RuntoonSharePrompt` globally |

### Key contracts to preserve

- **Feature flag gating** — `_check_feature_flag` / `_require_feature_flag` must still gate all endpoints. Only athletes in the `allowed_athlete_ids` list can access Runtoon features.
- **Tier-based regeneration limits** — existing 3-attempt limit stays. "Try another look" in the share view respects this.
- **Photo minimum** — 3+ photos required. The bottom sheet prompt must NOT appear for athletes without photos. The activity page CTA ("Upload photos →") handles discovery for those users.
- **Privacy** — all image access via signed URLs (15-min TTL). No raw storage keys exposed. `to_public_url` wrapper for all browser-facing URLs.
- **Units** — always miles, never meters. All distance formatting uses `formatDistance` / the units context.

### Founder decisions (non-negotiable)

These are finalized. Do not re-open or deviate:

1. **On-demand generation.** Runtoons are generated when the athlete taps "Share Your Run," NOT on sync. Remove the auto-generation calls from webhook tasks.
2. **2-mile threshold for auto-prompt.** The bottom sheet only appears for runs >= 2 miles (3,218m). Shorter runs are still shareable from the activity page — they just don't get the popup.
3. **AI caption pre-populates.** The AI-generated caption auto-fills the share text. It's part of the surprise. Editable before sharing, but the default is the AI's take.
4. **No speech bubbles.** The STYLE_ANCHOR already prohibits comic text overlays. Don't revert this.
5. **Never meters.** All user-facing distance displays use miles.

---

## Tests Required

### Unit tests

- `test_pending_returns_eligible_activity` — run >= 2mi, synced < 24h, running type, not dismissed, photos uploaded
- `test_pending_returns_has_runtoon_true` — eligible activity WITH existing Runtoon returns `has_runtoon: true`
- `test_pending_returns_has_runtoon_false` — eligible activity WITHOUT existing Runtoon returns `has_runtoon: false`
- `test_pending_excludes_short_runs` — run < 2mi returns 204
- `test_pending_excludes_dismissed` — activity with `share_dismissed_at` set returns 204
- `test_pending_excludes_non_running` — cycling/swimming returns 204
- `test_pending_excludes_stale` — activity synced > 24h ago returns 204
- `test_pending_excludes_no_photos` — athlete without 3+ photos returns 204
- `test_pending_excludes_already_shared` — activity with Runtoon where `shared_at` is set returns 204
- `test_dismiss_sets_share_dismissed_at_on_activity` — `POST /activities/{id}/runtoon/dismiss` sets `Activity.share_dismissed_at`, subsequent `/pending` excludes it
- `test_shared_records_analytics` — `POST /runtoon/{id}/shared` records `shared_at` and `share_format`; `share_target` defaults to `"unknown"` if not provided
- `test_generate_endpoint_still_works` — existing generate endpoint still triggers generation correctly

### Integration tests

- `test_sync_no_longer_triggers_runtoon` — Garmin/Strava webhook processing does NOT call `generate_runtoon_for_latest`
- `test_full_share_flow` — `/pending` → `/generate` → poll for completion → image available → `/shared`

### Frontend tests

- `RuntoonSharePrompt` only renders on mobile viewport
- `RuntoonSharePrompt` does not render when no pending activity
- `RuntoonSharePrompt` dismisses and does not re-appear for same activity
- `RuntoonShareView` shows skeleton during generation, image on completion
- Web Share API called with correct file + caption when supported
- Fallback download works when Web Share API unavailable

### Production smoke checks

```bash
# 1. Verify sync no longer triggers generation
docker logs strideiq_worker --tail=50 | grep "runtoon"
# Should NOT show "runtoon: generating" on new syncs

# 2. Verify /pending endpoint
TOKEN=<founder_token>
curl -s -H "Authorization: Bearer $TOKEN" https://strideiq.run/v1/runtoon/pending | python3 -m json.tool

# 3. Verify /dismiss endpoint (keyed by activity_id)
curl -s -X POST -H "Authorization: Bearer $TOKEN" https://strideiq.run/v1/activities/<activity_id>/runtoon/dismiss

# 4. Verify generation still works on-demand
curl -s -X POST -H "Authorization: Bearer $TOKEN" https://strideiq.run/v1/activities/<id>/runtoon/generate | python3 -m json.tool
```

Paste command output in handoff (no summaries-only).

---

## Evidence Required in Handoff

1. Scoped file list changed (no `git add -A`)
2. Test output (verbatim) for all unit + integration tests
3. Production deploy logs
4. Mobile screenshot or screen recording of:
   - Bottom sheet appearing after sync
   - "Share Your Run" tap → generation skeleton → image fade-in
   - Native share sheet opening with image + caption
   - "Not now" dismiss → prompt does not reappear
5. Desktop screenshot of activity page RuntoonCard with "Share Your Run" button
6. Worker logs showing NO auto-generation on new sync

---

## Acceptance Criteria

- [ ] AC1: Garmin/Strava sync does NOT trigger Runtoon generation (worker logs confirm)
- [ ] AC2: `GET /v1/runtoon/pending` returns eligible activity with correct `has_runtoon` flag for runs >= 2mi synced < 24h
- [ ] AC3: `GET /v1/runtoon/pending` returns 204 for runs < 2mi, non-running, dismissed, stale, no photos, already shared
- [ ] AC4: Mobile bottom sheet appears within 5s of app detecting new eligible activity
- [ ] AC5: Tapping "Share Your Run" triggers on-demand generation with visible skeleton state
- [ ] AC6: Image fades in when generation completes (~15-20s)
- [ ] AC7: "Share" button invokes `navigator.share({ files, text })` on mobile
- [ ] AC8: AI caption pre-populates in the share text
- [ ] AC9: "Not now" calls `POST /activities/{id}/runtoon/dismiss`, sets `Activity.share_dismissed_at`, and does not re-prompt
- [ ] AC10: Desktop fallback: download + copy caption (no bottom sheet)
- [ ] AC11: Activity page RuntoonCard has "Share Your Run" button for ALL runs (no distance gate)
- [ ] AC12: All existing feature flag, tier, photo, and privacy contracts preserved
- [ ] AC13: Tree clean, tests green, production healthy

---

## Mandatory: Site Audit Update

`docs/SITE_AUDIT_LIVING.md` must be updated in the same session for every material ship.

Required update block in the delivery pack:

1. Exact section(s) updated in `docs/SITE_AUDIT_LIVING.md`
2. What changed in product truth (not plan text):
   - Runtoon is now on-demand share flow, not auto-generated
   - Mobile bottom sheet prompt on eligible runs
   - Web Share API native sharing
   - Activity page card updated with Share button
3. Any inventory count/surface/tool updates

No task is complete until this is done.
