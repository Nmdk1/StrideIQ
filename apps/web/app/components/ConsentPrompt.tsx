'use client';

/**
 * ConsentPrompt — full-screen AI consent capture for existing users.
 *
 * Shown when: authenticated + ai_consent === false + not dismissed this session.
 * "Enable AI Insights" → POST /v1/consent/ai {granted: true} → prompt disappears.
 * "Not now" → sessionStorage key set → prompt disappears for this session.
 * Does NOT use localStorage — reappears after browser is fully closed/reopened.
 */

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Sparkles, X } from 'lucide-react';
import { useAuth } from '@/lib/hooks/useAuth';
import { useConsent } from '@/lib/context/ConsentContext';

const SESSION_KEY = 'strideiq_consent_dismissed';

export function ConsentPrompt() {
  const { isAuthenticated } = useAuth();
  const { aiConsent, loading, grantConsent } = useConsent();
  const [dismissed, setDismissed] = useState(false);
  const [granting, setGranting] = useState(false);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setDismissed(!!sessionStorage.getItem(SESSION_KEY));
    }
  }, []);

  const handleDismiss = () => {
    sessionStorage.setItem(SESSION_KEY, '1');
    setDismissed(true);
  };

  const handleGrant = async () => {
    setGranting(true);
    try {
      await grantConsent();
      // Context re-fetches automatically — prompt will unmount because aiConsent becomes true.
    } finally {
      setGranting(false);
    }
  };

  // Render nothing until we know: authenticated, loaded, consent is false, not dismissed this session.
  if (!isAuthenticated || loading || aiConsent !== false || dismissed) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 bg-slate-950/95 z-50 flex items-center justify-center p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="consent-heading"
    >
      <div className="max-w-md w-full">
        {/* Icon */}
        <div className="flex justify-center mb-6">
          <div className="w-16 h-16 rounded-2xl bg-orange-500/10 border border-orange-500/20 flex items-center justify-center">
            <Sparkles className="w-8 h-8 text-orange-500" />
          </div>
        </div>

        {/* Heading */}
        <h1 id="consent-heading" className="text-2xl font-bold text-white text-center mb-3">
          Enable AI Insights
        </h1>

        {/* Body copy */}
        <div className="text-slate-300 text-center space-y-3 mb-8">
          <p>
            StrideIQ uses AI to generate coaching insights — morning briefings, activity
            narratives, and progress analysis. Your training data is sent to Google Gemini
            and Anthropic Claude for processing.
          </p>
          <p className="text-slate-400 text-sm">
            Neither provider trains AI models on your data under current paid API terms.{' '}
            <Link href="/privacy#ai-powered-insights" className="text-orange-400 hover:text-orange-300 underline">
              Privacy policy
            </Link>
          </p>
          <p className="text-slate-400 text-sm">
            All charts, metrics, calendar, and training data work without AI — no dead ends.
            You can withdraw consent at any time in Settings.
          </p>
        </div>

        {/* Actions */}
        <div className="space-y-3">
          <button
            onClick={handleGrant}
            disabled={granting}
            className="w-full px-6 py-3 bg-orange-600 hover:bg-orange-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl text-white font-semibold transition-colors"
          >
            {granting ? 'Enabling…' : 'Enable AI Insights'}
          </button>

          <button
            onClick={handleDismiss}
            className="w-full px-6 py-3 text-slate-400 hover:text-slate-200 text-sm transition-colors flex items-center justify-center gap-1.5"
          >
            <X className="w-4 h-4" />
            Not now
          </button>
        </div>
      </div>
    </div>
  );
}
