"use client";

import { useMemo } from "react";
import { api } from "./api";
import { useAuth } from "./auth";
import { useResource } from "./hooks";
import type { Gage, OrgUser, Page, Plant } from "./types";

export function useUsers() {
  const { can } = useAuth();
  const res = useResource(() => (can("users:read") ? api.get<OrgUser[]>("/users") : Promise.resolve([] as OrgUser[])), []);
  const names = useMemo(() => Object.fromEntries((res.data ?? []).map((u) => [u.id, u.full_name])), [res.data]);
  return { list: (res.data ?? []).filter((u) => u.is_active && !u.email.endsWith("@service.invalid")), names };
}

export function useGages() {
  const res = useResource(() => api.get<Page<Gage>>("/gages", { page_size: 200 }), []);
  return res.data?.items ?? [];
}

export function usePlants() {
  return useResource(() => api.get<Plant[]>("/plants"), []).data ?? [];
}

/** "a, b , c" -> ["a","b","c"] */
export const csv = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

/** Number or undefined from an input string ("," accepted as decimal mark). */
export const num = (s: string) => (s.trim() === "" ? undefined : Number(s.replace(",", ".")));
