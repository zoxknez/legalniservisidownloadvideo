const API_KEY_STORAGE = "videodownload_api_key";

export function getApiHost(): string {
  if (typeof window === "undefined") return "";
  const { hostname, port } = window.location;
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    if (port === "5173") return ""; // Vite dev proxy
    if (port === "8000") return "";
    return "http://127.0.0.1:8000";
  }
  return "";
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

/** Resolve path to full URL (respects dev proxy and production same-origin). */
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
  const host =
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1"
      ? window.location.port === "5173"
        ? "localhost:5173"
        : "localhost:8000"
      : window.location.host;
  const key = getStoredApiKey();
  const qs = key ? `?api_key=${encodeURIComponent(key)}` : "";
  return `${protocol}//${host}${path}${qs}`;
}

export async function apiFetch(
  path: string,
  init?: RequestInit
): Promise<Response> {
  const headers = buildApiHeaders(init?.headers);
  return fetch(resolveApiUrl(path), { ...init, headers });
}
