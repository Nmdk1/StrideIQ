import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Privacy Policy',
  description: 'Privacy policy for StrideIQ',
}

export default function PrivacyPolicyPage() {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 py-16">
      <div className="max-w-4xl mx-auto px-6">
        <h1 className="text-4xl font-bold mb-8">Privacy Policy</h1>
        <p className="text-slate-400 mb-8">Last updated: January 7, 2026</p>
        
        <div className="prose prose-invert max-w-none space-y-8">
          <section>
            <h2 className="text-2xl font-semibold mb-4">1. Information We Collect</h2>
            <p className="text-slate-300 mb-4">
              We collect information you provide directly:
            </p>
            <ul className="list-disc pl-6 text-slate-300 space-y-2">
              <li>Account information (email, display name, birthdate)</li>
              <li>Activity data from connected services (Strava)</li>
              <li>Health metrics you choose to log (sleep, nutrition, body composition)</li>
              <li>Training availability preferences</li>
              <li>Activity feedback and notes</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">2. How We Use Your Data</h2>
            <p className="text-slate-300 mb-4">
              Your data is used exclusively to:
            </p>
            <ul className="list-disc pl-6 text-slate-300 space-y-2">
              <li>Calculate efficiency metrics and performance trends</li>
              <li>Identify correlations between your inputs and performance outcomes</li>
              <li>Provide personalized insights based on YOUR data only</li>
              <li>Generate age-graded performance comparisons</li>
            </ul>
            <p className="text-slate-300 mt-4">
              <strong>We do not:</strong> Sell your data, share individual data with third parties, 
              or use your data for advertising purposes.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">3. Data Storage & Security</h2>
            <p className="text-slate-300">
              Your data is stored securely using industry-standard encryption. 
              We use PostgreSQL databases with encrypted connections, and all API 
              communications use HTTPS/TLS encryption.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">4. Third-Party Services</h2>
            <p className="text-slate-300 mb-4">
              We integrate with:
            </p>
            <ul className="list-disc pl-6 text-slate-300 space-y-2">
              <li><strong>Strava:</strong> To import your activity data (with your authorization)</li>
            </ul>
            <p className="text-slate-300 mt-4">
              Each integration requires your explicit consent. You can disconnect 
              integrations at any time from your settings.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">5. Your Rights</h2>
            <p className="text-slate-300 mb-4">
              You have the right to:
            </p>
            <ul className="list-disc pl-6 text-slate-300 space-y-2">
              <li><strong>Access:</strong> Request a copy of all your data</li>
              <li><strong>Export:</strong> Download your data in standard formats</li>
              <li><strong>Delete:</strong> Request permanent deletion of your account and all data</li>
              <li><strong>Correct:</strong> Update or correct your personal information</li>
            </ul>
            <p className="text-slate-300 mt-4">
              Use the Settings page to exercise these rights, or contact us directly.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">6. Data Retention</h2>
            <p className="text-slate-300">
              We retain your data for as long as your account is active. 
              Upon account deletion, all personal data is permanently removed within 30 days. 
              Anonymized, aggregated data may be retained for service improvement.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">7. Cookies</h2>
            <p className="text-slate-300">
              We use essential cookies only for authentication and session management. 
              No tracking cookies or third-party analytics cookies are used.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">8. Contact</h2>
            <p className="text-slate-300">
              For privacy-related questions or requests, contact us at: 
              <a href="mailto:info@strideiq.run" className="text-orange-400 hover:text-orange-300 ml-1">
                info@strideiq.run
              </a>
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">9. Changes to This Policy</h2>
            <p className="text-slate-300">
              We may update this policy periodically. Significant changes will be 
              communicated via email or in-app notification.
            </p>
          </section>
        </div>
      </div>
    </div>
  )
}
