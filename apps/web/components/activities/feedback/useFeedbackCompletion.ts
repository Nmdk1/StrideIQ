'use client';

/**
 * Aggregates the three pieces of post-run feedback (reflection, perception
 * RPE, workout-type classification) into a single `isComplete` signal that
 * the page uses to decide whether to auto-open the FeedbackModal.
 *
 * 404s are treated as "not yet submitted" rather than errors, because the
 * backend uses 404 to mean "this athlete hasn't filed feedback for this
 * activity yet" — that's expected, not exceptional.
 *
 * Returned shape matches what FeedbackModal needs to pre-fill its form.
 */

import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/lib/hooks/useAuth';
import { API_CONFIG } from '@/lib/api/config';
import type { ActivityFeedback } from '@/lib/api/types';

export type ReflectionValue = 'harder' | 'expected' | 'easier';

export interface ReflectionRecord {
  id: string;
  activity_id: string;
  response: ReflectionValue;
  created_at: string;
}

export interface WorkoutTypeRecord {
  activity_id: string;
  workout_type: string | null;
  workout_zone: string | null;
  workout_confidence: number | null;
  is_user_override: boolean;
}

export interface FeedbackCompletion {
  reflection: ReflectionRecord | null;
  feedback: ActivityFeedback | null;
  workoutType: WorkoutTypeRecord | null;
  isLoading: boolean;
  /** True iff all three pieces have been recorded. */
  isComplete: boolean;
  refetch: () => void;
}

async function fetchSilentlyOn404<T>(
  url: string,
  token: string | null,
): Promise<T | null> {
  if (!token) return null;
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const body = await res.json();
  return (body ?? null) as T | null;
}

export function useFeedbackCompletion(activityId: string): FeedbackCompletion {
  const { token } = useAuth();
  const enabled = !!token && !!activityId;

  const reflectionQ = useQuery<ReflectionRecord | null>({
    queryKey: ['feedback-modal', 'reflection', activityId],
    queryFn: () =>
      fetchSilentlyOn404<ReflectionRecord>(
        `${API_CONFIG.baseURL}/v1/activities/${activityId}/reflection`,
        token,
      ),
    enabled,
    staleTime: 30_000,
  });

  const feedbackQ = useQuery<ActivityFeedback | null>({
    queryKey: ['feedback-modal', 'feedback', activityId],
    queryFn: () =>
      fetchSilentlyOn404<ActivityFeedback>(
        `${API_CONFIG.baseURL}/v1/activity-feedback/activity/${activityId}`,
        token,
      ),
    enabled,
    staleTime: 30_000,
  });

  const workoutTypeQ = useQuery<WorkoutTypeRecord | null>({
    queryKey: ['feedback-modal', 'workout-type', activityId],
    queryFn: () =>
      fetchSilentlyOn404<WorkoutTypeRecord>(
        `${API_CONFIG.baseURL}/v1/activities/${activityId}/workout-type`,
        token,
      ),
    enabled,
    staleTime: 30_000,
  });

  const isLoading = reflectionQ.isLoading || feedbackQ.isLoading || workoutTypeQ.isLoading;

  const reflection = reflectionQ.data ?? null;
  const feedback = feedbackQ.data ?? null;
  const workoutType = workoutTypeQ.data ?? null;

  const hasReflection = !!reflection?.response;
  const hasRpe = typeof feedback?.perceived_effort === 'number' && feedback.perceived_effort > 0;
  const hasWorkoutType = !!workoutType?.workout_type;
  const isComplete = !isLoading && hasReflection && hasRpe && hasWorkoutType;

  return {
    reflection,
    feedback,
    workoutType,
    isLoading,
    isComplete,
    refetch: () => {
      reflectionQ.refetch();
      feedbackQ.refetch();
      workoutTypeQ.refetch();
    },
  };
}
