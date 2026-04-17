# Comparison Product Build Log

Append-only log of the seven-phase build of the comparison product family.
Each phase appends a section when complete with what shipped, smoke evidence,
and judgment calls made autonomously.

**Phases:**

1. Activities-list filters (brushable histograms + workout-type chips)
2. Route fingerprinting + ingest + backfill
3. Route naming UX
4. Block detection engine + persistence
5. Activity-page comparable runs (workout-type-specific visuals)
6. Anniversary card (route + condition tolerance)
7. Block-over-block view

**Operating rules in effect:**

- Suppression default everywhere (no card / no chart / no histogram if no data).
- Heat-adjusted pace requires both compared activities have temp + dew; otherwise raw only, no heat claim.
- Visual-first per `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` — narrative below visual, not as a card with text.
- Tests xfailed first, then implementation.
- CI green before push to prod.
- Behavioral smoke against real founder data on prod after each phase.

---

## Phase 1 — Activities-list filters

**Status:** in progress

