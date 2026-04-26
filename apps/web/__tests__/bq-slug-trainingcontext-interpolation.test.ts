/**
 * Regression test for the BQ slug trainingContext interpolation bug.
 *
 * The bug: trainingContext was typed as `string` but several entries used
 * ${...} template-literal syntax inside single-quoted strings, so the raw
 * literal tokens rendered verbatim on production PSEO pages.
 *
 * Invariants this test protects:
 *   1. No trainingContext entry is a single-quoted string that contains ${
 *      (would render as literal text, not interpolated).
 *   2. No template-literal form ends up producing output with ${ residue
 *      for a plausible sample BQEntry.
 */

import * as fs from 'fs'
import * as path from 'path'

const PAGE_PATH = path.join(
  __dirname,
  '..',
  'app',
  'tools',
  'boston-qualifying',
  '[slug]',
  'page.tsx',
)

describe('BQ slug trainingContext — no un-interpolated ${ residue on PSEO pages', () => {
  const source = fs.readFileSync(PAGE_PATH, 'utf8')

  test('no trainingContext single-quoted string contains ${ (the original bug shape)', () => {
    // Match: trainingContext: '...${...
    // Single-quoted string is NOT a template literal, so ${} is rendered as text.
    const badPattern = /trainingContext:\s*'[^']*\$\{/g
    const matches = source.match(badPattern) ?? []
    expect(matches).toEqual([])
  })

  test('no trainingContext double-quoted string contains ${ (symmetric bug)', () => {
    const badPattern = /trainingContext:\s*"[^"]*\$\{/g
    const matches = source.match(badPattern) ?? []
    expect(matches).toEqual([])
  })

  test('function-form trainingContext entries interpolate a plausible BQEntry without leaving ${ residue', () => {
    // Extract every `trainingContext: (d) => \`...\`,` arrow-function body
    // and evaluate it against a sample BQEntry.
    // Intentionally narrow: only validates that our sample inputs produce
    // template-literal output without raw ${ tokens.
    const sample = {
      slug: 'test-slug',
      gender: 'men',
      genderLabel: 'Men',
      ageGroup: '40–44',
      midAge: 42,
      bqTime: '3:05',
      bqSeconds: 11100,
      rpi: 53.2,
      wmaGradePct: 72.5,
      paces: {
        easy:       { mi: '8:45', km: '5:26', secPerMile: 525 },
        marathon:   { mi: '7:03', km: '4:23', secPerMile: 423 },
        threshold:  { mi: '6:31', km: '4:03', secPerMile: 391 },
        interval:   { mi: '6:00', km: '3:44', secPerMile: 360 },
        repetition: { mi: '5:34', km: '3:28', secPerMile: 334 },
      },
      equivalents: {
        '5k':   { label: '5K',           distanceMeters: 5000,  timeSeconds: 1200, timeFormatted: '20:00', paceMi: '6:26', paceKm: '4:00' },
        '10k':  { label: '10K',          distanceMeters: 10000, timeSeconds: 2500, timeFormatted: '41:40', paceMi: '6:42', paceKm: '4:10' },
        'half': { label: 'Half marathon',distanceMeters: 21097, timeSeconds: 5500, timeFormatted: '1:31:40', paceMi: '6:59', paceKm: '4:20' },
      },
    }

    // Find every `trainingContext: (d) => \`...\`,` occurrence.
    // Backtick-delimited template literal with arrow-function prefix.
    const fnPattern = /trainingContext:\s*\(d\)\s*=>\s*`([^`]+)`/g
    const bodies: string[] = []
    let m: RegExpExecArray | null
    while ((m = fnPattern.exec(source)) !== null) {
      bodies.push(m[1])
    }

    expect(bodies.length).toBeGreaterThan(0) // sanity: we expect at least the 4 we converted

    for (const body of bodies) {
      // Rebuild a template literal function and invoke it with the sample.
      // eslint-disable-next-line no-new-func
      const render = new Function('d', 'return `' + body + '`') as (d: unknown) => string
      const rendered = render(sample)
      expect(rendered).not.toMatch(/\$\{/)
    }
  })
})
