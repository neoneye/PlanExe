import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Enable static export for Railway single-service deployment
  output: 'export',

  // Required for static export
  trailingSlash: true,

  // Railway deployment: FastAPI serves both static files and API, no separate API URL needed
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || '',
    NEXT_PUBLIC_STREAMING_ENABLED:
      process.env.NEXT_PUBLIC_STREAMING_ENABLED ??
      process.env.STREAMING_ENABLED ??
      'true',
  },

  // Optimize for production deployment
  experimental: {
    optimizePackageImports: ['lucide-react'],
  },

  // Static export doesn't support rewrites - API calls will use relative paths in production
};

export default nextConfig;
