/**
 * SymptomLogger contract:
 *   - Severity buttons render the runner-language ladder (niggle / ache /
 *     pain / injury) and one is selected by default.
 *   - Submitting POSTs the right payload; the form preserves the
 *     "system never auto-classifies" contract by sending exactly what
 *     the athlete chose.
 *   - Active vs resolved sections render off the API list response.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { SymptomLogger } from '../SymptomLogger';
import { symptomService } from '@/lib/api/services/symptoms';

jest.mock('@/lib/api/services/symptoms', () => {
  const actual = jest.requireActual('@/lib/api/services/symptoms');
  return {
    ...actual,
    symptomService: {
      list: jest.fn(),
      create: jest.fn(),
      update: jest.fn(),
      remove: jest.fn(),
    },
  };
});

const mockList = symptomService.list as jest.MockedFunction<
  typeof symptomService.list
>;
const mockCreate = symptomService.create as jest.MockedFunction<
  typeof symptomService.create
>;

function renderWithClient(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('SymptomLogger', () => {
  beforeEach(() => {
    mockList.mockReset();
    mockCreate.mockReset();
  });

  test('renders all four severity tiers', async () => {
    mockList.mockResolvedValue({ active: [], history: [] });
    renderWithClient(<SymptomLogger />);
    expect(await screen.findByText('Niggle')).toBeInTheDocument();
    expect(screen.getByText('Ache')).toBeInTheDocument();
    expect(screen.getByText('Pain')).toBeInTheDocument();
    expect(screen.getByText('Injury')).toBeInTheDocument();
  });

  test('submit posts athlete-entered values verbatim', async () => {
    mockList.mockResolvedValue({ active: [], history: [] });
    mockCreate.mockResolvedValue({
      id: 's-1',
      body_area: 'left_calf',
      severity: 'pain',
      started_at: '2026-04-19',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
    renderWithClient(<SymptomLogger />);

    fireEvent.click(await screen.findByText('Pain'));
    fireEvent.click(screen.getByRole('button', { name: /log symptom/i }));

    await waitFor(() => expect(mockCreate).toHaveBeenCalledTimes(1));
    const payload = mockCreate.mock.calls[0][0];
    expect(payload.severity).toBe('pain');
    expect(payload.body_area).toBe('left_calf');
    expect(payload.started_at).toMatch(/\d{4}-\d{2}-\d{2}/);
  });

  test('renders active and resolved sections from the API response', async () => {
    mockList.mockResolvedValue({
      active: [
        {
          id: 'a-1',
          body_area: 'right_knee',
          severity: 'ache',
          started_at: '2026-04-15',
          resolved_at: null,
          triggered_by: 'long run',
          notes: null,
          created_at: '',
          updated_at: '',
        },
      ],
      history: [
        {
          id: 'h-1',
          body_area: 'left_calf',
          severity: 'niggle',
          started_at: '2026-03-01',
          resolved_at: '2026-03-05',
          triggered_by: null,
          notes: null,
          created_at: '',
          updated_at: '',
        },
      ],
    });
    renderWithClient(<SymptomLogger />);

    await waitFor(() =>
      expect(screen.getByText(/right knee/i)).toBeInTheDocument(),
    );
    await waitFor(() =>
      expect(screen.getByText(/left calf/i)).toBeInTheDocument(),
    );
    const headings = screen
      .getAllByRole('heading')
      .map((el) => el.textContent?.trim());
    expect(headings).toEqual(
      expect.arrayContaining([expect.stringMatching(/^Resolved$/)]),
    );
  });
});
