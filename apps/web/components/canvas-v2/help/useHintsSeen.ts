'use client';

/**
 * Tiny localStorage flag that lets us show first-visit hints once and then
 * stay quiet. `reset` lets the persistent help button re-trigger the tour.
 */

import { useCallback, useEffect, useState } from 'react';

const KEY = 'canvasV2:hintsSeen';

export function useHintsSeen() {
  const [seen, setSeen] = useState<boolean | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined') {
      setSeen(true);
      return;
    }
    setSeen(window.localStorage.getItem(KEY) === '1');
  }, []);

  const markSeen = useCallback(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(KEY, '1');
    }
    setSeen(true);
  }, []);

  const reset = useCallback(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(KEY);
    }
    setSeen(false);
  }, []);

  return { seen, markSeen, reset };
}
