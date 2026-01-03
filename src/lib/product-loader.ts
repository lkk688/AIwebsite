import type { Product } from "@/lib/types";
import { productFromJson, type ProductJson } from "@/lib/helpers";

// Dynamically load all product JSON files
// @ts-ignore
const context = require.context("../data/products", false, /\.json$/);
const all: ProductJson[] = context.keys().map((key: any) => context(key));

export const products: Product[] = all.map(productFromJson);
