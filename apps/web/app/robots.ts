import { MetadataRoute } from 'next'

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: '*',
      allow: '/',
      disallow: [
        '/api/',
        '/admin/',
        '/dashboard/',
        '/home/',
        '/activities/',
        '/checkin/',
        '/settings/',
        '/profile/',
        '/onboarding/',
        '/discovery/',
        '/nutrition/',
        '/availability/',
        '/calendar/',
        '/insights/',
        '/coach/',
        '/analytics/',
        '/training-load/',
        '/personal-bests/',
        '/compare/',
        '/plans/',
        '/diagnostic/',
        '/progress/',
        '/fingerprint/',
      ],
    },
    sitemap: 'https://strideiq.run/sitemap.xml',
  }
}
