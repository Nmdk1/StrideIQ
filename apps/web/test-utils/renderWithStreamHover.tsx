/**
 * Wrap RunShapeCanvas (and siblings) with StreamHoverProvider — required because
 * hover index lives in context for splits ↔ chart ↔ map linkage.
 */
import React from 'react';
import { render, type RenderOptions } from '@testing-library/react';
import { StreamHoverProvider } from '@/lib/context/StreamHoverContext';

export function renderWithStreamHover(
  ui: React.ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>,
) {
  return render(ui, {
    ...options,
    wrapper: ({ children }) => <StreamHoverProvider>{children}</StreamHoverProvider>,
  });
}
