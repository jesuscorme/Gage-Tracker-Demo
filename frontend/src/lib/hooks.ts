"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "./api";
import { useAuth } from "./auth";

export interface Resource<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  reload: () => void;
}

/** Loads data from the API and reloads when `deps` or the active organization change. */
export function useResource<T>(loader: () => Promise<T>, deps: unknown[] = []): Resource<T> {
  const { membership } = useAuth();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    loaderRef
      .current()
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e : new ApiError(0, "error", String(e))))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [membership?.organization_id, tick, ...deps]);

  const reload = useCallback(() => setTick((x) => x + 1), []);
  return { data, error, loading, reload };
}
