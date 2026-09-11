const TOKEN_KEY = "ithotline_admin_token";

function isNgrokHostname(hostname: string): boolean {
  return (
    hostname.includes("ngrok-free.app") ||
    hostname.includes("ngrok.io") ||
    hostname.endsWith(".ngrok.app")
  );
}

function resolveApiBaseUrl(): string {
  const explicit = import.meta.env.VITE_API_URL?.replace(/\/$/, "");
  if (explicit) return explicit;

  if (typeof window !== "undefined") {
    const { hostname, protocol, host } = window.location;
    if (isNgrokHostname(hostname)) {
      const ngrokApi = import.meta.env.VITE_NGROK_API_URL?.replace(/\/$/, "");
      if (ngrokApi) return ngrokApi;
      return `${protocol}//${host}`;
    }
  }

  return "http://127.0.0.1:5001";
}

export const API_BASE_URL = resolveApiBaseUrl();

export function usesNgrokApi(): boolean {
  return API_BASE_URL.includes("ngrok");
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

type ApiFetchOptions = RequestInit & {
  auth?: boolean;
};

export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const { auth = true, ...init } = options;
  const headers = new Headers(init.headers);

  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (usesNgrokApi()) {
    headers.set("ngrok-skip-browser-warning", "true");
  }

  if (auth) {
    const token = getToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  });

  let data: unknown = null;
  const text = await response.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { error: text };
    }
  }

  if (response.status === 401 && auth) {
    clearToken();
  }

  if (!response.ok) {
    const message =
      typeof data === "object" && data !== null && "error" in data
        ? String((data as { error: unknown }).error)
        : response.statusText || "Request failed";
    throw new ApiError(message, response.status);
  }

  return data as T;
}
