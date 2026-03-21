# Workout fluency registry — PR checklist & gate attestation

**Canonical spec:** `docs/specs/WORKOUT_FLUENCY_REGISTRY_SPEC.md` **v0.2.25** (§2 / §2.1 execution gate + CI limits, §7 schema, §8 machine index + Phase 4 post–Phase 3 enrichment note, §11 wiring acceptance, §13 watch mode).

This document is the **operational** companion: what to paste in PRs and who may approve content.

---

## 1. When CI enforces the P0 / registry gate

On **pull requests**, if the diff touches either:

- `apps/api/services/plan_framework/**`, or  
- `apps/api/routers/plan_generation.py`,

then **GitHub Actions** runs `.github/scripts/ci_p0_registry_gate.py` and **fails** unless the PR description contains an attestation (see §2).

**KB-only** changes under `_AI_CONTEXT_/KNOWLEDGE_BASE/workouts/variants/**` do **not** trigger this check by themselves.

**What CI does *not* do:** The gate script only checks that **`P0-GATE:`** lines exist (and that **`WAIVER`** includes **`P0-WAIVER-REF:`**). It cannot judge whether **`GREEN`** is true, whether recovery-spec acceptance is satisfied, or whether a waiver is appropriate. Treat that as **human** accountability (author, reviewer, founder)—never as automated P0 proof.

---

## 2. PR description template (copy when gated paths change)

Paste into the PR body (edit the bracketed parts):

```text
## P0 / workout registry gate

P0-GATE: GREEN
P0-GATE-NOTES: [1–3 sentences: which recovery-spec criteria are satisfied for this change, or what was verified.]

## OR, if founder-approved scoped exception:

P0-GATE: WAIVER
P0-WAIVER-REF: [ticket, date, or one-line founder-scoped reason — required when using WAIVER]
```

**Rules:**

- **`GREEN`** — Use when `PLAN_GENERATION_VISION_ALIGNMENT_RECOVERY_SPEC.md` acceptance for the affected paths is actually met, or the change is **non-behavioral** (comments/types only) and you state that explicitly in `P0-GATE-NOTES`.
- **`WAIVER`** — Founder-scoped only; **`P0-WAIVER-REF:`** must be non-empty or CI fails.

---

## 3. `sme_status`: who flips `draft` → `approved`

| Status | Meaning | Who sets |
|--------|---------|----------|
| `draft` | Under review; not production-truth. | Agent or founder while iterating. |
| `vetoed` | Must not be used or wired. | **Founder (SME)** only. |
| `approved` | Eligible for wiring / “shipping” contract tests per spec. | **Founder (SME)** only — not optional for agents to self-approve coaching claims. |

### PR checklist (variant / KB content)

For any PR that adds or changes variant rows in `_AI_CONTEXT_/KNOWLEDGE_BASE/workouts/variants/`:

- [ ] If `STEM_COVERAGE.md` or plan_framework `workout_type` emissions change, `pytest tests/test_stem_coverage_sync.py` passes (from `apps/api`).
- [ ] Every variant has `sme_status` set (`draft` until founder review).
- [ ] `typical_build_context_tags` uses **only** tags from spec §6.3.
- [ ] `volume_family` is one of `E`, `M`, `T`, `I`, `R`, `long`, `composite`.
- [ ] **Reviewer:** founder (or delegate explicitly named in the PR) must **comment** with SME sign-off before any row is changed from `draft` to `approved` in that PR (or a follow-up PR that only promotes status).

**Agent rule:** Do not set `sme_status: approved` on new coaching content unless the PR description states **founder SME approval** (or links to a comment where the founder approves the exact variant IDs).

---

## 4. Optional: manual pre-flight for authors

Before opening a PR that touches gated runtime paths:

1. Read spec §2 and `PLAN_GENERATION_VISION_ALIGNMENT_RECOVERY_SPEC.md` for current P0 expectations.
2. Add the §2 attestation block to the PR body **before** pushing (avoids a red CI cycle).

---

*Last updated: 2026-03-22 — aligned with registry spec v0.2.25; fluency **Phase 3 active**; Phase 4 enrichment mandatory after Phase 3 (`WORKOUT_FLUENCY_BUILD_SEQUENCE.md`).*
