/**
 * Settings Page
 * 
 * Enhanced with shadcn/ui + Lucide.
 * User settings including integrations, preferences, and data management.
 * Tone: Sparse, direct, empowering.
 */

'use client';

import { useEffect, useState, useRef, Suspense } from 'react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { StravaConnection } from '@/components/integrations/StravaConnection';
import { GarminConnection } from '@/components/integrations/GarminConnection';
import { useAuth } from '@/lib/hooks/useAuth';
import { useUnits } from '@/lib/context/UnitsContext';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { API_CONFIG } from '@/lib/api/config';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Settings, Link2, Gauge, CreditCard, Download, Trash2, AlertTriangle, X, ArrowUpRight, BrainCircuit, ChevronUp } from 'lucide-react';
import { authService } from '@/lib/api/services/auth';
import { useConsent } from '@/lib/context/ConsentContext';

// Map legacy/raw tier values to canonical 3-tier model.
type CanonicalTier = 'free' | 'guided' | 'premium';
function canonicalizeTier(raw: string, hasActiveSub: boolean): CanonicalTier {
  const t = (raw || '').toLowerCase();
  if (!hasActiveSub) return 'free';
  if (t === 'guided') return 'guided';
  return 'premium';
}

const TIER_LABELS: Record<CanonicalTier, string> = {
  free: 'Free',
  guided: 'Guided',
  premium: 'Premium',
};

const TIER_PRICES = {
  guided:  { monthly: '$15/mo', annual: '$150/yr', savingsNote: 'Save $30/yr on annual' },
  premium: { monthly: '$25/mo', annual: '$250/yr', savingsNote: 'Save $50/yr on annual' },
};

