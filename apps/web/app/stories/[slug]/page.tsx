import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import Link from 'next/link'
import { JsonLd } from '@/components/seo/JsonLd'

/**
 * Story registry — add an entry here when publishing a new story.
 * Each entry drives metadata, JSON-LD, and page content.
 */
const STORIES: Record<string, Story> = {
  'father-son-state-age-group-records': {
    slug: 'father-son-state-age-group-records',
    title: 'Father and Son Set State Age Group Records at the Same Race — Both Using StrideIQ',
    description:
      'A 57-year-old and a 79-year-old. Same race. Two state age group records. The training data, pacing strategy, and what StrideIQ tracked before the gun.',
    publishedAt: '2026-03-08',
    author: 'Michael Shaffer',
    content: null, // Set to JSX content when publishing
  },
}

interface Story {
  slug: string
  title: string
  description: string
  publishedAt: string
  author: string
  content: React.ReactNode | null
}

interface Props {
  params: { slug: string }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const story = STORIES[params.slug]
  if (!story) return {}

  return {
    title: story.title,
    description: story.description,
    authors: [{ name: story.author }],
    alternates: {
      canonical: `https://strideiq.run/stories/${story.slug}`,
    },
    openGraph: {
      type: 'article',
      url: `https://strideiq.run/stories/${story.slug}`,
      images: [{ url: '/og-image.png', width: 1200, height: 630, alt: story.title }],
      publishedTime: story.publishedAt,
      authors: [story.author],
    },
  }
}

export default function StoryPage({ params }: Props) {
  const story = STORIES[params.slug]
  if (!story) notFound()

  const articleJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: story.title,
    description: story.description,
    author: { '@type': 'Person', name: story.author },
    publisher: {
      '@type': 'Organization',
      name: 'StrideIQ',
      url: 'https://strideiq.run',
    },
    datePublished: story.publishedAt,
    url: `https://strideiq.run/stories/${story.slug}`,
    image: 'https://strideiq.run/og-image.png',
  }

  const breadcrumbJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://strideiq.run' },
      { '@type': 'ListItem', position: 2, name: 'Stories', item: 'https://strideiq.run/stories' },
      { '@type': 'ListItem', position: 3, name: story.title, item: `https://strideiq.run/stories/${story.slug}` },
    ],
  }

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <JsonLd data={articleJsonLd} />
      <JsonLd data={breadcrumbJsonLd} />

      <article className="max-w-3xl mx-auto px-6 py-16">
        {/* Breadcrumb */}
        <nav className="text-sm text-slate-400 mb-10">
          <Link href="/" className="hover:text-orange-400 transition-colors">Home</Link>
          <span className="mx-2">/</span>
          <Link href="/stories" className="hover:text-orange-400 transition-colors">Stories</Link>
          <span className="mx-2">/</span>
          <span className="text-slate-200">Case Study</span>
        </nav>

        {/* Header */}
        <header className="mb-12">
          <p className="text-orange-400 text-sm font-semibold uppercase tracking-widest mb-4">
            Real Results
          </p>
          <h1 className="text-3xl md:text-4xl font-black leading-tight mb-6">
            {story.title}
          </h1>
          <div className="flex items-center gap-4 text-sm text-slate-400">
            <span>{story.author}</span>
            <span>·</span>
            <time dateTime={story.publishedAt}>
              {new Date(story.publishedAt).toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'long',
                day: 'numeric',
              })}
            </time>
          </div>
        </header>

        {/* Content — populated when publishing */}
        {story.content ? (
          <div className="prose prose-invert prose-slate prose-lg max-w-none">
            {story.content}
          </div>
        ) : (
          <div className="bg-slate-800/60 border border-orange-500/30 rounded-2xl p-8 text-center">
            <p className="text-orange-400 font-semibold mb-2">Coming soon</p>
            <p className="text-slate-300">
              This story publishes within 48 hours of race day.
            </p>
          </div>
        )}

        {/* Footer CTA */}
        <div className="border-t border-slate-800 mt-16 pt-10">
          <p className="text-slate-400 mb-4">
            Want to see what StrideIQ can do with your data?
          </p>
          <div className="flex flex-wrap gap-3">
            <Link
              href="/tools"
              className="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 border border-slate-700/50 rounded-lg text-slate-200 font-semibold text-sm transition-colors"
            >
              Free training calculators
            </Link>
            <Link
              href="/register"
              className="px-5 py-2.5 bg-orange-600 hover:bg-orange-500 text-white rounded-lg font-semibold text-sm shadow-lg shadow-orange-500/20 transition-colors"
            >
              Start free trial
            </Link>
          </div>
        </div>
      </article>
    </div>
  )
}
