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
import { useNutritionEntries, useCreateNutritionEntry, useParseNutritionText, useNLParsingAvailable } from '@/lib/hooks/queries/nutrition';
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
  const { data: nlAvailable } = useNLParsingAvailable();
  const createEntry = useCreateNutritionEntry();
  const parseNutritionText = useParseNutritionText();
  
  const [showForm, setShowForm] = useState(false);
  const [nlText, setNlText] = useState('');
  const [postSubmitMessage, setPostSubmitMessage] = useState<string | null>(null);
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

  const handleParse = async (e: React.FormEvent) => {
    e.preventDefault();
    setPostSubmitMessage(null);
    const text = nlText.trim();
    if (!text) return;

    try {
      const draft = await parseNutritionText.mutateAsync(text);
      setFormData((prev) => ({
        ...prev,
        athlete_id: user?.id || draft.athlete_id || prev.athlete_id,
        date: draft.date || prev.date,
        entry_type: draft.entry_type || prev.entry_type,
        calories: draft.calories,
        protein_g: draft.protein_g,
        carbs_g: draft.carbs_g,
        fat_g: draft.fat_g,
        fiber_g: draft.fiber_g,
        notes: draft.notes || text,
      }));
      setShowForm(true);
    } catch (err) {
      // Error handled by mutation state
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createEntry.mutateAsync(formData);
      setShowForm(false);
      setPostSubmitMessage("Logged. We'll surface patterns once we have enough check-ins + nutrition to compare.");
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

  const showNLParsing = nlAvailable?.available === true;

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-[#0a0a0f] text-slate-100 py-8">
        <div className="max-w-4xl mx-auto px-4">
          <div className="mb-8">
            <h1 className="text-3xl font-bold mb-2">Nutrition</h1>
            <p className="text-slate-400">
              Log nutrition to spot patterns. Completely optional. Log when convenient.
            </p>
          </div>

          {postSubmitMessage && (
            <div className="bg-green-900/20 border border-green-700/40 text-green-200 rounded-lg p-4 mb-6">
              <p className="text-sm">{postSubmitMessage}</p>
            </div>
          )}

          {/* Quick Presets */}
          {!showForm && (
            <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6 mb-6">
              <h2 className="text-lg font-semibold mb-4">Quick Add</h2>

              {/* Natural language input */}
              {showNLParsing && (
                <form onSubmit={handleParse} className="mb-5">
                  <label className="block text-sm font-medium mb-2">Describe what you ate (optional)</label>
                  <div className="flex gap-2">
                    <input
                      value={nlText}
                      onChange={(e) => setNlText(e.target.value)}
                      className="flex-1 px-3 py-2 bg-[#0a0a0f] border border-slate-700/50 rounded text-white"
                      placeholder='e.g., "oatmeal and black coffee"'
                    />
                    <button
                      type="submit"
                      disabled={parseNutritionText.isPending || !nlText.trim()}
                      className="px-4 py-2 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:cursor-not-allowed rounded text-slate-200 font-medium"
                    >
                      {parseNutritionText.isPending ? <LoadingSpinner size="sm" /> : 'Parse'}
                    </button>
                  </div>
                  <p className="text-xs text-slate-500 mt-2">
                    We&apos;ll estimate macros and pre-fill the form. You can edit anything before saving.
                  </p>
                  {parseNutritionText.isError && <ErrorMessage error={parseNutritionText.error} />}
                </form>
              )}

              <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                {NUTRITION_PRESETS.map((preset) => (
                  <button
                    key={preset.name}
                    onClick={() => handlePreset(preset)}
                    className="px-3 py-2 bg-slate-700 hover:bg-slate-600 rounded text-sm text-slate-300 transition-colors"
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
            <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6 mb-6">
              <h2 className="text-lg font-semibold mb-4">Log Nutrition</h2>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">Type</label>
                    <select
                      value={formData.entry_type}
                      onChange={(e) => setFormData({ ...formData, entry_type: e.target.value as any })}
                      className="w-full px-3 py-2 bg-[#0a0a0f] border border-slate-700/50 rounded text-white"
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
                      className="w-full px-3 py-2 bg-[#0a0a0f] border border-slate-700/50 rounded text-white"
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
                      className="w-full px-3 py-2 bg-[#0a0a0f] border border-slate-700/50 rounded text-white"
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
                      className="w-full px-3 py-2 bg-[#0a0a0f] border border-slate-700/50 rounded text-white"
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
                      className="w-full px-3 py-2 bg-[#0a0a0f] border border-slate-700/50 rounded text-white"
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
                      className="w-full px-3 py-2 bg-[#0a0a0f] border border-slate-700/50 rounded text-white"
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
                    className="w-full px-3 py-2 bg-[#0a0a0f] border border-slate-700/50 rounded text-white"
                    placeholder="e.g., Pre-run fuel"
                  />
                </div>

                {createEntry.isError && <ErrorMessage error={createEntry.error} />}

                <div className="flex gap-2">
                  <button
                    type="submit"
                    disabled={createEntry.isPending}
                    className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:cursor-not-allowed rounded text-white font-medium"
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
                    className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded text-slate-300 font-medium"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* Today&apos;s Entries */}
          {entries && entries.length > 0 && (
            <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6">
              <h2 className="text-lg font-semibold mb-4">Today&apos;s Entries</h2>
              <div className="space-y-3">
                {entries.map((entry) => (
                  <div key={entry.id} className="bg-[#0a0a0f] rounded p-4">
                    <div className="flex justify-between items-start mb-2">
                      <span className="text-sm font-medium capitalize">{entry.entry_type.replace('_', ' ')}</span>
                      {entry.calories && <span className="text-sm text-slate-400">{entry.calories} cal</span>}
                    </div>
                    {(entry.protein_g || entry.carbs_g || entry.fat_g) && (
                      <div className="text-xs text-slate-400">
                        {entry.protein_g && `P: ${entry.protein_g}g `}
                        {entry.carbs_g && `C: ${entry.carbs_g}g `}
                        {entry.fat_g && `F: ${entry.fat_g}g`}
                      </div>
                    )}
                    {entry.notes && <p className="text-sm text-slate-300 mt-2">{entry.notes}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {entries && entries.length === 0 && !showForm && (
            <div className="bg-slate-800 rounded-lg border border-slate-700/50 p-6 text-center">
              <p className="text-slate-400">No entries today. Log when convenient.</p>
            </div>
          )}
        </div>
      </div>
    </ProtectedRoute>
  );
}

