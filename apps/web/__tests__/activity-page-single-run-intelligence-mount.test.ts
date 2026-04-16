/**
 * Regression test: exactly one <RunIntelligence /> mount on the activity page.
 *
 * Context
 * -------
 * Before the April 2026 UX cleanup, the activity detail page mounted the
 * "Athlete Intelligence" card in BOTH the Overview panel (above the fold) and
 * the Context panel.  Because ActivityTabs keeps inactive panels mounted in
 * the DOM (apps/web/components/activities/ActivityTabs.tsx lines 20-21,
 * 52-63), both instances existed simultaneously on every page load.  Users
 * saw the same intelligence card twice depending on which tab they opened,
 * which trained them to ignore it.
 *
 * UX fix #1 removed the Context-tab mount.  The Overview placement is
 * canonical because it is above the fold and the default tab.
 *
 * This test is a structural assertion (static source scan of page.tsx).  A
 * behavioral render test would be stronger but requires mocking auth, units,
 * the React-Query client, and ~15 child components that this page pulls in.
 * When UX fixes #2 and #3 land we will invest in a full render harness for
 * the activity page and this test can be upgraded to a DOM-count assertion.
 * For now the static check catches the specific class of regression --
 * someone pasting a second <RunIntelligence /> back onto the page.
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

  test('The single RunIntelligence mount sits in the Overview tab, above the fold', () => {
    // Rather than brittle-match surrounding JSX, assert ordering: the mount
    // appears before the `context:` tab-panel key (which starts the Context
    // tab content).  This guards against someone re-adding it to Context
    // while removing it from Overview.
    const mountIndex = source.search(/<RunIntelligence[\s/>]/);
    const contextKeyIndex = source.search(/\bcontext:\s*\(/);
    expect(mountIndex).toBeGreaterThan(-1);
    expect(contextKeyIndex).toBeGreaterThan(-1);
    expect(mountIndex).toBeLessThan(contextKeyIndex);
  });
});
