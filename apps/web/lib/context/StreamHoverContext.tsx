'use client';

import { createContext, useContext, useState, useCallback, ReactNode } from 'react';

interface StreamHoverState {
  hoveredIndex: number | null;
  setHoveredIndex: (index: number | null) => void;
}

const StreamHoverContext = createContext<StreamHoverState>({
  hoveredIndex: null,
  setHoveredIndex: () => {},
});

export function StreamHoverProvider({ children }: { children: ReactNode }) {
  const [hoveredIndex, setIdx] = useState<number | null>(null);
  const setHoveredIndex = useCallback((index: number | null) => setIdx(index), []);
  return (
    <StreamHoverContext.Provider value={{ hoveredIndex, setHoveredIndex }}>
      {children}
    </StreamHoverContext.Provider>
  );
}

export function useStreamHover() {
  return useContext(StreamHoverContext);
}
