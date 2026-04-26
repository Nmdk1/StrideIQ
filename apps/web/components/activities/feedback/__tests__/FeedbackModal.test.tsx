/**
 * FeedbackModal tests focus on the founder-mandated invariants:
 *
 *   • Save & Close is disabled until all three sections have a value.
 *   • The modal cannot be dismissed without saving (no X button, no
 *     escape-to-close, no backdrop-to-close).
 *   • A successful save fires onSaved (which the page uses to close).
 *   • A failed save preserves the athlete's selections so they can retry
 *     — never close optimistically and lose data.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { FeedbackModal } from '../FeedbackModal';
// Module-level jest.fn instances so the jest.mock factory below can
// reference them via closure (instead of requiring a `require()` to
// pull the mocked module back out, which Next's strict ESLint config
// forbids via @typescript-eslint/no-require-imports and no-var-requires).
const mockGet = jest.fn();
const mockPost = jest.fn();
const mockPut = jest.fn();

jest.mock('@/lib/api/client', () => ({
  apiClient: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
    put: (...args: unknown[]) => mockPut(...args),
  },
}));

function renderModal(overrides: Partial<React.ComponentProps<typeof FeedbackModal>> = {}) {
  const onSaved = jest.fn();
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  const props: React.ComponentProps<typeof FeedbackModal> = {
    activityId: 'act-1',
    open: true,
    existingReflection: null,
    existingFeedback: null,
    existingWorkoutType: null,
    onSaved,
    ...overrides,
  };

  const utils = render(
    <QueryClientProvider client={queryClient}>
      <FeedbackModal {...props} />
    </QueryClientProvider>,
  );
  return { ...utils, onSaved, queryClient };
}

beforeEach(() => {
  mockGet.mockReset();
  mockPost.mockReset();
  mockPut.mockReset();
  mockGet.mockResolvedValue({
    options: [
      { value: 'easy_run', label: 'Easy Run', zone: 'recovery', description: 'Easy aerobic' },
      { value: 'tempo_run', label: 'Tempo Run', zone: 'stamina', description: 'Sustained threshold' },
    ],
  });
});

describe('FeedbackModal — gating', () => {
  test('Save & Close is disabled when no inputs have been chosen', () => {
    renderModal();
    const save = screen.getByRole('button', { name: /Save & Close/i });
    expect(save).toBeDisabled();
  });

  test('Save & Close enables only after reflection + RPE + workout type are set', async () => {
    renderModal({
      existingWorkoutType: {
        activity_id: 'act-1',
        workout_type: 'easy_run',
        workout_zone: 'recovery',
        workout_confidence: 0.9,
        is_user_override: false,
      },
    });

    const save = screen.getByRole('button', { name: /Save & Close/i });
    expect(save).toBeDisabled();

    // Pick reflection.
    fireEvent.click(screen.getByRole('button', { name: /Harder than expected/i }));
    expect(save).toBeDisabled();

    // Pick RPE 7.
    fireEvent.click(screen.getByRole('button', { name: '7' }));
    expect(save).toBeDisabled();

    // Confirm workout type.
    fireEvent.click(screen.getByRole('button', { name: /Looks right/i }));

    await waitFor(() => expect(save).not.toBeDisabled());
  });
});

describe('FeedbackModal — dismissal', () => {
  test('renders no escape-hatch buttons (founder requirement: not skippable)', () => {
    renderModal();
    // The only "close" affordance permitted is the Save & Close primary
    // action — that one DOES include the word close, by design.  But there
    // must be no Cancel, no Skip, no Maybe Later, no bare X.
    expect(screen.queryByRole('button', { name: /^cancel$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /maybe later/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^skip/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /dismiss/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^×$|^x$/i })).not.toBeInTheDocument();
  });
});

describe('FeedbackModal — save flow', () => {
  test('successful save calls all three endpoints then fires onSaved', async () => {
    mockPost.mockResolvedValueOnce({}); // reflection
    mockPost.mockResolvedValueOnce({}); // feedback
    mockPut.mockResolvedValueOnce({}); // workout-type (PUT only fires when dirty)

    const { onSaved } = renderModal({
      existingWorkoutType: {
        activity_id: 'act-1',
        workout_type: 'easy_run',
        workout_zone: 'recovery',
        workout_confidence: 0.9,
        is_user_override: false,
      },
    });

    fireEvent.click(screen.getByRole('button', { name: /As expected/i }));
    fireEvent.click(screen.getByRole('button', { name: '5' }));
    fireEvent.click(screen.getByRole('button', { name: /Looks right/i }));

    const save = screen.getByRole('button', { name: /Save & Close/i });
    await waitFor(() => expect(save).not.toBeDisabled());
    fireEvent.click(save);

    await waitFor(() => {
      expect(onSaved).toHaveBeenCalledTimes(1);
    });

    // Reflection POST + feedback POST.  Workout type is unchanged (Looks
    // right with no value change) so no PUT — this is a feature, not a
    // bug: we never write redundantly to the backend.
    expect(mockPost).toHaveBeenCalledWith(
      '/v1/activities/act-1/reflection',
      { response: 'expected' },
    );
    expect(mockPost).toHaveBeenCalledWith(
      '/v1/activity-feedback',
      { activity_id: 'act-1', perceived_effort: 5 },
    );
    expect(mockPut).not.toHaveBeenCalled();
  });

  test('failed save leaves the modal open with selections intact', async () => {
    mockPost.mockRejectedValueOnce(new Error('network down'));

    const { onSaved } = renderModal({
      existingWorkoutType: {
        activity_id: 'act-1',
        workout_type: 'easy_run',
        workout_zone: 'recovery',
        workout_confidence: 0.9,
        is_user_override: false,
      },
    });

    fireEvent.click(screen.getByRole('button', { name: /Easier than expected/i }));
    fireEvent.click(screen.getByRole('button', { name: '4' }));
    fireEvent.click(screen.getByRole('button', { name: /Looks right/i }));

    const save = screen.getByRole('button', { name: /Save & Close/i });
    await waitFor(() => expect(save).not.toBeDisabled());
    fireEvent.click(save);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/Save failed/i);
    });

    expect(onSaved).not.toHaveBeenCalled();

    // Selections preserved — RPE 4 still highlighted, save button still
    // available for retry.
    const rpe4 = screen.getByRole('button', { name: '4' });
    expect(rpe4).toHaveAttribute('aria-pressed', 'true');
    expect(save).not.toBeDisabled();
  });

  test('edit-later flow pre-fills from existing values and treats workout type as already acked', async () => {
    renderModal({
      existingReflection: {
        id: 'r-1',
        activity_id: 'act-1',
        response: 'harder',
        created_at: '2026-04-15T00:00:00Z',
      },
      existingFeedback: {
        id: 'f-1',
        activity_id: 'act-1',
        athlete_id: 'a-1',
        perceived_effort: 8,
        submitted_at: '2026-04-15T00:00:00Z',
        created_at: '2026-04-15T00:00:00Z',
        updated_at: '2026-04-15T00:00:00Z',
      },
      existingWorkoutType: {
        activity_id: 'act-1',
        workout_type: 'tempo_run',
        workout_zone: 'stamina',
        workout_confidence: 0.85,
        is_user_override: true,
      },
    });

    // Reflection 'harder' is pre-selected.
    expect(screen.getByRole('button', { name: /Harder than expected/i })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    // RPE 8 is pre-selected.
    expect(screen.getByRole('button', { name: '8' })).toHaveAttribute('aria-pressed', 'true');
    // Workout type already acked → Save is immediately enabled.
    const save = screen.getByRole('button', { name: /Save & Close/i });
    await waitFor(() => expect(save).not.toBeDisabled());
  });
});
