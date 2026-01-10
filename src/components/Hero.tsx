'use client';
import { useLanguage } from '@/contexts/LanguageContext';
import { useChat } from '@/contexts/ChatContext';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowRight, ChevronLeft, ChevronRight, MessageCircle } from 'lucide-react';
import { useState, useEffect } from 'react';
import Link from 'next/link';

type SlideLayout = 'left' | 'center' | 'right';

import { images } from '@/lib/images';

export default function Hero() {
  const { t } = useLanguage();
  const { setIsOpen } = useChat();
  const [currentSlide, setCurrentSlide] = useState(0);

  const slideKeys = Object.keys(images.hero);

  // Configuration for visual aspects of slides
  const slideConfig: Record<string, { color: string, layout: SlideLayout }> = {
    slide1: { color: 'from-blue-900/90', layout: 'left' },
    slide2: { color: 'from-purple-900/90', layout: 'center' },
    slide3: { color: 'from-orange-900/90', layout: 'right' },
    slide4: { color: 'from-green-900/90', layout: 'center' },
  };

  const defaultSlideConfig = { color: 'from-gray-900/90', layout: 'center' as SlideLayout };

  const slides = slideKeys.map(key => {
    // @ts-ignore
    const slideData = t.hero.slides?.[key] || { title: '', subtitle: '' };
    // @ts-ignore
    const img = images.hero[key];
    const config = slideConfig[key] || defaultSlideConfig;

    return {
      img,
      color: config.color,
      layout: config.layout,
      title: slideData.title,
      subtitle: slideData.subtitle,
    };
  });

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentSlide((prev) => (prev + 1) % slides.length);
    }, 6000); // Increased duration slightly for better readability
    return () => clearInterval(timer);
  }, [slides.length]);

  const nextSlide = () => setCurrentSlide((prev) => (prev + 1) % slides.length);
  const prevSlide = () => setCurrentSlide((prev) => (prev - 1 + slides.length) % slides.length);

  const getLayoutClasses = (layout: SlideLayout) => {
    switch (layout) {
      case 'left': return 'items-start text-left';
      case 'center': return 'items-center text-center mx-auto';
      case 'right': return 'items-end text-right ml-auto';
      default: return 'items-start text-left';
    }
  };

  return (
    <section className="relative h-screen flex items-center overflow-hidden">
      {/* Slideshow Background */}
      <div className="absolute inset-0 z-0">
        <AnimatePresence mode="wait">
          <motion.div
            key={currentSlide}
            initial={{ opacity: 0, scale: 1.1 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 1.5 }}
            className="absolute inset-0"
          >
            {/* Dynamic gradient overlay based on slide color */}
            <div className={`absolute inset-0 bg-gradient-to-t md:bg-gradient-to-r ${slides[currentSlide].color} via-black/40 to-transparent z-10 opacity-80`} />
            <img
              src={slides[currentSlide].img}
              alt="Background"
              className="w-full h-full object-cover"
            />
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Content Layer */}
      <div className="container mx-auto px-4 z-20 relative text-white h-full flex items-center">
        <AnimatePresence mode="wait">
           <motion.div
            key={currentSlide}
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -40 }}
            transition={{ duration: 0.8, delay: 0.3 }}
            className={`flex flex-col max-w-4xl w-full ${getLayoutClasses(slides[currentSlide].layout)}`}
          >
            <h1 className="text-4xl md:text-6xl lg:text-7xl font-bold mb-6 leading-tight drop-shadow-2xl">
              {slides[currentSlide].title}
            </h1>
            <p className="text-lg md:text-xl lg:text-2xl mb-10 text-gray-100 max-w-2xl drop-shadow-md leading-relaxed">
              {slides[currentSlide].subtitle}
            </p>
            
            <div className={`flex flex-col sm:flex-row gap-4 ${slides[currentSlide].layout === 'right' ? 'flex-row-reverse' : ''}`}>
              <Link
                href="/products/all"
                className="px-8 py-4 bg-white text-gray-900 hover:bg-gray-100 rounded-full text-lg font-bold transition-all flex items-center justify-center gap-2 shadow-xl hover:scale-105"
              >
                {t.hero.cta} <ArrowRight size={20} />
              </Link>
              <button
                type="button"
                onClick={() => {
                  console.log('Opening chat widget...');
                  setIsOpen(true);
                }}
                className="px-8 py-4 bg-transparent border-2 border-white hover:bg-white/10 backdrop-blur-md rounded-full text-white text-lg font-bold transition-all flex items-center justify-center gap-2 hover:scale-105"
              >
                {t.hero.contact} <MessageCircle size={20} />
              </button>
            </div>
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Navigation Controls */}
      <button 
        onClick={prevSlide}
        className="absolute left-4 md:left-8 top-1/2 -translate-y-1/2 z-30 p-3 rounded-full bg-black/20 hover:bg-black/40 backdrop-blur-md border border-white/20 text-white transition-all hover:scale-110"
        aria-label="Previous Slide"
      >
        <ChevronLeft size={32} />
      </button>
      <button 
        onClick={nextSlide}
        className="absolute right-4 md:right-8 top-1/2 -translate-y-1/2 z-30 p-3 rounded-full bg-black/20 hover:bg-black/40 backdrop-blur-md border border-white/20 text-white transition-all hover:scale-110"
        aria-label="Next Slide"
      >
        <ChevronRight size={32} />
      </button>
      
      {/* Slide Indicators */}
      <div className="absolute bottom-10 left-1/2 -translate-x-1/2 z-30 flex gap-3">
        {slides.map((_, index) => (
          <button
            key={index}
            onClick={() => setCurrentSlide(index)}
            className={`h-1.5 rounded-full transition-all duration-500 ${
              index === currentSlide ? 'bg-white w-12' : 'bg-white/30 w-6 hover:bg-white/50'
            }`}
          />
        ))}
      </div>
    </section>
  );
}
