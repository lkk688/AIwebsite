'use client';
import { useLanguage } from '@/contexts/LanguageContext';
import { CheckCircle } from 'lucide-react';
import { motion } from 'framer-motion';
import { useState } from 'react';
import ImageModal from './ImageModal';

import { images } from '@/lib/images';

export default function About() {
  const { t } = useLanguage();
  const [selectedImage, setSelectedImage] = useState<{
    src: string;
    alt: string;
    title: string;
    desc: string;
  } | null>(null);

  const aboutEntries = Object.entries(images.about);

  return (
    <section id="about" className="py-24 bg-white">
      <div className="container mx-auto px-4">
        {aboutEntries.map(([key, img], index) => {
          // Use dynamic data if available, fallback to main 'about' data for the first item
          // @ts-ignore
          const itemData = t.about.items?.[key] || (index === 0 ? t.about : {});
          
          const title = itemData.title || (index === 0 ? t.about.title : '');
          const description = itemData.description || (index === 0 ? t.about.description : '');
          const mission = itemData.mission || (index === 0 ? t.about.mission : '');
          // @ts-ignore
          const imageDesc = itemData.imageDesc || (index === 0 ? t.about.imageDesc : '');
          // @ts-ignore
          const stats = itemData.stats || (index === 0 ? t.about.stats : null);
          
          // Determine layout direction (alternate or consistent)
          const isEven = index % 2 === 0;

          return (
            <div key={key} className={`flex flex-col lg:flex-row items-center gap-16 ${index > 0 ? 'mt-24' : ''} ${!isEven ? 'lg:flex-row-reverse' : ''}`}>
              <motion.div 
                initial={{ opacity: 0, x: isEven ? -50 : 50 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6 }}
                className="w-full lg:w-1/2 relative group cursor-pointer"
                onClick={() => setSelectedImage({
                  src: img,
                  alt: title,
                  title: title,
                  desc: imageDesc
                })}
              >
                <div className="absolute -top-4 -left-4 w-24 h-24 bg-blue-100 rounded-tl-3xl -z-10"></div>
                <div className="absolute -bottom-4 -right-4 w-24 h-24 bg-blue-100 rounded-br-3xl -z-10"></div>
                 <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors duration-300 z-10 flex items-center justify-center rounded-2xl">
                     <span className="opacity-0 group-hover:opacity-100 bg-white/90 text-gray-900 px-6 py-3 rounded-full font-medium text-lg transition-opacity duration-300 shadow-xl transform translate-y-4 group-hover:translate-y-0">
                       View Image
                     </span>
                 </div>
                <img
                  src={img}
                  alt={title}
                  className="rounded-2xl shadow-2xl w-full h-[500px] object-cover"
                />
              </motion.div>
              
              <motion.div 
                initial={{ opacity: 0, x: isEven ? 50 : -50 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6 }}
                className="w-full lg:w-1/2"
              >
                <h2 className="text-4xl font-bold mb-6 text-gray-900 leading-tight">
                  {title}
                </h2>
                <p className="text-gray-600 text-lg mb-6 leading-relaxed">
                  {description}
                </p>
                {mission && (
                  <p className="text-gray-600 text-lg mb-8 leading-relaxed border-l-4 border-blue-600 pl-4 italic">
                    {mission}
                  </p>
                )}
                
                {stats && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                    {Object.entries(stats).map(([statKey, value]) => (
                      <div key={statKey} className="flex items-start gap-3">
                        <CheckCircle className="text-blue-600 mt-1 shrink-0" size={20} />
                        <span className="font-semibold text-gray-800 text-lg">{value as string}</span>
                      </div>
                    ))}
                  </div>
                )}
              </motion.div>
            </div>
          );
        })}
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
