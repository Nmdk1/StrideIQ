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
 *      user-facing score name, creating a brand/product inconsistency.
 *
 *   3. "Not lookup tables" claim. The training-pace engine literally uses a
 *      hardcoded lookup table (_RPI_PACE_TABLE, RPI 20–85). Public copy must
 *      not claim otherwise.
 *
 *   4. Landing-page WebApplication JSON-LD price. StrideIQ is a paid product;
 *      declaring `price: '0'` on the top-level WebApplication entity is
 *      misleading. Free calculators have their own SoftwareApplication
 *      entries that correctly declare price 0.
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
    expect(src).not.toMatch(/\bVDOT\b/)
  })

  test('landing page WebApplication JSON-LD does not declare price: "0"', () => {
    const src = r('app/page.tsx')
    // Extract the webAppJsonLd object literal; assert no price key inside.
    const m = src.match(/const\s+webAppJsonLd\s*=\s*\{[\s\S]*?^\}/m)
    expect(m).not.toBeNull()
    const obj = m![0]
    expect(obj).not.toMatch(/price:\s*['"]0['"]/)
    expect(obj).not.toMatch(/priceCurrency/)
  })
})
