import { MetadataRoute } from 'next'
import goalPaceData from '@/data/goal-pace-tables.json'
import ageDemoData from '@/data/age-gender-tables.json'
import equivalencyData from '@/data/equivalency-tables.json'
import bqData from '@/data/bq-tables.json'

const BASE_URL = 'https://strideiq.run'
const NOW = new Date()

type Freq = MetadataRoute.Sitemap[0]['changeFrequency']

function entry(url: string, priority: number, freq: Freq = 'monthly') {
  return { url: `${BASE_URL}${url}`, lastModified: NOW, changeFrequency: freq, priority }
}

export default function sitemap(): MetadataRoute.Sitemap {
  // ---- Static core pages ----
  const staticPages = [
    entry('/', 1.0, 'weekly'),
    entry('/tools', 0.9),
    entry('/tools/training-pace-calculator', 0.85),
    entry('/tools/age-grading-calculator', 0.85),
    entry('/tools/heat-adjusted-pace', 0.85),
    // Static distance tool pages (config-driven, slugs do not change)
    entry('/tools/training-pace-calculator/5k-training-paces', 0.75),
    entry('/tools/training-pace-calculator/10k-training-paces', 0.75),
    entry('/tools/training-pace-calculator/half-marathon-training-paces', 0.75),
    entry('/tools/training-pace-calculator/marathon-training-paces', 0.75),
    entry('/tools/age-grading-calculator/good-5k-times-by-age', 0.75),
    entry('/tools/age-grading-calculator/good-10k-times-by-age', 0.75),
    entry('/tools/age-grading-calculator/good-half-marathon-times-by-age', 0.75),
    entry('/tools/age-grading-calculator/good-marathon-times-by-age', 0.75),
    // Race equivalency hub
    entry('/tools/race-equivalency', 0.8),
    // BQ hub
    entry('/tools/boston-qualifying', 0.85),
    // Editorial / brand
    entry('/stories', 0.8, 'weekly'),
    entry('/mission', 0.8),
    entry('/about', 0.7),
    entry('/support', 0.6),
    entry('/register', 0.6),
    entry('/privacy', 0.4, 'yearly'),
    entry('/terms', 0.4, 'yearly'),
  ]

  // ---- Goal pages — auto-generated from goal-pace-tables.json ----
  const goalPages = Object.keys(goalPaceData)
    .filter((k) => k !== '_meta')
    .map((slug) => entry(`/tools/training-pace-calculator/goals/${slug}`, 0.7))

  // ---- Demographic pages — auto-generated from age-gender-tables.json ----
  const demoPages = Object.keys(ageDemoData)
    .filter((k) => k !== '_meta')
    .map((slug) => entry(`/tools/age-grading-calculator/demographics/${slug}`, 0.7))

  // ---- Equivalency pages — auto-generated from equivalency-tables.json ----
  const equivPages = Object.keys(equivalencyData)
    .filter((k) => k !== '_meta')
    .map((slug) => entry(`/tools/race-equivalency/${slug}`, 0.7))

  // ---- BQ per-age-group pages — auto-generated from bq-tables.json ----
  const bqPages = Object.keys(bqData)
    .filter((k) => k !== '_meta')
    .map((slug) => entry(`/tools/boston-qualifying/${slug}`, 0.75))

  return [
    ...staticPages,
    ...goalPages,
    ...demoPages,
    ...equivPages,
    ...bqPages,
  ]
}
