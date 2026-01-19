---
title: ADR-043 Check-in + Nutrition UX Overhaul (Phase 1)
status: accepted
date: 2026-01-18
---

## Context

Check-in and Nutrition are high-signal inputs for the correlation engine, but they are currently under-discoverable and require manual data entry that feels “form-y”.

Phase 1 focuses on improving discoverability and reducing friction without redesigning the entire workflow.

## Decision (Phase 1)

- **Navigation discoverability**: Add `Check-in` and `Nutrition` to authenticated navigation.
- **Natural language nutrition input**: Add a simple text field on the Nutrition page that calls a backend parsing endpoint and pre-fills the existing form.
- **Post-submit feedback**: After a successful Check-in or Nutrition log, show a short “correlation/progress” teaser so users understand why logging matters.
- **Fallback preserved**: Manual entry and presets remain fully functional if parsing is unavailable.

## Backend API

- **New endpoint**: `POST /v1/nutrition/parse`
  - Request: `{ "text": string }`
  - Response: `NutritionEntryCreate` (prefilled for authenticated user as a `daily` entry for today)
  - Implementation: Uses OpenAI with a constrained JSON-only prompt to estimate macros.

## Consequences

- Users can discover and use Check-in/Nutrition without hunting.
- Nutrition logging supports a “type what you ate” flow, while keeping structured editing as a safety/accuracy step.
- Parsing depends on `OPENAI_API_KEY`; when missing, users fall back to manual logging.

## Out of Scope (Phase 2+)

- Rich “correlation insight” computation immediately after logging (Phase 1 uses a lightweight teaser).
- Meal-level itemization and editable food lists.
- Persisting parser provenance/confidence and surfacing uncertainty in UI.

