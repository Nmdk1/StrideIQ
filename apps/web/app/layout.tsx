import type { Metadata, Viewport } from 'next'
import Navigation from './components/Navigation'
import ClientShell from './components/ClientShell'
import { QueryProvider } from '@/lib/providers/QueryProvider'
import { AuthProvider } from '@/lib/context/AuthContext'
import { UnitsProvider } from '@/lib/context/UnitsContext'
import { CompareProvider } from '@/lib/context/CompareContext'
import { ConsentProvider } from '@/lib/context/ConsentContext'
import { ConsentPrompt } from './components/ConsentPrompt'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { TooltipProvider } from '@/components/ui/tooltip'
import { ImpersonationBanner } from '@/components/admin/ImpersonationBanner'
import './globals.css'

export const metadata: Metadata = {
  title: {
    default: 'StrideIQ - AI Running Coach & Training Intelligence',
    template: '%s | StrideIQ'
  },
  description: 'Free training pace calculator, age-grading calculator, and heat-adjusted pace tools. Evidence-based AI running coach that correlates sleep, nutrition, and training with your performance.',
  authors: [{ name: 'StrideIQ' }],
  creator: 'StrideIQ',
  openGraph: {
    type: 'website',
    locale: 'en_US',
    siteName: 'StrideIQ',
    title: 'StrideIQ - AI Running Coach & Training Intelligence',
    description: 'Free training pace calculator, age-grading calculator, and heat-adjusted pace tools. Evidence-based AI running coach that correlates sleep, nutrition, and training with your performance.',
    images: [{ url: '/og-image.png', width: 1200, height: 630, alt: 'StrideIQ - AI Running Coach' }],
    url: 'https://strideiq.run',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'StrideIQ - AI Running Coach & Training Intelligence',
    description: 'Free training pace calculator, age-grading, and heat-adjusted pace tools. Evidence-based AI running coach.',
    images: ['/og-image.png'],
  },
  robots: {
    index: true,
    follow: true
  },
  metadataBase: new URL('https://strideiq.run'),
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
      <body className="min-h-screen bg-slate-900 text-slate-100">
        <ErrorBoundary>
          <AuthProvider>
            <QueryProvider>
              <UnitsProvider>
                <CompareProvider>
                  <ConsentProvider>
                    <TooltipProvider>
                      <Navigation />
                      <ImpersonationBanner />
                      <ClientShell>
                        <ConsentPrompt />
                        <main className="pb-[76px] md:pb-0">{children}</main>
                      </ClientShell>
                    </TooltipProvider>
                  </ConsentProvider>
                </CompareProvider>
              </UnitsProvider>
            </QueryProvider>
          </AuthProvider>
        </ErrorBoundary>
      </body>
    </html>
  )
}




