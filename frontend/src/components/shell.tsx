"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import type { MessageKey } from "@/lib/messages";
import { Icon, type IconName } from "./icons";
import { NotificationBell } from "./notifications";
import { cx } from "./ui";

interface NavItem {
  href: string;
  label: MessageKey;
  icon: IconName;
  permission?: string;
  /** Module planned in a later phase: shown for orientation, not navigable. */
  soon?: boolean;
}

const NAV: { section: MessageKey; items: NavItem[] }[] = [
  {
    section: "nav.section.operations",
    items: [
      { href: "/dashboard", label: "nav.dashboard", icon: "dashboard", permission: "gages:read" },
      { href: "/gages", label: "nav.gages", icon: "gauge", permission: "gages:read" },
    ],
  },
  {
    section: "nav.section.metrology",
    items: [
      { href: "/calibrations", label: "nav.calibration", icon: "calibration", permission: "calibration:read" },
      { href: "/calibrations/calendar", label: "nav.calendar", icon: "calendar", permission: "calibration:read" },
      { href: "/standards", label: "nav.standards", icon: "standards", permission: "standards:read" },
      { href: "/competency", label: "nav.competency", icon: "people", permission: "competency:read" },
      { href: "/msa", label: "nav.msa", icon: "msa", permission: "msa:read" },
      { href: "/oot", label: "nav.oot", icon: "oot", permission: "oot:read" },
    ],
  },
  {
    section: "nav.section.laboratory",
    items: [
      { href: "/laboratory", label: "nav.labOverview", icon: "lab", permission: "lab:read" },
      { href: "/laboratory/requests", label: "nav.labRequests", icon: "inbox", permission: "lab:read" },
      { href: "/laboratory/schedule", label: "nav.labSchedule", icon: "board", permission: "lab:manage" },
      { href: "/laboratory/work-orders", label: "nav.labWorkOrders", icon: "wrench", permission: "lab:read" },
      { href: "/laboratory/reports", label: "nav.labReports", icon: "file", permission: "lab:read" },
    ],
  },
  {
    section: "nav.section.quality",
    items: [
      { href: "/compliance", label: "nav.compliance", icon: "audit", permission: "compliance:read" },
      { href: "/integrations", label: "nav.integrations", icon: "board", permission: "integrations:read" },
      { href: "/settings/configuration", label: "nav.configuration", icon: "gear", permission: "config:read" },
    ],
  },
  {
    section: "nav.section.admin",
    items: [
      { href: "/settings/gage-types", label: "nav.gageTypes", icon: "types", permission: "gages:read" },
      { href: "/settings/organization", label: "nav.organization", icon: "org", permission: "organization:read" },
      { href: "/settings/users", label: "nav.users", icon: "users", permission: "users:read" },
      { href: "/settings/technical", label: "nav.settings", icon: "gear", permission: "calibration:read" },
      { href: "/audit", label: "nav.audit", icon: "audit", permission: "audit:read" },
    ],
  },
];

function Brand() {
  const { t } = useI18n();
  return (
    <div className="flex items-center gap-2.5 px-4 py-4">
      <svg width="30" height="30" viewBox="0 0 32 32" aria-hidden>
        <rect width="32" height="32" rx="6" fill="#0b63c1" />
        <path d="M7 21a9 9 0 0118 0" stroke="#fff" strokeWidth="2" fill="none" />
        <path d="M16 21l5-6" stroke="#fff" strokeWidth="2" strokeLinecap="round" />
        <path d="M7 24h18" stroke="#7fb3ea" strokeWidth="2" />
      </svg>
      <div className="leading-tight">
        <div className="text-[14px] font-semibold tracking-wide text-white">{t("app.name")}</div>
        <div className="text-[10px] uppercase tracking-[0.14em] text-rail-mute">{t("app.tagline")}</div>
      </div>
    </div>
  );
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useI18n();
  const { can } = useAuth();
  const pathname = usePathname();
  // The most specific matching entry is the active one (/calibrations vs /calibrations/calendar).
  const activeHref = NAV.flatMap((s) => s.items)
    .filter((i) => !i.soon && (pathname === i.href || pathname.startsWith(`${i.href}/`)))
    .sort((a, b) => b.href.length - a.href.length)[0]?.href;

  return (
    <nav className="flex h-full flex-col bg-rail text-rail-ink" aria-label="Main">
      <Brand />
      <div className="flex-1 overflow-y-auto px-2 pb-4">
        {NAV.map(({ section, items }) => {
          const visible = items.filter((i) => i.soon || !i.permission || can(i.permission));
          if (!visible.length) return null;
          return (
            <div key={section} className="mt-4">
              <div className="px-3 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-rail-mute">
                {t(section)}
              </div>
              {visible.map((item) => {
                if (item.soon) {
                  return (
                    <div
                      key={item.href}
                      title={t("nav.soon")}
                      className="flex cursor-not-allowed items-center gap-2.5 rounded-md px-3 py-2 text-[13px] text-rail-mute/70"
                    >
                      <Icon name={item.icon} />
                      <span className="flex-1">{t(item.label)}</span>
                      <Icon name="lock" size={13} />
                    </div>
                  );
                }
                const active = item.href === activeHref;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    className={cx(
                      "relative flex items-center gap-2.5 rounded-md px-3 py-2 text-[13px] transition-colors",
                      active ? "bg-rail-2 text-white" : "hover:bg-rail-2/60 hover:text-white",
                    )}
                  >
                    {active && <span className="absolute inset-y-1.5 left-0 w-[3px] rounded-r bg-accent" />}
                    <Icon name={item.icon} />
                    {t(item.label)}
                  </Link>
                );
              })}
            </div>
          );
        })}
      </div>
    </nav>
  );
}

