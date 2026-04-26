# Marketing Voice Rewrite — 2026-04-16

**Status:** in-progress (spec + execution in single session).
**Authority:** founder calls captured in this conversation. All copy decisions
explicit and locked.
**Predecessor:** `docs/reviews/MARKETING_REVIEW_2026-04-16.md` (April 16
marketing review). Priority 1 (BQ slug bug) and Priority 3 (claim-contract
conflicts) shipped in commits `ed9b17d` and `0bd5f24`. Priority 2 (Hero +
WhyGuidedCoaching voice rewrite) was missed and is the core of this pass.

## Problem

The landing page voice does not match the product manifesto. Specific failures
identified by the April 16 review and confirmed in this session:

1. Hero leads with generic SaaS positioning ("AI Running Coach") instead of
   the manifesto-direct line in the meta description.
2. `WhyGuidedCoaching.tsx` picks an unnecessary fight with human coaches ("Never
   sleeps, never forgets") and lists a price comparison ($24.99 vs $50–300)
   that is brand-hostile.
3. `QuickValue.tsx` displays "3 / 360° / 24/7" — fake-precision stats that
   say nothing.
4. FAQ #7 ("What is the best AI running coach for marathon training?") is
   keyword-bend, not a real question a real user would ask.
5. `mission/page.tsx` contains the "New Masters" 8-tier taxonomy ("Centurion
   Prime 100+"), an external Unsplash image with referrer leak, "silent,
   brilliant assistant" theater language, and a "measurable efficiency" claim
   that violates the internal `OUTPUT_METRIC_REGISTRY` polarity contract.
6. Training pace page does not reconcile RPI (the user-facing name) with VDOT
   (the publicly known name for the same Daniels/Gilbert math), losing SEO and
   creating an internal inconsistency.
7. Hero advertises "No credit card required" — **production flow requires a
   credit card.** Onboarding completion (`onboarding/page.tsx:110`) POSTs to
   `/v1/billing/checkout/trial` which creates a Stripe Checkout Session
   collecting a card. This is the most serious item: shipped-to-production
   trust rupture.
8. No real customer social proof. Only the founder's quote.

## Decisions (locked)

| Surface | Decision | Source |
|---|---|---|
| Hero H1 | "Your body has a voice. StrideIQ gives it one." | founder pick |
| Tagline | Keep "Deep Intelligence. Zero Fluff." | outside-Opus + founder agree |
| Value-prop stack | Outcome-named (option 2) | founder pick |
| Subhead | "Personal patterns. Real evidence. Coaching that can't be faked." | founder pick |
| Trust pill #3 | Replace "No credit card required" with **"Cancel anytime via Stripe"** (true: `billing.py:137`) | trust contract |
| Hero testimonial | Adam S. distillation #1 | founder pick |
| QuickValue | Drop "3 / 360° / 24/7", replace with capability stripe (option 3) | founder pick |
| WhyGuidedCoaching title | "Why StrideIQ exists" | founder pick |
| WhyGuidedCoaching content | Drop AI-vs-human framing + price comparison. Four cooperative cards: Memory, Pattern detection, Availability, Evidence. Add DEXA case-study callout. | scope expansion |
| FAQ #7 replacement | "Does StrideIQ tell me what my sleep or nutrition did to my training?" | founder pick |
| Mission page | Drop New Masters taxonomy. Replace Unsplash with no image. Rewrite "silent, brilliant assistant" → "the system records the patterns; the athlete decides what to do." Replace "measurable efficiency" → "real adaptation". | wide scope |
| Training pace | Add VDOT/RPI reconciliation paragraph. | wide scope |
| Case studies | Two new routes: `/case-studies/dexa-and-the-7-pound-gap` (de-identified per Brian's pre-clearance) and `/case-studies/strength-and-durability` (de-identified). | scope expansion |
| Calculator share-link lift | Out of scope this pass — separate ticket. | scope discipline |

## Files changed

### Code
- `apps/web/app/components/Hero.tsx` — full content rewrite
- `apps/web/app/components/QuickValue.tsx` — drop trio, add capability stripe
- `apps/web/app/components/WhyGuidedCoaching.tsx` — full rewrite, new title, four cards, DEXA callout
- `apps/web/app/components/FAQ.tsx` — replace question 7
- `apps/web/app/mission/page.tsx` — drop New Masters, drop Unsplash, rewrite Guided Self-Coaching paragraph
- `apps/web/app/tools/training-pace-calculator/page.tsx` — insert RPI/VDOT reconciliation paragraph
- `apps/web/app/case-studies/dexa-and-the-7-pound-gap/page.tsx` — NEW
- `apps/web/app/case-studies/strength-and-durability/page.tsx` — NEW

### Tests
- `apps/web/__tests__/marketing-claim-contracts.test.ts` — add 8 new contract tests:
  1. Hero contains the manifesto H1 line
  2. Hero does not contain "No credit card required" (the false claim)
  3. Hero contains "Adam S." testimonial attribution
  4. QuickValue does not contain "24/7" or "360°" (the fake-precision stats)
  5. WhyGuidedCoaching title is "Why StrideIQ exists"
  6. WhyGuidedCoaching does not contain "AI Running Coach vs Human" framing
  7. Mission page does not contain "New Masters" taxonomy nor Unsplash URL
  8. Mission page does not claim "measurable efficiency"
  9. Training pace page reconciles RPI with VDOT publicly

### Docs
- `docs/specs/MARKETING_VOICE_REWRITE_2026-04-16.md` — this file
- `docs/wiki/marketing-voice.md` — wiki entry (per `wiki-currency.mdc`)

## Permissions on file

- **Adam S.** — pre-cleared by founder for "Adam S." attribution
- **Brian (DEXA + cardiac decoupling)** — pre-cleared for de-identified marketing use; case studies attribute to "an athlete" / "a 47-year-old runner" without name, race name, or precise date triangulation

## Out of scope (separate tickets)

- Calculator share-link / community-seeding affordance (UTM-tagged share button on `/tools/*` pages)
- Brian DEXA-flow product surfacing (when strength v1 ships, the coach's DEXA-aware behavior should be discoverable from the activity page)
- Footer brand-copy strengthening (April 16 review §6)
- OG image refresh (April 16 review §6)
- Person/Author JSON-LD schema (April 16 review §6)

## CC claim — what we did not do

We did not migrate onboarding from `/checkout/trial` to `/trial/start`.
That is a business decision (CC-collected trials convert ~2-3x better) and
the founder rejected option B in favor of option A (drop the false claim).
The product flow is unchanged. Only the marketing claim is now true.
