"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Card, Check, EmptyState, ErrorState, Loading, PageHeader, Select, ToneBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { PRIORITY_TONE, WO_STATUS_TONE } from "@/lib/status";
import type { WorkOrder } from "@/lib/types";

const STATUSES = ["PENDING", "SCHEDULED", "IN_PROGRESS", "COMPLETED", "CANCELLED"] as const;

export default function WorkOrdersPage() {
  return <Suspense fallback={<Loading />}><WorkOrders /></Suspense>;
}

function WorkOrders() {
  const { t, fmtDate, fmtDateTime } = useI18n();
  const params = useSearchParams();
  const [status, setStatus] = useState("OPEN");
  const [overdueOnly, setOverdueOnly] = useState(params.get("overdue") === "1");
  const list = useResource(() => api.get<WorkOrder[]>("/lab/work-orders", {
    status: status === "OPEN" ? ["PENDING", "SCHEDULED", "IN_PROGRESS"] : status ? [status] : undefined,
  }), [status]);
  const rows = (list.data ?? []).filter((w) => !overdueOnly || w.overdue);
  return (
    <>
      <PageHeader title={t("nav.labWorkOrders")} />
      <Card flush>
        <div className="flex flex-wrap items-center gap-3 border-b border-line p-3">
          <Select className="max-w-[260px]" value={status} onChange={(e) => setStatus(e.target.value)} aria-label={t("common.status")}>
            <option value="OPEN">{t("lab.kpi.open")}</option>
            <option value="">{t("common.status")}: {t("common.all")}</option>
            {STATUSES.map((s) => <option key={s} value={s}>{t(`lab.wostatus.${s}`)}</option>)}
          </Select>
          <Check label={t("lab.wo.overdue")} checked={overdueOnly} onChange={setOverdueOnly} />
        </div>
        {list.error ? <div className="px-4"><ErrorState error={list.error} onRetry={list.reload} /></div>
          : !list.data ? <div className="px-4"><Loading /></div>
          : rows.length === 0 ? <EmptyState>{t("lab.wo.empty")}</EmptyState>
          : (
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead><tr><th>{t("lab.wo.code")}</th><th>{t("lab.request.service")}</th><th>{t("common.part")}</th><th>{t("lab.wo.technician")}</th>
                  <th>{t("lab.wo.start")}</th><th>{t("lab.request.committed")}</th><th>{t("common.priority")}</th><th>{t("common.status")}</th></tr></thead>
                <tbody>
                  {rows.map((w) => (
                    <tr key={w.id}>
                      <td><Link href={`/laboratory/work-orders/${w.id}`} className="font-mono text-[13px] font-semibold text-accent hover:underline">{w.work_order_code}</Link>
                        <div className="font-mono text-[11px] text-ink-3">{w.request_code}</div></td>
                      <td>{w.service_name}</td>
                      <td className="font-mono text-[12px]">{w.part_number ?? "—"}</td>
                      <td className="text-[12px]">{w.technician_name ?? "—"}</td>
                      <td className="tabular text-[12px]">{w.scheduled_start ? fmtDateTime(w.scheduled_start) : "—"}</td>
                      <td className="tabular">{fmtDate(w.due_date)}{w.overdue && <div className="text-[11px] font-semibold text-bad">{t("lab.wo.overdue")}</div>}</td>
                      <td><ToneBadge tone={PRIORITY_TONE[w.priority]}>{t(`lab.priority.${w.priority}`)}</ToneBadge></td>
                      <td><ToneBadge tone={WO_STATUS_TONE[w.status]}>{t(`lab.wostatus.${w.status}`)}</ToneBadge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </Card>
    </>
  );
}
