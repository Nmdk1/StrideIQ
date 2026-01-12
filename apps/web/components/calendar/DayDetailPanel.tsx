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

import React, { useState } from 'react';
import Link from 'next/link';
import { useUnits } from '@/lib/context/UnitsContext';
import { useCalendarDay, useAddNote, useSendCoachMessage } from '@/lib/hooks/queries/calendar';
import type { CalendarDay, CalendarNote, InlineInsight } from '@/lib/api/services/calendar';

interface DayDetailPanelProps {
  date: string;
  isOpen: boolean;
  onClose: () => void;
}

export function DayDetailPanel({ date, isOpen, onClose }: DayDetailPanelProps) {
  const { formatDistance, formatPace } = useUnits();
  const { data: dayData, isLoading } = useCalendarDay(date, isOpen);
  const addNote = useAddNote();
  const sendCoachMessage = useSendCoachMessage();
  
  const [noteText, setNoteText] = useState('');
  const [coachMessage, setCoachMessage] = useState('');
  const [coachResponse, setCoachResponse] = useState('');
  
  const dateObj = new Date(date);
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
  
  const handleSendCoachMessage = async () => {
    if (!coachMessage.trim()) return;
    
    const response = await sendCoachMessage.mutateAsync({
      message: coachMessage,
      context_type: 'day',
      context_date: date,
    });
    
    setCoachResponse(response.response);
    setCoachMessage('');
  };
  
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
        bg-gray-900 border-l border-gray-700
        z-50 overflow-y-auto
        transition-transform duration-300 ease-out
        ${isOpen ? 'translate-x-0' : 'translate-x-full'}
      `}>
        {/* Header */}
        <div className="sticky top-0 bg-gray-900 border-b border-gray-700 p-4 flex justify-between items-center">
          <div>
            <h2 className="text-lg font-semibold text-white">{formattedDate}</h2>
            {dayData?.planned_workout && (
              <p className="text-sm text-gray-400">
                Week {dayData.planned_workout.phase} • {dayData.planned_workout.workout_type.replace(/_/g, ' ')}
              </p>
            )}
          </div>
          <button 
            onClick={onClose}
            className="text-gray-400 hover:text-white text-2xl"
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
                'bg-gray-800/50 border border-gray-700/30'
              }`}>
                <div className="flex items-center justify-between">
                  <span className={`text-sm font-medium ${
                    dayData.inline_insight.sentiment === 'positive' ? 'text-emerald-400' :
                    dayData.inline_insight.sentiment === 'negative' ? 'text-orange-400' :
                    'text-gray-300'
                  }`}>
                    {dayData.inline_insight.value}
                  </span>
                  {dayData.inline_insight.delta && (
                    <span className="text-xs text-gray-500">
                      {dayData.inline_insight.delta > 0 ? '+' : ''}{dayData.inline_insight.delta}% vs avg
                    </span>
                  )}
                </div>
              </div>
            )}
            
            {/* Planned Workout Section */}
            {dayData.planned_workout && (
              <section className="bg-gray-800 rounded-lg p-4">
                <h3 className="text-xs uppercase tracking-wider text-gray-500 mb-3">Planned Workout</h3>
                <div className="border-l-2 border-orange-500 pl-3">
                  <div className="font-semibold text-white">{dayData.planned_workout.title}</div>
                  {dayData.planned_workout.target_distance_km && (
                    <div className="text-gray-400 text-sm">
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
                    <div className="text-gray-300 text-sm mt-2 bg-gray-900/50 rounded p-2 font-mono">
                      {dayData.planned_workout.description}
                    </div>
                  )}
                </div>
              </section>
            )}
            
            {/* Actual Activities Section - CLICKABLE to full detail */}
            {dayData.activities.length > 0 && (
              <section className="bg-gray-800 rounded-lg p-4">
                <h3 className="text-xs uppercase tracking-wider text-gray-500 mb-3">Actual</h3>
                <div className="border-l-2 border-emerald-500 pl-3 space-y-3">
                  {dayData.activities.map((activity) => (
                    <div key={activity.id} className="space-y-2">
                      <Link 
                        href={`/activities/${activity.id}`}
                        className="block group hover:bg-gray-700/30 rounded-lg transition-colors p-2 -m-2"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="font-semibold text-white group-hover:text-emerald-400 transition-colors">
                            {activity.name || 'Run'}
                          </div>
                          <div className="text-gray-500 group-hover:text-emerald-400 transition-colors text-sm flex items-center gap-1">
                            View Details
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                            </svg>
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                          <div className="bg-gray-900/50 rounded p-2 text-center">
                            <div className="text-lg font-bold text-white">
                              {formatDistance(activity.distance_m || 0, 1)}
                            </div>
                            <div className="text-xs text-gray-500">Distance</div>
                          </div>
                          <div className="bg-gray-900/50 rounded p-2 text-center">
                            <div className="text-lg font-bold text-white">
                              {activity.duration_s ? `${Math.floor(activity.duration_s / 60)}:${String(activity.duration_s % 60).padStart(2, '0')}` : '--'}
                            </div>
                            <div className="text-xs text-gray-500">Duration</div>
                          </div>
                          {activity.avg_hr && (
                            <div className="bg-gray-900/50 rounded p-2 text-center">
                              <div className="text-lg font-bold text-white">{activity.avg_hr}</div>
                              <div className="text-xs text-gray-500">Avg HR</div>
                            </div>
                          )}
                          {activity.workout_type && (
                            <div className="bg-gray-900/50 rounded p-2 text-center">
                              <div className="text-sm font-bold text-orange-400 uppercase">
                                {activity.workout_type.replace(/_/g, ' ')}
                              </div>
                              <div className="text-xs text-gray-500">Detected</div>
                            </div>
                          )}
                        </div>
                      </Link>
                      {/* Compare to similar runs */}
                      <Link
                        href={`/compare/context/${activity.id}`}
                        className="flex items-center justify-between p-2 bg-gray-900/50 rounded-lg text-xs text-gray-500 hover:text-orange-400 hover:bg-orange-900/20 transition-colors"
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
                    <div key={insight.id} className="text-gray-200 text-sm">
                      <strong>{insight.title}</strong>
                      <p className="text-gray-400 mt-1">{insight.content}</p>
                    </div>
                  ))}
                </div>
              </section>
            )}
            
            {/* Notes Section */}
            <section className="bg-gray-800 rounded-lg p-4">
              <h3 className="text-xs uppercase tracking-wider text-gray-500 mb-3">📝 Notes</h3>
              
              {/* Existing notes */}
              {dayData.notes.length > 0 && (
                <div className="space-y-2 mb-3">
                  {dayData.notes.map((note) => (
                    <div key={note.id} className="bg-gray-900/50 rounded p-2 text-sm text-gray-300">
                      {note.text_content}
                      {note.structured_data && (
                        <div className="flex gap-2 mt-1 flex-wrap">
                          {note.structured_data.sleep_hours && (
                            <span className="text-xs bg-gray-700 px-2 py-0.5 rounded">🛏️ {note.structured_data.sleep_hours}h</span>
                          )}
                          {note.structured_data.energy && (
                            <span className="text-xs bg-gray-700 px-2 py-0.5 rounded">⚡ {note.structured_data.energy}</span>
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
                  className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                  onKeyDown={(e) => e.key === 'Enter' && handleAddNote()}
                />
                <button
                  onClick={handleAddNote}
                  disabled={addNote.isPending}
                  className="px-3 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 rounded-lg text-sm transition-colors"
                >
                  Add
                </button>
              </div>
            </section>
            
            {/* Coach Chat Section */}
            <section className="bg-gradient-to-br from-gray-800 to-purple-900/30 border border-purple-700/30 rounded-lg p-4">
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
                    onClick={() => setCoachMessage(q)}
                    className="text-xs bg-purple-900/40 border border-purple-700/50 text-purple-300 px-3 py-1.5 rounded-full hover:bg-purple-900/60 transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
              
              {/* Coach response */}
              {coachResponse && (
                <div className="bg-gray-900/50 rounded-lg p-3 mb-3 text-sm text-gray-200">
                  {coachResponse}
                </div>
              )}
              
              {/* Chat input */}
              <div className="flex gap-2">
                <input
                  type="text"
                  value={coachMessage}
                  onChange={(e) => setCoachMessage(e.target.value)}
                  placeholder="Ask about this workout..."
                  className="flex-1 bg-gray-900 border border-gray-700 rounded-full px-4 py-2 text-white text-sm focus:outline-none focus:border-purple-500"
                  onKeyDown={(e) => e.key === 'Enter' && handleSendCoachMessage()}
                />
                <button
                  onClick={handleSendCoachMessage}
                  disabled={sendCoachMessage.isPending}
                  className="w-10 h-10 bg-gradient-to-br from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 rounded-full flex items-center justify-center transition-colors"
                >
                  →
                </button>
              </div>
            </section>
          </div>
        ) : (
          <div className="p-4 text-gray-400">No data available for this day.</div>
        )}
      </div>
    </>
  );
}
