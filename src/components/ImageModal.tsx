'use client';
import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';
import { useEffect } from 'react';

interface ImageModalProps {
  isOpen: boolean;
  onClose: () => void;
  imageSrc: string;
  altText: string;
  title?: string;
  description?: string;
}

export default function ImageModal({
  isOpen,
  onClose,
  imageSrc,
  altText,
  title,
  description
}: ImageModalProps) {
  // Prevent scrolling when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isOpen]);

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
            
            <div className="w-full md:w-2/3 h-[40vh] md:h-auto bg-gray-100 flex items-center justify-center relative p-4">
               <img
                src={imageSrc}
                alt={altText}
                className="w-full h-full object-contain"
              />
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
