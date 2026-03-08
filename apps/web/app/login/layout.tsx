import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Sign In',
  description: 'Sign in to your StrideIQ account to access your training intelligence dashboard.',
  alternates: {
    canonical: 'https://strideiq.run/login',
  },
}

export default function LoginLayout({ children }: { children: React.ReactNode }) {
  return children
}
