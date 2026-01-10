'use client';
import { useLanguage } from '@/contexts/LanguageContext';
import { motion } from 'framer-motion';
import { Factory, Cog, CheckCircle, ChevronRight, ChevronLeft } from 'lucide-react';
import { useState } from 'react';
import ImageModal from './ImageModal';

import { images } from '@/lib/images';

// Helper component for individual facility cards
const FacilityCard = ({ 
  featureKey, 
  index, 
  title, 
  desc, 
  imageList, 
  config, 
  onImageClick 
}: { 
  featureKey: string, 
  index: number, 
  title: string, 
  desc: string, 
  imageList: string[], 
  config: { icon: any, color: string },
  onImageClick: (src: string) => void
}) => {
  const [currentImageIndex, setCurrentImageIndex] = useState(0);
  const Icon = config.icon;

  const handleNext = (e: React.MouseEvent) => {
    e.stopPropagation();
    setCurrentImageIndex((prev) => (prev + 1) % imageList.length);
  };

  const handlePrev = (e: React.MouseEvent) => {
    e.stopPropagation();
    setCurrentImageIndex((prev) => (prev - 1 + imageList.length) % imageList.length);
  };

  const currentImage = imageList[currentImageIndex];

  return (
    <motion.div
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
        <p className="text-gray-600 text-sm">
            {/* Display description if needed, though usually hidden in card until modal? 
                The original code didn't show desc in card body, only title. 
                I'll keep it consistent and not show desc here, or maybe I should?
                Original: <div className="p-8 ..."> ... <h3>{title}</h3> </div>
                It seems it didn't show desc. I'll stick to original design.
            */}
        </p>
      </div>
      <div 
        className="h-64 overflow-hidden cursor-pointer group relative"
        onClick={() => onImageClick(currentImage)}
      >
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors duration-300 z-10 flex items-center justify-center">
          <span className="opacity-0 group-hover:opacity-100 bg-white/90 text-gray-900 px-4 py-2 rounded-full font-medium text-sm transition-opacity duration-300 shadow-lg transform translate-y-2 group-hover:translate-y-0">
            View Details
          </span>
        </div>
        
        <img 
          src={currentImage} 
          alt={`${title} - Image ${currentImageIndex + 1}`} 
          className="w-full h-full object-cover transition-transform duration-700"
          // Removed hover:scale-105 to avoid conflict with carousel controls or just kept it? 
          // I'll keep it but maybe reduce effect or rely on group-hover on container.
        />

        {/* Carousel Controls */}
        {imageList.length > 1 && (
          <>
            <button
              onClick={handlePrev}
              className="absolute left-2 top-1/2 -translate-y-1/2 z-20 bg-white/80 hover:bg-white text-gray-800 p-1 rounded-full shadow-md transition-all opacity-0 group-hover:opacity-100"
              aria-label="Previous image"
            >
              <ChevronLeft size={20} />
            </button>
            <button
              onClick={handleNext}
              className="absolute right-2 top-1/2 -translate-y-1/2 z-20 bg-white/80 hover:bg-white text-gray-800 p-1 rounded-full shadow-md transition-all opacity-0 group-hover:opacity-100"
              aria-label="Next image"
            >
              <ChevronRight size={20} />
            </button>
            
            {/* Dots Indicator */}
            <div className="absolute bottom-2 left-1/2 -translate-x-1/2 z-20 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              {imageList.map((_, idx) => (
                <div 
                  key={idx} 
                  className={`w-1.5 h-1.5 rounded-full ${idx === currentImageIndex ? 'bg-white' : 'bg-white/50'}`}
                />
              ))}
            </div>
          </>
        )}
      </div>
    </motion.div>
  );
};

export default function Facility() {
  const { t } = useLanguage();
  const [selectedImage, setSelectedImage] = useState<{
    src: string;
    images?: string[];
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
            
            // @ts-ignore - Dynamic access to image data (now an array)
            const rawImages = images.facility[key];
            // Ensure it's an array
            const imageList = Array.isArray(rawImages) ? rawImages : [rawImages];
            
            const config = featureConfig[key] || defaultFeature;

            return (
              <FacilityCard
                key={key}
                featureKey={key}
                index={index}
                title={title}
                desc={desc}
                imageList={imageList}
                config={config}
                onImageClick={(src) => setSelectedImage({
                  src,
                  images: imageList,
                  alt: title,
                  title: title,
                  desc: desc
                })}
              />
            );
          })}
        </div>
      </div>

      <ImageModal
        isOpen={!!selectedImage}
        onClose={() => setSelectedImage(null)}
        imageSrc={selectedImage?.src || ''}
        images={selectedImage?.images}
        altText={selectedImage?.alt || ''}
        title={selectedImage?.title}
        description={selectedImage?.desc}
      />
    </section>
  );
}