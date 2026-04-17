/**
 * Units toggle regression tests
 *
 * Why this exists:
 *   Several components were rendering distance/pace/speed without going through
 *   the global unit preference (useUnits). That produced mixed-unit displays
 *   (e.g. distance in km, pace in /mi on the same row) for athletes whose
 *   preference was metric. The component-level fixes route every render through
 *   useUnits; these tests lock that behavior in for both unit modes so the
 *   bypass cannot regress unnoticed.
 *
 * Components under test:
 *   - ActivityCard       (the activity-list row)
 *   - DayCell            (the calendar tile)
 *   - CyclingDetail      (the cycling activity detail)
 *   - HikingDetail       (the hiking/walking activity detail)
 *   - RecentCrossTrainingCard (home-page cross-training card)
 *
 * Each test renders the component twice, first with units='imperial', then with
 * units='metric', and asserts the visible output uses the correct unit.
 */

import React from 'react';
import { render, screen, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom';

// ---------------------------------------------------------------------------
// Mockable units context — switched between tests via setUnits()
// ---------------------------------------------------------------------------

let _units: 'imperial' | 'metric' = 'imperial';
const setUnits = (u: 'imperial' | 'metric') => {
  _units = u;
};

jest.mock('@/lib/context/UnitsContext', () => ({
  useUnits: () => {
    const units = _units;
    return {
      units,
      formatDistance: (m: number, decimals = 2) => {
        if (units === 'imperial') {
          return `${(m / 1609.344).toFixed(decimals)} mi`;
        }
        return `${(m / 1000).toFixed(decimals)} km`;
      },
      formatPace: (sPerKm: number) => {
        if (units === 'imperial') {
          const sPerMi = sPerKm * 1.60934;
          const m = Math.floor(sPerMi / 60);
          const s = Math.round(sPerMi % 60);
          return `${m}:${s.toString().padStart(2, '0')}/mi`;
        }
        const m = Math.floor(sPerKm / 60);
        const s = Math.round(sPerKm % 60);
        return `${m}:${s.toString().padStart(2, '0')}/km`;
      },
      formatElevation: (m: number) => {
        if (units === 'imperial') {
          return `${Math.round(m * 3.28084)} ft`;
        }
        return `${Math.round(m)} m`;
      },
      distanceUnitShort: units === 'imperial' ? 'mi' : 'km',
      paceUnit: units === 'imperial' ? 'min/mi' : 'min/km',
    };
  },
}));

// next/link mock
jest.mock('next/link', () => {
  const Link = ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  );
  Link.displayName = 'Link';
  return Link;
});

// ---------------------------------------------------------------------------
// ActivityCard
// ---------------------------------------------------------------------------

import { ActivityCard } from '@/components/activities/ActivityCard';

const baseActivity = {
  id: 'a1',
  name: 'Morning Run',
  sport: 'run',
  distance: 11180, // ~11.18 km / ~6.95 mi
  moving_time: 3060, // 51 min → ~7:39/mi or ~4:34/km
  start_date: '2026-04-15T07:00:00Z',
  average_speed: 11180 / 3060,
} as any;

