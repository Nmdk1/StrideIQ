/**
 * A3: Moment Narratives — Frontend Tests
 *
 * Verifies:
 * - Narrative displayed when present (coaching sentence preferred)
 * - Fallback to metric label when narrative is null
 * - Metric value hidden when narrative is present
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { CoachableMoments } from '@/components/activities/rsi/CoachableMoments';

jest.mock('@/lib/context/UnitsContext', () => ({
  useUnits: () => ({
    units: 'imperial',
    formatDistance: (m: number) => `${(m / 1609.34).toFixed(1)} mi`,
    formatPace: (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}/mi`,
    formatElevation: (m: number) => `${Math.round(m * 3.28084)} ft`,
    distanceUnitShort: 'mi',
    paceUnit: 'min/mi',
  }),
}));

const momentWithNarrative = {
  type: 'pace_surge',
  index: 100,
  time_s: 2520,
  value: 15.3,
  context: 'Pace Surge',
  narrative: 'Your pace shifted from 5:30 to 4:45 at 42:00 as you opened up for the finish.',
};

const momentWithoutNarrative = {
  type: 'cadence_drop',
  index: 200,
  time_s: 1800,
  value: 6.0,
  context: 'Cadence Drop',
  narrative: null,
};

const momentWithoutNarrativeOrContext = {
  type: 'cardiac_drift_onset',
  index: 300,
  time_s: 3000,
  value: 4.2,
  context: null,
  narrative: null,
};

describe('A3: Moment Narratives', () => {
  test('narrative displayed when present', () => {
    render(
      <CoachableMoments
        moments={[momentWithNarrative]}
        confidence={0.9}
      />
    );

    expect(screen.getByText(/Your pace shifted from 5:30 to 4:45/)).toBeInTheDocument();
    // Metric value should NOT be shown when narrative exists
    expect(screen.queryByText('15.3')).not.toBeInTheDocument();
  });

  test('fallback to context label when narrative is null', () => {
    render(
      <CoachableMoments
        moments={[momentWithoutNarrative]}
        confidence={0.9}
      />
    );

    expect(screen.getByText('Cadence Drop')).toBeInTheDocument();
    // Metric value SHOULD be shown in fallback mode
    expect(screen.getByText('6.0')).toBeInTheDocument();
  });

  test('fallback to formatted type when narrative and context are both null', () => {
    render(
      <CoachableMoments
        moments={[momentWithoutNarrativeOrContext]}
        confidence={0.9}
      />
    );

    // formatMomentType converts "cardiac_drift_onset" → "Cardiac Drift Onset"
    expect(screen.getByText('Cardiac Drift Onset')).toBeInTheDocument();
    expect(screen.getByText('4.2')).toBeInTheDocument();
  });

  test('mixed: narrative and fallback moments render together', () => {
    render(
      <CoachableMoments
        moments={[momentWithNarrative, momentWithoutNarrative]}
        confidence={0.9}
      />
    );

    // First moment: narrative
    expect(screen.getByText(/Your pace shifted/)).toBeInTheDocument();
    // Second moment: fallback
    expect(screen.getByText('Cadence Drop')).toBeInTheDocument();
  });

  test('confidence gate still applies with narratives', () => {
    const { container } = render(
      <CoachableMoments
        moments={[momentWithNarrative]}
        confidence={0.5}  // Below 0.8 threshold
      />
    );

    expect(container.innerHTML).toBe('');
  });
});
