'use client';
import React, { useState, useEffect, useMemo } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { Product } from '@/lib/types';
import ProductCard from '@/components/products/ProductCard';
import { Search, X } from 'lucide-react';
import { getAllProducts } from '@/lib/products';
import { config } from '@/config';

interface ProductBrowserProps {
  initialCategory?: string;
}

export default function ProductBrowser({ initialCategory }: ProductBrowserProps) {
  const { t } = useLanguage();
  const [products, setProducts] = useState<Product[]>([]);
  const [allData, setAllData] = useState<Product[]>([]); // Store all products for suggestions
  const [loading, setLoading] = useState(true);
  
  // Filter states
  const [selectedCategory, setSelectedCategory] = useState<string>(initialCategory || 'all');
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  
  // Suggestion states
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);

  // Fetch all products on mount
  useEffect(() => {
    const init = async () => {
      setLoading(true);
      const all = await getAllProducts();
      setProducts(all);
      setAllData(all);
      setLoading(false);
    };
    init();
  }, []);

  // Update selected category if initialCategory changes (e.g. navigation)
  useEffect(() => {
    if (initialCategory) {
      setSelectedCategory(initialCategory);
    }
  }, [initialCategory]);

  const [showAllTags, setShowAllTags] = useState(false);

  // Derived data for filters (based on all data to persist filters even when no results)
  const categories = useMemo(() => {
    const cats = new Set(allData.map(p => p.attributes.category));
    return Array.from(cats);
  }, [allData]);

  const allTags = useMemo(() => {
    const tags = new Set<string>();
    allData.forEach(p => {
      const pTags = p.attributes.tags || p.attributes.collections || [];
      pTags.forEach(tag => tags.add(tag));
    });
    return Array.from(tags);
  }, [allData]);

  const visibleTags = showAllTags ? allTags : allTags.slice(0, 10);

  // Helper to convert kebab-case to camelCase for translation lookup
  const toCamelCase = (str: string) => {
    return str.replace(/-([a-z])/g, (g) => g[1].toUpperCase());
  };

  const filteredProducts = useMemo(() => {
    return products.filter((product) => {
      // 1. Category Filter
      if (selectedCategory !== 'all' && product.attributes.category !== selectedCategory) {
        return false;
      }

      // 2. Tags Filter (match ANY selected tag)
      if (selectedTags.length > 0) {
        const productTags = (product.attributes.tags || product.attributes.collections || []).map(t => t.toLowerCase());
        const hasTag = selectedTags.some(tag => productTags.includes(tag.toLowerCase()));
        if (!hasTag) return false;
      }

      return true;
    });
  }, [products, selectedCategory, selectedTags]);

  // Perform API Search
  const performSearch = async (query: string) => {
      setLoading(true);
      try {
        let fetchedProducts: Product[] = [];
        if (query.trim()) {
           // Use Search API
           const params = new URLSearchParams({
             q: query,
             // @ts-ignore
             locale: t.nav?.home === '首页' ? 'zh' : 'en',
             limit: config.products.searchLimit
           });
           const res = await fetch(`${config.apiBaseUrl}${config.endpoints.productSearch}?${params.toString()}`);
           if (res.ok) {
             const data = await res.json();
             const results = data.results || data;
             
             // Transform API result to Product type
             fetchedProducts = Array.isArray(results) ? results.map((item: any) => {
                // If it already looks like a Product (has attributes), return it
                if (item.attributes) return item as Product;

                const dir = item.assetDir || item.id || item.slug;
                // API doesn't return mainCount, default to 1 so at least cover image works
                const mainCount = 1; 

                // Helper to get image URL from pattern
                const getImg = (pattern: string) => pattern.replace('{dir}', dir);

                // Construct images (simple approximation)
                const images = [{
                    id: 1,
                    url: getImg(config.products.images.patterns.lg),
                    alt: item.name
                }];

                return {
                    id: item.id,
                    attributes: {
                        name: { en: item.name, zh: item.name }, // Use same string for both as fallback
                        description: { en: item.description, zh: item.description },
                        category: item.category,
                        slug: item.slug,
                        tags: item.tags || [],
                        collections: item.tags || [],
                        materials: { en: [], zh: [] },
                        specifications: { en: {}, zh: {} },
                        images: images,
                        imagesBySize: {
                            thumb: [getImg(config.products.images.patterns.thumb)],
                            sm: [getImg(config.products.images.patterns.sm)],
                            lg: [getImg(config.products.images.patterns.lg)]
                        },
                        cover: {
                             thumb: getImg(config.products.images.patterns.thumb),
                             sm: getImg(config.products.images.patterns.sm),
                             lg: getImg(config.products.images.patterns.lg)
                        }
                    }
                } as Product;
             }) : [];
           }
        } else {
           // Load all products locally if no search
           fetchedProducts = await getAllProducts();
        }
        setProducts(fetchedProducts);
      } catch (error) {
        console.error("Error fetching products:", error);
        // Fallback to local
        setProducts(await getAllProducts());
      } finally {
        setLoading(false);
      }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = e.target.value;
      setSearchQuery(val);
      
      if (!val.trim()) {
          setSuggestions([]);
          setShowSuggestions(false);
          // Optional: Reset to all products when cleared? 
          // performSearch(''); 
          return;
      }

      // Generate suggestions from allData
      const lowerQ = val.toLowerCase();
      const uniqueCats = new Set(allData.map(p => p.attributes.category));
      const uniqueTags = new Set<string>();
      allData.forEach(p => {
           const pTags = p.attributes.tags || p.attributes.collections || [];
           pTags.forEach(t => uniqueTags.add(t));
      });

      const matchedCats = Array.from(uniqueCats).filter(c => c.toLowerCase().includes(lowerQ));
      const matchedTags = Array.from(uniqueTags).filter(t => t.toLowerCase().includes(lowerQ));

      const combined = [...matchedCats, ...matchedTags].slice(0, 8); // Limit to 8 suggestions
      setSuggestions(combined);
      setShowSuggestions(combined.length > 0);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
          setShowSuggestions(false);
          performSearch(searchQuery);
      }
  };

  const handleSuggestionClick = (suggestion: string) => {
      setSearchQuery(suggestion);
      setShowSuggestions(false);
      performSearch(suggestion);
  };

  const toggleTag = (tag: string) => {
    setSelectedTags(prev => 
      prev.includes(tag) 
        ? prev.filter(t => t !== tag) 
        : [...prev, tag]
    );
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Search Bar */}
      <div className="relative max-w-2xl mx-auto z-20">
        <input
          type="text"
          placeholder={t.products.searchPlaceholder || "Search products..."} 
          value={searchQuery}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onFocus={() => searchQuery && suggestions.length > 0 && setShowSuggestions(true)}
          // Delay blur to allow click on suggestion
          onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
          className="w-full pl-12 pr-4 py-4 rounded-full border border-gray-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition-all shadow-sm text-lg"
        />
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" size={24} />
        {searchQuery && (
          <button 
            onClick={() => {
                setSearchQuery('');
                setSuggestions([]);
                setShowSuggestions(false);
                performSearch('');
            }}
            className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
          >
            <X size={20} />
          </button>
        )}

        {/* Suggestions Dropdown */}
        {showSuggestions && suggestions.length > 0 && (
            <div className="absolute top-full left-0 right-0 mt-2 bg-white rounded-xl shadow-xl border border-gray-100 overflow-hidden z-30">
                <ul>
                    {suggestions.map((item, idx) => (
                        <li key={idx}>
                            <button
                                onClick={() => handleSuggestionClick(item)}
                                className="w-full text-left px-6 py-3 hover:bg-gray-50 text-gray-700 hover:text-blue-600 transition-colors flex items-center gap-2"
                            >
                                <Search size={16} className="text-gray-400" />
                                {item}
                            </button>
                        </li>
                    ))}
                </ul>
            </div>
        )}
      </div>

      {/* Filters Container */}
      <div className="flex flex-col gap-6">
        {/* Categories */}
        <div className="flex flex-wrap gap-2 justify-center">
          <button
            onClick={() => {
                setSelectedCategory('all');
                setSearchQuery(''); // Clear search
                setProducts(allData); // Reset to all products
            }}
            className={`px-6 py-2 rounded-full text-sm font-bold transition-all ${
              selectedCategory === 'all'
                ? 'bg-blue-600 text-white shadow-md'
                : 'bg-white text-gray-600 hover:bg-gray-100 border border-gray-200'
            }`}
          >
            ALL
          </button>
          {categories.map(cat => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-6 py-2 rounded-full text-sm font-bold uppercase transition-all ${
                selectedCategory === cat
                  ? 'bg-blue-600 text-white shadow-md'
                  : 'bg-white text-gray-600 hover:bg-gray-100 border border-gray-200'
              }`}
            >
              {/* @ts-ignore */}
              {t.products.categories[cat] || cat}
            </button>
          ))}
        </div>

        {/* Tags */}
        {allTags.length > 0 && (
          <div className="flex flex-col items-center gap-4 max-w-4xl mx-auto">
            <div className="flex flex-wrap gap-2 justify-center">
              {visibleTags.map(tag => {
                 // Adaptive translation lookup
                 // @ts-ignore
                 const tagName = t.products.collections?.[tag] || t.products.collections?.[tag.toLowerCase()] || t.products.collections?.[toCamelCase(tag)] || tag;
                 
                 return (
                  <button
                    key={tag}
                    onClick={() => toggleTag(tag)}
                    className={`px-4 py-1.5 rounded-full text-xs font-medium transition-all border ${
                      selectedTags.includes(tag)
                        ? 'bg-gray-800 text-white border-gray-800'
                        : 'bg-white text-gray-600 border-gray-200 hover:border-gray-400'
                    }`}
                  >
                    {tagName}
                  </button>
                );
              })}
            </div>
            
            {allTags.length > 10 && (
              <button
                onClick={() => setShowAllTags(!showAllTags)}
                className="text-sm text-blue-600 hover:text-blue-800 font-medium underline-offset-4 hover:underline transition-all"
              >
                {showAllTags ? (t.products.showLess || 'Show Less') : (t.products.showMore || 'Show More')}
              </button>
            )}
          </div>
        )}
      </div>

      {/* Results Grid */}
      {filteredProducts.length === 0 ? (
        <div className="text-center py-20 text-gray-500">
          <p className="text-xl font-medium">{t.products.notFound || "No products found"}</p>
          <p className="mt-2">Try adjusting your filters or search query</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {filteredProducts.map((product) => (
            <ProductCard key={product.id} product={product} category={product.attributes.category} />
          ))}
        </div>
      )}
    </div>
  );
}
