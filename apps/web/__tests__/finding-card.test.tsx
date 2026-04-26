import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';

import FindingCard, { getDomainVisual } from '@/components/findings/FindingCard';

describe('FindingCard', () => {
  const ARC_CIRCUMFERENCE = 2 * Math.PI * 22;

  test('arc fill scales with confirmations', () => {
    const { rerender } = render(
      <FindingCard
        text="Sleep consistency improved your long-run pace."
        domain="sleep"
        confidenceTier="strong"
        timesConfirmed={4}
      />
    );
    const earlyDash = screen.getByTestId('finding-arc-fill').getAttribute('stroke-dasharray') || '';

    rerender(
      <FindingCard
        text="Sleep consistency improved your long-run pace."
        domain="sleep"
        confidenceTier="strong"
        timesConfirmed={40}
      />
    );
    const lateDash = screen.getByTestId('finding-arc-fill').getAttribute('stroke-dasharray') || '';

    const earlyValue = Number((earlyDash.split(' ')[0] || '0'));
    const lateValue = Number((lateDash.split(' ')[0] || '0'));
    expect(lateValue).toBeGreaterThan(earlyValue);
  });

  test('minimum arc is visible with one confirmation', () => {
    render(
      <FindingCard
        text="Early pattern signal."
        domain="pace"
        confidenceTier="confirmed"
        timesConfirmed={1}
      />
    );
    const dashArray = screen.getByTestId('finding-arc-fill').getAttribute('stroke-dasharray') || '';
    const dashValue = Number((dashArray.split(' ')[0] || '0'));
    const minimumExpected = ARC_CIRCUMFERENCE * 0.12;
    expect(dashValue).toBeGreaterThanOrEqual(minimumExpected - 0.001);
  });

  test('maps domain to visual key', () => {
    expect(getDomainVisual('sleep').key).toBe('sleep');
    expect(getDomainVisual('hr').key).toBe('cardiac');
    expect(getDomainVisual('pace').key).toBe('pace');
    expect(getDomainVisual('heat').key).toBe('environmental');
    expect(getDomainVisual('volume').key).toBe('volume');
    expect(getDomainVisual('anything_else').key).toBe('general');
  });

  test('renders cold-start copy when no finding text', () => {
    render(<FindingCard activityCount={6} />);
    expect(screen.getByText(/Learning your patterns/i)).toBeInTheDocument();
    expect(screen.queryByTestId('finding-arc-fill')).not.toBeInTheDocument();
  });

  test('expand/collapse reveals evidence and ask-coach link', () => {
    render(
      <FindingCard
        text="Long runs in cool weather improve your next-day freshness."
        domain="environmental"
        confidenceTier="confirmed"
        timesConfirmed={12}
        evidence="Across 12 long runs, next-day soreness trended lower."
        implication="Use cooler windows when possible for key long runs."
        expandable
      />
    );

    expect(screen.queryByTestId('finding-expanded')).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId('finding-expand-toggle'));
    expect(screen.getByTestId('finding-expanded')).toBeInTheDocument();
    expect(screen.getByTestId('finding-ask-coach-link')).toHaveAttribute(
      'href',
      expect.stringContaining('/coach?q=')
    );

    fireEvent.click(screen.getByTestId('finding-expand-toggle'));
    expect(screen.queryByTestId('finding-expanded')).not.toBeInTheDocument();
  });
});

