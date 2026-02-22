# Garmin API Configuration — Official Portal Documentation

**Source:** Garmin Connect Developer Program > API Configuration
**Captured:** February 22, 2026

---

## Overview

"The APIs selected here will correlate with data sharing permissions an end-user
can control from their Garmin Connect Account."

---

## Data Shared from Garmin Connect to StrideIQ

| API | Enabled | Permission | Active Endpoints |
|-----|---------|------------|-----------------|
| Daily Health Stats | Yes | Approved | 0 |
| Activity | Yes | Approved | 0 |
| Women's Health | Yes | Approved | 0 |
| Historical Data Export ** | Yes | Approved | — |

**All four inbound data APIs are enabled and approved.**

Active Endpoints = 0 because webhook URLs have not been configured yet
(see ENDPOINT_CONFIGURATION.md).

**Historical Data Export** has a `**` annotation — likely indicates special terms
or that it depends on user consent (user toggle defaults to OFF on consent screen).

---

## Data Shared from StrideIQ to Garmin Connect

| API | Enabled | Permission |
|-----|---------|------------|
| Courses | No (unchecked) | Approved |
| Training | No (unchecked) | Approved |

**Both outbound APIs are approved but not enabled.** These are out of scope for
Phase 2. They would allow pushing workouts/courses to the user's Garmin device.

Note: The founder has stated Training API is out of scope and treated as
permanent until specific conditions are met (legal review, client base, use case).

---

## Mapping to User Consent Screen

| API Configuration Name | User Consent Toggle | API Permission Enum |
|----------------------|--------------------|--------------------|
| Activity | Activities | `ACTIVITY_EXPORT` |
| Daily Health Stats | Daily Health Stats | `HEALTH_EXPORT` |
| Women's Health | Women's Health | `MCT_EXPORT` |
| Historical Data Export | Historical Data | (controls backfill) |
| Courses | — (not shown to user) | `COURSE_IMPORT` |
| Training | — (not shown to user) | `WORKOUT_IMPORT` |
