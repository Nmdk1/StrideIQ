'use client';

import React from 'react';

// Phase 2: collapsed from 6 tabs (overview/splits/analysis/compare/context/feedback)
// to 3.  Splits is the default — daily users land on the data they care about
// most.  Coach absorbs the old Overview intelligence card, the Analysis tab
// (drift / plan-comparison / effort intensity), and the Context tab (Going-In,
// Why This Run, Findings, narrative).  Compare keeps the existing comparables
// panel.  Feedback is no longer a tab — it's a required modal (Phase 3) that
// auto-opens until the athlete has completed reflection + RPE + workout type.
export type ActivityTabId = 'splits' | 'coach' | 'compare';

const TAB_LABELS: Record<ActivityTabId, string> = {
  splits: 'Splits',
  coach: 'Coach',
  compare: 'Compare',
};

const ORDER: ActivityTabId[] = ['splits', 'coach', 'compare'];

export interface ActivityTabsProps {
  activeTab: ActivityTabId;
  onTabChange: (id: ActivityTabId) => void;
  /** Inactive panels stay mounted; CSS `hidden` (display:none) for instant switching. */
  panels: Record<ActivityTabId, React.ReactNode>;
}

export function ActivityTabs({ activeTab, onTabChange, panels }: ActivityTabsProps) {
  const tabButtonClass = (id: ActivityTabId) =>
    id === activeTab
      ? 'text-white border-b-2 border-emerald-400 md:border-b-0 md:border-l-2 md:border-l-emerald-400 bg-slate-800/40'
      : 'text-slate-400 hover:text-slate-200 border-b-2 border-transparent md:border-b-0 md:border-l-2 md:border-l-transparent';

  return (
    <div className="flex flex-col md:flex-row md:gap-0 md:items-start">
      <div
        className="flex flex-row md:flex-col overflow-x-auto md:overflow-visible gap-0 pb-0 mb-4 md:mb-0 md:pb-0 md:w-[130px] md:flex-shrink-0 md:border-r md:border-slate-700/40 md:pr-4 md:mr-6 -mx-1 px-1 md:mx-0 md:px-0 border-b border-slate-700/40 md:border-b-0 scrollbar-thin"
        role="tablist"
        aria-label="Activity sections"
      >
        {ORDER.map(id => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={activeTab === id}
            id={`activity-tab-${id}`}
            onClick={() => onTabChange(id)}
            className={`flex-shrink-0 md:w-full text-left px-4 py-2.5 md:py-3 text-sm font-medium whitespace-nowrap transition-colors ${tabButtonClass(id)}`}
          >
            {TAB_LABELS[id]}
          </button>
        ))}
      </div>

      <div className="flex-1 min-w-0">
        {ORDER.map(id => (
          <div
            key={id}
            role="tabpanel"
            aria-labelledby={`activity-tab-${id}`}
            hidden={activeTab !== id}
            className={activeTab === id ? 'block' : 'hidden'}
          >
            {panels[id]}
          </div>
        ))}
      </div>
    </div>
  );
}
