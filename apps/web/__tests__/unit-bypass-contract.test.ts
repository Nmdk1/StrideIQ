/**
 * Unit-bypass contract guards.
 *
 * Why this exists:
 *   The unit-formatting layer (apps/web/lib/context/UnitsContext.tsx) is
 *   correct in isolation, but distance/pace fields ship from the API with
 *   imperial-baked field names (`distance_mi`, `pace_per_mile`,
 *   `current_week_mi`, etc.). Surfaces that forget to route those values
 *   through the global formatter quietly render miles to km-preference
 *   athletes. Dejan Kadunc (2026-04-21 support email) hit three such
 *   surfaces — the Efficiency Trend chart, the Age-Graded Trajectory
 *   chart, and the Coach tab "Your data" panel — none of which had ever
 *   been wired up to useUnits.
 *
 *   This file is the regression net for that bug class. It greps the
 *   source files of the three reported surfaces (and the Coach chat
 *   brief composer) for the specific anti-patterns that produced the
 *   bug, and asserts they don't reappear.
 *
 *   Same shape as marketing-claim-contracts.test.ts — file-level source
 *   asserts, no render mounting, fast and deterministic.
 */

import * as fs from 'fs';
import * as path from 'path';

const WEB_ROOT = path.join(__dirname, '..');
const r = (p: string) => fs.readFileSync(path.join(WEB_ROOT, p), 'utf8');

describe('Unit-bypass contracts — surfaces that consume mi-baked API fields', () => {
  test('EfficiencyChart imports useUnits and does not hardcode "/mi" suffix', () => {
    const src = r('components/dashboard/EfficiencyChart.tsx');
    expect(src).toMatch(/from\s+['"]@\/lib\/context\/UnitsContext['"]/);
    expect(src).toMatch(/useUnits\(\)/);
    // Tooltip pace must go through the global formatter, not a hardcoded
    // "/mi" suffix glued onto the raw API value.
    expect(src).not.toMatch(/\/mi['"`]\s*$/m);
    expect(src).not.toMatch(/['"]\s*\/mi['"]/);
  });

  test('AgeGradedChart imports useUnits and does not hardcode "/mi" suffix', () => {
    const src = r('components/dashboard/AgeGradedChart.tsx');
    expect(src).toMatch(/from\s+['"]@\/lib\/context\/UnitsContext['"]/);
    expect(src).toMatch(/useUnits\(\)/);
    expect(src).not.toMatch(/\/mi['"`]\s*$/m);
    expect(src).not.toMatch(/['"]\s*\/mi['"]/);
  });

  test('Coach page imports useUnits (entire page used to bypass it)', () => {
    const src = r('app/coach/page.tsx');
    expect(src).toMatch(/from\s+['"]@\/lib\/context\/UnitsContext['"]/);
    expect(src).toMatch(/useUnits\(\)/);
  });

  test('Coach page does not append the literal string "mi" to current_week_mi', () => {
    const src = r('app/coach/page.tsx');
    // The two pre-fix sites both did:  current_week_mi.toFixed(N) + 'mi'
    // (chat brief composer) or  {...current_week_mi.toFixed(N)}mi  (data panel).
    // Both are unit-bypass anti-patterns — current_week_mi must flow through
    // the formatter, never get a literal 'mi' / "mi" appended.
    expect(src).not.toMatch(/current_week_mi[^)]*\.toFixed\([^)]*\)\s*\+\s*['"]mi['"]/);
    expect(src).not.toMatch(/current_week_mi[^)]*\.toFixed\([^)]*\)\s*\}\s*mi\b/);
    // peak_week_mi had the same anti-pattern in the chat brief composer.
    expect(src).not.toMatch(/peak_week_mi[^)]*\.toFixed\([^)]*\)\s*\+\s*['"]mi['"]/);
  });

  test('Settings "Training paces" card respects the unit preference (no hardcoded .mi)', () => {
    // Dejan Kadunc support email follow-up (2026-04-21): the in-app
    // Settings card showed "Easy 9:06 or slower / Marathon 8:05 / ..."
    // verbatim min/mi to a metric athlete because every span was hardcoded
    // to `paceProfile?.paces?.X?.mi`. The API already returns both `.mi`
    // and `.km` for every zone (services/rpi_calculator.py
    // _secs_to_pace_dict), so the fix is to pick the unit-matching key.
    const src = r('app/settings/page.tsx');
    expect(src).toMatch(/from\s+['"]@\/lib\/context\/UnitsContext['"]/);
    expect(src).toMatch(/useUnits\(\)/);
    // Forbid the hardcoded `.marathon?.mi` / `.threshold?.mi` /
    // `.interval?.mi` / `.repetition?.mi` patterns. The easy zone has its
    // own `display_mi` / `display_km` pair so it's exempt from this exact
    // grep, but the unit-key-conditional access guards it anyway.
    expect(src).not.toMatch(/paces\?\.marathon\?\.mi\b/);
    expect(src).not.toMatch(/paces\?\.threshold\?\.mi\b/);
    expect(src).not.toMatch(/paces\?\.interval\?\.mi\b/);
    expect(src).not.toMatch(/paces\?\.repetition\?\.mi\b/);
  });

  test('Onboarding "Training pace profile saved" panel respects the unit preference', () => {
    // Same bug class as Settings — the onboarding success panel that
    // appears after the goals step also hardcoded `.mi` on every zone.
    const src = r('app/onboarding/page.tsx');
    expect(src).toMatch(/from\s+['"]@\/lib\/context\/UnitsContext['"]/);
    expect(src).toMatch(/useUnits\(\)/);
    expect(src).not.toMatch(/paces\?\.marathon\?\.mi\b/);
    expect(src).not.toMatch(/paces\?\.threshold\?\.mi\b/);
    expect(src).not.toMatch(/paces\?\.interval\?\.mi\b/);
  });

  test('Home page does not claim "Recovery day." as a fallback for athletes without a planned workout', () => {
    // The string was rendered every day for any athlete without a plan,
    // independent of TSB / readiness / recovery score — the same class of
    // failure as the Jim narration incident: confidently asserting
    // something the system has no basis for. Honest copy is "No workout
    // planned today." — anything else is template narration.
    const src = r('app/home/page.tsx');
    expect(src).not.toMatch(/['"]Recovery day\.['"]/);
  });
});
