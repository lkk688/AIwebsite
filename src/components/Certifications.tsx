'use client';
import { useLanguage } from '@/contexts/LanguageContext';
import { motion } from 'framer-motion';
import { useState } from 'react';
import ImageModal from './ImageModal';

import { images } from '@/lib/images';

export default function Certifications() {
  const { t } = useLanguage();
  const [selectedCert, setSelectedCert] = useState<{
    src: string;
    alt: string;
    title: string;
    desc: string;
  } | null>(null);

  const certKeys = Object.keys(images.certifications);

  return (
    <section id="certifications" className="py-20 bg-white border-t border-gray-100">
      <div className="container mx-auto px-4 text-center">
        <h2 className="text-3xl font-bold mb-4 text-gray-900">{t.certifications.title}</h2>
        <p className="text-xl text-gray-600 mb-12 max-w-2xl mx-auto">{t.certifications.subtitle}</p>

        <div className="flex flex-wrap justify-center gap-12 items-center">
          {certKeys.map((key, index) => {
            // @ts-ignore
            const item = t.certifications.items[key];
            const title = item?.title || key;
            const desc = item?.desc || '';
            // @ts-ignore
            const img = images.certifications[key];

            return (
              <motion.div
                key={key}
                initial={{ opacity: 0, scale: 0.8 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.1 }}
                className="w-48 h-48 flex items-center justify-center p-4 bg-white rounded-xl shadow-sm border border-gray-100 hover:shadow-md transition-all duration-300 cursor-pointer hover:scale-105"
                onClick={() => setSelectedCert({
                  src: img,
                  alt: title,
                  title: title,
                  desc: desc
                })}
              >
                <img 
                  src={img} 
                  alt={title} 
                  className="max-w-full max-h-full object-contain transition-all duration-300"
                />
              </motion.div>
            );
          })}
        </div>
      </div>
      
      <ImageModal
        isOpen={!!selectedCert}
        onClose={() => setSelectedCert(null)}
        imageSrc={selectedCert?.src || ''}
        altText={selectedCert?.alt || ''}
        title={selectedCert?.title}
        description={selectedCert?.desc}
      />
    </section>
  );
}
