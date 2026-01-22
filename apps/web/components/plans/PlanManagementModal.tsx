'use client';

/**
 * Plan Management Modal
 * 
 * Allows users to manage their active training plan:
 * - Withdraw from race (archive plan)
 * - Pause plan (freeze progress)
 * - Resume plan (continue after pause)
 * - Change race date (recalculate schedule)
 * - Skip current week
 * - Adjust plan (swap days, adjust load)
 * - View full plan overview
 * 
 * DESIGN PRINCIPLE: Life happens. The plan should flex.
 */

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/lib/hooks/useAuth';
import { API_CONFIG } from '@/lib/api/config';

interface ActivePlan {
  id: string;
  name: string;
  goal_race_name?: string;
  goal_race_date?: string;
  total_weeks: number;
  status?: string;
}

interface PlanManagementModalProps {
  plan: ActivePlan;
  currentWeek?: number | null;
  isOpen: boolean;
  onClose: () => void;
}

interface WeekWorkout {
  id: string;
  date: string | null;
  day_of_week: number;
  day_name: string;
  workout_type: string;
  title: string;
  description: string | null;
  target_distance_km: number | null;
  completed: boolean;
  skipped: boolean;
}

type Action = 'withdraw' | 'pause' | 'resume' | 'change-date' | 'skip-week' | 'adjust' | null;
type AdjustMode = 'menu' | 'swap' | 'load' | 'move' | 'edit' | 'add' | null;

interface WorkoutType {
  value: string;
  label: string;
  description: string;
}

