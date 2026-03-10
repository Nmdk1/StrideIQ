import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

jest.mock('@/lib/hooks/useAuth', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

jest.mock('@tanstack/react-query', () => ({
  useQuery: () => ({
    data: {
      history: [
        { date: '2026-03-06', ctl: 42, atl: 48, tsb: -6 },
        { date: '2026-03-07', ctl: 43, atl: 47, tsb: -4 },
      ],
    },
  }),
}));

jest.mock('@/components/ui/tooltip', () => ({
  TooltipProvider: ({ children }: any) => <>{children}</>,
  Tooltip: ({ children }: any) => <>{children}</>,
  TooltipTrigger: ({ children }: any) => <>{children}</>,
  TooltipContent: ({ children }: any) => <>{children}</>,
}));

jest.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
  ComposedChart: ({ children }: any) => <div>{children}</div>,
  CartesianGrid: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  Tooltip: () => <div />,
  Area: ({ name }: any) => <div>{name}</div>,
  Line: ({ name }: any) => <div>{name}</div>,
}));

import { CompactPMC } from '@/components/home/CompactPMC';

describe('CompactPMC legend labels', () => {
  test('uses athlete-facing labels without CTL/ATL/TSB acronyms', () => {
    const { container } = render(<CompactPMC />);

    expect(screen.getAllByText('Fitness').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Fatigue').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Form').length).toBeGreaterThan(0);

    expect(container).not.toHaveTextContent('CTL');
    expect(container).not.toHaveTextContent('ATL');
    expect(container).not.toHaveTextContent('TSB');
    expect(container).not.toHaveTextContent('Fitness (CTL)');
    expect(container).not.toHaveTextContent('Fatigue (ATL)');
    expect(container).not.toHaveTextContent('Form (TSB)');
  });
});
