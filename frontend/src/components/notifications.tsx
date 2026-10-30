"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import type { MessageKey } from "@/lib/messages";
import type { NotificationT } from "@/lib/types";
import { Icon } from "./icons";
import { cx } from "./ui";

const ALERT_LINKS: Record<string, string> = {
  gages_overdue: "/gages?status=OVERDUE",
  gages_due_soon: "/gages?status=DUE_SOON",
  standards_expired: "/standards",
  standards_expiring: "/standards",
  authorizations_expiring: "/competency",
  competency_records_expiring: "/competency",
  work_orders_overdue: "/laboratory/work-orders",
};
const BAD = new Set(["gages_overdue", "standards_expired", "work_orders_overdue"]);

/** Header bell: live alert counters + in-app notifications. */
export function NotificationBell() {
  const { t, fmtDateTime } = useI18n();
  const { membership } = useAuth();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [tick, setTick] = useState(0);
  const ref = useRef<HTMLDivElement>(null);
  const notes = useResource(() => api.get<{ unread: number; items: NotificationT[] }>("/notifications"), [tick, pathname]);
  const alerts = useResource(() => api.get<Record<string, number | string>>("/alerts"), [tick, pathname]);

  useEffect(() => {
    const id = setInterval(() => setTick((x) => x + 1), 60_000);
    return () => clearInterval(id);
  }, []);
  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    const onDoc = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  if (!membership) return null;
  const alertRows = Object.entries(alerts.data ?? {}).filter(([k, v]) => k !== "as_of" && typeof v === "number" && v > 0);
  const unread = notes.data?.unread ?? 0;
  const badge = unread + alertRows.filter(([k]) => BAD.has(k)).length;

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label={t("common.notifications")}
        className="relative rounded-md p-1.5 text-ink-2 hover:bg-line-2"
      >
        <Icon name="bell" />
        {badge > 0 && (
          <span className="absolute -right-0.5 -top-0.5 grid min-w-4 place-items-center rounded-full bg-bad px-1 text-[10px] font-semibold text-white">
            {badge > 99 ? "99+" : badge}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-10 z-30 w-[min(360px,calc(100vw-32px))] overflow-hidden rounded-lg border border-line bg-surface shadow-xl">
          {alertRows.length > 0 && (
            <div className="border-b border-line p-2">
              <div className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-3">{t("common.alerts")}</div>
              {alertRows.map(([k, v]) => (
                <Link key={k} href={ALERT_LINKS[k] ?? "/dashboard"} className="flex items-center justify-between rounded px-2 py-1.5 text-[13px] hover:bg-line-2">
                  <span className="flex items-center gap-2">
                    <span className={cx("size-2 rounded-[2px]", BAD.has(k) ? "bg-bad" : "bg-warn")} />
                    {t(`alert.${k}` as MessageKey)}
                  </span>
                  <span className="tabular font-semibold">{v}</span>
                </Link>
              ))}
            </div>
          )}
          <div className="flex items-center justify-between px-4 py-2">
            <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-3">{t("common.notifications")}</span>
            {unread > 0 && (
              <button
                className="text-[12px] text-accent hover:underline"
                onClick={() => api.post("/notifications/read", []).then(() => setTick((x) => x + 1))}
              >
                {t("common.markAllRead")}
              </button>
            )}
          </div>
          <ul className="max-h-80 overflow-y-auto">
            {notes.data?.items.length ? (
              notes.data.items.map((n) => (
                <li key={n.id} className={cx("border-t border-line-2", !n.read_at && "bg-accent-soft/50")}>
                  <Link
                    href={n.link ?? "#"}
                    onClick={() => !n.read_at && api.post("/notifications/read", [n.id]).then(() => setTick((x) => x + 1))}
                    className="block px-4 py-2.5 hover:bg-line-2"
                  >
                    <div className="text-[13px] font-medium">{n.title}</div>
                    {n.body && <div className="truncate text-[12px] text-ink-2">{n.body}</div>}
                    <div className="mt-0.5 text-[11px] text-ink-3">{fmtDateTime(n.created_at)}</div>
                  </Link>
                </li>
              ))
            ) : (
              <li className="px-4 pb-4 text-[13px] text-ink-3">{t("common.noNotifications")}</li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
