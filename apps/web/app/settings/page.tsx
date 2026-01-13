/**
 * Settings Page
 * 
 * User settings including integrations, preferences, and data management.
 * Tone: Sparse, direct, empowering.
 */

'use client';

import { useState } from 'react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { StravaConnection } from '@/components/integrations/StravaConnection';
import { useAuth } from '@/lib/hooks/useAuth';
import { useUnits } from '@/lib/context/UnitsContext';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { API_CONFIG } from '@/lib/api/config';

export default function SettingsPage() {
  const { user } = useAuth();
  const { units, setUnits } = useUnits();
  const [exporting, setExporting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const handleExportData = async () => {
    setExporting(true);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(
        `${API_CONFIG.baseURL}/v1/gdpr/export`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (response.ok) {
        const data = await response.json();
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `my-data-${new Date().toISOString().split('T')[0]}.json`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch (err) {
      console.error('Export failed:', err);
    } finally {
      setExporting(false);
    }
  };

  const handleDeleteAccount = async () => {
    const token = localStorage.getItem('auth_token');
    try {
      await fetch(
        `${API_CONFIG.baseURL}/v1/gdpr/delete`,
        {
          method: 'DELETE',
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      localStorage.removeItem('auth_token');
      window.location.href = '/';
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gray-900 text-gray-100 py-8">
        <div className="max-w-4xl mx-auto px-4">
          <h1 className="text-3xl font-bold mb-8">Settings</h1>

          <div className="space-y-8">
            {/* Integrations */}
            <section>
              <h2 className="text-xl font-semibold mb-4">Integrations</h2>
              <StravaConnection />
              
              {/* Future integrations placeholder */}
              <div className="mt-4 bg-gray-800 rounded-lg border border-gray-700 p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-gray-700 rounded flex items-center justify-center text-gray-500">G</div>
                    <div>
                      <p className="font-medium text-gray-400">Garmin Connect</p>
                      <p className="text-sm text-gray-500">Coming soon</p>
                    </div>
                  </div>
                  <span className="text-xs text-gray-500 bg-gray-700 px-2 py-1 rounded">Pending</span>
                </div>
              </div>
            </section>

            {/* Preferences */}
            <section>
              <h2 className="text-xl font-semibold mb-4">Preferences</h2>
              <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Distance Units</p>
                    <p className="text-sm text-gray-400">Choose kilometers or miles for displaying distances</p>
                  </div>
                  <div className="flex items-center gap-1 bg-gray-900 rounded-lg p-1">
                    <button
                      onClick={() => setUnits('metric')}
                      className={`px-4 py-2 text-sm rounded-md transition-colors ${
                        units === 'metric'
                          ? 'bg-orange-600 text-white'
                          : 'text-gray-400 hover:text-white'
                      }`}
                    >
                      Kilometers (km)
                    </button>
                    <button
                      onClick={() => setUnits('imperial')}
                      className={`px-4 py-2 text-sm rounded-md transition-colors ${
                        units === 'imperial'
                          ? 'bg-orange-600 text-white'
                          : 'text-gray-400 hover:text-white'
                      }`}
                    >
                      Miles (mi)
                    </button>
                  </div>
                </div>
              </div>
            </section>

            {/* Subscription */}
            <section>
              <h2 className="text-xl font-semibold mb-4">Subscription</h2>
              <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium capitalize">{user?.subscription_tier || 'Free'} Plan</p>
                    <p className="text-sm text-gray-400">Current subscription tier</p>
                  </div>
                  <button
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded text-white text-sm font-medium transition-colors"
                  >
                    Upgrade
                  </button>
                </div>
              </div>
            </section>

            {/* Data Management */}
            <section>
              <h2 className="text-xl font-semibold mb-4">Data Management</h2>
              <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 space-y-4">
                {/* Export */}
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Export Your Data</p>
                    <p className="text-sm text-gray-400">Download all your data as JSON</p>
                  </div>
                  <button
                    onClick={handleExportData}
                    disabled={exporting}
                    className="px-4 py-2 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-700 disabled:cursor-not-allowed rounded text-white text-sm font-medium transition-colors"
                  >
                    {exporting ? <LoadingSpinner size="sm" /> : 'Export'}
                  </button>
                </div>

                {/* Delete Account */}
                <div className="border-t border-gray-700 pt-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-red-400">Delete Account</p>
                      <p className="text-sm text-gray-400">Permanently delete all your data</p>
                    </div>
                    <button
                      onClick={() => setShowDeleteConfirm(true)}
                      className="px-4 py-2 bg-red-600/20 hover:bg-red-600/30 border border-red-600/50 rounded text-red-400 text-sm font-medium transition-colors"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            </section>
          </div>

          {/* Delete Confirmation Modal */}
          {showDeleteConfirm && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
              <div className="bg-gray-800 rounded-lg border border-gray-700 p-6 max-w-md mx-4">
                <h3 className="text-xl font-semibold mb-4">Delete Account</h3>
                <p className="text-gray-400 mb-6">
                  This will permanently delete your account and all associated data. This action cannot be undone.
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={handleDeleteAccount}
                    className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 rounded text-white font-medium"
                  >
                    Yes, Delete Everything
                  </button>
                  <button
                    onClick={() => setShowDeleteConfirm(false)}
                    className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-gray-300 font-medium"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </ProtectedRoute>
  );
}

