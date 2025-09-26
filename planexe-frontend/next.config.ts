import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Enable static export for Railway single-service deployment
  output: 'export',

  // Required for static export
  trailingSlash: true,

  // Environment variables for Railway deployment
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080',
  },

  // Optimize for production deployment
  experimental: {
    optimizePackageImports: ['lucide-react'],
  },

  // Static export doesn't support rewrites - API calls will use relative paths in production
};

export default nextConfig;
