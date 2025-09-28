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
  const envUrl = (process.env.NEXT_PUBLIC_API_URL || '').trim();

  if (envUrl.length > 0) {
    return envUrl.replace(/\/$/, '');
  }

  const defaultDevUrl = 'http://localhost:8080';

  if (typeof window === 'undefined') {
    return process.env.NODE_ENV === 'development' ? defaultDevUrl : '';
  }

  const hostname = window.location.hostname;
  const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1';

  return isLocalhost ? defaultDevUrl : '';
}

/**
 * Create a full API URL for the given endpoint
 */
export function createApiUrl(endpoint: string): string {
  const baseUrl = getApiBaseUrl();
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  return `${baseUrl}${cleanEndpoint}`;
}