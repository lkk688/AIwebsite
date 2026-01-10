import certificationsData from '../data/certifications.json';
import productInfoData from '../data/productinfo.json';
import websiteInfoData from '../data/websiteinfo.json';

const certImages = certificationsData.reduce((acc, item) => {
  acc[item.key] = item.image;
  return acc;
}, {} as Record<string, string>);

const productCategoriesImages = productInfoData.categories.reduce((acc, item) => {
  acc[item.key] = item.image;
  return acc;
}, {} as Record<string, string>);

const productCollectionsImages = productInfoData.collections.reduce((acc, item) => {
  if (item.image) {
    acc[item.key] = item.image;
  }
  return acc;
}, {} as Record<string, string>);

export const images = {
  hero: {
    slide1: websiteInfoData.hero.slides.slide1.image,
    slide2: websiteInfoData.hero.slides.slide2.image,
    slide3: websiteInfoData.hero.slides.slide3.image,
    slide4: websiteInfoData.hero.slides.slide4.image,
  },
  about: {
    factory: websiteInfoData.about.image,
  },
  facility: {
    capacity: websiteInfoData.facility.features.capacity.images,
    machinery: websiteInfoData.facility.features.machinery.images,
    inspection: websiteInfoData.facility.features.inspection.images,
  },
  certifications: certImages,
  products: {
    categories: productCategoriesImages,
    collections: productCollectionsImages,
  },
} as const;
