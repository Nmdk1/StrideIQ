/**
 * GarminEffortFallback enforces the founder rule: the athlete's own RPE
 * always wins. This card only appears when (a) we have a Garmin
 * self-eval and (b) the athlete has not entered their own. As soon as
 * the athlete reflects, this card hides.
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { GarminEffortFallback } from '../GarminEffortFallback';

describe('GarminEffortFallback', () => {
  test('renders nothing when athlete has logged their own RPE', () => {
    const { container } = render(
      <GarminEffortFallback
        garminPerceivedEffort={7}
        garminFeel="strong"
        athleteRpe={6}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  test('renders nothing when no Garmin self-eval is present', () => {
    const { container } = render(
      <GarminEffortFallback
        garminPerceivedEffort={null}
        garminFeel={null}
        athleteRpe={null}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  test('renders effort + feel when athlete has not reflected', () => {
    render(
      <GarminEffortFallback
        garminPerceivedEffort={7}
        garminFeel="strong"
        athleteRpe={null}
      />,
    );
    expect(screen.getByText('7')).toBeInTheDocument();
    expect(screen.getByText(/Strong/i)).toBeInTheDocument();
    expect(screen.getByText(/from your watch/i)).toBeInTheDocument();
    expect(screen.getByText(/Reflect on this run/i)).toBeInTheDocument();
  });

  test('renders feel alone when only feel is present', () => {
    render(
      <GarminEffortFallback
        garminPerceivedEffort={null}
        garminFeel="weak"
        athleteRpe={null}
      />,
    );
    expect(screen.getByText(/Weak/i)).toBeInTheDocument();
    expect(screen.queryByText('/ 10')).not.toBeInTheDocument();
  });

  test('hides when athleteRpe is 0 only if 0 is treated as not-set', () => {
    // RPE of 0 is not a valid score; treat as "not entered".
    render(
      <GarminEffortFallback
        garminPerceivedEffort={5}
        garminFeel={null}
        athleteRpe={0}
      />,
    );
    expect(screen.getByText('5')).toBeInTheDocument();
  });
});
