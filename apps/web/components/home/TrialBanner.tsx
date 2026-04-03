'use client';

import React from 'react';
import Link from 'next/link';
import { useTrialStatus } from '@/lib/hooks/queries/billing';
import { Clock, AlertTriangle, XCircle, CreditCard } from 'lucide-react';

type BannerVariant = 'info' | 'warning' | 'error' | 'expired';

const VARIANT_STYLES: Record<BannerVariant, { border: string; bg: string; text: string; icon: string }> = {
  info:    { border: 'border-blue-500/30',   bg: 'bg-blue-500/10',   text: 'text-blue-200',   icon: 'text-blue-400' },
  warning: { border: 'border-amber-500/30',  bg: 'bg-amber-500/10',  text: 'text-amber-200',  icon: 'text-amber-400' },
  error:   { border: 'border-red-500/30',    bg: 'bg-red-500/10',    text: 'text-red-200',    icon: 'text-red-400' },
  expired: { border: 'border-slate-600/50',  bg: 'bg-slate-800/60',  text: 'text-slate-300',  icon: 'text-slate-400' },
};

export function TrialBanner() {
  const { data, isLoading } = useTrialStatus();

  if (isLoading || !data) return null;

  const {
    has_trial,
    trial_days_remaining,
    subscription_status,
    subscription_tier,
  } = data;

  const isActivePaid = subscription_tier !== 'free' && ['active'].includes(subscription_status || '');
  if (isActivePaid) return null;

  const isPaymentFailed = ['past_due', 'unpaid'].includes(subscription_status || '');
  const isTrialing = subscription_status === 'trialing';
  const isCanceled = subscription_status === 'canceled';
  const trialExpired = has_trial && trial_days_remaining <= 0 && !isTrialing;

  if (isPaymentFailed) {
    return (
      <Banner
        variant="error"
        icon={<AlertTriangle className="w-4 h-4 flex-shrink-0" />}
        message="Payment failed. Update your card to keep full access."
        action={{ label: 'Update Card', href: '/settings?tab=billing' }}
      />
    );
  }

  if (trialExpired && !isTrialing && subscription_tier === 'free') {
    return (
      <Banner
        variant="expired"
        icon={<XCircle className="w-4 h-4 flex-shrink-0" />}
        message="Your trial has ended. Subscribe to restore coaching insights, narratives, and your training plan."
        action={{ label: 'Subscribe', href: '/settings?tab=billing' }}
      />
    );
  }

  if (isCanceled && subscription_tier === 'free') {
    return (
      <Banner
        variant="expired"
        icon={<XCircle className="w-4 h-4 flex-shrink-0" />}
        message="Your subscription has been canceled. Subscribe to restore full access."
        action={{ label: 'Subscribe', href: '/settings?tab=billing' }}
      />
    );
  }

  if ((isTrialing || has_trial) && trial_days_remaining > 0 && trial_days_remaining <= 7) {
    const variant: BannerVariant = trial_days_remaining <= 3 ? 'warning' : 'info';
    const dayWord = trial_days_remaining === 1 ? 'day' : 'days';
    return (
      <Banner
        variant={variant}
        icon={<Clock className="w-4 h-4 flex-shrink-0" />}
        message={`Your trial ends in ${trial_days_remaining} ${dayWord}. You'll be billed $24.99/month after that.`}
        action={
          subscription_status !== 'trialing'
            ? { label: 'Add Card', href: '/settings?tab=billing' }
            : undefined
        }
      />
    );
  }

  return null;
}

function Banner({
  variant,
  icon,
  message,
  action,
}: {
  variant: BannerVariant;
  icon: React.ReactNode;
  message: string;
  action?: { label: string; href: string };
}) {
  const s = VARIANT_STYLES[variant];
  return (
    <div className={`rounded-lg border ${s.border} ${s.bg} px-4 py-3`}>
      <div className="flex items-center gap-3">
        <span className={s.icon}>{icon}</span>
        <p className={`text-sm flex-1 ${s.text}`}>{message}</p>
        {action && (
          <Link
            href={action.href}
            className="flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-semibold bg-white/10 hover:bg-white/15 text-white transition-colors whitespace-nowrap"
          >
            <CreditCard className="w-3 h-3" />
            {action.label}
          </Link>
        )}
      </div>
    </div>
  );
}
