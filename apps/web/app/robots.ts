import { MetadataRoute } from 'next'

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: '*',
      allow: '/',
      disallow: [
        '/api/',
        '/admin/',
        '/home/',
        '/activities/',
        '/checkin/',
        '/settings/',
        '/profile/',
        '/onboarding/',
        '/discovery/',
        '/nutrition/',
        '/calendar/',
        '/insights/',
        '/coach/',
        '/analytics/',
        '/training-load/',
        '/personal-bests/',
        '/compare/',
        '/plans/',
        '/progress/',
        '/fingerprint/',
      ],
    },
    sitemap: 'https://strideiq.run/sitemap.xml',
  }
}
