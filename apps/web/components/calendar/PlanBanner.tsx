'use client';

/**
 * PlanBanner Component
 * 
 * Clean, professional display of active training plan.
 * Shows essential info only - no badge soup.
 * 
 * DESIGN: Minimal, scannable, actionable.
 */

import React, { useState } from 'react';
import Link from 'next/link';
import { PlanManagementModal } from '@/components/plans/PlanManagementModal';

interface ActivePlan {
  id: string;
  name: string;
  goal_race_name?: string;
  goal_race_date?: string;
  total_weeks: number;
  status?: string;
}

interface PlanBannerProps {
  plan: ActivePlan;
  currentWeek?: number | null;
  currentPhase?: string | null;
}

// Map internal phase keys to human-readable display names
const PHASE_DISPLAY_NAMES: Record<string, string> = {
  'base': 'Base Building',
  'base_speed': 'Base + Speed',
  'volume_build': 'Volume Build',
  'threshold': 'Threshold Focus',
  'marathon_specific': 'Marathon Specific',
  'race_specific': 'Race Specific',
  'hold': 'Maintenance',
  'taper': 'Taper',
  'race': 'Race Week',
  'recovery': 'Recovery',
};

function formatPhase(phase: string | null | undefined): string {
  if (!phase) return '';
  return PHASE_DISPLAY_NAMES[phase] || phase.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

export function PlanBanner({ plan, currentWeek, currentPhase }: PlanBannerProps) {
  const [showManagement, setShowManagement] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  
  // Parse date without timezone issues
  const formatRaceDate = (dateStr: string) => {
    const [year, month, day] = dateStr.split('-').map(Number);
    const date = new Date(year, month - 1, day);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };
  
  // Calculate days until race
  const daysUntilRace = (() => {
    if (!plan.goal_race_date) return null;
    const [y, m, d] = plan.goal_race_date.split('-').map(Number);
    const raceDate = new Date(y, m - 1, d);
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    return Math.ceil((raceDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
  })();

  // Display name: Use race name if different from plan name, otherwise just plan name
  const displayName = plan.goal_race_name && plan.goal_race_name !== plan.name 
    ? plan.goal_race_name 
    : plan.name;
  
  return (
    <>
      {/* Clean, minimal banner - no badge soup */}
      <div className="bg-gray-800/80 border border-gray-700 rounded-lg p-4 mb-6">
        <div className="flex items-center justify-between">
          {/* Left: Plan info - clean hierarchy */}
          <div className="flex items-center gap-6">
            {/* Primary info */}
            <div>
              <h2 className="text-base font-semibold text-white">{displayName}</h2>
              <p className="text-sm text-gray-400">
                {currentWeek && `Week ${currentWeek} of ${plan.total_weeks}`}
                {currentWeek && currentPhase && ' · '}
                {currentPhase && formatPhase(currentPhase)}
                {(currentWeek || currentPhase) && daysUntilRace && daysUntilRace > 0 && ' · '}
                {daysUntilRace !== null && daysUntilRace > 0 && (
                  <span className="text-orange-400">{daysUntilRace}d to race</span>
                )}
              </p>
            </div>
          </div>
          
          {/* Right: Actions - minimal */}
          <div className="flex items-center gap-2">
            <Link
              href={`/plans/${plan.id}`}
              className="px-3 py-1.5 text-sm text-gray-300 hover:text-white hover:bg-gray-700 rounded transition-colors"
            >
              View Plan
            </Link>
            
            {/* Menu */}
            <div className="relative">
              <button
                onClick={() => setShowMenu(!showMenu)}
                className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors"
                aria-label="Plan options"
              >
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z" />
                </svg>
              </button>
              
              {showMenu && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setShowMenu(false)} />
                  <div className="absolute right-0 top-full mt-1 w-48 bg-gray-800 border border-gray-700 rounded-lg shadow-xl z-20 py-1">
                    <button
                      onClick={() => { setShowMenu(false); setShowManagement(true); }}
                      className="w-full px-4 py-2 text-sm text-left text-gray-300 hover:bg-gray-700 hover:text-white"
                    >
                      Manage Plan
                    </button>
                    <button
                      onClick={() => { setShowMenu(false); setShowManagement(true); }}
                      className="w-full px-4 py-2 text-sm text-left text-amber-400 hover:bg-gray-700"
                    >
                      Pause Plan
                    </button>
                    <button
                      onClick={() => { setShowMenu(false); setShowManagement(true); }}
                      className="w-full px-4 py-2 text-sm text-left text-red-400 hover:bg-gray-700"
                    >
                      Withdraw
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
      
      <PlanManagementModal
        plan={plan}
        currentWeek={currentWeek}
        isOpen={showManagement}
        onClose={() => setShowManagement(false)}
      />
    </>
  );
}
