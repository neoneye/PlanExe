/**
 * Author: Codex using GPT-5
 * Date: 2024-06-08
 * PURPOSE: Central API configuration for handling development vs production URL differences
 *          and shared websocket URL construction so realtime clients avoid duplicating
 *          protocol/origin logic.
 * SRP and DRY check: Pass - Single responsibility for API URL configuration helpers shared
 *          across REST and websocket consumers.
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

  const { hostname, port, origin } = window.location;
  const normalizedHost = hostname.toLowerCase();
  const localHostnames = new Set(['localhost', '127.0.0.1', '::1', '0.0.0.0', 'localhost.localdomain']);
  const devPorts = new Set(['3000', '3001']);

  const shouldUseLocalBackend = localHostnames.has(normalizedHost) || devPorts.has(port);

  if (shouldUseLocalBackend) {
    try {
      const url = new URL(origin);
      url.port = '8080';
      url.pathname = '';
      url.search = '';
      url.hash = '';

      // Some environments expose the dev server as 0.0.0.0 which is not directly reachable.
      if (normalizedHost === '0.0.0.0') {
        url.hostname = 'localhost';
      }

      return url.origin;
    } catch (error) {
      const protocol = window.location.protocol || 'http:';
      const host = normalizedHost === '0.0.0.0' ? 'localhost' : hostname;
      return `${protocol}//${host}:8080`;
    }
  }

  return '';
}

/**
 * Create a full API URL for the given endpoint
 */
export function createApiUrl(endpoint: string): string {
  const baseUrl = getApiBaseUrl();
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  return `${baseUrl}${cleanEndpoint}`;
}

const websocketSegments = (planId: string, basePath: string): string => {
  const cleanedBase = basePath
    .replace(/^\/+/, '')
    .replace(/\/+$/, '')
    .trim();
  const segments = cleanedBase ? [cleanedBase, 'ws', 'plans', planId, 'progress'] : ['ws', 'plans', planId, 'progress'];
  return `/${segments.filter(Boolean).join('/')}`;
};

export function createWebSocketUrl(planId: string): string {
  const baseUrl = getApiBaseUrl().trim();
  const isAbsolute = /^https?:\/\//i.test(baseUrl);

  if (isAbsolute) {
    const url = new URL(baseUrl);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    url.pathname = websocketSegments(planId, url.pathname);
    url.search = '';
    url.hash = '';
    return url.toString().replace(/\/$/, '');
  }

  if (typeof window === 'undefined' || !window.location?.origin) {
    throw new Error('Unable to resolve WebSocket URL without window.location origin.');
  }

  const originUrl = new URL(window.location.origin);
  originUrl.protocol = originUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  originUrl.pathname = websocketSegments(planId, baseUrl);
  originUrl.search = '';
  originUrl.hash = '';
  return originUrl.toString().replace(/\/$/, '');
}
