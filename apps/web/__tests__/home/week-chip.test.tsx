/**
 * Week chip: multi-run +N, other-sport links, today ring — shared Home + Analytics.
 */

import React from 'react';
import { render, screen } from '@testing-library/react';

jest.mock('next/link', () => {
  return ({ children, href, ...props }: { children: React.ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  );
});

import { WeekChipDay } from '@/components/home/WeekChipDay';
import type { WeekDay } from '@/lib/api/services/home';

const fmt = (m: number | null | undefined) => (m == null ? '—' : `${(Number(m) / 1609.344).toFixed(1)}`);

describe('WeekChipDay', () => {
  test('single-run day shows checkmark link to longest run', () => {
    const day: WeekDay = {
      date: '2026-04-21',
      day_abbrev: 'T',
      completed: true,
      is_today: false,
      distance_m: 8369,
      activity_id: 'run-1',
      run_count: 1,
      other_activities: [],
    };
    render(<WeekChipDay day={day} formatDistNoUnit={fmt} />);
    const link = screen.getByLabelText(/open longest run/i);
    expect(link).toHaveAttribute('href', '/activities/run-1');
  });

  test('multi-run day shows +N affordance linking to calendar day', () => {
    const day: WeekDay = {
      date: '2026-04-22',
      day_abbrev: 'W',
      completed: true,
      is_today: false,
      distance_m: 16093,
      activity_id: 'longest',
      run_count: 3,
      other_activities: [],
    };
    render(<WeekChipDay day={day} formatDistNoUnit={fmt} />);
    expect(screen.getByLabelText('+2 more runs this day')).toHaveAttribute('href', '/calendar?date=2026-04-22');
  });

  test('non-run activity renders separate link with walking icon affordance', () => {
    const day: WeekDay = {
      date: '2026-04-22',
      day_abbrev: 'W',
      completed: true,
      is_today: false,
      distance_m: 16093,
      activity_id: 'longest',
      run_count: 1,
      other_activities: [
        { activity_id: 'w1', sport: 'walking', distance_m: 1609, duration_s: null, name: 'Walk' },
      ],
    };
    render(<WeekChipDay day={day} formatDistNoUnit={fmt} />);
    const walk = screen.getByLabelText(/Walking/i);
    expect(walk.tagName).toBe('A');
    expect(walk).toHaveAttribute('href', '/activities/w1');
  });

  test('today gets ring-2 ring-orange-500', () => {
    const day: WeekDay = {
      date: '2026-04-23',
      day_abbrev: 'W',
      workout_type: 'rest',
      completed: false,
      is_today: true,
    };
    const { container } = render(<WeekChipDay day={day} formatDistNoUnit={fmt} />);
    const ring = container.querySelector('.ring-2.ring-orange-500');
    expect(ring).toBeTruthy();
  });

  test('rest day shows em dash in distance slot', () => {
    const day: WeekDay = {
      date: '2026-04-24',
      day_abbrev: 'F',
      workout_type: 'rest',
      completed: false,
      is_today: false,
    };
    const { container } = render(<WeekChipDay day={day} formatDistNoUnit={fmt} />);
    expect(container.textContent).toMatch(/\u2014/);
  });
});
