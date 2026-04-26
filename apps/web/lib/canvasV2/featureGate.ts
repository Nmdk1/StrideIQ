/**
 * Run Shape Canvas v2 — feature gate.
 *
 * SANDBOX. Anything inside `apps/web/{app,components,lib}/canvasV2*` or
 * `apps/web/app/activities/[id]/canvas-v2` is experimental and gated to the
 * founder's account in production. Removing the gate is intentional and
 * requires a separate decision.
 *
 * Default allow-list: just the founder. Override via NEXT_PUBLIC_CANVAS_V2_ALLOWLIST
 * (comma-separated emails) for local dev / staging without code changes.
 */

const DEFAULT_ALLOWLIST = ['mbshaf@gmail.com'];

function parseAllowlist(raw: string | undefined | null): string[] {
  if (!raw) return [];
  return raw
    .split(',')
    .map((e) => e.trim().toLowerCase())
    .filter((e) => e.length > 0);
}

export function canvasV2Allowlist(): string[] {
  // NEXT_PUBLIC_ vars are inlined at build time, so this is safe in client code.
  const overrideRaw =
    typeof process !== 'undefined'
      ? process.env.NEXT_PUBLIC_CANVAS_V2_ALLOWLIST
      : undefined;
  const override = parseAllowlist(overrideRaw);
  if (override.length > 0) return override;
  return DEFAULT_ALLOWLIST.map((e) => e.toLowerCase());
}

export function isCanvasV2Allowed(email: string | null | undefined): boolean {
  if (!email) return false;
  return canvasV2Allowlist().includes(email.toLowerCase());
}
