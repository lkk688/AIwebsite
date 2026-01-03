'use client';
import { useState, useEffect } from 'react';
import { Locale } from '@/lib/types';
import { useLanguage } from '@/contexts/LanguageContext';
import { Menu, X, Globe, ShoppingBag, Search } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import Link from 'next/link';

import { config } from '@/config';

export default function Navbar() {
  const { t, locale, switchLanguage } = useLanguage();
  const [isOpen, setIsOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // @ts-ignore
  const navLinks = Object.entries(t.nav).map(([key, value]) => {
    const href = key === 'home' ? '/' : key === 'productSearch' ? '/products/all' : `/#${key}`;
    const isSearch = key === 'productSearch';
    return { name: value, href, isSearch };
  });

  // Use languages from config
  const languages = config.languages;

  const currentLang = languages.find((lang) => lang.code === locale);
  const nextLang = languages.find((lang) => lang.code !== locale) || languages[0];

  const handleSwitchLanguage = () => {
    switchLanguage(nextLang.code as Locale);
  };

  return (
    <nav className={`fixed w-full z-50 transition-all duration-300 ${scrolled ? 'bg-white shadow-md py-3' : 'bg-gradient-to-r from-blue-900/80 to-blue-800/80 backdrop-blur-md py-4 border-b border-white/10'}`}>
      <div className="container mx-auto px-4 flex justify-between items-center">
        {/* Logo & Brand */}
        <Link href="/" className="flex items-center gap-2 group">
          <div className="bg-amber-400 p-2 rounded-lg text-blue-900 group-hover:bg-amber-300 transition-colors shadow-lg">
             <ShoppingBag size={24} strokeWidth={2.5} />
          </div>
          <div className={`text-xl md:text-2xl font-bold tracking-tight ${scrolled ? 'text-gray-900' : 'text-white'} group-hover:opacity-90 transition-opacity`}>
            {t.companyName}
          </div>
        </Link>

        {/* Desktop Nav */}
        <div className="hidden md:flex items-center space-x-8">
          {navLinks.map((link) => (
            link.isSearch ? (
              <Link 
                key={link.name} 
                href={link.href} 
                className="group/search relative flex items-center justify-center w-10 h-10 rounded-full hover:bg-white/10 transition-colors"
              >
                <Search size={20} className={scrolled ? 'text-gray-700 hover:text-blue-700' : 'text-white/90 hover:text-amber-400'} />
                <span className="absolute top-full mt-2 px-2 py-1 bg-gray-800 text-white text-xs rounded opacity-0 group-hover/search:opacity-100 transition-opacity whitespace-nowrap pointer-events-none shadow-lg">
                  {link.name}
                </span>
              </Link>
            ) : (
              <Link key={link.name} href={link.href} className={`text-sm font-semibold tracking-wide uppercase ${scrolled ? 'text-gray-700 hover:text-blue-700' : 'text-white/90 hover:text-amber-400'} transition-colors`}>
                {link.name}
              </Link>
            )
          ))}
          <button
            onClick={handleSwitchLanguage}
            className={`flex items-center space-x-1 px-3 py-1 rounded-full border-2 font-bold text-xs ${scrolled ? 'border-blue-600 text-blue-700 hover:bg-blue-50' : 'border-amber-400 text-amber-400 hover:bg-amber-400/10'} transition-all`}
          >
            <Globe size={14} />
            <span>{nextLang.name}</span>
          </button>
        </div>

        {/* Mobile Menu Button */}
        <div className="md:hidden flex items-center space-x-4">
             <button
            onClick={handleSwitchLanguage}
            className={`text-xs font-bold px-2 py-1 rounded border ${scrolled ? 'border-gray-300 text-gray-700' : 'border-white/30 text-white'}`}
          >
            {nextLang.label}
          </button>
          <button onClick={() => setIsOpen(!isOpen)} className={scrolled ? 'text-gray-900' : 'text-white'}>
            {isOpen ? <X size={28} /> : <Menu size={28} />}
          </button>
        </div>
      </div>

      {/* Mobile Menu */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="md:hidden bg-white border-t border-gray-100 shadow-xl"
          >
            <div className="flex flex-col p-6 space-y-6">
              {navLinks.map((link) => (
                <Link
                  key={link.name}
                  href={link.href}
                  className="text-gray-800 hover:text-blue-700 text-xl font-bold border-b border-gray-100 pb-2"
                  onClick={() => setIsOpen(false)}
                >
                  {link.name}
                </Link>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </nav>
  );
}
