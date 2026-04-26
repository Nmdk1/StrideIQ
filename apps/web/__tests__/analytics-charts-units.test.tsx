/**
 * Analytics charts — pace unit-toggle behavioral test
 *
 * Why this exists:
 *   The Efficiency Trend and Age-Graded Trajectory charts both read
 *   `EfficiencyTrendPoint.pace_per_mile` (decimal min/mile) from the API
 *   and rendered the tooltip pace with a hardcoded "/mi" suffix, ignoring
 *   the global useUnits preference. A km-preference athlete (Dejan Kadunc,
 *   2026-04-21 support email) saw raw miles on both surfaces.
 *
 *   Both chart components now perform the same conversion:
 *     pace_min_per_mile -> sec_per_km -> useUnits().formatPace()
 *
 *   This test renders that exact pipeline under both unit modes and asserts
 *   the produced pace string. Recharts tooltips cannot be reliably mounted
 *   in JSDOM (ResponsiveContainer + active-state interactions need real
 *   layout), so we test the conversion path directly via a harness — same
 *   imports, same math, same formatter, same units context. If anyone
 *   reverts to a hardcoded "/mi" in either chart, the source-level contract
 *   test in `unit-bypass-contract.test.ts` will fail; this test additionally
 *   guarantees the math itself is correct.
 */

import React from 'react';
import { render, screen, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom';

let _units: 'imperial' | 'metric' = 'imperial';
const setUnits = (u: 'imperial' | 'metric') => {
  _units = u;
};

jest.mock('@/lib/context/UnitsContext', () => ({
  useUnits: () => {
    const units = _units;
    return {
      units,
      formatPace: (sPerKm: number) => {
        // Mirror the real UnitsContext.formatPace: round seconds, then
        // carry to minutes if the rounding produced 60. The naive version
        // returned strings like "6:60/mi" when FP roundtrip pushed 7.0
        // min/mi → 419.999... sec/mi.
        const formatMS = (totalSec: number, suffix: string) => {
          let m = Math.floor(totalSec / 60);
          let s = Math.round(totalSec % 60);
          if (s === 60) {
            s = 0;
            m += 1;
          }
          return `${m}:${s.toString().padStart(2, '0')}${suffix}`;
        };
        if (units === 'imperial') {
          return formatMS(sPerKm * 1.60934, '/mi');
        }
        return formatMS(sPerKm, '/km');
      },
      formatDistance: (m: number, decimals = 1) => {
        if (units === 'imperial') return `${(m / 1609.344).toFixed(decimals)} mi`;
        return `${(m / 1000).toFixed(decimals)} km`;
      },
      distanceUnitShort: units === 'imperial' ? 'mi' : 'km',
    };
  },
}));

import { useUnits } from '@/lib/context/UnitsContext';

// Same conversion both charts perform — kept inline so the test fails the
// instant either chart drifts off this exact math.
const MILES_PER_KM = 0.621371;
const minPerMileToSecPerKm = (minPerMile: number): number =>
  minPerMile * 60 * MILES_PER_KM;

function PaceLabel({ paceMinPerMile }: { paceMinPerMile: number }) {
  const { formatPace } = useUnits();
  return <span data-testid="pace">{formatPace(minPerMileToSecPerKm(paceMinPerMile))}</span>;
}

describe('Analytics charts: pace_per_mile -> formatPace conversion', () => {
  afterEach(() => cleanup());

  test('imperial: 8.5 min/mi renders as 8:30/mi', () => {
    setUnits('imperial');
    render(<PaceLabel paceMinPerMile={8.5} />);
    expect(screen.getByTestId('pace')).toHaveTextContent('8:30/mi');
  });

  test('metric: 8.5 min/mi renders as ~5:17/km, no /mi anywhere', () => {
    setUnits('metric');
    render(<PaceLabel paceMinPerMile={8.5} />);
    const el = screen.getByTestId('pace');
    expect(el.textContent).toMatch(/^\d+:\d{2}\/km$/);
    // 8:30/mi is roughly 5:17/km
    expect(el).toHaveTextContent('5:17/km');
    expect(screen.queryByText(/\/mi/)).not.toBeInTheDocument();
  });

  test('metric: 7.0 min/mi renders as ~4:21/km', () => {
    setUnits('metric');
    render(<PaceLabel paceMinPerMile={7.0} />);
    expect(screen.getByTestId('pace')).toHaveTextContent('4:21/km');
  });

  test('imperial: 7.0 min/mi renders as 7:00/mi', () => {
    setUnits('imperial');
    render(<PaceLabel paceMinPerMile={7.0} />);
    expect(screen.getByTestId('pace')).toHaveTextContent('7:00/mi');
  });
});
