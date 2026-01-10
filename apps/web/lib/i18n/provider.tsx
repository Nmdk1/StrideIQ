"use client";

/**
 * i18n Provider and Hooks
 * 
 * Provides translation functions throughout the app.
 */

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { i18nConfig, SupportedLocale, getPreferredLocale } from './config';
import { en, TranslationKeys } from './translations/en';
import { es } from './translations/es';
import { ja } from './translations/ja';

// Translation dictionaries
const translations: Record<SupportedLocale, TranslationKeys> = {
  en,
  es,
  ja,
};

// Context type
interface I18nContextType {
  locale: SupportedLocale;
  setLocale: (locale: SupportedLocale) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
}

const I18nContext = createContext<I18nContextType | null>(null);

/**
 * Get nested value from object by dot-notation key
 */
function getNestedValue(obj: any, path: string): string {
  const keys = path.split('.');
  let value = obj;
  
  for (const key of keys) {
    if (value === undefined || value === null) {
      return path; // Return key if path doesn't exist
    }
    value = value[key];
  }
  
  return typeof value === 'string' ? value : path;
}

/**
 * Replace template params in string
 * e.g., "Hello {{name}}" with {name: "World"} => "Hello World"
 */
function interpolate(str: string, params?: Record<string, string | number>): string {
  if (!params) return str;
  
  return str.replace(/\{\{(\w+)\}\}/g, (_, key) => {
    return params[key]?.toString() ?? `{{${key}}}`;
  });
}

/**
 * I18n Provider Component
 */
interface I18nProviderProps {
  children: ReactNode;
  initialLocale?: SupportedLocale;
}

export function I18nProvider({ children, initialLocale }: I18nProviderProps) {
  const [locale, setLocaleState] = useState<SupportedLocale>(initialLocale || 'en');
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    // On mount, check localStorage or browser preference
    const stored = localStorage.getItem('locale') as SupportedLocale;
    if (stored && i18nConfig.supportedLocales.includes(stored)) {
      setLocaleState(stored);
    } else {
      setLocaleState(getPreferredLocale());
    }
    setMounted(true);
  }, []);

  const setLocale = (newLocale: SupportedLocale) => {
    setLocaleState(newLocale);
    localStorage.setItem('locale', newLocale);
    // Update HTML lang attribute
    document.documentElement.lang = newLocale;
  };

  const t = (key: string, params?: Record<string, string | number>): string => {
    const dict = translations[locale] || translations.en;
    const value = getNestedValue(dict, key);
    return interpolate(value, params);
  };

  // Prevent hydration mismatch by rendering default locale first
  if (!mounted) {
    const t = (key: string, params?: Record<string, string | number>): string => {
      const value = getNestedValue(en, key);
      return interpolate(value, params);
    };
    
    return (
      <I18nContext.Provider value={{ locale: 'en', setLocale, t }}>
        {children}
      </I18nContext.Provider>
    );
  }

  return (
    <I18nContext.Provider value={{ locale, setLocale, t }}>
      {children}
    </I18nContext.Provider>
  );
}

/**
 * Hook to access translation function
 */
export function useTranslation() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error('useTranslation must be used within I18nProvider');
  }
  return { t: context.t };
}

/**
 * Hook to access and change locale
 */
export function useLocale() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error('useLocale must be used within I18nProvider');
  }
  return { locale: context.locale, setLocale: context.setLocale };
}

/**
 * Language Selector Component
 */
export function LanguageSelector() {
  const { locale, setLocale } = useLocale();

  return (
    <select
      value={locale}
      onChange={(e) => setLocale(e.target.value as SupportedLocale)}
      className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-300"
      aria-label="Select language"
    >
      {i18nConfig.supportedLocales.map((loc) => (
        <option key={loc} value={loc}>
          {i18nConfig.localeNames[loc]}
        </option>
      ))}
    </select>
  );
}


