/**
 * ExercisePicker contract:
 *   - Search input is auto-focused on open.
 *   - "Recent" section shows when query is empty and recents exist.
 *   - Free-text fallback row appears for unknown queries so logging
 *     is never blocked by a missing taxonomy entry.
 *   - Selecting a row calls onSelect with the entry and onClose.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { ExercisePicker } from '../ExercisePicker';
import { strengthService } from '@/lib/api/services/strength';

jest.mock('@/lib/api/services/strength', () => {
  const actual = jest.requireActual('@/lib/api/services/strength');
  return {
    ...actual,
    strengthService: {
      ...actual.strengthService,
      searchExercises: jest.fn(),
    },
  };
});

const mockedSearch = strengthService.searchExercises as jest.MockedFunction<
  typeof strengthService.searchExercises
>;

function renderWithClient(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('ExercisePicker', () => {
  beforeEach(() => {
    mockedSearch.mockReset();
  });

  test('renders nothing when not open', () => {
    mockedSearch.mockResolvedValue({ results: [], recent: [] });
    const { container } = renderWithClient(
      <ExercisePicker open={false} onClose={() => {}} onSelect={() => {}} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  test('shows Recent section when query is empty and recents exist', async () => {
    mockedSearch.mockResolvedValue({
      results: [
        {
          name: 'back squat',
          movement_pattern: 'squat',
          muscle_group: 'quads',
          is_unilateral: false,
        },
      ],
      recent: [
        {
          name: 'deadlift',
          movement_pattern: 'hinge',
          muscle_group: 'posterior chain',
          is_unilateral: false,
        },
      ],
    });
    renderWithClient(
      <ExercisePicker open={true} onClose={() => {}} onSelect={() => {}} />,
    );
    await waitFor(() =>
      expect(screen.getByText('deadlift')).toBeInTheDocument(),
    );
    expect(screen.getByText('Recent')).toBeInTheDocument();
  });

  test('surfaces a free-text fallback row for unknown queries', async () => {
    mockedSearch.mockResolvedValue({
      results: [],
      recent: [],
    });
    renderWithClient(
      <ExercisePicker open={true} onClose={() => {}} onSelect={() => {}} />,
    );

    const input = screen.getByPlaceholderText(/search or type/i);
    fireEvent.change(input, { target: { value: 'sandbag carry' } });

    await waitFor(() =>
      expect(
        screen.getByText(
          (_, node) =>
            node?.tagName === 'P' &&
            (node?.textContent ?? '')
              .toLowerCase()
              .includes('use “sandbag carry”'),
        ),
      ).toBeInTheDocument(),
    );
  });

  test('selecting a row calls onSelect and onClose', async () => {
    mockedSearch.mockResolvedValue({
      results: [
        {
          name: 'overhead press',
          movement_pattern: 'push_vertical',
          muscle_group: 'shoulders',
          is_unilateral: false,
        },
      ],
      recent: [],
    });
    const onSelect = jest.fn();
    const onClose = jest.fn();
    renderWithClient(
      <ExercisePicker open={true} onClose={onClose} onSelect={onSelect} />,
    );

    const row = await screen.findByText('overhead press');
    fireEvent.click(row);

    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'overhead press' }),
    );
    expect(onClose).toHaveBeenCalled();
  });
});
