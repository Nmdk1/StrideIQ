/**
 * SessionLogger contract:
 *   - Save button stays disabled until at least one set has an exercise.
 *   - "Repeat set" copies the exercise + reps + weight forward.
 *   - Save POSTs the right payload (lbs converted to kg) and routes to
 *     the new session detail page.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { SessionLogger } from '../SessionLogger';
import { strengthService } from '@/lib/api/services/strength';

jest.mock('@/lib/api/services/strength', () => {
  const actual = jest.requireActual('@/lib/api/services/strength');
  return {
    ...actual,
    strengthService: {
      ...actual.strengthService,
      createSession: jest.fn(),
      searchExercises: jest.fn(),
    },
  };
});

const push = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push, back: jest.fn() }),
}));

const mockedCreate = strengthService.createSession as jest.MockedFunction<
  typeof strengthService.createSession
>;
const mockedSearch = strengthService.searchExercises as jest.MockedFunction<
  typeof strengthService.searchExercises
>;

function renderWithClient(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('SessionLogger', () => {
  beforeEach(() => {
    push.mockReset();
    mockedCreate.mockReset();
    mockedSearch.mockReset();
    mockedSearch.mockResolvedValue({
      results: [
        {
          name: 'deadlift',
          movement_pattern: 'hinge',
          muscle_group: 'posterior chain',
          is_unilateral: false,
        },
      ],
      recent: [],
    });
  });

  test('save button is disabled until a set has an exercise name', () => {
    renderWithClient(<SessionLogger />);
    const btn = screen.getByRole('button', { name: /save session/i });
    expect(btn).toBeDisabled();
  });

  test('repeat set carries exercise, reps, and weight forward', async () => {
    renderWithClient(<SessionLogger />);

    fireEvent.click(screen.getByRole('button', { name: /pick exercise/i }));
    const row = await screen.findByText('deadlift');
    fireEvent.click(row);

    const inputs = screen.getAllByRole('textbox');
    const reps = inputs.find((i) =>
      i.previousElementSibling?.textContent?.toLowerCase().includes('reps'),
    )!;
    const weight = inputs.find((i) =>
      i.previousElementSibling?.textContent?.toLowerCase().includes('weight'),
    )!;
    fireEvent.change(reps, { target: { value: '5' } });
    fireEvent.change(weight, { target: { value: '225' } });

    fireEvent.click(screen.getByRole('button', { name: /repeat set/i }));

    expect(screen.getAllByText('deadlift').length).toBeGreaterThanOrEqual(2);
    const repsAfter = screen
      .getAllByRole('textbox')
      .filter((i) =>
        i.previousElementSibling?.textContent?.toLowerCase().includes('reps'),
      );
    expect(repsAfter[1]).toHaveValue('5');
  });

  test('save converts lbs to kg and routes to detail page', async () => {
    mockedCreate.mockResolvedValue({
      id: 'sess-123',
      athlete_id: 'a',
      start_time: new Date().toISOString(),
      duration_s: null,
      name: null,
      sport: 'strength',
      source: 'manual',
      sets: [],
      set_count: 1,
      total_volume_kg: null,
      movement_patterns: [],
    });

    renderWithClient(<SessionLogger />);

    fireEvent.click(screen.getByRole('button', { name: /pick exercise/i }));
    fireEvent.click(await screen.findByText('deadlift'));

    const inputs = screen.getAllByRole('textbox');
    const reps = inputs.find((i) =>
      i.previousElementSibling?.textContent?.toLowerCase().includes('reps'),
    )!;
    const weight = inputs.find((i) =>
      i.previousElementSibling?.textContent?.toLowerCase().includes('weight'),
    )!;
    fireEvent.change(reps, { target: { value: '5' } });
    fireEvent.change(weight, { target: { value: '225' } });

    fireEvent.click(screen.getByRole('button', { name: /save session/i }));

    await waitFor(() => expect(mockedCreate).toHaveBeenCalledTimes(1));
    const payload = mockedCreate.mock.calls[0][0];
    expect(payload.sets).toHaveLength(1);
    expect(payload.sets[0].exercise_name).toBe('deadlift');
    expect(payload.sets[0].reps).toBe(5);
    // 225 lb * 0.45359237 ≈ 102.06 kg
    expect(payload.sets[0].weight_kg).toBeCloseTo(102.06, 1);

    await waitFor(() =>
      expect(push).toHaveBeenCalledWith('/strength/sessions/sess-123'),
    );
  });
});
