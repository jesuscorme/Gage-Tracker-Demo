"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Button, Card, ErrorState, Loading, PageHeader, StatusDot, cx } from "@/components/ui";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import type { MessageKey } from "@/lib/messages";
import type { CalendarEvent, GageStatus } from "@/lib/types";

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

export default function CalendarPage() {
  const { t, lang } = useI18n();
  const [month, setMonth] = useState(() => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), 1); });

  // Monday-first grid covering the whole month.
  const days = useMemo(() => {
    const first = new Date(month);
    const offset = (first.getDay() + 6) % 7;
    const start = new Date(first.getFullYear(), first.getMonth(), 1 - offset);
    const count = Math.ceil((offset + new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate()) / 7) * 7;
    return Array.from({ length: count }, (_, i) => new Date(start.getFullYear(), start.getMonth(), start.getDate() + i));
  }, [month]);
  const range = { start: iso(days[0]), end: iso(days[days.length - 1]) };
  const events = useResource(() => api.get<CalendarEvent[]>("/calibrations/calendar", range), [range.start, range.end]);
  const byDay = useMemo(() => {
    const m = new Map<string, CalendarEvent[]>();
    for (const e of events.data ?? []) m.set(e.date, [...(m.get(e.date) ?? []), e]);
    return m;
  }, [events.data]);
  const today = iso(new Date());
  const locale = lang === "es" ? "es-MX" : "en-US";

  return (
    <>
      <PageHeader
        eyebrow={t("cal.title")}
        title={t("cal.calendar")}
        actions={
          <div className="flex items-center gap-2">
            <Button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))}>‹</Button>
            <Button onClick={() => { const d = new Date(); setMonth(new Date(d.getFullYear(), d.getMonth(), 1)); }}>{t("common.today")}</Button>
            <Button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))}>›</Button>
          </div>
        }
      >
        <p className="mt-1 text-[15px] font-medium capitalize text-ink-2">{month.toLocaleDateString(locale, { month: "long", year: "numeric" })}</p>
      </PageHeader>
      {events.error ? <ErrorState error={events.error} onRetry={events.reload} /> : !events.data ? <Loading /> : (
        <Card flush>
          <div className="grid grid-cols-7 border-b border-line bg-[#f7f8fa] text-center text-[11px] font-semibold uppercase tracking-wide text-ink-3">
            {[1, 2, 3, 4, 5, 6, 7].map((d) => <div key={d} className="py-2">{t(`lab.weekday.${d}` as MessageKey)}</div>)}
          </div>
          <div className="grid grid-cols-7">
            {days.map((d) => {
              const key = iso(d);
              const list = byDay.get(key) ?? [];
              const out = d.getMonth() !== month.getMonth();
              return (
                <div key={key} className={cx("min-h-[96px] border-b border-r border-line-2 p-1.5", out && "bg-line-2/40")}>
                  <div className={cx("mb-1 text-right text-[11px] tabular", key === today ? "font-bold text-accent" : out ? "text-ink-3" : "text-ink-2")}>
                    {d.getDate()}
                  </div>
                  <div className="space-y-0.5">
                    {list.slice(0, 4).map((e, i) =>
                      e.kind === "activity" ? (
                        <Link key={i} href={`/calibrations/${e.id}`} title={`${e.code} · ${t(`cal.status.${e.status}` as MessageKey)}`}
                          className={cx("block truncate rounded px-1 py-0.5 text-[10.5px] font-medium",
                            e.status === "RELEASED" ? "bg-ok-soft text-ok" : "bg-info-soft text-info")}>
                          {e.gage_code} · {t(`cal.type.${e.activity_type}` as MessageKey).split(" ")[0]}
                        </Link>
                      ) : (
                        <Link key={i} href={`/gages/${e.gage_id}`} className="flex items-center gap-1 truncate rounded px-1 py-0.5 text-[10.5px] text-ink-2 hover:bg-line-2">
                          <StatusDot status={e.status as GageStatus} /> {t("cal.calendar.due")} {e.gage_code}
                        </Link>
                      ),
                    )}
                    {list.length > 4 && <div className="px-1 text-[10px] text-ink-3">+{list.length - 4}</div>}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </>
  );
}
