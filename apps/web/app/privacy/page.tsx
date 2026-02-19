import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Privacy Policy',
  description: 'Privacy policy for StrideIQ - compliant with GDPR, Strava API, and Garmin Connect requirements',
}

export default function PrivacyPolicyPage() {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 py-16">
      <div className="max-w-4xl mx-auto px-6">
        <h1 className="text-4xl font-bold mb-8">Privacy Policy</h1>
        <p className="text-slate-400 mb-8">Last updated: February 19, 2026</p>
        
        <div className="prose prose-invert max-w-none space-y-8">
          <section>
            <h2 className="text-2xl font-semibold mb-4">1. Information We Collect</h2>
            <p className="text-slate-300 mb-4">
              We collect information you provide directly:
            </p>
            <ul className="list-disc pl-6 text-slate-300 space-y-2">
              <li>Account information (email, display name, birthdate, gender)</li>
              <li>Health metrics you choose to log (sleep, nutrition, body composition)</li>
              <li>Training availability preferences</li>
              <li>Activity feedback and notes</li>
            </ul>
            
            <h3 className="text-xl font-semibold mt-6 mb-3">1.1 Data from Connected Services</h3>
            <p className="text-slate-300 mb-4">
              With your explicit authorization, we collect data from third-party fitness platforms:
            </p>
            
            <h4 className="text-lg font-semibold mt-4 mb-2">Strava</h4>
            <p className="text-slate-300 mb-2">
              When you connect your Strava account, we access:
            </p>
            <ul className="list-disc pl-6 text-slate-300 space-y-1">
              <li>Activity data: distance, duration, pace, elevation, GPS routes</li>
              <li>Performance metrics: heart rate, power, cadence, splits</li>
              <li>Activity metadata: date, time, activity type, title, description</li>
              <li>Athlete profile: name, profile photo, measurement preferences</li>
            </ul>
            <p className="text-slate-300 mt-2 text-sm">
              We only access data you explicitly authorize. We do not access your Strava social features, 
              followers, or other users&apos; data.
            </p>
            
            <h4 className="text-lg font-semibold mt-4 mb-2">Garmin Connect</h4>
            <p className="text-slate-300 mb-2">
              When you connect your Garmin account, we access:
            </p>
            <ul className="list-disc pl-6 text-slate-300 space-y-1">
              <li>Activity data: distance, duration, pace, elevation, GPS routes</li>
              <li>Performance metrics: heart rate, power, cadence, training effect</li>
              <li>Health metrics: sleep data, stress, body battery, HRV</li>
              <li>Body composition: weight, body fat percentage (if recorded)</li>
            </ul>
            <p className="text-slate-300 mt-2 text-sm">
              Garmin data displayed in StrideIQ is sourced from Garmin devices and Garmin Connect.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">2. How We Collect Your Data</h2>
            <p className="text-slate-300 mb-4">
              We collect data through:
            </p>
            <ul className="list-disc pl-6 text-slate-300 space-y-2">
              <li><strong>Direct input:</strong> Information you enter in forms (registration, check-ins, settings)</li>
              <li><strong>OAuth authorization:</strong> When you connect Strava or Garmin, you authenticate 
                directly with those services. We receive an access token that allows us to retrieve your data 
                on your behalf.</li>
              <li><strong>Automatic sync:</strong> After authorization, we periodically sync your new activities 
                and health data from connected services.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">3. How We Use Your Data</h2>
            <p className="text-slate-300 mb-4">
              Your data is used exclusively to provide you with personalized insights:
            </p>
            <ul className="list-disc pl-6 text-slate-300 space-y-2">
              <li>Calculate efficiency metrics (pace at heart rate, heart rate at pace)</li>
              <li>Identify correlations between inputs (sleep, nutrition) and performance outcomes</li>
              <li>Generate age-graded performance comparisons</li>
              <li>Provide AI-powered coaching recommendations based on YOUR data only</li>
              <li>Display your activities, trends, and personal records</li>
            </ul>
            
            <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 mt-4">
              <p className="text-slate-300 font-semibold mb-2">We do NOT:</p>
              <ul className="list-disc pl-6 text-slate-300 space-y-1">
                <li>Sell, rent, or lease your data to third parties</li>
                <li>Share your individual data with other users or third parties</li>
                <li>Use your data for advertising or marketing purposes</li>
                <li>Use your data to train AI models or for machine learning purposes</li>
                <li>Display your data to other users without your explicit consent</li>
                <li>Aggregate your data with other users&apos; data for analytics or insights</li>
              </ul>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">4. Data Storage & Security</h2>
            <p className="text-slate-300 mb-4">
              We implement appropriate technical and organizational security measures:
            </p>
            <ul className="list-disc pl-6 text-slate-300 space-y-2">
              <li>All data is encrypted in transit using HTTPS/TLS</li>
              <li>Database connections use encrypted channels</li>
              <li>OAuth tokens from Strava and Garmin are encrypted at rest</li>
              <li>Access to production systems is restricted and logged</li>
              <li>Regular security reviews and updates</li>
            </ul>
            <p className="text-slate-300 mt-4">
              In the event of a security breach affecting your personal data, we will notify you 
              and relevant authorities within 72 hours as required by applicable law.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">5. Third-Party Services & Data Sharing</h2>
            
            <h3 className="text-xl font-semibold mt-4 mb-3">5.1 Connected Fitness Platforms</h3>
            <p className="text-slate-300 mb-4">
              We integrate with the following services. Each requires your explicit OAuth authorization:
            </p>
            <ul className="list-disc pl-6 text-slate-300 space-y-2">
              <li>
                <strong>Strava:</strong> Activity and performance data. 
                See <a href="https://www.strava.com/legal/privacy" className="text-orange-400 hover:text-orange-300" target="_blank" rel="noopener noreferrer">Strava Privacy Policy</a>.
              </li>
              <li>
                <strong>Garmin Connect:</strong> Activity, health, and body composition data. 
                See <a href="https://www.garmin.com/en-US/privacy/connect/" className="text-orange-400 hover:text-orange-300" target="_blank" rel="noopener noreferrer">Garmin Privacy Policy</a>.
              </li>
            </ul>
            
            <h3 className="text-xl font-semibold mt-6 mb-3">5.2 Service Providers</h3>
            <p className="text-slate-300 mb-4">
              We use the following service providers to operate StrideIQ:
            </p>
            <ul className="list-disc pl-6 text-slate-300 space-y-2">
              <li><strong>Cloud hosting:</strong> For secure data storage and application hosting</li>
              <li><strong>AI services:</strong> For generating personalized coaching insights. See Section 6 (AI-Powered Insights) for full disclosure of providers, data handling, and your consent rights.</li>
            </ul>
            
            <h3 className="text-xl font-semibold mt-6 mb-3">5.3 Platform Usage Data</h3>
            <p className="text-slate-300">
              Strava and Garmin may collect usage data about how you access their APIs through StrideIQ. 
              This is governed by their respective privacy policies.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">6. AI-Powered Insights</h2>
            <p className="text-slate-300 mb-4">
              StrideIQ uses third-party AI services to generate personalized coaching insights, including
              morning briefings, activity narratives, coaching moments, and progress analysis. This section
              explains what data is processed, who processes it, and how you control AI use of your data.
            </p>

            <h3 className="text-xl font-semibold mt-6 mb-3">6.1 What Data Is Sent to AI Services</h3>
            <p className="text-slate-300 mb-2">
              To generate personalized coaching insights, we send relevant portions of your training data to
              AI providers. This includes:
            </p>
            <ul className="list-disc pl-6 text-slate-300 space-y-2">
              <li><strong>Activity metrics:</strong> pace, heart rate, cadence, distance, elevation, training
                load, splits, and effort data from your runs</li>
              <li><strong>Health data:</strong> sleep duration and quality, stress scores, HRV status, and
                body battery (when connected from Garmin)</li>
              <li><strong>Training context:</strong> recent training history, weekly volume, planned workouts,
                race goals, and training phase</li>
            </ul>
            <p className="text-slate-300 mt-3">
              Data is sent only to generate insights for you. We do not send your account credentials,
              payment information, or data from other users.
            </p>

            <h3 className="text-xl font-semibold mt-6 mb-3">6.2 AI Providers</h3>
            <p className="text-slate-300 mb-2">
              StrideIQ uses paid API tiers from the following AI providers:
            </p>
            <ul className="list-disc pl-6 text-slate-300 space-y-2">
              <li>
                <strong>Google (Gemini)</strong> — used for narrative generation and coaching intelligence.
                See <a href="https://policies.google.com/privacy" className="text-orange-400 hover:text-orange-300" target="_blank" rel="noopener noreferrer">Google Privacy Policy</a>.
              </li>
              <li>
                <strong>Anthropic (Claude)</strong> — used for coaching intelligence and correlational
                analysis. See <a href="https://www.anthropic.com/privacy" className="text-orange-400 hover:text-orange-300" target="_blank" rel="noopener noreferrer">Anthropic Privacy Policy</a>.
              </li>
            </ul>

            <h3 className="text-xl font-semibold mt-6 mb-3">6.3 Model Training</h3>
            <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
              <p className="text-slate-300 mb-2 font-semibold">StrideIQ does not train AI models on your data.</p>
              <p className="text-slate-300">
                Under the current terms of service for both Google&apos;s Gemini API and Anthropic&apos;s
                Claude API (verified February 2026), neither provider trains their models on data submitted
                through paid API tiers. We review provider terms quarterly. If a provider&apos;s terms
                change, we will update this policy immediately and, where required, seek renewed consent.
              </p>
            </div>

            <h3 className="text-xl font-semibold mt-6 mb-3">6.4 Your Consent</h3>
            <p className="text-slate-300 mb-2">
              AI processing of your training data requires your explicit consent. You are never enrolled
              silently. You can:
            </p>
            <ul className="list-disc pl-6 text-slate-300 space-y-2">
              <li><strong>Grant consent</strong> during onboarding or when prompted in the app</li>
              <li>
                <strong>Withdraw consent at any time</strong> via{' '}
                <strong>Settings → AI Processing</strong> — withdrawal takes effect immediately, and no
                new AI requests will be made on your behalf after withdrawal
              </li>
            </ul>

            <h3 className="text-xl font-semibold mt-6 mb-3">6.5 What Continues Without Consent</h3>
            <p className="text-slate-300">
              All non-AI features remain fully functional if you decline or withdraw AI processing consent.
              This includes activity data, charts, metrics, training calendar, pace splits, training load
              analysis, and performance tracking. Only AI-generated coaching text — morning briefings,
              activity narratives, coach chat, and progress analysis — requires consent.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">7. Withdrawing Consent & Disconnecting Services</h2>
            <p className="text-slate-300 mb-4">
              You can withdraw your consent and disconnect services at any time:
            </p>
            <ul className="list-disc pl-6 text-slate-300 space-y-2">
              <li>Go to <strong>Settings → Integrations</strong> in StrideIQ</li>
              <li>Click <strong>&quot;Disconnect&quot;</strong> next to any connected service</li>
              <li>This immediately stops new data syncing from that service</li>
            </ul>
            <p className="text-slate-300 mt-4">
              When you disconnect a service:
            </p>
            <ul className="list-disc pl-6 text-slate-300 space-y-2">
              <li>We stop accessing your data from that service immediately</li>
              <li>Previously synced activities remain in your StrideIQ account</li>
              <li>To delete previously synced data, use the account deletion feature or contact us</li>
            </ul>
            <p className="text-slate-300 mt-4">
              You can also revoke access directly from Strava or Garmin:
            </p>
            <ul className="list-disc pl-6 text-slate-300 space-y-2">
              <li><strong>Strava:</strong> Settings → My Apps → Revoke Access</li>
              <li><strong>Garmin:</strong> Garmin Connect → Account Settings → Connected Apps</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">8. Your Rights (GDPR & UK GDPR)</h2>
            <p className="text-slate-300 mb-4">
              Under applicable data protection laws, you have the right to:
            </p>
            <ul className="list-disc pl-6 text-slate-300 space-y-2">
              <li><strong>Access:</strong> Request a copy of all personal data we hold about you</li>
              <li><strong>Rectification:</strong> Correct inaccurate or incomplete personal data</li>
              <li><strong>Erasure:</strong> Request permanent deletion of your personal data</li>
              <li><strong>Portability:</strong> Receive your data in a structured, machine-readable format</li>
              <li><strong>Restriction:</strong> Request we limit processing of your data</li>
              <li><strong>Objection:</strong> Object to processing of your personal data</li>
              <li><strong>Withdraw consent:</strong> Withdraw consent at any time where processing is based on consent</li>
            </ul>
            <p className="text-slate-300 mt-4">
              To exercise these rights, use the Settings page or contact us at{' '}
              <a href="mailto:privacy@strideiq.run" className="text-orange-400 hover:text-orange-300">
                privacy@strideiq.run
              </a>. We will respond within 30 days.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">9. Data Retention</h2>
            <ul className="list-disc pl-6 text-slate-300 space-y-2">
              <li><strong>Active accounts:</strong> Data retained for as long as your account is active</li>
              <li><strong>Account deletion:</strong> All personal data permanently deleted within 30 days</li>
              <li><strong>User request:</strong> Data deleted upon your request within 30 days</li>
              <li><strong>Disconnected services:</strong> Previously synced data retained until you request deletion</li>
              <li><strong>Cached data:</strong> Temporary API caches cleared within 7 days</li>
            </ul>
            <p className="text-slate-300 mt-4">
              If you delete an activity on Strava or Garmin, we will reflect that deletion in StrideIQ 
              within 48 hours of our next sync.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">10. Cookies</h2>
            <p className="text-slate-300">
              We use essential cookies only for authentication and session management. 
              We do not use tracking cookies, advertising cookies, or third-party analytics cookies.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">11. International Data Transfers</h2>
            <p className="text-slate-300">
              Your data may be processed in the United States where our servers are located. 
              We ensure appropriate safeguards are in place for international transfers in 
              compliance with GDPR and UK GDPR requirements.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">12. Children&apos;s Privacy</h2>
            <p className="text-slate-300">
              StrideIQ is not intended for users under 18 years of age. We do not knowingly 
              collect personal data from children. If you believe we have collected data from 
              a child, please contact us immediately.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">13. Contact</h2>
            <p className="text-slate-300 mb-4">
              For privacy-related questions, data requests, or to exercise your rights:
            </p>
            <ul className="list-none text-slate-300 space-y-2">
              <li>
                <strong>Email:</strong>{' '}
                <a href="mailto:privacy@strideiq.run" className="text-orange-400 hover:text-orange-300">
                  privacy@strideiq.run
                </a>
              </li>
              <li>
                <strong>General inquiries:</strong>{' '}
                <a href="mailto:info@strideiq.run" className="text-orange-400 hover:text-orange-300">
                  info@strideiq.run
                </a>
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">14. Changes to This Policy</h2>
            <p className="text-slate-300">
              We may update this policy periodically. Significant changes will be communicated 
              via email or in-app notification. Continued use of StrideIQ after changes 
              constitutes acceptance of the updated policy.
            </p>
          </section>
        </div>
      </div>
    </div>
  )
}
