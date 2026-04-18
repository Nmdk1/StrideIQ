import React from 'react';
import { render, act } from '@testing-library/react';
import { ScrubProvider, useScrubState, clampScrub } from '../useScrubState';

describe('clampScrub', () => {
  it('returns null unchanged', () => {
    expect(clampScrub(null)).toBeNull();
  });

  it('clamps below 0 to 0', () => {
    expect(clampScrub(-0.5)).toBe(0);
    expect(clampScrub(-Infinity)).toBe(0);
  });

  it('clamps above 1 to 1', () => {
    expect(clampScrub(1.7)).toBe(1);
    expect(clampScrub(Infinity)).toBe(1);
  });

  it('passes valid values through', () => {
    expect(clampScrub(0)).toBe(0);
    expect(clampScrub(0.42)).toBe(0.42);
    expect(clampScrub(1)).toBe(1);
  });

  it('rejects NaN by returning null (defensive)', () => {
    expect(clampScrub(NaN)).toBeNull();
  });
});

describe('useScrubState (with provider)', () => {
  function captureContext() {
    const ref: { current: ReturnType<typeof useScrubState> | null } = { current: null };
    function Probe() {
      ref.current = useScrubState();
      return null;
    }
    return { Probe, ref };
  }

  it('starts with null position', () => {
    const { Probe, ref } = captureContext();
    render(
      <ScrubProvider>
        <Probe />
      </ScrubProvider>
    );
    expect(ref.current?.position).toBeNull();
  });

  it('sets and reads a normalized position', () => {
    const { Probe, ref } = captureContext();
    render(
      <ScrubProvider>
        <Probe />
      </ScrubProvider>
    );
    act(() => {
      ref.current?.setPosition(0.5);
    });
    expect(ref.current?.position).toBe(0.5);
  });

  it('clamps out-of-range values', () => {
    const { Probe, ref } = captureContext();
    render(
      <ScrubProvider>
        <Probe />
      </ScrubProvider>
    );
    act(() => {
      ref.current?.setPosition(2.5);
    });
    expect(ref.current?.position).toBe(1);
    act(() => {
      ref.current?.setPosition(-1);
    });
    expect(ref.current?.position).toBe(0);
  });

  it('clear() resets to null', () => {
    const { Probe, ref } = captureContext();
    render(
      <ScrubProvider>
        <Probe />
      </ScrubProvider>
    );
    act(() => {
      ref.current?.setPosition(0.3);
    });
    expect(ref.current?.position).toBe(0.3);
    act(() => {
      ref.current?.clear();
    });
    expect(ref.current?.position).toBeNull();
  });

  it('multiple consumers see the same position', () => {
    const refA: { current: ReturnType<typeof useScrubState> | null } = { current: null };
    const refB: { current: ReturnType<typeof useScrubState> | null } = { current: null };
    function ProbeA() {
      refA.current = useScrubState();
      return null;
    }
    function ProbeB() {
      refB.current = useScrubState();
      return null;
    }
    render(
      <ScrubProvider>
        <ProbeA />
        <ProbeB />
      </ScrubProvider>
    );
    act(() => {
      refA.current?.setPosition(0.7);
    });
    expect(refB.current?.position).toBe(0.7);
  });

  it('throws if used outside provider', () => {
    const { Probe } = captureContext();
    // jsdom logs the React error; suppress for this assertion only.
    const errSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(<Probe />)).toThrow(/ScrubProvider/);
    errSpy.mockRestore();
  });
});
