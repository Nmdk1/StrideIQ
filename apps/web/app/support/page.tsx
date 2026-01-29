import type { Metadata } from 'next'
import Link from 'next/link'

export const metadata: Metadata = {
  title: 'Support',
  description: 'Get help with StrideIQ - contact us, FAQs, and troubleshooting',
}

export default function SupportPage() {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 py-16">
      <div className="max-w-4xl mx-auto px-6">
        <h1 className="text-4xl font-bold mb-4">Support</h1>
        <p className="text-slate-400 mb-12">
          Need help? We&apos;re here for you. Check the FAQ below or contact us directly.
        </p>
        
        {/* Contact Section */}
        <section className="bg-slate-800 border border-slate-700 rounded-lg p-6 mb-12">
          <h2 className="text-2xl font-semibold mb-4">Contact Us</h2>
          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <h3 className="text-lg font-medium text-slate-200 mb-2">General Support</h3>
              <a 
                href="mailto:support@strideiq.run" 
                className="text-orange-400 hover:text-orange-300 text-lg"
              >
                support@strideiq.run
              </a>
              <p className="text-slate-400 text-sm mt-1">
                For help with your account, syncing, or features
              </p>
            </div>
            <div>
              <h3 className="text-lg font-medium text-slate-200 mb-2">Privacy & Data Requests</h3>
              <a 
                href="mailto:privacy@strideiq.run" 
                className="text-orange-400 hover:text-orange-300 text-lg"
              >
                privacy@strideiq.run
              </a>
              <p className="text-slate-400 text-sm mt-1">
                For data export, deletion, or privacy questions
              </p>
            </div>
          </div>
          <p className="text-slate-400 text-sm mt-6">
            We typically respond within 24-48 hours.
          </p>
        </section>

        {/* FAQ Section */}
        <section className="mb-12">
          <h2 className="text-2xl font-semibold mb-6">Frequently Asked Questions</h2>
          
          <div className="space-y-6">
            <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-5">
              <h3 className="text-lg font-medium text-slate-100 mb-2">
                How do I connect my Strava account?
              </h3>
              <p className="text-slate-300">
                Go to <Link href="/settings" className="text-orange-400 hover:text-orange-300">Settings</Link> and 
                click the &quot;Connect with Strava&quot; button. You&apos;ll be redirected to Strava to authorize 
                access. Once authorized, your activities will begin syncing automatically.
              </p>
            </div>

            <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-5">
              <h3 className="text-lg font-medium text-slate-100 mb-2">
                How do I disconnect Strava?
              </h3>
              <p className="text-slate-300">
                Go to <Link href="/settings" className="text-orange-400 hover:text-orange-300">Settings</Link> and 
                scroll to the Strava section. Click &quot;Disconnect Strava&quot; to remove the connection. 
                Your previously synced activities will remain in StrideIQ unless you request deletion.
              </p>
            </div>

            <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-5">
              <h3 className="text-lg font-medium text-slate-100 mb-2">
                How do I delete my account and data?
              </h3>
              <p className="text-slate-300">
                Go to <Link href="/settings" className="text-orange-400 hover:text-orange-300">Settings</Link> and 
                scroll to the bottom to find the account deletion option. Alternatively, email{' '}
                <a href="mailto:privacy@strideiq.run" className="text-orange-400 hover:text-orange-300">
                  privacy@strideiq.run
                </a>{' '}
                and we&apos;ll process your request within 30 days.
              </p>
            </div>

            <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-5">
              <h3 className="text-lg font-medium text-slate-100 mb-2">
                Why aren&apos;t my activities syncing?
              </h3>
              <p className="text-slate-300 mb-3">
                Try these steps:
              </p>
              <ol className="list-decimal pl-5 text-slate-300 space-y-1">
                <li>Go to Settings and click &quot;Sync Activities Now&quot;</li>
                <li>If that doesn&apos;t work, disconnect and reconnect Strava</li>
                <li>Make sure your activities are not set to private on Strava</li>
                <li>Contact support if the issue persists</li>
              </ol>
            </div>

            <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-5">
              <h3 className="text-lg font-medium text-slate-100 mb-2">
                What data do you collect from Strava?
              </h3>
              <p className="text-slate-300">
                We access your activities (distance, pace, heart rate, GPS, splits), athlete profile, 
                and performance metrics. We only use this data to provide you with personalized insights. 
                See our{' '}
                <Link href="/privacy" className="text-orange-400 hover:text-orange-300">
                  Privacy Policy
                </Link>{' '}
                for full details.
              </p>
            </div>

            <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-5">
              <h3 className="text-lg font-medium text-slate-100 mb-2">
                Is my data shared with anyone?
              </h3>
              <p className="text-slate-300">
                No. Your data is never sold, shared with third parties, or used for advertising. 
                Your data is only used to provide YOU with insights. We do not share your data 
                with other users or use it to train AI models.
              </p>
            </div>
          </div>
        </section>

        {/* Links Section */}
        <section className="border-t border-slate-700 pt-8">
          <h2 className="text-xl font-semibold mb-4">Additional Resources</h2>
          <div className="flex flex-wrap gap-4">
            <Link 
              href="/privacy" 
              className="px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-300 hover:text-white hover:border-slate-600 transition-colors"
            >
              Privacy Policy
            </Link>
            <Link 
              href="/terms" 
              className="px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-300 hover:text-white hover:border-slate-600 transition-colors"
            >
              Terms of Service
            </Link>
            <Link 
              href="/about" 
              className="px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-300 hover:text-white hover:border-slate-600 transition-colors"
            >
              About StrideIQ
            </Link>
          </div>
        </section>
      </div>
    </div>
  )
}
