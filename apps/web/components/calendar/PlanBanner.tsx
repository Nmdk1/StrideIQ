'use client';

/**
 * PlanBanner Component
 * 
 * Shows the active training plan with:
 * - Plan name and race info
 * - Quick access to coach
 * - Plan management dropdown
 * 
 * DESIGN PRINCIPLE: Every element is actionable. 
 * The plan banner is the gateway to plan management.
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

export function PlanBanner({ plan, currentWeek, currentPhase }: PlanBannerProps) {
  const [showManagement, setShowManagement] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  
  // Parse date without timezone issues
  const formatRaceDate = (dateStr: string) => {
    const [year, month, day] = dateStr.split('-').map(Number);
    const date = new Date(year, month - 1, day);
    return date.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
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
  
  return (
    <>
      <div className="bg-gradient-to-r from-orange-900/30 to-gray-800 rounded-lg border border-orange-700/50 p-4 mb-6">
        <div className="flex items-center justify-between flex-wrap gap-4">
          {/* Plan Info */}
          <div className="flex items-center gap-4">
            <div>
              <h2 className="text-lg font-bold text-white">{plan.name}</h2>
              {plan.goal_race_name && plan.goal_race_date && (
                <p className="text-gray-400 text-sm">
                  {plan.goal_race_name} • {formatRaceDate(plan.goal_race_date)}
                </p>
              )}
            </div>
            
            {/* Status badges */}
            <div className="hidden sm:flex items-center gap-2">
              {currentWeek && (
                <span className="px-2 py-1 bg-blue-600/50 text-blue-200 rounded text-xs font-medium">
                  Week {currentWeek} of {plan.total_weeks}
                </span>
              )}
              {currentPhase && (
                <span className="px-2 py-1 bg-orange-600/30 text-orange-300 border border-orange-700/50 rounded text-xs font-medium">
                  {currentPhase}
                </span>
              )}
              {daysUntilRace !== null && daysUntilRace > 0 && (
                <span className="px-2 py-1 bg-pink-600/30 text-pink-300 rounded text-xs font-medium">
                  {daysUntilRace} days
                </span>
              )}
            </div>
          </div>
          
          {/* Actions */}
          <div className="flex items-center gap-2">
            {/* View Plan Button */}
            <Link
              href={`/plans/${plan.id}`}
              className="px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors hidden sm:flex items-center gap-1"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              View Plan
            </Link>
            
            {/* Coach Button */}
            <Link 
              href="/coach" 
              className="px-3 py-2 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 rounded-lg text-sm font-medium transition-colors flex items-center gap-1"
            >
              💬
              <span className="hidden sm:inline">Ask Coach</span>
            </Link>
            
            {/* Menu Button */}
            <div className="relative">
              <button
                onClick={() => setShowMenu(!showMenu)}
                className="px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" />
                </svg>
              </button>
              
              {/* Dropdown Menu */}
              {showMenu && (
                <>
                  <div 
                    className="fixed inset-0 z-10"
                    onClick={() => setShowMenu(false)}
                  />
                  <div className="absolute right-0 top-full mt-2 w-56 bg-gray-800 border border-gray-700 rounded-lg shadow-xl z-20 py-1">
                    <Link
                      href={`/plans/${plan.id}`}
                      className="flex items-center gap-3 px-4 py-2.5 text-sm text-gray-300 hover:bg-gray-700 hover:text-white transition-colors sm:hidden"
                      onClick={() => setShowMenu(false)}
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                      </svg>
                      View Full Plan
                    </Link>
                    <button
                      onClick={() => {
                        setShowMenu(false);
                        setShowManagement(true);
                      }}
                      className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-gray-300 hover:bg-gray-700 hover:text-white transition-colors text-left"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                      Manage Plan
                    </button>
                    <div className="border-t border-gray-700 my-1" />
                    <button
                      onClick={() => {
                        setShowMenu(false);
                        setShowManagement(true);
                      }}
                      className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-amber-400 hover:bg-gray-700 transition-colors text-left"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      Pause Plan
                    </button>
                    <button
                      onClick={() => {
                        setShowMenu(false);
                        setShowManagement(true);
                      }}
                      className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-red-400 hover:bg-gray-700 transition-colors text-left"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                      Withdraw from Race
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
        
        {/* Mobile status badges */}
        <div className="flex sm:hidden items-center gap-2 mt-3 flex-wrap">
          {currentWeek && (
            <span className="px-2 py-1 bg-blue-600/50 text-blue-200 rounded text-xs font-medium">
              Week {currentWeek}/{plan.total_weeks}
            </span>
          )}
          {currentPhase && (
            <span className="px-2 py-1 bg-orange-600/30 text-orange-300 border border-orange-700/50 rounded text-xs font-medium">
              {currentPhase}
            </span>
          )}
          {daysUntilRace !== null && daysUntilRace > 0 && (
            <span className="px-2 py-1 bg-pink-600/30 text-pink-300 rounded text-xs font-medium">
              {daysUntilRace} days to race
            </span>
          )}
        </div>
      </div>
      
      {/* Plan Management Modal */}
      <PlanManagementModal
        plan={plan}
        currentWeek={currentWeek}
        isOpen={showManagement}
        onClose={() => setShowManagement(false)}
      />
    </>
  );
}
