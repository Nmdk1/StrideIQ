/**
 * Profile Page
 * 
 * Display and edit athlete profile information.
 * Tone: Sparse, direct, non-prescriptive.
 */

'use client';

import { useState } from 'react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useAuth } from '@/lib/hooks/useAuth';
import { authService } from '@/lib/api/services/auth';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';

export default function ProfilePage() {
  const { user, refreshUser } = useAuth();
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  
  const [formData, setFormData] = useState({
    display_name: user?.display_name || '',
    email: user?.email || '',
    birthdate: user?.birthdate ? user.birthdate.split('T')[0] : '',
    sex: user?.sex || '',
    height_cm: user?.height_cm || '',
  });

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    try {
      const updates: any = {};
      if (formData.display_name !== user?.display_name) {
        updates.display_name = formData.display_name || null;
      }
      if (formData.email !== user?.email) {
        updates.email = formData.email || null;
      }
      if (formData.birthdate !== (user?.birthdate ? user.birthdate.split('T')[0] : '')) {
        updates.birthdate = formData.birthdate || null;
      }
      if (formData.sex !== user?.sex) {
        updates.sex = formData.sex || null;
      }
      if (formData.height_cm !== (user?.height_cm || '')) {
        updates.height_cm = formData.height_cm ? parseFloat(formData.height_cm.toString()) : null;
      }

      await authService.updateProfile(updates);
      await refreshUser();
      setEditing(false);
    } catch (err) {
      setError(err as Error);
    } finally {
      setSaving(false);
    }
  };

  const calculateAge = (birthdate: string | null): number | null => {
    if (!birthdate) return null;
    const birth = new Date(birthdate);
    const today = new Date();
    let age = today.getFullYear() - birth.getFullYear();
    const monthDiff = today.getMonth() - birth.getMonth();
    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birth.getDate())) {
      age--;
    }
    return age;
  };

  if (!user) {
    return (
      <ProtectedRoute>
        <div className="min-h-screen flex items-center justify-center">
          <LoadingSpinner size="lg" />
        </div>
      </ProtectedRoute>
    );
  }

  const age = calculateAge(user.birthdate || null);

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gray-900 text-gray-100 py-8">
        <div className="max-w-4xl mx-auto px-4">
          <h1 className="text-3xl font-bold mb-8">Profile</h1>

          {/* Personal Information */}
          <div className="bg-gray-800 rounded-lg border border-gray-700 p-6 mb-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">Personal Information</h2>
              {!editing && (
                <button
                  onClick={() => setEditing(true)}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm font-medium transition-colors"
                >
                  Edit
                </button>
              )}
            </div>

            {editing ? (
              <form onSubmit={handleSave} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Display Name</label>
                  <input
                    type="text"
                    value={formData.display_name}
                    onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
                    className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">Email</label>
                  <input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">Birthdate</label>
                  <input
                    type="date"
                    value={formData.birthdate}
                    onChange={(e) => setFormData({ ...formData, birthdate: e.target.value })}
                    className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">Sex</label>
                  <select
                    value={formData.sex}
                    onChange={(e) => setFormData({ ...formData, sex: e.target.value })}
                    className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
                  >
                    <option value="">Select...</option>
                    <option value="M">Male</option>
                    <option value="F">Female</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">Height (cm)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={formData.height_cm}
                    onChange={(e) => setFormData({ ...formData, height_cm: e.target.value })}
                    className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-white"
                    placeholder="e.g., 175.0"
                  />
                </div>

                {error && <ErrorMessage error={error} />}

                <div className="flex gap-2">
                  <button
                    type="submit"
                    disabled={saving}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:cursor-not-allowed rounded text-white font-medium"
                  >
                    {saving ? <LoadingSpinner size="sm" /> : 'Save'}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setEditing(false);
                      setFormData({
                        display_name: user.display_name || '',
                        email: user.email || '',
                        birthdate: user.birthdate ? user.birthdate.split('T')[0] : '',
                        sex: user.sex || '',
                        height_cm: user.height_cm || '',
                      });
                      setError(null);
                    }}
                    className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-white font-medium"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            ) : (
              <div className="space-y-3">
                <div>
                  <span className="text-sm text-gray-400">Display Name:</span>
                  <p className="font-medium">{user.display_name || '--'}</p>
                </div>
                <div>
                  <span className="text-sm text-gray-400">Email:</span>
                  <p className="font-medium">{user.email || '--'}</p>
                </div>
                <div>
                  <span className="text-sm text-gray-400">Birthdate:</span>
                  <p className="font-medium">
                    {user.birthdate
                      ? new Date(user.birthdate).toLocaleDateString()
                      : '--'}
                  </p>
                </div>
                {age && (
                  <div>
                    <span className="text-sm text-gray-400">Age:</span>
                    <p className="font-medium">{age} years</p>
                  </div>
                )}
                <div>
                  <span className="text-sm text-gray-400">Sex:</span>
                  <p className="font-medium">{user.sex || '--'}</p>
                </div>
                {user.age_category && (
                  <div>
                    <span className="text-sm text-gray-400">Age Category:</span>
                    <p className="font-medium">{user.age_category}</p>
                  </div>
                )}
                {user.height_cm && (
                  <div>
                    <span className="text-sm text-gray-400">Height:</span>
                    <p className="font-medium">{user.height_cm} cm</p>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Performance Metrics */}
          {(user.durability_index != null || 
            user.recovery_half_life_hours != null || 
            user.consistency_index != null) && (
            <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
              <h2 className="text-xl font-semibold mb-4">Performance Metrics</h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {user.durability_index != null && (
                  <div>
                    <p className="text-sm text-gray-400">Durability Index</p>
                    <p className="text-2xl font-bold">{user.durability_index.toFixed(1)}</p>
                  </div>
                )}
                {user.recovery_half_life_hours != null && (
                  <div>
                    <p className="text-sm text-gray-400">Recovery Half-Life</p>
                    <p className="text-2xl font-bold">{user.recovery_half_life_hours.toFixed(1)} hrs</p>
                  </div>
                )}
                {user.consistency_index != null && (
                  <div>
                    <p className="text-sm text-gray-400">Consistency Index</p>
                    <p className="text-2xl font-bold">{user.consistency_index.toFixed(1)}</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </ProtectedRoute>
  );
}
