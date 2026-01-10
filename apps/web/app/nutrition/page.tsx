/**
 * Nutrition Logging Page
 * 
 * Low-friction, non-guilt-inducing nutrition tracking.
 * Tone: Sparse, optional-friendly, no pressure.
 */

'use client';

import { useState } from 'react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useAuth } from '@/lib/hooks/useAuth';
import { useNutritionEntries, useCreateNutritionEntry } from '@/lib/hooks/queries/nutrition';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import type { NutritionEntryCreate } from '@/lib/api/services/nutrition';

const NUTRITION_PRESETS = [
  { name: 'Banana', calories: 105, carbs_g: 27, protein_g: 1.3, fat_g: 0.4 },
  { name: 'Energy Gel', calories: 100, carbs_g: 25, protein_g: 0, fat_g: 0 },
  { name: 'Protein Shake', calories: 150, protein_g: 25, carbs_g: 5, fat_g: 3 },
  { name: 'Toast with Peanut Butter', calories: 250, carbs_g: 30, protein_g: 10, fat_g: 12 },
  { name: 'Oatmeal', calories: 150, carbs_g: 27, protein_g: 5, fat_g: 3 },
];

export default function NutritionPage() {
  const { user } = useAuth();
  const today = new Date().toISOString().split('T')[0];
  const { data: entries, isLoading } = useNutritionEntries({ start_date: today, end_date: today });
  const createEntry = useCreateNutritionEntry();
  
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState<NutritionEntryCreate>({
    athlete_id: user?.id || '',
    date: today,
    entry_type: 'daily',
    calories: undefined,
    protein_g: undefined,
    carbs_g: undefined,
    fat_g: undefined,
    fiber_g: undefined,
    notes: '',
  });

  const handlePreset = (preset: typeof NUTRITION_PRESETS[0]) => {
    setFormData({
      ...formData,
      calories: preset.calories,
      carbs_g: preset.carbs_g,
      protein_g: preset.protein_g,
      fat_g: preset.fat_g,
    });
    setShowForm(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createEntry.mutateAsync(formData);
      setShowForm(false);
      setFormData({
        athlete_id: user?.id || '',
        date: today,
        entry_type: 'daily',
        calories: undefined,
        protein_g: undefined,
        carbs_g: undefined,
        fat_g: undefined,
        fiber_g: undefined,
        notes: '',
      });
    } catch (err) {
      // Error handled by mutation
    }
  };

  if (isLoading) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen flex items-center justify-center">
          <LoadingSpinner size="lg" />
        </div>
      </ProtectedRoute>
    );
  }

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gray-900 text-gray-100 py-8">
        <div className="max-w-4xl mx-auto px-4">
          <div className="mb-8">
            <h1 className="text-3xl font-bold mb-2">Nutrition</h1>
            <p className="text-gray-400">
              Log nutrition to spot patterns. Completely optional. Log when convenient.
            </p>
          </div>

          {/* Quick Presets */}
          {!showForm && (
            <div className="bg-gray-800 rounded-lg border border-gray-700 p-6 mb-6">
              <h2 className="text-lg font-semibold mb-4">Quick Add</h2>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                {NUTRITION_PRESETS.map((preset) => (
                  <button
                    key={preset.name}
                    onClick={() => handlePreset(preset)}
                    className="px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm text-gray-300 transition-colors"
                  >
                    {preset.name}
                  </button>
                ))}
              </div>
              <button
                onClick={() => setShowForm(true)}
                className="mt-4 w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded text-white font-medium"
              >
                Custom Entry
              </button>
            </div>
          )}

          {/* Entry Form */}
          {showForm && (
            <div className="bg-gray-800 rounded-lg border border-gray-700 p-6 mb-6">
              <h2 className="text-lg font-semibold mb-4">Log Nutrition</h2>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">Type</label>
                    <select
                      value={formData.entry_type}
                      onChange={(e) => setFormData({ ...formData, entry_type: e.target.value as any })}
                      className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
                    >
                      <option value="daily">Daily</option>
                      <option value="pre_activity">Pre-Run</option>
                      <option value="during_activity">During Run</option>
                      <option value="post_activity">Post-Run</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">Date</label>
                    <input
                      type="date"
                      value={formData.date}
                      onChange={(e) => setFormData({ ...formData, date: e.target.value })}
                      className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">Calories</label>
                    <input
                      type="number"
                      value={formData.calories || ''}
                      onChange={(e) => setFormData({ ...formData, calories: e.target.value ? parseFloat(e.target.value) : undefined })}
                      className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
                      placeholder="Optional"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">Protein (g)</label>
                    <input
                      type="number"
                      step="0.1"
                      value={formData.protein_g || ''}
                      onChange={(e) => setFormData({ ...formData, protein_g: e.target.value ? parseFloat(e.target.value) : undefined })}
                      className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
                      placeholder="Optional"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">Carbs (g)</label>
                    <input
                      type="number"
                      step="0.1"
                      value={formData.carbs_g || ''}
                      onChange={(e) => setFormData({ ...formData, carbs_g: e.target.value ? parseFloat(e.target.value) : undefined })}
                      className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
                      placeholder="Optional"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">Fat (g)</label>
                    <input
                      type="number"
                      step="0.1"
                      value={formData.fat_g || ''}
                      onChange={(e) => setFormData({ ...formData, fat_g: e.target.value ? parseFloat(e.target.value) : undefined })}
                      className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
                      placeholder="Optional"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">Notes (Optional)</label>
                  <textarea
                    value={formData.notes || ''}
                    onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                    rows={2}
                    className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
                    placeholder="e.g., Pre-run fuel"
                  />
                </div>

                {createEntry.isError && <ErrorMessage error={createEntry.error} />}

                <div className="flex gap-2">
                  <button
                    type="submit"
                    disabled={createEntry.isPending}
                    className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:cursor-not-allowed rounded text-white font-medium"
                  >
                    {createEntry.isPending ? <LoadingSpinner size="sm" /> : 'Log Entry'}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowForm(false);
                      setFormData({
                        athlete_id: user?.id || '',
                        date: today,
                        entry_type: 'daily',
                        calories: undefined,
                        protein_g: undefined,
                        carbs_g: undefined,
                        fat_g: undefined,
                        fiber_g: undefined,
                        notes: '',
                      });
                    }}
                    className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-gray-300 font-medium"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* Today&apos;s Entries */}
          {entries && entries.length > 0 && (
            <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
              <h2 className="text-lg font-semibold mb-4">Today&apos;s Entries</h2>
              <div className="space-y-3">
                {entries.map((entry) => (
                  <div key={entry.id} className="bg-gray-900 rounded p-4">
                    <div className="flex justify-between items-start mb-2">
                      <span className="text-sm font-medium capitalize">{entry.entry_type.replace('_', ' ')}</span>
                      {entry.calories && <span className="text-sm text-gray-400">{entry.calories} cal</span>}
                    </div>
                    {(entry.protein_g || entry.carbs_g || entry.fat_g) && (
                      <div className="text-xs text-gray-400">
                        {entry.protein_g && `P: ${entry.protein_g}g `}
                        {entry.carbs_g && `C: ${entry.carbs_g}g `}
                        {entry.fat_g && `F: ${entry.fat_g}g`}
                      </div>
                    )}
                    {entry.notes && <p className="text-sm text-gray-300 mt-2">{entry.notes}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {entries && entries.length === 0 && !showForm && (
            <div className="bg-gray-800 rounded-lg border border-gray-700 p-6 text-center">
              <p className="text-gray-400">No entries today. Log when convenient.</p>
            </div>
          )}
        </div>
      </div>
    </ProtectedRoute>
  );
}

