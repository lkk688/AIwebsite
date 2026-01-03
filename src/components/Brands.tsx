'use client';
import { useLanguage } from '@/contexts/LanguageContext';
import { motion } from 'framer-motion';

export default function Brands() {
  const { t } = useLanguage();
  
  // @ts-ignore
  const brands = t.brands.list || [];
  
  // Duplicate brands to create seamless loop effect
  const marqueeBrands = [...brands, ...brands, ...brands];

  return (
    <section className="py-20 bg-gray-50 border-y border-gray-100 overflow-hidden">
      <div className="container mx-auto px-4 text-center mb-12">
        <h2 className="text-3xl font-bold mb-4 text-gray-900">{t.brands.title}</h2>
        <p className="text-gray-600 max-w-2xl mx-auto">{t.brands.subtitle}</p>
      </div>

      <div className="relative w-full overflow-hidden">
        {/* Gradient Masks for fading effect */}
        <div className="absolute top-0 left-0 z-10 w-24 h-full bg-gradient-to-r from-gray-50 to-transparent pointer-events-none" />
        <div className="absolute top-0 right-0 z-10 w-24 h-full bg-gradient-to-l from-gray-50 to-transparent pointer-events-none" />
        
        <motion.div 
          className="flex whitespace-nowrap items-center"
          animate={{ x: [0, -1000] }}
          transition={{
            x: {
              repeat: Infinity,
              repeatType: "loop",
              duration: 30,
              ease: "linear",
            },
          }}
        >
          {marqueeBrands.map((brand: string, index: number) => (
            <div 
              key={`${brand}-${index}`} 
              className="inline-block mx-12 text-3xl md:text-5xl font-black text-gray-300 hover:text-blue-900 transition-colors duration-300 cursor-default select-none uppercase tracking-tight"
            >
              {brand}
            </div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