function SettingsPageContent() {
  const { user } = useAuth();
  const { units, setUnits } = useUnits();
  const { aiConsent, loading: consentLoading, grantConsent, revokeConsent } = useConsent();
  const membershipRef = useRef<HTMLDivElement>(null);
  const [exporting, setExporting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showRevokeConfirm, setShowRevokeConfirm] = useState(false);
  const [consentSaving, setConsentSaving] = useState(false);
  const [billingLoading, setBillingLoading] = useState<string | null>(null);
  const [paceProfileStatus, setPaceProfileStatus] = useState<'loading' | 'computed' | 'missing' | 'error'>('loading');
  const [paceProfile, setPaceProfile] = useState<any | null>(null);

  // Upgrade panel state — pre-seeded from ?upgrade= and ?period= URL params (e.g. from Pricing page CTA).
  // Uses window.location.search instead of useSearchParams to avoid Next.js Suspense boundary requirement.
  const [urlUpgradeTier, setUrlUpgradeTier] = useState<'guided' | 'premium' | null>(null);
  const [upgradePeriod, setUpgradePeriod] = useState<'monthly' | 'annual'>('annual');
  const [upgradePanel, setUpgradePanel] = useState<boolean>(false);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    const tier = params.get('upgrade') as 'guided' | 'premium' | null;
    const period = params.get('period') as 'monthly' | 'annual' | null;
    if (tier === 'guided' || tier === 'premium') {
      setUrlUpgradeTier(tier);
      setUpgradePanel(true);
    }
    if (period === 'monthly') setUpgradePeriod('monthly');
  }, []);

  // Canonical tier derived from user data.
  const rawTier = (user?.subscription_tier || 'free').toLowerCase();
  const hasActiveSub = !!user?.has_active_subscription || (rawTier !== 'free' && rawTier !== '');
  const canonicalTier = canonicalizeTier(rawTier, hasActiveSub);
  const displayTier = TIER_LABELS[canonicalTier];

  // Trial state
  const trialUsed = !!user?.trial_started_at;
  const trialEndsAt = user?.trial_ends_at ? new Date(user.trial_ends_at) : null;
  const trialActive = !!trialEndsAt && trialEndsAt.getTime() > Date.now();

  // Scroll membership card into view when opened via Pricing page deep link.
  useEffect(() => {
    if (urlUpgradeTier && membershipRef.current) {
      setTimeout(() => {
        membershipRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 400);
    }
  }, [urlUpgradeTier]);

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

  const handleConsentToggle = async (enable: boolean) => {
    if (!enable) {
      setShowRevokeConfirm(true);
      return;
    }
    setConsentSaving(true);
    try {
      await grantConsent();
    } finally {
      setConsentSaving(false);
    }
  };

  const handleRevokeConfirmed = async () => {
    setShowRevokeConfirm(false);
    setConsentSaving(true);
    try {
      await revokeConsent();
    } finally {
      setConsentSaving(false);
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

  const handleUpgrade = async (tier: 'guided' | 'premium', period: 'monthly' | 'annual') => {
    const key = `checkout_${tier}_${period}`;
    setBillingLoading(key);
    try {
      const token = localStorage.getItem('auth_token');
      const resp = await fetch(`${API_CONFIG.baseURL}/v1/billing/checkout`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ tier, billing_period: period }),
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

                <GarminConnection />
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

            {/* Membership */}
            <Card ref={membershipRef} className={`bg-slate-800 border-slate-700 ${urlUpgradeTier ? 'ring-1 ring-orange-500/50' : ''}`}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <CreditCard className="w-5 h-5 text-purple-500" />
                  Membership
                </CardTitle>
                <CardDescription>Your current plan and upgrade options</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">

                {/* Current tier row */}
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-medium flex items-center gap-2">
                      {displayTier} Plan
                      <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30">Active</Badge>
                    </div>
                    <p className="text-sm text-slate-400 mt-0.5">
                      {canonicalTier === 'free' && !trialActive && 'Basic tools and plan previews. Upgrade for coaching that adapts.'}
                      {canonicalTier === 'free' && trialActive && (
                        <>Trial ends <span className="text-slate-200">{trialEndsAt?.toLocaleDateString()}</span>. Upgrade to keep full access.</>
                      )}
                      {canonicalTier === 'guided' && 'Daily adaptation, readiness score, and all 7 intelligence rules.'}
                      {canonicalTier === 'premium' && 'Full coaching stack — narratives, advisory mode, conversational AI.'}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {canonicalTier === 'premium' ? (
                      <Button
                        className="bg-slate-700 hover:bg-slate-600"
                        onClick={user?.stripe_customer_id ? handleManageSubscription : () => handleUpgrade('premium', upgradePeriod)}
                        disabled={billingLoading !== null}
                        title={!user?.stripe_customer_id ? 'No billing profile yet — start Premium billing to enable portal' : undefined}
                      >
                        {billingLoading === 'portal' ? <LoadingSpinner size="sm" /> : (
                          <>{user?.stripe_customer_id ? 'Manage subscription' : 'Start Premium billing'} <ArrowUpRight className="w-4 h-4 ml-1" /></>
                        )}
                      </Button>
                    ) : (
                      <>
                        {canonicalTier === 'free' && !trialUsed && (
                          <Button
                            className="bg-slate-700 hover:bg-slate-600"
                            onClick={handleStartTrial}
                            disabled={billingLoading !== null}
                            title="7-day free trial"
                          >
                            {billingLoading === 'trial' ? <LoadingSpinner size="sm" /> : 'Start 7-day trial'}
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          className="text-orange-400 hover:text-orange-300 hover:bg-orange-500/10"
                          onClick={() => setUpgradePanel(p => !p)}
                          disabled={billingLoading !== null}
                        >
                          {upgradePanel ? (
                            <><ChevronUp className="w-4 h-4 mr-1" /> Hide upgrade</>
                          ) : (
                            <><ArrowUpRight className="w-4 h-4 mr-1" /> Upgrade</>
                          )}
                        </Button>
                      </>
                    )}
                  </div>
                </div>

                {/* Upgrade panel — visible for free/guided users when panel is open */}
                {upgradePanel && canonicalTier !== 'premium' && (
                  <div className="border border-slate-700 rounded-xl p-4 space-y-4 bg-slate-900/40">

                    {/* Period toggle */}
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-slate-400">Billing period</span>
                      <div className="inline-flex items-center bg-slate-800 border border-slate-700 rounded-lg p-0.5 gap-0.5">
                        <button
                          onClick={() => setUpgradePeriod('monthly')}
                          className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                            upgradePeriod === 'monthly' ? 'bg-slate-600 text-white' : 'text-slate-400 hover:text-white'
                          }`}
                        >
                          Monthly
                        </button>
                        <button
                          onClick={() => setUpgradePeriod('annual')}
                          className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                            upgradePeriod === 'annual' ? 'bg-orange-600 text-white' : 'text-slate-400 hover:text-white'
                          }`}
                        >
                          Annual
                        </button>
                      </div>
                    </div>

                    {/* Tier buttons */}
                    <div className={`grid gap-3 ${canonicalTier === 'free' ? 'sm:grid-cols-2' : 'grid-cols-1'}`}>

                      {/* Guided — show for free users only */}
                      {canonicalTier === 'free' && (
                        <div className="border border-orange-500/40 rounded-xl p-4 bg-orange-500/5">
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-semibold text-orange-300">Guided</span>
                            <span className="text-sm font-bold">{TIER_PRICES.guided[upgradePeriod]}</span>
                          </div>
                          <p className="text-xs text-slate-400 mb-3">{TIER_PRICES.guided.savingsNote}</p>
                          <ul className="text-xs text-slate-400 space-y-1 mb-4">
                            <li>✓ Daily adaptation engine</li>
                            <li>✓ Readiness score at 5 AM</li>
                            <li>✓ All 7 intelligence rules</li>
                            <li>✓ Continuous plan generation</li>
                          </ul>
                          <Button
                            className="w-full bg-orange-600 hover:bg-orange-500 text-white"
                            onClick={() => handleUpgrade('guided', upgradePeriod)}
                            disabled={billingLoading !== null}
                          >
                            {billingLoading === `checkout_guided_${upgradePeriod}` ? (
                              <LoadingSpinner size="sm" />
                            ) : (
                              <>Start Guided <ArrowUpRight className="w-4 h-4 ml-1" /></>
                            )}
                          </Button>
                        </div>
                      )}

                      {/* Premium */}
                      <div className="border border-purple-500/40 rounded-xl p-4 bg-purple-500/5">
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-semibold text-purple-300">Premium</span>
                          <span className="text-sm font-bold">{TIER_PRICES.premium[upgradePeriod]}</span>
                        </div>
                        <p className="text-xs text-slate-400 mb-3">{TIER_PRICES.premium.savingsNote}</p>
                        <ul className="text-xs text-slate-400 space-y-1 mb-4">
                          {canonicalTier === 'free' ? (
                            <>
                              <li>✓ Everything in Guided</li>
                              <li>✓ Contextual workout narratives</li>
                              <li>✓ AI advisory mode</li>
                              <li>✓ Conversational AI coach</li>
                            </>
                          ) : (
                            <>
                              <li>✓ Contextual workout narratives</li>
                              <li>✓ AI advisory mode — coach proposes, you approve</li>
                              <li>✓ Full conversational AI coach</li>
                              <li>✓ Multi-race planning</li>
                            </>
                          )}
                        </ul>
                        <Button
                          className="w-full bg-purple-700 hover:bg-purple-600 text-white"
                          onClick={() => handleUpgrade('premium', upgradePeriod)}
                          disabled={billingLoading !== null}
                        >
                          {billingLoading === `checkout_premium_${upgradePeriod}` ? (
                            <LoadingSpinner size="sm" />
                          ) : (
                            <>{canonicalTier === 'guided' ? 'Upgrade to Premium' : 'Start Premium'} <ArrowUpRight className="w-4 h-4 ml-1" /></>
                          )}
                        </Button>
                      </div>

                    </div>

                    <p className="text-xs text-slate-500 text-center">
                      Cancel anytime via the customer portal. Annual plans billed upfront.
                    </p>
                  </div>
                )}

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

            {/* AI Processing */}
            <Card className="bg-slate-800 border-slate-700">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BrainCircuit className="w-5 h-5 text-orange-500" />
                  AI Processing
                </CardTitle>
                <CardDescription>Control how StrideIQ uses AI to personalise your coaching</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between p-4 bg-slate-700/30 rounded-lg border border-slate-600">
                  <div className="flex-1 min-w-0 pr-4">
                    <p className="font-medium">Allow AI-powered insights</p>
                    <p className="text-sm text-slate-400 mt-0.5">
                      {aiConsent
                        ? 'AI coaching is active — briefings, narratives, and progress analysis are enabled.'
                        : 'AI coaching is off. Charts, metrics, and training data still work fully.'}
                    </p>
                  </div>
                  <div className="flex-shrink-0">
                    {consentLoading ? (
                      <div className="w-11 h-6 bg-slate-600 rounded-full animate-pulse" />
                    ) : (
                      <button
                        role="switch"
                        aria-checked={aiConsent === true}
                        onClick={() => handleConsentToggle(!(aiConsent === true))}
                        disabled={consentSaving}
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 focus:ring-offset-slate-800 disabled:opacity-50 ${
                          aiConsent ? 'bg-orange-600' : 'bg-slate-600'
                        }`}
                      >
                        <span
                          className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                            aiConsent ? 'translate-x-6' : 'translate-x-1'
                          }`}
                        />
                      </button>
                    )}
                  </div>
                </div>
                <p className="text-xs text-slate-500 mt-3">
                  Your data is sent to Google Gemini and Anthropic Claude for AI processing.
                  Neither provider trains models on your data.{' '}
                  <a href="/privacy#ai-powered-insights" className="text-orange-400 hover:text-orange-300 underline">
                    Privacy policy
                  </a>
                </p>
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

          {/* Revoke AI Consent Confirmation Modal */}
          {showRevokeConfirm && (
            <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
              <Card className="bg-slate-800 border-slate-700 max-w-md mx-4">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-orange-400">
                    <BrainCircuit className="w-5 h-5" />
                    Disable AI Insights?
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-slate-300 mb-2">This will immediately stop all AI processing of your data. The following will stop working:</p>
                  <ul className="text-sm text-slate-400 list-disc list-inside mb-6 space-y-1">
                    <li>Morning coach briefing</li>
                    <li>Activity narratives and moments</li>
                    <li>Progress headlines and coaching cards</li>
                    <li>Coach chat</li>
                  </ul>
                  <p className="text-sm text-slate-500 mb-6">Charts, metrics, calendar, splits, and training load are unaffected. You can re-enable AI at any time.</p>
                  <div className="flex gap-2">
                    <Button
                      onClick={handleRevokeConfirmed}
                      className="flex-1 bg-orange-600 hover:bg-orange-700"
                    >
                      Disable AI Insights
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => setShowRevokeConfirm(false)}
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

export default function SettingsPage() {
  return (
    <Suspense fallback={null}>
      <SettingsPageContent />
    </Suspense>
  );
}
