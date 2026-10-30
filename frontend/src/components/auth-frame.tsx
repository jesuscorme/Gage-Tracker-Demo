"use client";

import { useI18n } from "@/lib/i18n";

/** Split layout for sign-in / registration: brand panel + form. */
export function AuthFrame({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  const { t, lang, setLang } = useI18n();
  return (
    <div className="grid min-h-dvh lg:grid-cols-[minmax(380px,44%)_1fr]">
      <aside className="relative hidden overflow-hidden bg-rail p-10 text-rail-ink lg:flex lg:flex-col">
        <div className="flex items-center gap-2.5">
          <svg width="34" height="34" viewBox="0 0 32 32" aria-hidden>
            <rect width="32" height="32" rx="6" fill="#0b63c1" />
            <path d="M7 21a9 9 0 0118 0" stroke="#fff" strokeWidth="2" fill="none" />
            <path d="M16 21l5-6" stroke="#fff" strokeWidth="2" strokeLinecap="round" />
            <path d="M7 24h18" stroke="#7fb3ea" strokeWidth="2" />
          </svg>
          <span className="text-[16px] font-semibold tracking-wide text-white">{t("app.name")}</span>
        </div>
        <div className="mt-auto max-w-md">
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-rail-mute">{t("app.tagline")}</div>
          <p className="mt-3 text-2xl font-semibold leading-snug text-white">
            {lang === "es"
              ? "Control del ciclo de vida de instrumentos de medición, con trazabilidad completa."
              : "Lifecycle control of measuring equipment, with full traceability."}
          </p>
        </div>
        {/* Vernier-scale motif */}
        <svg className="absolute -right-6 bottom-28 opacity-[0.12]" width="420" height="80" viewBox="0 0 420 80" aria-hidden>
          {Array.from({ length: 43 }, (_, i) => (
            <line key={i} x1={i * 10} y1="0" x2={i * 10} y2={i % 10 === 0 ? 40 : i % 5 === 0 ? 28 : 18} stroke="#fff" strokeWidth="1.5" />
          ))}
          {Array.from({ length: 11 }, (_, i) => (
            <line key={`v${i}`} x1={60 + i * 9} y1="80" x2={60 + i * 9} y2={i % 5 === 0 ? 48 : 58} stroke="#7fb3ea" strokeWidth="1.5" />
          ))}
        </svg>
      </aside>

      <main className="flex flex-col px-4 py-8 sm:px-10">
        <div className="flex justify-end">
          <div className="flex rounded-md border border-line p-0.5 text-[11px] font-semibold">
            {(["es", "en"] as const).map((l) => (
              <button
                key={l}
                onClick={() => setLang(l)}
                aria-pressed={lang === l}
                className={`rounded px-2 py-1 uppercase ${lang === l ? "bg-ink text-white" : "text-ink-3"}`}
              >
                {l}
              </button>
            ))}
          </div>
        </div>
        <div className="mx-auto my-auto w-full max-w-[440px] py-8">
          <h1 className="text-2xl font-semibold">{title}</h1>
          <p className="mt-1 text-[13px] text-ink-3">{subtitle}</p>
          <div className="mt-7">{children}</div>
        </div>
      </main>
    </div>
  );
}
