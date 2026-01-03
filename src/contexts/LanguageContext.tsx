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

  const switchLanguage = (lang: Locale) => {
    setLocale(lang);
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
