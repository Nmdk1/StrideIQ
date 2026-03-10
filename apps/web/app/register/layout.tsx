import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Sign Up',
  description: 'Create your free StrideIQ account. Connect Strava or Garmin to get AI-powered training intelligence from your own data.',
  alternates: {
    canonical: 'https://strideiq.run/register',
  },
}

export default function RegisterLayout({ children }: { children: React.ReactNode }) {
  return children
}
