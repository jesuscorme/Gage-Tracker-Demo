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

function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (orgId) headers["X-Organization-Id"] = orgId;
  return headers;
}

async function send(method: string, path: string, body: BodyInit | undefined, extra: Record<string, string>, query?: Query) {
  try {
    return await fetch(`/api/v1${path}${qs(query)}`, { method, headers: { ...authHeaders(), ...extra }, body });
  } catch {
    throw new ApiError(0, "network_error", "Network error");
  }
}

async function failure(res: Response): Promise<ApiError> {
  const data = await res.json().catch(() => null);
  const err = data?.error ?? {};
  if (res.status === 401 && token) onUnauthorized?.();
  return new ApiError(res.status, err.code ?? "http_error", err.message ?? res.statusText, err.details);
}

async function request<T>(method: string, path: string, body?: unknown, query?: Query): Promise<T> {
  const extra: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined && !(body instanceof FormData)) extra["Content-Type"] = "application/json";
  const payload = body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body);
  const res = await send(method, path, payload, extra, query);

  if (!res.ok) throw await failure(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Fetch a protected file and hand it to the browser (open inline or save). */
async function download(path: string, query?: Query, opts: { open?: boolean; filename?: string } = {}) {
  const res = await send("GET", path, undefined, {}, query);
  if (!res.ok) throw await failure(res);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const cd = res.headers.get("Content-Disposition") ?? "";
  const name = opts.filename ?? decodeURIComponent(/filename\*=UTF-8''([^;]+)/.exec(cd)?.[1] ?? /filename="([^"]+)"/.exec(cd)?.[1] ?? "file");
  if (opts.open) {
    window.open(url, "_blank", "noopener");
  } else {
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
  }
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export const api = {
  get: <T>(path: string, query?: Query) => request<T>("GET", path, undefined, query),
  post: <T>(path: string, body?: unknown, query?: Query) => request<T>("POST", path, body ?? {}, query),
  patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, body),
  put: <T>(path: string, body: unknown) => request<T>("PUT", path, body),
  download,
};

export function form(fields: Record<string, string | Blob | null | undefined>): FormData {
  const fd = new FormData();
  for (const [k, v] of Object.entries(fields)) if (v !== null && v !== undefined && v !== "") fd.append(k, v);
  return fd;
}
