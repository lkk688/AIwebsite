'use client';
import { useLanguage } from '@/contexts/LanguageContext';
import { motion } from 'framer-motion';
import Link from 'next/link';

import { images } from '@/lib/images';

export default function Products() {
  const { t } = useLanguage();
  
  const categoryKeys = Object.keys(images.products.categories);

  return (
    <section id="products" className="py-24 bg-white">
      <div className="container mx-auto px-4">
        <div className="text-center mb-16">
          <h2 className="text-4xl font-bold mb-4 text-gray-900">{t.products.title}</h2>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto mb-8">{t.products.subtitle}</p>
          <Link 
            href="/products/all" 
            className="inline-flex items-center px-8 py-4 bg-blue-600 hover:bg-blue-700 text-white rounded-full font-bold text-lg transition-all shadow-md hover:shadow-lg gap-2"
          >
            {t.products.searchButton}
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {categoryKeys.map((key, index) => {
            // @ts-ignore
            const name = t.products.categories[key] || key;
            // @ts-ignore
            const img = images.products.categories[key];
            
            return (
              <motion.div
                key={key}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.1, duration: 0.5 }}
                className="group cursor-pointer"
              >
                <Link href={`/products/${key}`}>
                  <div className="relative overflow-hidden rounded-2xl shadow-lg aspect-[4/3] bg-gray-100">
                    <div className="absolute inset-0 bg-black/20 group-hover:bg-black/10 transition-colors z-10" />
                    <img
                      src={img}
                      alt={name}
                      className="w-full h-full object-cover transform group-hover:scale-110 transition-transform duration-700"
                    />
                    <div className="absolute bottom-0 left-0 right-0 p-6 bg-gradient-to-t from-black/90 via-black/50 to-transparent z-20">
                      <h3 className="text-2xl font-bold text-white translate-y-2 group-hover:translate-y-0 transition-transform duration-300">{name}</h3>
                    </div>
                  </div>
                </Link>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
