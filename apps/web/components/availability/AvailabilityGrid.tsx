/**
 * Training Availability Grid Component
 * 
 * Interactive 7×3 grid for setting training availability.
 * Built with modular cells that can be swapped/refactored independently.
 */

'use client';

import { useAvailabilityGrid, useBulkUpdateAvailability } from '@/lib/hooks/queries/availability';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import type { TrainingAvailability } from '@/lib/api/types';

const DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const TIME_BLOCKS: Array<'morning' | 'afternoon' | 'evening'> = ['morning', 'afternoon', 'evening'];

const STATUS_ORDER: Array<'unavailable' | 'available' | 'preferred'> = [
  'unavailable',
  'available',
  'preferred',
];

const STATUS_COLORS = {
  unavailable: 'bg-slate-800 border-slate-700/50',
  available: 'bg-blue-900/30 border-blue-700/50',
  preferred: 'bg-green-900/30 border-green-700/50',
};

const STATUS_LABELS = {
  unavailable: 'Unavailable',
  available: 'Available',
  preferred: 'Preferred',
};

interface AvailabilityCellProps {
  slot: TrainingAvailability;
  onToggle: () => void;
}

function AvailabilityCell({ slot, onToggle }: AvailabilityCellProps) {
  const currentIndex = STATUS_ORDER.indexOf(slot.status);
  const nextStatus = STATUS_ORDER[(currentIndex + 1) % STATUS_ORDER.length];

  return (
    <button
      onClick={onToggle}
      className={`
        p-4 rounded border transition-all
        ${STATUS_COLORS[slot.status]}
        hover:opacity-80 cursor-pointer
        text-sm text-left
      `}
      title={`Click to change to ${STATUS_LABELS[nextStatus]}`}
    >
      <div className="font-medium mb-1">{STATUS_LABELS[slot.status]}</div>
      <div className="text-xs text-slate-400 capitalize">{slot.time_block}</div>
    </button>
  );
}

export function AvailabilityGrid() {
  const { data: gridData, isLoading, error } = useAvailabilityGrid();
  const bulkUpdate = useBulkUpdateAvailability();

  if (isLoading) {
    return <LoadingSpinner size="lg" />;
  }

  if (error) {
    return <ErrorMessage error={error} title="Failed to load availability grid" />;
  }

  if (!gridData) {
    return <p className="text-slate-400">No availability data</p>;
  }

  const handleToggle = (slot: TrainingAvailability) => {
    const currentIndex = STATUS_ORDER.indexOf(slot.status);
    const nextStatus = STATUS_ORDER[(currentIndex + 1) % STATUS_ORDER.length];

    bulkUpdate.mutate([
      {
        day_of_week: slot.day_of_week,
        time_block: slot.time_block,
        status: nextStatus,
      },
    ]);
  };

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-4">
        <h3 className="text-lg font-semibold mb-2">Summary</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <p className="text-slate-400">Total Slots</p>
            <p className="text-xl font-semibold">{gridData.summary.total_slots}</p>
          </div>
          <div>
            <p className="text-slate-400">Available</p>
            <p className="text-xl font-semibold text-blue-400">
              {gridData.summary.available_slots}
            </p>
          </div>
          <div>
            <p className="text-slate-400">Preferred</p>
            <p className="text-xl font-semibold text-green-400">
              {gridData.summary.preferred_slots}
            </p>
          </div>
          <div>
            <p className="text-slate-400">Total Available</p>
            <p className="text-xl font-semibold">
              {gridData.summary.total_available_slots} (
              {gridData.summary.total_available_percentage.toFixed(1)}%)
            </p>
          </div>
        </div>
      </div>

      {/* Grid */}
      <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6">
        <h3 className="text-lg font-semibold mb-4">Availability Grid</h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr>
                <th className="text-left p-2">Day</th>
                {TIME_BLOCKS.map((block) => (
                  <th key={block} className="p-2 text-sm capitalize">
                    {block}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {DAY_NAMES.map((dayName, dayIndex) => {
                const daySlots = gridData.grid.filter((s) => s.day_of_week === dayIndex);
                return (
                  <tr key={dayIndex} className="border-t border-slate-700/50">
                    <td className="p-2 font-medium">{dayName}</td>
                    {TIME_BLOCKS.map((block) => {
                      const slot = daySlots.find((s) => s.time_block === block);
                      if (!slot) return <td key={block} className="p-2" />;
                      return (
                        <td key={block} className="p-2">
                          <AvailabilityCell
                            slot={slot}
                            onToggle={() => handleToggle(slot)}
                          />
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {bulkUpdate.isError && (
        <ErrorMessage error={bulkUpdate.error} title="Failed to update availability" />
      )}
    </div>
  );
}


