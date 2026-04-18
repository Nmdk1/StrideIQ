'use client';

/**
 * useElementWidth — observe a div's width with ResizeObserver, with SSR-safe
 * defaults. Used by the SVG streams stack which needs an explicit pixel width.
 */

import { useEffect, useRef, useState } from 'react';

export function useElementWidth<T extends HTMLElement = HTMLDivElement>(): {
  ref: React.RefObject<T>;
  width: number;
} {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState<number>(0);

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const w = Math.round(entry.contentRect.width);
      setWidth((prev) => (prev === w ? prev : w));
    });
    ro.observe(el);
    setWidth(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  return { ref, width };
}
