'use client';
import React, { use } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import ProductBrowser from '@/components/products/ProductBrowser';

export default function ProductPage({ params }: { params: Promise<{ category: string }> }) {
  const { category } = use(params);
  const { t } = useLanguage();

  return (
    <div className="min-h-screen bg-gray-50 pt-24 pb-12">
      <div className="container mx-auto px-4">
        <Link 
          href="/#products" 
          className="inline-flex items-center text-blue-600 hover:text-blue-700 font-medium mb-8 transition-colors"
        >
          <ArrowLeft size={20} className="mr-2" />
          {t.products.backToCategories}
        </Link>
        
        <ProductBrowser initialCategory={category} />
      </div>
    </div>
  );
}
