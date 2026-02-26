import type { Metadata } from 'next'
import Link from 'next/link'
import HeatAdjustedPace from '@/app/components/tools/HeatAdjustedPace'
import { JsonLd } from '@/components/seo/JsonLd'

export const metadata: Metadata = {
  title: 'Heat-Adjusted Running Pace Calculator - Hot Weather Running',
  description:
    'Free heat-adjusted running pace calculator. Adjust your training paces for temperature and humidity. Maintain true physiological effort in hot conditions using research-backed heat stress formulas.',
  alternates: {
    canonical: 'https://strideiq.run/tools/heat-adjusted-pace',
  },
  openGraph: {
    url: 'https://strideiq.run/tools/heat-adjusted-pace',
    images: [{ url: '/og-image.png', width: 1200, height: 630, alt: 'StrideIQ Heat-Adjusted Pace Calculator' }],
  },
}

const toolJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'SoftwareApplication',
  name: 'StrideIQ Heat-Adjusted Pace Calculator',
  url: 'https://strideiq.run/tools/heat-adjusted-pace',
  applicationCategory: 'HealthApplication',
  operatingSystem: 'Web',
  description:
    'Calculate heat-adjusted running paces for temperature and humidity. Maintain correct physiological effort in hot weather.',
  offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
}

const FAQ_ITEMS = [
  {
    q: 'At what temperature does heat start slowing running pace?',
    a: 'Heat effects on running pace begin around 55–60°F (13–15°C) and become significant above 70°F (21°C). At 80°F (27°C) with moderate humidity, most runners need to slow 15–30 seconds per mile to maintain the same physiological effort as their normal training paces.',
  },
  {
    q: 'Does humidity matter as much as temperature for running pace?',
    a: 'Yes — humidity can matter more than air temperature. High humidity prevents sweat from evaporating, reducing your body\'s ability to cool itself. The dew point is the most useful single measure: above 60°F dew point, cooling becomes impaired; above 70°F dew point, all runners are significantly affected.',
  },
  {
    q: 'Should I use my heat-adjusted pace for races in hot weather?',
    a: 'Yes, for effort-based racing. In hot conditions, running your normal goal pace means significantly higher physiological stress and higher race failure risk. Adjust your goal pace based on conditions — the heat-adjusted pace reflects an equivalent physiological effort to your cool-weather race pace.',
  },
]

export default function HeatAdjustedPacePage() {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <JsonLd data={toolJsonLd} />

      <div className="max-w-4xl mx-auto px-6 py-12">
        {/* Breadcrumb */}
        <nav className="text-sm text-slate-400 mb-8">
          <Link href="/tools" className="hover:text-orange-400 transition-colors">Tools</Link>
          <span className="mx-2">/</span>
          <span className="text-slate-200">Heat-Adjusted Pace</span>
        </nav>

        {/* H1 */}
        <h1 className="text-3xl md:text-4xl font-bold mb-4">
          Heat-Adjusted Running Pace Calculator
        </h1>

        {/* Answer capsule */}
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-5 mb-6">
          <p className="text-slate-200 leading-relaxed">
            <strong className="text-orange-400">Quick answer:</strong> Enter your normal training pace and current temperature (with optional humidity). The calculator estimates the physiological cost increase from heat stress and outputs an adjusted pace that matches the same internal effort — so you train at the right intensity regardless of conditions.
          </p>
        </div>

        {/* Calculator island */}
        <div className="bg-slate-800 border border-slate-700/50 rounded-2xl p-6 mb-10 shadow-xl">
          <HeatAdjustedPace />
        </div>

        {/* How it works */}
        <section className="mb-12">
          <h2 className="text-2xl font-bold mb-4">How heat-adjusted running pace works</h2>
          <div className="prose prose-invert prose-slate max-w-none space-y-4 text-slate-300">
            <p>
              Running in heat and humidity stresses the body beyond the mechanical demands of the pace itself. Your cardiovascular system works harder to both deliver oxygen to muscles <em>and</em> pump blood to the skin for cooling. This dual demand reduces the aerobic capacity available for running — meaning your normal training paces require more effort than they would in cool conditions.
            </p>
            <p>
              The calculator uses <strong>temperature and dew point</strong> to estimate the effective heat stress (similar to wet-bulb globe temperature concepts used in exercise science research). The dew point matters more than relative humidity because it directly measures the moisture content of air — the key factor limiting sweat evaporation and cooling.
            </p>
            <p>
              The adjustment is intended to maintain <strong>equivalent physiological effort</strong>, not to match a specific pace. When you run your heat-adjusted pace in 85°F conditions, your body is working as hard as it would at your normal pace in 55°F conditions. This preserves the training stimulus while avoiding unnecessary fatigue and heat illness risk.
            </p>
            <p>
              For <strong>race pacing in hot weather</strong> — including marathon training cycles that include summer long runs — use this calculator to set realistic pace targets. Attempting goal marathon pace in high heat is a leading cause of late-race blow-ups. Accepting a slower pace early protects your ability to finish strong.
            </p>
          </div>
        </section>

        {/* Related FAQs */}
        <section className="mb-12">
          <h2 className="text-2xl font-bold mb-6">Common questions</h2>
          <div className="space-y-5">
            {FAQ_ITEMS.map((item, i) => (
              <div key={i} className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-5">
                <h3 className="font-semibold text-white mb-2">{item.q}</h3>
                <p className="text-slate-300 text-sm leading-relaxed">{item.a}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Related tools */}
        <section className="border-t border-slate-800 pt-8">
          <h2 className="text-xl font-bold mb-4">Related calculators</h2>
          <div className="flex flex-wrap gap-3">
            <Link href="/tools/training-pace-calculator" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              Training Pace Calculator →
            </Link>
            <Link href="/tools/age-grading-calculator" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              Age-Grading Calculator →
            </Link>
            <Link href="/tools" className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-sm text-slate-200 transition-colors">
              All Tools →
            </Link>
          </div>
        </section>
      </div>
    </div>
  )
}
