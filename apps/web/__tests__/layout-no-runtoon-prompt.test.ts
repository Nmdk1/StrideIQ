/**
 * Regression test: the global app layout must not render the
 * RuntoonSharePrompt.
 *
 * Context
 * -------
 * Phase 4 of the activity-page rebuild (April 2026) removed the
 * always-on mobile bottom sheet that polled /v1/runtoon/pending every
 * 10 seconds and slid up uninvited on every recent run.  The founder
 * directive was unambiguous: sharing is a *pull* action, surfaced from
 * the activity page chrome via ShareButton -> ShareDrawer.  Nothing
 * about a run should ever auto-share itself.
 *
 * The component file is intentionally preserved on disk (per the
 * "saved for posterity" rule), but it must remain unrendered.  This
 * test is a static guard: it scans apps/web/app/layout.tsx and fails
 * if either an active import or a JSX mount of RuntoonSharePrompt
 * comes back.
 */

import * as fs from 'fs';
import * as path from 'path';

const LAYOUT_PATH = path.join(__dirname, '..', 'app', 'layout.tsx');

describe('App layout — no RuntoonSharePrompt auto-popup', () => {
  const source = fs.readFileSync(LAYOUT_PATH, 'utf8');

  test('does not render <RuntoonSharePrompt /> as a JSX element', () => {
    const mountMatches = source.match(/<RuntoonSharePrompt[\s/>]/g) ?? [];
    expect(mountMatches).toHaveLength(0);
  });

  test('does not actively import RuntoonSharePrompt', () => {
    // Strip block comments and line comments before scanning so the
    // archived "// import { RuntoonSharePrompt }" reference doesn't
    // count as an active import.
    const stripped = source
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .split('\n')
      .map((line) => line.replace(/\/\/.*$/, ''))
      .join('\n');

    const importMatches =
      stripped.match(/^\s*import\s+\{[^}]*RuntoonSharePrompt[^}]*\}\s+from/gm) ?? [];
    expect(importMatches).toHaveLength(0);
  });
});
