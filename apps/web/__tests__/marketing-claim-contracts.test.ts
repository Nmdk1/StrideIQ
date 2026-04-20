/**
 * Marketing / PSEO claim contracts.
 *
 * These tests guard against regressions where public copy makes claims that
 * contradict internal product contracts:
 *
 *   1. `efficiency` as a polarity-ambiguous metric (see
 *      apps/api/services/intelligence/n1_insight_generator.py:
 *      OUTPUT_METRIC_REGISTRY). Marketing must not use "efficiency trend(s)"
 *      as the headline adaptation signal, because athlete-facing directional
 *      claims on efficiency are forbidden internally.
 *
 *   2. RPI terminology. The product uses "RPI (Running Performance Index)"
 *      throughout. Public calculator copy previously used "VDOT" as the
 *      user-facing score name, creating a brand/product inconsistency. The
 *      training pace page may reconcile RPI with VDOT (the publicly known
 *      name for the same Daniels/Gilbert math) for SEO, but must not use
 *      VDOT as the user-facing score name.
 *
 *   3. "Not lookup tables" claim. The training-pace engine literally uses a
 *      hardcoded lookup table (_RPI_PACE_TABLE, RPI 20–85). Public copy must
 *      not claim otherwise.
 *
 *   4. Landing-page WebApplication JSON-LD price. StrideIQ is a paid product;
 *      declaring `price: '0'` on the top-level WebApplication entity is
 *      misleading. Free calculators have their own SoftwareApplication
 *      entries that correctly declare price 0.
 *
 *   5. "No credit card required" claim. The production trial flow
 *      (apps/web/app/onboarding/page.tsx -> /v1/billing/checkout/trial)
 *      collects a credit card via Stripe Checkout. Marketing must not
 *      claim otherwise. "Cancel anytime via Stripe" is the truthful
 *      replacement (apps/api/routers/billing.py:137).
 *
 *   6. Voice rewrite 2026-04-16: Hero must lead with the manifesto line,
 *      QuickValue must not display fake-precision stat trio, WhyGuidedCoaching
 *      must not pick a fight with human coaches, Mission page must not
 *      contain the "New Masters" 8-tier taxonomy nor an external Unsplash
 *      image, and must not claim "measurable efficiency".
 */

import * as fs from 'fs'
import * as path from 'path'

const WEB_ROOT = path.join(__dirname, '..')
const r = (p: string) => fs.readFileSync(path.join(WEB_ROOT, p), 'utf8')

