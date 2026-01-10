/**
 * Internationalization (i18n) System
 * 
 * Usage:
 *   const { t } = useTranslation();
 *   <p>{t('dashboard.title')}</p>
 */

export { i18nConfig, type Locale, type SupportedLocale } from './config';
export { useTranslation, I18nProvider, useLocale } from './provider';
export { en, type TranslationKeys } from './translations/en';
export { es } from './translations/es';
export { ja } from './translations/ja';


