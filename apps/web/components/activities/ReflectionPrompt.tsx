/**
 * RSI Layer 2 — Reflection Prompt
 *
 * Three-tap post-run reflection: Harder than expected | As expected | Easier than expected.
 * Replaces the heavier PerceptionPrompt on the activity detail page.
 *
 * Spec: docs/specs/RSI_WIRING_SPEC.md (Layer 2, item 3)
 * - Single tap submits. Shows checkmark after submission.
 * - Stores: { activity_id, athlete_id, response: enum, timestamp }
 * - No free text in v1.
 */

'use client';

import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

type ReflectionValue = 'harder' | 'expected' | 'easier';

interface ReflectionPromptProps {
  activityId: string;
  className?: string;
}

interface ReflectionData {
  id: string;
  activity_id: string;
  response: ReflectionValue;
  created_at: string;
}

const REFLECTION_OPTIONS: { value: ReflectionValue; label: string; icon: string }[] = [
  { value: 'harder', label: 'Harder than expected', icon: '▲' },
  { value: 'expected', label: 'As expected', icon: '●' },
  { value: 'easier', label: 'Easier than expected', icon: '▼' },
];

function useReflection(activityId: string) {
  return useQuery<ReflectionData | null>({
    queryKey: ['reflection', activityId],
    queryFn: async () => {
      const result = await apiClient.get<ReflectionData | null>(
        `/v1/activities/${activityId}/reflection`
      );
      return result;
    },
    enabled: !!activityId,
    staleTime: Infinity, // Reflections don't change
  });
}

function useSubmitReflection(activityId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (response: ReflectionValue) =>
      apiClient.post<ReflectionData>(`/v1/activities/${activityId}/reflection`, { response }),
    onSuccess: (data) => {
      queryClient.setQueryData(['reflection', activityId], data);
    },
  });
}

export function ReflectionPrompt({ activityId, className = '' }: ReflectionPromptProps) {
  const { data: existing, isLoading } = useReflection(activityId);
  const submitMutation = useSubmitReflection(activityId);
  const [selected, setSelected] = useState<ReflectionValue | null>(null);
  const [submitted, setSubmitted] = useState(false);

  // Sync with existing data
  useEffect(() => {
    if (existing?.response) {
      setSelected(existing.response);
      setSubmitted(true);
    }
  }, [existing]);

  const handleSelect = async (value: ReflectionValue) => {
    if (submitted && selected === value) return; // Already submitted this option
    setSelected(value);
    setSubmitted(true);
    try {
      await submitMutation.mutateAsync(value);
    } catch {
      // Revert on failure
      if (!existing) {
        setSelected(null);
        setSubmitted(false);
      } else {
        setSelected(existing.response);
      }
    }
  };

  if (isLoading) return null; // No skeleton — silent upgrade principle

  return (
    <div className={`${className}`} data-testid="reflection-prompt">
      <p className="text-sm text-slate-400 mb-3">
        {submitted ? 'Your reflection' : 'How did this run feel?'}
      </p>
      <div className="flex gap-2">
        {REFLECTION_OPTIONS.map((option) => {
          const isSelected = selected === option.value;
          const isOtherSelected = submitted && selected !== option.value;

          return (
            <button
              key={option.value}
              onClick={() => handleSelect(option.value)}
              disabled={submitMutation.isPending}
              data-testid={`reflection-${option.value}`}
              className={`
                flex-1 px-3 py-2.5 rounded-lg text-sm font-medium transition-all
                ${isSelected
                  ? 'bg-orange-500/20 text-orange-300 border border-orange-500/50 ring-1 ring-orange-500/30'
                  : isOtherSelected
                    ? 'bg-slate-800/30 text-slate-500 border border-slate-700/30'
                    : 'bg-slate-800/50 text-slate-300 border border-slate-700/50 hover:bg-slate-700/50 hover:text-white'
                }
              `}
            >
              <span className="block text-base mb-0.5">{option.icon}</span>
              <span className="block text-xs leading-tight">{option.label}</span>
              {isSelected && submitted && (
                <span className="block text-xs text-orange-400 mt-1">✓</span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
