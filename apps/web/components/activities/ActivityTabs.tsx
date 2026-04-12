'use client';

import React from 'react';

export type ActivityTabId = 'splits' | 'analysis' | 'context' | 'feedback';

const TAB_LABELS: Record<ActivityTabId, string> = {
  splits: 'Splits',
  analysis: 'Analysis',
  context: 'Context',
  feedback: 'Feedback',
};

const ORDER: ActivityTabId[] = ['splits', 'analysis', 'context', 'feedback'];

export interface ActivityTabsProps {
  activeTab: ActivityTabId;
  onTabChange: (id: ActivityTabId) => void;
  /** Inactive panels stay mounted; CSS `hidden` (display:none) for instant switching. */
  panels: Record<ActivityTabId, React.ReactNode>;
}

export function ActivityTabs({ activeTab, onTabChange, panels }: ActivityTabsProps) {
  const tabButtonClass = (id: ActivityTabId) =>
    id === activeTab
      ? 'bg-slate-700/80 text-white border border-slate-600/60'
      : 'text-slate-400 hover:text-slate-200 border border-transparent';

  return (
    <div className="flex flex-col md:flex-row md:gap-0 md:items-start">
      {/* Single tablist: horizontal scroll on mobile, vertical sidebar on md+ */}
      <div
        className="flex flex-row md:flex-col overflow-x-auto md:overflow-visible gap-1 pb-2 mb-3 md:mb-0 md:pb-0 md:w-[120px] md:flex-shrink-0 md:border-r md:border-slate-700/40 md:pr-3 md:mr-5 md:gap-0.5 -mx-1 px-1 md:mx-0 md:px-0 border-b border-slate-700/40 md:border-b-0 scrollbar-thin"
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
            className={`flex-shrink-0 md:w-full text-left px-3 py-2 md:py-2.5 text-sm rounded-md whitespace-nowrap transition-colors ${tabButtonClass(id)}`}
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
