import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

import { ProposalCard, type ProposalCardProposal } from '@/components/coach/ProposalCard';

const postMock = jest.fn();
jest.mock('@/lib/api/client', () => ({
  apiClient: {
    post: (...args: any[]) => postMock(...args),
  },
}));

describe('ProposalCard', () => {
  beforeEach(() => {
    postMock.mockReset();
  });

  const baseProposal: ProposalCardProposal = {
    proposal_id: 'prop_1',
    status: 'proposed',
    plan_name: '10K Build',
    reason: 'Move my long run earlier this week.',
    diff_preview: [
      {
        plan_id: 'plan_1',
        workout_id: 'w_1',
        before: {
          id: 'w_1',
          scheduled_date: '2026-01-26',
          title: 'Long Run',
          workout_type: 'long_run',
          target_distance_km: 20,
          target_duration_minutes: 120,
          skipped: false,
        },
        after: {
          id: 'w_1',
          scheduled_date: '2026-01-25',
          title: 'Long Run',
          workout_type: 'long_run',
          target_distance_km: 20,
          target_duration_minutes: 120,
          skipped: false,
        },
      },
    ],
    risk_notes: ['Swapping days can change recovery spacing between key sessions.'],
    created_at: '2026-01-25T00:00:00Z',
  };

  it('renders header, reason, diff preview, risk notes, and action buttons', () => {
    render(<ProposalCard proposal={baseProposal} />);

    expect(screen.getByText(/Proposed changes to/i)).toBeInTheDocument();
    expect(screen.getByText('10K Build')).toBeInTheDocument();
    expect(screen.getByText('Reason')).toBeInTheDocument();
    expect(screen.getByText('Move my long run earlier this week.')).toBeInTheDocument();

    expect(screen.getByText('Diff preview')).toBeInTheDocument();
    expect(screen.getAllByText('Before').length).toBeGreaterThan(0);
    expect(screen.getAllByText('After').length).toBeGreaterThan(0);

    expect(screen.getByText('Risk notes')).toBeInTheDocument();
    expect(screen.getByText(/recovery spacing/i)).toBeInTheDocument();

    expect(screen.getByRole('button', { name: 'Confirm & Apply' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reject' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ask follow-up' })).toBeInTheDocument();
  });

  it('calls confirm endpoint and shows apply receipt toast/summary', async () => {
    postMock.mockImplementation((path: string) => {
      if (path === '/v2/coach/actions/prop_1/confirm') {
        return Promise.resolve({
          proposal_id: 'prop_1',
          status: 'applied',
          confirmed_at: '2026-01-25T00:00:05Z',
          applied_at: '2026-01-25T00:00:06Z',
          receipt: { actions_applied: 1, changes: baseProposal.diff_preview },
          error: null,
        });
      }
      return Promise.reject(new Error(`unexpected POST ${path}`));
    });

    render(<ProposalCard proposal={baseProposal} />);
    fireEvent.click(screen.getByRole('button', { name: 'Confirm & Apply' }));

    await waitFor(() => {
      expect(postMock).toHaveBeenCalled();
    });

    expect(await screen.findByText('Apply receipt')).toBeInTheDocument();
    expect(await screen.findByText(/Applied 1 action/i)).toBeInTheDocument();
  });

  it('calls reject endpoint and updates UI state to rejected', async () => {
    postMock.mockImplementation((path: string) => {
      if (path === '/v2/coach/actions/prop_1/reject') {
        return Promise.resolve({ proposal_id: 'prop_1', status: 'rejected', rejected_at: '2026-01-25T00:00:06Z' });
      }
      return Promise.reject(new Error(`unexpected POST ${path}`));
    });

    render(<ProposalCard proposal={baseProposal} />);
    fireEvent.click(screen.getByRole('button', { name: 'Reject' }));

    await waitFor(() => {
      expect(postMock).toHaveBeenCalled();
    });

    // Status label is split across nodes ("Status:" + <span>rejected</span>)
    expect(await screen.findByText('rejected')).toBeInTheDocument();
  });
});

