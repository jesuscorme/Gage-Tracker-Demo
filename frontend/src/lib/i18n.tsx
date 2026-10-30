"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { en, es, format, type MessageKey } from "./messages";
import { enB3, esB3 } from "./messages-b3";
import { enModules, esModules } from "./messages-modules";

export type Lang = "es" | "en";
const DICTS: Record<Lang, Record<MessageKey, string>> = {
  es: { ...es, ...esModules, ...esB3 },
  en: { ...en, ...enModules, ...enB3 },
};
const KEY = "gt.lang";

interface I18n {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: MessageKey, vars?: Record<string, string | number>) => string;
  fmtDate: (iso: string | null | undefined) => string;
  fmtDateTime: (iso: string | null | undefined) => string;
}

const Ctx = createContext<I18n | null>(null);

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("es");

  useEffect(() => {
    try {
      const saved = localStorage.getItem(KEY);
      if (saved === "es" || saved === "en") setLangState(saved);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem(KEY, l);
    } catch {
      /* ignore */
    }
  }, []);

  const t = useCallback(
    (key: MessageKey, vars?: Record<string, string | number>) => format(DICTS[lang][key] ?? key, vars),
    [lang],
  );

  const locale = lang === "es" ? "es-MX" : "en-US";
  // Dates without time are calendar dates: format them without time-zone shifting.
  const fmtDate = useCallback(
    (iso: string | null | undefined) => {
      if (!iso) return "—";
      const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
      return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString(locale, {
        timeZone: "UTC",
        year: "numeric",
        month: "short",
        day: "2-digit",
      });
    },
    [locale],
  );
  const fmtDateTime = useCallback(
    (iso: string | null | undefined) =>
      iso ? new Date(iso).toLocaleString(locale, { dateStyle: "medium", timeStyle: "short" }) : "—",
    [locale],
  );

  return <Ctx.Provider value={{ lang, setLang, t, fmtDate, fmtDateTime }}>{children}</Ctx.Provider>;
}

export function useI18n(): I18n {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useI18n outside I18nProvider");
  return ctx;
}
