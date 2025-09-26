/**
 * Author: Claude Code using Sonnet 4
 * Date: 2025-09-26
 * PURPOSE: Central API configuration for handling development vs production URL differences
 * SRP and DRY check: Pass - Single responsibility for API URL configuration
 */

/**
 * Get the correct API base URL for the current environment
 * - Development: Use localhost:8080 (separate Next.js and FastAPI servers)
 * - Production: Use relative URLs (FastAPI serves both static files and API)
 */
export function getApiBaseUrl(): string {
  // In production (static export served by FastAPI), use relative paths
  // In development, use absolute URL to localhost:8080
  if (typeof window !== 'undefined') {
    // Client-side: check if we're in development or production
    const isDevelopment = process.env.NODE_ENV === 'development' ||
                         process.env.NEXT_PUBLIC_API_URL === 'http://localhost:8080';
    return isDevelopment ? 'http://localhost:8080' : '';
  } else {
    // Server-side: always use localhost for SSR/SSG
    return 'http://localhost:8080';
  }
}

/**
 * Create a full API URL for the given endpoint
 */
export function createApiUrl(endpoint: string): string {
  const baseUrl = getApiBaseUrl();
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  return `${baseUrl}${cleanEndpoint}`;
}