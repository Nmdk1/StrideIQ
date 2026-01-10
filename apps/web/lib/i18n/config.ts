/**
 * Internationalization Configuration
 * 
 * Supports global running markets, especially:
 * - Major marathon cities (Tokyo, Berlin, London, Chicago, NYC, Boston)
 * - Countries with strong running cultures
 * 
 * Start with: English, Spanish, Japanese
 * Expand to: German, French, Portuguese, Chinese
 */

export const i18nConfig = {
  defaultLocale: 'en',
  locales: ['en', 'es', 'ja', 'de', 'fr', 'pt', 'zh'] as const,
  
  // Locales we actively support (have translations for)
  supportedLocales: ['en', 'es', 'ja'] as const,
  
  // Locale metadata
  localeNames: {
    en: 'English',
    es: 'Español',
    ja: '日本語',
    de: 'Deutsch',
    fr: 'Français',
    pt: 'Português',
    zh: '中文',
  } as const,
  
  // Markets by marathon majors and running culture
  markets: {
    en: ['US', 'UK', 'AU', 'CA', 'NZ', 'KE', 'ET'], // English-speaking + elite nations
    es: ['ES', 'MX', 'AR', 'CO', 'CL', 'PE'],       // Spanish-speaking
    ja: ['JP'],                                       // Japan
    de: ['DE', 'AT', 'CH'],                          // German-speaking
    fr: ['FR', 'BE', 'CH', 'CA'],                    // French-speaking
    pt: ['BR', 'PT'],                                 // Portuguese-speaking
    zh: ['CN', 'TW', 'HK', 'SG'],                    // Chinese-speaking
  },
} as const;

export type Locale = typeof i18nConfig.locales[number];
export type SupportedLocale = typeof i18nConfig.supportedLocales[number];

/**
 * Get locale from browser or default
 */
export function getPreferredLocale(): SupportedLocale {
  if (typeof window === 'undefined') return 'en';
  
  const browserLocale = navigator.language.split('-')[0];
  
  if (i18nConfig.supportedLocales.includes(browserLocale as SupportedLocale)) {
    return browserLocale as SupportedLocale;
  }
  
  return 'en';
}

/**
 * Check if locale is supported
 */
export function isSupported(locale: string): locale is SupportedLocale {
  return i18nConfig.supportedLocales.includes(locale as SupportedLocale);
}


