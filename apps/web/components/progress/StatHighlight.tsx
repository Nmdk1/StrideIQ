'use client';

import React from 'react';
import { Trophy } from 'lucide-react';

interface StatHighlightProps {
  distance: string;
  time: string;
  dateAchieved?: string;
}

export function StatHighlight({ distance, time, dateAchieved }: StatHighlightProps) {
  return (
    <div className="flex items-center gap-4 bg-gradient-to-r from-yellow-500/10 to-orange-500/10 border border-yellow-500/20 rounded-lg p-4">
      <div className="p-2 bg-yellow-500/20 rounded-lg">
        <Trophy className="w-6 h-6 text-yellow-400" />
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-yellow-300">{distance}</span>
          <span className="bg-yellow-500/20 text-yellow-400 text-xs px-1.5 py-0.5 rounded font-bold">NEW</span>
        </div>
        <p className="text-2xl font-bold text-white mt-0.5">{time}</p>
        {dateAchieved && (
          <p className="text-xs text-slate-400 mt-0.5">{dateAchieved}</p>
        )}
      </div>
    </div>
  );
}
