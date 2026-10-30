"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, session } from "./api";
import { useI18n } from "./i18n";
import type { Me, Membership } from "./types";

interface Auth {
  ready: boolean;
  me: Me | null;
  membership: Membership | null;
  /** UI hint only: the backend enforces every permission again. */
  can: (permission: string) => boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (body: Record<string, string>) => Promise<void>;
  logout: () => void;
  switchOrganization: (orgId: string) => void;
}

const Ctx = createContext<Auth | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { setLang } = useI18n();
  const [ready, setReady] = useState(false);
  const [me, setMe] = useState<Me | null>(null);
  const [orgId, setOrgId] = useState<string | null>(null);

  const logout = useCallback(() => {
    session.setToken(null);
    session.setOrg(null);
    setMe(null);
    setOrgId(null);
  }, []);

  const loadMe = useCallback(async () => {
    const data = await api.get<Me>("/auth/me");
    const preferred = session.orgId;
    const chosen =
      data.memberships.find((m) => m.organization_id === preferred) ?? data.memberships[0] ?? null;
    session.setOrg(chosen?.organization_id ?? null);
    setOrgId(chosen?.organization_id ?? null);
    setMe(data);
    return data;
  }, []);

  useEffect(() => {
    session.load();
    session.onUnauthorized(logout);
    if (!session.token) {
      setReady(true);
      return;
    }
    loadMe()
      .catch(() => logout())
      .finally(() => setReady(true));
  }, [loadMe, logout]);

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await api.post<{ access_token: string }>("/auth/login", { email, password });
      session.setToken(res.access_token);
      const data = await loadMe();
      setLang(data.preferred_language);
    },
    [loadMe, setLang],
  );

  const register = useCallback(
    async (body: Record<string, string>) => {
      const res = await api.post<{ access_token: string }>("/auth/register", body);
      session.setToken(res.access_token);
      await loadMe();
    },
    [loadMe],
  );

  const switchOrganization = useCallback((id: string) => {
    session.setOrg(id);
    setOrgId(id);
  }, []);

  const membership = useMemo(
    () => me?.memberships.find((m) => m.organization_id === orgId) ?? null,
    [me, orgId],
  );
  const can = useCallback((p: string) => !!membership?.permissions.includes(p), [membership]);

  return (
    <Ctx.Provider value={{ ready, me, membership, can, login, register, logout, switchOrganization }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAuth(): Auth {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}
