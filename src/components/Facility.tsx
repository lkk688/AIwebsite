'use client';
import { useLanguage } from '@/contexts/LanguageContext';
import { motion } from 'framer-motion';
import { Factory, Cog, CheckCircle } from 'lucide-react';
import { useState } from 'react';
import ImageModal from './ImageModal';

import { images } from '@/lib/images';

export default function Facility() {
  const { t } = useLanguage();
  const [selectedImage, setSelectedImage] = useState<{
    src: string;
    alt: string;
    title: string;
    desc: string;
  } | null>(null);

  // Configuration for features based on keys
  const featureConfig: Record<string, { icon: any, color: string }> = {
    capacity: { icon: Factory, color: 'bg-blue-100 text-blue-600' },
    machinery: { icon: Cog, color: 'bg-amber-100 text-amber-600' },
    inspection: { icon: CheckCircle, color: 'bg-green-100 text-green-600' },
  };

  const defaultFeature = { icon: Factory, color: 'bg-gray-100 text-gray-600' };

  const featureKeys = Object.keys(images.facility);

  return (
    <section id="facility" className="py-24 bg-gray-50">
      <div className="container mx-auto px-4">
        <div className="text-center mb-16">
          <h2 className="text-4xl font-bold mb-4 text-gray-900">{t.facility.title}</h2>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">{t.facility.subtitle}</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {featureKeys.map((key, index) => {
            // @ts-ignore - Dynamic access to translation data
            const featureData = t.facility.features[key] || { title: key, desc: '' };
            const title = featureData.title;
            const desc = featureData.desc;
            // @ts-ignore - Dynamic access to image data
            const image = images.facility[key];
            
            const config = featureConfig[key] || defaultFeature;
            const Icon = config.icon;

            return (
              <motion.div
                key={key}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.1 }}
                className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden flex flex-col"
              >
                <div className="p-8 flex flex-col items-center text-center flex-grow">
                  <div className={`w-16 h-16 ${config.color} rounded-full flex items-center justify-center mb-6`}>
                    <Icon size={32} />
                  </div>
                  <h3 className="text-xl font-bold text-gray-900 mb-4">
                    {title}
                  </h3>
                </div>
                <div 
                  className="h-64 overflow-hidden cursor-pointer group relative"
                  onClick={() => setSelectedImage({
                    src: image,
                    alt: title,
                    title: title,
                    desc: desc
                  })}
                >
                  <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors duration-300 z-10 flex items-center justify-center">
                    <span className="opacity-0 group-hover:opacity-100 bg-white/90 text-gray-900 px-4 py-2 rounded-full font-medium text-sm transition-opacity duration-300 shadow-lg transform translate-y-2 group-hover:translate-y-0">
                      View Details
                    </span>
                  </div>
                  <img 
                    src={image} 
                    alt={title} 
                    className="w-full h-full object-cover hover:scale-105 transition-transform duration-700"
                  />
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>

      <ImageModal
        isOpen={!!selectedImage}
        onClose={() => setSelectedImage(null)}
        imageSrc={selectedImage?.src || ''}
        altText={selectedImage?.alt || ''}
        title={selectedImage?.title}
        description={selectedImage?.desc}
      />
    </section>
  );
}