describe('ActivityCard pace/distance unit toggle', () => {
  afterEach(() => cleanup());

  test('imperial: pace in /mi, distance in mi', () => {
    setUnits('imperial');
    render(<ActivityCard activity={baseActivity} />);
    expect(screen.getByText(/\d+:\d{2}\/mi/)).toBeInTheDocument();
    expect(screen.getByText(/^\d+(\.\d+)?\s*mi$/)).toBeInTheDocument();
    expect(screen.queryByText(/\/km/)).not.toBeInTheDocument();
  });

  test('metric: pace in /km, distance in km', () => {
    setUnits('metric');
    render(<ActivityCard activity={baseActivity} />);
    expect(screen.getByText(/\d+:\d{2}\/km/)).toBeInTheDocument();
    expect(screen.getByText(/^\d+(\.\d+)?\s*km$/)).toBeInTheDocument();
    expect(screen.queryByText(/\/mi/)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// DayCell (calendar)
// ---------------------------------------------------------------------------

import { DayCell } from '@/components/calendar/DayCell';

const dayWithRun = {
  date: '2026-04-15',
  is_today: false,
  is_past: true,
  is_future: false,
  is_recovery_day: false,
  load_pct: 50,
  load_band: 'green' as const,
  activities: [
    {
      id: 'a1',
      sport: 'run',
      duration_s: 3060,
      distance_m: 11180,
      name: 'Morning Run',
      workout_type: null,
      avg_hr: null,
    },
  ],
  planned_workout: null,
} as any;

describe('DayCell pace unit toggle', () => {
  afterEach(() => cleanup());

  test('imperial: pace shown with /mi suffix', () => {
    setUnits('imperial');
    render(<DayCell day={dayWithRun} isToday={false} isSelected={false} onClick={() => {}} />);
    const paceMatches = screen.queryAllByText(/\d+:\d{2}\/mi/);
    expect(paceMatches.length).toBeGreaterThan(0);
  });

  test('metric: pace shown with /km suffix (no /mi anywhere)', () => {
    setUnits('metric');
    render(<DayCell day={dayWithRun} isToday={false} isSelected={false} onClick={() => {}} />);
    const paceMatches = screen.queryAllByText(/\d+:\d{2}\/km/);
    expect(paceMatches.length).toBeGreaterThan(0);
    expect(screen.queryByText(/\/mi/)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// CyclingDetail (cross-training)
// ---------------------------------------------------------------------------

import { CyclingDetail } from '@/components/activities/cross-training/CyclingDetail';

const cyclingActivity = {
  id: 'c1',
  sport_type: 'cycling',
  distance_m: 32000, // 32 km / ~19.88 mi
  moving_time_s: 3600, // 1 hour → 32 km/h or 19.88 mph
  total_elevation_gain_m: 200,
  average_hr: 140,
  max_hr: null,
  active_kcal: null,
  avg_cadence_device: null,
} as any;

describe('CyclingDetail speed unit toggle', () => {
  afterEach(() => cleanup());

  test('imperial: speed shown in mph', () => {
    setUnits('imperial');
    render(<CyclingDetail activity={cyclingActivity} />);
    expect(screen.getByText('mph')).toBeInTheDocument();
    expect(screen.queryByText('km/h')).not.toBeInTheDocument();
  });

  test('metric: speed shown in km/h', () => {
    setUnits('metric');
    render(<CyclingDetail activity={cyclingActivity} />);
    expect(screen.getByText('km/h')).toBeInTheDocument();
    expect(screen.queryByText('mph')).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// HikingDetail (cross-training)
// ---------------------------------------------------------------------------

import { HikingDetail } from '@/components/activities/cross-training/HikingDetail';

const hikingActivity = {
  id: 'h1',
  sport_type: 'hiking',
  distance_m: 8000,
  moving_time_s: 5400,
  total_elevation_gain_m: 500,
  average_hr: 130,
  max_hr: null,
  steps: null,
  active_kcal: null,
  avg_cadence_device: null,
  max_cadence: null,
} as any;

describe('HikingDetail speed unit toggle', () => {
  afterEach(() => cleanup());

  test('imperial: shows mph in metric grid', () => {
    setUnits('imperial');
    render(<HikingDetail activity={hikingActivity} />);
    expect(screen.getByText('mph')).toBeInTheDocument();
    expect(screen.queryByText('km/h')).not.toBeInTheDocument();
  });

  test('metric: shows km/h in metric grid', () => {
    setUnits('metric');
    render(<HikingDetail activity={hikingActivity} />);
    expect(screen.getByText('km/h')).toBeInTheDocument();
    expect(screen.queryByText('mph')).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// RecentCrossTrainingCard (home page)
// ---------------------------------------------------------------------------

import { RecentCrossTrainingCard } from '@/components/home/RecentCrossTrainingCard';

const cyclingHomeData = {
  id: 'c1',
  sport: 'cycling',
  name: 'Evening Ride',
  distance_m: 32000,
  duration_s: 3600,
  avg_hr: 140,
  steps: null,
  active_kcal: null,
  start_time: '2026-04-15T17:00:00Z',
  additional_count: 0,
} as any;

describe('RecentCrossTrainingCard distance unit toggle', () => {
  afterEach(() => cleanup());

  test('imperial: distance label includes mi', () => {
    setUnits('imperial');
    render(<RecentCrossTrainingCard data={cyclingHomeData} />);
    expect(screen.getByText(/\d+(\.\d+)?\s*mi/)).toBeInTheDocument();
    expect(screen.queryByText(/\d+(\.\d+)?\s*km/)).not.toBeInTheDocument();
  });

  test('metric: distance label includes km', () => {
    setUnits('metric');
    render(<RecentCrossTrainingCard data={cyclingHomeData} />);
    expect(screen.getByText(/\d+(\.\d+)?\s*km/)).toBeInTheDocument();
    expect(screen.queryByText(/\d+(\.\d+)?\s*mi/)).not.toBeInTheDocument();
  });
});
