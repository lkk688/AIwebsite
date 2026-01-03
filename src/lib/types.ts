export type Locale = 'en' | 'zh';

export interface LocalizedString {
  en: string;
  zh: string;
}

export interface LocalizedStringArray {
  en: string[];
  zh: string[];
}

export interface LocalizedRecord {
  en: Record<string, string>;
  zh: Record<string, string>;
}

// Product Types
export interface ProductImage {
  id: number;
  url: string;
  alt: string;
}

export interface ProductVariant {
  id: string;
  name: { en: string; zh: string };
  sku: string;
  image: string; // URL for the variant image (thumb)
  imageLarge?: string; // URL for the variant image (large)
}

export interface ProductAttributes {
  name: { en: string; zh: string };
  description: { en: string; zh: string };
  materials: { en: string[]; zh: string[] };
  specifications: { en: Record<string, string>; zh: Record<string, string> };
  images: ProductImage[];
  category: string;
  collections?: string[];
  tags?: string[];
  imagesBySize?: {
    thumb: string[];
    sm: string[];
    lg: string[];
  };
  cover?: {
    thumb: string;
    sm: string;
    lg: string;
  };
  variants?: ProductVariant[];
  slug: string;
  price?: string; // Optional, as B2B often doesn't show price
}

export interface Product {
  id: string;
  attributes: ProductAttributes;
}
