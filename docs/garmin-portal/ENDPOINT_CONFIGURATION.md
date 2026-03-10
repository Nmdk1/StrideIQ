# Garmin Endpoint Configuration — Official Portal Documentation

**Source:** Garmin Connect Developer Program > Endpoint Configuration
**Captured:** February 22, 2026

---

## Overview

Each data type has its own webhook URL field and delivery mode. URLs can all point
to the same StrideIQ endpoint, but Garmin sends each type to its configured URL
independently.

**No HMAC / signing secret configuration exists on this page.** Garmin does not
provide webhook payload signatures. Security must use compensating controls:
- `garmin-client-id` header verification
- IP allowlisting (if Garmin publishes source ranges)
- Strict schema validation
- Unknown userId skip-and-log policy

---

## Delivery Modes

| Mode | Behavior |
|------|----------|
| `on hold` | Paused — no data sent |
| `enabled` | Ping mode — Garmin notifies, you pull via API |
| `push` | Full push — Garmin sends complete data in webhook payload |

---

## Endpoint Types

### ACTIVITY

| Type | Push Available | Notes |
|------|---------------|-------|
| Activities | Yes | Activity summaries |
| Activity Details | Yes | GPS, samples, laps |
| Activity Files | **No** (ping only) | FIT/TCX/GPX files — must pull via `GET /rest/activityFile` |
| Manually Updated Activities | Yes | User-edited activities on Connect site |
| MoveIQ | Yes | Auto-detected activities (not user-initiated) |

### COMMON

| Type | Push Available | Notes |
|------|---------------|-------|
| Deregistrations | **No** (ping only) | User disconnected from app |
| User Permissions Change | **No** (ping only) | User changed permission toggles |

### HEALTH

| Type | Push Available | Notes |
|------|---------------|-------|
| Blood Pressure | Yes | |
| Body Compositions | Yes | Weight, BMI, body fat |
| Dailies | Yes | Daily summary (midnight-to-midnight) |
| Epochs | Yes | 15-minute granularity wellness data |
| HRV Summary | Yes | Overnight HRV |
| Health Snapshot | Yes | 2-minute health session |
| Pulse Ox | Yes | SpO2 readings |
| Respiration | Yes | Breathing rate |
| Skin Temperature | Yes | Skin temp deviation |
| Sleeps | Yes | Sleep staging, scores, SpO2, respiration |
| Stress | Yes | Stress levels + Body Battery |
| User Metrics | Yes | VO2 max, fitness age |

### WOMEN'S HEALTH

| Type | Push Available | Notes |
|------|---------------|-------|
| Menstrual Cycle Tracking | Yes | Cycle schedule, phases, predictions |

---

## Architecture Decision: Webhook URL Strategy

**Option A — Single URL (recommended for Phase 2):**
Point all 22 endpoints to `https://strideiq.run/v1/garmin/webhook`.
Discriminate by payload keys (each data type has a distinct schema).

**Option B — Per-type URLs:**
Use paths like `/v1/garmin/webhook/activities`, `/v1/garmin/webhook/sleeps`, etc.
Cleaner routing but 22 endpoint registrations.

**Current AC decision (D4):** Single multiplexed endpoint. This portal evidence
shows that Garmin supports per-type URLs, but we can still use one URL and
discriminate by payload content.

---

## Current Status

All endpoints currently show `https://example.com/path` (placeholder).
None are configured yet. Will be configured when D4 webhook endpoint is deployed.

---

## Phase 2 — Endpoints to Enable (push mode)

**Tier 1 (required for MVP):**
- ACTIVITY - Activities (push)
- ACTIVITY - Activity Details (push)
- HEALTH - Sleeps (push)
- HEALTH - HRV Summary (push)
- HEALTH - Stress (push) — includes Body Battery
- HEALTH - Dailies (push)
- HEALTH - User Metrics (push) — VO2 max
- COMMON - Deregistrations (enabled/ping)
- COMMON - User Permissions Change (enabled/ping)

**Tier 2 (enable for completeness):**
- WOMEN_HEALTH - Menstrual Cycle Tracking (push)
- HEALTH - Respiration (push)
- HEALTH - Body Compositions (push)
- HEALTH - Pulse Ox (push)

**Tier 3 (defer):**
- ACTIVITY - Activity Files (ping only — FIT file parsing is future work)
- ACTIVITY - Manually Updated Activities (push)
- ACTIVITY - MoveIQ (push)
- HEALTH - Epochs (push — high volume, 15-min granularity)
- HEALTH - Blood Pressure (push)
- HEALTH - Skin Temperature (push)
- HEALTH - Health Snapshot (push)
