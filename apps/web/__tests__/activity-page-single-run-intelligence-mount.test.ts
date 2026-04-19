/**
 * Regression test: exactly one <RunIntelligence /> mount on the activity page.
 *
 * Context
 * -------
 * Before the April 2026 UX cleanup, the activity detail page mounted the
 * "Athlete Intelligence" card in BOTH the Overview panel (above the fold) and
 * the Context panel.  Because ActivityTabs keeps inactive panels mounted in
 * the DOM (apps/web/components/activities/ActivityTabs.tsx), both instances
 * existed simultaneously on every page load.  Users saw the same intelligence
 * card twice depending on which tab they opened, which trained them to
 * ignore it.
 *
 * Phase 2 of the canvas-v2 rollout (April 2026) collapsed the page to
 * 3 tabs: Splits / Coach / Compare.  RunIntelligence now lives at the top of
 * the Coach panel as the canonical placement (one mount, never duplicated).
 *
 * This test is a structural assertion (static source scan of page.tsx).  A
 * behavioral render test would be stronger but requires mocking auth, units,
 * the React-Query client, and ~15 child components that this page pulls in.
 * The static check catches the specific class of regression -- someone
 * pasting a second <RunIntelligence /> back onto the page.
 */

import * as fs from 'fs';
import * as path from 'path';

const PAGE_PATH = path.join(
  __dirname,
  '..',
  'app',
  'activities',
  '[id]',
  'page.tsx',
);

describe('Activity detail page — single RunIntelligence mount', () => {
  const source = fs.readFileSync(PAGE_PATH, 'utf8');

  test('RunIntelligence is imported exactly once', () => {
    const importMatches = source.match(/import\s+\{[^}]*\bRunIntelligence\b[^}]*\}\s+from/g) ?? [];
    expect(importMatches).toHaveLength(1);
  });

  test('RunIntelligence is rendered exactly once as a JSX element', () => {
    // Match `<RunIntelligence` at the start of a JSX element (not the import
    // line, which uses `{ RunIntelligence }` with braces).
    const jsxMountMatches = source.match(/<RunIntelligence[\s/>]/g) ?? [];
    expect(jsxMountMatches).toHaveLength(1);
  });

  test('The single RunIntelligence mount sits inside the Coach tab panel', () => {
    // Phase 2: Coach tab is the canonical home.  Assert the mount appears
    // after the `coach:` panel key and before the `compare:` panel key.
    const coachKeyIndex = source.search(/\bcoach:\s*\(/);
    const compareKeyIndex = source.search(/\bcompare:\s*</);
    const mountIndex = source.search(/<RunIntelligence[\s/>]/);
    expect(coachKeyIndex).toBeGreaterThan(-1);
    expect(compareKeyIndex).toBeGreaterThan(coachKeyIndex);
    expect(mountIndex).toBeGreaterThan(coachKeyIndex);
    expect(mountIndex).toBeLessThan(compareKeyIndex);
  });
});
