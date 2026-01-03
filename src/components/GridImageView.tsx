'use client';
import { useLanguage } from '@/contexts/LanguageContext';
import { useState } from 'react';
import { motion } from 'framer-motion';
import { Grid, ArrowRight } from 'lucide-react';
import GalleryModal from './GalleryModal';

import { config } from '@/config';

// Generate list of images JWL001.jpg to JWL238.jpg
const generateSampleImages = () => {
  const images = [];
  for (let i = 1; i <= 238; i++) {
    const num = i.toString().padStart(3, '0');
    images.push(config.gallery.imagePattern.replace('{num}', num));
  }
  return images;
};

const allSampleImages = generateSampleImages();

export default function GridImageView() {
  const { t } = useLanguage();
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Show first 12 images as preview
  const previewImages = allSampleImages.slice(0, 12);

  return (
    <section className="py-20 bg-white border-b border-gray-100">
      <div className="container mx-auto px-4">
        <div className="text-center mb-12">
          {/* @ts-ignore */}
          <h2 className="text-3xl font-bold mb-4 text-gray-900">{t.samples?.title || 'Customer Samples'}</h2>
          {/* @ts-ignore */}
          <p className="text-gray-600 max-w-2xl mx-auto">{t.samples?.subtitle || 'A glimpse into our extensive portfolio.'}</p>
        </div>

        {/* Preview Grid */}
        <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-10">
          {previewImages.map((src, index) => (
            <motion.div
              key={src}
              initial={{ opacity: 0, scale: 0.9 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ delay: index * 0.05 }}
              className="aspect-square rounded-xl overflow-hidden shadow-sm border border-gray-100 cursor-pointer group relative"
              onClick={() => setIsModalOpen(true)}
            >
              <img
                src={src}
                alt={`Sample ${index + 1}`}
                className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500"
                loading="lazy"
              />
              <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors duration-300 flex items-center justify-center">
                 <div className="opacity-0 group-hover:opacity-100 text-white transform scale-50 group-hover:scale-100 transition-all duration-300">
                   <Grid size={24} />
                 </div>
              </div>
            </motion.div>
          ))}
        </div>

        {/* View All Button */}
        <div className="text-center">
          <button
            onClick={() => setIsModalOpen(true)}
            className="inline-flex items-center gap-2 px-8 py-3 bg-white border-2 border-blue-600 text-blue-600 font-bold rounded-full hover:bg-blue-600 hover:text-white transition-all duration-300 group"
          >
            {/* @ts-ignore */}
            {t.samples?.viewAll || 'View All Samples'}
            <ArrowRight size={20} className="group-hover:translate-x-1 transition-transform" />
          </button>
        </div>
      </div>

      <GalleryModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        images={allSampleImages}
        // @ts-ignore
        title={t.samples?.galleryTitle}
      />
    </section>
  );
}
