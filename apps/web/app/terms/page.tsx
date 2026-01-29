import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Terms of Service',
  description: 'Terms of service for StrideIQ - compliant with Strava API and Garmin Connect requirements',
}

export default function TermsOfServicePage() {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 py-16">
      <div className="max-w-4xl mx-auto px-6">
        <h1 className="text-4xl font-bold mb-8">Terms of Service</h1>
        <p className="text-slate-400 mb-8">Last updated: January 29, 2026</p>
        
        <div className="prose prose-invert max-w-none space-y-8">
          <section>
            <h2 className="text-2xl font-semibold mb-4">1. Acceptance of Terms</h2>
            <p className="text-slate-300">
              By accessing or using StrideIQ, you agree to be bound by these Terms of Service 
              and our <a href="/privacy" className="text-orange-400 hover:text-orange-300">Privacy Policy</a>. 
              If you do not agree, do not use the service.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">2. Description of Service</h2>
            <p className="text-slate-300">
              StrideIQ provides AI-powered running analytics, efficiency tracking, and correlation 
              analysis tools. We analyze your training data to identify patterns and provide insights. 
              The service includes free tools (calculators) and subscription-based features.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">3. Eligibility</h2>
            <p className="text-slate-300">
              You must be at least 18 years of age to use StrideIQ. By using the service, you 
              represent and warrant that you meet this requirement and have the legal capacity 
              to enter into these terms.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">4. User Accounts</h2>
            <p className="text-slate-300 mb-4">
              To access certain features, you must create an account. You agree to:
            </p>
            <ul className="list-disc pl-6 text-slate-300 space-y-2">
              <li>Provide accurate, current, and complete information</li>
              <li>Maintain the security and confidentiality of your password</li>
              <li>Accept responsibility for all activities under your account</li>
              <li>Notify us immediately of any unauthorized use</li>
              <li>Not share your account credentials with others</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">5. Third-Party Integrations</h2>
            <p className="text-slate-300 mb-4">
              StrideIQ integrates with third-party fitness platforms including Strava and Garmin Connect. 
              By connecting these services:
            </p>
            <ul className="list-disc pl-6 text-slate-300 space-y-2">
              <li>You authorize StrideIQ to access your data from those services</li>
              <li>You agree to comply with each platform&apos;s terms of service</li>
              <li>You understand that your use of those platforms is governed by their respective terms</li>
              <li>You can disconnect integrations at any time from Settings</li>
            </ul>
            
            <h3 className="text-xl font-semibold mt-6 mb-3">5.1 Strava</h3>
            <p className="text-slate-300 mb-2">
              Your use of Strava data through StrideIQ is subject to the{' '}
              <a href="https://www.strava.com/legal/terms" className="text-orange-400 hover:text-orange-300" target="_blank" rel="noopener noreferrer">
                Strava Terms of Service
              </a>{' '}and{' '}
              <a href="https://www.strava.com/legal/privacy" className="text-orange-400 hover:text-orange-300" target="_blank" rel="noopener noreferrer">
                Strava Privacy Policy
              </a>.
            </p>
            
            <h3 className="text-xl font-semibold mt-6 mb-3">5.2 Garmin Connect</h3>
            <p className="text-slate-300 mb-2">
              Your use of Garmin data through StrideIQ is subject to the{' '}
              <a href="https://www.garmin.com/en-US/legal/terms-of-use/" className="text-orange-400 hover:text-orange-300" target="_blank" rel="noopener noreferrer">
                Garmin Terms of Use
              </a>{' '}and{' '}
              <a href="https://www.garmin.com/en-US/privacy/connect/" className="text-orange-400 hover:text-orange-300" target="_blank" rel="noopener noreferrer">
                Garmin Privacy Policy
              </a>.
              Activity data displayed in StrideIQ may be sourced from Garmin devices and Garmin Connect.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">6. Acceptable Use</h2>
            <p className="text-slate-300 mb-4">
              You agree NOT to:
            </p>
            <ul className="list-disc pl-6 text-slate-300 space-y-2">
              <li>Violate any applicable laws or regulations</li>
              <li>Attempt to gain unauthorized access to our systems or other users&apos; accounts</li>
              <li>Interfere with or disrupt the service or its infrastructure</li>
              <li>Use the service for any illegal, fraudulent, or unauthorized purpose</li>
              <li>Transmit malware, viruses, or malicious code</li>
              <li>Scrape, harvest, or collect data without permission</li>
              <li>Reverse engineer, decompile, or disassemble any part of the service</li>
              <li>Circumvent any security or access controls</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">7. Health Disclaimer</h2>
            <div className="bg-orange-900/30 border border-orange-700/50 rounded-lg p-4">
              <p className="text-orange-400 font-semibold mb-2">
                IMPORTANT: THIS SERVICE DOES NOT PROVIDE MEDICAL ADVICE
              </p>
              <p className="text-slate-300">
                The insights, metrics, analysis, and recommendations provided by StrideIQ are for 
                informational and educational purposes only. They are not intended to diagnose, treat, 
                cure, or prevent any disease, injury, or health condition. Always consult with a 
                qualified healthcare provider, physician, or certified coach before making changes 
                to your training, nutrition, or health regimen. You use StrideIQ at your own risk.
              </p>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">8. Data Accuracy</h2>
            <p className="text-slate-300">
              We strive to provide accurate analysis based on the data you and connected services provide. 
              However, the accuracy of insights depends on the quality, completeness, and accuracy of input 
              data from your devices and connected platforms. We make no guarantees about the accuracy of 
              correlations, predictions, or recommendations.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">9. Intellectual Property</h2>
            <p className="text-slate-300 mb-4">
              The service, including all content, features, functionality, software, and branding, is 
              owned by StrideIQ and is protected by copyright, trademark, and other intellectual property 
              laws. Your data remains your property.
            </p>
            <p className="text-slate-300">
              Strava and the Strava logo are trademarks of Strava, Inc. Garmin and the Garmin logo are 
              trademarks of Garmin Ltd. or its subsidiaries.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">10. Third-Party Service Provider Disclaimers</h2>
            <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
              <p className="text-slate-300 mb-4">
                STRAVA, GARMIN, AND OTHER THIRD-PARTY SERVICE PROVIDERS DISCLAIM ALL WARRANTIES, 
                WHETHER EXPRESS, IMPLIED, OR STATUTORY, INCLUDING WITHOUT LIMITATION ANY IMPLIED 
                WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT.
              </p>
              <p className="text-slate-300">
                THIRD-PARTY SERVICE PROVIDERS SHALL NOT BE LIABLE FOR ANY CONSEQUENTIAL, SPECIAL, 
                PUNITIVE, OR INDIRECT DAMAGES ARISING FROM YOUR USE OF THEIR DATA THROUGH STRIDEIQ, 
                INCLUDING BUT NOT LIMITED TO LOSS OF PROFITS, DATA, OR OTHER INTANGIBLE LOSSES.
              </p>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">11. Limitation of Liability</h2>
            <p className="text-slate-300 mb-4">
              TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW:
            </p>
            <ul className="list-disc pl-6 text-slate-300 space-y-2">
              <li>
                STRIDEIQ AND ITS AFFILIATES, OFFICERS, DIRECTORS, EMPLOYEES, AND AGENTS SHALL NOT BE 
                LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, 
                INCLUDING BUT NOT LIMITED TO LOSS OF PROFITS, DATA, USE, OR OTHER INTANGIBLE LOSSES.
              </li>
              <li>
                OUR TOTAL LIABILITY FOR ANY CLAIMS ARISING FROM YOUR USE OF THE SERVICE SHALL NOT 
                EXCEED THE AMOUNT YOU PAID TO US IN THE TWELVE (12) MONTHS PRIOR TO THE CLAIM, OR 
                ONE HUNDRED DOLLARS ($100), WHICHEVER IS GREATER.
              </li>
              <li>
                THE SERVICE IS PROVIDED &quot;AS IS&quot; AND &quot;AS AVAILABLE&quot; WITHOUT WARRANTIES OF ANY KIND, 
                EITHER EXPRESS OR IMPLIED.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">12. Indemnification</h2>
            <p className="text-slate-300">
              You agree to indemnify, defend, and hold harmless StrideIQ and its affiliates, officers, 
              directors, employees, and agents from any claims, damages, losses, liabilities, costs, 
              and expenses (including reasonable attorneys&apos; fees) arising from your use of the service, 
              your violation of these terms, or your violation of any third party&apos;s rights.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">13. Termination</h2>
            <p className="text-slate-300 mb-4">
              We may terminate or suspend your account immediately, without prior notice, for:
            </p>
            <ul className="list-disc pl-6 text-slate-300 space-y-2">
              <li>Violations of these terms</li>
              <li>Conduct that may expose StrideIQ to liability</li>
              <li>Conduct that we reasonably believe is harmful to other users or the service</li>
            </ul>
            <p className="text-slate-300 mt-4">
              You may delete your account at any time from the Settings page. Upon termination, 
              your right to use the service ceases immediately, and we may delete your data in 
              accordance with our Privacy Policy.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">14. Governing Law & Dispute Resolution</h2>
            <p className="text-slate-300 mb-4">
              These terms shall be governed by and construed in accordance with the laws of the 
              State of Texas, United States, without regard to its conflict of law provisions.
            </p>
            <p className="text-slate-300">
              Any dispute arising from these terms or your use of the service shall be resolved 
              through binding arbitration in accordance with the rules of the American Arbitration 
              Association, except that either party may seek injunctive relief in any court of 
              competent jurisdiction.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">15. Changes to Terms</h2>
            <p className="text-slate-300">
              We reserve the right to modify these terms at any time. We will notify you of material 
              changes via email or in-app notification. Continued use of the service after such 
              notification constitutes acceptance of the updated terms.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">16. Severability</h2>
            <p className="text-slate-300">
              If any provision of these terms is found to be unenforceable or invalid, that provision 
              shall be limited or eliminated to the minimum extent necessary, and the remaining 
              provisions shall remain in full force and effect.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-4">17. Contact</h2>
            <p className="text-slate-300 mb-4">
              For questions about these terms:
            </p>
            <ul className="list-none text-slate-300 space-y-2">
              <li>
                <strong>Email:</strong>{' '}
                <a href="mailto:legal@strideiq.run" className="text-orange-400 hover:text-orange-300">
                  legal@strideiq.run
                </a>
              </li>
              <li>
                <strong>Support:</strong>{' '}
                <a href="mailto:support@strideiq.run" className="text-orange-400 hover:text-orange-300">
                  support@strideiq.run
                </a>
              </li>
            </ul>
          </section>
        </div>
      </div>
    </div>
  )
}
