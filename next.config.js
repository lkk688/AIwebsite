const { loadEnvConfig } = require('@next/env');
const path = require('path');

// Load env from backend directory
loadEnvConfig(path.join(process.cwd(), 'backend'));

/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:8000/api/:path*',
      },
    ];
  },
};

module.exports = nextConfig;

//website request to /api/chat/stream, will be redirect to 127.0.0.1:8000/api/chat/stream