/**
 * Perception Prompt Component
 * 
 * Displays perception question prompt and collects feedback.
 * Can be swapped for different feedback collection UIs.
 */

'use client';

import { useState, useEffect } from 'react';
import { useActivityFeedback, useCreateFeedback, useUpdateFeedback } from '@/lib/hooks/queries/activities';
import type { RunDelivery, ActivityFeedbackCreate } from '@/lib/api/types';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';

interface PerceptionPromptProps {
  delivery?: RunDelivery;
  activityId: string;
  className?: string;
  workoutType?: string;
  expectedRpeRange?: [number, number];  // Expected RPE range from classification
}

// Default fields to show when no delivery is provided
const DEFAULT_PROMPT = {
  should_prompt: true,
  prompt_text: 'How did this run feel?',
  required_fields: [] as string[],
  optional_fields: ['perceived_effort', 'leg_feel', 'notes'],
};

export function PerceptionPrompt({ 
  delivery, 
  activityId, 
  className = '',
  workoutType,
  expectedRpeRange 
}: PerceptionPromptProps) {
  const prompt = delivery?.perception_prompt ?? DEFAULT_PROMPT;
  const { data: existingFeedback, isLoading: isLoadingFeedback } = useActivityFeedback(activityId);
  const createFeedback = useCreateFeedback();
  const updateFeedback = useUpdateFeedback();

  const [formData, setFormData] = useState<ActivityFeedbackCreate>({
    activity_id: activityId,
    perceived_effort: undefined,
    leg_feel: undefined,
    mood_pre: undefined,
    mood_post: undefined,
    energy_pre: undefined,
    energy_post: undefined,
    notes: undefined,
  });

  // Update form data when existing feedback loads
  useEffect(() => {
    if (existingFeedback) {
      setFormData({
        activity_id: activityId,
        perceived_effort: existingFeedback.perceived_effort,
        leg_feel: existingFeedback.leg_feel,
        mood_pre: existingFeedback.mood_pre,
        mood_post: existingFeedback.mood_post,
        energy_pre: existingFeedback.energy_pre,
        energy_post: existingFeedback.energy_post,
        notes: existingFeedback.notes,
      });
    }
  }, [existingFeedback, activityId]);

  // Don't show if no prompt and no existing feedback
  if (!prompt.should_prompt && !existingFeedback) {
    return null;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (existingFeedback) {
      await updateFeedback.mutateAsync({
        feedbackId: existingFeedback.id,
        updates: formData,
      });
    } else {
      await createFeedback.mutateAsync(formData);
    }
  };

  if (isLoadingFeedback) {
    return <LoadingSpinner />;
  }

  const showField = (fieldName: string) => {
    return prompt.required_fields.includes(fieldName) ||
           prompt.optional_fields.includes(fieldName) ||
           existingFeedback;
  };

  const isRequired = (fieldName: string) => {
    return prompt.required_fields.includes(fieldName);
  };

  return (
    <div className={`bg-slate-800 rounded-lg border border-slate-700 p-6 ${className}`}>
      <h3 className="text-lg font-semibold mb-4">
        {existingFeedback ? 'Update Feedback' : prompt.prompt_text}
      </h3>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Perceived Effort (RPE) */}
        {showField('perceived_effort') && (
          <div>
            <label className="block text-sm font-medium mb-2">
              RPE (Rate of Perceived Exertion, 1-10) {isRequired('perceived_effort') && '*'}
            </label>
            
            {/* Expected RPE hint */}
            {expectedRpeRange && !existingFeedback && (
              <div className="mb-2 p-2 bg-slate-900/50 border border-slate-700 rounded text-sm">
                <span className="text-slate-400">Expected for </span>
                <span className="text-orange-400 font-medium">
                  {workoutType?.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) || 'this workout'}
                </span>
                <span className="text-slate-400">: </span>
                <span className="text-green-400 font-semibold">
                  RPE {expectedRpeRange[0]}-{expectedRpeRange[1]}
                </span>
              </div>
            )}
            
            {/* RPE Scale Input */}
            <div className="flex items-center gap-2">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((value) => {
                const isSelected = formData.perceived_effort === value;
                const isInExpectedRange = expectedRpeRange && 
                  value >= expectedRpeRange[0] && value <= expectedRpeRange[1];
                
                return (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setFormData({ ...formData, perceived_effort: value })}
                    className={`
                      w-8 h-8 rounded-full text-sm font-medium transition-all
                      ${isSelected 
                        ? 'bg-orange-500 text-white ring-2 ring-orange-400 ring-offset-1 ring-offset-slate-800' 
                        : isInExpectedRange
                          ? 'bg-green-900/30 text-green-400 hover:bg-green-800/50'
                          : 'bg-slate-700 text-slate-300 hover:bg-slate-600'}
                    `}
                  >
                    {value}
                  </button>
                );
              })}
            </div>
            
            {/* RPE labels */}
            <div className="flex justify-between text-xs text-slate-500 mt-1">
              <span>Very Easy</span>
              <span>Moderate</span>
              <span>Maximum</span>
            </div>
            
            {/* RPE Gap Analysis - only show if there's feedback and expected range */}
            {existingFeedback?.perceived_effort && expectedRpeRange && (
              <div className={`mt-2 p-2 rounded text-sm ${
                existingFeedback.perceived_effort < expectedRpeRange[0]
                  ? 'bg-blue-900/30 text-blue-300'
                  : existingFeedback.perceived_effort > expectedRpeRange[1]
                    ? 'bg-amber-900/30 text-amber-300'
                    : 'bg-green-900/30 text-green-300'
              }`}>
                {existingFeedback.perceived_effort < expectedRpeRange[0] && (
                  <>💪 Felt easier than expected - good sign of fitness!</>
                )}
                {existingFeedback.perceived_effort > expectedRpeRange[1] && (
                  <>⚠️ Felt harder than expected - check recovery/fatigue</>
                )}
                {existingFeedback.perceived_effort >= expectedRpeRange[0] && 
                 existingFeedback.perceived_effort <= expectedRpeRange[1] && (
                  <>✓ RPE matches expected effort</>
                )}
              </div>
            )}
          </div>
        )}

        {/* Leg Feel */}
        {showField('leg_feel') && (
          <div>
            <label className="block text-sm font-medium mb-2">
              Leg Feel {isRequired('leg_feel') && '*'}
            </label>
            <select
              value={formData.leg_feel || ''}
              onChange={(e) => setFormData({ ...formData, leg_feel: e.target.value as any || undefined })}
              className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded text-white"
              required={isRequired('leg_feel')}
            >
              <option value="">Select...</option>
              <option value="fresh">Fresh</option>
              <option value="normal">Normal</option>
              <option value="tired">Tired</option>
              <option value="heavy">Heavy</option>
              <option value="sore">Sore</option>
              <option value="injured">Injured</option>
            </select>
          </div>
        )}

        {/* Energy Post */}
        {showField('energy_post') && (
          <div>
            <label className="block text-sm font-medium mb-2">
              Energy Level Post-Run (1-10) {isRequired('energy_post') && '*'}
            </label>
            <input
              type="number"
              min="1"
              max="10"
              value={formData.energy_post || ''}
              onChange={(e) => setFormData({ ...formData, energy_post: parseInt(e.target.value) || undefined })}
              className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded text-white"
              required={isRequired('energy_post')}
            />
          </div>
        )}

        {/* Notes */}
        {showField('notes') && (
          <div>
            <label className="block text-sm font-medium mb-2">Notes (Optional)</label>
            <textarea
              value={formData.notes || ''}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              rows={3}
              className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded text-white"
            />
          </div>
        )}

        {(createFeedback.isError || updateFeedback.isError) && (
          <ErrorMessage error={createFeedback.error || updateFeedback.error} />
        )}

        <button
          type="submit"
          disabled={createFeedback.isPending || updateFeedback.isPending}
          className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:cursor-not-allowed rounded text-white font-medium"
        >
          {createFeedback.isPending || updateFeedback.isPending ? (
            <LoadingSpinner size="sm" />
          ) : (
            existingFeedback ? 'Update Feedback' : 'Submit Feedback'
          )}
        </button>
      </form>
    </div>
  );
}
