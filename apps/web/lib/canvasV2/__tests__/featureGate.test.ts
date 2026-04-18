import { isCanvasV2Allowed, canvasV2Allowlist } from '../featureGate';

describe('canvas v2 feature gate', () => {
  const ORIGINAL_ENV = process.env.NEXT_PUBLIC_CANVAS_V2_ALLOWLIST;

  afterEach(() => {
    if (ORIGINAL_ENV === undefined) {
      delete process.env.NEXT_PUBLIC_CANVAS_V2_ALLOWLIST;
    } else {
      process.env.NEXT_PUBLIC_CANVAS_V2_ALLOWLIST = ORIGINAL_ENV;
    }
  });

  it('allows the founder by default', () => {
    delete process.env.NEXT_PUBLIC_CANVAS_V2_ALLOWLIST;
    expect(isCanvasV2Allowed('mbshaf@gmail.com')).toBe(true);
  });

  it('is case-insensitive on email', () => {
    delete process.env.NEXT_PUBLIC_CANVAS_V2_ALLOWLIST;
    expect(isCanvasV2Allowed('MBshaf@Gmail.com')).toBe(true);
  });

  it('blocks every other email', () => {
    delete process.env.NEXT_PUBLIC_CANVAS_V2_ALLOWLIST;
    expect(isCanvasV2Allowed('demo@strideiq.run')).toBe(false);
    expect(isCanvasV2Allowed('anyone.else@example.com')).toBe(false);
  });

  it('blocks null / undefined / empty', () => {
    delete process.env.NEXT_PUBLIC_CANVAS_V2_ALLOWLIST;
    expect(isCanvasV2Allowed(null)).toBe(false);
    expect(isCanvasV2Allowed(undefined)).toBe(false);
    expect(isCanvasV2Allowed('')).toBe(false);
  });

  it('respects NEXT_PUBLIC_CANVAS_V2_ALLOWLIST override (replaces default)', () => {
    process.env.NEXT_PUBLIC_CANVAS_V2_ALLOWLIST = 'a@x.com, b@y.com';
    expect(canvasV2Allowlist()).toEqual(['a@x.com', 'b@y.com']);
    expect(isCanvasV2Allowed('a@x.com')).toBe(true);
    expect(isCanvasV2Allowed('b@y.com')).toBe(true);
    // Default founder is replaced, not merged.
    expect(isCanvasV2Allowed('mbshaf@gmail.com')).toBe(false);
  });

  it('handles whitespace in override', () => {
    process.env.NEXT_PUBLIC_CANVAS_V2_ALLOWLIST = '  a@x.com  ,   b@y.com  ';
    expect(canvasV2Allowlist()).toEqual(['a@x.com', 'b@y.com']);
  });

  it('treats empty override as falling back to default', () => {
    process.env.NEXT_PUBLIC_CANVAS_V2_ALLOWLIST = '';
    expect(isCanvasV2Allowed('mbshaf@gmail.com')).toBe(true);
  });
});
