'use client';

import Link from 'next/link';
import { sendToolTelemetry } from '@/lib/hooks/useToolTelemetry';

type Props = {
  className?: string;
  children: React.ReactNode;
  /** Extra metadata e.g. { cta: 'hook_banner' } */
  telemetry?: Record<string, unknown>;
};

export function SignupCtaLink({ className, children, telemetry }: Props) {
  return (
    <Link
      href="/register"
      className={className}
      onClick={() => void sendToolTelemetry('signup_cta_click', telemetry)}
    >
      {children}
    </Link>
  );
}
