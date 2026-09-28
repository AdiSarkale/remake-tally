// Fetch client for the Minitally FastAPI backend.
// Base URL: VITE_API_URL env var, defaulting to the local backend on :8000.

const BASE_URL = (import.meta.env["VITE_API_URL"] as string | undefined) ?? "http://localhost:8000";
const TOKEN_KEY = "minitally.token";
const PROFILE_KEY = "minitally.profile";

export interface StoredProfile {
  full_name: string;
  role: string;
  username: string;
  company_id: string;
  company_code: string;
  company_name: string;
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function getStoredProfile(): StoredProfile | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(PROFILE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredProfile;
  } catch {
    return null;
  }
}

export function storeSession(token: string, profile: StoredProfile) {
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
}

export function clearSession() {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(PROFILE_KEY);
}

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}/api/v1${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : null,
    });
  } catch {
    throw new ApiError(0, `Cannot reach the Minitally API at ${BASE_URL}. Is the backend running?`);
  }

  if (res.status === 401) {
    clearSession();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
    throw new ApiError(401, "Session expired. Please sign in again.");
  }

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data?.detail === "string") detail = data.detail;
      else if (Array.isArray(data?.detail)) detail = data.detail.map((d: { msg?: string }) => d.msg).join(", ");
    } catch {
      // keep default
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  delete: <T>(path: string) => request<T>("DELETE", path),
};

export { BASE_URL };


export async function apiFetch<T = unknown>(
  path: string,
  init: { method?: string; body?: string } = {},
): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const body = init.body ? JSON.parse(init.body) : undefined;
  if (method === "GET") return api.get<T>(path);
  if (method === "POST") return api.post<T>(path, body);
  if (method === "PUT") return api.put<T>(path, body);
  if (method === "PATCH") return api.patch<T>(path, body);
  if (method === "DELETE") return api.delete<T>(path);
  throw new Error(`Unsupported HTTP method: ${method}`);
}
