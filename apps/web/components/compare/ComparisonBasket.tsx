'use client';

/**
 * Comparison Basket
 * 
 * A floating bar that appears when activities are selected for comparison.
 * Shows the selected activities and a button to navigate to the compare page.
 */

import React from 'react';
import Link from 'next/link';
import { useCompareSelection } from '@/lib/context/CompareContext';

export function ComparisonBasket() {
  const { 
    selectedActivities, 
    removeFromSelection, 
    clearSelection,
    selectionCount,
    MAX_SELECTION,
  } = useCompareSelection();

  if (selectionCount === 0) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 bg-slate-800 border-t border-slate-700/50 shadow-lg">
      <div className="max-w-6xl mx-auto px-4 py-3">
        <div className="flex items-center justify-between">
          {/* Selected activities */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1">
            <span className="text-sm text-slate-400 whitespace-nowrap">
              Compare ({selectionCount}/{MAX_SELECTION}):
            </span>
            <div className="flex gap-2">
              {selectedActivities.map((activity) => (
                <div
                  key={activity.id}
                  className="flex items-center gap-1 bg-slate-700 rounded-full px-3 py-1 text-sm"
                >
                  <span className="max-w-[100px] truncate">
                    {activity.name || new Date(activity.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  </span>
                  <button
                    onClick={() => removeFromSelection(activity.id)}
                    className="text-slate-400 hover:text-white ml-1"
                    aria-label={`Remove ${activity.name} from comparison`}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3 ml-4">
            <button
              onClick={clearSelection}
              className="text-sm text-slate-400 hover:text-white"
            >
              Clear
            </button>
            <Link
              href="/compare/results"
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                selectionCount >= 2
                  ? 'bg-orange-600 hover:bg-orange-700 text-white'
                  : 'bg-slate-600 text-slate-400 cursor-not-allowed'
              }`}
              onClick={(e) => {
                if (selectionCount < 2) {
                  e.preventDefault();
                }
              }}
            >
              Compare {selectionCount >= 2 ? `${selectionCount} Runs →` : '(Select 2+)'}
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
