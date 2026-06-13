const API_KEY_STORAGE = "videodownload_api_key";
const DEFAULT_TIMEOUT_MS = 15_000;
const DEFAULT_BACKEND_PORT = import.meta.env.VITE_BACKEND_PORT || "8200";

function isLocalHostname(hostname: string): boolean {
  return hostname === "localhost" || hostname === "127.0.0.1";
}

export function getApiHostForLocation(hostname: string, port: string): string {
  if (isLocalHostname(hostname)) {
    if (port === "5173") return ""; // Vite dev proxy
    if (port === DEFAULT_BACKEND_PORT) return "";
    return `http://127.0.0.1:${DEFAULT_BACKEND_PORT}`;
  }
  return "";
}

export function getWebSocketHostForLocation(hostname: string, port: string, host: string): string {
  if (!isLocalHostname(hostname)) return host;
  return port === "5173" ? "localhost:5173" : `localhost:${DEFAULT_BACKEND_PORT}`;
}

export function getApiHost(): string {
  if (typeof window === "undefined") return "";
  const { hostname, port } = window.location;
  return getApiHostForLocation(hostname, port);
}

export function getStoredApiKey(): string {
  if (typeof window === "undefined") return "";
  return (
    localStorage.getItem(API_KEY_STORAGE) ||
    import.meta.env.VITE_API_KEY ||
    ""
  ).trim();
}

export function setStoredApiKey(key: string): void {
  const trimmed = key.trim();
  if (trimmed) {
    localStorage.setItem(API_KEY_STORAGE, trimmed);
  } else {
    localStorage.removeItem(API_KEY_STORAGE);
  }
}

export function buildApiHeaders(extra?: HeadersInit): Headers {
  const headers = new Headers(extra);
  const key = getStoredApiKey();
  if (key && !headers.has("X-API-Key")) {
    headers.set("X-API-Key", key);
  }
  return headers;
}

export function resolveApiUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  const host = getApiHost();
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return host ? `${host}${normalized}` : normalized;
}

export function buildWebSocketUrl(path = "/ws"): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = getWebSocketHostForLocation(
    window.location.hostname,
    window.location.port,
    window.location.host,
  );
  const key = getStoredApiKey();
  const qs = key ? `?api_key=${encodeURIComponent(key)}` : "";
  return `${protocol}//${host}${path}${qs}`;
}

export interface ApiFetchOptions extends RequestInit {
  timeoutMs?: number;
}

export async function apiFetch(
  path: string,
  init?: ApiFetchOptions,
): Promise<Response> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, ...fetchInit } = init ?? {};
  const headers = buildApiHeaders(fetchInit.headers);
  const signal = fetchInit.signal
    ? fetchInit.signal
    : AbortSignal.timeout(timeoutMs);
  return fetch(resolveApiUrl(path), { ...fetchInit, headers, signal });
}

export async function parseApiError(res: Response, fallback = "Greška na serveru"): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail)) {
      return data.detail.map((d: { msg?: string }) => d.msg || String(d)).join("; ");
    }
    if (typeof data?.message === "string") return data.message;
    if (typeof data?.error === "string") return data.error;
  } catch {
    /* ignore */
  }
  return fallback;
}
