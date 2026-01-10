import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Terms of Service',
  description: 'Terms of service for StrideIQ',
}

export default function TermsOfServicePage() {
  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 py-16">
      <div className="max-w-4xl mx-auto px-6">
        <h1 className="text-4xl font-bold mb-8">Terms of Service</h1>
        <p className="text-gray-400 mb-8">Last updated: January 7, 2026</p>
        
        <div className="prose prose-invert max-w-none space-y-8">
          <section>
            <h2 className="text-2xl font-semibold mb-4">1. Acceptance of Terms</h2>
            <p className="text-gray-300">
              By accessing or using StrideIQ, you agree to 
              be bound by these Terms of Service. If you do not agree, do not use the service.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">2. Description of Service</h2>
            <p className="text-gray-300">
StrideIQ provides AI-powered running analytics, efficiency 
                tracking, and correlation analysis tools. We analyze your training data to 
              identify patterns and provide insights. The service includes free tools 
              (calculators) and subscription-based features.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">3. User Accounts</h2>
            <p className="text-gray-300 mb-4">
              To access certain features, you must create an account. You agree to:
            </p>
            <ul className="list-disc pl-6 text-gray-300 space-y-2">
              <li>Provide accurate information</li>
              <li>Maintain the security of your password</li>
              <li>Accept responsibility for all activities under your account</li>
              <li>Notify us immediately of any unauthorized use</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">4. Acceptable Use</h2>
            <p className="text-gray-300 mb-4">
              You agree NOT to:
            </p>
            <ul className="list-disc pl-6 text-gray-300 space-y-2">
              <li>Violate any laws or regulations</li>
              <li>Attempt to gain unauthorized access to our systems</li>
              <li>Interfere with or disrupt the service</li>
              <li>Use the service for any illegal or unauthorized purpose</li>
              <li>Transmit malware or malicious code</li>
              <li>Scrape or harvest data without permission</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">5. Health Disclaimer</h2>
            <p className="text-gray-300 mb-4 font-semibold text-orange-400">
              IMPORTANT: This service does not provide medical advice.
            </p>
            <p className="text-gray-300">
              The insights, metrics, and analysis provided are for informational purposes only. 
              They are not intended to diagnose, treat, cure, or prevent any disease or health 
              condition. Always consult with a qualified healthcare provider before making 
              changes to your training, nutrition, or health regimen.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">6. Data Accuracy</h2>
            <p className="text-gray-300">
              We strive to provide accurate analysis based on the data you provide. However, 
              the accuracy of insights depends on the quality and completeness of input data. 
              We make no guarantees about the accuracy of correlations or predictions.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">7. Intellectual Property</h2>
            <p className="text-gray-300">
              The service, including all content, features, and functionality, is owned by 
                StrideIQ and is protected by copyright and other intellectual 
              property laws. Your data remains your property.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">8. Limitation of Liability</h2>
            <p className="text-gray-300">
              TO THE MAXIMUM EXTENT PERMITTED BY LAW, WE SHALL NOT BE LIABLE FOR ANY INDIRECT, 
              INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, INCLUDING BUT NOT LIMITED 
              TO LOSS OF PROFITS, DATA, OR OTHER INTANGIBLE LOSSES, RESULTING FROM YOUR USE OF 
              THE SERVICE.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">9. Termination</h2>
            <p className="text-gray-300">
              We may terminate or suspend your account at any time for violations of these terms. 
              You may delete your account at any time from the Settings page. Upon termination, 
              your right to use the service ceases immediately.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">10. Changes to Terms</h2>
            <p className="text-gray-300">
              We reserve the right to modify these terms at any time. Continued use of the 
              service after changes constitutes acceptance of the new terms.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">11. Contact</h2>
            <p className="text-gray-300">
              For questions about these terms, contact us at: 
              <a href="mailto:support@strideiq.run" className="text-orange-400 hover:text-orange-300 ml-1">
                support@strideiq.run
              </a>
            </p>
          </section>
        </div>
      </div>
    </div>
  )
}