function LanguageSwitch() {
  const { lang, setLang, t } = useI18n();
  return (
    <div role="group" aria-label={t("header.language")} className="flex rounded-md border border-line p-0.5 text-[11px] font-semibold">
      {(["es", "en"] as const).map((l) => (
        <button
          key={l}
          onClick={() => setLang(l)}
          aria-pressed={lang === l}
          className={cx("rounded px-2 py-1 uppercase", lang === l ? "bg-ink text-white" : "text-ink-3 hover:text-ink")}
        >
          {l}
        </button>
      ))}
    </div>
  );
}

function Header({ onMenu }: { onMenu: () => void }) {
  const { t } = useI18n();
  const { me, membership, switchOrganization, logout } = useAuth();
  if (!me || !membership) return null;
  const plants = membership.plants.length ? membership.plants.map((p) => p.code).join(", ") : t("header.allPlants");
  const initials = me.full_name.split(/\s+/).map((s) => s[0]).slice(0, 2).join("").toUpperCase();

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-line bg-surface/95 px-4 backdrop-blur">
      <button onClick={onMenu} className="rounded-md p-1.5 text-ink-2 hover:bg-line-2 lg:hidden" aria-label="Menu">
        <Icon name="menu" />
      </button>

      <div className="flex min-w-0 items-center gap-2">
        <span className="hidden text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-3 sm:inline">
          {t("header.organization")}
        </span>
        {me.memberships.length > 1 ? (
          <select
            value={membership.organization_id}
            onChange={(e) => switchOrganization(e.target.value)}
            className="h-8 max-w-[200px] truncate rounded-md border border-line bg-surface px-2 text-[13px] font-medium"
          >
            {me.memberships.map((m) => (
              <option key={m.organization_id} value={m.organization_id}>
                {m.organization_name}
              </option>
            ))}
          </select>
        ) : (
          <span className="truncate text-[13px] font-semibold">{membership.organization_name}</span>
        )}
        <span className="hidden truncate rounded bg-line-2 px-2 py-0.5 font-mono text-[11px] text-ink-2 md:inline">
          {plants}
        </span>
      </div>

      <div className="ml-auto flex items-center gap-3">
        <NotificationBell />
        <LanguageSwitch />
        <div className="hidden text-right leading-tight sm:block">
          <div className="text-[13px] font-medium">{me.full_name}</div>
          <div className="text-[11px] text-ink-3">{membership.role_name}</div>
        </div>
        <span className="grid size-8 place-items-center rounded-full bg-ink text-[11px] font-semibold text-white">
          {initials}
        </span>
        <button onClick={logout} title={t("header.logout")} aria-label={t("header.logout")} className="rounded-md p-1.5 text-ink-3 hover:bg-line-2 hover:text-ink">
          <Icon name="logout" />
        </button>
      </div>
    </header>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  useEffect(() => setOpen(false), [pathname]);

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[240px_1fr]">
      <div className="hidden bg-rail lg:block">
        <aside className="sticky top-0 h-dvh">
          <Sidebar />
        </aside>
      </div>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button className="absolute inset-0 bg-ink/50" aria-label="Close menu" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-[260px] shadow-xl">
            <Sidebar onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      )}
      <div className="flex min-w-0 flex-col">
        <Header onMenu={() => setOpen(true)} />
        <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 sm:px-6">{children}</main>
      </div>
    </div>
  );
}
