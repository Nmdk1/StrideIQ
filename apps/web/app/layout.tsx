import type { Metadata, Viewport } from 'next'
import Navigation from './components/Navigation'
import ClientShell from './components/ClientShell'
import { QueryProvider } from '@/lib/providers/QueryProvider'
import { AuthProvider } from '@/lib/context/AuthContext'
import { UnitsProvider } from '@/lib/context/UnitsContext'
import { CompareProvider } from '@/lib/context/CompareContext'
import { ConsentProvider } from '@/lib/context/ConsentContext'
import { ConsentPrompt } from './components/ConsentPrompt'
// RuntoonSharePrompt was a global mobile auto-popup that polled
// /v1/runtoon/pending every 10s and slid up a bottom sheet on every
// recent run.  Phase 4 retired it: sharing is a pull action now,
// surfaced via the Share button in the activity page chrome (which
// opens ShareDrawer -> RuntoonCard).  Component file is preserved on
// disk for reference and possible rollback; intentionally not imported.
// import { RuntoonSharePrompt } from '@/components/runtoon/RuntoonSharePrompt'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { TooltipProvider } from '@/components/ui/tooltip'
import { ImpersonationBanner } from '@/components/admin/ImpersonationBanner'
import './globals.css'

const META_DESCRIPTION =
  'Your body has a voice. StrideIQ is AI running intelligence that turns your data into decisions — training paces, trend signals, and coaching that adapts to you.'
const OG_IMAGE_URL = '/og-image.png?v=6'

export const metadata: Metadata = {
  title: {
    default: 'StrideIQ - AI Running Coach & Training Intelligence',
    template: '%s | StrideIQ'
  },
  description: META_DESCRIPTION,
  authors: [{ name: 'StrideIQ' }],
  creator: 'StrideIQ',
  openGraph: {
    type: 'website',
    locale: 'en_US',
    siteName: 'StrideIQ',
    title: 'StrideIQ - AI Running Coach & Training Intelligence',
    description: META_DESCRIPTION,
    images: [{ url: OG_IMAGE_URL, width: 1200, height: 630, alt: 'StrideIQ - AI Running Coach' }],
    url: 'https://strideiq.run',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'StrideIQ - AI Running Coach & Training Intelligence',
    description: META_DESCRIPTION,
    images: [OG_IMAGE_URL],
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




