/**
 * Founder-mandated invariant: the feedback modal must never re-pop after
 * the athlete has filed feedback.  These tests pin down the trigger hook
 * that decides auto-open behaviour.
 *
 * The four cases that matter:
 *   1. Incomplete + recent + never-shown  → auto-open
 *   2. Incomplete + recent + already-shown → DO NOT auto-open (glitch guard)
 *   3. Complete (any age, any localStorage) → DO NOT auto-open (glitch guard)
 *   4. Incomplete but old (> maxAgeDays)   → DO NOT auto-open
 */

import React from 'react';
import { renderHook, act } from '@testing-library/react';
import { useFeedbackTrigger } from '../useFeedbackTrigger';

const ACTIVITY_ID = 'act-123';

function isoDaysAgo(days: number): string {
  return new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();
}

describe('useFeedbackTrigger', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  test('auto-opens on a recent run that has no feedback yet', () => {
    const { result } = renderHook(() =>
      useFeedbackTrigger({
        activityId: ACTIVITY_ID,
        startTime: isoDaysAgo(1),
        isComplete: false,
        isLoading: false,
      }),
    );
    expect(result.current.shouldAutoOpen).toBe(true);
  });

  test('once shown, never auto-opens again — even on rerender', () => {
    const { result, rerender } = renderHook(() =>
      useFeedbackTrigger({
        activityId: ACTIVITY_ID,
        startTime: isoDaysAgo(1),
        isComplete: false,
        isLoading: false,
      }),
    );
    expect(result.current.shouldAutoOpen).toBe(true);

    act(() => {
      result.current.markShown();
    });
    expect(result.current.shouldAutoOpen).toBe(false);

    rerender();
    expect(result.current.shouldAutoOpen).toBe(false);
  });

  test('backend completion overrides localStorage absence', () => {
    // The athlete completed feedback on another device — backend says
    // complete even though this device has no localStorage flag yet.
    // We must NOT pop the modal in that case.
    const { result } = renderHook(() =>
      useFeedbackTrigger({
        activityId: ACTIVITY_ID,
        startTime: isoDaysAgo(1),
        isComplete: true,
        isLoading: false,
      }),
    );
    expect(result.current.shouldAutoOpen).toBe(false);
  });

  test('does not auto-open while completion is still loading', () => {
    const { result } = renderHook(() =>
      useFeedbackTrigger({
        activityId: ACTIVITY_ID,
        startTime: isoDaysAgo(1),
        isComplete: false,
        isLoading: true,
      }),
    );
    expect(result.current.shouldAutoOpen).toBe(false);
  });

  test('does not auto-open for runs older than maxAgeDays', () => {
    const { result } = renderHook(() =>
      useFeedbackTrigger({
        activityId: ACTIVITY_ID,
        startTime: isoDaysAgo(60),
        isComplete: false,
        isLoading: false,
        maxAgeDays: 14,
      }),
    );
    expect(result.current.shouldAutoOpen).toBe(false);
  });

  test('does not auto-open when start time is missing', () => {
    const { result } = renderHook(() =>
      useFeedbackTrigger({
        activityId: ACTIVITY_ID,
        startTime: null,
        isComplete: false,
        isLoading: false,
      }),
    );
    expect(result.current.shouldAutoOpen).toBe(false);
  });

  test('localStorage flag is per activity, not global', () => {
    // Mark activity A as shown.
    const { result: resultA } = renderHook(() =>
      useFeedbackTrigger({
        activityId: 'act-A',
        startTime: isoDaysAgo(1),
        isComplete: false,
        isLoading: false,
      }),
    );
    act(() => {
      resultA.current.markShown();
    });
    expect(resultA.current.shouldAutoOpen).toBe(false);

    // Activity B should still auto-open.
    const { result: resultB } = renderHook(() =>
      useFeedbackTrigger({
        activityId: 'act-B',
        startTime: isoDaysAgo(1),
        isComplete: false,
        isLoading: false,
      }),
    );
    expect(resultB.current.shouldAutoOpen).toBe(true);
  });
});
