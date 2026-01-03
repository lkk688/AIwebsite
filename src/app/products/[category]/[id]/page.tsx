'use client';
import React, { use, useState, useEffect } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { useChat } from '@/contexts/ChatContext';
import Link from 'next/link';
import { ArrowLeft, MessageSquareText } from 'lucide-react';
import { getProductById, Product } from '@/lib/products';
import { motion } from 'framer-motion';

export default function ProductDetailPage({ params }: { params: Promise<{ category: string; id: string }> }) {
  const { category, id } = use(params);
  const { locale, t } = useLanguage();
  const { openChatWithContext } = useChat();
  const [product, setProduct] = useState<Product | null>(null);
  const [activeImage, setActiveImage] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [selectedVariant, setSelectedVariant] = useState<string | null>(null);

  useEffect(() => {
    const fetchProduct = async () => {
      const data = await getProductById(id);
      if (data) {
        setProduct(data);
        setActiveImage(data.attributes.images[0].url);
        // Set default variant if available
        if (data.attributes.variants && data.attributes.variants.length > 0) {
          setSelectedVariant(data.attributes.variants[0].id);
          // If the variant has an image, set it as active
          if (data.attributes.variants[0].imageLarge) {
            setActiveImage(data.attributes.variants[0].imageLarge);
          } else if (data.attributes.variants[0].image) {
            setActiveImage(data.attributes.variants[0].image);
          }
        }
      }
      setLoading(false);
    };
    fetchProduct();
  }, [id]);

  const handleVariantSelect = (variantId: string, imageUrl: string, imageLarge?: string) => {
    setSelectedVariant(variantId);
    if (imageLarge) {
      setActiveImage(imageLarge);
    } else if (imageUrl) {
      setActiveImage(imageUrl);
    }
  };

  if (loading) return <div className="min-h-screen pt-24 flex justify-center items-center">Loading...</div>;
  if (!product) return <div className="min-h-screen pt-24 flex justify-center items-center">Product not found</div>;

  // @ts-ignore
  const currentName = product.attributes.name[locale] || product.attributes.name['en'];
  // @ts-ignore
  const currentDescription = product.attributes.description[locale] || product.attributes.description['en'];
  // @ts-ignore
  const currentMaterials = product.attributes.materials[locale] || product.attributes.materials['en'];
  // @ts-ignore
  const currentSpecs = product.attributes.specifications[locale] || product.attributes.specifications['en'];
  const images = product.attributes.images;
  const variants = product.attributes.variants;

  const name = currentName;
  const description = currentDescription;
  const materials = currentMaterials;

  const handleContactClick = () => {
    let message = `Hi, I'm interested in the ${currentName} (ID: ${id}).`;
    if (selectedVariant) {
      const variant = variants?.find(v => v.id === selectedVariant);
      if (variant) {
        // @ts-ignore
        const variantName = variant.name[locale] || variant.name['en'];
        message += ` Variant: ${variantName}.`;
      }
    }
    message += ` Can you provide a quote?`;
    openChatWithContext(message);
  };

  // @ts-ignore
  const categoryName = t.products.categories[category] || category;

  return (
    <div className="min-h-screen bg-gray-50 pt-24 pb-12">
      <div className="container mx-auto px-4">
        {/* Breadcrumb / Back Link */}
        <Link 
          href={`/products/${category}`} 
          className="inline-flex items-center text-blue-600 hover:text-blue-700 font-medium mb-8 transition-colors"
        >
          <ArrowLeft size={20} className="mr-2" />
          {t.products.backTo} {categoryName}
        </Link>
        
        <div className="bg-white rounded-3xl shadow-xl overflow-hidden">
          <div className="flex flex-col lg:flex-row">
            
            {/* Image Gallery Section */}
            <div className="w-full lg:w-1/2 p-6 md:p-10 bg-gray-100">
              <motion.div 
                key={activeImage}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.3 }}
                className="aspect-[4/3] rounded-2xl overflow-hidden bg-white shadow-sm mb-4"
              >
                <img src={activeImage} alt={name} className="w-full h-full object-cover" />
              </motion.div>
              
              <div className="flex gap-4 overflow-x-auto pb-2">
                {images.map((img) => (
                  <button 
                    key={img.id} 
                    onClick={() => setActiveImage(img.url)}
                    className={`shrink-0 w-20 h-20 rounded-lg overflow-hidden border-2 transition-all ${activeImage === img.url ? 'border-blue-600 ring-2 ring-blue-200' : 'border-transparent opacity-70 hover:opacity-100'}`}
                  >
                    <img src={img.url} alt={img.alt} className="w-full h-full object-cover" />
                  </button>
                ))}
              </div>
            </div>

            {/* Product Details Section */}
            <div className="w-full lg:w-1/2 p-8 md:p-12 flex flex-col justify-center">
              <div className="flex flex-col gap-2 mb-4">
                <span className="text-blue-600 font-bold uppercase tracking-wider text-sm">{categoryName}</span>
                {(product.attributes.tags || product.attributes.collections) && (product.attributes.tags || product.attributes.collections)?.length! > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {(product.attributes.tags || product.attributes.collections)?.map((tag) => {
                      // Try direct match, then lowercased match, then fallback to original tag
                      // @ts-ignore
                      const displayTag = t.products.collections?.[tag] || t.products.collections?.[tag.toLowerCase()] || tag;
                      return (
                        <span key={tag} className="bg-gray-100 text-gray-600 text-xs font-medium px-2.5 py-0.5 rounded border border-gray-200 uppercase tracking-wider">
                          {displayTag}
                        </span>
                      );
                    })}
                  </div>
                )}
              </div>
              <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">{name}</h1>
              
              <div className="prose prose-lg text-gray-600 mb-8">
                <p>{description}</p>
                <p className="text-xs text-gray-400 font-mono mt-2">ID: {id}</p>
              </div>

              {/* Variants Section */}
              {variants && variants.length > 0 && (
                <div className="mb-8">
                  <h3 className="text-lg font-bold text-gray-900 mb-4">{t.products.selectVariant || 'Select Variant'}</h3>
                  <div className="flex flex-wrap gap-4">
                    {variants.map((variant) => {
                      // @ts-ignore
                      const variantName = variant.name[locale] || variant.name['en'];
                      const isSelected = selectedVariant === variant.id;
                      
                      return (
                        <button
                          key={variant.id}
                          onClick={() => handleVariantSelect(variant.id, variant.image, variant.imageLarge)}
                          className={`group relative flex items-center p-2 rounded-xl border-2 transition-all ${
                            isSelected 
                              ? 'border-blue-600 bg-blue-50 ring-1 ring-blue-200' 
                              : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                          }`}
                        >
                          <div className="w-12 h-12 rounded-lg overflow-hidden bg-gray-100 mr-3 border border-gray-100">
                            {variant.image ? (
                              <img 
                                src={variant.image} 
                                alt={variantName} 
                                className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-300" 
                              />
                            ) : (
                              <div className="w-full h-full flex items-center justify-center bg-gray-200 text-gray-400 text-xs">
                                No Img
                              </div>
                            )}
                          </div>
                          <div className="text-left pr-2">
                            <p className={`font-semibold text-sm ${isSelected ? 'text-blue-900' : 'text-gray-900'}`}>
                              {variantName}
                            </p>
                            <p className="text-xs text-gray-500 font-mono mt-0.5">{variant.sku}</p>
                          </div>
                          {isSelected && (
                            <div className="absolute top-2 right-2 w-2 h-2 rounded-full bg-blue-600 animate-pulse"></div>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Materials Section */}
              <div className="mb-8">
                <h3 className="text-lg font-bold text-gray-900 mb-4">{t.products.materials}</h3>
                <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {/* @ts-ignore */}
                  {currentMaterials.map((material: string, idx: number) => (
                    <li key={idx} className="flex items-center text-gray-700 bg-gray-50 px-4 py-2 rounded-lg border border-gray-100">
                      <span className="w-2 h-2 bg-blue-500 rounded-full mr-3"></span>
                      {material}
                    </li>
                  ))}
                </ul>
              </div>

              {/* Specifications Section */}
              <div>
                <h3 className="text-lg font-bold text-gray-900 mb-4">{t.products.specifications}</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-4">
                  {/* @ts-ignore */}
                  {Object.entries(currentSpecs).map(([key, value]) => (
                    <div key={key} className="flex flex-col border-b border-gray-100 pb-2">
                      <span className="text-sm text-gray-500 mb-1">{key}</span>
                      <span className="text-gray-900 font-medium">{value as React.ReactNode}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* CTA Section */}
              <div className="mt-10 pt-8 border-t border-gray-100">
                <button 
                  onClick={handleContactClick}
                  className="w-full md:w-auto px-8 py-4 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-bold text-lg shadow-lg hover:shadow-xl transition-all flex items-center justify-center gap-2"
                >
                  <MessageSquareText size={20} />
                  {t.products.inquire}
                </button>
                <p className="text-center md:text-left mt-3 text-sm text-gray-500">
                  {t.products.minimumOrder}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
