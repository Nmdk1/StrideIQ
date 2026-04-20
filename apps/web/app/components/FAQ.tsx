import { JsonLd } from '@/components/seo/JsonLd'

const FAQ_ITEMS = [
  {
    question: 'How do I calculate my training paces from a race result?',
    answer:
      'Enter your recent race time and distance into our training pace calculator. It uses the Daniels/Gilbert oxygen cost equations to generate your personal Easy, Marathon, Threshold, Interval, and Repetition pace zones — calibrated to your current fitness level, not generic tables.',
  },
  {
    question: 'What is age-graded running performance and why does it matter?',
    answer:
      'Age-grading compares your performance to world-standard benchmarks for your age using WMA (World Masters Athletics) tables. A 75% age-grade means you ran 75% as fast as the world record for your age group — enabling fair comparison and recognition across all ages.',
  },
  {
    question: 'How much does heat slow down my running pace?',
    answer:
      'Heat and humidity significantly slow running performance. Our heat-adjusted pace calculator estimates the physiological cost increase using temperature and dew point. Above 55°F adjustments begin; at 80°F+ with high humidity, expect 20–30 seconds per mile of slowdown.',
  },
  {
    question: 'Can runners over 50 still improve with structured training?',
    answer:
      'Yes — with the right approach. Masters runners adapt well to structured training when recovery is respected. StrideIQ builds N=1 response curves from your own data, ignoring population averages and age-based assumptions that may not apply to you at all.',
  },
  {
    question: 'How does StrideIQ differ from a human running coach?',
    answer:
      'StrideIQ learns exclusively from your data — not population averages or one coach\'s intuition. Every insight cites the underlying evidence (dates, run labels, key values). You can verify every claim. It\'s auditable precision alongside your own judgment as the athlete.',
  },
  {
    question: 'What running data does StrideIQ analyze to improve performance?',
    answer:
      'StrideIQ syncs with Garmin Connect and Strava to analyze run splits, pace, heart rate, and elevation. Combined with self-reported sleep and nutrition check-ins, it identifies which factors actually correlate with your best and worst performances — specific to you, not population averages.',
  },
  {
    question: 'Does StrideIQ tell me what my sleep or nutrition did to my training?',
    answer:
      'Yes — that is the core of what StrideIQ does. A Bayesian engine runs every night across your sleep, nutrition check-ins, training load, and outcomes, looking for correlations specific to you. When the evidence is strong enough, the coach surfaces it with the runs, dates, and numbers attached. When the evidence is not strong enough, the system stays quiet rather than guess.',
  },
  {
    question: 'What training paces should I use for a half marathon?',
    answer:
      'Your half marathon training paces depend on your current fitness, not generic charts. Use our training pace calculator with a recent 5K or 10K result to get personalized Easy, Threshold, and Interval paces. Threshold pace — close to half marathon race pace — is most critical.',
  },
]

const faqJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  mainEntity: FAQ_ITEMS.map((item) => ({
    '@type': 'Question',
    name: item.question,
    acceptedAnswer: {
      '@type': 'Answer',
      text: item.answer,
    },
  })),
}

export default function FAQ() {
  return (
    <section className="py-20 bg-slate-900 border-t border-slate-800">
      <JsonLd data={faqJsonLd} />
      <div className="max-w-4xl mx-auto px-6">
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            Common questions from runners
          </h2>
          <p className="text-lg text-slate-400">
            Direct answers. No filler.
          </p>
        </div>

        <div className="space-y-6">
          {FAQ_ITEMS.map((item, i) => (
            <div
              key={i}
              className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-6"
            >
              <h3 className="text-lg font-semibold text-white mb-3">
                {item.question}
              </h3>
              <p className="text-slate-300 leading-relaxed">{item.answer}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
