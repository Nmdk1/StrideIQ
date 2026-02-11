'use client';

/**
 * DayDetailPanel Component
 * 
 * Slide-in panel showing full details for a selected day:
 * - Planned workout with structure
 * - Actual activities (clickable → full detail page)
 * - Notes (pre/post)
 * - Insights
 * - Coach chat
 * 
 * DESIGN: Every element is actionable. No dead ends.
 * TONE: Sparse, direct. Data speaks.
 */

import React, { useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useUnits } from '@/lib/context/UnitsContext';
import { useCalendarDay, useAddNote, useSendCoachMessage } from '@/lib/hooks/queries/calendar';
import type { CalendarDay, CalendarNote, InlineInsight } from '@/lib/api/services/calendar';
import { apiClient } from '@/lib/api/client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

interface DayDetailPanelProps {
  date: string;
  isOpen: boolean;
  onClose: () => void;
}

export function DayDetailPanel({ date, isOpen, onClose }: DayDetailPanelProps) {
  const { formatDistance, units, distanceUnitShort } = useUnits();
  const { data: dayData, isLoading } = useCalendarDay(date, isOpen);
  const addNote = useAddNote();
  const sendCoachMessage = useSendCoachMessage();
  const queryClient = useQueryClient();
  
  const [noteText, setNoteText] = useState('');
  const [coachMessage, setCoachMessage] = useState('');
  const [coachResponse, setCoachResponse] = useState('');
  const [coachError, setCoachError] = useState<string | null>(null);
  const [coachPendingStartedAt, setCoachPendingStartedAt] = useState<number | null>(null);
  const coachAbortRef = useRef<AbortController | null>(null);
  const isCoachSending = coachPendingStartedAt !== null;

  // Day-level plan edits
  const [isEditingPlan, setIsEditingPlan] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [swapTargetId, setSwapTargetId] = useState<string>('');
  const [editForm, setEditForm] = useState<{
    workout_type: string;
    workout_subtype: string;
    title: string;
    distance: string;
    coach_notes: string;
    description: string;
  }>({
    workout_type: '',
    workout_subtype: '',
    title: '',
    distance: '',
    coach_notes: '',
    description: '',
  });

  const planned = dayData?.planned_workout;
  const canEditPlannedWorkout = !!planned && !planned.completed && !planned.skipped;

  // Init edit form from planned workout
  React.useEffect(() => {
    if (!planned) return;
    const distKm = planned.target_distance_km ?? null;
    const distDisplay =
      distKm === null
        ? ''
        : units === 'imperial'
          ? String((distKm * 0.621371).toFixed(1))
          : String(distKm.toFixed(1));
    setEditForm({
      workout_type: planned.workout_type || 'easy',
      title: planned.title || '',
      distance: distDisplay,
      workout_subtype: planned.workout_subtype || '',
      coach_notes: planned.coach_notes || '',
      description: planned.description || '',
    });
  }, [planned, planned?.id, planned?.workout_type, planned?.title, planned?.target_distance_km, units]);

  const planId = planned?.plan_id;
  const weekNumber = planned?.week_number;

  // Fetch workout types (for the dropdown) when editing
  const { data: workoutTypesData, isLoading: workoutTypesLoading } = useQuery({
    queryKey: ['plan-workout-types', planId],
    queryFn: async () => {
      if (!planId) throw new Error('Missing plan id');
      return apiClient.get<{ workout_types: Array<{ value: string; label: string; description: string }>; can_modify: boolean }>(
        `/v2/plans/${planId}/workout-types`
      );
    },
    enabled: isEditingPlan && !!planId,
    staleTime: 1000 * 60 * 60,
  });

  // Fetch the week workouts (for swap) when editing
  const { data: weekData, isLoading: weekLoading } = useQuery({
    queryKey: ['plan-week-workouts', planId, weekNumber],
    queryFn: async () => {
      if (!planId || !weekNumber) throw new Error('Missing plan id/week');
      return apiClient.get<{ workouts: Array<{ id: string; day_name: string; date: string | null; title: string; completed: boolean; skipped: boolean }> }>(
        `/v2/plans/${planId}/week/${weekNumber}`
      );
    },
    enabled: isEditingPlan && !!planId && !!weekNumber,
  });

  const swapOptions = useMemo(() => {
    const currentId = planned?.id;
    const workouts = weekData?.workouts || [];
    return workouts.filter(w => w.id !== currentId && !w.completed && !w.skipped && !!w.date);
  }, [weekData?.workouts, planned?.id]);

  const updateWorkoutMutation = useMutation({
    mutationFn: async () => {
      if (!planId || !planned?.id) throw new Error('Missing plan/workout id');
      setEditError(null);

      const distanceValue = editForm.distance.trim();
      const distanceKm =
        distanceValue === ''
          ? null
          : units === 'imperial'
            ? parseFloat(distanceValue) * 1.60934
            : parseFloat(distanceValue);

      if (distanceKm !== null && (Number.isNaN(distanceKm) || distanceKm < 0)) {
        throw new Error('Distance must be a number');
      }

      return apiClient.put(`/v2/plans/${planId}/workouts/${planned.id}`, {
        workout_type: editForm.workout_type,
        workout_subtype: editForm.workout_subtype || null,
        title: editForm.title,
        target_distance_km: distanceKm === null ? null : Number(distanceKm.toFixed(2)),
        coach_notes: editForm.coach_notes,
        description: editForm.description,
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['calendar'] });
      setIsEditingPlan(false);
      setSwapTargetId('');
    },
    onError: (e: any) => {
      setEditError(e?.message || 'Unable to update workout.');
    },
  });

  const swapDaysMutation = useMutation({
    mutationFn: async () => {
      if (!planId || !planned?.id) throw new Error('Missing plan/workout id');
      if (!swapTargetId) throw new Error('Select a workout to swap with');
      setEditError(null);
      return apiClient.post(`/v2/plans/${planId}/swap-days`, {
        workout_id_1: planned.id,
        workout_id_2: swapTargetId,
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['calendar'] });
      setIsEditingPlan(false);
      setSwapTargetId('');
    },
    onError: (e: any) => {
      setEditError(e?.message || 'Unable to swap workouts.');
    },
  });
  
  // Parse date as local timezone (not UTC) to avoid off-by-one errors
  // "2026-01-16" should display as Jan 16 regardless of timezone
  const [year, month, day] = date.split('-').map(Number);
  const dateObj = new Date(year, month - 1, day); // month is 0-indexed
  const formattedDate = dateObj.toLocaleDateString('en-US', { 
    weekday: 'long', 
    month: 'long', 
    day: 'numeric' 
  });
  
  const handleAddNote = async () => {
    if (!noteText.trim()) return;
    
    await addNote.mutateAsync({
      date,
      note: {
        note_type: 'free_text',
        text_content: noteText,
      }
    });
    setNoteText('');
  };
  
  const handleSendCoachMessage = async (messageOverride?: string) => {
    const messageToSend = (messageOverride ?? coachMessage).trim();
    if (!messageToSend) return;
    // Prevent double-submits even if React Query hasn't flipped isPending yet.
    if (isCoachSending) return;

    setCoachError(null);
    setCoachPendingStartedAt(Date.now());
    coachAbortRef.current?.abort();
    coachAbortRef.current = new AbortController();
    try {
      const response = await sendCoachMessage.mutateAsync({
        request: {
          message: messageToSend,
          context_type: 'day',
          context_date: date,
        },
        signal: coachAbortRef.current.signal,
      });

      setCoachResponse(response.response);
      setCoachMessage('');
    } catch (e: any) {
      const msg = e?.message || 'Unable to reach coach right now.';
      // Abort is user-driven or timeout-driven; keep it neutral.
      if (msg.toLowerCase().includes('cancel')) {
        setCoachError('Cancelled.');
      } else if (msg.toLowerCase().includes('timed out')) {
        setCoachError('Still working, but the request timed out. Try again.');
      } else {
        setCoachError(msg);
      }
    } finally {
      setCoachPendingStartedAt(null);
    }
  };

  const coachElapsedSec = coachPendingStartedAt ? Math.max(1, Math.floor((Date.now() - coachPendingStartedAt) / 1000)) : 0;
  
  // Quick questions - sparse, data-focused
  const quickQuestions = [
    "What does the data say?",
    "How did similar runs go?",
    "What changed this week?",
  ];
  
  return (
    <>
      {/* Overlay */}
      <div 
        className={`fixed inset-0 bg-black/50 z-40 transition-opacity duration-300 ${
          isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
        onClick={onClose}
      />
      
      {/* Panel */}
      <div className={`
        fixed right-0 top-0 h-full w-[420px] max-w-full
        bg-slate-900 border-l border-slate-700/50
        z-50 overflow-y-auto
        transition-transform duration-300 ease-out
        ${isOpen ? 'translate-x-0' : 'translate-x-full'}
      `}>
        {/* Header */}
        <div className="sticky top-0 bg-slate-900 border-b border-slate-700/50 p-4 flex justify-between items-center">
          <div>
            <h2 className="text-lg font-semibold text-white">{formattedDate}</h2>
            {dayData?.planned_workout && (
              <p className="text-sm text-slate-400">
                {dayData.planned_workout.phase && `${dayData.planned_workout.phase.replace(/_/g, ' ')} phase`}
                {dayData.planned_workout.phase && dayData.planned_workout.workout_type && ' • '}
                {dayData.planned_workout.workout_type?.replace(/_/g, ' ')}
              </p>
            )}
          </div>
          <button 
            onClick={onClose}
            className="text-slate-400 hover:text-white text-2xl"
          >
            ×
          </button>
        </div>
        
        {isLoading ? (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-500" />
          </div>
        ) : dayData ? (
          <div className="p-4 space-y-4">
            {/* Key Insight Banner - if available */}
            {dayData.inline_insight && (
              <div className={`rounded-lg px-4 py-3 ${
                dayData.inline_insight.sentiment === 'positive' ? 'bg-emerald-900/30 border border-emerald-700/30' :
                dayData.inline_insight.sentiment === 'negative' ? 'bg-orange-900/30 border border-orange-700/30' :
                'bg-slate-800/50 border border-slate-700/50/30'
              }`}>
                <div className="flex items-center justify-between">
                  <span className={`text-sm font-medium ${
                    dayData.inline_insight.sentiment === 'positive' ? 'text-emerald-400' :
                    dayData.inline_insight.sentiment === 'negative' ? 'text-orange-400' :
                    'text-slate-300'
                  }`}>
                    {dayData.inline_insight.value}
                  </span>
                  {dayData.inline_insight.delta && (
                    <span className="text-xs text-slate-500">
                      {dayData.inline_insight.delta > 0 ? '+' : ''}{dayData.inline_insight.delta}% vs avg
                    </span>
                  )}
                </div>
              </div>
            )}
            
            {/* Planned Workout Section */}
            {dayData.planned_workout && (
              <section className="bg-slate-800 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-xs uppercase tracking-wider text-slate-500">Planned Workout</h3>
                  {canEditPlannedWorkout && (
                    <button
                      onClick={() => {
                        setEditError(null);
                        setIsEditingPlan(v => !v);
                      }}
                      className="text-xs text-blue-300 hover:text-blue-200"
                    >
                      {isEditingPlan ? 'Close' : 'Edit'}
                    </button>
                  )}
                </div>
                <div className="border-l-2 border-orange-500 pl-3">
                  <div className="font-semibold text-white">{dayData.planned_workout.title}</div>
                  {dayData.planned_workout.target_distance_km && (
                    <div className="text-slate-400 text-sm">
                      {formatDistance(dayData.planned_workout.target_distance_km * 1000, 1)}
                    </div>
                  )}
                  {/* Pace - the key training information */}
                  {dayData.planned_workout.coach_notes && (
                    <div className="text-green-400 text-sm mt-2 font-semibold">
                      {dayData.planned_workout.coach_notes}
                    </div>
                  )}
                  {dayData.planned_workout.description && (
                    <div className="text-slate-300 text-sm mt-2 bg-slate-900/50 rounded p-2 font-mono">
                      {dayData.planned_workout.description}
                    </div>
                  )}
                </div>

                {/* Day-level plan editor */}
                {isEditingPlan && canEditPlannedWorkout && (
                  <div className="mt-4 bg-slate-900/50 border border-slate-700/50 rounded-lg p-3 space-y-3">
                    {workoutTypesData?.can_modify === false && (
                      <div className="text-xs text-slate-300 bg-slate-800/60 border border-slate-700/50 rounded p-2">
                        Full plan edits require a paid tier. You can still swap and adjust load from “Manage Plan.”
                      </div>
                    )}

                    {editError && (
                      <div className="text-sm text-red-300 bg-red-900/20 border border-red-700/40 rounded p-2">
                        {editError}
                      </div>
                    )}

                    <div className="grid grid-cols-2 gap-2">
                      <div className="col-span-2">
                        <label className="block text-xs text-slate-400 mb-1">Workout type</label>
                        <select
                          value={editForm.workout_type}
                          onChange={(e) => setEditForm({ ...editForm, workout_type: e.target.value })}
                          className="w-full bg-slate-900 border border-slate-700/50 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                          disabled={workoutTypesLoading || workoutTypesData?.can_modify === false}
                        >
                          {(workoutTypesData?.workout_types || []).map((t) => (
                            <option key={t.value} value={t.value}>
                              {t.label}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div className="col-span-2">
                        <label className="block text-xs text-slate-400 mb-1">Subtype (optional)</label>
                        <input
                          type="text"
                          value={editForm.workout_subtype}
                          onChange={(e) => setEditForm({ ...editForm, workout_subtype: e.target.value })}
                          placeholder="e.g., easy_to_mp"
                          className="w-full bg-slate-900 border border-slate-700/50 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                          disabled={workoutTypesData?.can_modify === false}
                        />
                      </div>

                      <div className="col-span-2">
                        <label className="block text-xs text-slate-400 mb-1">Title</label>
                        <input
                          type="text"
                          value={editForm.title}
                          onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                          className="w-full bg-slate-900 border border-slate-700/50 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                          disabled={workoutTypesData?.can_modify === false}
                        />
                      </div>

                      <div className="col-span-1">
                        <label className="block text-xs text-slate-400 mb-1">Distance ({distanceUnitShort})</label>
                        <input
                          type="number"
                          step="0.1"
                          value={editForm.distance}
                          onChange={(e) => setEditForm({ ...editForm, distance: e.target.value })}
                          className="w-full bg-slate-900 border border-slate-700/50 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                          disabled={workoutTypesData?.can_modify === false}
                        />
                      </div>

                      <div className="col-span-2">
                        <label className="block text-xs text-slate-400 mb-1">Pace notes</label>
                        <input
                          type="text"
                          value={editForm.coach_notes}
                          onChange={(e) => setEditForm({ ...editForm, coach_notes: e.target.value })}
                          placeholder="e.g., Start easy, smoothly build to MP"
                          className="w-full bg-slate-900 border border-slate-700/50 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                          disabled={workoutTypesData?.can_modify === false}
                        />
                      </div>

                      <div className="col-span-2">
                        <label className="block text-xs text-slate-400 mb-1">Workout details</label>
                        <textarea
                          value={editForm.description}
                          onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                          placeholder="Write the workout in detail…"
                          rows={3}
                          className="w-full bg-slate-900 border border-slate-700/50 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                          disabled={workoutTypesData?.can_modify === false}
                        />
                      </div>

                      <div className="col-span-1 flex items-end">
                        <button
                          onClick={() => updateWorkoutMutation.mutate()}
                          disabled={updateWorkoutMutation.isPending || workoutTypesData?.can_modify === false}
                          className="w-full px-3 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 rounded-lg text-sm font-semibold transition-colors"
                        >
                          {updateWorkoutMutation.isPending ? 'Saving…' : 'Save'}
                        </button>
                      </div>
                    </div>

                    <div className="border-t border-slate-700/50 pt-3">
                      <div className="text-xs text-slate-400 mb-2">Swap with another day (this week)</div>
                      {weekLoading ? (
                        <div className="text-sm text-slate-500">Loading week…</div>
                      ) : (
                        <div className="flex gap-2">
                          <select
                            value={swapTargetId}
                            onChange={(e) => setSwapTargetId(e.target.value)}
                            className="flex-1 bg-slate-900 border border-slate-700/50 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-purple-500"
                          >
                            <option value="">Select day…</option>
                            {swapOptions.map((w) => (
                              <option key={w.id} value={w.id}>
                                {w.day_name} — {w.title}
                              </option>
                            ))}
                          </select>
                          <button
                            onClick={() => swapDaysMutation.mutate()}
                            disabled={swapDaysMutation.isPending || !swapTargetId}
                            className="px-3 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-slate-700 rounded-lg text-sm font-semibold transition-colors"
                          >
                            {swapDaysMutation.isPending ? 'Swapping…' : 'Swap'}
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </section>
            )}
            
            {/* Actual Activities Section - CLICKABLE to full detail */}
            {dayData.activities.length > 0 && (
              <section className="bg-slate-800 rounded-lg p-4">
                <h3 className="text-xs uppercase tracking-wider text-slate-500 mb-3">Actual</h3>
                <div className="border-l-2 border-emerald-500 pl-3 space-y-3">
                  {dayData.activities.map((activity) => (
                    <div key={activity.id} className="space-y-2">
                      <Link 
                        href={`/activities/${activity.id}`}
                        className="block group hover:bg-slate-700/30 rounded-lg transition-colors p-2 -m-2"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="font-semibold text-white group-hover:text-emerald-400 transition-colors">
                            {activity.name || 'Run'}
                          </div>
                          <div className="text-slate-500 group-hover:text-emerald-400 transition-colors text-sm flex items-center gap-1">
                            View Details
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                            </svg>
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                          <div className="bg-slate-900/50 rounded p-2 text-center">
                            <div className="text-lg font-bold text-white">
                              {formatDistance(activity.distance_m || 0, 1)}
                            </div>
                            <div className="text-xs text-slate-500">Distance</div>
                          </div>
                          <div className="bg-slate-900/50 rounded p-2 text-center">
                            <div className="text-lg font-bold text-white">
                              {activity.duration_s ? (
                                activity.duration_s >= 3600
                                  ? `${Math.floor(activity.duration_s / 3600)}:${String(Math.floor((activity.duration_s % 3600) / 60)).padStart(2, '0')}:${String(activity.duration_s % 60).padStart(2, '0')}`
                                  : `${Math.floor(activity.duration_s / 60)}:${String(activity.duration_s % 60).padStart(2, '0')}`
                              ) : '--'}
                            </div>
                            <div className="text-xs text-slate-500">Duration</div>
                          </div>
                          {activity.avg_hr && (
                            <div className="bg-slate-900/50 rounded p-2 text-center">
                              <div className="text-lg font-bold text-white">{activity.avg_hr}</div>
                              <div className="text-xs text-slate-500">Avg HR</div>
                            </div>
                          )}
                          {activity.workout_type && (
                            <div className="bg-slate-900/50 rounded p-2 text-center">
                              <div className="text-sm font-bold text-orange-400 uppercase">
                                {activity.workout_type.replace(/_/g, ' ')}
                              </div>
                              <div className="text-xs text-slate-500">Detected</div>
                            </div>
                          )}
                        </div>
                      </Link>
                      {/* Compare to similar runs */}
                      <Link
                        href={`/compare/context/${activity.id}`}
                        className="flex items-center justify-between p-2 bg-slate-900/50 rounded-lg text-xs text-slate-500 hover:text-orange-400 hover:bg-orange-900/20 transition-colors"
                      >
                        <span>👻 Compare to similar runs</span>
                        <span>→</span>
                      </Link>
                    </div>
                  ))}
                </div>
              </section>
            )}
            
            {/* Insights Section */}
            {dayData.insights.length > 0 && (
              <section className="bg-gradient-to-br from-pink-900/30 to-orange-900/30 border border-pink-700/30 rounded-lg p-4">
                <h3 className="text-xs uppercase tracking-wider text-pink-400 mb-3">🔥 Insights</h3>
                <div className="space-y-2">
                  {dayData.insights.map((insight) => (
                    <div key={insight.id} className="text-slate-200 text-sm">
                      <strong>{insight.title}</strong>
                      <p className="text-slate-400 mt-1">{insight.content}</p>
                    </div>
                  ))}
                </div>
              </section>
            )}
            
            {/* Notes Section */}
            <section className="bg-slate-800 rounded-lg p-4">
              <h3 className="text-xs uppercase tracking-wider text-slate-500 mb-3">📝 Notes</h3>
              
              {/* Existing notes */}
              {dayData.notes.length > 0 && (
                <div className="space-y-2 mb-3">
                  {dayData.notes.map((note) => (
                    <div key={note.id} className="bg-slate-900/50 rounded p-2 text-sm text-slate-300">
                      {note.text_content}
                      {note.structured_data && (
                        <div className="flex gap-2 mt-1 flex-wrap">
                          {note.structured_data.sleep_hours && (
                            <span className="text-xs bg-slate-700 px-2 py-0.5 rounded">🛏️ {note.structured_data.sleep_hours}h</span>
                          )}
                          {note.structured_data.energy && (
                            <span className="text-xs bg-slate-700 px-2 py-0.5 rounded">⚡ {note.structured_data.energy}</span>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
              
              {/* Add note */}
              <div className="flex gap-2">
                <input
                  type="text"
                  value={noteText}
                  onChange={(e) => setNoteText(e.target.value)}
                  placeholder="Add a note..."
                  className="flex-1 bg-slate-900 border border-slate-700/50 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                  onKeyDown={(e) => e.key === 'Enter' && handleAddNote()}
                />
                <button
                  onClick={handleAddNote}
                  disabled={addNote.isPending}
                  className="px-3 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 rounded-lg text-sm transition-colors"
                >
                  Add
                </button>
              </div>
            </section>
            
            {/* Coach Chat Section */}
            <section className="bg-gradient-to-br from-slate-800 to-purple-900/30 border border-purple-700/30 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-8 h-8 bg-gradient-to-br from-purple-500 to-pink-500 rounded-full flex items-center justify-center">
                  🏃
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white">Coach</h3>
                  <span className="text-xs text-emerald-400">● Available</span>
                </div>
              </div>
              
              {/* Quick questions */}
              <div className="flex flex-wrap gap-2 mb-3">
                {quickQuestions.map((q) => (
                  <button
                    key={q}
                    onClick={() => handleSendCoachMessage(q)}
                    disabled={isCoachSending}
                    className="text-xs bg-purple-900/40 border border-purple-700/50 text-purple-300 px-3 py-1.5 rounded-full hover:bg-purple-900/60 transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
              
              {/* Coach response */}
              {coachResponse && (
                <div className="bg-slate-900/50 rounded-lg p-3 mb-3 text-sm text-slate-200">
                  {coachResponse}
                </div>
              )}

              {/* Coach pending */}
              {isCoachSending && (
                <div className="bg-slate-900/50 border border-purple-700/20 rounded-lg p-3 mb-3 text-sm text-slate-200">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <span className="animate-spin inline-block w-4 h-4 border-2 border-white/20 border-t-white rounded-full" />
                      <span>
                        Coach is thinking… <span className="text-slate-400">({coachElapsedSec}s)</span>
                      </span>
                    </div>
                    <button
                      onClick={() => coachAbortRef.current?.abort()}
                      className="text-xs text-slate-300 hover:text-white border border-slate-700/60 rounded px-2 py-1"
                    >
                      Cancel
                    </button>
                  </div>
                  <div className="text-xs text-slate-400 mt-2">
                    This can take ~30–60s (data + tools + coach run). If it’s still going after ~90s, cancel and retry.
                  </div>
                </div>
              )}

              {/* Coach error */}
              {coachError && (
                <div className="bg-red-900/20 border border-red-700/40 rounded-lg p-3 mb-3 text-sm text-red-300">
                  {coachError}
                </div>
              )}
              
              {/* Chat input */}
              <div className="flex gap-2">
                <input
                  type="text"
                  value={coachMessage}
                  onChange={(e) => setCoachMessage(e.target.value)}
                  placeholder="Ask about this workout..."
                  className="flex-1 bg-slate-900 border border-slate-700/50 rounded-full px-4 py-2 text-white text-sm focus:outline-none focus:border-purple-500"
                  onKeyDown={(e) => e.key === 'Enter' && handleSendCoachMessage()}
                  disabled={isCoachSending}
                />
                <button
                  onClick={() => handleSendCoachMessage()}
                  disabled={isCoachSending}
                  className="w-10 h-10 bg-gradient-to-br from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 disabled:from-slate-700 disabled:to-slate-700 rounded-full flex items-center justify-center transition-colors"
                >
                  {isCoachSending ? (
                    <span className="animate-spin inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full" />
                  ) : (
                    '→'
                  )}
                </button>
              </div>
            </section>
          </div>
        ) : (
          <div className="p-4 text-slate-400">No data available for this day.</div>
        )}
      </div>
    </>
  );
}
