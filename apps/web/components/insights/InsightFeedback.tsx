/**
 * Insight Feedback Component
 * 
 * Allows users to rate insights as helpful/not helpful.
 * Tone: Sparse, optional, non-guilt-inducing.
 */

'use client';

import { useState } from 'react';
import { useCreateInsightFeedback } from '@/lib/hooks/queries/insightFeedback';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';

interface InsightFeedbackProps {
  insightType: 'correlation' | 'activity_insight' | 'efficiency_trend';
  insightId?: string;
  insightText: string;
  className?: string;
}

export function InsightFeedback({ 
  insightType, 
  insightId, 
  insightText, 
  className = '' 
}: InsightFeedbackProps) {
  const [showFeedback, setShowFeedback] = useState(false);
  const [helpful, setHelpful] = useState<boolean | null>(null);
  const [feedbackText, setFeedbackText] = useState('');
  const createFeedback = useCreateInsightFeedback();

  const handleSubmit = async (isHelpful: boolean) => {
    try {
      await createFeedback.mutateAsync({
        insight_type: insightType,
        insight_id: insightId,
        insight_text: insightText,
        helpful: isHelpful,
        feedback_text: feedbackText || undefined,
      });
      setHelpful(isHelpful);
      setShowFeedback(false);
    } catch (err) {
      // Error handled by mutation
    }
  };

  if (helpful !== null) {
    return (
      <div className={`text-xs text-slate-500 ${className}`}>
        {helpful ? 'Thanks for the feedback.' : 'Noted.'}
      </div>
    );
  }

  if (!showFeedback) {
    return (
      <button
        onClick={() => setShowFeedback(true)}
        className={`text-xs text-slate-500 hover:text-slate-400 ${className}`}
      >
        Was this helpful?
      </button>
    );
  }

  return (
    <div className={`space-y-2 ${className}`}>
      <div className="flex gap-2">
        <button
          onClick={() => handleSubmit(true)}
          disabled={createFeedback.isPending}
          className="px-3 py-1 text-xs bg-green-900/50 hover:bg-green-900/70 border border-green-700/50 rounded text-green-400 disabled:opacity-50"
        >
          {createFeedback.isPending ? <LoadingSpinner size="sm" /> : 'Yes'}
        </button>
        <button
          onClick={() => handleSubmit(false)}
          disabled={createFeedback.isPending}
          className="px-3 py-1 text-xs bg-red-900/50 hover:bg-red-900/70 border border-red-700/50 rounded text-red-400 disabled:opacity-50"
        >
          {createFeedback.isPending ? <LoadingSpinner size="sm" /> : 'No'}
        </button>
        <button
          onClick={() => {
            setShowFeedback(false);
            setFeedbackText('');
          }}
          className="px-3 py-1 text-xs text-slate-500 hover:text-slate-400"
        >
          Cancel
        </button>
      </div>
      <textarea
        value={feedbackText}
        onChange={(e) => setFeedbackText(e.target.value)}
        placeholder="Optional comment"
        rows={2}
        className="w-full px-2 py-1 text-xs bg-slate-900 border border-slate-700/50 rounded text-white"
      />
    </div>
  );
}


