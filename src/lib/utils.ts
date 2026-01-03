// Helper to generate mock images
export const getMockImages = (base: string, count: number) => {
  return Array.from({ length: count }).map((_, i) => ({
    id: i,
    url: `${base}&random=${i}`,
    alt: 'Product detail view'
  }));
};
