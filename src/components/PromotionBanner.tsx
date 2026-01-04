'use client';

import { motion } from 'framer-motion';
import { useEffect, useState } from 'react';

import { config } from '@/config';

export default function PromotionBanner() {
  const [message, setMessage] = useState('');

  useEffect(() => {
    const bannerMessage = config.promotionBanner;
    if (bannerMessage) {
      setMessage(bannerMessage);
    }
  }, []);

  if (!message) {
    return null;
  }

  return (
    <div className="bg-gradient-to-r from-amber-500 to-orange-500 text-white py-2 overflow-hidden relative z-50 shadow-md">
      <div className="flex whitespace-nowrap overflow-hidden">
        <motion.div
          className="flex min-w-full"
          animate={{ x: ["0%", "-50%"] }}
          transition={{
            repeat: Infinity,
            ease: "linear",
            duration: 20,
          }}
        >
          {/* First copy */}
          <div className="flex shrink-0 items-center justify-around min-w-full">
             {[...Array(4)].map((_, i) => (
                <span key={`a-${i}`} className="text-sm font-bold tracking-wide mx-8">
                  {message}
                </span>
             ))}
          </div>
           {/* Second copy for seamless loop */}
           <div className="flex shrink-0 items-center justify-around min-w-full">
             {[...Array(4)].map((_, i) => (
                <span key={`b-${i}`} className="text-sm font-bold tracking-wide mx-8">
                  {message}
                </span>
             ))}
          </div>
        </motion.div>
      </div>
    </div>
  );
}
