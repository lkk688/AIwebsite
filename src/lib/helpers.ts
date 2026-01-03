//generate product image path and variant thumb

import type { Product } from "@/lib/types";

const PBASE = "/images/products";
type ImgSize = "thumb" | "sm" | "lg";

function mainImg(dir: string, idx: number, size: ImgSize) {
  const suffix = size === "thumb" ? "thumb" : size === "sm" ? "600" : "1600";
  return `${PBASE}/${dir}/${idx}_${suffix}.webp`;
}

function makeMedia(dir: string, slugForAlt: string, count: number) {
  const ids = Array.from({ length: count }, (_, i) => i + 1);
  const imagesBySize = {
    thumb: ids.map((i) => mainImg(dir, i, "thumb")),
    sm: ids.map((i) => mainImg(dir, i, "sm")),
    lg: ids.map((i) => mainImg(dir, i, "lg")),
  };
  return {
    images: ids.map((i) => ({
      id: i,
      url: mainImg(dir, i, "lg"),
      alt: `${slugForAlt} view ${i}`, // alt 仍用 slug（面向用户/SEO）
    })),
    imagesBySize,
    cover: {
      thumb: mainImg(dir, 1, "thumb"),
      sm: mainImg(dir, 1, "sm"),
      lg: mainImg(dir, 1, "lg"),
    },
  };
}

function variantThumb(dir: string, key: string) {
  return `${PBASE}/${dir}/variants/${key}_thumb.webp`;
}

function variantLarge(dir: string, key: string) {
  return `${PBASE}/${dir}/variants/${key}_1600.webp`;
}

export type ProductJson = {
  id: string;
  slug: string;
  assetDir?: string; // ✅ 新增：图片目录名（推荐 = id）
  mainCount: number;

  category: string;
  tags?: string[];
  name: { en: string; zh: string };
  description: { en: string; zh: string };
  materials?: { en: string[]; zh: string[] };
  specifications?: { en: Record<string, string>; zh: Record<string, string> };
  variants?: Array<{ key: string; sku?: string; en: string; zh: string }>;
};

export function productFromJson(j: ProductJson): Product {
  // ✅ 图片目录优先：assetDir -> id -> slug（兼容）
  const dir = j.assetDir ?? j.id ?? j.slug;

  return {
    id: j.id, // ✅ 系统唯一标识
    attributes: {
      name: j.name,
      slug: j.slug, // ✅ 面向用户（URL/SEO/页面路径）
      category: j.category as any,
      tags: j.tags ?? [],
      description: j.description,
      materials: j.materials ?? { en: [], zh: [] },
      specifications: j.specifications ?? { en: {}, zh: {} },

      ...makeMedia(dir, j.slug, j.mainCount),

      variants: (j.variants ?? []).map((v) => ({
        id: v.key,
        sku: v.sku ?? v.key,
        name: { en: v.en, zh: v.zh },
        image: variantThumb(dir, v.key),
        imageLarge: variantLarge(dir, v.key),
      })),
    } as any,
  };
}