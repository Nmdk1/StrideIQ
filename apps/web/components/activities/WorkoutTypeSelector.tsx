'use client';

/**
 * Workout Type Selector Component
 * 
 * Allows athletes to:
 * - View the current workout type classification
 * - Override with their own classification
 * - See if it was auto-classified or user-set
 * 
 * PHILOSOPHY NOTE:
 * We deliberately avoid "zone" terminology in athlete-facing UI.
 * The body operates on a continuous spectrum, not discrete zones.
 * We use effort categories (Easy, Moderate, Hard, Race) for grouping
 * similar workout types, not to imply physiological buckets.
 * 
 * See: _AI_CONTEXT_/KNOWLEDGE_BASE/01_INTENSITY_PHILOSOPHY.md
 */

import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

interface WorkoutTypeOption {
  value: string;
  label: string;
  zone: string; // Internal categorization, not exposed as "zone" to users
  description: string;
}

interface WorkoutTypeSelectorProps {
  activityId: string;
  initialType?: string | null;
  onTypeChange?: (newType: string) => void;
  compact?: boolean;
}

// Effort category colors - used for visual grouping only (NOT "zones")
const EFFORT_COLORS: Record<string, string> = {
  recovery: 'bg-gray-600',
  endurance: 'bg-green-600',
  stamina: 'bg-orange-600',
  speed: 'bg-red-600',
  sprint: 'bg-purple-600',
  race_specific: 'bg-yellow-600',
  mixed: 'bg-blue-600',
};

// User-friendly effort category labels (we avoid "Zone X" terminology)
const EFFORT_LABELS: Record<string, string> = {
  recovery: 'Easy Effort',
  endurance: 'Aerobic',
  stamina: 'Threshold',
  speed: 'High Intensity',
  sprint: 'Maximum',
  race_specific: 'Race Effort',
  mixed: 'Variable',
};

export function WorkoutTypeSelector({ 
  activityId, 
  initialType,
  onTypeChange,
  compact = false 
}: WorkoutTypeSelectorProps) {
  const queryClient = useQueryClient();
  const [isEditing, setIsEditing] = useState(false);
  const [selectedType, setSelectedType] = useState<string | null>(initialType || null);

  // Fetch available options
  const { data: optionsData } = useQuery({
    queryKey: ['workout-type-options'],
    queryFn: async () => {
      return apiClient.get<{ options: WorkoutTypeOption[] }>('/v1/activities/workout-types/options');
    },
    staleTime: Infinity, // Options don't change
  });

  // Fetch current workout type
  const { data: currentType, isLoading } = useQuery({
    queryKey: ['activity-workout-type', activityId],
    queryFn: async () => {
      return apiClient.get<{
        activity_id: string;
        workout_type: string | null;
        workout_zone: string | null;
        workout_confidence: number | null;
        is_user_override: boolean;
      }>(`/v1/activities/${activityId}/workout-type`);
    },
    enabled: !!activityId,
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: async (workoutType: string) => {
      return apiClient.put(`/v1/activities/${activityId}/workout-type`, {
        workout_type: workoutType,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['activity-workout-type', activityId] });
      queryClient.invalidateQueries({ queryKey: ['compare'] });
      queryClient.invalidateQueries({ queryKey: ['activities'] });
      setIsEditing(false);
      if (onTypeChange && selectedType) {
        onTypeChange(selectedType);
      }
    },
  });

  // Update local state when data loads
  useEffect(() => {
    if (currentType?.workout_type) {
      setSelectedType(currentType.workout_type);
    }
  }, [currentType]);

  const options = optionsData?.options || [];
  const currentOption = options.find(o => o.value === selectedType);
  const effortColor = currentOption ? EFFORT_COLORS[currentOption.zone] : 'bg-gray-700';

  const handleSave = () => {
    if (selectedType) {
      updateMutation.mutate(selectedType);
    }
  };

  if (isLoading) {
    return <div className="text-gray-500 text-sm">Loading...</div>;
  }

  // Compact display mode
  if (compact && !isEditing) {
    return (
      <button
        onClick={() => setIsEditing(true)}
        className={`inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs ${effortColor} text-white hover:opacity-80 transition-opacity`}
        title="Click to change workout type"
      >
        {currentOption?.label || 'Set Type'}
        {currentType?.is_user_override && <span className="text-white/60">✓</span>}
      </button>
    );
  }

  // Full display mode
  if (!isEditing) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-medium text-gray-400">Workout Type</h3>
          <button
            onClick={() => setIsEditing(true)}
            className="text-xs text-orange-400 hover:text-orange-300"
          >
            Edit
          </button>
        </div>
        
        {currentOption ? (
          <div className="flex items-center gap-3">
            <span className={`px-2 py-1 rounded text-sm font-medium ${effortColor} text-white`}>
              {currentOption.label}
            </span>
            <span className="text-sm text-gray-400">
              {currentOption.description}
            </span>
            {currentType?.is_user_override && (
              <span className="text-xs text-green-400" title="You set this">✓ Your classification</span>
            )}
          </div>
        ) : (
          <div className="text-gray-400">
            <span className="text-sm">Not classified</span>
            <button
              onClick={() => setIsEditing(true)}
              className="ml-2 text-sm text-orange-400 hover:text-orange-300"
            >
              Set workout type →
            </button>
          </div>
        )}
      </div>
    );
  }

  // Editing mode
  return (
    <div className="bg-gray-800 rounded-lg border border-orange-600/50 p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-white">Select Workout Type</h3>
        <button
          onClick={() => {
            setIsEditing(false);
            setSelectedType(currentType?.workout_type || null);
          }}
          className="text-xs text-gray-400 hover:text-white"
        >
          Cancel
        </button>
      </div>
      
      {/* Group by effort category (NOT "zones" - see philosophy doc) */}
      <div className="space-y-3 max-h-80 overflow-y-auto">
        {Object.keys(EFFORT_LABELS).map(category => {
          const categoryOptions = options.filter(o => o.zone === category);
          if (categoryOptions.length === 0) return null;
          
          return (
            <div key={category}>
              <div className={`text-xs font-medium mb-1 ${EFFORT_COLORS[category]} text-white px-2 py-0.5 rounded inline-block`}>
                {EFFORT_LABELS[category]}
              </div>
              <div className="grid grid-cols-2 gap-1">
                {categoryOptions.map(option => (
                  <button
                    key={option.value}
                    onClick={() => setSelectedType(option.value)}
                    className={`text-left p-2 rounded text-sm transition-colors ${
                      selectedType === option.value
                        ? 'bg-orange-600/30 border border-orange-500 text-white'
                        : 'bg-gray-700/50 border border-transparent text-gray-300 hover:bg-gray-700'
                    }`}
                  >
                    <div className="font-medium">{option.label}</div>
                    <div className="text-xs text-gray-400 truncate">{option.description}</div>
                  </button>
                ))}
              </div>
            </div>
          );
        })}
      </div>
      
      <div className="mt-4 flex gap-2">
        <button
          onClick={handleSave}
          disabled={!selectedType || updateMutation.isPending}
          className="flex-1 py-2 bg-orange-600 hover:bg-orange-700 disabled:bg-gray-700 disabled:cursor-not-allowed rounded-lg text-sm font-medium transition-colors"
        >
          {updateMutation.isPending ? 'Saving...' : 'Save'}
        </button>
      </div>
    </div>
  );
}
