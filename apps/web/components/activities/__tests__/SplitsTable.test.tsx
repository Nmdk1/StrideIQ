/**
 * SplitsTable Phase 2 contract:
 * - Column toggle UI appears only when at least one optional column has data
 *   somewhere in the splits.
 * - Toggling a column adds/removes its <th>.
 * - The toggle state persists in localStorage across remounts.
 * - Cells in non-data splits show "—" so the table stays uniform.
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { SplitsTable } from '../SplitsTable';
import type { Split } from '@/lib/types/splits';

jest.mock('@/lib/context/UnitsContext', () => ({
  useUnits: () => ({
    units: 'imperial',
    formatDistance: (m: number, decimals = 1) => `${(m / 1609.34).toFixed(decimals)} mi`,
    formatPace: (sPerKm: number | null) => {
      if (!sPerKm) return '—';
      const sPerMi = sPerKm * 1.60934;
      const min = Math.floor(sPerMi / 60);
      const sec = Math.round(sPerMi % 60).toString().padStart(2, '0');
      return `${min}:${sec}/mi`;
    },
  }),
}));

const STORAGE_KEY = 'splits:columnPrefs:v1';

function makeSplit(overrides: Partial<Split>, n: number): Split {
  return {
    split_number: n,
    distance: 1609.34,
    elapsed_time: 420,
    moving_time: 420,
    average_heartrate: 155,
    max_heartrate: null,
    average_cadence: 175,
    gap_s_per_km: null,
    lap_type: null,
    interval_number: null,
    ...overrides,
  };
}

describe('SplitsTable column toggle (Phase 2)', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  test('toggle UI hidden when no FIT-derived data exists in any split', () => {
    const splits = [makeSplit({}, 1), makeSplit({}, 2)];
    render(<SplitsTable splits={splits} />);
    expect(screen.queryByRole('button', { name: /columns/i })).not.toBeInTheDocument();
  });

  test('toggle UI shown and clicking adds the column', () => {
    const splits = [
      makeSplit({ avg_power_w: 240 }, 1),
      makeSplit({ avg_power_w: 250 }, 2),
    ];
    render(<SplitsTable splits={splits} />);

    const toggleBtn = screen.getByRole('button', { name: /columns/i });
    expect(toggleBtn).toBeInTheDocument();

    // Power column not yet rendered.
    expect(screen.queryByRole('columnheader', { name: /power/i })).not.toBeInTheDocument();

    fireEvent.click(toggleBtn);
    fireEvent.click(screen.getByLabelText('Power'));

    expect(screen.getByRole('columnheader', { name: /Power \(W\)/i })).toBeInTheDocument();
    expect(screen.getByText('240')).toBeInTheDocument();
    expect(screen.getByText('250')).toBeInTheDocument();
  });

  test('persists toggle state across remount via localStorage', () => {
    const splits = [
      makeSplit({ avg_stride_length_m: 1.18, avg_power_w: 240 }, 1),
    ];
    const { unmount } = render(<SplitsTable splits={splits} />);
    fireEvent.click(screen.getByRole('button', { name: /columns/i }));
    fireEvent.click(screen.getByLabelText('Stride'));
    expect(screen.getByRole('columnheader', { name: /Stride/i })).toBeInTheDocument();

    unmount();

    render(<SplitsTable splits={splits} />);
    expect(screen.getByRole('columnheader', { name: /Stride/i })).toBeInTheDocument();
    // We never enabled Power on second mount; it must stay hidden.
    expect(screen.queryByRole('columnheader', { name: /Power/i })).not.toBeInTheDocument();
  });

  test('cells render em-dash for splits missing the optional metric', () => {
    const splits = [
      makeSplit({ avg_power_w: 240 }, 1),
      makeSplit({ avg_power_w: null }, 2),
    ];
    render(<SplitsTable splits={splits} />);
    fireEvent.click(screen.getByRole('button', { name: /columns/i }));
    fireEvent.click(screen.getByLabelText('Power'));

    // Row 2 power cell should be "—".
    const rows = screen.getAllByRole('row');
    // Header + 2 body rows.
    expect(rows).toHaveLength(3);
    const row2Cells = rows[2].querySelectorAll('td');
    // Last cell is the Power column.
    expect(row2Cells[row2Cells.length - 1].textContent).toBe('—');
  });
});
