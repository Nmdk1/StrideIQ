'use client';

/**
 * Decides when the FeedbackModal should auto-open.
 *
 * Founder rule: feedback "needs to happen every run."  At the same time,
 * we don't want to ambush an athlete who is browsing months-old runs in
 * their history.  So:
 *
 *   1. The modal auto-opens once per device per activity (tracked in
 *      localStorage so refreshes don't re-pop after a successful save).
 *   2. Once feedback is complete in the backend, the modal never auto-opens
 *      again on any device — backend completion takes precedence over the
 *      localStorage flag.
 *   3. For activities older than `maxAgeDays` (default 14), the modal does
 *      not auto-open even if feedback is incomplete.  Athletes can still
 *      open it via the Reflect pill in the page chrome.
 *
 * The hook returns `shouldAutoOpen` plus a `markShown` callback that the
 * page calls once the modal has opened, so it doesn't reopen on the next
 * navigation within the same session if the athlete navigated away.
 */

import { useEffect, useState, useCallback } from 'react';

const STORAGE_KEY_PREFIX = 'feedbackModalShown:';
const DEFAULT_MAX_AGE_DAYS = 14;

interface UseFeedbackTriggerArgs {
  activityId: string;
  startTime: string | null | undefined;
  isComplete: boolean;
  isLoading: boolean;
  maxAgeDays?: number;
}

export function useFeedbackTrigger({
  activityId,
  startTime,
  isComplete,
  isLoading,
  maxAgeDays = DEFAULT_MAX_AGE_DAYS,
}: UseFeedbackTriggerArgs) {
  const [shouldAutoOpen, setShouldAutoOpen] = useState(false);

  useEffect(() => {
    if (isLoading) return;
    if (isComplete) {
      setShouldAutoOpen(false);
      return;
    }
    if (typeof window === 'undefined') return;

    const ageDays = computeAgeDays(startTime);
    if (ageDays === null || ageDays > maxAgeDays) {
      setShouldAutoOpen(false);
      return;
    }

    const key = `${STORAGE_KEY_PREFIX}${activityId}`;
    const alreadyShown = window.localStorage.getItem(key) === '1';
    setShouldAutoOpen(!alreadyShown);
  }, [activityId, startTime, isComplete, isLoading, maxAgeDays]);

  const markShown = useCallback(() => {
    if (typeof window === 'undefined') return;
    const key = `${STORAGE_KEY_PREFIX}${activityId}`;
    window.localStorage.setItem(key, '1');
    setShouldAutoOpen(false);
  }, [activityId]);

  return { shouldAutoOpen, markShown };
}

function computeAgeDays(startTime: string | null | undefined): number | null {
  if (!startTime) return null;
  const t = Date.parse(startTime);
  if (Number.isNaN(t)) return null;
  const ms = Date.now() - t;
  if (ms < 0) return 0;
  return ms / (1000 * 60 * 60 * 24);
}