export function PlanManagementModal({ plan, currentWeek, isOpen, onClose }: PlanManagementModalProps) {
  const router = useRouter();
  const { token } = useAuth();
  const queryClient = useQueryClient();
  
  const [selectedAction, setSelectedAction] = useState<Action>(null);
  const [confirmText, setConfirmText] = useState('');
  const [newRaceDate, setNewRaceDate] = useState(plan.goal_race_date || '');
  
  // Adjust plan state
  const [adjustMode, setAdjustMode] = useState<AdjustMode>(null);
  const [swapSelection, setSwapSelection] = useState<string[]>([]);
  const [selectedLoadAdjustment, setSelectedLoadAdjustment] = useState<string>('');
  
  // Full workout control state
  const [selectedWorkout, setSelectedWorkout] = useState<WeekWorkout | null>(null);
  const [editForm, setEditForm] = useState<{
    workout_type: string;
    title: string;
    target_distance_km: string;
    coach_notes: string;
  }>({ workout_type: '', title: '', target_distance_km: '', coach_notes: '' });
  const [moveDate, setMoveDate] = useState('');
  const [newWorkout, setNewWorkout] = useState<{
    scheduled_date: string;
    workout_type: string;
    title: string;
    target_distance_km: string;
    coach_notes: string;
  }>({ scheduled_date: '', workout_type: 'easy', title: '', target_distance_km: '', coach_notes: '' });
  const [canModify, setCanModify] = useState(false);
  
  // Fetch current week's workouts when in adjust mode
  const { data: weekData, isLoading: weekLoading, refetch: refetchWeek } = useQuery({
    queryKey: ['week-workouts', plan.id, currentWeek],
    queryFn: async () => {
      if (!currentWeek) return null;
      const res = await fetch(`${API_CONFIG.baseURL}/v2/plans/${plan.id}/week/${currentWeek}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return null;
      return res.json();
    },
    enabled: selectedAction === 'adjust' && !!currentWeek && !!token,
  });
  
  // Fetch workout types
  const { data: workoutTypesData } = useQuery({
    queryKey: ['workout-types', plan.id],
    queryFn: async () => {
      const res = await fetch(`${API_CONFIG.baseURL}/v2/plans/${plan.id}/workout-types`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return { workout_types: [], can_modify: false };
      return res.json();
    },
    enabled: selectedAction === 'adjust' && !!token,
  });
  
  // Update canModify when data loads
  useEffect(() => {
    if (workoutTypesData) {
      setCanModify(workoutTypesData.can_modify);
    }
  }, [workoutTypesData]);
  
  // Format date for display
  const formatDate = (dateStr: string) => {
    const [year, month, day] = dateStr.split('-').map(Number);
    const date = new Date(year, month - 1, day);
    return date.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
  };
  
  // API mutation for plan actions
  const planAction = useMutation({
    mutationFn: async ({ action, data }: { action: string; data?: Record<string, unknown> }) => {
      const res = await fetch(`${API_CONFIG.baseURL}/v2/plans/${plan.id}/${action}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: data ? JSON.stringify(data) : undefined,
      });
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || 'Action failed');
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar'] });
      queryClient.invalidateQueries({ queryKey: ['active-plan'] });
      onClose();
      setSelectedAction(null);
      setConfirmText('');
    },
  });
  
  const handleWithdraw = () => {
    if (confirmText.toLowerCase() !== 'withdraw') return;
    planAction.mutate({ action: 'withdraw' });
  };
  
  const handlePause = () => {
    planAction.mutate({ action: 'pause' });
  };
  
  const handleResume = () => {
    planAction.mutate({ action: 'resume' });
  };
  
  const handleChangeDate = () => {
    if (!newRaceDate) return;
    planAction.mutate({ action: 'change-date', data: { new_race_date: newRaceDate } });
  };
  
  const handleSkipWeek = () => {
    planAction.mutate({ action: 'skip-week', data: { week_number: currentWeek } });
  };
  
  // Swap days mutation
  const swapDays = useMutation({
    mutationFn: async ({ workout1, workout2 }: { workout1: string; workout2: string }) => {
      const res = await fetch(`${API_CONFIG.baseURL}/v2/plans/${plan.id}/swap-days`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ workout_id_1: workout1, workout_id_2: workout2 }),
      });
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || 'Swap failed');
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar'] });
      queryClient.invalidateQueries({ queryKey: ['week-workouts'] });
      setSwapSelection([]);
      setAdjustMode('menu');
    },
  });
  
  // Adjust load mutation
  const adjustLoad = useMutation({
    mutationFn: async ({ adjustment }: { adjustment: string }) => {
      const res = await fetch(`${API_CONFIG.baseURL}/v2/plans/${plan.id}/adjust-load`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ week_number: currentWeek, adjustment }),
      });
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || 'Adjustment failed');
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar'] });
      queryClient.invalidateQueries({ queryKey: ['week-workouts'] });
      setSelectedLoadAdjustment('');
      setAdjustMode('menu');
    },
  });
  
  // Move workout mutation
  const moveWorkout = useMutation({
    mutationFn: async ({ workoutId, newDate }: { workoutId: string; newDate: string }) => {
      const res = await fetch(`${API_CONFIG.baseURL}/v2/plans/${plan.id}/workouts/${workoutId}/move`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ new_date: newDate }),
      });
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || 'Move failed');
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar'] });
      refetchWeek();
      setSelectedWorkout(null);
      setMoveDate('');
      setAdjustMode('menu');
    },
  });
  
  // Edit workout mutation
  const editWorkout = useMutation({
    mutationFn: async ({ workoutId, updates }: { workoutId: string; updates: Record<string, unknown> }) => {
      const res = await fetch(`${API_CONFIG.baseURL}/v2/plans/${plan.id}/workouts/${workoutId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(updates),
      });
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || 'Update failed');
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar'] });
      refetchWeek();
      setSelectedWorkout(null);
      setAdjustMode('menu');
    },
  });
  
  // Delete workout mutation
  const deleteWorkout = useMutation({
    mutationFn: async ({ workoutId }: { workoutId: string }) => {
      const res = await fetch(`${API_CONFIG.baseURL}/v2/plans/${plan.id}/workouts/${workoutId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || 'Delete failed');
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar'] });
      refetchWeek();
      setSelectedWorkout(null);
      setAdjustMode('menu');
    },
  });
  
  // Add workout mutation
  const addWorkout = useMutation({
    mutationFn: async (workout: typeof newWorkout) => {
      const res = await fetch(`${API_CONFIG.baseURL}/v2/plans/${plan.id}/workouts`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          scheduled_date: workout.scheduled_date,
          workout_type: workout.workout_type,
          title: workout.title || `${workout.workout_type.replace('_', ' ')} Run`,
          target_distance_km: workout.target_distance_km ? parseFloat(workout.target_distance_km) : null,
          coach_notes: workout.coach_notes || null,
        }),
      });
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || 'Add failed');
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar'] });
      refetchWeek();
      setNewWorkout({ scheduled_date: '', workout_type: 'easy', title: '', target_distance_km: '', coach_notes: '' });
      setAdjustMode('menu');
    },
  });
  
  const handleSwapSelection = (workoutId: string) => {
    if (swapSelection.includes(workoutId)) {
      setSwapSelection(swapSelection.filter(id => id !== workoutId));
    } else if (swapSelection.length < 2) {
      const newSelection = [...swapSelection, workoutId];
      setSwapSelection(newSelection);
      
      // Auto-execute swap when 2 selected
      if (newSelection.length === 2) {
        swapDays.mutate({ workout1: newSelection[0], workout2: newSelection[1] });
      }
    }
  };
  
  const handleAdjustLoad = (adjustment: string) => {
    setSelectedLoadAdjustment(adjustment);
    adjustLoad.mutate({ adjustment });
  };
  
  // Reset state when closing
  useEffect(() => {
    if (!isOpen) {
      setSelectedAction(null);
      setAdjustMode(null);
      setSwapSelection([]);
      setConfirmText('');
      setSelectedWorkout(null);
      setMoveDate('');
      setEditForm({ workout_type: '', title: '', target_distance_km: '', coach_notes: '' });
      setNewWorkout({ scheduled_date: '', workout_type: 'easy', title: '', target_distance_km: '', coach_notes: '' });
    }
  }, [isOpen]);
  
  // Handler to start editing a workout
  const handleStartEdit = (workout: WeekWorkout) => {
    setSelectedWorkout(workout);
    setEditForm({
      workout_type: workout.workout_type,
      title: workout.title,
      target_distance_km: workout.target_distance_km?.toString() || '',
      coach_notes: '',
    });
    setAdjustMode('edit');
  };
  
  // Handler to start moving a workout
  const handleStartMove = (workout: WeekWorkout) => {
    setSelectedWorkout(workout);
    setMoveDate(workout.date || '');
    setAdjustMode('move');
  };
  
  if (!isOpen) return null;
  
  return (
    <>
      {/* Overlay */}
      <div 
        className="fixed inset-0 bg-black/70 z-50 transition-opacity"
        onClick={() => {
          onClose();
          setSelectedAction(null);
        }}
      />
      
      {/* Modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div 
          className="bg-slate-900 border border-slate-700/50 rounded-xl max-w-lg w-full max-h-[90vh] overflow-y-auto shadow-2xl"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="p-6 border-b border-slate-700/50">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-white">Manage Plan</h2>
                <p className="text-slate-400 text-sm mt-1">{plan.name}</p>
              </div>
              <button 
                onClick={() => {
                  onClose();
                  setSelectedAction(null);
                }}
                className="text-slate-400 hover:text-white text-2xl"
              >
                ×
              </button>
            </div>
            
            {plan.goal_race_name && plan.goal_race_date && (
              <div className="mt-4 bg-slate-800/50 rounded-lg p-3">
                <div className="text-sm text-slate-400">Target Race</div>
                <div className="text-white font-semibold">{plan.goal_race_name}</div>
                <div className="text-slate-400 text-sm">{formatDate(plan.goal_race_date)}</div>
              </div>
            )}
          </div>
          
          {/* Actions or Confirmation */}
          <div className="p-6">
            {!selectedAction ? (
              <div className="space-y-3">
                {/* View Full Plan */}
                <button
                  onClick={() => router.push(`/plans/${plan.id}`)}
                  className="w-full p-4 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-left transition-colors group"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-semibold text-white">View Full Plan</div>
                      <div className="text-sm text-slate-400">See all {plan.total_weeks} weeks at a glance</div>
                    </div>
                    <svg className="w-5 h-5 text-slate-500 group-hover:text-white transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </button>
                
                {/* Change Race Date */}
                <button
                  onClick={() => setSelectedAction('change-date')}
                  className="w-full p-4 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-left transition-colors"
                >
                  <div className="font-semibold text-white">Change Race Date</div>
                  <div className="text-sm text-slate-400">Recalculate your plan for a new race date</div>
                </button>
                
                {/* Adjust Plan - NEW */}
                {currentWeek && (
                  <button
                    onClick={() => {
                      setSelectedAction('adjust');
                      setAdjustMode('menu');
                    }}
                    className="w-full p-4 bg-blue-900/30 hover:bg-blue-900/50 border border-blue-700/50 rounded-lg text-left transition-colors"
                  >
                    <div className="font-semibold text-blue-400">Adjust This Week</div>
                    <div className="text-sm text-slate-400">Swap workout days or adjust training load</div>
                  </button>
                )}
                
                {/* Skip Current Week */}
                {currentWeek && (
                  <button
                    onClick={() => setSelectedAction('skip-week')}
                    className="w-full p-4 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-left transition-colors"
                  >
                    <div className="font-semibold text-white">Skip Week {currentWeek}</div>
                    <div className="text-sm text-slate-400">Mark this week as skipped and adjust</div>
                  </button>
                )}
                
                {/* Pause Plan */}
                <button
                  onClick={() => setSelectedAction('pause')}
                  className="w-full p-4 bg-amber-900/30 hover:bg-amber-900/50 border border-amber-700/50 rounded-lg text-left transition-colors"
                >
                  <div className="font-semibold text-amber-400">Pause Plan</div>
                  <div className="text-sm text-slate-400">Freeze your plan temporarily (injury, travel, life)</div>
                </button>
                
                {/* Withdraw */}
                <button
                  onClick={() => setSelectedAction('withdraw')}
                  className="w-full p-4 bg-red-900/30 hover:bg-red-900/50 border border-red-700/50 rounded-lg text-left transition-colors"
                >
                  <div className="font-semibold text-red-400">Withdraw from Race</div>
                  <div className="text-sm text-slate-400">Archive this plan and clear your calendar</div>
                </button>
              </div>
            ) : selectedAction === 'withdraw' ? (
              <div>
                <div className="bg-red-900/20 border border-red-700/50 rounded-lg p-4 mb-4">
                  <div className="text-red-400 font-semibold mb-2">⚠️ This cannot be undone</div>
                  <div className="text-sm text-slate-300">
                    Withdrawing will archive your training plan and remove all planned workouts from your calendar.
                    Your training history will be preserved.
                  </div>
                </div>
                
                <div className="mb-4">
                  <label className="block text-sm text-slate-400 mb-2">
                    Type &quot;withdraw&quot; to confirm:
                  </label>
                  <input
                    type="text"
                    value={confirmText}
                    onChange={(e) => setConfirmText(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700/50 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-red-500"
                    placeholder="withdraw"
                  />
                </div>
                
                <div className="flex gap-3">
                  <button
                    onClick={() => {
                      setSelectedAction(null);
                      setConfirmText('');
                    }}
                    className="flex-1 px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleWithdraw}
                    disabled={confirmText.toLowerCase() !== 'withdraw' || planAction.isPending}
                    className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-slate-700 disabled:text-slate-500 rounded-lg font-semibold transition-colors"
                  >
                    {planAction.isPending ? 'Withdrawing...' : 'Withdraw'}
                  </button>
                </div>
              </div>
            ) : selectedAction === 'pause' ? (
              <div>
                <div className="bg-amber-900/20 border border-amber-700/50 rounded-lg p-4 mb-4">
                  <div className="text-amber-400 font-semibold mb-2">⏸️ Pause Your Training</div>
                  <div className="text-sm text-slate-300">
                    Your plan will be frozen at Week {currentWeek}. When you resume, 
                    workouts will be recalculated from your current week to your race date.
                  </div>
                </div>
                
                <div className="flex gap-3">
                  <button
                    onClick={() => setSelectedAction(null)}
                    className="flex-1 px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handlePause}
                    disabled={planAction.isPending}
                    className="flex-1 px-4 py-2 bg-amber-600 hover:bg-amber-700 disabled:bg-slate-700 rounded-lg font-semibold transition-colors"
                  >
                    {planAction.isPending ? 'Pausing...' : 'Pause Plan'}
                  </button>
                </div>
              </div>
            ) : selectedAction === 'skip-week' ? (
              <div>
                <div className="bg-slate-800 border border-slate-700/50 rounded-lg p-4 mb-4">
                  <div className="text-white font-semibold mb-2">Skip Week {currentWeek}</div>
                  <div className="text-sm text-slate-300">
                    This week&apos;s workouts will be marked as skipped. Your plan will continue 
                    from next week. This is useful if you&apos;re traveling, sick, or need extra rest.
                  </div>
                </div>
                
                <div className="flex gap-3">
                  <button
                    onClick={() => setSelectedAction(null)}
                    className="flex-1 px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSkipWeek}
                    disabled={planAction.isPending}
                    className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 rounded-lg font-semibold transition-colors"
                  >
                    {planAction.isPending ? 'Skipping...' : 'Skip This Week'}
                  </button>
                </div>
              </div>
            ) : selectedAction === 'change-date' ? (
              <div>
                <div className="mb-4">
                  <label className="block text-sm text-slate-400 mb-2">
                    New Race Date
                  </label>
                  <input
                    type="date"
                    value={newRaceDate}
                    onChange={(e) => setNewRaceDate(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700/50 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                    min={new Date().toISOString().split('T')[0]}
                  />
                </div>
                
                <div className="bg-slate-800 border border-slate-700/50 rounded-lg p-4 mb-4">
                  <div className="text-sm text-slate-300">
                    Your plan will be recalculated to peak on your new race date. 
                    Workouts already completed will be preserved.
                  </div>
                </div>
                
                <div className="flex gap-3">
                  <button
                    onClick={() => setSelectedAction(null)}
                    className="flex-1 px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleChangeDate}
                    disabled={!newRaceDate || planAction.isPending}
                    className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:text-slate-500 rounded-lg font-semibold transition-colors"
                  >
                    {planAction.isPending ? 'Updating...' : 'Update Race Date'}
                  </button>
                </div>
              </div>
            ) : selectedAction === 'adjust' ? (
              <div>
                {/* Adjust Menu */}
                {adjustMode === 'menu' && (
                  <div className="space-y-3">
                    <div className="text-center mb-4">
                      <span className="px-3 py-1.5 bg-blue-600 text-white rounded-full text-sm font-medium">
                        Week {currentWeek}
                      </span>
                      {canModify && (
                        <span className="ml-2 px-2 py-1 bg-emerald-600/30 text-emerald-400 rounded text-xs">
                          Full Control
                        </span>
                      )}
                    </div>
                    
                    <button
                      onClick={() => setAdjustMode('swap')}
                      className="w-full p-4 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-left transition-colors"
                    >
                      <div className="font-semibold text-white">🔄 Swap Workout Days</div>
                      <div className="text-sm text-slate-400">Swap two workouts with each other</div>
                    </button>
                    
                    <button
                      onClick={() => setAdjustMode('load')}
                      className="w-full p-4 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-left transition-colors"
                    >
                      <div className="font-semibold text-white">📊 Adjust Training Load</div>
                      <div className="text-sm text-slate-400">Make this week easier or slightly harder</div>
                    </button>
                    
                    {/* Full control options - paid tier only */}
                    {canModify ? (
                      <>
                        <div className="border-t border-slate-700/50 pt-3 mt-3">
                          <div className="text-xs text-slate-500 uppercase tracking-wide mb-2">Full Control</div>
                        </div>
                        
                        <button
                          onClick={() => setAdjustMode('move')}
                          className="w-full p-4 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-left transition-colors"
                        >
                          <div className="font-semibold text-white">📅 Move Workout</div>
                          <div className="text-sm text-slate-400">Reschedule any workout to a different date</div>
                        </button>
                        
                        <button
                          onClick={() => setAdjustMode('edit')}
                          className="w-full p-4 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-left transition-colors"
                        >
                          <div className="font-semibold text-white">✏️ Edit Workout</div>
                          <div className="text-sm text-slate-400">Change type, distance, or details</div>
                        </button>
                        
                        <button
                          onClick={() => setAdjustMode('add')}
                          className="w-full p-4 bg-emerald-900/30 hover:bg-emerald-900/50 border border-emerald-700/50 rounded-lg text-left transition-colors"
                        >
                          <div className="font-semibold text-emerald-400">➕ Add Workout</div>
                          <div className="text-sm text-slate-400">Add a new workout on any day</div>
                        </button>
                      </>
                    ) : (
                      <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4 text-center">
                        <div className="text-slate-400 text-sm mb-2">Want full control?</div>
                        <div className="text-xs text-slate-500">
                          Upgrade to move, edit, add, or remove any workout
                        </div>
                      </div>
                    )}
                    
                    <button
                      onClick={() => setSelectedAction(null)}
                      className="w-full px-4 py-2 bg-slate-800/50 hover:bg-slate-700 rounded-lg transition-colors text-slate-400"
                    >
                      ← Back
                    </button>
                  </div>
                )}
                
                {/* Swap Days UI */}
                {adjustMode === 'swap' && (
                  <div>
                    <div className="mb-4">
                      <div className="text-white font-semibold mb-2">🔄 Swap Workout Days</div>
                      <div className="text-sm text-slate-400">
                        Select two workouts to swap their days. Tap to select.
                      </div>
                    </div>
                    
                    {weekLoading ? (
                      <div className="text-center py-8 text-slate-500">Loading workouts...</div>
                    ) : weekData?.workouts?.length > 0 ? (
                      <div className="space-y-2 mb-4">
                        {(weekData.workouts as WeekWorkout[]).filter((w: WeekWorkout) => !w.completed && !w.skipped).map((workout: WeekWorkout) => {
                          const isSelected = swapSelection.includes(workout.id);
                          const distanceMiles = workout.target_distance_km 
                            ? (workout.target_distance_km * 0.621371).toFixed(1)
                            : null;
                          
                          return (
                            <button
                              key={workout.id}
                              onClick={() => handleSwapSelection(workout.id)}
                              disabled={swapDays.isPending}
                              className={`w-full p-3 rounded-lg text-left transition-all ${
                                isSelected 
                                  ? 'bg-blue-600 border-2 border-blue-400 ring-2 ring-blue-400/50' 
                                  : 'bg-slate-800 border border-slate-700/50 hover:border-slate-600'
                              }`}
                            >
                              <div className="flex items-center justify-between">
                                <div>
                                  <div className="text-xs text-slate-400 mb-0.5">{workout.day_name}</div>
                                  <div className={`font-semibold ${isSelected ? 'text-white' : 'text-slate-200'}`}>
                                    {workout.title}
                                  </div>
                                  {distanceMiles && (
                                    <div className="text-xs text-slate-400 mt-0.5">{distanceMiles} mi</div>
                                  )}
                                </div>
                                {isSelected && (
                                  <div className="w-6 h-6 bg-blue-400 rounded-full flex items-center justify-center text-white text-sm">
                                    {swapSelection.indexOf(workout.id) + 1}
                                  </div>
                                )}
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    ) : (
                      <div className="text-center py-8 text-slate-500">No workouts available to swap</div>
                    )}
                    
                    {swapSelection.length === 1 && (
                      <div className="bg-blue-900/30 border border-blue-700/50 rounded-lg p-3 mb-4 text-sm text-blue-300">
                        Select one more workout to swap with
                      </div>
                    )}
                    
                    {swapDays.isPending && (
                      <div className="text-center py-4 text-blue-400">Swapping workouts...</div>
                    )}
                    
                    {swapDays.isError && (
                      <div className="bg-red-900/20 border border-red-700/50 rounded-lg p-3 mb-4 text-sm text-red-400">
                        {swapDays.error instanceof Error ? swapDays.error.message : 'Swap failed'}
                      </div>
                    )}
                    
                    {swapDays.isSuccess && (
                      <div className="bg-emerald-900/20 border border-emerald-700/50 rounded-lg p-3 mb-4 text-sm text-emerald-400">
                        ✓ Workouts swapped successfully!
                      </div>
                    )}
                    
                    <div className="flex gap-3">
                      <button
                        onClick={() => {
                          setAdjustMode('menu');
                          setSwapSelection([]);
                        }}
                        className="flex-1 px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors"
                      >
                        ← Back
                      </button>
                    </div>
                  </div>
                )}
                
                {/* Adjust Load UI */}
                {adjustMode === 'load' && (
                  <div>
                    <div className="mb-4">
                      <div className="text-white font-semibold mb-2">📊 Adjust Training Load</div>
                      <div className="text-sm text-slate-400">
                        Choose how to adjust Week {currentWeek}&apos;s training:
                      </div>
                    </div>
                    
                    <div className="space-y-3 mb-4">
                      <button
                        onClick={() => handleAdjustLoad('reduce_light')}
                        disabled={adjustLoad.isPending}
                        className={`w-full p-4 rounded-lg text-left transition-all ${
                          selectedLoadAdjustment === 'reduce_light'
                            ? 'bg-blue-600 border-2 border-blue-400'
                            : 'bg-slate-800 border border-slate-700/50 hover:border-slate-600'
                        }`}
                      >
                        <div className="font-semibold text-white">🟡 Reduce Light</div>
                        <div className="text-sm text-slate-400">
                          Convert one quality session to easy, reduce all distances by 10%
                        </div>
                      </button>
                      
                      <button
                        onClick={() => handleAdjustLoad('reduce_moderate')}
                        disabled={adjustLoad.isPending}
                        className={`w-full p-4 rounded-lg text-left transition-all ${
                          selectedLoadAdjustment === 'reduce_moderate'
                            ? 'bg-amber-600 border-2 border-amber-400'
                            : 'bg-amber-900/30 border border-amber-700/50 hover:border-amber-600/50'
                        }`}
                      >
                        <div className="font-semibold text-amber-400">🟠 Recovery Week</div>
                        <div className="text-sm text-slate-400">
                          All easy runs at 70% volume — good for illness, travel, or extra recovery
                        </div>
                      </button>
                      
                      <button
                        onClick={() => handleAdjustLoad('increase_light')}
                        disabled={adjustLoad.isPending}
                        className={`w-full p-4 rounded-lg text-left transition-all ${
                          selectedLoadAdjustment === 'increase_light'
                            ? 'bg-emerald-600 border-2 border-emerald-400'
                            : 'bg-emerald-900/30 border border-emerald-700/50 hover:border-emerald-600/50'
                        }`}
                      >
                        <div className="font-semibold text-emerald-400">🟢 Increase Light</div>
                        <div className="text-sm text-slate-400">
                          Add ~1 mile to easy runs — feeling good and want a bit more
                        </div>
                      </button>
                    </div>
                    
                    {adjustLoad.isPending && (
                      <div className="text-center py-4 text-blue-400">Adjusting load...</div>
                    )}
                    
                    {adjustLoad.isError && (
                      <div className="bg-red-900/20 border border-red-700/50 rounded-lg p-3 mb-4 text-sm text-red-400">
                        {adjustLoad.error instanceof Error ? adjustLoad.error.message : 'Adjustment failed'}
                      </div>
                    )}
                    
                    {adjustLoad.isSuccess && (
                      <div className="bg-emerald-900/20 border border-emerald-700/50 rounded-lg p-3 mb-4 text-sm text-emerald-400">
                        ✓ Week adjusted! Check your calendar.
                      </div>
                    )}
                    
                    <div className="flex gap-3">
                      <button
                        onClick={() => {
                          setAdjustMode('menu');
                          setSelectedLoadAdjustment('');
                        }}
                        className="flex-1 px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors"
                      >
                        ← Back
                      </button>
                    </div>
                  </div>
                )}
                
                {/* Move Workout UI */}
                {adjustMode === 'move' && (
                  <div>
                    <div className="mb-4">
                      <div className="text-white font-semibold mb-2">📅 Move Workout</div>
                      <div className="text-sm text-slate-400">
                        {selectedWorkout ? 'Choose a new date' : 'Select a workout to move'}
                      </div>
                    </div>
                    
                    {!selectedWorkout ? (
                      <>
                        {weekLoading ? (
                          <div className="text-center py-8 text-slate-500">Loading workouts...</div>
                        ) : weekData?.workouts?.length > 0 ? (
                          <div className="space-y-2 mb-4">
                            {(weekData.workouts as WeekWorkout[]).filter((w: WeekWorkout) => !w.completed && !w.skipped).map((workout: WeekWorkout) => (
                              <button
                                key={workout.id}
                                onClick={() => handleStartMove(workout)}
                                className="w-full p-3 rounded-lg text-left bg-slate-800 border border-slate-700/50 hover:border-blue-500 transition-all"
                              >
                                <div className="flex items-center justify-between">
                                  <div>
                                    <div className="text-xs text-slate-400 mb-0.5">{workout.day_name}</div>
                                    <div className="font-semibold text-slate-200">{workout.title}</div>
                                  </div>
                                  <svg className="w-5 h-5 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                  </svg>
                                </div>
                              </button>
                            ))}
                          </div>
                        ) : (
                          <div className="text-center py-8 text-slate-500">No workouts to move</div>
                        )}
                      </>
                    ) : (
                      <div className="space-y-4">
                        <div className="bg-blue-900/20 border border-blue-700/50 rounded-lg p-3">
                          <div className="text-sm text-blue-300">Moving: {selectedWorkout.title}</div>
                          <div className="text-xs text-slate-400">Currently on {selectedWorkout.day_name}</div>
                        </div>
                        
                        <div>
                          <label className="block text-sm text-slate-400 mb-2">New Date</label>
                          <input
                            type="date"
                            value={moveDate}
                            onChange={(e) => setMoveDate(e.target.value)}
                            className="w-full bg-slate-800 border border-slate-700/50 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                          />
                        </div>
                        
                        <button
                          onClick={() => moveWorkout.mutate({ workoutId: selectedWorkout.id, newDate: moveDate })}
                          disabled={!moveDate || moveWorkout.isPending}
                          className="w-full px-4 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:text-slate-500 rounded-lg font-semibold transition-colors"
                        >
                          {moveWorkout.isPending ? 'Moving...' : 'Move Workout'}
                        </button>
                        
                        {moveWorkout.isError && (
                          <div className="bg-red-900/20 border border-red-700/50 rounded-lg p-3 text-sm text-red-400">
                            {moveWorkout.error instanceof Error ? moveWorkout.error.message : 'Move failed'}
                          </div>
                        )}
                      </div>
                    )}
                    
                    <div className="flex gap-3 mt-4">
                      <button
                        onClick={() => {
                          setAdjustMode('menu');
                          setSelectedWorkout(null);
                          setMoveDate('');
                        }}
                        className="flex-1 px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors"
                      >
                        ← Back
                      </button>
                    </div>
                  </div>
                )}
                
                {/* Edit Workout UI */}
                {adjustMode === 'edit' && (
                  <div>
                    <div className="mb-4">
                      <div className="text-white font-semibold mb-2">✏️ Edit Workout</div>
                      <div className="text-sm text-slate-400">
                        {selectedWorkout ? 'Update workout details' : 'Select a workout to edit'}
                      </div>
                    </div>
                    
                    {!selectedWorkout ? (
                      <>
                        {weekLoading ? (
                          <div className="text-center py-8 text-slate-500">Loading workouts...</div>
                        ) : weekData?.workouts?.length > 0 ? (
                          <div className="space-y-2 mb-4">
                            {(weekData.workouts as WeekWorkout[]).filter((w: WeekWorkout) => !w.completed && !w.skipped).map((workout: WeekWorkout) => (
                              <button
                                key={workout.id}
                                onClick={() => handleStartEdit(workout)}
                                className="w-full p-3 rounded-lg text-left bg-slate-800 border border-slate-700/50 hover:border-blue-500 transition-all"
                              >
                                <div className="flex items-center justify-between">
                                  <div>
                                    <div className="text-xs text-slate-400 mb-0.5">{workout.day_name} · {workout.workout_type}</div>
                                    <div className="font-semibold text-slate-200">{workout.title}</div>
                                    {workout.target_distance_km && (
                                      <div className="text-xs text-slate-500">{(workout.target_distance_km * 0.621371).toFixed(1)} mi</div>
                                    )}
                                  </div>
                                  <svg className="w-5 h-5 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                  </svg>
                                </div>
                              </button>
                            ))}
                          </div>
                        ) : (
                          <div className="text-center py-8 text-slate-500">No workouts to edit</div>
                        )}
                        
                        {/* Delete option */}
                        {weekData?.workouts?.length > 0 && (
                          <div className="border-t border-slate-700/50 pt-4 mt-4">
                            <div className="text-xs text-slate-500 mb-2">Or remove a workout:</div>
                            <div className="space-y-2">
                              {(weekData.workouts as WeekWorkout[]).filter((w: WeekWorkout) => !w.completed && !w.skipped).map((workout: WeekWorkout) => (
                                <button
                                  key={workout.id}
                                  onClick={() => {
                                    if (confirm(`Remove "${workout.title}" from your plan?`)) {
                                      deleteWorkout.mutate({ workoutId: workout.id });
                                    }
                                  }}
                                  disabled={deleteWorkout.isPending}
                                  className="w-full p-2 rounded-lg text-left bg-red-900/20 border border-red-700/30 hover:border-red-500/50 transition-all text-sm"
                                >
                                  <span className="text-red-400">🗑️ Remove {workout.title}</span>
                                </button>
                              ))}
                            </div>
                          </div>
                        )}
                      </>
                    ) : (
                      <div className="space-y-4">
                        <div className="bg-blue-900/20 border border-blue-700/50 rounded-lg p-3">
                          <div className="text-sm text-blue-300">Editing: {selectedWorkout.title}</div>
                          <div className="text-xs text-slate-400">{selectedWorkout.day_name}</div>
                        </div>
                        
                        <div>
                          <label className="block text-sm text-slate-400 mb-2">Workout Type</label>
                          <select
                            value={editForm.workout_type}
                            onChange={(e) => setEditForm({ ...editForm, workout_type: e.target.value })}
                            className="w-full bg-slate-800 border border-slate-700/50 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                          >
                            {workoutTypesData?.workout_types?.map((type: WorkoutType) => (
                              <option key={type.value} value={type.value}>{type.label}</option>
                            ))}
                          </select>
                        </div>
                        
                        <div>
                          <label className="block text-sm text-slate-400 mb-2">Title</label>
                          <input
                            type="text"
                            value={editForm.title}
                            onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                            className="w-full bg-slate-800 border border-slate-700/50 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                          />
                        </div>
                        
                        <div>
                          <label className="block text-sm text-slate-400 mb-2">Distance (km)</label>
                          <input
                            type="number"
                            step="0.1"
                            value={editForm.target_distance_km}
                            onChange={(e) => setEditForm({ ...editForm, target_distance_km: e.target.value })}
                            className="w-full bg-slate-800 border border-slate-700/50 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                            placeholder="e.g., 10.5"
                          />
                        </div>
                        
                        <button
                          onClick={() => editWorkout.mutate({
                            workoutId: selectedWorkout.id,
                            updates: {
                              workout_type: editForm.workout_type,
                              title: editForm.title,
                              target_distance_km: editForm.target_distance_km ? parseFloat(editForm.target_distance_km) : null,
                            },
                          })}
                          disabled={editWorkout.isPending}
                          className="w-full px-4 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:text-slate-500 rounded-lg font-semibold transition-colors"
                        >
                          {editWorkout.isPending ? 'Saving...' : 'Save Changes'}
                        </button>
                        
                        {editWorkout.isError && (
                          <div className="bg-red-900/20 border border-red-700/50 rounded-lg p-3 text-sm text-red-400">
                            {editWorkout.error instanceof Error ? editWorkout.error.message : 'Update failed'}
                          </div>
                        )}
                      </div>
                    )}
                    
                    <div className="flex gap-3 mt-4">
                      <button
                        onClick={() => {
                          setAdjustMode('menu');
                          setSelectedWorkout(null);
                        }}
                        className="flex-1 px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors"
                      >
                        ← Back
                      </button>
                    </div>
                  </div>
                )}
                
                {/* Add Workout UI */}
                {adjustMode === 'add' && (
                  <div>
                    <div className="mb-4">
                      <div className="text-white font-semibold mb-2">➕ Add Workout</div>
                      <div className="text-sm text-slate-400">Add a new workout to your plan</div>
                    </div>
                    
                    <div className="space-y-4">
                      <div>
                        <label className="block text-sm text-slate-400 mb-2">Date</label>
                        <input
                          type="date"
                          value={newWorkout.scheduled_date}
                          onChange={(e) => setNewWorkout({ ...newWorkout, scheduled_date: e.target.value })}
                          className="w-full bg-slate-800 border border-slate-700/50 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                        />
                      </div>
                      
                      <div>
                        <label className="block text-sm text-slate-400 mb-2">Workout Type</label>
                        <select
                          value={newWorkout.workout_type}
                          onChange={(e) => setNewWorkout({ ...newWorkout, workout_type: e.target.value })}
                          className="w-full bg-slate-800 border border-slate-700/50 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                        >
                          {workoutTypesData?.workout_types?.map((type: WorkoutType) => (
                            <option key={type.value} value={type.value}>{type.label}</option>
                          ))}
                        </select>
                      </div>
                      
                      <div>
                        <label className="block text-sm text-slate-400 mb-2">Title (optional)</label>
                        <input
                          type="text"
                          value={newWorkout.title}
                          onChange={(e) => setNewWorkout({ ...newWorkout, title: e.target.value })}
                          className="w-full bg-slate-800 border border-slate-700/50 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                          placeholder="e.g., Easy Recovery Run"
                        />
                      </div>
                      
                      <div>
                        <label className="block text-sm text-slate-400 mb-2">Distance (km, optional)</label>
                        <input
                          type="number"
                          step="0.1"
                          value={newWorkout.target_distance_km}
                          onChange={(e) => setNewWorkout({ ...newWorkout, target_distance_km: e.target.value })}
                          className="w-full bg-slate-800 border border-slate-700/50 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                          placeholder="e.g., 8.0"
                        />
                      </div>
                      
                      <button
                        onClick={() => addWorkout.mutate(newWorkout)}
                        disabled={!newWorkout.scheduled_date || !newWorkout.workout_type || addWorkout.isPending}
                        className="w-full px-4 py-3 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-700 disabled:text-slate-500 rounded-lg font-semibold transition-colors"
                      >
                        {addWorkout.isPending ? 'Adding...' : 'Add Workout'}
                      </button>
                      
                      {addWorkout.isError && (
                        <div className="bg-red-900/20 border border-red-700/50 rounded-lg p-3 text-sm text-red-400">
                          {addWorkout.error instanceof Error ? addWorkout.error.message : 'Add failed'}
                        </div>
                      )}
                      
                      {addWorkout.isSuccess && (
                        <div className="bg-emerald-900/20 border border-emerald-700/50 rounded-lg p-3 text-sm text-emerald-400">
                          ✓ Workout added! Check your calendar.
                        </div>
                      )}
                    </div>
                    
                    <div className="flex gap-3 mt-4">
                      <button
                        onClick={() => {
                          setAdjustMode('menu');
                          setNewWorkout({ scheduled_date: '', workout_type: 'easy', title: '', target_distance_km: '', coach_notes: '' });
                        }}
                        className="flex-1 px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors"
                      >
                        ← Back
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ) : null}
            
            {planAction.isError && (
              <div className="mt-4 bg-red-900/20 border border-red-700/50 rounded-lg p-3 text-sm text-red-400">
                {planAction.error instanceof Error ? planAction.error.message : 'An error occurred'}
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
