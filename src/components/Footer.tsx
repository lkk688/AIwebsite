'use client';
import { useLanguage } from '@/contexts/LanguageContext';

export default function Footer() {
  const { t } = useLanguage();
  return (
    <footer className="bg-blue-900 text-white py-12 border-t border-blue-800">
      <div className="container mx-auto px-4 text-center">
        <h3 className="text-2xl font-bold mb-4 text-amber-400 tracking-wide">{t.companyName}</h3>
        <p className="text-blue-200 mb-8 max-w-md mx-auto">{t.hero.subtitle}</p>
        <div className="text-blue-300/60 text-sm">
          {t.footer.rights}
        </div>
      </div>
    </footer>
  );
}
