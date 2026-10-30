"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Button, Card, EmptyState, ErrorState, Loading, PageHeader, ToneBadge, cx } from "@/components/ui";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import type { MessageKey } from "@/lib/messages";
import { PRIORITY_TONE, WO_STATUS_TONE } from "@/lib/status";
import type { WorkOrder } from "@/lib/types";

const dayKey = (d: Date) => `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;

/** Week board: technicians x days, plus unscheduled work orders. */
export default function SchedulePage() {
  const { t, fmtDate } = useI18n();
  const [weekStart, setWeekStart] = useState(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
    return d;
  });
  const days = useMemo(() => Array.from({ length: 7 }, (_, i) => new Date(weekStart.getFullYear(), weekStart.getMonth(), weekStart.getDate() + i)), [weekStart]);
  const end = new Date(weekStart.getTime() + 7 * 86400_000);
  const scheduled = useResource(() => api.get<WorkOrder[]>("/lab/work-orders", {
    status: ["SCHEDULED", "IN_PROGRESS", "COMPLETED"], start: weekStart.toISOString(), end: end.toISOString(),
  }), [weekStart.getTime()]);
  const pending = useResource(() => api.get<WorkOrder[]>("/lab/work-orders", { status: ["PENDING"] }));

  const techs = useMemo(() => {
    const m = new Map<string, string>();
    for (const w of scheduled.data ?? []) if (w.technician_id) m.set(w.technician_id, w.technician_name ?? "—");
    return [...m.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  }, [scheduled.data]);
  const cell = (tech: string, d: Date) => (scheduled.data ?? []).filter((w) => {
    if (w.technician_id !== tech || !w.scheduled_start || !w.scheduled_end) return false;
    const s = new Date(w.scheduled_start), e = new Date(w.scheduled_end);
    const dayStart = d.getTime(), dayEnd = dayStart + 86400_000;
    return s.getTime() < dayEnd && e.getTime() > dayStart;
  });
  const today = dayKey(new Date());
  const time = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  return (
    <>
      <PageHeader title={t("lab.schedule.title")} actions={
        <div className="flex gap-2">
          <Button onClick={() => setWeekStart(new Date(weekStart.getTime() - 7 * 86400_000))}>‹</Button>
          <Button onClick={() => { const d = new Date(); d.setHours(0, 0, 0, 0); d.setDate(d.getDate() - ((d.getDay() + 6) % 7)); setWeekStart(d); }}>{t("common.today")}</Button>
          <Button onClick={() => setWeekStart(new Date(weekStart.getTime() + 7 * 86400_000))}>›</Button>
        </div>}>
        <p className="mt-1 text-[13px] text-ink-2">{t("lab.schedule.week")} {fmtDate(days[0].toISOString())} – {fmtDate(days[6].toISOString())}</p>
      </PageHeader>
      {scheduled.error ? <ErrorState error={scheduled.error} onRetry={scheduled.reload} /> : !scheduled.data ? <Loading /> : (
        <Card flush>
          {techs.length === 0 ? <EmptyState>{t("lab.wo.empty")}</EmptyState> : (
            <div className="overflow-x-auto">
              <table className="data-table min-w-[900px] table-fixed">
                <thead>
                  <tr>
                    <th className="w-40">{t("lab.wo.technician")}</th>
                    {days.map((d, i) => (
                      <th key={i} className={cx(dayKey(d) === today && "text-accent")}>
                        {t(`lab.weekday.${i + 1}` as MessageKey)} {d.getDate()}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {techs.map(([id, name]) => (
                    <tr key={id}>
                      <td className="align-top font-medium">{name}</td>
                      {days.map((d, i) => (
                        <td key={i} className="align-top">
                          <div className="space-y-1">
                            {cell(id, d).map((w) => (
                              <Link key={w.id} href={`/laboratory/work-orders/${w.id}`}
                                className={cx("block rounded border-l-2 px-1.5 py-1 text-[11px] hover:brightness-95",
                                  w.status === "COMPLETED" ? "border-ok bg-ok-soft" : w.overdue ? "border-bad bg-bad-soft" : "border-info bg-info-soft")}>
                                <div className="font-mono font-semibold">{w.work_order_code}</div>
                                <div className="truncate text-ink-2">{w.service_name}</div>
                                <div className="tabular text-ink-3">{time(w.scheduled_start!)}–{time(w.scheduled_end!)}</div>
                              </Link>
                            ))}
                          </div>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
      <Card flush title={t("lab.schedule.unscheduled")} className="mt-4">
        {!pending.data?.length ? <p className="px-4 py-4 text-[13px] text-ink-3">{t("lab.wo.empty")}</p> : (
          <table className="data-table">
            <tbody>
              {pending.data.map((w) => (
                <tr key={w.id}>
                  <td><Link href={`/laboratory/work-orders/${w.id}`} className="font-mono font-semibold text-accent hover:underline">{w.work_order_code}</Link></td>
                  <td>{w.service_name}</td>
                  <td className="tabular">{w.planned_hours} h</td>
                  <td className="tabular">{fmtDate(w.due_date)}</td>
                  <td><ToneBadge tone={PRIORITY_TONE[w.priority]}>{t(`lab.priority.${w.priority}`)}</ToneBadge></td>
                  <td><ToneBadge tone={WO_STATUS_TONE[w.status]}>{t(`lab.wostatus.${w.status}`)}</ToneBadge></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
