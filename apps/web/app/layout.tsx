import type { Metadata, Viewport } from 'next'
import Navigation from './components/Navigation'
import { QueryProvider } from '@/lib/providers/QueryProvider'
import { AuthProvider } from '@/lib/context/AuthContext'
import { UnitsProvider } from '@/lib/context/UnitsContext'
import { CompareProvider } from '@/lib/context/CompareContext'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import './globals.css'

export const metadata: Metadata = {
  title: {
    default: 'StrideIQ | AI-Powered Running Intelligence',
    template: '%s | StrideIQ'
  },
  description: 'Discover what actually improves your running. AI-powered insights that correlate sleep, nutrition, and training with your performance. Free VDOT calculator and age-grading tools.',
  keywords: [
    'running intelligence',
    'AI running coach',
    'running efficiency',
    'runner performance analytics',
    'VDOT calculator',
    'age graded running',
    'heat adjusted pace',
    'masters running',
    'running insights',
    'Strava analytics'
  ],
  authors: [{ name: 'StrideIQ' }],
  creator: 'StrideIQ',
  openGraph: {
    type: 'website',
    locale: 'en_US',
    siteName: 'StrideIQ',
    title: 'StrideIQ | AI-Powered Running Intelligence',
    description: 'Discover what actually improves your running. AI-powered insights that correlate sleep, nutrition, and training with your performance.',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'StrideIQ | AI-Powered Running Intelligence',
    description: 'Discover what actually improves your running.',
  },
  robots: {
    index: true,
    follow: true
  },
  metadataBase: new URL(process.env.NEXT_PUBLIC_BASE_URL || 'https://strideiq.run'),
  manifest: '/manifest.json',
  appleWebApp: {
    capable: true,
    statusBarStyle: 'black-translucent',
    title: 'StrideIQ',
  },
  formatDetection: {
    telephone: false,
  },
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: 'cover',
  themeColor: '#ea580c',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-gray-900 text-gray-100">
        <ErrorBoundary>
          <AuthProvider>
            <QueryProvider>
              <UnitsProvider>
                <CompareProvider>
                  <Navigation />
                  <main>{children}</main>
                </CompareProvider>
              </UnitsProvider>
            </QueryProvider>
          </AuthProvider>
        </ErrorBoundary>
      </body>
    </html>
  )
}




