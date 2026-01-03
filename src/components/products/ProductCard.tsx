import React from 'react';
import Link from 'next/link';
import { Product } from '@/lib/products';
import { useLanguage } from '@/contexts/LanguageContext';

interface ProductCardProps {
  product: Product;
  category: string;
}

export default function ProductCard({ product, category }: ProductCardProps) {
  const { locale, t } = useLanguage();
  // @ts-ignore
  const currentName = product.attributes.name[locale];
  // @ts-ignore
  const currentDescription = product.attributes.description[locale];

  return (
    <Link 
      href={`/products/${category}/${product.id}`}
      className="block group"
    >
      <div className="bg-white rounded-2xl shadow-sm hover:shadow-lg transition-shadow duration-300 overflow-hidden">
        <div className="aspect-[4/3] overflow-hidden bg-gray-100 relative">
          <img 
            src={product.attributes.images[0].url} 
            alt={currentName} 
            className="w-full h-full object-cover transform group-hover:scale-105 transition-transform duration-500"
          />
          <div className="absolute inset-0 bg-black/0 group-hover:bg-black/5 transition-colors duration-300" />
        </div>
        <div className="p-6">
          {(product.attributes.tags || product.attributes.collections) && (product.attributes.tags || product.attributes.collections)?.length! > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {(product.attributes.tags || product.attributes.collections)?.slice(0, 3).map((tag) => {
                // Try direct match, then lowercased match, then fallback to original tag
                // @ts-ignore
                const displayTag = t.products.collections?.[tag] || t.products.collections?.[tag.toLowerCase()] || tag;
                return (
                  <span key={tag} className="bg-gray-100 text-gray-600 text-[10px] font-medium px-2 py-0.5 rounded border border-gray-200 uppercase tracking-wider">
                    {displayTag}
                  </span>
                );
              })}
            </div>
          )}
          <h3 className="text-xl font-bold text-gray-900 mb-2 group-hover:text-blue-600 transition-colors">
            {currentName}
          </h3>
          <p className="text-gray-500 line-clamp-2 mb-4 text-sm">
            {currentDescription}
          </p>
          <span className="text-blue-600 font-semibold text-sm uppercase tracking-wide">
            {t.products.viewDetails}
          </span>
        </div>
      </div>
    </Link>
  );
}