describe('Marketing claim contracts', () => {
  test('HowItWorks.tsx does not invoke efficiency trends as the adaptation signal', () => {
    const src = r('app/components/HowItWorks.tsx')
    expect(src).not.toMatch(/efficiency trends?/i)
  })

  test('FreeTools.tsx does not claim "not lookup tables"', () => {
    const src = r('app/components/FreeTools.tsx')
    expect(src).not.toMatch(/not\s+lookup\s+tables/i)
  })

  test('llms.txt does not claim "not static lookup tables"', () => {
    const src = r('public/llms.txt')
    expect(src).not.toMatch(/not\s+(static\s+)?lookup\s+tables/i)
  })

  test('training-pace-calculator page uses RPI, not VDOT, as user-facing score name', () => {
    const src = r('app/tools/training-pace-calculator/page.tsx')
    // VDOT may appear in a reconciliation paragraph (e.g. "publicly known as VDOT"),
    // but only in that explanatory context. Forbid VDOT inside the calculator
    // island, the H1, the answer capsule, the metadata title, and the JsonLd name.
    expect(src).not.toMatch(/<h1[^>]*>[^<]*VDOT/i)
    expect(src).not.toMatch(/title:\s*['"][^'"]*VDOT/i)
    expect(src).not.toMatch(/name:\s*['"][^'"]*VDOT/i)
  })

  test('training-pace-calculator page reconciles RPI with VDOT for SEO', () => {
    const src = r('app/tools/training-pace-calculator/page.tsx')
    // Both RPI and VDOT must appear (in the reconciliation paragraph) so that
    // a reader landing from a "VDOT" search query immediately understands
    // what they are looking at.
    expect(src).toMatch(/\bRPI\b/)
    expect(src).toMatch(/\bVDOT\b/)
  })

  test('landing page WebApplication JSON-LD does not declare price: "0"', () => {
    const src = r('app/page.tsx')
    const m = src.match(/const\s+webAppJsonLd\s*=\s*\{[\s\S]*?^\}/m)
    expect(m).not.toBeNull()
    const obj = m![0]
    expect(obj).not.toMatch(/price:\s*['"]0['"]/)
    expect(obj).not.toMatch(/priceCurrency/)
  })

  // --- Voice rewrite 2026-04-16 ---

  test('Hero leads with the manifesto line, not generic "AI Running Coach" subhead', () => {
    const src = r('app/components/Hero.tsx')
    expect(src).toMatch(/Your body has a voice/i)
    // The orange uppercase "AI Running Coach" pill that previously sat above
    // the trust indicators is gone — the manifesto line carries the role of
    // the subhead now.
    expect(src).not.toMatch(/uppercase[^>]*>\s*AI Running Coach/i)
  })

  test('Hero does not advertise "no credit card required" — production flow collects a card', () => {
    const src = r('app/components/Hero.tsx')
    expect(src).not.toMatch(/no\s+credit\s+card/i)
  })

  test('Hero contains the Adam S. user testimonial', () => {
    const src = r('app/components/Hero.tsx')
    expect(src).toMatch(/Adam S\./)
  })

  test('QuickValue does not display the "3 / 360° / 24/7" fake-precision stat trio', () => {
    const src = r('app/components/QuickValue.tsx')
    expect(src).not.toMatch(/24\/7/)
    expect(src).not.toMatch(/360°/)
    expect(src).not.toMatch(/Training Calculators/)
  })

  test('WhyGuidedCoaching uses cooperative title "Why StrideIQ exists"', () => {
    const src = r('app/components/WhyGuidedCoaching.tsx')
    expect(src).toMatch(/Why StrideIQ exists/)
    // Section is no longer headlined "Why Elite?".
    expect(src).not.toMatch(/Why Elite\?/)
  })

  test('WhyGuidedCoaching does not pick a fight with human coaches', () => {
    const src = r('app/components/WhyGuidedCoaching.tsx')
    expect(src).not.toMatch(/AI Running Coach vs Human Running Coach/i)
    expect(src).not.toMatch(/\$50-?\$300/)
    expect(src).not.toMatch(/Never sleeps,?\s+never forgets/i)
  })

  test('Mission page drops the "New Masters" 8-tier taxonomy', () => {
    const src = r('app/mission/page.tsx')
    expect(src).not.toMatch(/Centurion Prime/i)
    expect(src).not.toMatch(/Centurion Masters/i)
    expect(src).not.toMatch(/Icon Masters/i)
    expect(src).not.toMatch(/Legend Masters/i)
    expect(src).not.toMatch(/Senior Grandmasters/i)
    expect(src).not.toMatch(/The New Masters/i)
  })

  test('Mission page does not embed an external Unsplash image (referrer leak + drift risk)', () => {
    const src = r('app/mission/page.tsx')
    expect(src).not.toMatch(/images\.unsplash\.com/)
  })

  test('Mission page does not claim "measurable efficiency"', () => {
    const src = r('app/mission/page.tsx')
    // Same OUTPUT_METRIC_REGISTRY polarity contract as HowItWorks — efficiency
    // is not a measurable adaptation signal we are willing to defend publicly.
    expect(src).not.toMatch(/measurable efficiency/i)
  })

  test('Mission page does not use the "silent, brilliant assistant" theater language', () => {
    const src = r('app/mission/page.tsx')
    expect(src).not.toMatch(/silent,?\s+brilliant assistant/i)
  })
})
