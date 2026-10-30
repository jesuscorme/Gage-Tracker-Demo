// Thin fetch wrapper. Requests go to the same origin (/api/...) and Next.js proxies them
// to the FastAPI backend, so no CORS is involved in the browser.

const TOKEN_KEY = "gt.token";
const ORG_KEY = "gt.org";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
  }
}

function read(key: string): string | null {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null) {
  try {
    if (value === null) sessionStorage.removeItem(key);
    else sessionStorage.setItem(key, value);
  } catch {
    /* storage unavailable: session lasts until reload */
  }
}

let token: string | null = null;
let orgId: string | null = null;
let onUnauthorized: (() => void) | null = null;

export const session = {
  load() {
    token = read(TOKEN_KEY);
    orgId = read(ORG_KEY);
  },
  get token() {
    return token;
  },
  get orgId() {
    return orgId;
  },
  setToken(value: string | null) {
    token = value;
    write(TOKEN_KEY, value);
  },
  setOrg(value: string | null) {
    orgId = value;
    write(ORG_KEY, value);
  },
  onUnauthorized(cb: () => void) {
    onUnauthorized = cb;
  },
};

type Query = Record<string, string | number | boolean | string[] | null | undefined>;

function qs(query?: Query): string {
  if (!query) return "";
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === null || v === "") continue;
    if (Array.isArray(v)) v.forEach((x) => p.append(k, x));
    else p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

async function request<T>(method: string, path: string, body?: unknown, query?: Query): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  if (orgId) headers["X-Organization-Id"] = orgId;

  let res: Response;
  try {
    res = await fetch(`/api/v1${path}${qs(query)}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "network_error", "Network error");
  }

  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const err = data?.error ?? {};
    if (res.status === 401 && token) onUnauthorized?.();
    throw new ApiError(res.status, err.code ?? "http_error", err.message ?? res.statusText, err.details);
  }
  return data as T;
}

export const api = {
  get: <T>(path: string, query?: Query) => request<T>("GET", path, undefined, query),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, body),
};
