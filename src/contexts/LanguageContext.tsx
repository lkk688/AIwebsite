'use client';

import React, { createContext, useContext, useState, ReactNode } from 'react';
import { translations } from '@/lib/translations';
import { Locale } from '@/lib/types';

type LanguageContextType = {
  locale: Locale;
  t: typeof translations['en'] | typeof translations['zh'];
  switchLanguage: (lang: Locale) => void;
};

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [locale, setLocale] = useState<Locale>('en');

  // Load language preference on mount
  React.useEffect(() => {
    // 1. Check localStorage
    const savedLocale = localStorage.getItem('language') as Locale;
    if (savedLocale && (savedLocale === 'en' || savedLocale === 'zh')) {
      setLocale(savedLocale);
      return;
    }

    // 2. Check Browser Language
    const browserLang = navigator.language.toLowerCase();
    if (browserLang.startsWith('zh')) {
      setLocale('zh');
    }
    // Default is already 'en'
  }, []);

  const switchLanguage = (lang: Locale) => {
    setLocale(lang);
    localStorage.setItem('language', lang);
  };

  const t = translations[locale];

  return (
    <LanguageContext.Provider value={{ locale, t, switchLanguage }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (context === undefined) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
}
