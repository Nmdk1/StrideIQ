'use client';

/**
 * Compare Selection Context
 * 
 * Manages the state of activities selected for comparison across the app.
 * Athletes can select activities from the activity list, and the selection
 * persists as they navigate to the compare page.
 */

import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';

interface SelectedActivity {
  id: string;
  name: string;
  date: string;
  workout_type: string | null;
  distance_m: number;
}

interface CompareContextType {
  selectedActivities: SelectedActivity[];
  selectedIds: Set<string>;
  isSelected: (id: string) => boolean;
  toggleSelection: (activity: SelectedActivity) => void;
  addToSelection: (activity: SelectedActivity) => void;
  removeFromSelection: (id: string) => void;
  clearSelection: () => void;
  canAddMore: boolean;
  selectionCount: number;
  MAX_SELECTION: number;
}

const MAX_SELECTION = 10;

const CompareContext = createContext<CompareContextType | undefined>(undefined);

export function CompareProvider({ children }: { children: ReactNode }) {
  const [selectedActivities, setSelectedActivities] = useState<SelectedActivity[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const isSelected = useCallback((id: string) => {
    return selectedIds.has(id);
  }, [selectedIds]);

  const addToSelection = useCallback((activity: SelectedActivity) => {
    if (selectedIds.has(activity.id)) return;
    if (selectedActivities.length >= MAX_SELECTION) return;

    setSelectedActivities(prev => [...prev, activity]);
    setSelectedIds(prev => new Set([...Array.from(prev), activity.id]));
  }, [selectedIds, selectedActivities.length]);

  const removeFromSelection = useCallback((id: string) => {
    setSelectedActivities(prev => prev.filter(a => a.id !== id));
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  }, []);

  const toggleSelection = useCallback((activity: SelectedActivity) => {
    if (selectedIds.has(activity.id)) {
      removeFromSelection(activity.id);
    } else {
      addToSelection(activity);
    }
  }, [selectedIds, addToSelection, removeFromSelection]);

  const clearSelection = useCallback(() => {
    setSelectedActivities([]);
    setSelectedIds(new Set());
  }, []);

  const value: CompareContextType = {
    selectedActivities,
    selectedIds,
    isSelected,
    toggleSelection,
    addToSelection,
    removeFromSelection,
    clearSelection,
    canAddMore: selectedActivities.length < MAX_SELECTION,
    selectionCount: selectedActivities.length,
    MAX_SELECTION,
  };

  return (
    <CompareContext.Provider value={value}>
      {children}
    </CompareContext.Provider>
  );
}

export function useCompareSelection() {
  const context = useContext(CompareContext);
  if (!context) {
    throw new Error('useCompareSelection must be used within a CompareProvider');
  }
  return context;
}
