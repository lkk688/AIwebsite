'use client';
import { motion, AnimatePresence } from 'framer-motion';
import { X, ChevronLeft, ChevronRight } from 'lucide-react';
import { useEffect, useState } from 'react';

interface ImageModalProps {
  isOpen: boolean;
  onClose: () => void;
  imageSrc: string;
  images?: string[];
  altText: string;
  title?: string;
  description?: string;
}

export default function ImageModal({
  isOpen,
  onClose,
  imageSrc,
  images,
  altText,
  title,
  description
}: ImageModalProps) {
  const [currentIndex, setCurrentIndex] = useState(0);

  // Prevent scrolling when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      // Initialize index based on imageSrc if images array exists
      if (images && images.length > 0) {
        const foundIndex = images.indexOf(imageSrc);
        setCurrentIndex(foundIndex >= 0 ? foundIndex : 0);
      }
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, imageSrc, images]);

  const handleNext = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (images && images.length > 1) {
      setCurrentIndex((prev) => (prev + 1) % images.length);
    }
  };

  const handlePrev = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (images && images.length > 1) {
      setCurrentIndex((prev) => (prev - 1 + images.length) % images.length);
    }
  };

  const currentSrc = images && images.length > 0 ? images[currentIndex] : imageSrc;
  const showControls = images && images.length > 1;

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-8">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="absolute inset-0 bg-black/80 backdrop-blur-sm"
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            className="relative bg-white rounded-2xl shadow-2xl max-w-5xl w-full max-h-[90vh] overflow-hidden flex flex-col md:flex-row"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={onClose}
              className="absolute top-4 right-4 z-10 p-2 bg-black/50 hover:bg-black/70 text-white rounded-full transition-colors"
            >
              <X size={24} />
            </button>
            
            <div className="w-full md:w-2/3 h-[40vh] md:h-auto bg-gray-100 flex items-center justify-center relative p-4 group">
               <img
                src={currentSrc}
                alt={altText}
                className="w-full h-full object-contain"
              />

              {showControls && (
                <>
                  <button
                    onClick={handlePrev}
                    className="absolute left-4 top-1/2 -translate-y-1/2 p-2 bg-black/30 hover:bg-black/50 text-white rounded-full transition-all opacity-0 group-hover:opacity-100"
                  >
                    <ChevronLeft size={32} />
                  </button>
                  <button
                    onClick={handleNext}
                    className="absolute right-4 top-1/2 -translate-y-1/2 p-2 bg-black/30 hover:bg-black/50 text-white rounded-full transition-all opacity-0 group-hover:opacity-100"
                  >
                    <ChevronRight size={32} />
                  </button>
                  
                  <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex gap-2">
                    {images!.map((_, idx) => (
                      <div 
                        key={idx}
                        className={`w-2 h-2 rounded-full transition-colors ${idx === currentIndex ? 'bg-white' : 'bg-white/40'}`}
                      />
                    ))}
                  </div>
                </>
              )}
            </div>
            
            <div className="w-full md:w-1/3 p-8 flex flex-col overflow-y-auto bg-white max-h-[50vh] md:max-h-full">
              {title && (
                <h3 className="text-2xl font-bold text-gray-900 mb-4">{title}</h3>
              )}
              {description && (
                <p className="text-gray-600 text-lg leading-relaxed whitespace-pre-line">
                  {description}
                </p>
              )}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
