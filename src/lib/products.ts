import { products } from './products-data';
import { Locale, Product, ProductImage, ProductAttributes } from './types';

export type { Locale, Product, ProductImage, ProductAttributes };

export interface StrapiResponse<T> {
  data: T;
  meta: {
    pagination: {
      page: number;
      pageSize: number;
      pageCount: number;
      total: number;
    }
  }
}

// Service Logic
export const getProductsByCategory = async (category: string): Promise<Product[]> => {
  // Simulate network delay
  await new Promise(resolve => setTimeout(resolve, 100));
  return products.filter(p => p.attributes.category === category);
};

export const getProductById = async (id: string): Promise<Product | undefined> => {
  await new Promise(resolve => setTimeout(resolve, 100));
  return products.find(p => p.id === id);
};

export const getAllProducts = async (): Promise<Product[]> => {
  await new Promise(resolve => setTimeout(resolve, 100));
  return products;
};
