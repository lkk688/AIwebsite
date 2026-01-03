// Local configuration file for API URL
// Users can edit this file to quickly update the server URL

export const config = {
  // Base URL for the backend API
  // Use the environment variable if available, otherwise fallback to relative path (uses Next.js proxy)
  ////This forces the frontend to use relative paths (e.g., /api/inquiry instead of http://localhost:8000/api/inquiry ), which leverages the Next.js proxy configured in next.config.js to reliably forward requests to the backend.
  
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000',

  // API Endpoints
  // Used in: 
  // - src/components/Contact.tsx (inquiry)
  // - src/components/ChatWidget.tsx (chatStream)
  // - src/components/products/ProductBrowser.tsx (productSearch)
  endpoints: {
    // Endpoint for submitting inquiries (contact form)
    inquiry: '/api/inquiry',
    
    // Endpoint for streaming chat responses
    chatStream: '/api/chat/stream',
    
    // Endpoint for standard chat responses (non-streaming)
    chat: '/api/chat',
    
    // Endpoint for product search
    productSearch: '/api/products/search',
    
    // Endpoint for sending emails (legacy/direct)
    sendEmail: '/api/send-email',
  },

  // Product Configuration
  // Used in: src/components/products/ProductBrowser.tsx
  products: {
    // Default search limit
    searchLimit: '50',
    
    // Image path patterns
    // {dir} will be replaced by the product directory name
    images: {
      basePath: '/images/products',
      patterns: {
        thumb: '{dir}/1_thumb.webp',
        sm: '{dir}/1_600.webp',
        lg: '{dir}/1_1600.webp',
      }
    }
  },

  // Language Configuration
  // Used in: src/components/Navbar.tsx
  languages: [
    { code: 'en', label: 'EN', name: 'English' },
    { code: 'zh', label: 'CN', name: '中文' },
  ],

  // Gallery Configuration
  // Used in: src/components/GridImageView.tsx, src/components/GalleryModal.tsx
  gallery: {
    itemsPerPage: 24, // 6x4 grid
    imagePattern: '/images/products/items/JWL{num}.jpg'
  }
};
