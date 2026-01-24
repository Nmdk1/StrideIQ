/**
 * Settings Page
 * 
 * Enhanced with shadcn/ui + Lucide.
 * User settings including integrations, preferences, and data management.
 * Tone: Sparse, direct, empowering.
 */

'use client';

import { useEffect, useState } from 'react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { StravaConnection } from '@/components/integrations/StravaConnection';
import { useAuth } from '@/lib/hooks/useAuth';
import { useUnits } from '@/lib/context/UnitsContext';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { API_CONFIG } from '@/lib/api/config';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Settings, Link2, Watch, Gauge, CreditCard, Download, Trash2, AlertTriangle, X, ArrowUpRight } from 'lucide-react';
import { authService } from '@/lib/api/services/auth';

export default function SettingsPage() {
  const { user } = useAuth();
  const { units, setUnits } = useUnits();
  const [exporting, setExporting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [billingLoading, setBillingLoading] = useState<'checkout' | 'portal' | 'trial' | null>(null);
  const [paceProfileStatus, setPaceProfileStatus] = useState<'loading' | 'computed' | 'missing' | 'error'>('loading');
  const [paceProfile, setPaceProfile] = useState<any | null>(null);

  // Phase 6: paid access can come from Stripe OR an active trial.
  const rawTier = (user?.subscription_tier || 'free').toLowerCase();
  const hasPaidAccess = !!user?.has_active_subscription || rawTier !== 'free';
  const displayTier = hasPaidAccess ? 'pro' : 'free';
  const trialUsed = !!user?.trial_started_at;
  const trialEndsAt = user?.trial_ends_at ? new Date(user.trial_ends_at) : null;
  const trialActive = !!trialEndsAt && trialEndsAt.getTime() > Date.now();

  useEffect(() => {
    let mounted = true;
    (async () => {
      if (!user?.id) return;
      setPaceProfileStatus('loading');
      try {
        const resp = await authService.getTrainingPaceProfile();
        if (!mounted) return;
        if (resp?.status === 'computed' && resp?.pace_profile) {
          setPaceProfile(resp.pace_profile);
          setPaceProfileStatus('computed');
        } else {
          setPaceProfile(null);
          setPaceProfileStatus('missing');
        }
      } catch (e) {
        if (!mounted) return;
        setPaceProfile(null);
        setPaceProfileStatus('error');
      }
    })();
    return () => {
      mounted = false;
    };
  }, [user?.id]);

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

  const handleUpgrade = async () => {
    setBillingLoading('checkout');
    try {
      const token = localStorage.getItem('auth_token');
      const resp = await fetch(`${API_CONFIG.baseURL}/v1/billing/checkout`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || !data?.url) return;
      window.location.href = data.url;
    } catch (err) {
      console.error('Upgrade failed:', err);
    } finally {
      setBillingLoading(null);
    }
  };

  const handleManageSubscription = async () => {
    setBillingLoading('portal');
    try {
      const token = localStorage.getItem('auth_token');
      const resp = await fetch(`${API_CONFIG.baseURL}/v1/billing/portal`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || !data?.url) return;
      window.location.href = data.url;
    } catch (err) {
      console.error('Portal failed:', err);
    } finally {
      setBillingLoading(null);
    }
  };

  const handleStartTrial = async () => {
    setBillingLoading('trial');
    try {
      const token = localStorage.getItem('auth_token');
      const resp = await fetch(`${API_CONFIG.baseURL}/v1/billing/trial/start`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ days: 7 }),
      });
      if (!resp.ok) return;
      // Refresh the page so AuthContext re-pulls /me and membership UI updates.
      if (process.env.NODE_ENV !== 'test') {
        window.location.reload();
      }
    } catch (err) {
      console.error('Trial start failed:', err);
    } finally {
      setBillingLoading(null);
    }
  };

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-slate-900 text-slate-100 py-8">
        <div className="max-w-4xl mx-auto px-4">
          <div className="flex items-center gap-3 mb-8">
            <div className="p-2.5 rounded-xl bg-orange-500/20 ring-1 ring-orange-500/30">
              <Settings className="w-6 h-6 text-orange-500" />
            </div>
            <h1 className="text-3xl font-bold">Settings</h1>
          </div>

          <div className="space-y-6">
            {/* Integrations */}
            <Card className="bg-slate-800 border-slate-700">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Link2 className="w-5 h-5 text-orange-500" />
                  Integrations
                </CardTitle>
                <CardDescription>Connect your fitness platforms</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <StravaConnection />
                
                {/* Future integrations placeholder */}
                <Card className="bg-slate-700/50 border-slate-600">
                  <CardContent className="py-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-slate-600/50 rounded-lg">
                          <Watch className="w-5 h-5 text-slate-400" />
                        </div>
                        <div>
                          <p className="font-medium text-slate-300">Garmin Connect</p>
                          <p className="text-sm text-slate-500">Direct sync from your Garmin device</p>
                        </div>
                      </div>
                      <Badge variant="outline" className="text-slate-400 border-slate-500">Coming Soon</Badge>
                    </div>
                  </CardContent>
                </Card>
              </CardContent>
            </Card>

            {/* Preferences */}
            <Card className="bg-slate-800 border-slate-700">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Gauge className="w-5 h-5 text-blue-500" />
                  Preferences
                </CardTitle>
                <CardDescription>Customize your experience</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Distance Units</p>
                    <p className="text-sm text-slate-400">Choose kilometers or miles for displaying distances</p>
                  </div>
                  <div className="flex items-center gap-1 bg-slate-900 rounded-lg p-1 border border-slate-700">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setUnits('metric')}
                      className={units === 'metric' ? 'bg-orange-600 text-white hover:bg-orange-600' : 'text-slate-400 hover:text-white'}
                    >
                      Kilometers (km)
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setUnits('imperial')}
                      className={units === 'imperial' ? 'bg-orange-600 text-white hover:bg-orange-600' : 'text-slate-400 hover:text-white'}
                    >
                      Miles (mi)
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Subscription */}
            <Card className="bg-slate-800 border-slate-700">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <CreditCard className="w-5 h-5 text-purple-500" />
                  Membership
                </CardTitle>
                <CardDescription>Free vs Pro</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div>
                      <div className="font-medium flex items-center gap-2">
                        {displayTier.toUpperCase()} Plan
                        <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30">Active</Badge>
                      </div>
                      <p className="text-sm text-slate-400">
                        {trialActive ? (
                          <>
                            Trial ends{' '}
                            <span className="text-slate-200">
                              {trialEndsAt?.toLocaleDateString()}
                            </span>
                            . Upgrade anytime to keep Pro.
                          </>
                        ) : (
                          <>Pro unlocks the full planning and intelligence stack.</>
                        )}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {!hasPaidAccess ? (
                      <>
                        {!trialUsed ? (
                          <Button
                            className="bg-slate-700 hover:bg-slate-600"
                            onClick={handleStartTrial}
                            disabled={billingLoading !== null}
                            title="7-day free trial"
                          >
                            {billingLoading === 'trial' ? <LoadingSpinner size="sm" /> : 'Start 7-day trial'}
                          </Button>
                        ) : null}
                        <Button className="bg-orange-600 hover:bg-orange-500" onClick={handleUpgrade} disabled={billingLoading !== null}>
                          {billingLoading === 'checkout' ? <LoadingSpinner size="sm" /> : (
                            <>
                              Upgrade to Pro <ArrowUpRight className="w-4 h-4 ml-1" />
                            </>
                          )}
                        </Button>
                      </>
                    ) : (
                      <Button
                        className="bg-slate-700 hover:bg-slate-600"
                        onClick={user?.stripe_customer_id ? handleManageSubscription : handleUpgrade}
                        disabled={billingLoading !== null}
                        title={!user?.stripe_customer_id ? 'No billing profile linked yet — start Pro billing to enable portal' : undefined}
                      >
                        {billingLoading === 'portal' ? <LoadingSpinner size="sm" /> : (
                          <>
                            {user?.stripe_customer_id ? 'Manage subscription' : 'Start Pro billing'} <ArrowUpRight className="w-4 h-4 ml-1" />
                          </>
                        )}
                      </Button>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Training pace profile */}
            <Card className="bg-slate-800 border-slate-700">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Gauge className="w-5 h-5 text-emerald-400" />
                  Training paces
                </CardTitle>
                <CardDescription>Prescriptive paces from your most recent race/time trial</CardDescription>
              </CardHeader>
              <CardContent>
                {paceProfileStatus === 'loading' ? (
                  <div className="py-4 flex items-center justify-center">
                    <LoadingSpinner size="sm" />
                  </div>
                ) : paceProfileStatus === 'computed' && paceProfile ? (
                  <div className="space-y-3">
                    <div className="text-xs text-slate-500">
                      Anchor: {paceProfile?.anchor?.distance_key || '—'} in {paceProfile?.anchor?.time_display || '—'}
                      {paceProfile?.anchor?.race_date ? ` (${paceProfile.anchor.race_date})` : ''}
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
                      <div className="flex items-center justify-between bg-slate-900/40 border border-slate-700/50 rounded px-3 py-2">
                        <span className="text-slate-300">Easy</span>
                        <span className="text-slate-100">{paceProfile?.paces?.easy?.display_mi || paceProfile?.paces?.easy?.mi || '—'}</span>
                      </div>
                      <div className="flex items-center justify-between bg-slate-900/40 border border-slate-700/50 rounded px-3 py-2">
                        <span className="text-slate-300">Marathon</span>
                        <span className="text-slate-100">{paceProfile?.paces?.marathon?.mi || '—'}</span>
                      </div>
                      <div className="flex items-center justify-between bg-slate-900/40 border border-slate-700/50 rounded px-3 py-2">
                        <span className="text-slate-300">Threshold</span>
                        <span className="text-slate-100">{paceProfile?.paces?.threshold?.mi || '—'}</span>
                      </div>
                      <div className="flex items-center justify-between bg-slate-900/40 border border-slate-700/50 rounded px-3 py-2">
                        <span className="text-slate-300">Interval</span>
                        <span className="text-slate-100">{paceProfile?.paces?.interval?.mi || '—'}</span>
                      </div>
                      <div className="flex items-center justify-between bg-slate-900/40 border border-slate-700/50 rounded px-3 py-2">
                        <span className="text-slate-300">Repetition</span>
                        <span className="text-slate-100">{paceProfile?.paces?.repetition?.mi || '—'}</span>
                      </div>
                    </div>
                    <div className="text-xs text-slate-500">
                      If you haven&apos;t raced recently, do a short time trial to unlock accurate prescriptive paces.
                    </div>
                  </div>
                ) : paceProfileStatus === 'missing' ? (
                  <div className="text-sm text-slate-400">
                    No prescriptive paces yet. Add a recent race/time trial result during onboarding (Goals stage) to compute them.
                  </div>
                ) : (
                  <div className="text-sm text-slate-400">
                    Couldn&apos;t load training paces right now.
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Data Management */}
            <Card className="bg-slate-800 border-slate-700">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Download className="w-5 h-5 text-cyan-500" />
                  Data Management
                </CardTitle>
                <CardDescription>Export or delete your data</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Export */}
                <div className="flex items-center justify-between p-4 bg-slate-700/30 rounded-lg border border-slate-600">
                  <div>
                    <p className="font-medium">Export Your Data</p>
                    <p className="text-sm text-slate-400">Download all your data as JSON</p>
                  </div>
                  <Button
                    variant="outline"
                    onClick={handleExportData}
                    disabled={exporting}
                    className="border-slate-600 hover:bg-slate-700"
                  >
                    {exporting ? <LoadingSpinner size="sm" /> : (
                      <>
                        <Download className="w-4 h-4 mr-1.5" />
                        Export
                      </>
                    )}
                  </Button>
                </div>

                {/* Delete Account */}
                <div className="flex items-center justify-between p-4 bg-red-900/20 rounded-lg border border-red-900/50">
                  <div>
                    <p className="font-medium text-red-400 flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4" />
                      Delete Account
                    </p>
                    <p className="text-sm text-slate-400">Permanently delete all your data</p>
                  </div>
                  <Button
                    variant="outline"
                    onClick={() => setShowDeleteConfirm(true)}
                    className="border-red-600/50 text-red-400 hover:bg-red-600/20"
                  >
                    <Trash2 className="w-4 h-4 mr-1.5" />
                    Delete
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Delete Confirmation Modal */}
          {showDeleteConfirm && (
            <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
              <Card className="bg-slate-800 border-slate-700 max-w-md mx-4">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-red-400">
                    <AlertTriangle className="w-5 h-5" />
                    Delete Account
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-slate-400 mb-6">
                    This will permanently delete your account and all associated data. This action cannot be undone.
                  </p>
                  <div className="flex gap-2">
                    <Button
                      onClick={handleDeleteAccount}
                      className="flex-1 bg-red-600 hover:bg-red-700"
                    >
                      <Trash2 className="w-4 h-4 mr-1.5" />
                      Yes, Delete Everything
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => setShowDeleteConfirm(false)}
                      className="border-slate-600 hover:bg-slate-700"
                    >
                      <X className="w-4 h-4 mr-1.5" />
                      Cancel
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </div>
    </ProtectedRoute>
  );
}
